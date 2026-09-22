import sys, time, os
t0 = time.time()
def log(m): print(f"[{time.time()-t0:6.1f}s] {m}", flush=True)

from OCP.STEPCAFControl import STEPCAFControl_Reader
from OCP.TDocStd import TDocStd_Document
from OCP.XCAFApp import XCAFApp_Application
from OCP.XCAFDoc import XCAFDoc_DocumentTool
from OCP.TCollection import TCollection_ExtendedString, TCollection_AsciiString
from OCP.TDF import TDF_LabelSequence
from OCP.BRep import BRep_Builder
from OCP.TopoDS import TopoDS_Compound
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.RWGltf import RWGltf_CafWriter
from OCP.TColStd import TColStd_IndexedDataMapOfStringString
from OCP.Message import Message_ProgressRange
from OCP.IFSelect import IFSelect_ReturnStatus

src, out = sys.argv[1], sys.argv[2]
deflection = float(sys.argv[3]) if len(sys.argv) > 3 else 0.6

log(f"reading {os.path.basename(src)} ({os.path.getsize(src)/1e6:.0f} MB)")
reader = STEPCAFControl_Reader()
reader.SetNameMode(True); reader.SetColorMode(True); reader.SetLayerMode(True)
if reader.ReadFile(src) != IFSelect_ReturnStatus.IFSelect_RetDone:
    log("FAILED to read"); sys.exit(1)
log("parsed; transferring into an XCAF document (colours + part names)")

app = XCAFApp_Application.GetApplication_s()
doc = TDocStd_Document(TCollection_ExtendedString("BinXCAF"))
app.NewDocument(TCollection_ExtendedString("BinXCAF"), doc)
if not reader.Transfer(doc):
    log("FAILED to transfer"); sys.exit(1)

tool = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
labels = TDF_LabelSequence(); tool.GetFreeShapes(labels)
log(f"{labels.Length()} top-level shape(s)")

builder = BRep_Builder(); comp = TopoDS_Compound(); builder.MakeCompound(comp)
for i in range(1, labels.Length() + 1):
    builder.Add(comp, tool.GetShape_s(labels.Value(i)))

box = Bnd_Box(); BRepBndLib.Add_s(comp, box)
xa, ya, za, xb, yb, zb = box.Get()
log(f"bounding box (mm): X {xb-xa:.1f}  Y {yb-ya:.1f}  Z {zb-za:.1f}")
log(f"  origin corner ({xa:.1f}, {ya:.1f}, {za:.1f})")

log(f"tessellating at {deflection} mm linear deflection — the slow part")
BRepMesh_IncrementalMesh(comp, deflection, False, 0.5, True)
log("meshed; writing glTF")

writer = RWGltf_CafWriter(TCollection_AsciiString(out), True)   # True = binary .glb
ok = writer.Perform(doc, TColStd_IndexedDataMapOfStringString(), Message_ProgressRange())
log(f"write {'ok' if ok else 'FAILED'} -> {out} ({os.path.getsize(out)/1e6:.1f} MB)" if ok else "write FAILED")
