"""EQUATION_AUDIT: close R-1 (the D002 pin) and R-4 (the ramp), and record the new R-5."""
import io


def patch(path, old, new):
    raw = io.open(path, encoding="utf-8", newline="").read()
    crlf = "\r\n" in raw
    s = raw.replace("\r\n", "\n")
    if s.count(old) != 1:
        raise SystemExit("FAILED %s: %d matches for %r" % (path, s.count(old), old[:70]))
    s = s.replace(old, new)
    if crlf:
        s = s.replace("\n", "\r\n")
    io.open(path, "w", encoding="utf-8", newline="").write(s)
    print("patched", path)


patch("EQUATION_AUDIT.md",
      "## R-2 — what already rippled correctly",
      """## R-5 — the ramp's root cause, and what closing it unlocked (2026-07-23) — **R-1 and R-4 CLOSED**

R-4 was localised by walking the operator-supplied stream map with every node instrumented:
207 → 208 → 301/311 → 313 → 302/314 → 319 → 317. The stripper bottoms feeding 323C003 are **bit-flat
for 6 h** while `w_c003` falls at −0.0041 pp/h, so nothing rides in on the feed — the ramp is *born*
in the stage. A CSTR with a 2-minute residence and constant inputs cannot ramp for 14 hours, so an
input had to be moving, and it was the boil-up: falling 5.97 kg/h per hour, perfectly linearly.

**Root cause — an open-loop temperature integrator.** Three stages take the energy-limited branch
`m_vap = M_DES·(q_avail/Q_DES)`, and each one's latent constant is back-solved from that same design
duty, `λ = Q_DES/(M_DES/3600)`. Together they give

    P = q_avail − m_vap·λ/3600 = q_avail·(1 − M_DES·λ/(3600·Q_DES)) = q_avail·(1 − 1) = 0

*identically*, at every load. The stage temperature had no input at all; the controller was
integrating against zero gain and walked its steam valve down forever, at a rate independent of `dt`
because a velocity increment is Kc·(dt/Ti)·err. That is the tick-invariance that made it look like a
model property. It was one-sided — hence monotone — because the composition-split branch caps the
other direction.

**Fix:** the bubble-point relaxation 323F004 already used, so `dT/dt = (T_bub − T)/τ`. 323C003's
bubble point rides the live column pressure; 323F010's rides **composition**, via Raoult on water,
which is the real physics of a fixed-vacuum evaporator and makes TIC-323012 the concentration
controller it is on the plant. Result: the least-squares slope at every 323 node is now exactly 0.0
over the second half of a 6 h run. Full write-up and the Raoult validation table: TECH_DEBT TD-014.
324E001/324E003 carry the same identity and are **not** fixed — TD-015, blocked on retuning two
controllers that were tuned against a zero-gain plant.

**R-1 closed as a consequence.** The only argument for keeping the 323D002 strength pin was that its
inlet was drifting. It is not any more, so the pin is gone: `s.w_d002` is a plain `sol_advance` and
the tank tracks 323F010 with its own residence-time lag. The last composition-blind node between the
reactor and the evaporators is open, and a C2 violation (+0.600 kg of urea fabricated per 1000 kg of
holdup per call) goes with it. The vessel was also rebuilt to its real two-compartment topology with
the field tie-in spool — see TD-013.

## R-2 — what already rippled correctly""")

print("done")
