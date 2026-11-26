---
title: "Dissecting Button & Debouncer Verilog"
page_title: "Lesson 0004: Dissecting Button & Debouncer Verilog — Tang Nano 20K"
nav_id: "lesson-0004"
badge: "Lesson 0004 • Verilog Submodules, Sync Chains & Edge Detection"
subtitle: "Dissect the multi-module Verilog Yosys generates for ButtonCounter and ButtonDebouncer—learning named port instantiation, 2-flop sync chains, nested muxes, and bitwise edge detection."
card:
  title: "**Dissecting Button & Debouncer Verilog**"
  summary: "Read multi-module Yosys Verilog line by line: escaped submodule names, .port(wire) wiring, pruned outputs, and nested mux priority."
---

:::callout title="Recommended Primary Sources"
- **Companion app**: `apps/0004-buttons-generated-verilog/` (`.venv/bin/pytest -v apps/0004-buttons-generated-verilog/`)
- **Primary docs**: [Amaranth HDL Documentation](https://amaranth-lang.org/docs/amaranth/latest/) • [Project F: Verilog Primer](https://projectf.io/)
- **Course references**: [Lesson 0003: Buttons, Synchronizers & Debouncing](0003-buttons-and-debouncing.md), [Lesson 0002: Dissecting Generated Verilog](0002-dissecting-generated-verilog.md), [Glossary](../reference/GLOSSARY.md), and [Tang Nano 20K Pinout & Toolchain Sheet](../reference/tang-nano-20k-pinout.md)
:::

## 1. Two Modules in One File: Hierarchy in Generated Verilog {#big-picture}

In [Lesson 0002](0002-dissecting-generated-verilog.md), `blinky.v` was a single flat module of 50 lines. Now that `ButtonCounter` instantiates `ButtonDebouncer` via `m.submodules.debouncer`, `buttons.v` grows to **138 lines containing two separate `module ... endmodule` blocks**.

Everything you learned in Lesson 0002 still applies—`always @(posedge clk)` with `<=`, `always @*` with `=`, carry-preserving adders, and `$auto$` simulation guards. Five **brand-new Verilog patterns** appear here for the first time:

1. **Multi-module hierarchy & escaped hierarchical names:** Only the top chip boundary `button_counter` carries `(* top = 1 *)`. The child module is emitted right below it as `\button_counter.debouncer `.
2. **Named port instantiation (`.port(signal)`):** `button_counter` wires its `clk`, `rst`, `s2`, and `pressed` nets into the `debouncer` instance by port name rather than fragile positional order.
3. **Unused port pruning:** Even though `ButtonDebouncer` declared `level: Out(1)`, `ButtonCounter` never read `debouncer.level`—so Amaranth dropped `level` from the submodule port list and left `wire level;` internal.
4. **Independent `\$N` scopes per module:** Both `button_counter` and `\button_counter.debouncer ` start numbering their temporary nets from `\$1` independently.
5. **Nested `always @*` multiplexers and bitwise edge detection:** `counter` uses a nested `if`/`else` inside `if`/`else`, while `pressed = stable & \$4` (`\$4 = ~ prev_stable`) implements our gate-to-trigger pulse in two continuous `assign` lines.

```mermaid caption="Figure 4.1: Hierarchy and signal flow inside buttons.v — button_counter instantiates \button_counter.debouncer"
flowchart LR
  subgraph TOP["module button_counter (top = 1)"]
    S2["s2 (input)"] --> INST
    INST["debouncer instance (.raw(s2), .pressed(pressed))"] --> MUX2["\$2 (count next-state mux)"]
    CNT["count[5:0] (posedge clk)"] --> ADD1["\$1[6:0] = count + 1"]
    ADD1 -->|"[5:0]"| MUX2
    MUX2 -->|"<= clk"| CNT
    CNT --> INV["assign leds = ~ count"]
    INV --> LEDS["leds[5:0] (output)"]
  end
  subgraph SUB["module \button_counter.debouncer"]
    RAW["raw (input)"] --> SYNC0["sync_0 (posedge clk)"]
    SYNC0 --> SYNC1["sync_1 (posedge clk)"]
    SYNC1 --> CMP1["\$1 = (sync_1 == stable)"]
    DBCNT["counter[18:0]"] --> CMP2["\$2 = (counter == 19'h41eaf)"]
    DBCNT --> ADD3["\$3[19:0] = counter + 1"]
    CMP1 --> MUX7["\$7 (counter next)"]
    CMP2 --> MUX7
    ADD3 -->|"[18:0]"| MUX7
    MUX7 -->|"<= clk"| DBCNT
    CMP1 --> MUX8["\$8 (stable next)"]
    CMP2 --> MUX8
    MUX8 -->|"<= clk"| STB["stable (posedge clk)"]
    STB --> PREV["prev_stable (posedge clk)"]
    PREV --> NOT4["\$4 = ~ prev_stable"]
    STB --> ANDP["assign pressed = stable & \$4"]
    NOT4 --> ANDP
  end
```

## 2. Reading `buttons.v` Block by Block {#block-walkthrough}

### Block 1: Top-Level `button_counter` and Named Port Instantiation

```verilog caption="Lines 3–41 of buttons.v: top-level module, count register, and submodule wiring"
(* top = 1 *)
(* generator = "Amaranth" *)
module button_counter(clk, rst, leds, s2);
  reg \$auto$verilog_backend.cc:2542:dump_module$1  = 0;
  input clk;
  wire clk;
  input rst;
  wire rst;
  output [5:0] leds;
  wire [5:0] leds;
  input s2;
  wire s2;
  wire [6:0] \$1 ;
  reg [5:0] \$2 ;
  reg [5:0] count = 6'h00;
  wire pressed;
  wire raw;
  assign leds = ~ count;
  assign \$1  = count + 1'h1;
  always @(posedge clk)
    count <= \$2 ;
  \button_counter.debouncer  debouncer (
    .clk(clk),
    .pressed(pressed),
    .raw(s2),
    .rst(rst)
  );
  always @* begin
    if (\$auto$verilog_backend.cc:2542:dump_module$1 ) begin end
    \$2  = count;
    if (pressed) begin
      \$2  = \$1 [5:0];
    end
    if (rst) begin
      \$2  = 6'h00;
    end
  end
  assign raw = s2;
endmodule
```

- **Two-part instantiation (`<module_type> <instance_name> (...);`):** Look closely at line 24:
  `\button_counter.debouncer  debouncer (`
  Why are there **two spaces** before `debouncer`? Because `\button_counter.debouncer` contains a dot (`.`), which isn't allowed in ordinary Verilog identifiers—so Yosys makes it an **escaped identifier** starting with `\`. One space terminates the escaped module type name `\button_counter.debouncer`, and the second space separates it from the instance name `debouncer`!
- **Named port mapping (`.port(local_wire)`):** Inside the parentheses (lines 25–28), `.clk(clk)` connects the child's `clk` port to the parent's `clk` wire, `.pressed(pressed)` brings the 1-cycle strobe back out to `wire pressed;`, `.raw(s2)` feeds button `S2` straight in, and `.rst(rst)` shares reset. Named port connections never break if a module reorders its port list!{{sidenote: Line 40 also emits `assign raw = s2;` alongside `.raw(s2)` because Amaranth kept a local alias wire `raw` from `debouncer.raw.eq(self.s2)`. Yosys treats it as a simple zero-gate alias.}}
- **Familiar `count` logic:** Lines 15–23 and 30–39 follow the exact same `blinky.v` recipe you read in Lesson 0002: `\$1` is a 7-bit carry-preserving adder (`count + 1'h1`), `\$2` holds `count` unless `pressed` increments it to `\$1 [5:0]`, and `if (rst)` wins at the bottom.

### Block 2: Submodule `\button_counter.debouncer ` Boundary and Registers

```verilog caption="Lines 43–69 of buttons.v: submodule ports, pruned level wire, and five flip-flops"
(* generator = "Amaranth" *)
module \button_counter.debouncer (clk, rst, pressed, raw);
  reg \$auto$verilog_backend.cc:2542:dump_module$2  = 0;
  input clk;
  wire clk;
  input rst;
  wire rst;
  output pressed;
  wire pressed;
  input raw;
  wire raw;
  wire \$1 ;
  wire \$2 ;
  wire [19:0] \$3 ;
  wire \$4 ;
  reg \$5 ;
  reg \$6 ;
  reg [18:0] \$7 ;
  reg \$8 ;
  reg \$9 ;
  reg [18:0] counter = 19'h00000;
  (* init = 1'h0 *)
  wire level;
  reg prev_stable = 1'h0;
  reg stable = 1'h0;
  reg sync_0 = 1'h0;
  reg sync_1 = 1'h0;
```

- Notice line 43 has `(* generator = "Amaranth" *)` **without** `(* top = 1 *)`, telling downstream synthesis tools this block is an internal child module.
- **Where did `level` go?** Look at line 44: the port list is `(clk, rst, pressed, raw)`—`level` is gone! Because `ButtonCounter` never wired `debouncer.level`, Amaranth pruned `level` from the module boundary and left `(* init = 1'h0 *) wire level;` (lines 64–65, driven by `assign level = stable;` on line 137) as an unused internal net that `yosys` synthesis drops to zero gates.
- **Why does `\$1` restart at `1`?** Each `module ... endmodule` block has its own local namespace: `\$1`–`\$4` are combinational wires, `\$5`–`\$9` are combinational `reg` next-state muxes, and `counter` (`[18:0]`), `prev_stable`, `stable`, `sync_0`, and `sync_1` are our five real flip-flops.

### Block 3: Continuous Comparators, Threshold, and Gate-to-Trigger `assign`s

```verilog caption="Lines 70–84 of buttons.v: continuous combinational logic and five clocked flip-flops"
  assign \$1  = sync_1 == stable;
  assign \$2  = counter == 19'h41eaf;
  assign \$3  = counter + 1'h1;
  assign \$4  = ~ prev_stable;
  assign pressed = stable & \$4 ;
  always @(posedge clk)
    sync_0 <= \$5 ;
  always @(posedge clk)
    sync_1 <= \$6 ;
  always @(posedge clk)
    counter <= \$7 ;
  always @(posedge clk)
    stable <= \$8 ;
  always @(posedge clk)
    prev_stable <= \$9 ;
```

- `\$1` checks whether the synchronized button (`sync_1`) already matches `stable`.
- `\$2` compares `counter` against `19'h41eaf`. In decimal, $0\text{x41EAF} = 269{,}999 = 270{,}000 - 1$—matching our $10\text{ ms}$ debounce window at 27 MHz!
- `\$3` is a **20-bit** (`[19:0]`) carry-preserving adder for the 19-bit `counter`.
- Lines 73–74 implement `self.pressed.eq(stable & ~prev_stable)` using two bitwise primitives: `\$4 = ~ prev_stable` (1-bit inverter) followed by `pressed = stable & \$4` (1-bit AND gate). Both `stable` and `~prev_stable` are `1` simultaneously **only** on the single clock cycle immediately after `stable` rises `0 -> 1`.
- Lines 75–84 snapshot all five flip-flops (`sync_0`, `sync_1`, `counter`, `stable`, `prev_stable`) simultaneously on every rising clock edge via non-blocking `<=`.

### Block 4: Sync Chain Muxes and Nested Debounce Priority Muxes

```verilog caption="Lines 85–138 of buttons.v: synchronizer chains, nested counter/stable muxes, and edge delay"
  always @* begin
    if (\$auto$verilog_backend.cc:2542:dump_module$2 ) begin end
    \$5  = raw;
    if (rst) begin
      \$5  = 1'h0;
    end
  end
  always @* begin
    if (\$auto$verilog_backend.cc:2542:dump_module$2 ) begin end
    \$6  = sync_0;
    if (rst) begin
      \$6  = 1'h0;
    end
  end
  always @* begin
    if (\$auto$verilog_backend.cc:2542:dump_module$2 ) begin end
    (* full_case = 1 *)
    if (\$1 ) begin
      \$7  = 19'h00000;
    end else begin
      (* full_case = 1 *)
      if (\$2 ) begin
        \$7  = 19'h00000;
      end else begin
        \$7  = \$3 [18:0];
      end
    end
    if (rst) begin
      \$7  = 19'h00000;
    end
  end
  always @* begin
    if (\$auto$verilog_backend.cc:2542:dump_module$2 ) begin end
    \$8  = stable;
    (* full_case = 1 *)
    if (\$1 ) begin
    end else begin
      if (\$2 ) begin
        \$8  = sync_1;
      end
    end
    if (rst) begin
      \$8  = 1'h0;
    end
  end
  always @* begin
    if (\$auto$verilog_backend.cc:2542:dump_module$2 ) begin end
    \$9  = stable;
    if (rst) begin
      \$9  = 1'h0;
    end
  end
  assign level = stable;
endmodule
```

- **Why are `\$5` (`sync_0`), `\$6` (`sync_1`), and `\$9` (`prev_stable`) wrapped in `always @*`?** Even a simple `sync_0.eq(self.raw)` needs synchronous reset priority (`if (rst) \$5 = 1'h0;`), so Yosys emits a small 2-input mux for each flip-flop.
- **Nested `if`/`else` in `\$7` (`counter_next`):** Trace the three priority branches top-to-bottom:
  1. If `\$1` (`sync_1 == stable`): reset `\$7 = 19'h00000`.
  2. Else if `\$2` (`counter == 19'h41eaf`): reset `\$7 = 19'h00000`.
  3. Else: advance `\$7 = \$3 [18:0]` (lower 19 bits of `counter + 1`).
  4. Bottom override: `if (rst) \$7 = 19'h00000;` beats all three.
- **Why does `if (\$1 ) begin end` have an empty body in `\$8` (`stable_next`)?** Because line 118 already set the latch-preventing default `\$8 = stable;`. When `sync_1 == stable` (`\$1`), keeping `\$8` at `stable` requires no extra assignment, so Yosys leaves the `if` branch empty and only overrides `\$8 = sync_1` inside `else -> if (\$2 )` (and `1'h0` on `rst`).{{sidenote: Seeing an empty `if (...) begin end` in generated Verilog looks bizarre until you recognise the pattern: the default assignment right above the `if` already handled that case!}}

### Block 5: Clean Human-Written Equivalent

Stripping away Yosys's temporary `\$N` wires and `$auto$` guards leaves a crystal-clear pair of human-readable Verilog modules:

```verilog caption="Conceptual hand-written Verilog equivalent of buttons.v"
module button_debouncer(input clk, input rst, input raw, output pressed);
  reg sync_0 = 1'b0, sync_1 = 1'b0;
  reg stable = 1'b0, prev_stable = 1'b0;
  reg [18:0] counter = 19'd0;

  always @(posedge clk) begin
    if (rst) begin
      sync_0 <= 1'b0;
      sync_1 <= 1'b0;
      stable <= 1'b0;
      prev_stable <= 1'b0;
      counter <= 19'd0;
    end else begin
      sync_0 <= raw;
      sync_1 <= sync_0;
      prev_stable <= stable;

      if (sync_1 == stable) begin
        counter <= 19'd0;
      end else if (counter == 19'd269999) begin
        stable <= sync_1;
        counter <= 19'd0;
      end else begin
        counter <= counter + 19'd1;
      end
    end
  end

  assign pressed = stable & ~prev_stable;
endmodule

module button_counter(input clk, input rst, input s2, output [5:0] leds);
  wire pressed;
  reg [5:0] count = 6'd0;

  button_debouncer debouncer(
    .clk(clk),
    .rst(rst),
    .raw(s2),
    .pressed(pressed)
  );

  always @(posedge clk) begin
    if (rst)
      count <= 6'd0;
    else if (pressed)
      count <= count + 6'd1;
  end

  assign leds = ~count;
endmodule
```

## 3. Complete `buttons.v` Listing & Rosetta Stone {#complete-listing}

### Complete buttons.v Listing

```verilog caption="apps/0004-buttons-generated-verilog/buttons.v"
/* Generated by Yosys 0.71 (git sha1 b4c586fd3, Release, Clang /home/runner/work/amaranth-yosys/amaranth-yosys/wasi-sdk-34.0-x86_64-linux/bin/clang++ 23.1.0) */

(* top = 1 *)
(* generator = "Amaranth" *)
module button_counter(clk, rst, leds, s2);
  reg \$auto$verilog_backend.cc:2542:dump_module$1  = 0;
  input clk;
  wire clk;
  input rst;
  wire rst;
  output [5:0] leds;
  wire [5:0] leds;
  input s2;
  wire s2;
  wire [6:0] \$1 ;
  reg [5:0] \$2 ;
  reg [5:0] count = 6'h00;
  wire pressed;
  wire raw;
  assign leds = ~ count;
  assign \$1  = count + 1'h1;
  always @(posedge clk)
    count <= \$2 ;
  \button_counter.debouncer  debouncer (
    .clk(clk),
    .pressed(pressed),
    .raw(s2),
    .rst(rst)
  );
  always @* begin
    if (\$auto$verilog_backend.cc:2542:dump_module$1 ) begin end
    \$2  = count;
    if (pressed) begin
      \$2  = \$1 [5:0];
    end
    if (rst) begin
      \$2  = 6'h00;
    end
  end
  assign raw = s2;
endmodule

(* generator = "Amaranth" *)
module \button_counter.debouncer (clk, rst, pressed, raw);
  reg \$auto$verilog_backend.cc:2542:dump_module$2  = 0;
  input clk;
  wire clk;
  input rst;
  wire rst;
  output pressed;
  wire pressed;
  input raw;
  wire raw;
  wire \$1 ;
  wire \$2 ;
  wire [19:0] \$3 ;
  wire \$4 ;
  reg \$5 ;
  reg \$6 ;
  reg [18:0] \$7 ;
  reg \$8 ;
  reg \$9 ;
  reg [18:0] counter = 19'h00000;
  (* init = 1'h0 *)
  wire level;
  reg prev_stable = 1'h0;
  reg stable = 1'h0;
  reg sync_0 = 1'h0;
  reg sync_1 = 1'h0;
  assign \$1  = sync_1 == stable;
  assign \$2  = counter == 19'h41eaf;
  assign \$3  = counter + 1'h1;
  assign \$4  = ~ prev_stable;
  assign pressed = stable & \$4 ;
  always @(posedge clk)
    sync_0 <= \$5 ;
  always @(posedge clk)
    sync_1 <= \$6 ;
  always @(posedge clk)
    counter <= \$7 ;
  always @(posedge clk)
    stable <= \$8 ;
  always @(posedge clk)
    prev_stable <= \$9 ;
  always @* begin
    if (\$auto$verilog_backend.cc:2542:dump_module$2 ) begin end
    \$5  = raw;
    if (rst) begin
      \$5  = 1'h0;
    end
  end
  always @* begin
    if (\$auto$verilog_backend.cc:2542:dump_module$2 ) begin end
    \$6  = sync_0;
    if (rst) begin
      \$6  = 1'h0;
    end
  end
  always @* begin
    if (\$auto$verilog_backend.cc:2542:dump_module$2 ) begin end
    (* full_case = 1 *)
    if (\$1 ) begin
      \$7  = 19'h00000;
    end else begin
      (* full_case = 1 *)
      if (\$2 ) begin
        \$7  = 19'h00000;
      end else begin
        \$7  = \$3 [18:0];
      end
    end
    if (rst) begin
      \$7  = 19'h00000;
    end
  end
  always @* begin
    if (\$auto$verilog_backend.cc:2542:dump_module$2 ) begin end
    \$8  = stable;
    (* full_case = 1 *)
    if (\$1 ) begin
    end else begin
      if (\$2 ) begin
        \$8  = sync_1;
      end
    end
    if (rst) begin
      \$8  = 1'h0;
    end
  end
  always @* begin
    if (\$auto$verilog_backend.cc:2542:dump_module$2 ) begin end
    \$9  = stable;
    if (rst) begin
      \$9  = 1'h0;
    end
  end
  assign level = stable;
endmodule
```

Table: Amaranth-to-Verilog Rosetta Stone for `ButtonCounter` and `ButtonDebouncer`.

| Amaranth Construct | Exact `buttons.v` Line(s) | Hardware Meaning |
| :--- | :--- | :--- |
| `m.submodules.debouncer = ...` | `\button_counter.debouncer  debouncer ( .clk(clk), ... );` | Hierarchical child module wired by named port connections |
| `s2: In(1)` | `input s2; wire s2;` | Single-bit physical input pin into top module |
| Unused `level: Out(1)` | Pruned from ports; internal `wire level;` | Unconnected submodule outputs stripped from port boundary |
| `sync_0.eq(self.raw); sync_1.eq(sync_0)` | `sync_0 <= \$5 ;` & `sync_1 <= \$6 ;` | 2-stage metastability synchronizer shift chain |
| `Signal(range(270_000))` | `reg [18:0] counter = 19'h00000;` & `19'h41eaf` | 19-bit debounce counter comparing against `269_999` (`0x41EAF`) |
| Nested `with m.If` / `with m.Else` | Nested `if (\$1 ) ... else if (\$2 ) ...` | Priority next-state mux with `if (rst)` overriding last |
| `stable & ~prev_stable` | `assign \$4 = ~ prev_stable;` & `assign pressed = stable & \$4 ;` | Combinational 1-cycle rising-edge trigger pulse |

:::exercise id="ex-0004" title="Interactive Lab: Named Ports, 2-Flop Sync & Rising-Edge Verilog" badge="Skill Practice • Tight Feedback Loop"
Complete the human-readable Verilog snippet below to connect `s2` by named port, advance the 2-flop synchronizer with non-blocking updates, and build the 1-cycle rising-edge pulse:

```verilog
button_debouncer debouncer (
  .clk(clk),
  .rst(rst),
  .{{blank:raw|Name of the debouncer input port?|???|3}}(s2),
  .{{blank:pressed|Name of the 1-cycle strobe output port?|???????|7}}(pressed)
);

always @(posedge clk) begin
  sync_0 {{blank:<=|Non-blocking assignment for clocked registers?|??|2}} raw;
  sync_1 <= sync_0;
  prev_stable <= stable;
end

assign pressed = stable {{blank:&|Verilog bitwise AND operator?|?|1}} {{blank:~|Verilog bitwise NOT operator?|?|1}}prev_stable;
```

:::prompts
hint: "Use `.raw(s2)` and `.pressed(pressed)` for named port connections, `<=` for clocked flip-flops, `&` for bitwise AND, and `~` for bitwise NOT."
success: "Verified! You can now read and write named Verilog port connections, non-blocking sync chains, and bitwise rising-edge detectors."
:::
:::

:::verify id="verify-0004" title="Verification Lab: Verify Exact Parity & Watch Widths Shrink" badge="Terminal Gate"
Run the Lesson 0004 verification suite and linter, then run `--debounce-cycles 4` to watch the 19-bit debounce counter shrink automatically to 2 bits:

```bash
.venv/bin/pytest -v apps/0004-buttons-generated-verilog/
.venv/bin/ruff check apps/0004-buttons-generated-verilog/
.venv/bin/python apps/0004-buttons-generated-verilog/buttons.py --verilog --debounce-cycles 4
```

Notice in the `--debounce-cycles 4` output: `reg [18:0] counter = 19'h00000;` shrinks to `reg [1:0] counter = 2'h0;`, `wire [19:0] \$3 ;` shrinks to `wire [2:0] \$3 ;`, and `19'h41eaf` shrinks to `2'h3`.

- [ ] All 6 tests in `test_buttons_verilog.py` pass (`buttons.v == emit_verilog()`, named port wiring, `19'h41eaf`, edge detection, and `--debounce-cycles 4` shrinking).
- [ ] `ruff check` reports `All checks passed!`.
- [ ] `--debounce-cycles 4` keeps both `module button_counter` and `module \button_counter.debouncer ` intact with 2-bit counter registers.
:::

:::quiz id="quiz-0004" title="Retrieval Practice: Reading Multi-Module Yosys Verilog" badge="3 Questions • Equal-Length Options"
- question: "In `buttons.v`, why is `\\button_counter.debouncer  debouncer (` written with a leading backslash and two spaces before `debouncer (`?"
  wrong_hint: "Recall Verilog's escaped identifier rule from Lesson 0002."
  options:
    - letter: "A"
      text: "Verilator requires two spaces before any module name with periods"
      correct: false
      explain: "This rule is standard Verilog-2001 syntax emitted by Yosys, not a Verilator-specific spacing quirk."
    - letter: "B"
      text: "Amaranth outputs two copies of every submodule for timing redundancy"
      correct: false
      explain: "There is only one instance named `debouncer` of type `\\button_counter.debouncer `."
    - letter: "C"
      text: "Escaped identifiers containing dots end at whitespace before instance names"
      correct: true
      explain: "Because `button_counter.debouncer` contains a dot, `\\` starts an escaped identifier that must end with whitespace before the instance name `debouncer`."
    - letter: "D"
      text: "Yosys uses backslashes to mark modules running at half clock"
      correct: false
      explain: "Both `button_counter` and `\\button_counter.debouncer ` run on the exact same 27 MHz `clk`."
- question: "Why does `level` appear inside `\\button_counter.debouncer ` as an internal `wire level;` rather than in the module port list `(...)`?"
  wrong_hint: "Check which outputs of `debouncer` are actually read inside `ButtonCounter.elaborate()`."
  options:
    - letter: "A"
      text: "Verilog submodules cannot have more than one output port declared"
      correct: false
      explain: "Verilog modules can declare any number of `output` ports; `level` was dropped only because nothing connected to it."
    - letter: "B"
      text: "Unused submodule outputs are pruned from ports by Amaranth lowering"
      correct: true
      explain: "`ButtonCounter` only read `debouncer.pressed`, so Amaranth omitted `level` from the module boundary while keeping `assign level = stable;` internal."
    - letter: "C"
      text: "Active-low LED pins automatically merge `level` and `pressed` into `leds`"
      correct: false
      explain: "`leds` is driven only by `~count`, and `count` only reads `pressed`."
    - letter: "D"
      text: "Yosys moves `level` into `button_counter` and deletes the `stable` register"
      correct: false
      explain: "`reg stable = 1'h0;` remains inside `\\button_counter.debouncer ` and drives both `level` and `pressed`."
- question: "Inside `\\button_counter.debouncer `, how do lines 73–74 (`assign \\$4  = ~ prev_stable;` and `assign pressed = stable & \\$4 ;`) guarantee `pressed` stays high for only one clock cycle?"
  wrong_hint: "Trace `stable` and `prev_stable` on the cycle `stable` flips `0 -> 1` and the very next cycle."
  options:
    - letter: "A"
      text: "Both `stable` and `~prev_stable` are `1` only immediately after rising"
      correct: true
      explain: "`prev_stable` lags `stable` by one clock edge, so `stable & ~prev_stable` is `1` only on the first cycle after `stable` becomes `1`."
    - letter: "B"
      text: "The `counter` register resets `pressed` to zero after four ticks"
      correct: false
      explain: "`counter` only gates changes to `stable`; `pressed` drops back to `0` after one tick because `prev_stable <= stable` catches up."
    - letter: "C"
      text: "Bitwise AND runs on falling clock edges before `sync_0` samples"
      correct: false
      explain: "`assign` statements are continuous combinational gates, and all registers here clock on `posedge clk`."
    - letter: "D"
      text: "Button `S1` pulses `rst` low for one cycle every press"
      correct: false
      explain: "Active-high `rst` on `S1` resets the entire circuit only when the user presses `S1`."
:::

:::teacher-prompt title="Extend This Lesson with Your Agent"
You can now read multi-module Amaranth-generated Verilog confidently! Ready for **Lesson 0005** (PWM LED brightness & Finite State Machines) or want to dig deeper? Ask your AI teacher:
- *"What would change in `buttons.v` if `ButtonCounter` also wired `debouncer.level` to `leds[5]`?"*
- *"I understand Lesson 0004 — let's build Lesson 0005 with PWM brightness control and an Amaranth state machine!"*
:::
