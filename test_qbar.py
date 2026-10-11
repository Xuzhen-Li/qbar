#!/usr/bin/env python3
"""Small checks for qbar. Run: python3 test_qbar.py"""
import os
import tempfile
import unittest

import numpy as np
from PIL import Image

import qbar


class SortTests(unittest.TestCase):
    def test_blocks_iid_and_hclust_only_moves_its_group(self):
        iids = ["b", "a", "d", "c"]
        groups = ["A", "A", "B", "B"]
        q = np.array([
            [1.0, 0.0],
            [1.0, 0.0],
            [0.0, 1.0],
            [1.0, 0.0],
        ])
        order, spans = qbar.build_order(
            iids, groups, ["A", "B"], "iid", {"B": "hclust"}, "NA",
            q, q, None, None,
        )
        names = [iids[i] for i in order]
        self.assertEqual(names[:2], ["a", "b"])
        self.assertEqual(set(names[2:]), {"c", "d"})
        self.assertEqual([s["name"] for s in spans], ["A", "B"])

    def test_within_q_uses_the_group_majority_column(self):
        iids = ["low", "high", "other"]
        groups = ["A", "A", "B"]
        q = np.array([
            [0.2, 0.8],
            [0.9, 0.1],
            [0.0, 1.0],
        ])
        order, _spans = qbar.build_order(
            iids, groups, ["A", "B"], "q", {}, "NA",
            q, q, None, None,
        )
        self.assertEqual([iids[i] for i in order], ["high", "low", "other"])

    def test_sort_col_overrides_every_block(self):
        iids = ["low", "high"]
        groups = ["A", "A"]
        q = np.array([[0.2, 0.8], [0.9, 0.1]])
        order, _spans = qbar.build_order(
            iids, groups, ["A"], "q", {}, "NA",
            q, q, 2, None,
        )
        self.assertEqual([iids[i] for i in order], ["low", "high"])

    def test_order_file_exact_and_leftover_keeps_input_order(self):
        iids = ["a", "b", "c"]
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "ord.txt")
            with open(path, "w") as f:
                f.write("# comment\nb\n")
            order = qbar.order_from_file(path, iids)
            table = os.path.join(td, "order.tsv")
            with open(table, "w") as f:
                f.write("rank\tiid\tgroup\n2\tb\tA\n")
            order_tbl = qbar.order_from_file(table, iids)
        self.assertEqual([iids[i] for i in order], ["b", "a", "c"])
        self.assertEqual([iids[i] for i in order_tbl], ["b", "a", "c"])

    def test_unlisted_groups_follow_blocks_by_name(self):
        iids = ["x", "y", "z"]
        groups = ["C", "A", "B"]
        order, spans = qbar.build_order(
            iids, groups, ["A"], "input", {}, "NA",
            None, None, None, None,
        )
        self.assertEqual([iids[i] for i in order], ["y", "z", "x"])
        self.assertEqual([s["name"] for s in spans], ["A", "B", "C"])


class AlignTests(unittest.TestCase):
    def test_anchor_puts_pure_column_first(self):
        q = np.array([
            [0.1, 0.9],
            [0.8, 0.2],
        ])
        perm = qbar.anchor_perm(q, ["W", "E"], "W")
        self.assertEqual(perm, [1, 0])

    def test_new_column_is_last(self):
        n = 20
        q2 = np.zeros((n, 2))
        q2[:10, 0] = 1.0
        q2[10:, 1] = 1.0
        q3 = np.zeros((n, 3))
        q3[:10, 2] = 1.0
        q3[10:15, 0] = 1.0
        q3[15:, 1] = 1.0
        perm, _rs = qbar.match_next(q2, q3, np.ones(n, dtype=bool))
        self.assertEqual(perm[0], 2)
        self.assertEqual(sorted(perm), [0, 1, 2])
        self.assertEqual(len(perm), 3)

    def test_core_mask_keeps_high_qmax_and_group_fallback(self):
        q = np.array([
            [0.99, 0.01],
            [0.96, 0.04],
            [0.50, 0.50],
            [0.20, 0.80],
            [0.10, 0.90],
        ])
        groups = ["W", "W", "W", "X", "E"]
        mask = qbar.core_mask(q, q, groups, ["W", "E"], 0.75)
        self.assertEqual(mask.tolist(), [True, True, False, False, True])

    def test_gap_in_k_refuses_align(self):
        q = {
            2: np.array([[1.0, 0.0], [0.0, 1.0]]),
            4: np.array([[1.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 1.0]]),
        }
        with self.assertRaises(SystemExit):
            qbar.align_qs(q, ["A", "B"], "", "all", [], 0.75, True)


