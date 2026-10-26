import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { DEFAULT_BAR_WIDTH, classifyOutputDiffs } from "./web_check.mjs";

const repo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const python = path.join(repo, ".venv-audit", "bin", "python");

function drawPair(dir) {
  const script = [
    "from PIL import Image, ImageDraw",
    "import os, sys",
    "root = sys.argv[1]",
    "BAR_LEFT = 56",
    "bar_w = 2200",
    "height = 120",
    "gap = 12",
    "def make(legend_w, name, flip):",
    "    width = BAR_LEFT + bar_w + gap + legend_w + 16",
    "    im = Image.new('RGB', (width, height), (255, 255, 255))",
    "    draw = ImageDraw.Draw(im)",
    "    draw.rectangle([BAR_LEFT, 8, BAR_LEFT + bar_w - 1, height - 48 - 1], fill=(30, 80, 160))",
    "    lx = BAR_LEFT + bar_w + gap",
    "    draw.rectangle([lx, 10, lx + max(legend_w - 1, 0), 40], fill=(0, 0, 0))",
    "    if flip:",
    "        im.putpixel((BAR_LEFT, 8), (255, 0, 0))",
    "    im.save(os.path.join(root, name))",
    "make(80, 'same_a.png', False)",
    "make(160, 'same_b.png', False)",
    "make(80, 'bad_a.png', False)",
    "make(160, 'bad_b.png', True)",
    "open(os.path.join(root, 'a.pdf'), 'wb').write(b'pdf-a')",
    "open(os.path.join(root, 'b.pdf'), 'wb').write(b'pdf-b')",
  ].join("\n");
  const proc = spawnSync(python, ["-c", script, dir], { encoding: "utf8" });
  if (proc.status !== 0) {
    throw new Error(proc.stderr || proc.stdout || "could not draw the PNG pair");
  }
}

test("a legend-width pair is explained and a bar pixel is not", function () {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "qbar-bar-crop-"));
  drawPair(dir);
  const options = { barW: DEFAULT_BAR_WIDTH, python: python };
  const same = classifyOutputDiffs([
    {
      rel: "bar_K2.png",
      leftPath: path.join(dir, "same_a.png"),
      rightPath: path.join(dir, "same_b.png"),
      sameBytes: false,
    },
  ], options);
  assert.deepEqual(same.unexpected, []);
  assert.equal(same.explained.length, 1);
  assert.match(same.explained[0], /bar crop matches; widths \d+ and \d+/);

  const bad = classifyOutputDiffs([
    {
      rel: "bar_K2.png",
      leftPath: path.join(dir, "bad_a.png"),
      rightPath: path.join(dir, "bad_b.png"),
      sameBytes: false,
    },
  ], options);
  assert.deepEqual(bad.explained, []);
  assert.equal(bad.unexpected.length, 1);
  assert.match(bad.unexpected[0], /crop mismatch [1-9]\d*/);

  const pdfOk = classifyOutputDiffs([
    {
      rel: "bar_K2.png",
      leftPath: path.join(dir, "same_a.png"),
      rightPath: path.join(dir, "same_b.png"),
      sameBytes: false,
    },
    {
      rel: "panel.pdf",
      leftPath: path.join(dir, "a.pdf"),
      rightPath: path.join(dir, "b.pdf"),
      sameBytes: false,
    },
  ], options);
  assert.deepEqual(pdfOk.unexpected, []);
  assert.match(pdfOk.explained.join("\n"), /panel.pdf bytes differ; every PNG bar crop matches/);

  const pdfBad = classifyOutputDiffs([
    {
      rel: "bar_K2.png",
      leftPath: path.join(dir, "bad_a.png"),
      rightPath: path.join(dir, "bad_b.png"),
      sameBytes: false,
    },
    {
      rel: "panel.pdf",
      leftPath: path.join(dir, "a.pdf"),
      rightPath: path.join(dir, "b.pdf"),
      sameBytes: false,
    },
  ], options);
  assert.match(pdfBad.unexpected.join("\n"), /PDF bytes differ; a PNG bar crop does not match/);

  const pdfAlone = classifyOutputDiffs([
    {
      rel: "panel.pdf",
      leftPath: path.join(dir, "a.pdf"),
      rightPath: path.join(dir, "b.pdf"),
      sameBytes: false,
    },
  ], options);
  assert.match(pdfAlone.unexpected.join("\n"), /PDF bytes differ; there is no PNG/);
});
