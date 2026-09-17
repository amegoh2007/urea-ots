# -*- coding: utf-8 -*-
"""Build the OV overlay arrays for the seven 2026-09 slides.

One element per shape the background gives up: every DCS tag textbox, every
commented bargraph slot / nav block / pump icon / XV icon / override square.
Geometry is the slide's own (EMU -> 1366x720 stage); bindings are carried over
from the existing overlays.js by tag so no live value is lost in the re-seed.
"""
import json, re

B = json.load(open('binds_all.json'))

# --- binds the harvest could not supply (new tags on the 2026-09 slides) -------------
EXTRA = {
 'LT-323504': {'bind': 'RECIRC_323.D002.LI_323504', 'u': '%', 'dec': 1,
               'note': '323D002 passive compartment II - indication and alarms only, normally 0 %'},
 'FV-323418': {'bind': 'LPCC_3232.C005.FIC_323418.op', 'u': '%', 'dec': 1},
 'LT-324501': {'bind': 'EVAP_324.E003.LIC_324501.pv', 'mode': 'EVAP_324.E003.LIC_324501.mode',
               'u': '%', 'dec': 1,
               'note': '324F003 product level; LIC-324501 A/B is the exclusive discharge-route selector'},
 'PY-324701': {'bind': 'EVAP_324.E003.AY_324701', 'u': 'wt%', 'dec': 1,
               'note': '324F003 product concentration soft-sensor (VLE inversion of PT-324204 / TIC-324002); backend key AY_324701'},
 'PIC-335201': {'bind': 'EVAP_324.E003.PIC_335201', 'u': 'BAR G', 'dec': 2,
                'note': '335 melt-header pressure (battery-limit boundary); above the LV-324501B relief setting the B route is forced'},
 # 2026-09-15 16:44: 323-1 retagged TT-323103 -> TT-323008 on the 323D002 readout.  Both
 # RECIRC_323.D002.T_C (the old TT-323103 leaf) and .TI_323008 publish round(s.r323_d002_T, 1),
 # the same number, so bind the tag-named leaf and nothing is lost by TT-323103 going away.
 'TT-323008': {'bind': 'RECIRC_323.D002.TI_323008', 'u': 'C', 'dec': 1,
               'note': '323D002 Comp-I bulk temperature (TAL: a falling tank walks the 80 % liquor toward crystallisation and blocks the 323P003 suction)'},
 # 2026-09-15: the packet published the 323E003 shell-liquid temperature as TT_323003 while
 # 323-2 labels that instrument TT-323006.  Key renamed in main.py; this row binds the box.
 'TT-323006': {'bind': 'LPCC_3232.E003.TT_323006', 'u': 'C', 'dec': 1,
               'note': '323E003 shell liquid temperature (hold 74 C); packet key was TT_323003 until 2026-09-15'},
}
for k, v in EXTRA.items():
    B.setdefault(k, {}).update(v)

# --- tags the slide prints wrong: {slide-name: {printed-id: corrected}} --------------
# pump icons the deck never annotated: {slide: {shape-id: pump tag}}.  Same picture as the
# commented pumps on the same slide, and the drawing labels them right beside the symbol.
ADD_PUMP = {
 '328-2': {119: '328P003A', 120: '328P003B'},
}

RETAG = {}                       # empty: the 2026-09-15 deck fixed 328-1 shape 214, which had
                                 # printed LIC-328503 on the 328C003 leg whose own bargraph
                                 # comment reads LIC-328504.  Same revision retagged the second
                                 # TT-328007 (shape 181) to TT-328009, its real tag.

# Slide-centre nudges.  An .ov.ind is sized by its VALUE, not by the label it replaced, so a
# few boxes render wider than the hole in the background and clip a neighbour.  These are the
# only three on the seven screens; each moves the box the minimum needed to clear, and the
# reason is recorded so a re-seed does not silently undo it.  {slide: {tag: (x, y)}}
NUDGE = {
 '323-2': {
   'PIC-323203': (1183, 38),   # 88.5 px wide vs a 78.9 px label -> clipped the 323F004 nav block
   'SIC-323901': (120, 578),   # cleared the 323P001A pump icon (below) and the 'A' letter (right)
   'SIC-323902': (266, 578),   # cleared the 323P001B pump icon (below) and the 'B' letter (left)
 },
}

