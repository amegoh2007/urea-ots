"""PPTX slide -> shape inventory for the image-backed HMI migration.

    python parse_slide.py 323-1 [324-1 ...]

Unzips each deck under ./pptx/<name>/ and writes ./<name>_shapes.json: one record per
shape with its absolute EMU box (group transforms resolved), the same box mapped to the
1366x720 stage, its rotation and mirror flags, and any PowerPoint comment attached to it.
The comments are what make the deck self-describing -- they carry the DCS tag for a
bargraph slot, the pump tag for an icon, and "LINK TO PAGE nnn-n" for a nav block.
"""
import sys, os, re, json, zipfile
import xml.etree.ElementTree as ET

SRC = r'D:/Work/Urea Simulation Docs/Equipment Drawing/UI Pages'

A='{http://schemas.openxmlformats.org/drawingml/2006/main}'
P='{http://schemas.openxmlformats.org/presentationml/2006/main}'
R='{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
P188='{http://schemas.microsoft.com/office/powerpoint/2018/8/main}'
AC='{http://schemas.microsoft.com/office/drawing/2013/main/command}'

SLD_W, SLD_H = 12192000, 6858000
STAGE_W, STAGE_H = 1366, 720

def txt(el):
    if el is None: return ''
    return ''.join(t.text or '' for t in el.iter(A+'t')).strip()

def get_xfrm(sp):
    x = sp.find('./'+P+'spPr/'+A+'xfrm')
    if x is None: x = sp.find('./'+P+'grpSpPr/'+A+'xfrm')
    if x is None: x = sp.find('./'+P+'xfrm')
    return x

def xf_vals(x):
    if x is None: return None
    off = x.find(A+'off'); ext = x.find(A+'ext')
    cho = x.find(A+'chOff'); che = x.find(A+'chExt')
    d = {'rot': int(x.get('rot') or 0), 'flipH': x.get('flipH'), 'flipV': x.get('flipV')}
    if off is not None: d['x'], d['y'] = int(off.get('x')), int(off.get('y'))
    if ext is not None: d['cx'], d['cy'] = int(ext.get('cx')), int(ext.get('cy'))
    if cho is not None: d['chx'], d['chy'] = int(cho.get('x')), int(cho.get('y'))
    if che is not None: d['chcx'], d['chcy'] = int(che.get('cx')), int(che.get('cy'))
    return d

