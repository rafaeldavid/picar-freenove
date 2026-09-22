#!/usr/bin/env python3
"""Fit and printability tests for the electronics-bay cover.

    ../tools/cadenv/bin/python -m unittest -v test_cover

WHAT THESE PROVE, AND WHAT THEY DO NOT
--------------------------------------
They prove the cover's solid does not occupy the same space as any car geometry
in Freenove's published CAD, that it clears the panning camera and the wheels,
that its bosses land on the four standoffs, that it is a closed manifold, and
that it prints without support in the stated orientation. Every threshold is
compared against a number measured from the STEP, not a number someone typed.

They do NOT prove it fits your physical car. Freenove's CAD is nominal. A real
kit has assembly tolerance; a printer has shrinkage and its own tolerance. The
clearances were chosen with that in mind -- 1 mm under the wall rim, 2.8 mm over
the tallest hardware, 3.7 mm to the wheels -- but only a print settles it.

The car is a 669,581-point surface sample tessellated from the STEP at 1.0 mm
(tools/analyse3.py). Interference is checked two ways: an exact point-in-solid
classification of every car point inside the cover's bounding box, and a
nearest-neighbour distance from the cover's own surface.
"""

import json
import os
import struct
import unittest

import numpy as np
from scipy.spatial import cKDTree

HERE = os.path.dirname(os.path.abspath(__file__))
STL = os.path.join(HERE, "freenove-top-cover.stl")
STEP = os.path.join(HERE, "freenove-top-cover.step")
PTS = os.path.join(HERE, "carpoints.npy")
PARAMS = os.path.join(HERE, "cover_params.json")

DECK = 0.0
ON_DECK = 0.8       # above this, car geometry is "standing on the deck"


def load_stl(path):
    """Binary STL -> (triangles Nx3x3, vertices Mx3) in CadQuery coordinates."""
    with open(path, "rb") as f:
        f.read(80)
        n = struct.unpack("<I", f.read(4))[0]
        data = f.read(n * 50)
    a = np.frombuffer(data, dtype=np.uint8).reshape(n, 50)
    fl = a[:, :48].copy().view("<f4").reshape(n, 4, 3)
    return (fl[:, 1:, :].astype(np.float64),
            fl[:, 1:, :].reshape(-1, 3).astype(np.float64))


def cq_to_car(v):
    """CadQuery (x=width, y=length, z=height) -> car frame (X, Y up, Z length)."""
    out = np.empty_like(v)
    out[..., 0] = v[..., 0]
    out[..., 1] = v[..., 2]
    out[..., 2] = v[..., 1]
    return out


