"""Measure the car's top deck from Freenove's STEP: the plate a cover sits on,
the holes it can bolt to, and everything above it that must be cleared."""
import sys, json, math, time
t0=time.time()
def log(m): print(f"[{time.time()-t0:6.1f}s] {m}", flush=True)

from OCP.STEPControl import STEPControl_Reader
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_FACE
from OCP.TopoDS import TopoDS
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Plane, GeomAbs_Cylinder
from OCP.GProp import GProp_GProps
from OCP.BRepGProp import BRepGProp
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.IFSelect import IFSelect_ReturnStatus

src = sys.argv[1]
log("reading STEP")
r = STEPControl_Reader()
assert r.ReadFile(src) == IFSelect_ReturnStatus.IFSelect_RetDone
r.TransferRoots()
shape = r.OneShape()
log("transferred")

box = Bnd_Box(); BRepBndLib.Add_s(shape, box)
xa, ya, za, xb, yb, zb = box.Get()
log(f"bbox X {xa:.1f}..{xb:.1f}  Y {ya:.1f}..{yb:.1f}  Z {za:.1f}..{zb:.1f}")

UP = 1  # index of the vertical axis; confirmed Y-up (height 118.9 < length 213)
planes = {}      # rounded Y level -> total area of upward-facing planar faces
cyls = []        # vertical small cylinders: candidate M3 holes / screw shafts

exp = TopExp_Explorer(shape, TopAbs_FACE)
n = 0
while exp.More():
    f = TopoDS.Face_s(exp.Current()); exp.Next(); n += 1
    ad = BRepAdaptor_Surface(f)
    t = ad.GetType()
    props = GProp_GProps()
    if t == GeomAbs_Plane:
        pl = ad.Plane()
        d = pl.Axis().Direction()
        if abs(d.Y()) > 0.99:                       # horizontal face
            BRepGProp.SurfaceProperties_s(f, props)
            a = props.Mass()
            if a > 50:                              # ignore slivers
                lvl = round(pl.Location().Y(), 1)
                planes[lvl] = planes.get(lvl, 0.0) + a
    elif t == GeomAbs_Cylinder:
        cy = ad.Cylinder()
        ax = cy.Axis().Direction()
        rad = cy.Radius()
        if abs(ax.Y()) > 0.99 and 1.0 < rad < 2.6:
            fb = Bnd_Box(); BRepBndLib.Add_s(f, fb)
            _, y0, _, _, y1, _ = fb.Get()
            loc = cy.Location()
            cyls.append({"x": round(loc.X(), 2), "z": round(loc.Z(), 2),
                         "r": round(rad, 2), "y0": round(y0, 1), "y1": round(y1, 1)})
log(f"{n} faces scanned")

top = sorted(planes.items(), key=lambda kv: -kv[1])[:14]
print("\n  largest horizontal planes (Y level -> mm^2 of face area):")
for lvl, a in sorted(top, key=lambda kv: kv[0]):
    print(f"    Y = {lvl:7.1f}   area {a:9.0f}")

# Cluster the vertical small cylinders by (x,z) so a hole and the screw in it
# collapse to one mount point.
pts = []
for c in cyls:
    for p in pts:
        if abs(p["x"] - c["x"]) < 1.2 and abs(p["z"] - c["z"]) < 1.2:
            p["n"] += 1; p["ytop"] = max(p["ytop"], c["y1"]); p["r"] = max(p["r"], c["r"])
            break
    else:
        pts.append({"x": c["x"], "z": c["z"], "r": c["r"], "ytop": c["y1"], "n": 1})
print(f"\n  {len(cyls)} vertical small cylinders -> {len(pts)} distinct (x,z) locations")

json.dump({"bbox": [xa, ya, za, xb, yb, zb],
           "planes": sorted(planes.items()),
           "mounts": sorted(pts, key=lambda p: (-p["ytop"], p["x"]))},
          open(sys.argv[2], "w"), indent=1)
log(f"wrote {sys.argv[2]}")
