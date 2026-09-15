# -*- coding: utf-8 -*-
"""Delete from each slide exactly the shapes the overlay layer will redraw live.

The strip list is not hand-maintained: it is whatever gen_ov.py claimed, so the
background and the overlay array can never drift apart.
"""
import zipfile, os, json
import xml.etree.ElementTree as ET

SRC = r'D:/Work/Urea Simulation Docs/Equipment Drawing/UI Pages'
OUT = os.path.join(os.getcwd(), 'stripped')
os.makedirs(OUT, exist_ok=True)

P = '{http://schemas.openxmlformats.org/presentationml/2006/main}'
for pfx, uri in [('a', 'http://schemas.openxmlformats.org/drawingml/2006/main'),
                 ('r', 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'),
                 ('p', 'http://schemas.openxmlformats.org/presentationml/2006/main')]:
    ET.register_namespace(pfx, uri)

KINDS = (P + 'sp', P + 'pic', P + 'cxnSp', P + 'graphicFrame', P + 'grpSp')


def prune(node, ids, removed):
    for child in list(node):
        if child.tag not in KINDS:
            continue
        sid = None
        for p in ('nvSpPr', 'nvPicPr', 'nvCxnSpPr', 'nvGraphicFramePr', 'nvGrpSpPr'):
            n = child.find('./' + P + p + '/' + P + 'cNvPr')
            if n is not None:
                sid = n.get('id')
                break
        if sid and int(sid) in ids:
            node.remove(child)
            removed.add(int(sid))
            continue
        if child.tag == P + 'grpSp':
            prune(child, ids, removed)


BUILD = json.load(open('ov_build.json'))
for name in BUILD:
    ids = set(BUILD[name]['strip'])
    zin = zipfile.ZipFile(os.path.join(SRC, name + '.pptx'))
    root = ET.fromstring(zin.read('ppt/slides/slide1.xml'))
    removed = set()
    prune(root.find('./' + P + 'cSld/' + P + 'spTree'), ids, removed)
    new = ET.tostring(root, encoding='UTF-8', xml_declaration=True)
    dst = os.path.join(OUT, name + '.pptx')
    with zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED) as zout:
        for it in zin.infolist():
            data = zin.read(it.filename)
            if it.filename == 'ppt/slides/slide1.xml':
                data = new
            zout.writestr(it, data)
    zin.close()
    missing = sorted(ids - removed)
    print('%-7s removed %d/%d%s' % (name, len(removed), len(ids),
                                    ('  MISSING ' + str(missing)) if missing else ''))
