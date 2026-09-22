#!/usr/bin/env python3
"""Build the Freenove 4WD electronics-bay cover as a real solid, and export it.

    ../tools/cadenv/bin/python build_cover.py     -> STL + STEP + cover_params.json

COORDINATES. The car's STEP is Y-up: X is width, Y is height, Z is length with
the sensor mast at +Z. Printers and CadQuery are Z-up. This file models in
CadQuery space and converts once, at the boundary:

    cq_x = car_x (width)    cq_y = car_z (length)    cq_z = car_y (height)

Car-frame Y = 0 is the top face of the main deck plate.

EVERY NUMBER BELOW WAS MEASURED off Freenove's STEP by tools/analyse*.py. Where
a value looks arbitrary, the comment says what was measured and why the value
follows from it. Do not adjust one without re-running test_cover.py.

THREE MEASUREMENTS DECIDED THIS SHAPE
-------------------------------------
1. Four standoffs stand on the deck at (+/-24.50, +10.10) and (+/-24.50, -47.90)
   -- a 49 x 58 mm rectangle -- with their tops at 15.75 mm, all four identical
   to 0.00 mm. That is a ready-made 4-point mount, so the cover hangs off those
   rather than resting on the deck plate, whose outline is full of slots and
   whose narrow waist (|x| <= 34.7) leaves straight walls hanging in air.

2. Nothing stands above the deck at |x| = 44..46 anywhere along the bay, while
   the wheels reach |x| >= 49.7 and stand 19.8 mm proud. So side walls sit at
   |x| = 46: 3.7 mm inboard of a wheel, and clear to the deck.

3. THE BACK CANNOT BE CLOSED. Every 1 mm slice from z = -51 to z = -45 carries
   hardware up to 22.2 mm tall across |x| = 0..27.5, and z = -54 and beyond is
   the battery holder at 27.5-29.5 mm. The only clear slices are z = -52 and
   -53, a 2 mm window a 2.4 mm wall cannot fit. The bay is therefore open at
   the rear -- which is also where the cables and the battery want access.
"""

import json
import os

import cadquery as cq

# --- measured, do not edit without re-measuring ------------------------------

STANDOFF_TOP  = 15.75   # all four, spread 0.00 mm
STANDOFF_XY   = [(24.5, 10.1), (-24.5, 10.1), (24.5, -47.9), (-24.5, -47.9)]
STANDOFF_R    = 2.31    # measured pillar radius; a boss must not exceed ~3.5
BAY_TALLEST   = 22.2    # tallest hardware inside the chosen footprint
WHEEL_X       = 49.7    # nearest wheel surface to the centreline
WHEEL_H       = 19.8
CAM_SWEEP_Z   = 57.1    # rearmost reach of the camera head when panning

# --- chosen geometry ---------------------------------------------------------

WALL          = 2.4     # 6 x 0.4 mm perimeters; stiff over a 92 mm span
ROOF          = 2.4

HALF_W        = 46.0    # see measurement 2
Z_BACK        = -52.0   # roof edge; last clear slice behind the bay
Z_FRONT       =  51.4   # front face outer. z 44..53 measured clear; 5.7 mm
                        # short of the camera's rearmost sweep at 57.1

FLOOR_GAP     = 1.0     # wall bottoms stop 1 mm above the deck. The standoffs
                        # carry the cover, so the walls never need to touch --
                        # and not touching removes every deck-flatness and
                        # print-tolerance argument at a stroke.
INNER_H       = 25.0    # 2.8 mm over the tallest hardware in the bay
HEIGHT        = INNER_H + ROOF          # 27.4 outer

CORNER_R      = 8.0     # front vertical corners only; the rear is open

# A plain 6 mm column, and the diameter is the whole story. Measured clearance
# in the column above each standoff: r = 3.0 is clear from 15.75 mm up on all
# four. Wider bosses were built and both failed test_05 against real hardware
# beside the rear mount -- 7 mm OD left 0.86 mm, 8 mm left 0.20 mm. Do not
# widen this to "strengthen" it: the roof carries the load, and the screw head
# clamps against 2.4 mm of roof rather than against the boss wall.
BOSS_OD       = 6.0
BOSS_ID       = 3.2     # M3 clearance. See README on verifying the thread.

