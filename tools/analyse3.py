"""Third pass: exact numbers for the cover design, plus a cached point cloud
the fit tests reuse so they never have to re-read the 69 MB STEP."""
import sys, json, time
import numpy as np
t0=time.time()
def log(m): print(f"[{time.time()-t0:5.1f}s] {m}", flush=True)

from OCP.STEPControl import STEPControl_Reader
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_FACE
from OCP.TopoDS import TopoDS
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.BRep import BRep_Tool
from OCP.TopLoc import TopLoc_Location

DECK = 0.0
r = STEPControl_Reader(); r.ReadFile(sys.argv[1]); r.TransferRoots()
shape = r.OneShape(); log("STEP loaded")
BRepMesh_IncrementalMesh(shape, 1.0, False, 0.5, True); log("meshed")

pts = []
exp = TopExp_Explorer(shape, TopAbs_FACE)
while exp.More():
    f = TopoDS.Face_s(exp.Current()); exp.Next()
    loc = TopLoc_Location(); tri = BRep_Tool.Triangulation_s(f, loc)
    if tri is None: continue
    trsf = loc.Transformation()
    for i in range(1, tri.NbNodes() + 1):
        p = tri.Node(i).Transformed(trsf)
        pts.append((p.X(), p.Y(), p.Z()))
P = np.asarray(pts, dtype=np.float32)
np.save(sys.argv[2], P); log(f"cached {len(P):,} points -> {sys.argv[2]}")

A = P[P[:, 1] > DECK + 0.8]          # everything standing on the deck
out = {"deck_top": DECK, "n_points": int(len(P)), "max_above_deck": float(A[:,1].max())}

# A. how far out in X can a cover go before it meets a wheel?
log("A. wheel intrusion vs |x|")
for xlim in (40, 45, 50, 52, 55, 58, 60, 65, 70):
    m = np.abs(A[:, 0]) > xlim
    out[f"max_h_beyond_x{xlim}"] = float(A[m, 1].max()) if m.any() else 0.0
    print(f"    |x| > {xlim:3d} mm : {len(A[m]):7,} pts, tallest {out[f'max_h_beyond_x{xlim}']:6.1f} mm above deck")

# B. is each candidate mount hole actually reachable from above?
log("B. clearance around each deck hole (radius 7 mm)")
holes = json.load(open(sys.argv[3]))["holes"]
free = []
for x, z, rad in holes:
    d = np.hypot(A[:, 0] - x, A[:, 2] - z)
    near = A[d < 7.0]
    h = float(near[:, 1].max()) if len(near) else 0.0
    tag = "CLEAR" if h < 3.0 else f"blocked by {h:.0f} mm"
    print(f"    x={x:7.2f} z={z:7.2f} r={rad:.2f}  {tag}")
    if h < 3.0: free.append({"x": x, "z": z, "r": rad})
out["free_holes"] = free
log(f"   {len(free)} holes usable for standoffs")

# C. the front mast: ultrasonic + camera + pan/tilt
log("C. front mast envelope")
mast = A[(A[:, 2] > 60) & (A[:, 1] > 20)]
out["mast"] = {"x": [float(mast[:,0].min()), float(mast[:,0].max())],
               "y": [float(mast[:,1].min()), float(mast[:,1].max())],
               "z": [float(mast[:,2].min()), float(mast[:,2].max())]}
print(f"    x {out['mast']['x'][0]:7.1f}..{out['mast']['x'][1]:6.1f}"
      f"   y {out['mast']['y'][0]:6.1f}..{out['mast']['y'][1]:6.1f}"
      f"   z {out['mast']['z'][0]:6.1f}..{out['mast']['z'][1]:6.1f}")

# D. tallest thing in the middle of the deck (the Pi and its headers)
log("D. mid-deck stack height")
mid = A[(A[:, 2] > -30) & (A[:, 2] < 55)]
out["mid_deck_max_h"] = float(mid[:, 1].max())
print(f"    z -30..55 : tallest {out['mid_deck_max_h']:.1f} mm above deck")

# E. the back (battery holder)
back = A[A[:, 2] < -45]
out["back_max_h"] = float(back[:, 1].max())
print(f"    z < -45   : tallest {out['back_max_h']:.1f} mm above deck")

# F. deck plate outline, so the cover cannot overhang into thin air
plate = P[(P[:, 1] > -1.9) & (P[:, 1] < 0.2)]
out["deck_extent"] = {"x": [float(plate[:,0].min()), float(plate[:,0].max())],
                      "z": [float(plate[:,2].min()), float(plate[:,2].max())]}
print(f"    deck plate spans x {out['deck_extent']['x'][0]:.1f}..{out['deck_extent']['x'][1]:.1f}"
      f"  z {out['deck_extent']['z'][0]:.1f}..{out['deck_extent']['z'][1]:.1f}")

json.dump(out, open(sys.argv[4], "w"), indent=1)
log("done")
