import sys, json
import numpy as np
P = np.load(sys.argv[1]); DECK = 0.0
A = P[P[:, 1] > DECK + 0.8]

print("== wheels: exact z extents of anything above deck at |x| > 48 ==")
w = A[np.abs(A[:, 0]) > 48]
zz = np.sort(w[:, 2])
gaps = np.where(np.diff(zz) > 6)[0]
segs, s = [], 0
for gi in gaps:
    segs.append((zz[s], zz[gi])); s = gi + 1
segs.append((zz[s], zz[-1]))
for a, b in segs:
    m = w[(w[:, 2] >= a - .01) & (w[:, 2] <= b + .01)]
    print(f"   z {a:7.1f} .. {b:7.1f}  ({b-a:5.1f} mm)  |x| {np.abs(m[:,0]).min():5.1f}..{np.abs(m[:,0]).max():5.1f}"
          f"  tallest {m[:,1].max():5.1f}")

print("\n== deck plate outline: |x| of the plate edge vs z ==")
plate = P[(P[:, 1] > -1.9) & (P[:, 1] < 0.2)]
for z0 in range(-85, 116, 10):
    m = plate[(plate[:, 2] >= z0) & (plate[:, 2] < z0 + 10)]
    if len(m): print(f"   z {z0:5d}..{z0+10:4d}: |x|max {np.abs(m[:,0]).max():6.1f}")

print("\n== side-wall corridor: max height above deck in a 6 mm strip at each |x| ==")
band = A[(A[:, 2] > -62) & (A[:, 2] < 54)]
for xw in (44, 46, 48, 50, 52, 54):
    m = band[(np.abs(band[:, 0]) > xw - 3) & (np.abs(band[:, 0]) < xw + 3)]
    if len(m):
        zs = np.sort(m[:, 2])
        print(f"   |x|={xw}: tallest {m[:,1].max():5.1f} mm, z occupied {zs.min():6.1f}..{zs.max():6.1f}, {len(m):5,} pts")
    else:
        print(f"   |x|={xw}: CLEAR through the whole band")

print("\n== front wall at z=+50: what is nearby? ==")
for z0 in (44, 48, 50, 52, 56, 60):
    m = A[(A[:, 2] > z0 - 3) & (A[:, 2] < z0 + 3)]
    if len(m): print(f"   z={z0}: {len(m):6,} pts, |x|max {np.abs(m[:,0]).max():5.1f}, tallest {m[:,1].max():5.1f}")
    else: print(f"   z={z0}: clear")

print("\n== rear wall at z=-58 ==")
for z0 in (-54, -56, -58, -60, -62):
    m = A[(A[:, 2] > z0 - 3) & (A[:, 2] < z0 + 3)]
    if len(m): print(f"   z={z0}: {len(m):6,} pts, |x|max {np.abs(m[:,0]).max():5.1f}, tallest {m[:,1].max():5.1f}")
    else: print(f"   z={z0}: clear")
