"""Second pass: which holes go through the deck plate, and what stands on it."""
import sys, json, time
import numpy as np
t0=time.time()
def log(m): print(f"[{time.time()-t0:6.1f}s] {m}", flush=True)

from OCP.STEPControl import STEPControl_Reader
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_FACE
from OCP.TopoDS import TopoDS
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Cylinder
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.BRep import BRep_Tool
from OCP.TopLoc import TopLoc_Location
from OCP.IFSelect import IFSelect_ReturnStatus

DECK_TOP = 0.0          # measured: the 43,199 mm^2 plate spans Y -1.5 .. 0.0
PLATE_BOT = -1.5

r = STEPControl_Reader(); r.ReadFile(sys.argv[1]); r.TransferRoots()
shape = r.OneShape(); log("STEP loaded")

# --- holes through the deck plate -------------------------------------------
holes = []
exp = TopExp_Explorer(shape, TopAbs_FACE)
while exp.More():
    f = TopoDS.Face_s(exp.Current()); exp.Next()
    ad = BRepAdaptor_Surface(f)
    if ad.GetType() != GeomAbs_Cylinder: continue
    cy = ad.Cylinder()
    if abs(cy.Axis().Direction().Y()) < 0.99: continue
    rad = cy.Radius()
    if not (1.2 < rad < 2.4): continue
    fb = Bnd_Box(); BRepBndLib.Add_s(f, fb)
    _, y0, _, _, y1, _ = fb.Get()
    # a hole THROUGH the plate spans its full thickness
    if y0 <= PLATE_BOT + 0.35 and y1 >= DECK_TOP - 0.35:
        holes.append((round(cy.Location().X(), 2), round(cy.Location().Z(), 2), round(rad, 2)))

uniq = []
for x, z, rad in holes:
    if not any(abs(x-a) < 1.0 and abs(z-b) < 1.0 for a, b, _ in uniq):
        uniq.append((x, z, rad))
log(f"{len(uniq)} distinct holes through the deck plate")
for x, z, rad in sorted(uniq, key=lambda h: (round(h[1]), h[0])):
    print(f"    x={x:8.2f}  z={z:8.2f}  r={rad:.2f}  (M{rad*2:.0f} clearance)")

# --- what stands on the deck ------------------------------------------------
log("meshing at 1.5 mm to build an obstacle map")
BRepMesh_IncrementalMesh(shape, 1.5, False, 0.7, True)
pts = []
exp = TopExp_Explorer(shape, TopAbs_FACE)
while exp.More():
    f = TopoDS.Face_s(exp.Current()); exp.Next()
    loc = TopLoc_Location()
    tri = BRep_Tool.Triangulation_s(f, loc)
    if tri is None: continue
    trsf = loc.Transformation()
    for i in range(1, tri.NbNodes() + 1):
        p = tri.Node(i).Transformed(trsf)
        pts.append((p.X(), p.Y(), p.Z()))
P = np.array(pts); log(f"{len(P):,} mesh points")

above = P[P[:, 1] > DECK_TOP + 1.0]
log(f"{len(above):,} points stand above the deck")

CELL = 4.0
xs = np.arange(-80, 80.1, CELL); zs = np.arange(-96, 124.1, CELL)
H = np.zeros((len(zs), len(xs)))
ix = np.clip(((above[:, 0] + 80) / CELL).astype(int), 0, len(xs)-1)
iz = np.clip(((above[:, 2] + 96) / CELL).astype(int), 0, len(zs)-1)
np.maximum.at(H, (iz, ix), above[:, 1])

print("\n  height map above the deck (mm above deck top; '.' = clear)")
print("  rows = Z (front +Z at the BOTTOM), cols = X")
for j in range(len(zs) - 1, -1, -2):
    row = ""
    for i in range(0, len(xs), 2):
        h = max(H[j, i], H[j, min(i+1, len(xs)-1)])
        row += "." if h <= 0 else ("#" if h > 60 else ("+" if h > 25 else ("-" if h > 8 else "o")))
    print(f"  z={zs[j]:7.1f} |{row}|")
print("   legend: o<=8   -<=25   +<=60   #>60 mm above deck")

json.dump({"deck_top": DECK_TOP, "holes": uniq,
           "max_above": float(above[:, 1].max())},
          open(sys.argv[2], "w"), indent=1)
log("done")
