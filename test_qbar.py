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

    def test_hungarian_without_scipy_exits(self):
        import builtins
        from unittest import mock
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name.startswith("scipy"):
                raise ImportError("no scipy")
            return real_import(name, *args, **kwargs)

        q2, q3, mask = self._greedy_vs_hungarian_case()
        with mock.patch("builtins.__import__", side_effect=fake_import):
            with self.assertRaises(SystemExit) as cm:
                qbar.match_next(q2, q3, mask, "hungarian")
            self.assertIn("scipy", str(cm.exception.code))
            self.assertEqual(qbar.match_next(q2, q3, mask, "greedy")[0], [0, 2, 1])

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

    def _split_case(self):
        # K=2: C1 = rows 0-9, C2 = rows 10-29. K=3 raw: col 1 = rows 0-9,
        # C2 splits into raw col 2 (0.9 on rows 10-19) and raw col 0 (0.1 on rows 10-19, 1 on 20-29).
        # Against C2, pong_sim is 0.497 for raw 2 and 0.550 for raw 0, so raw 0 keeps C2.
        n = 30
        q2 = np.zeros((n, 2))
        q2[:10, 0] = 1.0
        q2[10:, 1] = 1.0
        q3 = np.zeros((n, 3))
        q3[:10, 1] = 1.0
        q3[10:20, 2] = 0.9
        q3[10:20, 0] = 0.1
        q3[20:, 0] = 1.0
        return q2, q3, np.ones(n, dtype=bool)

    def test_pong_sim_matches_manual_formula(self):
        a = np.array([1.0, 0.5, 0.0, 0.0])
        b = np.array([0.5, 0.5, 0.5, 0.0])
        # N* = first three; sum sq = 0.25 + 0 + 0.25
        self.assertAlmostEqual(qbar.pong_sim(a, b), 1 - np.sqrt(0.5 / 6))
        self.assertAlmostEqual(qbar.pong_sim(a, a), 1.0)

    def test_pong_without_scipy_exits(self):
        import builtins
        from unittest import mock
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name.startswith("scipy"):
                raise ImportError("no scipy")
            return real_import(name, *args, **kwargs)

        q2, q3, mask = self._split_case()
        with mock.patch("builtins.__import__", side_effect=fake_import):
            with self.assertRaises(SystemExit) as cm:
                qbar.match_next_pong(q2, q3, mask)
        self.assertIn("pong", str(cm.exception.code))
        self.assertIn("scipy", str(cm.exception.code))

    def test_pong_split_records_parent(self):
        q2, q3, mask = self._split_case()
        perm, sims, split = qbar.match_next_pong(q2, q3, mask)
        self.assertEqual(perm, [1, 0, 2])
        self.assertEqual(split, {"parent": 1, "pair": (0, 2)})
        self.assertAlmostEqual(sims[0], 1.0)
        self.assertAlmostEqual(sims[1], 1.0)
        self.assertIsNone(sims[2])

    def test_pong_align_tsv_has_split_parent(self):
        q2, q3, _ = self._split_case()
        with tempfile.TemporaryDirectory() as tmp:
            for k, q in ((2, q2), (3, q3)):
                np.savetxt(os.path.join(tmp, "t.%d.Q" % k), q, fmt="%.6f")
            ids = os.path.join(tmp, "ids.txt")
            with open(ids, "w") as f:
                f.write("".join("s%d\n" % i for i in range(30)))
            out = os.path.join(tmp, "o")
            qbar.main(["--q", os.path.join(tmp, "t.2.Q"), os.path.join(tmp, "t.3.Q"),
                       "--ids", ids, "--align-method", "pong", "--outdir", out])
            with open(os.path.join(out, "align.tsv")) as f:
                lines = f.read().splitlines()
            self.assertEqual(lines[0], "K_to\tn_mask\tpong_sim\tsplit_parent")
            self.assertEqual(lines[1], "3\t30\t1.000 1.000\tC2")

    def test_member_sets_and_jaccard_matrix(self):
        q = np.array([[0.7, 0.3], [0.5, 0.5], [0.2, 0.8]])
        m = np.ones(3, dtype=bool)
        self.assertEqual(qbar.member_sets(q, m, "dominant", 0.5).tolist(),
                         [[True, False], [True, False], [False, True]])
        self.assertEqual(qbar.member_sets(q, m, "threshold", 0.5).tolist(),
                         [[True, False], [True, True], [False, True]])
        q3 = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])
        j = qbar.jaccard_matrix(q, q3, m, "dominant")
        self.assertEqual(j.tolist(), [[0.5, 0.5, 0.0], [0.0, 0.0, 1.0]])

    def test_jaccard_threshold_differs_from_greedy(self):
        q2, q3, mask = self._greedy_vs_hungarian_case()
        # threshold 0.5 sets: C1 = rows 0-19, C2 = rows 0-9; raw cols are blocks A, B, C
        j = qbar.jaccard_matrix(q2, q3, mask, "threshold", 0.5)
        self.assertEqual(j.tolist(), [[0.5, 0.5, 0.0], [1.0, 0.0, 0.0]])
        perm, sims = qbar.match_next_jaccard(q2, q3, mask, "threshold", 0.5)
        self.assertEqual(perm, [1, 0, 2])
        self.assertEqual(sims, [0.5, 1.0, None])
        self.assertEqual(qbar.match_next(q2, q3, mask)[0], [0, 2, 1])

    def test_jaccard_is_optimal_by_brute_force(self):
        import itertools
        rng = np.random.default_rng(11)
        for kind in ("dominant", "threshold"):
            for _ in range(10):
                k = int(rng.integers(2, 5))
                q_prev = rng.dirichlet(np.ones(k) * 0.5, size=30)
                q_new = rng.dirichlet(np.ones(k + 1) * 0.5, size=30)
                mask = np.ones(30, dtype=bool)
                j = qbar.jaccard_matrix(q_prev, q_new, mask, kind, 0.3)
                best = max(sum(j[c, p[c]] for c in range(k)) for p in itertools.permutations(range(k + 1), k))
                perm, sims = qbar.match_next_jaccard(q_prev, q_new, mask, kind, 0.3)
                self.assertAlmostEqual(sum(sims[:-1]), best)
                self.assertEqual(sorted(perm), list(range(k + 1)))

    def test_jaccard_without_scipy_exits(self):
        import builtins
        from unittest import mock
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name.startswith("scipy"):
                raise ImportError("no scipy")
            return real_import(name, *args, **kwargs)

        q2, q3, mask = self._greedy_vs_hungarian_case()
        with mock.patch("builtins.__import__", side_effect=fake_import):
            with self.assertRaises(SystemExit) as cm:
                qbar.match_next_jaccard(q2, q3, mask)
        self.assertIn("jaccard", str(cm.exception.code))
        self.assertIn("scipy", str(cm.exception.code))

    def test_cli_jaccard_writes_jaccard_column(self):
        q2, q3, _ = self._greedy_vs_hungarian_case()
        with tempfile.TemporaryDirectory() as tmp:
            for k, q in ((2, q2), (3, q3)):
                np.savetxt(os.path.join(tmp, "t.%d.Q" % k), q, fmt="%.6f")
            ids = os.path.join(tmp, "ids.txt")
            with open(ids, "w") as f:
                f.write("".join("s%d\n" % i for i in range(30)))
            out = os.path.join(tmp, "o")
            qbar.main(["--q", os.path.join(tmp, "t.2.Q"), os.path.join(tmp, "t.3.Q"), "--ids", ids,
                       "--align-method", "jaccard", "--jaccard-set", "threshold", "--outdir", out])
            with open(os.path.join(out, "align.tsv")) as f:
                self.assertEqual(f.read().splitlines(), ["K_to\tn_mask\tjaccard", "3\t30\t0.500 1.000"])
            with open(os.path.join(out, "perm_K3.tsv")) as f:
                self.assertEqual([l.split("\t")[1] for l in f.read().splitlines()[1:]], ["2", "1", "3"])
        args = qbar.build_parser().parse_args(["--q", "x.Q", "--outdir", "o"])
        self.assertEqual((args.jaccard_set, args.jaccard_cut), ("dominant", 0.5))

    def _report(self, method, q2, q3, low=None):
        groups = ["A"] * 10 + ["B"] * 10 + ["C"] * (q2.shape[0] - 20)
        aligned, perm, meta = qbar.align_qs({2: q2, 3: q3}, groups, "", "all", [], 0.75, True, method)
        rows, cut = qbar.align_report_rows(aligned, meta, groups, method, perm, low)
        return rows, cut, aligned

    def test_report_greedy_and_hungarian(self):
        q2, q3, _ = self._greedy_vs_hungarian_case()
        for method, raws, parent in (("greedy", [1, 3, 2], "C1"), ("hungarian", [2, 1, 3], "C2")):
            rows, cut, aligned = self._report(method, q2, q3)
            self.assertEqual(cut, 0.5)
            self.assertEqual([r["raw_column"] for r in rows], raws)
            self.assertEqual([r["matched_from"] for r in rows], ["C1", "C2", "new"])
            self.assertEqual(rows[0]["similarity"], rows[0]["pearson"])
            self.assertEqual(rows[2]["split_parent"], parent)
            self.assertEqual(rows[2]["runner_up"], "C2" if parent == "C1" else "C1")
            self.assertEqual(rows[0]["runner_up"], "")
            self.assertEqual(rows[2]["low_confidence"], "NA")
        rows, _cut, _a = self._report("greedy", q2, q3)
        self.assertEqual(rows[1]["low_confidence"], "yes")  # r = -0.11
        self.assertEqual(rows[0]["top_groups_mean"].split(";")[0], "A:1.000")

    def test_report_split_parent_share(self):
        prev = np.array([[1.0, 0.0], [0.5, 0.5], [0.0, 1.0]])
        c, share, ru, ru_share = qbar.split_parent_of(prev, np.array([0.0, 1.0, 1.0]), np.ones(3, dtype=bool))
        self.assertEqual((c, ru), (1, 0))
        self.assertAlmostEqual(share, 0.75)
        self.assertAlmostEqual(ru_share, 0.25)
        # tie goes to the lower column
        c, share, ru, ru_share = qbar.split_parent_of(prev, np.array([0.0, 1.0, 0.0]), np.ones(3, dtype=bool))
        self.assertEqual((c, ru, share, ru_share), (0, 1, 0.5, 0.5))

    def test_report_zero_new_column_is_na(self):
        prev = np.array([[1.0, 0.0], [0.0, 1.0]])
        self.assertEqual(qbar.split_parent_of(prev, np.zeros(2), np.ones(2, dtype=bool)), (None, None, None, None))
        n = 30
        q2 = np.zeros((n, 2))
        q2[:15, 0] = 1.0
        q2[15:, 1] = 1.0
        q3 = np.zeros((n, 3))
        q3[:15, 0] = 1.0
        q3[15:, 1] = 1.0
        for method in qbar.ALIGN_METHODS:
            rows, _cut, _a = self._report(method, q2, q3)
            new = rows[2]
            self.assertEqual(new["matched_from"], "new")
            self.assertEqual((new["split_parent"], new["parent_share"], new["runner_up"], new["runner_up_share"]),
                             ("NA", "NA", "NA", "NA"), method)

    def test_report_txt_zero_new_column_prints_na(self):
        n = 30
        q2 = np.zeros((n, 2))
        q2[:15, 0] = 1.0
        q2[15:, 1] = 1.0
        q3 = np.zeros((n, 3))
        q3[:15, 0] = 1.0
        q3[15:, 1] = 1.0
        groups = ["A"] * 10 + ["B"] * 10 + ["C"] * (n - 20)
        for method in qbar.ALIGN_METHODS:
            aligned, perm, meta = qbar.align_qs({2: q2, 3: q3}, groups, "", "all", [], 0.75, True, method)
            with tempfile.TemporaryDirectory() as d:
                qbar.write_align_report(d, aligned, meta, groups, method, perm)
                with open(os.path.join(d, "align_report.txt")) as f:
                    line = [x for x in f if " new, split from " in x][0]
            self.assertIn("C3 new, split from NA (parent share NA; runner-up NA NA)", line, method)

    def test_report_pong_uses_split_pair(self):
        q2, q3, _ = self._split_case()
        rows, cut, _a = self._report("pong", q2, q3)
        self.assertEqual(cut, 0.8)
        self.assertEqual(rows[2]["split_parent"], "C2")
        self.assertEqual(rows[2]["parent_share"], "1.000")
        self.assertEqual((rows[2]["runner_up"], rows[2]["runner_up_share"]), ("C1", "0.000"))
        self.assertEqual(rows[0]["similarity"], "1.000")
        self.assertEqual(rows[2]["top_groups_dominant"], "B:10")

    def test_report_jaccard_and_low_override(self):
        q2, q3, _ = self._greedy_vs_hungarian_case()
        rows, cut, _a = self._report("jaccard", q2, q3, low=0.6)
        self.assertEqual(cut, 0.6)
        self.assertEqual([r["low_confidence"] for r in rows], ["yes", "no", "NA"])
        self.assertNotEqual(rows[0]["similarity"], rows[0]["pearson"])

    def test_low_confidence_matches_printed_similarity(self):
        # 0.4996 prints as 0.500. The stored flag must follow that printed number.
        sim = 0.4996
        self.assertEqual("%.3f" % sim, "0.500")
        self.assertLess(sim, 0.5)
        prev = np.array([[1.0, 0.0], [1.0, 0.0], [0.0, 1.0], [0.0, 1.0]])
        new = np.array([[1.0, 0.0, 0.0], [0.8, 0.2, 0.0], [0.0, 1.0, 0.0], [0.0, 0.2, 0.8]])
        mask = np.ones(4, dtype=bool)
        aligned = {2: prev, 3: new}
        perm = {3: [0, 1, 2]}
        groups = ["A", "A", "B", "B"]
        meta = {3: {"n_mask": 4, "pearson": [sim, 0.9, None], "mask": mask}}
        rows, cut = qbar.align_report_rows(aligned, meta, groups, "greedy", perm, 0.5)
        self.assertEqual(cut, 0.5)
        self.assertEqual(rows[0]["similarity"], "0.500")
        self.assertEqual(rows[0]["low_confidence"], "no")
        below = 0.4944
        self.assertEqual("%.3f" % below, "0.494")
        self.assertLess(below, 0.5)
        meta_below = {3: {"n_mask": 4, "pearson": [below, 0.9, None], "mask": mask}}
        rows_below, _cut = qbar.align_report_rows(aligned, meta_below, groups, "greedy", perm, 0.5)
        self.assertEqual(rows_below[0]["similarity"], "0.494")
        self.assertEqual(rows_below[0]["low_confidence"], "yes")

    def test_tied_or_low_confidence_new_column_is_not_called_a_split(self):
        # Shares [0.5, 0.5]. The lower column stays in the TSV. The text must not say "split from".
        prev = np.array([[1.0, 0.0], [0.5, 0.5], [0.0, 1.0]])
        new_col = np.array([0.0, 1.0, 0.0])
        parent, share, runner, runner_share = qbar.split_parent_of(prev, new_col, np.ones(3, dtype=bool))
        self.assertEqual((parent, share, runner, runner_share), (0, 0.5, 1, 0.5))
        new = np.column_stack([prev, new_col])
        groups = ["A", "B", "C"]
        meta = {3: {"n_mask": 3, "pearson": [1.0, 1.0, None], "mask": np.ones(3, dtype=bool)}}
        with tempfile.TemporaryDirectory() as d:
            qbar.write_align_report(d, {2: prev, 3: new}, meta, groups, "greedy", {3: [0, 1, 2]})
            with open(os.path.join(d, "align_report.tsv")) as f:
                tied_row = f.read().splitlines()[-1].split("\t")
            with open(os.path.join(d, "align_report.txt")) as f:
                tied_txt = f.read()
        self.assertEqual(tied_row[8], "C1")
        self.assertEqual((tied_row[9], tied_row[11]), ("0.500", "0.500"))
        self.assertIn("parent not identified", tied_txt)
        self.assertNotIn("split from", tied_txt)

        # New column is exactly old column 1. A matched similarity of 0 is under the 0.5 cut.
        prev2 = np.array([[1.0, 0.0], [0.0, 1.0]])
        new2 = np.array([[1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])
        parent2, share2, runner2, runner_share2 = qbar.split_parent_of(
            prev2, new2[:, 2], np.ones(2, dtype=bool))
        self.assertEqual((parent2, share2, runner2, runner_share2), (1, 1.0, 0, 0.0))
        meta2 = {3: {"n_mask": 2, "pearson": [0.0, 1.0, None], "mask": np.ones(2, dtype=bool)}}
        with tempfile.TemporaryDirectory() as d:
            rows = qbar.write_align_report(
                d, {2: prev2, 3: new2}, meta2, ["A", "B"], "greedy", {3: [0, 1, 2]})
            with open(os.path.join(d, "align_report.tsv")) as f:
                low_row = f.read().splitlines()[-1].split("\t")
            with open(os.path.join(d, "align_report.txt")) as f:
                low_txt = f.read()
        self.assertEqual(rows[0]["low_confidence"], "yes")
        self.assertEqual(low_row[8], "C2")
        self.assertIn("not a split", low_txt)
        self.assertNotIn("split from", low_txt)

    def test_cli_report_is_opt_in(self):
        q2, q3, _ = self._greedy_vs_hungarian_case()
        with tempfile.TemporaryDirectory() as tmp:
            for k, q in ((2, q2), (3, q3)):
                np.savetxt(os.path.join(tmp, "t.%d.Q" % k), q, fmt="%.6f")
            ids = os.path.join(tmp, "ids.txt")
            with open(ids, "w") as f:
                f.write("".join("s%d\n" % i for i in range(30)))
            base = ["--q", os.path.join(tmp, "t.2.Q"), os.path.join(tmp, "t.3.Q"), "--ids", ids]
            qbar.main(base + ["--outdir", os.path.join(tmp, "a")])
            self.assertFalse(os.path.exists(os.path.join(tmp, "a", "align_report.tsv")))
            for m in qbar.ALIGN_METHODS:
                out = os.path.join(tmp, m)
                qbar.main(base + ["--align-method", m, "--align-report", "--outdir", out])
                with open(os.path.join(out, "align_report.tsv")) as f:
                    lines = f.read().splitlines()
                self.assertEqual(lines[0].split("\t"), list(qbar.REPORT_COLS))
                self.assertEqual(len(lines), 4)
                with open(os.path.join(out, "align_report.txt")) as f:
                    txt = f.read()
                self.assertIn("method: %s" % m, txt)
                self.assertIn("K=2 -> K=3", txt)
                self.assertIn("runner-up", txt)

    def _hc_q(self):
        rng = np.random.default_rng(3)
        return rng.dirichlet(np.ones(3) * 0.4, size=25)

    def test_hclust_default_matches_scipy_average_correlation(self):
        from scipy.cluster.hierarchy import leaves_list, linkage
        q = self._hc_q()
        self.assertEqual(qbar.hclust_order(q), [int(x) for x in leaves_list(linkage(q, "average", "correlation"))])
        self.assertEqual(qbar.hclust_block_order(q), qbar.hclust_order(q))

    def test_hclust_dist_and_linkage_follow_scipy(self):
        from scipy.cluster.hierarchy import leaves_list, linkage
        q = self._hc_q()
        for dist, link in (("euclidean", "average"), ("braycurtis", "complete"), ("euclidean", "ward"),
                           ("correlation", "complete")):
            want = [int(x) for x in leaves_list(linkage(q, link, dist))]
            self.assertEqual(qbar.hclust_order(q, dist, link), want)
        self.assertNotEqual(qbar.hclust_order(q, "euclidean", "ward"), qbar.hclust_order(q))

    def test_braycurtis_nonfinite_distance_exits(self):
        # Bray-Curtis of two all-zero rows is 0/0, which is not finite.
        # Correlation already jitters a zero-variance row and must still return an order.
        zeros = np.zeros((4, 3))
        with self.assertRaises(SystemExit) as cm:
            qbar.hclust_order(zeros, "braycurtis", "average")
        self.assertIn("braycurtis", str(cm.exception.code))
        self.assertIn("非有限", str(cm.exception.code))
        one_zero = np.array([[1.0, 0.0], [0.0, 1.0], [0.0, 0.0], [0.4, 0.6]])
        # One all-zero row against nonzero rows is finite: the denominator is the other row.
        self.assertEqual(sorted(qbar.hclust_order(one_zero, "braycurtis", "average")), [0, 1, 2, 3])
        two_zero = np.array([[0.0, 0.0], [0.0, 0.0], [0.2, 0.8], [0.7, 0.3]])
        with self.assertRaises(SystemExit) as cm2:
            qbar.hclust_order(two_zero, "braycurtis", "average")
        self.assertIn("非有限", str(cm2.exception.code))
        corr = qbar.hclust_order(zeros, "correlation", "average")
        self.assertEqual(sorted(corr), [0, 1, 2, 3])
        finite = np.array([[0.2, 0.8], [0.9, 0.1], [0.4, 0.6], [0.7, 0.3]])
        from scipy.cluster.hierarchy import leaves_list, linkage
        want = [int(x) for x in leaves_list(linkage(finite, "average", "braycurtis"))]
        self.assertEqual(qbar.hclust_order(finite, "braycurtis", "average"), want)

    def test_ward_needs_euclidean(self):
        for dist in ("correlation", "braycurtis"):
            with self.assertRaises(SystemExit) as cm:
                qbar.hclust_order(self._hc_q(), dist, "ward")
            self.assertIn("euclidean", str(cm.exception.code))
        with self.assertRaises(SystemExit):
            qbar.main(["--q", "x.Q", "--hclust-linkage", "ward", "--outdir", "o"])

    def test_hclust_olo_matches_scipy(self):
        from scipy.cluster.hierarchy import leaves_list, linkage, optimal_leaf_ordering
        from scipy.spatial.distance import pdist
        q = self._hc_q()
        z = optimal_leaf_ordering(linkage(q, "average", "correlation"), pdist(q, "correlation"))
        got = qbar.hclust_order(q, olo=True)
        self.assertEqual(got, [int(x) for x in leaves_list(z)])
        self.assertEqual(sorted(got), list(range(25)))

    def test_hclust_pre_dominant_keeps_blocks_contiguous(self):
        q = self._hc_q()
        order = qbar.hclust_block_order(q, pre="dominant")
        tops = [int(q[i].argmax()) for i in order]
        self.assertEqual(tops, sorted(tops))
        self.assertEqual(sorted(order), list(range(25)))
        for c in range(3):
            ii = [i for i in range(25) if q[i].argmax() == c]
            sub = [ii[j] for j in qbar.hclust_order(q[ii])]
            self.assertEqual([i for i in order if q[i].argmax() == c], sub)

    def test_hclust_order_is_the_same_for_every_k(self):
        # row i carries i in a tiny offset of column 1 so each drawn row can be identified
        n = 24
        rng = np.random.default_rng(5)
        seen = {}
        real = qbar.ancestry_image

        def spy(q, hexes, height):
            seen[q.shape[1]] = [int(round(x)) for x in q[:, -1] * 1e6 % 1000]
            return real(q, hexes, height)

        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp:
            paths = []
            for k in (2, 3, 4):
                q = rng.dirichlet(np.ones(k), size=n)
                q[:, -1] = np.floor(q[:, -1] * 1000) / 1000 + np.arange(n) * 1e-6
                path = os.path.join(tmp, "t.%d.Q" % k)
                np.savetxt(path, q, fmt="%.9f")
                paths.append(path)
            ids = os.path.join(tmp, "ids.txt")
            with open(ids, "w") as f:
                f.write("".join("s%02d\n" % i for i in range(n)))
            out = os.path.join(tmp, "o")
            with mock.patch.object(qbar, "ancestry_image", side_effect=spy):
                qbar.main(["--q"] + paths + ["--ids", ids, "--no-align", "--within", "hclust",
                           "--hclust-dist", "euclidean", "--hclust-linkage", "ward", "--hclust-olo",
                           "--hclust-pre", "dominant", "--hclust-k", "3", "--outdir", out])
            with open(os.path.join(out, "order.tsv")) as f:
                want = [int(l.split("\t")[1][1:]) for l in f.read().splitlines()[1:]]
        self.assertEqual(sorted(seen), [2, 3, 4])
        for k in (2, 3, 4):
            self.assertEqual(seen[k], want)

    def test_gap_in_k_refuses_align(self):
        q = {
            2: np.array([[1.0, 0.0], [0.0, 1.0]]),
            4: np.array([[1.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 1.0]]),
        }
        with self.assertRaises(SystemExit):
            qbar.align_qs(q, ["A", "B"], "", "all", [], 0.75, True)

    def test_match_next_dispatches_pong_and_jaccard(self):
        # AUD-03 toy, built here. Old C1 correlates perfectly with the small
        # new column, so greedy Pearson takes that column. pong prefers the
        # large column. Expected pong and jaccard values are the dedicated
        # functions, not a copy of match_next.
        c1 = np.array([0.90, 0.80, 0.70, 0.30, 0.20, 0.10])
        large = np.array([0.62, 0.58, 0.54, 0.46, 0.40, 0.34])
        third = np.array([0.335, 0.380, 0.425, 0.525, 0.590, 0.655])
        q_prev = np.column_stack([c1, 1.0 - c1])
        q_new = np.column_stack([large, 0.05 * c1, third])
        self.assertTrue(np.allclose(q_new.sum(axis=1), 1.0))
        mask = np.ones(q_prev.shape[0], dtype=bool)
        greedy = qbar.match_next(q_prev, q_new, mask, "greedy")
        pong = qbar.match_next_pong(q_prev, q_new, mask)
        self.assertNotEqual(greedy[0], pong[0])
        self.assertEqual(qbar.match_next(q_prev, q_new, mask, "pong"), pong)

        q2, q3, mask2 = self._greedy_vs_hungarian_case()
        jac = qbar.match_next_jaccard(q2, q3, mask2, "threshold", 0.5)
        self.assertNotEqual(qbar.match_next(q2, q3, mask2, "greedy")[0], jac[0])
        self.assertEqual(
            qbar.match_next(q2, q3, mask2, "jaccard", "threshold", 0.5),
            jac,
        )
        self.assertEqual(
            qbar.match_next(q2, q3, mask2, "jaccard"),
            qbar.match_next_jaccard(q2, q3, mask2),
        )


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

    def test_narrow_group_name_warns_on_stderr(self):
        # render skips a name when the bar span is under 14 px. That skip must be said on stderr.
        # n=4 and bar_w=40: samples 3:4 are 10 px, samples 0:3 are 30 px.
        import io
        from contextlib import redirect_stderr
        n = 4
        bar_w = 40
        self.assertLess(int(4 * bar_w / n) - int(3 * bar_w / n), 14)
        self.assertGreaterEqual(int(3 * bar_w / n) - int(0 * bar_w / n), 14)
        image = np.zeros((2, n, 3), dtype=np.uint8)
        image[:, :, 0] = 255
        spans = [
            {"name": "Wide", "start": 0, "end": 3},
            {"name": "Tiny", "start": 3, "end": 4},
        ]
        rows = [{"k": 2, "image": image, "legend": [("#ff0000", "C1")]}]
        buf = io.StringIO()
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "bar.png")
            with redirect_stderr(buf):
                qbar.render(path, rows, spans, bar_w, 20, "")
            err = buf.getvalue()
            self.assertIn("注意：组 Tiny 的条宽小于 14 像素，图上没写组名", err)
            self.assertNotIn("Wide", err)
            with Image.open(path) as img:
                self.assertEqual(img.mode, "RGB")
                self.assertGreater(img.size[0], bar_w)


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

    def test_non_numeric_q_names_the_file(self):
        # loadtxt cannot parse a comma or a header. The exit must name the file.
        # A whitespace-separated numeric matrix is the format that is read.
        with tempfile.TemporaryDirectory() as td:
            comma = os.path.join(td, "bad.2.Q")
            with open(comma, "w") as f:
                f.write("0.2,0.8\n0.3,0.7\n")
            with self.assertRaises(SystemExit) as cm:
                qbar.read_q(comma)
            self.assertIn(comma, str(cm.exception.code))
            self.assertIn("空白分隔", str(cm.exception.code))
            header = os.path.join(td, "head.2.Q")
            with open(header, "w") as f:
                f.write("sample a\n0.2 0.8\n")
            with self.assertRaises(SystemExit) as cmh:
                qbar.read_q(header)
            self.assertIn(header, str(cmh.exception.code))
            good = os.path.join(td, "ok.2.Q")
            with open(good, "w") as f:
                f.write("0.2 0.8\n0.4 0.6\n")
            got = qbar.read_q(good)
            self.assertTrue(np.allclose(got, [[0.2, 0.8], [0.4, 0.6]]))
        help_s = _cli_flag(qbar.build_parser(), "--q").help or ""
        self.assertIn("空白分隔", help_s)
        self.assertIn(".q", help_s)
        en = open("README.md", encoding="utf-8").read()
        zh = open("README.zh.md", encoding="utf-8").read()
        self.assertIn("whitespace-separated numeric", en)
        self.assertIn("空白分隔的数字", zh)