def walk(node, ctx, out, depth=0):
    """ctx = (ox, oy, sx, sy) mapping child coords -> absolute EMU"""
    for child in node:
        tag = child.tag
        if tag == P+'grpSp':
            x = xf_vals(get_xfrm(child))
            nv = child.find('./'+P+'nvGrpSpPr/'+P+'cNvPr')
            gid = nv.get('id') if nv is not None else '?'
            gname = nv.get('name') if nv is not None else ''
            nctx = ctx
            if x and 'x' in x and 'chx' in x and x.get('chcx'):
                sx = x['cx']/x['chcx'] if x['chcx'] else 1
                sy = x['cy']/x['chcy'] if x['chcy'] else 1
                # absolute of group origin
                ax = ctx[0] + x['x']*ctx[2]; ay = ctx[1] + x['y']*ctx[3]
                nctx = (ax - x['chx']*sx*ctx[2], ay - x['chy']*sy*ctx[3], sx*ctx[2], sy*ctx[3])
            out.append({'kind':'grp','id':gid,'name':gname,'depth':depth})
            walk(child, nctx, out, depth+1)
        elif tag in (P+'sp', P+'pic', P+'cxnSp', P+'graphicFrame'):
            kind = tag.split('}')[1]
            nvpr = None
            for pfx in ('nvSpPr','nvPicPr','nvCxnSpPr','nvGraphicFramePr'):
                n = child.find('./'+P+pfx+'/'+P+'cNvPr')
                if n is not None: nvpr = n; break
            sid = nvpr.get('id') if nvpr is not None else '?'
            sname = nvpr.get('name') if nvpr is not None else ''
            cid = ''
            if nvpr is not None:
                ce = nvpr.find(A+'extLst/'+A+'ext/{http://schemas.microsoft.com/office/drawing/2014/main}creationId')
                if ce is not None: cid = ce.get('id')
            x = xf_vals(get_xfrm(child))
            rec = {'kind':kind,'id':sid,'name':sname,'cid':cid,'depth':depth,
                   'text':txt(child.find('./'+P+'txBody'))}
            if x and 'x' in x:
                ax = ctx[0] + x['x']*ctx[2]; ay = ctx[1] + x['y']*ctx[3]
                acx = x.get('cx',0)*ctx[2]; acy = x.get('cy',0)*ctx[3]
                rec['emu'] = [round(ax), round(ay), round(acx), round(acy)]
                rec['rot'] = x.get('rot', 0) / 60000.0
                if x.get('flipH'): rec['flipH'] = 1
                if x.get('flipV'): rec['flipV'] = 1
                rec['px'] = [round((ax+acx/2)*STAGE_W/SLD_W,1), round((ay+acy/2)*STAGE_H/SLD_H,1)]
                rec['wh'] = [round(acx*STAGE_W/SLD_W,1), round(acy*STAGE_H/SLD_H,1)]
                rec['tl'] = [round(ax*STAGE_W/SLD_W,1), round(ay*STAGE_H/SLD_H,1)]
            # picture rel
            b = child.find('./'+P+'blipFill/'+A+'blip')
            if b is not None: rec['embed'] = b.get(R+'embed')
            # shape geometry preset
            g = child.find('./'+P+'spPr/'+A+'prstGeom')
            if g is not None: rec['geom'] = g.get('prst')
            # fill color
            sf = child.find('./'+P+'spPr/'+A+'solidFill/'+A+'srgbClr')
            if sf is not None: rec['fill'] = '#'+sf.get('val')
            ln = child.find('./'+P+'spPr/'+A+'ln/'+A+'solidFill/'+A+'srgbClr')
            if ln is not None: rec['line'] = '#'+ln.get('val')
            # hyperlink
            hl = None
            if nvpr is not None:
                hl = nvpr.find(A+'hlinkClick')
            if hl is not None: rec['hlink'] = hl.get(R+'id') or hl.get('action','')
            out.append(rec)

def parse_comments(path):
    """returns {shapeId: [comment texts]}"""
    m = {}
    if not os.path.isdir(path): return m
    for f in os.listdir(path):
        if not f.endswith('.xml'): continue
        t = ET.parse(os.path.join(path,f)).getroot()
        for cm in t.iter(P188+'cm'):
            body = ''.join(x.text or '' for x in cm.iter(A+'t')).strip()
            ids = []
            for mk in ('spMk','picMk','cxnSpMk','grpSpMk','graphicFrameMk'):
                for e in cm.iter(AC+mk):
                    ids.append(e.get('id'))
            for i in ids:
                m.setdefault(i, []).append(body)
    return m

def rels(path):
    m={}
    if os.path.exists(path):
        t=ET.parse(path).getroot()
        for r in t:
            m[r.get('Id')] = r.get('Target')
    return m

def unzip(d):
    dst = f'pptx/{d}'
    if os.path.isdir(dst):
        return
    os.makedirs(dst, exist_ok=True)
    zipfile.ZipFile(os.path.join(SRC, d + '.pptx')).extractall(dst)


for d in sys.argv[1:]:
  unzip(d)
  root = ET.parse(f'pptx/{d}/ppt/slides/slide1.xml').getroot()
  tree = root.find('./'+P+'cSld/'+P+'spTree')
  out=[]
  walk(tree, (0,0,1,1), out)
  cm = parse_comments(f'pptx/{d}/ppt/comments')
  rl = rels(f'pptx/{d}/ppt/slides/_rels/slide1.xml.rels')
  for r in out:
      if r['id'] in cm: r['COMMENT'] = cm[r['id']]
      if r.get('embed'): r['img'] = rl.get(r['embed'],'')
      if r.get('hlink') and r['hlink'] in rl: r['hlink_t']=rl[r['hlink']]
  json.dump(out, open(f'{d}_shapes.json','w'), indent=1)
  print(f'{d}: {len(out)} shapes, {len(cm)} commented ids')
