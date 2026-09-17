# -*- coding: utf-8 -*-
"""Render ov_build.json into the OV literal blocks that go into frontend/overlays.js."""
import json

OUT = json.load(open('ov_build.json'))

ORDER = ['k', 't', 'x', 'y', 'w', 'h', 'rot', 'fx', 'fy', 'tag', 'bind', 'u', 'dec', 'mode', 'cas',
         'face', 'fp', 'cmd', 'id', 'xv', 'latch', 'goto', 'route', 'def', 'stream', 'note']

HDR = {
 '323-1':  ('323-1  LP RECIRCULATION & PRE-EVAPORATION',
            'roots RECIRC_323 (323C003 rect. column / 323F004 flash / 323F010 pre-evap / 323D002 tank).'),
 '323-2':  ('323-2  LP RECIRCULATION 2  (323D001 / 323E003 / 323E011 / 323C005)',
            'root LPCC_3232, with DESORB_328.D001 and 328C002 cross-refs drawn on this screen.'),
 '324-1':  ('324-1  EVAPORATION STAGE 1  (324E001 vacuum evaporator / 324F001 separator)',
            'root EVAP_324.E001; cross-refs RECIRC_323.D002 (feed) and .F010 (pre-evap).'),
 '324-1b': ('324-1b  EVAPORATION STAGE 2  (324E003 deep-vacuum evaporator / 324F003) + 335 tie-in',
            'root EVAP_324.E003; the Unit-335 finishing side is unmodelled -> white frames.'),
 '328-1':  ('328-1  DESORPTION  (328C002 / 328C003 hydrolyser / 328C004 / 328D001)',
            'root DESORB_328, with ABSORB_328.D003 and LPCC_3232.E003 cross-refs.'),
 '328-2':  ('328-2  ABSORPTION  (322C001 GCB absorber / 328D003 collection tank)',
            'root ABSORB_328 (C001 absorber / D003 collection tank).'),
 '329-1':  ('329-1  UREA STEAM SYSTEM  (25 bar BL / 329D005 / 329D009 / 322D001A/B 4 bar)',
            'root STEAM_SYSTEM; every 322E00x consumer links back to 322-1.'),
}

SECT = [('ind', 'indicators, controllers and modulating-valve openings'),
        ('avalve', None),
        ('bar', 'level bargraphs (fill height = bound level, 0-100 %)'),
        ('pump', 'pumps: A duty (drawn running), B installed standby (drawn stopped)'),
        ('xv', 'block valves and external-override pushbuttons'),
        ('ovrd', None),
        ('nav', 'screen-nav hotspots (slide comment "LINK TO PAGE ...")')]


def lit(o):
    parts = []
    for f in ORDER:
        if f not in o:
            continue
        v = o[f]
        if isinstance(v, bool):
            parts.append(f + ': ' + ('true' if v else 'false'))
        elif isinstance(v, float):
            parts.append(f + ': ' + (str(int(v)) if v == int(v) else str(round(v, 2))))
        elif isinstance(v, int):
            parts.append(f + ': ' + str(v))
        else:
            parts.append(f + ": '" + str(v).replace('\\', '\\\\').replace("'", "\\'") + "'")
    return '{ ' + ', '.join(parts) + ' },'


def block(name):
    els = OUT[name]['els']
    title, sub = HDR[name]
    L = ['    // ============================ %s ============================' % title,
         '    // Seed geometry = the shape centres of UI Pages/%s.pptx, 12192000x6858000 EMU -> 1366x720' % name,
         '    // stage.  The background PNG is that slide with exactly these shapes deleted, so every',
         '    // overlay lands in the hole its own symbol left.  %s' % sub,
         "    'screen-%s': [" % name]
    done = set()
    for kind, cap in SECT:
        grp = [e for e in els if e['t'] == kind]
        if not grp:
            continue
        if cap:
            L.append('      // ---- %s ----' % cap)
        for e in sorted(grp, key=lambda e: (e['y'], e['x'])):
            L.append('      ' + lit(e))
            done.add(e['k'])
    for e in els:                                   # anything a section forgot
        if e['k'] not in done:
            L.append('      ' + lit(e))
    L.append('    ],')
    return '\n'.join(L)


with open('ov_blocks.txt', 'w', encoding='utf-8') as f:
    # file order, so the patch is a straight block-for-block swap
    for n in ['329-1', '323-1', '323-2', '328-1', '328-2', '324-1', '324-1b']:
        f.write(block(n) + '\n')
print('wrote ov_blocks.txt')