class CoverFit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tris_cq, cls.verts_cq = load_stl(STL)
        cls.verts = cq_to_car(cls.verts_cq)
        cls.P = np.load(PTS)
        cls.A = cls.P[cls.P[:, 1] > DECK + ON_DECK]
        cls.p = json.load(open(PARAMS))
        cls.tree = cKDTree(cls.verts)
        print(f"\n  cover {len(cls.tris_cq):,} triangles / {len(cls.verts):,} vertices"
              f"   car {len(cls.P):,} points ({len(cls.A):,} above the deck)")

    # --- the mesh itself -----------------------------------------------------

    def test_01_stl_is_a_closed_manifold(self):
        """Every edge shared by exactly two triangles. A slicer refuses anything
        else, and most print services refuse it only after you have paid."""
        v = np.round(self.verts_cq, 4)
        _, idx = np.unique(v, axis=0, return_inverse=True)
        f = idx.reshape(-1, 3)
        e = np.sort(np.vstack([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]), axis=1)
        _, counts = np.unique(e, axis=0, return_counts=True)
        bad = int((counts != 2).sum())
        self.assertEqual(bad, 0, f"{bad} edges are not shared by exactly 2 faces")

    def test_02_no_degenerate_triangles(self):
        a, b, c = self.tris_cq[:, 0], self.tris_cq[:, 1], self.tris_cq[:, 2]
        area = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
        self.assertEqual(int((area < 1e-9).sum()), 0, "zero-area triangles present")

    def test_03_solid_is_valid_and_single_bodied(self):
        """A cover that exports as two lumps has a boss floating free of the
        roof. The slicer would print both and neither would be useful."""
        import cadquery as cq
        shape = cq.importers.importStep(STEP).val()
        solids = shape.Solids()
        print(f"    {len(solids)} solid(s), volume {shape.Volume()/1000:.1f} cm^3")
        self.assertEqual(len(solids), 1, f"exported as {len(solids)} separate solids")
        self.assertGreater(shape.Volume() / 1000.0, 10.0, "suspiciously small")

    # --- does it hit the car? ------------------------------------------------

    def test_04_no_car_geometry_inside_the_cover_material(self):
        """Exact: classify every car point inside the cover's bounding box
        against the real solid. Anything inside is a collision."""
        import cadquery as cq
        from OCP.BRepClass3d import BRepClass3d_SolidClassifier
        from OCP.gp import gp_Pnt
        from OCP.TopAbs import TopAbs_IN

        solid = cq.importers.importStep(STEP).val().Solids()[0]
        lo, hi = np.array(self.p["bbox_cq"][0]), np.array(self.p["bbox_cq"][1])
        Pc = self.P[:, [0, 2, 1]]                     # car -> cq ordering
        cand = Pc[np.all((Pc >= lo - 0.01) & (Pc <= hi + 0.01), axis=1)]
        self.assertGreater(len(cand), 1000, "bounding-box filter looks wrong")

        clf = BRepClass3d_SolidClassifier(solid.wrapped)
        inside, first = 0, None
        for q in cand:
            clf.Perform(gp_Pnt(*(float(t) for t in q)), 1e-7)
            if clf.State() == TopAbs_IN:
                inside += 1
                first = first if first is not None else q
        print(f"    classified {len(cand):,} car points; {inside} inside the material")
        self.assertEqual(inside, 0,
                         f"{inside} car points inside the cover, first at cq {first}")

    def test_05_clearance_to_hardware_standing_on_the_deck(self):
        """The bosses deliberately land on the standoffs, so exclude a small
        sphere around each. Everything else must keep its distance."""
        # The mounting interface is excluded, and nothing else. Each standoff
        # is a 2.31 mm pillar carrying a wider flange that reaches r = 3.5 at
        # its top; the boss is meant to come down beside that. So skip a 4.5 mm
        # cylinder around each standoff BELOW 17.5 mm -- and nowhere else. Above
        # that height, and everywhere off-axis, the full 1 mm rule still applies,
        # which is what caught the 8 mm boss body at 0.20 mm.
        keep = np.ones(len(self.A), dtype=bool)
        for x, z in self.p["standoff_xy"]:
            near_mount = ((np.hypot(self.A[:, 0] - x, self.A[:, 2] - z) < 4.5)
                          & (self.A[:, 1] < 17.5))
            keep &= ~near_mount
        d, _ = self.tree.query(self.A[keep], k=1)
        gap = float(d.min())
        w = self.A[keep][int(np.argmin(d))]
        print(f"    closest approach {gap:.2f} mm at car ({w[0]:.1f}, {w[1]:.1f}, {w[2]:.1f})")
        self.assertGreaterEqual(gap, 1.0, f"only {gap:.2f} mm from deck hardware")

    def test_06_walls_stay_inboard_of_the_wheels(self):
        wx = self.p["measured"]["wheel_x"]
        widest = float(np.abs(self.verts[:, 0]).max())
        print(f"    widest {widest:.1f} mm; wheels start at {wx} mm -> {wx-widest:.1f} mm gap")
        self.assertLess(widest, wx - 2.0)

    def test_07_roof_clears_the_tallest_thing_beneath_it(self):
        """Measured against what is actually under this footprint, not against
        the car's global maximum."""
        x0, x1 = self.verts[:, 0].min(), self.verts[:, 0].max()
        z0, z1 = self.verts[:, 2].min(), self.verts[:, 2].max()
        under = self.A[(self.A[:, 0] > x0) & (self.A[:, 0] < x1)
                       & (self.A[:, 2] > z0) & (self.A[:, 2] < z1)]
        tallest = float(under[:, 1].max())
        inner = self.p["inner_height"]
        print(f"    tallest under the footprint {tallest:.1f} mm, ceiling {inner} mm")
        self.assertGreater(inner, tallest + 1.5)

    def test_08_front_face_clears_the_panning_camera(self):
        """The camera head sweeps back to z = 57.1 worst case over a full
        circle about the pan axis. The cover must stop short of it."""
        sweep = self.p["measured"]["cam_sweep_z"]
        front = float(self.verts[:, 2].max())
        print(f"    front face z={front:.1f}; camera reaches z={sweep} -> {sweep-front:.1f} mm")
        self.assertLess(front, sweep - 3.0)

    def test_09_nothing_touches_the_deck_plate(self):
        """The standoffs carry the cover. The rim floats, by design, so deck
        flatness and print tolerance cannot make it rock."""
        lowest = float(self.verts[:, 1].min())
        print(f"    lowest point {lowest:.2f} mm above the deck")
        self.assertGreaterEqual(lowest, self.p["floor_gap"] - 0.01)

    # --- does it mount? ------------------------------------------------------

    def test_10_bosses_land_on_the_four_standoffs(self):
        """Each boss must have a face at exactly the standoff top height, at the
        standoff's x,z. If one is short the cover rocks; if one is long it will
        not seat."""
        top = self.p["standoff_top"]
        for x, z in self.p["standoff_xy"]:
            r = np.hypot(self.verts[:, 0] - x, self.verts[:, 2] - z)
            near = self.verts[r < self.p["boss_od"] / 2 + 0.2]
            self.assertGreater(len(near), 8, f"no boss geometry at ({x}, {z})")
            bottom = float(near[:, 1].min())
            self.assertAlmostEqual(
                bottom, top, delta=0.05,
                msg=f"boss at ({x}, {z}) bottoms at {bottom:.2f}, standoff is {top}")
        print(f"    all four bosses bottom at {top} mm")

    def test_11_screw_holes_are_open_and_aligned(self):
        """A hole must run clean through roof and boss, on the standoff axis."""
        import cadquery as cq
        from OCP.BRepClass3d import BRepClass3d_SolidClassifier
        from OCP.gp import gp_Pnt
        from OCP.TopAbs import TopAbs_IN
        solid = cq.importers.importStep(STEP).val().Solids()[0]
        clf = BRepClass3d_SolidClassifier(solid.wrapped)
        for x, z in self.p["standoff_xy"]:
            for h in np.arange(self.p["standoff_top"] + 0.2, self.p["height"], 0.5):
                clf.Perform(gp_Pnt(float(x), float(z), float(h)), 1e-7)
                self.assertNotEqual(clf.State(), TopAbs_IN,
                                    f"screw axis at ({x},{z}) is solid at h={h:.1f}")
        print(f"    all four axes clear from {self.p['standoff_top']} to "
              f"{self.p['height']} mm; hole {self.p['boss_id']} mm (M3 clearance)")

    def test_12_boss_columns_are_clear_of_the_car(self):
        """The boss occupies a cylinder above each standoff. Verify the car has
        nothing there apart from the standoff itself."""
        top, r = self.p["standoff_top"], self.p["boss_od"] / 2.0
        for x, z in self.p["standoff_xy"]:
            d = np.hypot(self.A[:, 0] - x, self.A[:, 2] - z)
            col = self.A[(d < r) & (self.A[:, 1] > top + 0.3)]
            self.assertEqual(
                len(col), 0,
                f"{len(col)} car points inside the boss at ({x},{z})"
                + (f", up to {col[:, 1].max():.1f} mm" if len(col) else ""))
        print(f"    all four {self.p['boss_od']} mm boss columns clear above {top} mm")

    # --- will it print? ------------------------------------------------------

    def test_13_wall_thickness_is_printable(self):
        w = min(self.p["wall"], self.p["roof"])
        self.assertGreaterEqual(w, 1.2, "thinner than 3 perimeters at 0.4 mm")
        self.assertAlmostEqual(w / 0.4, round(w / 0.4), places=6,
                               msg="not a whole number of 0.4 mm extrusions")
        boss_wall = (self.p["boss_od"] - self.p["boss_id"]) / 2.0
        print(f"    walls {w} mm, boss wall {boss_wall:.2f} mm")
        self.assertGreaterEqual(boss_wall, 1.2, "boss wall too thin to hold a screw")

    def test_14_fits_a_common_print_bed(self):
        bb = self.p["bbox_cq"]
        w, l, h = (bb[1][i] - bb[0][i] for i in range(3))
        print(f"    {w:.0f} x {l:.0f} mm footprint, {h:.0f} mm tall (printed roof-down)")
        self.assertLess(max(w, l), 200)
        self.assertLess(h, 200)

    def test_15_no_unsupported_overhang_printed_roof_down(self):
        """Roof on the bed, walls and bosses growing upward: every wall is
        vertical and every boss is a column. Nothing should need support."""
        a, b, c = self.tris_cq[:, 0], self.tris_cq[:, 1], self.tris_cq[:, 2]
        n = np.cross(b - a, c - a)
        ln = np.linalg.norm(n, axis=1)
        keep = ln > 1e-9
        n, area = n[keep] / ln[keep, None], 0.5 * ln[keep]
        # printed roof-down, a face whose normal points +Z in CQ faces the bed
        down = n[:, 2] > 1e-6
        steep = down & (n[:, 2] < np.cos(np.radians(45)))
        bad, total = float(area[steep].sum()), float(area.sum())
        print(f"    {bad:.1f} of {total:.0f} mm^2 exceeds 45 deg ({bad/total*100:.2f}%)")
        self.assertLess(bad / total, 0.02, f"{bad:.0f} mm^2 would need support")


    def test_16_part_is_left_right_symmetric(self):
        """This one guards the coordinate convention, not the shape.

        build_cover.py models with cq_y = car_z and cq_z = car_y. Swapping two
        axes is a REFLECTION, not a rotation, so a printed part cannot in
        general be placed on the car the way the other tests assume. It works
        here only because the cover is mirror-symmetric about x = 0: the
        placement becomes a -90 deg roll plus a 180 deg yaw, both real
        rotations, and the yaw's x-flip is invisible on a symmetric part.

        Add anything one-sided -- a cable notch, a logo, an asymmetric vent --
        and this test fails, which is exactly when you need to know."""
        v = np.round(self.verts_cq, 3)
        mirrored = v.copy()
        mirrored[:, 0] *= -1
        a = set(map(tuple, v))
        b = set(map(tuple, mirrored))
        only = len(a ^ b)
        print(f"    {len(a):,} distinct vertices, {only} without a mirror twin")
        self.assertEqual(only, 0,
                         f"{only} vertices have no mirror image; the part is "
                         f"asymmetric and the cq->car mapping is a reflection")


if __name__ == "__main__":
    unittest.main(verbosity=2)
