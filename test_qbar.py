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

    def _greedy_vs_hungarian_case(self):
        # raw K=3 columns are blocks A (rows 0-9), B (10-19), C (20-29).
        # aligned K=2: C1 = A 1.0 + B 0.8; C2 = A 0.5 + C 0.2.
        # r = [[0.65, 0.33, -0.98], [0.92, -0.80, -0.11]]
        n = 30
        q3 = np.zeros((n, 3))
        q3[:10, 0] = 1.0
        q3[10:20, 1] = 1.0
        q3[20:, 2] = 1.0
        q2 = np.zeros((n, 2))
        q2[:10, 0] = 1.0
        q2[10:20, 0] = 0.8
        q2[:10, 1] = 0.5
        q2[20:, 1] = 0.2
        return q2, q3, np.ones(n, dtype=bool)

    def test_greedy_and_hungarian_differ(self):
        q2, q3, mask = self._greedy_vs_hungarian_case()
        r = qbar.pearson_matrix(q2, q3, mask)
        g, g_rs = qbar.match_next(q2, q3, mask, "greedy")
        h, h_rs = qbar.match_next(q2, q3, mask, "hungarian")
        self.assertEqual(g, [0, 2, 1])
        self.assertEqual(h, [1, 0, 2])
        self.assertIsNone(h_rs[-1])
        self.assertGreater(sum(h_rs[:-1]), sum(g_rs[:-1]))
        for c in range(2):
            self.assertAlmostEqual(h_rs[c], r[c, h[c]])

    def test_hungarian_is_optimal_by_brute_force(self):
        import itertools
        rng = np.random.default_rng(7)
        for _ in range(20):
            k = int(rng.integers(2, 6))
            q_prev = rng.dirichlet(np.ones(k), size=40)
            q_new = rng.dirichlet(np.ones(k + 1), size=40)
            mask = np.ones(40, dtype=bool)
            r = qbar.pearson_matrix(q_prev, q_new, mask)
            best = max(sum(r[c, p[c]] for c in range(k)) for p in itertools.permutations(range(k + 1), k))
            h, h_rs = qbar.match_next(q_prev, q_new, mask, "hungarian")
            self.assertAlmostEqual(sum(h_rs[:-1]), best)
            self.assertEqual(sorted(h), list(range(k + 1)))

    def test_default_method_is_greedy(self):
        q2, q3, mask = self._greedy_vs_hungarian_case()
        self.assertEqual(qbar.match_next(q2, q3, mask), qbar.match_next(q2, q3, mask, "greedy"))
        args = qbar.build_parser().parse_args(["--q", "x.Q", "--outdir", "o"])
        self.assertEqual(args.align_method, "greedy")

    def test_cli_align_method_hungarian(self):
        q2, q3, _ = self._greedy_vs_hungarian_case()
        with tempfile.TemporaryDirectory() as tmp:
            for k, q in ((2, q2), (3, q3)):
                np.savetxt(os.path.join(tmp, "t.%d.Q" % k), q + 1e-6, fmt="%.6f")
            ids = os.path.join(tmp, "ids.txt")
            with open(ids, "w") as f:
                f.write("".join("s%d\n" % i for i in range(30)))
            got = {}
            for m in ("greedy", "hungarian"):
                out = os.path.join(tmp, m)
                qbar.main(["--q", os.path.join(tmp, "t.2.Q"), os.path.join(tmp, "t.3.Q"),
                           "--ids", ids, "--align-method", m, "--outdir", out])
                with open(os.path.join(out, "perm_K3.tsv")) as f:
                    got[m] = [line.split("\t")[1] for line in f.read().splitlines()[1:]]
            self.assertEqual(got["greedy"], ["1", "3", "2"])
            self.assertEqual(got["hungarian"], ["2", "1", "3"])

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
