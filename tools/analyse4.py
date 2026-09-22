"""Fourth pass: the numbers the cover geometry actually depends on."""
import sys, json
import numpy as np
P = np.load(sys.argv[1]); DECK = 0.0
A = P[P[:, 1] > DECK + 0.8]

print("== 1. where can a wall come down to the deck? ==")
print("   band z -45..58 (between battery and mast); max height vs |x|")
band = A[(A[:, 2] > -45) & (A[:, 2] < 58)]
for xl in range(20, 76, 4):
    m = np.abs(band[:, 0]) > xl
    h = float(band[m, 1].max()) if m.any() else 0.0
    print(f"     |x| > {xl:2d} : tallest {h:6.1f} mm   ({m.sum():6,} pts)")

print("\n== 2. wheel tops: the ceiling a canopy must clear to overhang ==")
w = A[np.abs(A[:, 0]) > 45]
print(f"     |x|>45: {len(w):,} pts, y {w[:,1].min():.1f}..{w[:,1].max():.1f} mm above deck")
for zl, zh in ((-95, -20), (-20, 40), (40, 120)):
    s = w[(w[:, 2] >= zl) & (w[:, 2] < zh)]
    if len(s): print(f"       z {zl:4d}..{zh:4d}: tallest {s[:,1].max():5.1f} mm  x {abs(s[:,0]).min():.1f}..{abs(s[:,0]).max():.1f}")

print("\n== 3. the camera head, and what it sweeps when it pans ==")
head = A[(A[:, 2] > 60) & (A[:, 1] > 45)]
print(f"     head (z>60, y>45): x {head[:,0].min():6.1f}..{head[:,0].max():5.1f}"
      f"  y {head[:,1].min():5.1f}..{head[:,1].max():5.1f}  z {head[:,2].min():6.1f}..{head[:,2].max():6.1f}")
# The pan axis is vertical through the mast centre. Estimate it as the centroid
# of the mast's lower structure in x, and the z of the narrowest waist.
low = A[(A[:, 2] > 60) & (A[:, 1] > 20) & (A[:, 1] < 40)]
print(f"     mast below the head: x {low[:,0].min():6.1f}..{low[:,0].max():5.1f}  z {low[:,2].min():6.1f}..{low[:,2].max():6.1f}")
for zc in range(66, 96, 3):
    d = np.hypot(head[:, 0] - 0.0, head[:, 2] - zc)
    print(f"       if the pan axis were x=0 z={zc}: head sweeps r={d.max():5.1f} mm"
          f"  -> reaches back to z={zc - d.max():6.1f}")

print("\n== 4. clear vertical columns on the deck (candidate feet) ==")
xs = np.arange(-70, 70.1, 5.0); zs = np.arange(-85, 110.1, 5.0)
clear = []
for x in xs:
    for z in zs:
        d = np.hypot(A[:, 0] - x, A[:, 2] - z)
        if not (d < 6.0).any():
            clear.append((float(x), float(z)))
print(f"     {len(clear)} grid points with nothing within 6 mm above the deck")
byz = {}
for x, z in clear: byz.setdefault(z, []).append(x)
for z in sorted(byz):
    xs_ = sorted(byz[z])
    if len(xs_) >= 2 and -60 < z < 80:
        print(f"       z={z:6.1f}: x = {', '.join(f'{v:.0f}' for v in xs_)}")
json.dump({"clear_columns": clear}, open(sys.argv[2], "w"))
