# Workspace Agent Rules — Sipeed Tang Nano 20K Course

This repository teaches FPGA hardware design on the **Sipeed Tang Nano 20K** (`GW2AR-LV18QN88C8/I7`) using **Amaranth HDL** first and **Verilog by assimilation** second. Follow this paired lesson cadence and build workflow whenever creating or updating course content.

## Two-Lesson Cadence (Amaranth → Verilog)

Every new hardware concept is taught across a **pair of lessons** rather than mixing Amaranth authoring and raw Yosys Verilog dissection into a single lesson:

### 1. Odd-Numbered Lessons (`0001`, `0003`, `0005`, ...): Amaranth Concept
- **Goal:** Introduce one tightly scoped hardware concept in Amaranth HDL (`amaranth.lib.wiring.Component`).
- **Explain:** Break the design down block by block using parallel-circuit and analog-synth analogies (e.g., `m.d.comb` as continuous op-amp signal paths, `m.d.sync` as clocked sample-and-hold stages) before showing the complete `.py` listing.
- **Verify:** Back the lesson with a runnable project in `apps/<NNNN-slug>/` verified cycle-by-cycle with `amaranth.sim` + `pytest`, `ruff check`, `.cst` pin constraints, and OSS CAD Suite flashing steps (`yosys`, `nextpnr-himbaechel`, `gowin_pack`, `openFPGALoader`).
- **Scope boundary:** Do **not** dissect raw Yosys-generated `.v` output inline here. Link forward to the paired even-numbered lesson (`Lesson NNNN+1`) for the Verilog breakdown.

### 2. Even-Numbered Lessons (`0002`, `0004`, `0006`, ...): Generated Verilog Dissection
- **Goal:** Pair directly with the preceding Amaranth lesson and dissect the exact Verilog produced by `amaranth.back.verilog.convert(..., emit_src=False)`.
- **Companion app (`apps/<NNNN-slug>/`):**
  - Copy the runnable Amaranth module from the preceding odd-numbered app.
  - Generate the `.v` file verbatim via `emit_verilog()` (never hand-edit the generated `.v` file) and add a `!apps/<NNNN-slug>/<name>.v` negation rule in `.gitignore` so Git tracks the reference output.
  - Write `pytest` tests verifying byte-for-byte parity between the saved `.v` file and fresh `emit_verilog()` output, plus structural assertions for the Verilog constructs taught in the lesson.
- **Breakdown structure:**
  - Start with a big-picture signal-flow overview and Mermaid diagram mapping internal Yosys nets (`\$1`, `\$2`, ...) back to physical hardware blocks.
  - Walk through the generated `.v` block by block, highlighting newly appearing Verilog constructs (buses, sized literals, `always @(posedge clk)` `<=` vs. `always @*` `=`, latches vs. default holds, reset priority, tool attributes, and Yosys artifacts) and showing a clean human-renamed Verilog equivalent.
  - Include `### Complete <name>.v Listing`, an Amaranth-to-Verilog Rosetta Stone table, an interactive Verilog fill-in-the-blank lab (`:::exercise`), a terminal inspection gate (`:::verify`), and a 3-question retrieval quiz (`:::quiz`).

## Course Build & Verification Rules

- **Test & lint all targets:** Run `pytest` and `ruff check` across affected `apps/*/` directories and `build.py` after every lesson or tooling edit.
- **Verify listings and HTML build:** Run `.agents/skills/teach-code/scripts/sync_listing.py --check` (`### Complete <filename> Listing`) and `build.py --out-dir _site --check`, then remove `_site/` afterward.
- **Quiz & Markdown formatting:**
  - Every `:::quiz` question must have 4 options with identical whitespace-split word counts.
  - In double-quoted YAML strings inside `:::quiz`, escape backslashes (`\\$`) so `\$` reaches Markdown literally, and avoid pairs of unescaped `$` characters inside sidenotes or quiz text (which `INLINE_MATH_RE` treats as KaTeX delimiters).
- **Git hygiene:** Never commit `_site/`, generated root/lesson/reference `*.html` files, or `apps/*/build/`.
