# -*- coding: utf-8 -*-
"""Harvest tag -> binding properties out of one or more overlays.js OV tables.

    python harvest_binds.py [source.js ...]

Sources are read in priority order and merged into binds_all.json; the first source to
supply a field keeps it. The default source is the live `frontend/overlays.js`.

Pass an older copy as a SECOND source when a drawing revision brings back a tag the live
table no longer carries:

    git show HEAD:frontend/overlays.js > ov_head.js
    python harvest_binds.py <live overlays.js> ov_head.js

That is how a binding survives a round trip through a slide revision that had dropped the
tag -- without it the tag comes back as an unbound white frame and the binding has to be
retyped from the packet.

Records span more than one line in the source, so scan by brace depth rather than by line:
a line-wise regex silently dropped every `mode:` that sat on a continuation line
(PIC-324202, PIC-323203, ...).
"""
import re, json, sys

LIVE = r'D:/Work/Urea Simulation/frontend/overlays.js'
SOURCES = sys.argv[1:] or [LIVE]
KEYS = ('bind', 'u', 'mode', 'note', 'face', 'fp', 'stream', 'cmd', 'id',
        'goto', 'xv', 'route', 'latch', 't')


def records(path):
    """Every `{ k: ... }` overlay literal in the file's OV table, one string each."""
    src = open(path, encoding='utf-8').read()
    start = src.index('const OV = {')
    body = src[start:src.index('\n  };', start)]

    # strip // comments outside string literals so a commented-out '{ k:' cannot open a record
    clean, i, n = [], 0, len(body)
    while i < n:
        c = body[i]
        if c == "'":
            j = i + 1
            while j < n and not (body[j] == "'" and body[j - 1] != '\\'):
                j += 1
            clean.append(body[i:j + 1]); i = j + 1; continue
        if c == '/' and i + 1 < n and body[i + 1] == '/':
            j = body.find('\n', i)
            i = n if j < 0 else j; continue
        clean.append(c); i += 1
    body = ''.join(clean)

    out, i = [], 0
    while True:
        m = re.search(r'\{\s*k:', body[i:])
        if not m:
            break
        s = i + m.start()
        d, j = 0, s
        while j < len(body):
            if body[j] == '{': d += 1
            elif body[j] == '}':
                d -= 1
                if d == 0:
                    break
            elif body[j] == "'":
                j += 1
                while j < len(body) and not (body[j] == "'" and body[j - 1] != '\\'):
                    j += 1
            j += 1
        out.append(body[s:j + 1])
        i = j + 1
    return out


def props_of(rec):
    props = {}
    for key in KEYS:
        mm = re.search(r"\b%s:\s*'((?:[^'\\]|\\.)*)'" % key, rec)
        if mm:
            props[key] = mm.group(1).replace("\\'", "'")
    mm = re.search(r'\bdec:\s*(\d+)', rec)
    if mm:
        props['dec'] = int(mm.group(1))
    if re.search(r'\bcas:\s*true', rec):
        props['cas'] = True
    return props


bytag, total = {}, 0
for path in SOURCES:
    recs = records(path)
    total += len(recs)
    for r in recs:
        t = re.search(r"tag:\s*'([^']+)'", r)
        if not t:
            continue
        tag = t.group(1).strip()
        props = props_of(r)
        # A tag is drawn on several screens and each copy carries a different subset of the
        # fields (one has the mode path, another the physics note).  Merge rather than pick:
        # the first BOUND record fixes bind/u/dec/t, every later record may fill a gap.
        old = bytag.setdefault(tag, {})
        if 'bind' in props and 'bind' not in old:
            old.update(props)
        else:
            for k, v in props.items():
                if k not in old and not (k == 'bind' and 'bind' in old):
                    old[k] = v

json.dump(bytag, open('binds_all.json', 'w'), indent=1, sort_keys=True)
print('%d source(s), %d records -> %d tags; %d bound, %d with mode'
      % (len(SOURCES), total, len(bytag),
         sum(1 for v in bytag.values() if 'bind' in v),
         sum(1 for v in bytag.values() if 'mode' in v)))