class ColorTests(unittest.TestCase):
    def test_same_requested_colour_is_not_used_twice(self):
        owners = [[("A", "a", 1.0)], [("B", "b", 1.0)]]
        hexes = qbar.assign_colors(2, owners, {"A": "#ff0000", "B": "#ff0000"}, {})
        self.assertEqual(hexes[0], "#ff0000")
        self.assertNotEqual(hexes[1], "#ff0000")
        self.assertEqual(len(set(hexes)), 2)

    def test_explicit_column_colour_wins(self):
        owners = [[("A", "a", 1.0)], [("B", "b", 1.0)]]
        hexes = qbar.assign_colors(2, owners, {"A": "#ff0000"}, {2: "#00ff00"})
        self.assertEqual(hexes[1], "#00ff00")
        self.assertEqual(hexes[0], "#ff0000")

    def test_bottom_of_bar_is_column_zero(self):
        q = np.array([[1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])
        img = qbar.ancestry_image(q, ["#ff0000", "#00ff00", "#0000ff"], height=20)
        self.assertTrue(np.all(img[:, 0] == np.array([255, 0, 0])))
        self.assertTrue(np.all(img[:, 1] == np.array([0, 0, 255])))

    def test_unowned_column_is_labelled_by_group_mean(self):
        q = np.array([[0.8, 0.2], [0.7, 0.3]])
        owners = qbar.column_owners(q, ["a", "b"], ["A", "A"], {})
        self.assertEqual(owners[1], [])
        self.assertEqual(qbar.column_label(owners[1], q, ["A", "A"], 1), "A 0.25")

    def test_half_split_puts_first_column_on_the_bottom(self):
        q = np.array([[0.5, 0.5]])
        img = qbar.ancestry_image(q, ["#ff0000", "#0000ff"], height=20)
        self.assertTrue(np.all(img[-1, 0] == np.array([255, 0, 0])))
        self.assertTrue(np.all(img[0, 0] == np.array([0, 0, 255])))


class DemoTests(unittest.TestCase):
    def test_chip2448_q_plots_in_block_order(self):
        demo = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo", "2448")
        fam = os.path.join(demo, "ref2448_pruned.fam")
        iids = []
        with open(fam) as f:
            for line in f:
                parts = line.split()
                if parts:
                    iids.append(parts[1])
        self.assertEqual(len(iids), 2448)
        groups = {}
        with open(os.path.join(demo, "groups.tsv")) as f:
            next(f)
            for line in f:
                iid, group = line.rstrip("\n").split("\t")
                groups[iid] = group
        self.assertEqual(set(groups), set(iids))
        for k in range(2, 13):
            path = os.path.join(demo, "ref2448_pruned.%d.Q" % k)
            with open(path) as f:
                rows = [ln for ln in f if ln.strip()]
            self.assertEqual(len(rows), 2448, path)
            self.assertEqual(len(rows[0].split()), k)
        out = tempfile.mkdtemp()
        try:
            qbar.main([
                "--q", os.path.join(demo, "ref2448_pruned.2.Q"),
                os.path.join(demo, "ref2448_pruned.8.Q"),
                "--fam", fam,
                "--groups", os.path.join(demo, "groups.tsv"),
                "--id-col", "id", "--group-col", "group",
                "--blocks", "C-Ad,CG1,CG2,CG3,CG4,CG5,CG6,W-Ad,WEE1,WEE2,WWE1,WWE2",
                "--within", "iid",
                "--anchor-group", "WWE1",
                "--no-align",
                "--outdir", out,
            ])
            with open(os.path.join(out, "order.tsv")) as f:
                order = [line.rstrip("\n").split("\t") for line in f.read().splitlines()[1:]]
            self.assertEqual(len(order), 2448)
            seen = [row[2] for row in order]
            blocks = ["C-Ad", "CG1", "CG2", "CG3", "CG4", "CG5", "CG6", "W-Ad", "WEE1", "WEE2", "WWE1", "WWE2"]
            self.assertEqual(seen, sorted(seen, key=blocks.index))
            cad = [row[1] for row in order if row[2] == "C-Ad"]
            self.assertEqual(cad, sorted(cad))
            self.assertEqual(len(cad), 534)
            with Image.open(os.path.join(out, "panel.png")) as img:
                self.assertGreater(img.size[0], 100)
        finally:
            import shutil
            shutil.rmtree(out)


class CliTests(unittest.TestCase):
    def test_cli_writes_order_and_png(self):
        with tempfile.TemporaryDirectory() as td:
            fam = os.path.join(td, "t.fam")
            with open(fam, "w") as f:
                f.write("F b 0 0 0 -9\nF a 0 0 0 -9\nF c 0 0 0 -9\n")
            grp = os.path.join(td, "g.tsv")
            with open(grp, "w") as f:
                f.write("analysis_IID\tDong_Grp\nb\tA\na\tA\nc\tB\n")
            q2 = os.path.join(td, "t.2.Q")
            q3 = os.path.join(td, "t.3.Q")
            np.savetxt(q2, [[0.1, 0.9], [0.2, 0.8], [0.7, 0.3]])
            np.savetxt(q3, [[0.1, 0.2, 0.7], [0.1, 0.1, 0.8], [0.6, 0.3, 0.1]])
            out = os.path.join(td, "out")
            qbar.main([
                "--q", q2, q3,
                "--fam", fam,
                "--groups", grp,
                "--blocks", "A,B",
                "--within", "iid",
                "--anchor-group", "A",
                "--outdir", out,
            ])
            with open(os.path.join(out, "order.tsv")) as f:
                rows = [line.split("\t")[1] for line in f.read().splitlines()[1:]]
            self.assertEqual(rows, ["a", "b", "c"])
            png = os.path.join(out, "panel.png")
            with Image.open(png) as img:
                self.assertGreater(img.size[0], 100)
            self.assertTrue(os.path.isfile(os.path.join(out, "perm_K2.tsv")))
            self.assertTrue(os.path.isfile(os.path.join(out, "panel.pdf")))

    def test_row_count_mismatch_exits(self):
        with tempfile.TemporaryDirectory() as td:
            fam = os.path.join(td, "t.fam")
            with open(fam, "w") as f:
                f.write("F a 0 0 0 -9\n")
            q = os.path.join(td, "t.2.Q")
            np.savetxt(q, [[0.5, 0.5], [0.2, 0.8]])
            with self.assertRaises(SystemExit):
                qbar.main(["--q", q, "--fam", fam, "--outdir", os.path.join(td, "out")])


if __name__ == "__main__":
    unittest.main()
