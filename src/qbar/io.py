"""Read Q matrices, sample ids, groups, an order file, and colour text.

``.Q`` is the default. ``.meanQ`` and ``.qopt`` are the same numeric
matrix with a different extension. An EIGENSTRAT ``.ind`` file supplies
sample ids from its first column.
"""
from __future__ import annotations

import csv
import glob
import os
import sys

import numpy as np

_Q_FORMATS = ("admixture", "meanq", "qopt")
_Q_EXT = {"admixture": ".q", "meanq": ".meanq", "qopt": ".qopt"}
_Q_DIR = {
    "admixture": ("*.Q", "*.q", "目录里没有 .Q 或 .q：%s"),
    "meanq": ("*.meanQ", "*.meanq", "目录里没有 .meanQ 或 .meanq：%s"),
    "qopt": ("*.qopt", "*.QOPT", "目录里没有 .qopt 或 .QOPT：%s"),
}


def _q_format(format):
    if format not in _Q_FORMATS:
        raise SystemExit("Q 格式只能是 admixture、meanq、qopt，收到 %s" % format)
    return format

def norm_hex(text):
    h = text.strip()
    if not h.startswith("#"):
        h = "#" + h
    if len(h) != 7:
        raise SystemExit("颜色要写成 #rrggbb，收到 %s" % text)
    int(h[1:], 16)
    return h.lower()


def load_ids(fam, ids_path, ind=None):
    chosen = []
    if fam:
        chosen.append("--fam")
    if ids_path:
        chosen.append("--ids")
    if ind:
        chosen.append("--ind")
    if len(chosen) > 1:
        raise SystemExit("%s 只留一个" % " 和 ".join(chosen))
    if not chosen:
        raise SystemExit("需要 --fam（PLINK .fam）或 --ids（一行一个 IID，顺序与 Q 的行一致）")
    path = fam or ids_path or ind
    iids = []
    extra_n = 0
    example = None
    with open(path) as f:
        for line in f:
            parts = line.split()
            if not parts or parts[0].startswith("#"):
                continue
            if fam and len(parts) >= 2:
                iids.append(parts[1])
            else:
                # --ind keeps column 1 and does not warn. --ids still warns.
                if ids_path and len(parts) > 1:
                    extra_n += 1
                    if example is None:
                        example = line.strip()
                iids.append(parts[0])
    if not fam and extra_n:
        print(
            "注意：--ids 有 %d 行含有多个字段，只保留了每行第一个。例如：%s" % (extra_n, example),
            file=sys.stderr,
        )
    if len(iids) != len(set(iids)):
        raise SystemExit("样本名有重复：%s" % path)
    if not iids:
        raise SystemExit("样本名单是空的：%s" % path)
    return iids


def load_groups(path, iids, id_col, group_col, rest_name):
    groups = [""] * len(iids)
    if not path:
        return [rest_name] * len(iids)
    with open(path, newline="") as f:
        sample = f.read(4096)
        f.seek(0)
        delim = "\t" if sample.count("\t") >= sample.count(",") else ","
        reader = csv.DictReader(f, delimiter=delim)
        if reader.fieldnames is None:
            raise SystemExit("分组表没有表头：%s" % path)
        if id_col not in reader.fieldnames or group_col not in reader.fieldnames:
            raise SystemExit(
                "分组表里没有列 %s / %s。现有列：%s"
                % (id_col, group_col, ", ".join(reader.fieldnames))
            )
        mp = {}
        for row in reader:
            mp[str(row[id_col]).strip()] = (row.get(group_col) or "").strip()
    out = []
    for iid in iids:
        g = mp.get(iid, "").strip()
        out.append(g if g else rest_name)
    return out


def _dir_q(item, first_pat, second_pat):
    first = sorted(glob.glob(os.path.join(item, first_pat)))
    hits = list(first)
    seen_real = {os.path.realpath(f) for f in first}
    for f in sorted(glob.glob(os.path.join(item, second_pat))):
        key = os.path.realpath(f)
        if key in seen_real:
            continue
        seen_real.add(key)
        hits.append(f)
    return hits


def collect_q(items, format="admixture"):
    format = _q_format(format)
    first_pat, second_pat, empty_msg = _Q_DIR[format]
    files = []
    for item in items:
        if os.path.isdir(item):
            hits = _dir_q(item, first_pat, second_pat)
            if not hits:
                raise SystemExit(empty_msg % item)
        else:
            hits = sorted(glob.glob(item))
            if not hits:
                if any(ch in item for ch in "*?["):
                    raise SystemExit("没有匹配到 Q：%s" % item)
                hits = [item]
        files.extend(hits)
    uniq = []
    seen = set()
    for f in files:
        if f not in seen:
            seen.add(f)
            uniq.append(f)
    if not uniq:
        raise SystemExit("没有 Q 文件")
    return uniq