VENT_ROWS     = 4
VENT_SLOT_L   = 44.0
VENT_SLOT_W   = 4.0
VENT_PITCH    = 12.0
VENT_Z0       = -12.0   # over the Pi, clear of the bosses at z = +10.1


def build():
    length = Z_FRONT - Z_BACK
    y_mid = (Z_FRONT + Z_BACK) / 2.0

    # Outer block. Only the two FRONT vertical corners are rounded -- the rear
    # is an open mouth, and filleting an edge that is about to be cut away just
    # makes the cut ragged.
    outer = (
        cq.Workplane("XY")
        .moveTo(0, y_mid).rect(HALF_W * 2, length).extrude(HEIGHT)
        .edges("|Z and >Y").fillet(CORNER_R)
    )
    cover = outer.faces("<Z").shell(-WALL)

    # Open the rear. The cut must span the WHOLE wall thickness -- centred on
    # Z_BACK, not behind it, or a sliver of wall survives on the inner face and
    # sits exactly where the deck hardware is.
    cover = cover.cut(
        cq.Workplane("XY")
        .moveTo(0, Z_BACK).rect(HALF_W * 2 + 20, WALL * 2)
        .extrude(INNER_H)
    )

    # Lift the wall bottoms clear of the deck.
    cover = cover.cut(
        cq.Workplane("XY")
        .moveTo(0, y_mid).rect(HALF_W * 2 + 20, length + 20)
        .extrude(FLOOR_GAP)
    )

    # Mounting bosses, hanging from the roof down onto the standoff tops.
    for x, z in STANDOFF_XY:
        cover = cover.union(
            cq.Workplane("XY", origin=(0, 0, STANDOFF_TOP))
            .moveTo(x, z).circle(BOSS_OD / 2.0)
            .extrude(INNER_H - STANDOFF_TOP))

    # Screw holes through the roof, so the heads land on the outside.
    cover = (
        cover.faces(">Z").workplane(centerOption="CenterOfBoundBox")
        .pushPoints([(x, z - y_mid) for x, z in STANDOFF_XY])
        .circle(BOSS_ID / 2.0).cutThruAll()
    )

    # Vents over the Pi. Kept off the centreline of the bosses.
    cover = (
        cover.faces(">Z").workplane(centerOption="CenterOfBoundBox")
        .pushPoints([(0.0, VENT_Z0 + i * VENT_PITCH - y_mid) for i in range(VENT_ROWS)])
        .slot2D(VENT_SLOT_L, VENT_SLOT_W, 0)
        .cutThruAll()
    )

    return cover


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    cover = build()

    stl = os.path.join(here, "freenove-top-cover.stl")
    stp = os.path.join(here, "freenove-top-cover.step")
    cq.exporters.export(cover, stl, tolerance=0.01, angularTolerance=0.1)
    cq.exporters.export(cover, stp)

    vol = cover.val().Volume() / 1000.0
    bb = cover.val().BoundingBox()
    json.dump({
        "half_width": HALF_W, "z_back": Z_BACK, "z_front": Z_FRONT,
        "height": HEIGHT, "inner_height": INNER_H, "wall": WALL, "roof": ROOF,
        "floor_gap": FLOOR_GAP, "corner_r": CORNER_R,
        "boss_od": BOSS_OD, "boss_id": BOSS_ID,
        "standoff_top": STANDOFF_TOP, "standoff_xy": STANDOFF_XY,
        "measured": {"bay_tallest": BAY_TALLEST, "wheel_x": WHEEL_X,
                     "wheel_h": WHEEL_H, "cam_sweep_z": CAM_SWEEP_Z,
                     "standoff_r": STANDOFF_R},
        "volume_cm3": round(vol, 1),
        "bbox_cq": [[bb.xmin, bb.ymin, bb.zmin], [bb.xmax, bb.ymax, bb.zmax]],
    }, open(os.path.join(here, "cover_params.json"), "w"), indent=1)

    print(f"  outer      {bb.xlen:.1f} x {bb.ylen:.1f} x {bb.zlen:.1f} mm (w x l x h)")
    print(f"  volume     {vol:.1f} cm^3  (~{vol * 1.24:.0f} g of PLA if it were solid;"
          f" at 3 perimeters and 15% infill expect 35-45 g)")
    print(f"  wrote      {os.path.basename(stl)}, {os.path.basename(stp)},"
          f" cover_params.json")


if __name__ == "__main__":
    main()