def _cli_flag(parser, name):
    for action in parser._actions:
        if name in action.option_strings:
            return action
    raise AssertionError("missing flag %s" % name)


class DocstringTests(unittest.TestCase):
    def test_module_docstring_names_align_methods(self):
        # Expectations come from argparse, not from the wording under test.
        doc = qbar.__doc__ or ""
        flat = " ".join(doc.split())
        parser = qbar.build_parser()
        align = _cli_flag(parser, "--align-method")
        missing = [name for name in align.choices if name not in flat]
        self.assertEqual(
            missing, [],
            "module docstring is missing --align-method choices",
        )
        self.assertEqual(align.default, "greedy")
        self.assertRegex(flat, r"default --align-method\s+is greedy")
        self.assertNotIn("column matching is greedy", flat)
        self.assertIn("--align-report", flat)
        dist = _cli_flag(parser, "--hclust-dist")
        link = _cli_flag(parser, "--hclust-linkage")
        pre = _cli_flag(parser, "--hclust-pre")
        missing_h = [
            name for name in list(dist.choices) + list(link.choices) + list(pre.choices)
            if name not in flat
        ]
        self.assertEqual(missing_h, [])
        self.assertEqual(dist.default, "correlation")
        self.assertEqual(link.default, "average")
        self.assertIn("hclust default is average linkage on correlation", flat)
        self.assertIn("--hclust-olo", flat)

    def test_no_c_align_name(self):
        import inspect
        src = inspect.getsource(qbar)
        self.assertNotIn("c_align", src)
        doc = qbar.core_mask.__doc__ or ""
        self.assertIn("qmax > cut", doc)
        help_s = _cli_flag(qbar.build_parser(), "--align-mode").help or ""
        self.assertNotIn("c_align", help_s)
        self.assertIn("严格大于", help_s)

    def test_align_mode_help_names_every_method(self):
        help_s = _cli_flag(qbar.build_parser(), "--align-mode").help or ""
        missing = [name for name in qbar.ALIGN_METHODS if name not in help_s]
        self.assertEqual(missing, [], "align-mode help must name every ALIGN_METHODS entry")

    def test_no_align_help_states_anchor_exception(self):
        # Two K, alignment off. anchor_perm runs on every K, not only the lowest.
        q2 = np.array([[0.2, 0.8], [0.9, 0.1]])
        q3 = np.array([[0.1, 0.2, 0.7], [0.6, 0.3, 0.1]])
        groups = ["A", "B"]
        _aligned, perm, _meta = qbar.align_qs(
            {2: q2, 3: q3}, groups, "A", "all", [], 0.75, False)
        self.assertEqual(perm[2], qbar.anchor_perm(q2, groups, "A"))
        self.assertEqual(perm[3], qbar.anchor_perm(q3, groups, "A"))
        self.assertNotEqual(perm[2], list(range(q2.shape[1])))
        self.assertNotEqual(perm[3], list(range(q3.shape[1])))
        parser = qbar.build_parser()
        epilog = parser.epilog or ""
        anchor = _cli_flag(parser, "--anchor-group").help or ""
        self.assertIn("--anchor-group", epilog)
        self.assertIn("--no-align", anchor)
        self.assertIn("每个 K", anchor)

    def test_align_mode_help_states_core_fallback(self):
        doc = " ".join((qbar.core_mask.__doc__ or "").split())
        self.assertIn("purest", doc)
        self.assertIn("lower K", doc)
        help_s = _cli_flag(qbar.build_parser(), "--align-mode").help or ""
        self.assertIn("最纯", help_s)
        self.assertIn("较低 K", help_s)

    def test_q_bounds_are_documented(self):
        import inspect
        import re
        src = inspect.getsource(qbar.check_shapes)
        self.assertIn("q < -1e-6", src)
        self.assertIn("q > 1.0 + 1e-4", src)
        self.assertIn("> 0.05", src)
        doc = qbar.check_shapes.__doc__ or ""
        for token in ("-1e-6", "1+1e-4", "0.05"):
            self.assertIn(token, doc)
        for path in ("README.md", "README.zh.md"):
            text = open(path, encoding="utf-8").read()
            for token in ("-1e-6", "1e-4", "0.05"):
                self.assertRegex(
                    text,
                    r"(?<![\w.])" + re.escape(token) + r"(?![\w])",
                    "%s missing %s" % (path, token),
                )

    def test_readmes_name_every_cli_option(self):
        import re
        flags = []
        for action in qbar.build_parser()._actions:
            for name in action.option_strings:
                if name in ("-h", "--help"):
                    continue
                flags.append(name)
        for path in ("README.md", "README.zh.md"):
            text = open(path, encoding="utf-8").read()
            missing = [
                name for name in flags
                if re.search(r"(?<![\w-])" + re.escape(name) + r"(?![\w-])", text) is None
            ]
            self.assertEqual(missing, [], path)

    def test_group_separators_are_documented(self):
        # Same splits as main() for --blocks and parse_colors for --color.
        self.assertEqual(
            [x.strip() for x in "East,West,North".split(",") if x.strip()],
            ["East", "West", "North"],
        )
        self.assertEqual("A=B=#112233".split("=", 1)[0], "A")
        blocks = _cli_flag(qbar.build_parser(), "--blocks").help or ""
        color = _cli_flag(qbar.build_parser(), "--color").help or ""
        self.assertIn("不能含逗号", blocks)
        self.assertIn("不能含等号", color)
        en = open("README.md", encoding="utf-8").read()
        zh = open("README.zh.md", encoding="utf-8").read()
        self.assertIn("cannot contain a comma", en)
        self.assertIn("cannot contain `=`", en)
        self.assertIn("不能含逗号", zh)
        self.assertIn("不能含等号", zh)

    def test_align_mode_help_requires_qmax_at_both_k(self):
        # core_mask keeps a person only when qmax is above the cut at both
        # adjacent K (q_prev and q_new). The help must say that.
        help_s = _cli_flag(qbar.build_parser(), "--align-mode").help or ""
        self.assertIn("相邻两个 K 的 qmax 都严格大于 --qmax", help_s)
        doc = qbar.core_mask.__doc__ or ""
        self.assertNotIn("c_align", doc)
        self.assertIn("both K", doc)

    def test_readmes_state_no_align_anchor_exception(self):
        # Help already says --no-align still runs the anchor on every K.
        # A paragraph that only names both flags is not enough: the alignment
        # section already does that while still saying the anchor is the lowest K.
        def paragraphs(text):
            return [p.strip() for p in text.split("\n\n") if p.strip()]

        en = open("README.md", encoding="utf-8").read()
        zh = open("README.zh.md", encoding="utf-8").read()
        en_ok = [
            p for p in paragraphs(en)
            if "--no-align" in p and "--anchor-group" in p and "every K" in p and "C1" in p
        ]
        zh_ok = [
            p for p in paragraphs(zh)
            if "--no-align" in p and "--anchor-group" in p and "每个 K" in p and "C1" in p
        ]
        self.assertTrue(en_ok, "README.md has no --no-align paragraph for the every-K anchor")
        self.assertTrue(zh_ok, "README.zh.md has no --no-align paragraph for the every-K anchor")


if __name__ == "__main__":
    unittest.main()
