# Viewer

A local, offline viewer for the car with the printable top cover fitted.
It loads `../cover/freenove-top-cover.stl` **directly** — the same file the
printer gets — so the render cannot drift from the part.

```bash
tools/viewer          # serves on :8000 and opens a browser
```

It needs a server — `file://` blocks both ES modules and the glTF fetch.

## What you are looking at

`car.glb` is Freenove's own `FNK0043_3D.STEP` (69 MB, SolidWorks 2018,
AP203) tessellated to 628k triangles at 0.6 mm deflection:

```bash
tools/step2glb.py cad_design/FNK0043_3D.STEP viewer/car.glb 0.6
```

Two things worth knowing about that conversion:

- **AP203 carries no colour.** Every one of the 244 parts arrives untextured,
  which is why the car renders in one neutral grey. The shells supply all the
  colour deliberately.
- **glTF's unit is the metre, OpenCASCADE's is the millimetre**, so
  `RWGltf_CafWriter` divides everything by 1000 on the way out. `app.js` scales
  it back by 1000 on load. Without that the whole car sits inside the camera's
  near plane and you get an empty screen.

**Freenove's CAD has the ordinary wheel set fitted, not mecanum.** Your car has
mecanum. They are a similar diameter but wider, so treat corner clearance in
this viewer as optimistic and check it against the real car before committing
to a shell.

## Measured, not guessed

Both numbers the shells are built from came out of the model itself:

- **Bounding box 151 × 211 × 117 mm**, from OpenCASCADE before export.
- **Deck at 46 mm** above the floor — a histogram of vertex heights across the
  whole assembly peaks hard in the 45–47 mm band, which is the main chassis
  plate the Pi and the LED strip sit on.
- **Front is +Z**, established by taking the mean Z of every vertex above 0.72
  of the model height — the ultrasonic and camera mast — which lands at +78 mm.
  The shells are modelled nose-toward −Z because that is easier to read, then
  rotated 180° in `buildCase`.

## Controls worth knowing

- **Explode** lifts the cover off so you can see the bay underneath.
- **Mount points** shows the four standoffs the cover bolts to — tops measured
  at 15.75 mm, all four identical to 0.00 mm, which is what makes a 4-point
  mount possible at all.
- **Camera sweep** draws what the camera head covers when it pans. The cover's
  front face stops 5.7 mm short of it.

`tools/viewer` picks a free port if 8000 is busy and tells you which one.

## Earlier work

Four whimsical shell concepts (ladybug, cat loaf, frog, toadstool) were built
here first and are in git history. They were look-and-feel studies with drawn
rather than cut apertures; the project settled on one properly engineered cover
instead. See `../cover/README.md`.
