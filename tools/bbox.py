"""Dump world-space bounding boxes of every leaf part in a STEP assembly (JSON)."""
import json, sys
from OCP.STEPCAFControl import STEPCAFControl_Reader
from OCP.TDocStd import TDocStd_Document
from OCP.TCollection import TCollection_ExtendedString
from OCP.XCAFDoc import XCAFDoc_DocumentTool
from OCP.TDF import TDF_Label
from OCP.collections import Sequence_TDF_Label as TDF_LabelSequence
from OCP.TDataStd import TDataStd_Name
from OCP.TopLoc import TopLoc_Location
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib

path, out = sys.argv[1], sys.argv[2]
doc = TDocStd_Document(TCollection_ExtendedString("doc"))
r = STEPCAFControl_Reader(); r.SetNameMode(True)
assert r.ReadFile(path) == 1
r.Transfer(doc)
st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())

def name(lab):
    a = TDataStd_Name()
    if lab.FindAttribute(TDataStd_Name.GetID_s(), a):
        return a.Get().ToExtString()
    return "?"

res = []
def walk(lab, loc, pathn):
    if st.IsAssembly_s(lab):
        comps = TDF_LabelSequence(); st.GetComponents_s(lab, comps)
        for i in range(1, comps.Length() + 1):
            c = comps.Value(i)
            ref = TDF_Label(); st.GetReferredShape_s(c, ref)
            walk(ref, loc.Multiplied(st.GetLocation_s(c)), pathn + [name(ref)])
    else:
        s = st.GetShape_s(lab).Moved(loc)
        b = Bnd_Box(); BRepBndLib.Add_s(s, b, True)
        if b.IsVoid(): return
        mn, mx = b.CornerMin(), b.CornerMax(); x0, y0, z0, x1, y1, z1 = mn.X(), mn.Y(), mn.Z(), mx.X(), mx.Y(), mx.Z()
        res.append({"path": "/".join(pathn), "bb": [round(v, 2) for v in (x0, y0, z0, x1, y1, z1)]})

roots = TDF_LabelSequence(); st.GetFreeShapes(roots)
for i in range(1, roots.Length() + 1):
    walk(roots.Value(i), TopLoc_Location(), [name(roots.Value(i))])
json.dump(res, open(out, "w"), indent=0)
print(len(res))