# a ratio master's MV is a flow, not the ratio unit: {tag: (unit, decimals)}
PANEL_MV = {'FFIC-329401': ('KG/H', 1)}

TAGRE = re.compile(r'^[A-Z]{1,4}[A-Z]?-?\d{6}[A-Z]?(/[AB])?$')
PANEL = re.compile(r'^([A-Z]{2,4}-\d{6})\s+(SP|MV)$')


def norm(t):
    return re.sub(r'\s+', '', (t or '').upper())


def etype(tag):
    return 'avalve' if re.match(r'^(PV|LV|FV|TV)-', tag) else 'ind'


def slug(tag, used):
    s = re.sub(r'[^a-z0-9]', '', tag.lower())
    k, i = s, 2
    while k in used:
        k = s + str(i)
        i += 1
    used.add(k)
    return k


def build(name):
    S = json.load(open(name + '_shapes.json'))
    retag = RETAG.get(name, {})
    addp = ADD_PUMP.get(name, {})
    nudge = NUDGE.get(name, {})
    used, els, strip = set(), [], []
    for r in S:
        txt = (r.get('text') or '').strip()
        cmt = ' | '.join(r.get('COMMENT', []))
        px, wh = r.get('px'), r.get('wh')
        sid = int(r['id']) if str(r['id']).isdigit() else -1
        if not px:
            continue

        # --- nav block: "LINK TO PAGE 324-1B" ---
        m = re.search(r'link\s+to\s+page\s+([0-9]{3}-[0-9]+[bB]?)', cmt, re.I)
        if m:
            pg = m.group(1).lower()
            if pg == name:                      # deck links GRANULATION back to its own page:
                continue                        # a no-op hotspot, so leave the block static
            label = re.sub(r'\s+', ' ', txt) or pg
            els.append({'k': slug('nav' + pg + label, used), 't': 'nav',
                        'x': round(px[0]), 'y': round(px[1]),
                        'w': round(wh[0]), 'h': round(wh[1]),
                        'tag': label + ' -> ' + pg, 'goto': 'screen-' + pg})
            strip.append(sid)
            continue

        # --- bargraph slot: "LIC-323501 dynamic vertical display bar" ---
        m = re.search(r'\b([A-Z]{1,3}-\d{6})\b', cmt.upper())
        if m and re.search(r'bar', cmt, re.I):
            tg = m.group(1)
            p = B.get(tg, {})
            e = {'k': slug('bar' + tg, used), 't': 'bar',
                 'x': round(px[0]), 'y': round(px[1]),
                 'w': round(wh[0]), 'h': round(wh[1]), 'tag': tg}
            if p.get('bind'):
                e['bind'] = p['bind']
            els.append(e)
            strip.append(sid)
            continue

        # --- pump icon: the comment is the pump tag (or the deck forgot to annotate it) ---
        m = re.match(r'^(\d{3}P\d{3}[AB])$', cmt.strip())
        pid = m.group(1) if m else addp.get(sid)
        if pid:
            e = {'k': slug('p' + pid, used), 't': 'pump',
                 'x': px[0], 'y': px[1], 'w': wh[0], 'h': wh[1], 'tag': pid}
            if r.get('rot'):
                e['rot'] = round(r['rot'])
            if r.get('flipH'):
                e['fx'] = True                      # PowerPoint mirrors the symbol inside its own
            if r.get('flipV'):                      # box BEFORE rotating it, so sizeIcon applies
                e['fy'] = True                      # the flip innermost to match that order
            if pid.endswith('B'):
                e['def'] = False                    # installed standby: drawn stopped
            els.append(e)
            strip.append(sid)
            continue

        # --- XV icon ---
        m = re.match(r'^(XV-\d{6})$', cmt.strip())
        if m:
            tg = m.group(1)
            p = B.get(tg, {})
            e = {'k': slug(tg, used), 't': 'xv',
                 'x': px[0], 'y': px[1], 'w': wh[0], 'h': wh[1], 'tag': tg}
            if r.get('rot'):
                e['rot'] = round(r['rot'])
            if r.get('flipH'):
                e['fx'] = True
            if r.get('flipV'):
                e['fy'] = True
            if p.get('bind'):
                e['bind'] = p['bind']
            e['cmd'] = tg.split('-')[1]
            els.append(e)
            strip.append(sid)
            continue

        # --- external-override square ---
        if re.search(r'override', cmt, re.I):
            m = re.search(r'(XV-\d{6})', cmt.upper())
            tg = m.group(1) if m else 'OVERRIDE'
            p = B.get(tg, {})
            e = {'k': slug('ovr' + tg, used), 't': 'ovrd',
                 'x': round(px[0]), 'y': round(px[1]),
                 'tag': 'EXT-OVR ' + tg, 'cmd': tg.split('-')[-1], 'latch': '22_1',
                 'note': 'external override on ' + tg
                         + '; lamp lit while the 22.1 steam-flood interlock is latched'}
            if p.get('bind'):
                e['xv'] = p['bind']
            els.append(e)
            strip.append(sid)
            continue

        # --- editable master setpoint ---
        if re.search(r'editable value', cmt, re.I):
            els.append({'k': slug('mastersp', used), 't': 'ind',
                        'x': round(px[0]), 'y': round(px[1]), 'tag': 'MASTER-SP',
                        'bind': 'STEAM_SYSTEM.MASTER_SP_329207.sp', 'u': 'BAR A', 'dec': 2,
                        'fp': 'MASTER_SP_329207',
                        'note': '4-bar header master setpoint; the A/B/C legs track it at +0.1 / 0 / -0.1'})
            strip.append(sid)
            continue

        if cmt:
            continue                                # any other annotation: leave the drawing alone

        # --- panel value box: "FFIC-329401 SP" / "FFIC-329401 MV" ---
        #     A ratio master's MV is its output, so MV reads the loop's `op` -- and for
        #     FFIC-329401 that output is a 931-steam flow in kg/h, not the T/M3 the ratio
        #     PV/SP carry.  Read-only: a 'FFIC-329401 SP' id would reach the backend as an
        #     unknown controller and be discarded, so neither box routes to a faceplate.
        m = PANEL.match(re.sub(r'\s+', ' ', txt.upper()))
        if m:
            tg, fld = m.group(1), m.group(2)
            p = B.get(tg, {})
            e = {'k': slug(tg + fld, used), 't': 'ind',
                 'x': round(px[0]), 'y': round(px[1]), 'tag': tg + ' ' + fld}
            if p.get('bind'):
                e['bind'] = re.sub(r'\.pv$', '.sp' if fld == 'SP' else '.op', p['bind'])
                for f in ('u', 'dec'):
                    if f in p:
                        e[f] = p[f]
                if fld == 'MV':
                    e['u'], e['dec'] = PANEL_MV.get(tg, (e.get('u', '%'), 1))
                    e['note'] = 'controller output of ' + tg + ' (read-only here)'
            els.append(e)
            strip.append(sid)
            continue

        # --- plain DCS tag label ---
        if txt and TAGRE.match(norm(txt)):
            tg = retag.get(sid, norm(txt))
            p = B.get(tg, {})
            e = {'k': slug(tg, used), 't': etype(tg),
                 'x': round(px[0]), 'y': round(px[1]), 'tag': tg}
            for f in ('bind', 'u', 'dec', 'mode', 'cas', 'face', 'fp', 'route', 'note'):
                if f in p:
                    e[f] = p[f]
            if tg.startswith('HV-') or tg.startswith('HIC-'):
                e['t'] = 'ind'
                if e.get('bind'):
                    e['face'] = 'hic'
                else:
                    e.pop('face', None)         # unbound hand valve: no CMD row -> no faceplate
            if sid in retag:
                e['note'] = ('the slide prints ' + norm(txt) + ' at this position; it labels the '
                             + 'leg whose bargraph is commented ' + tg + ' (slide typo)')
            els.append(e)
            strip.append(sid)
            continue
    for e in els:                                   # apply the collision nudges last
        if e['tag'] in nudge:
            e['x'], e['y'] = nudge[e['tag']]
    return els, strip


OUT = {}
for n in ['323-1', '323-2', '324-1', '324-1b', '328-1', '328-2', '329-1']:
    els, strip = build(n)
    bound = sum(1 for e in els if e.get('bind'))
    OUT[n] = {'els': els, 'strip': sorted(set(strip))}
    print('%-7s %3d overlays (%d bound, %d white), %d shapes stripped'
          % (n, len(els), bound, len(els) - bound, len(set(strip))))
json.dump(OUT, open('ov_build.json', 'w'), indent=1)
