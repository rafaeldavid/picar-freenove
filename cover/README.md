# Electronics-bay top cover — Freenove 4WD (FNK0043)

**92 × 103 × 26 mm.** Bolts to four existing standoffs. Open at the rear.
Clears the wheels, the panning camera and everything on the deck.

| File | |
|---|---|
| `freenove-top-cover.stl` | **send this to the printer** |
| `freenove-top-cover.step` | for editing in FreeCAD / Fusion / Onshape |
| `build_cover.py` | the source of both — parametric, every constant annotated |
| `test_cover.py` | 16 fit and printability tests |
| `cover_params.json` | the geometry as data, consumed by the tests |
| `carpoints.npy` | 669,581-point sample of the car, from Freenove's STEP |

```bash
../tools/cadenv/bin/python build_cover.py            # rebuild
../tools/cadenv/bin/python -m unittest -v test_cover # verify
../tools/viewer                                      # look at it on the car
```

The viewer loads **this exact STL**, not a preview model, so what you rotate
on screen cannot drift from what you print.

## Printing

| | |
|---|---|
| Orientation | **Roof down, open side up.** Test 15 measures 0.07% of the surface past 45° in this orientation. |
| Supports | **None.** That is what the orientation buys. |
| Material | PLA or PETG. PETG if the car lives somewhere hot — the Pi warms the bay. |
| Layer | 0.2 mm |
| Walls | 3 perimeters at 0.4 mm nozzle (part is 2.4 mm = 6 extrusions) |
| Infill | 15%, gyroid |
| Mass | ~35–45 g |
| Bed | 92 × 103 mm footprint. Fits anything from an Ender 3 upward. |

The four screw holes are **3.2 mm** — M3 clearance. See *Before you order*.

## How it mounts

Four standoffs already stand on the deck at **(±24.5, +10.1)** and
**(±24.5, −47.9)** — a 49 × 58 mm rectangle — with tops at **15.75 mm**, all
four identical to 0.00 mm. Internal bosses hang from the roof onto those tops;
M3 screws pass down through the roof.

That is why the cover does not rest on the deck plate at all. Its rim floats
**1 mm** clear. The plate's outline is full of slots and its waist narrows to
|x| ≤ 34.7 mm, so anything resting on it would rock; hanging off four
machined-height standoffs cannot.

## Why it is this shape

Three measurements, all taken from Freenove's STEP by `../tools/analyse*.py`:

1. **Nothing stands above the deck between |x| = 44 and 46**, while the wheels
   reach |x| ≥ 49.7 and stand 19.8 mm proud. Side walls sit at |x| = 46 —
   3.7 mm inboard of a wheel, and clear all the way down.

2. **The bay is only 22.2 mm tall.** The car's 51.7 mm stack is the camera mast,
   forward of this footprint. So the cover is 26 mm, not 56 mm — and the camera
   sweeps clean over the top of it.

3. **The back cannot be closed.** Every 1 mm slice from z = −51 to −45 carries
   hardware to 22.2 mm across the full width, and beyond z = −54 is the battery
   holder at 29.5 mm. The only clear slices are z = −52 and −53 — a 2 mm window
   that a 2.4 mm wall does not fit. Hence open at the rear, which is also where
   the cables and the battery want access.

## What the tests prove — and what they do not

All 16 pass. Minimum clearance to any deck hardware: **1.55 mm**.

They prove the solid does not occupy the same space as any car geometry in
Freenove's published CAD, that it clears the camera's full pan sweep by 5.7 mm
and the wheels by 3.7 mm, that the bosses land on all four standoffs, that the
mesh is a closed manifold with no degenerate faces, and that it prints without
support.

**They do not prove it fits your car.** Freenove's CAD is nominal. A real kit
has assembly tolerance; a printer has shrinkage and its own. The clearances were
chosen with that in mind, but only a print settles it.

Two further limits worth knowing:

- The car is a **point sample at 1.0 mm**, not solid booleans against all 244
  parts. A feature thinner than the sample spacing could in principle fall
  between points. The exact point-in-solid classification mitigates this; it
  does not eliminate it.
- `test_16` guards a subtlety: `build_cover.py` maps `cq_y = car_z` and
  `cq_z = car_y`, which is a *reflection*, not a rotation. It is only safe
  because the cover is mirror-symmetric. **Add anything one-sided — a cable
  notch, a logo — and that test fails, which is exactly when you need to know.**

## Before you order

**Check the standoff thread.** The pillars measure 4.62 mm across, which reads
as M3, and the holes are cut at 3.2 mm to match. But the STEP does not model
threads, so this is inference. Put a caliper and an M3 screw on a real standoff
before ordering. If they turn out to be M4, open the holes to 4.5 mm — the
6 mm boss has room, though the wall drops to 0.75 mm and you would want a
washer under each head.

**Consider printing it yourself first** if you have access to a printer. A
throwaway PLA copy costs a couple of hours and settles every tolerance question
a service cannot. If it fits, order the good one.
