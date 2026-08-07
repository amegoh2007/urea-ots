"""Process historian for the Urea OTS.

Records every numeric and boolean leaf of the WebSocket packet from process start, so a
trend pen can be backfilled with past data instead of starting blank the moment an
operator opens it.

Design notes (see docs/superpowers/specs/2026-08-07-trend-system-design.md):

* **Columnar with a shared time index.** Every path is sampled on the same tick, so the
  two timestamp arrays are held once for the whole ring rather than once per path.
* **Plant-time cadence.** Sampling is driven by ``t_sim`` (the physics clock), not wall
  clock, so a 1-hour trend always covers one hour of plant behaviour whether the sim runs
  at 1x (SLOW) or 60x (FAST).
* **Fixed-capacity circular buffers over ``array('f')``.** A deque of Python floats costs
  roughly 8x the memory for the same data and would push this past 300 MB.
* **``STREAMS`` excluded.** It is 2346 of the packet's 3213 numeric leaves and holds
  composition tables, which are read through the stream popup rather than trended. No
  bound indicator resolves into that subtree (verified: 217/217 resolve elsewhere).

Threading: writes happen in ``sim_task`` and reads in the REST handlers, both on the same
asyncio event loop, so the synchronous sections below cannot interleave. No lock needed.
"""

from array import array
from math import isnan

NAN = float("nan")

# Top-level packet keys never logged. Composition tables, not instruments.
PATH_EXCLUDE = ("STREAMS",)

# ring name -> (sample period in PLANT seconds, capacity in samples)
#   fast: 1 s x 3600 = 1 h   -> serves the 1m / 5m / 30m / 1h spans at full resolution
#   slow: 10 s x 2880 = 8 h  -> serves the 2h / 4h / 8h spans
RINGS = (("fast", 1.0, 3600), ("slow", 10.0, 2880))


def flatten(pkt, prefix="", out=None):
    """Flatten a packet to {dot.path: float}. Booleans become 0.0/1.0.

    Excluded top-level subtrees are skipped whole, so their cost is one dict lookup
    rather than a walk of ~2300 leaves.
    """
    if out is None:
        out = {}
    if isinstance(pkt, dict):
        for k, v in pkt.items():
            path = f"{prefix}.{k}" if prefix else str(k)
            if not prefix and k in PATH_EXCLUDE:
                continue
            flatten(v, path, out)
    elif isinstance(pkt, bool):
        out[prefix] = 1.0 if pkt else 0.0
    elif isinstance(pkt, (int, float)):
        out[prefix] = float(pkt)
    return out


class Ring:
    """One fixed-capacity circular buffer sampled every ``period`` plant-seconds."""

    def __init__(self, name, period, capacity):
        self.name = name
        self.period = float(period)
        self.cap = int(capacity)
        self.t_sim = array("d", bytes(8 * self.cap))
        self.t_wall = array("d", bytes(8 * self.cap))
        self.cols = {}          # path -> array('f') of length cap
        self.cursor = 0         # next slot to write
        self.count = 0          # samples written, saturating at cap
        self.next_due = None    # plant time of the next sample

    # ---- write side ----

    def _column(self, path):
        col = self.cols.get(path)
        if col is None:
            # A path that appears mid-run is NaN-padded, so its history correctly reads
            # "no data" for the period before it existed rather than a misleading zero.
            col = array("f", [NAN]) * self.cap
            self.cols[path] = col
        return col

    def due(self, t_sim):
        return self.next_due is None or t_sim >= self.next_due

    def write(self, flat, t_sim, t_wall):
        i = self.cursor
        self.t_sim[i] = t_sim
        self.t_wall[i] = t_wall
        for path, val in flat.items():
            self._column(path)[i] = val
        # Paths absent from this sample keep whatever the slot held one lap ago, which
        # would be a stale value from ~1 h back. Blank them instead.
        if len(self.cols) != len(flat):
            for path, col in self.cols.items():
                if path not in flat:
                    col[i] = NAN
        self.cursor = (i + 1) % self.cap
        self.count = min(self.count + 1, self.cap)
        self.next_due = t_sim + self.period

    # ---- read side ----

    def order(self):
        """Slot indices oldest to newest."""
        if self.count < self.cap:
            return range(0, self.count)
        return [(self.cursor + n) % self.cap for n in range(self.cap)]

    def span_covered(self):
        """Plant seconds between the oldest and newest retained sample."""
        idx = self.order()
        if len(idx) < 2:
            return 0.0
        first = idx[0] if isinstance(idx, list) else 0
        last = idx[-1] if isinstance(idx, list) else self.count - 1
        return self.t_sim[last] - self.t_sim[first]

    def window(self, span_s, now_sim):
        """Slot indices within ``span_s`` plant-seconds of ``now_sim``, oldest first."""
        cutoff = now_sim - span_s
        return [i for i in self.order() if self.t_sim[i] >= cutoff]