def read_q(path, format="admixture"):
    # admixture, meanq, and qopt share this numeric read, including trailing spaces.
    format = _q_format(format)
    if not os.path.isfile(path):
        raise SystemExit("找不到 Q：%s" % path)
    try:
        q = np.loadtxt(path, dtype=float, ndmin=2)
    except ValueError as exc:
        raise SystemExit("Q 只能是空白分隔的数字：%s" % path) from exc
    if q.size == 0 or q.ndim != 2:
        raise SystemExit("Q 是空的或不是矩阵：%s" % path)
    return q


def k_of(path, q, format="admixture"):
    # Filename K is the digit token immediately before the extension.
    # prefix.8.Q -> 8. toy.3.meanQ -> 3. myoutfiles.qopt -> none.
    # It must equal the column count. The returned K is the column count.
    format = _q_format(format)
    base = os.path.basename(path)
    stem, ext = os.path.splitext(base)
    if ext.lower() != _Q_EXT[format]:
        raise SystemExit("%s 的扩展名不符合格式 %s" % (path, format))
    tail = stem.rsplit(".", 1)[-1] if "." in stem else ""
    k_file = int(tail) if tail.isdigit() else None
    k_col = int(q.shape[1])
    if k_file is not None and k_file != k_col:
        raise SystemExit("%s 文件名是 K=%d，列数是 %d" % (path, k_file, k_col))
    return k_col


def load_q_set(paths, format="admixture"):
    format = _q_format(format)
    q_by_k = {}
    src = {}
    for path in paths:
        q = read_q(path, format=format)
        k = k_of(path, q, format=format)
        if k in q_by_k:
            raise SystemExit("K=%d 有两个 Q：%s 和 %s" % (k, src[k], path))
        q_by_k[k] = q
        src[k] = path
    return q_by_k, src


def check_shapes(q_by_k, n):
    """Reject a row-count mismatch, a NaN, or a loaded value < -1e-6 or > 1+1e-4.

    The endpoints -1e-6 and 1+1e-4 are kept. Inf still fails that range check.
    A row is kept, with a warning, when abs(sum - 1) > 0.05 on the loaded floats.
    """
    for k, q in sorted(q_by_k.items()):
        if q.shape[0] != n:
            raise SystemExit("K=%d 的 Q 有 %d 行，样本名单有 %d 行" % (k, q.shape[0], n))
        if np.any(q < -1e-6) or np.any(q > 1.0 + 1e-4):
            raise SystemExit("K=%d 的 Q 有超出 [0,1] 的数" % k)
        if np.any(np.isnan(q)):
            raise SystemExit("K=%d 的 Q 有 NaN" % k)
        bad = np.where(np.abs(q.sum(axis=1) - 1.0) > 0.05)[0]
        if len(bad):
            print("注意：K=%d 有 %d 行人的组分和离 1 超过 0.05，图上多出来的部分留白" % (k, len(bad)), file=sys.stderr)


def order_from_file(path, iids):
    """One IID per row, or a table whose header has a column named iid.

    A header is recognised only when the first cell is not itself a sample
    and one of the cells is exactly ``iid`` (case-insensitive). ``order.tsv``
    from a previous run is such a table: rank, iid, group.
    """
    lines = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            lines.append(line.split())
    if not lines:
        raise SystemExit("顺序文件是空的：%s" % path)
    head = [cell.lower() for cell in lines[0]]
    if "iid" in head and lines[0][head.index("iid")] not in set(iids):
        col = head.index("iid")
        want = [cells[col] for cells in lines[1:] if len(cells) > col]
    else:
        want = [cells[0] for cells in lines]
    if len(want) != len(set(want)):
        raise SystemExit("顺序文件里有重复的样本名：%s" % path)
    pos = {iid: i for i, iid in enumerate(iids)}
    missing = [x for x in want if x not in pos]
    if missing:
        raise SystemExit("顺序文件里有 %d 个名字不在样本名单中，例如 %s" % (len(missing), ", ".join(missing[:5])))
    order = [pos[x] for x in want]
    have = set(want)
    left = [i for i, iid in enumerate(iids) if iid not in have]
    if left:
        print("顺序文件少了 %d 人，这 %d 人按原名单顺序接在最后" % (len(left), len(left)), file=sys.stderr)
    order.extend(left)
    return order


def parse_colors(items, color_file):
    group, col = {}, {}
    raw = list(items or [])
    if color_file:
        with open(color_file) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                if len(parts) < 2:
                    raise SystemExit("颜色文件每行要是「名字  #rrggbb」：%s" % line)
                raw.append(parts[0] + "=" + parts[1])
    for item in raw:
        if "=" not in item:
            raise SystemExit("颜色写成 组名=#rrggbb 或 C3=#rrggbb，收到 %s" % item)
        key, hx = item.split("=", 1)
        key = key.strip()
        hx = norm_hex(hx)
        if key[:1] in ("C", "c") and key[1:].isdigit():
            col[int(key[1:])] = hx
        else:
            group[key] = hx
    return group, col
