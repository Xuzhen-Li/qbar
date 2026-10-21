#!/bin/bash
# Run the demo cases from the repository root.
# Usage: bash tools/run_demo_cases.sh PYTHON OUTROOT
# Each case writes OUTROOT/<case>/. Refuses a case directory that already
# exists and is not empty. Does not delete or overwrite existing files.
#
# QBAR_CMD, when set, is the qbar command split on spaces.
# Default: "$PYTHON" qbar.py
#   QBAR_CMD=qbar
#       runs the installed qbar command
#   QBAR_CMD="$PYTHON /path/to/qbar.py"
#       runs that interpreter on that file
# PYTHON is still required. It is the interpreter used when QBAR_CMD is unset.

set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: bash tools/run_demo_cases.sh PYTHON OUTROOT" >&2
  exit 2
fi

PYTHON=$1
OUTROOT=$2

if [[ -z "$PYTHON" || -z "$OUTROOT" ]]; then
  echo "PYTHON and OUTROOT must be non-empty" >&2
  exit 2
fi

# Resolve relative paths before changing directory.
if [[ "$PYTHON" != /* ]]; then
  PYTHON="$PWD/$PYTHON"
fi
if [[ "$OUTROOT" != /* ]]; then
  OUTROOT="$PWD/$OUTROOT"
fi

# This file lives at tools/run_demo_cases.sh.
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
REPO=$(cd "$SCRIPT_DIR/.." && pwd)
cd "$REPO"

export PYTHONDONTWRITEBYTECODE=1
export PYTHONHASHSEED=0

if [[ ! -f "$PYTHON" ]]; then
  echo "python not found: $PYTHON" >&2
  exit 2
fi
if [[ ! -d "$REPO/demo/2448" ]]; then
  echo "demo/2448 not found in $REPO" >&2
  exit 2
fi
if [[ -z "${QBAR_CMD:-}" && ! -f "$REPO/qbar.py" ]]; then
  echo "qbar.py not found in $REPO (set QBAR_CMD to run another qbar)" >&2
  exit 2
fi

mkdir -p "$OUTROOT"

launch_qbar() {
  if [[ -n "${QBAR_CMD:-}" ]]; then
    local -a cmd
    # Split on spaces so QBAR_CMD can be "python qbar.py" or "qbar".
    read -r -a cmd <<< "$QBAR_CMD"
    if [[ ${#cmd[@]} -eq 0 ]]; then
      echo "QBAR_CMD is empty" >&2
      exit 2
    fi
    "${cmd[@]}" "$@"
  else
    "$PYTHON" qbar.py "$@"
  fi
}

prepare_case() {
  local dest=$1
  if [[ -e "$dest" && ! -d "$dest" ]]; then
    echo "refuse: $dest exists and is not a directory" >&2
    exit 1
  fi
  if [[ -d "$dest" ]]; then
    local any
    any=$(ls -A "$dest")
    if [[ -n "$any" ]]; then
      echo "refuse: $dest exists and is not empty" >&2
      exit 1
    fi
  fi
  mkdir -p "$dest"
}

run_case() {
  local name=$1
  shift
  local dest="$OUTROOT/$name"
  prepare_case "$dest"
  echo "BEGIN $name $(date +%Y-%m-%dT%H:%M:%S%z)"
  set +e
  launch_qbar "$@" --outdir "$dest" >"$dest/_stdout.txt" 2>"$dest/_stderr.txt"
  local rc=$?
  set -e
  echo "END $name exit=$rc $(date +%Y-%m-%dT%H:%M:%S%z)"
  if [[ $rc -ne 0 ]]; then
    echo "case $name exited $rc (see $dest/_stderr.txt)" >&2
    exit "$rc"
  fi
}

# README quick start, with --outdir replaced by the case directory.
run_case quickstart \
  --q "demo/2448/ref2448_pruned.*.Q" \
  --fam demo/2448/ref2448_pruned.fam \
  --groups demo/2448/groups.tsv --id-col id --group-col group \
  --blocks C-Ad,CG1,CG2,CG3,CG4,CG5,CG6,W-Ad,WEE1,WEE2,WWE1,WWE2 \
  --within iid \
  --anchor-group WWE1 \
  --color WWE1=#4470b7 --color WEE1=#dc1f26 --color WEE2=#0b5475 \
  --color CG6=#981b1e --color CG4=#f7922c --color CG3=#835ca6 \
  --color CG5=#fbee61 --color WWE2=#f6a3b1

# Single K.
run_case single_k8 \
  --q demo/2448/ref2448_pruned.8.Q \
  --fam demo/2448/ref2448_pruned.fam \
  --groups demo/2448/groups.tsv --id-col id --group-col group \
  --blocks C-Ad,CG1,CG2,CG3,CG4,CG5,CG6,W-Ad,WEE1,WEE2,WWE1,WWE2 \
  --within iid \
  --color WWE1=#4470b7 --color WEE1=#dc1f26 --color WEE2=#0b5475 \
  --color CG6=#981b1e --color CG4=#f7922c --color CG3=#835ca6 \
  --color CG5=#fbee61 --color WWE2=#f6a3b1

# Order file, single K.
run_case order_file \
  --q demo/2448/ref2448_pruned.8.Q \
  --fam demo/2448/ref2448_pruned.fam \
  --groups demo/2448/groups.tsv --id-col id --group-col group \
  --order-file demo/2448/order.txt

# Within-group hclust with optimal leaf ordering.
run_case hclust_olo \
  --q "demo/2448/ref2448_pruned.[2-6].Q" \
  --fam demo/2448/ref2448_pruned.fam \
  --groups demo/2448/groups.tsv --id-col id --group-col group \
  --blocks C-Ad,CG1,CG2,CG3,CG4,CG5,CG6,W-Ad,WEE1,WEE2,WWE1,WWE2 \
  --within hclust \
  --anchor-group WWE1 \
  --hclust-olo

# Alignment report for each --align-method. Greedy is the default; it is
# passed explicitly here.
run_case report_greedy \
  --q "demo/2448/ref2448_pruned.[2-6].Q" \
  --fam demo/2448/ref2448_pruned.fam \
  --groups demo/2448/groups.tsv --id-col id --group-col group \
  --blocks C-Ad,CG1,CG2,CG3,CG4,CG5,CG6,W-Ad,WEE1,WEE2,WWE1,WWE2 \
  --within hclust \
  --anchor-group WWE1 \
  --align-method greedy \
  --align-report

run_case report_hungarian \
  --q "demo/2448/ref2448_pruned.[2-6].Q" \
  --fam demo/2448/ref2448_pruned.fam \
  --groups demo/2448/groups.tsv --id-col id --group-col group \
  --blocks C-Ad,CG1,CG2,CG3,CG4,CG5,CG6,W-Ad,WEE1,WEE2,WWE1,WWE2 \
  --within hclust \
  --anchor-group WWE1 \
  --align-method hungarian \
  --align-report

run_case report_pong \
  --q "demo/2448/ref2448_pruned.[2-6].Q" \
  --fam demo/2448/ref2448_pruned.fam \
  --groups demo/2448/groups.tsv --id-col id --group-col group \
  --blocks C-Ad,CG1,CG2,CG3,CG4,CG5,CG6,W-Ad,WEE1,WEE2,WWE1,WWE2 \
  --within hclust \
  --anchor-group WWE1 \
  --align-method pong \
  --align-report

run_case report_jaccard \
  --q "demo/2448/ref2448_pruned.[2-6].Q" \
  --fam demo/2448/ref2448_pruned.fam \
  --groups demo/2448/groups.tsv --id-col id --group-col group \
  --blocks C-Ad,CG1,CG2,CG3,CG4,CG5,CG6,W-Ad,WEE1,WEE2,WWE1,WWE2 \
  --within hclust \
  --anchor-group WWE1 \
  --align-method jaccard \
  --align-report

# Same three methods without --align-report.
run_case align_hungarian \
  --q "demo/2448/ref2448_pruned.[2-6].Q" \
  --fam demo/2448/ref2448_pruned.fam \
  --groups demo/2448/groups.tsv --id-col id --group-col group \
  --blocks C-Ad,CG1,CG2,CG3,CG4,CG5,CG6,W-Ad,WEE1,WEE2,WWE1,WWE2 \
  --within hclust \
  --anchor-group WWE1 \
  --align-method hungarian

run_case align_pong \
  --q "demo/2448/ref2448_pruned.[2-6].Q" \
  --fam demo/2448/ref2448_pruned.fam \
  --groups demo/2448/groups.tsv --id-col id --group-col group \
  --blocks C-Ad,CG1,CG2,CG3,CG4,CG5,CG6,W-Ad,WEE1,WEE2,WWE1,WWE2 \
  --within hclust \
  --anchor-group WWE1 \
  --align-method pong

run_case align_jaccard \
  --q "demo/2448/ref2448_pruned.[2-6].Q" \
  --fam demo/2448/ref2448_pruned.fam \
  --groups demo/2448/groups.tsv --id-col id --group-col group \
  --blocks C-Ad,CG1,CG2,CG3,CG4,CG5,CG6,W-Ad,WEE1,WEE2,WWE1,WWE2 \
  --within hclust \
  --anchor-group WWE1 \
  --align-method jaccard

# Core alignment mode. --align-groups is required for core mode.
# --qmax already defaults to 0.75, so it is not passed.
run_case core_mode \
  --q "demo/2448/ref2448_pruned.[2-6].Q" \
  --fam demo/2448/ref2448_pruned.fam \
  --groups demo/2448/groups.tsv --id-col id --group-col group \
  --blocks C-Ad,CG1,CG2,CG3,CG4,CG5,CG6,W-Ad,WEE1,WEE2,WWE1,WWE2 \
  --within iid \
  --anchor-group WWE1 \
  --align-mode core \
  --align-groups C-Ad,CG1,CG2,CG3,CG4,CG5,CG6,W-Ad,WEE1,WEE2,WWE1,WWE2

echo "ALL_CASES_OK $OUTROOT"