class Historian:
    def __init__(self, rings=RINGS):
        self.rings = [Ring(*r) for r in rings]

    # ---- write side ----

    def maybe_sample(self, pkt, t_sim, t_wall):
        """Sample every ring that is due. Called once per physics sub-step.

        The packet is flattened at most once per call, and only when some ring is
        actually due, so a SLOW tick that is not on a sample boundary costs two float
        comparisons.
        """
        due = [r for r in self.rings if r.due(t_sim)]
        if not due:
            return False
        flat = flatten(pkt)
        for ring in due:
            ring.write(flat, t_sim, t_wall)
        return True

    # ---- read side ----

    def pick_ring(self, span_s):
        """Finest ring whose retention covers ``span_s``; coarsest as fallback."""
        for ring in self.rings:
            if ring.period * ring.cap >= span_s:
                return ring
        return self.rings[-1]

    def query(self, paths, span_s, max_points=800):
        """Return ``span_s`` plant-seconds of history for ``paths``.

        Decimation keeps a min/max envelope so a spike between two output points still
        appears. Bucket boundaries are shared by every path, which is what lets all
        series keep a single shared time axis: each bucket emits two points, placed at
        the bucket's first and last timestamps, carrying the bucket's two extremes in
        the order they actually occurred.
        """
        ring = self.pick_ring(span_s)
        now_sim = self._now_sim(ring)
        idx = ring.window(span_s, now_sim) if now_sim is not None else []

        known = [p for p in paths if p in ring.cols]
        missing = [p for p in paths if p not in ring.cols]
        out = {
            "ring": ring.name,
            "period": ring.period,
            "span": span_s,
            "t_sim": [],
            "t_wall": [],
            "series": {p: [] for p in known},
            "missing": missing,
            "truncated": bool(idx) and ring.span_covered() < span_s * 0.999,
        }
        if not idx:
            return out

        buckets = self._buckets(idx, max_points)
        for chunk in buckets:
            out["t_sim"].append(ring.t_sim[chunk[0]])
            out["t_sim"].append(ring.t_sim[chunk[-1]])
            out["t_wall"].append(ring.t_wall[chunk[0]])
            out["t_wall"].append(ring.t_wall[chunk[-1]])
            for path in known:
                col = ring.cols[path]
                lo = hi = None
                lo_at = hi_at = 0
                for pos, i in enumerate(chunk):
                    v = col[i]
                    if isnan(v):
                        continue
                    if lo is None or v < lo:
                        lo, lo_at = v, pos
                    if hi is None or v > hi:
                        hi, hi_at = v, pos
                if lo is None:
                    out["series"][path].extend((None, None))
                elif lo_at <= hi_at:
                    out["series"][path].extend((lo, hi))
                else:
                    out["series"][path].extend((hi, lo))
        return out

    def paths(self):
        """Every logged path, with the ring that holds it."""
        seen = {}
        for ring in self.rings:
            for p in ring.cols:
                seen.setdefault(p, ring.name)
        return seen

    def stats(self):
        return {
            r.name: {
                "period": r.period,
                "capacity": r.cap,
                "samples": r.count,
                "paths": len(r.cols),
                "bytes": 4 * r.cap * len(r.cols) + 16 * r.cap,
            }
            for r in self.rings
        }

    # ---- internals ----

    @staticmethod
    def _now_sim(ring):
        if ring.count == 0:
            return None
        newest = (ring.cursor - 1) % ring.cap
        return ring.t_sim[newest]

    @staticmethod
    def _buckets(idx, max_points):
        """Split ``idx`` into at most ``max_points // 2`` contiguous chunks."""
        n_buckets = max(1, max_points // 2)
        if len(idx) <= n_buckets:
            return [[i] for i in idx]
        size = len(idx) / n_buckets
        chunks = []
        for b in range(n_buckets):
            lo = int(b * size)
            hi = int((b + 1) * size) if b < n_buckets - 1 else len(idx)
            if hi > lo:
                chunks.append(idx[lo:hi])
        return chunks
