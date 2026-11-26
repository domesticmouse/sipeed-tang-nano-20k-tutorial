---
title: "Dissecting PWM & FSM Verilog"
page_title: "Lesson 0006: Dissecting PWM & FSM Verilog — Tang Nano 20K"
nav_id: "lesson-0006"
badge: "Lesson 0006 • FSM casez, Comparators & Concatenation"
subtitle: "Dissect the 221-line Yosys Verilog generated for PwmBreather and PwmGenerator—learning FSM binary state encoding, casez blocks, MSB-first bit concatenation, logical !, and unsigned comparators."
card:
  title: "**Dissecting PWM & FSM Verilog**"
  summary: "Trace how Amaranth's m.FSM lowers into casez decoders, how Cat() reverses into { ... }, and how counter < duty synthesizes."
---

:::callout title="Recommended Primary Sources"
- **Companion app**: `apps/0006-pwm-fsm-generated-verilog/` (`.venv/bin/pytest -v apps/0006-pwm-fsm-generated-verilog/`)
- **Primary docs**: [Amaranth HDL Documentation](https://amaranth-lang.org/docs/amaranth/latest/) • [Project F: Verilog Primer](https://projectf.io/)
- **Course references**: [Lesson 0005: PWM Brightness & Finite State Machines](0005-pwm-and-state-machines.md), [Lesson 0004: Dissecting Button & Debouncer Verilog](0004-buttons-generated-verilog.md), [Glossary](../reference/GLOSSARY.md), and [Tang Nano 20K Pinout & Toolchain Sheet](../reference/tang-nano-20k-pinout.md)
:::

## 1. How Amaranth Lowers `m.FSM`, `Cat()`, and PWM Comparators {#big-picture}

In [Lesson 0005](0005-pwm-and-state-machines.md), we authored `PwmBreather` and `PwmGenerator` in 94 lines of Python. Converting that design with `emit_verilog()` produces **221 lines** of multi-module Verilog inside `pwm_breather.v` (`module pwm_breather` plus `module \pwm_breather.pwm `).

Five **brand-new Verilog constructs** appear here for the first time:

1. **FSM binary state register & per-signal `casez (fsm_state)` blocks:** Amaranth encodes `"RAMP_UP"`..`"HOLD_LOW"` into a 2-bit register `reg [1:0] fsm_state = 2'h0;` (`2'h0`..`2'h3`) and fans out a separate `always @*` `casez` mux for each signal the FSM drives (`state_leds`, `hold_count`, `fsm_state`, and `duty`).
2. **MSB-first concatenation (`{ state_leds, out, out }`):** Amaranth's LSB-first `Cat(pwm.out, pwm.out, state_leds)` flips order inside Verilog's MSB-first brace concatenation `{ ... }`.
3. **Unsigned magnitude comparator (`counter < duty`):** Inside `\pwm_breather.pwm `, the entire PWM duty comparator lowers to one clean `assign out = counter < duty;` line.
4. **Logical NOT (`! duty`) & carry-preserving subtraction (`duty - 1'h1`):** Yosys lowers `brightness == 0` into logical `! duty` (distinct from bitwise `~`) and emits a 9-bit `[8:0]` subtraction sliced back down to `[7:0]`.
5. **Amaranth `fsm.ongoing` helper nets (`\$1`–`\$4`) & empty `casez` arms (`/* empty */;`):** Yosys emits four state-decode wires and leaves unchanged `casez` branches empty or omitted because a latch-preventing default sits right above `casez`.

```mermaid caption="Figure 6.1: Signal flow inside pwm_breather.v — 2-bit fsm_state fans out to four casez muxes while duty drives \pwm_breather.pwm"
flowchart LR
  subgraph TOP["module pwm_breather (top = 1)"]
    TMR["step_timer[16:0]"] -->|"== 17'h19bfc"| TICK["step_tick"]
    FSM["fsm_state[1:0] (posedge clk)"] --> LEDMUX["casez -> state_leds[3:0]"]
    FSM --> STNMUX["casez -> \$16 (fsm_state next)"]
    TICK --> STNMUX
    FSM --> HLNMUX["casez -> \$15 (hold_count next)"]
    FSM --> DTNMUX["casez -> \$17 (duty next)"]
    DTNMUX -->|"<= clk"| DUTY["duty[7:0]"]
    DUTY --> INST["pwm instance (.duty(duty), .out(out))"]
    LEDMUX --> PACK["assign leds = ~ { state_leds, out, out }"]
    INST -->|"out"| PACK
    PACK --> LEDS["leds[5:0] (output)"]
  end
  subgraph SUB["module \pwm_breather.pwm"]
    PWMIN["duty[7:0] (input)"] --> CMP["assign out = counter < duty"]
    PWMCNT["counter[7:0] (posedge clk)"] --> CMP
    PWMCNT --> ADD["\$1[8:0] = counter + 1'h1"]
    ADD -->|"[7:0]"| PWMCNT
    CMP --> PWMOUT["out (output)"]
  end
```

## 2. Reading `pwm_breather.v` Block by Block {#block-walkthrough}

### Block 1: Boundary, Concatenation, Logical `!`, and Continuous Expressions

```verilog caption="Lines 3–53 of pwm_breather.v: module ports, registers, concatenation, and combinational expressions"
(* top = 1 *)
(* generator = "Amaranth" *)
module pwm_breather(rst, leds, clk);
  reg \$auto$verilog_backend.cc:2542:dump_module$1  = 0;
  input rst;
  wire rst;
  output [5:0] leds;
  wire [5:0] leds;
  input clk;
  wire clk;
  wire \$1 ;
  wire \$10 ;
  wire [8:0] \$11 ;
  wire \$12 ;
  wire [6:0] \$13 ;
  reg [16:0] \$14 ;
  reg [5:0] \$15 ;
  reg [1:0] \$16 ;
  reg [7:0] \$17 ;
  wire \$2 ;
  wire \$3 ;
  wire \$4 ;
  wire [17:0] \$5 ;
  wire \$6 ;
  wire [8:0] \$7 ;
  wire \$8 ;
  wire [6:0] \$9 ;
  (* init = 8'h00 *)
  wire [7:0] brightness;
  reg [7:0] duty = 8'h00;
  reg [1:0] fsm_state = 2'h0;
  reg [5:0] hold_count = 6'h00;
  wire out;
  reg [3:0] state_leds;
  wire step_tick;
  reg [16:0] step_timer = 17'h00000;
  assign step_tick = step_timer == 17'h19bfc;
  assign leds = ~ { state_leds, out, out };
  assign \$1  = ! fsm_state;
  assign \$2  = fsm_state == 1'h1;
  assign \$3  = fsm_state == 2'h2;
  assign \$4  = fsm_state == 2'h3;
  assign \$5  = step_timer + 1'h1;
  assign \$6  = duty == 8'hff;
  assign \$7  = duty + 1'h1;
  assign \$8  = hold_count == 6'h3f;
  assign \$9  = hold_count + 1'h1;
  assign \$10  = ! duty;
  assign \$11  = duty - 1'h1;
  assign \$12  = hold_count == 6'h3f;
  assign \$13  = hold_count + 1'h1;
```

- **Why did `Cat(pwm.out, pwm.out, state_leds)` become `{ state_leds, out, out }` (line 40)?** Verilog brace concatenation `{ msb, ..., lsb }` writes the **most-significant bits on the left** and the **least-significant bits on the right**—matching normal binary numbers. Because `state_leds` occupies bits `[5:2]` and the two `out` copies sit at `[1]` and `[0]`, Verilog writes `{ state_leds, out, out }`, then `~` inverts all 6 bits for our active-low LEDs.
- **Logical `!` vs. bitwise `~` (lines 41 and 50):** Compare `assign leds = ~ { ... };` against `assign \$10 = ! duty;` (and `assign \$1 = ! fsm_state;`).
  - Bitwise `~` flips every bit individually (`~ 4'b0001 == 4'b1110`).
  - Logical `!` tests whether **every bit is zero**, returning a 1-bit boolean `1'b1` when `duty == 8'h00` and `1'b0` otherwise. Yosys turns `brightness == 0` into `! duty`!
- **Carry/borrow-preserving arithmetic (lines 46–47 and 51):** Both `\$7` (`duty + 1'h1`) and `\$11` (`duty - 1'h1`) are declared `[8:0]` (9 bits wide for an 8-bit `duty`) so overflow/underflow bits never truncate prematurely before the `[7:0]` slice inside `always @*`.
- **Where did `brightness` go?** Notice line 32 declares `reg [7:0] duty = 8'h00;`, while line 31 (`wire [7:0] brightness;`) connects to `assign brightness = duty;` down on line 193. Because `pwm.duty.eq(brightness)` aliased `brightness` directly to the submodule input `duty`, Yosys merged the register under the name `duty`!{{sidenote: Look at lines 41–44 (`\$1`–`\$4`): Amaranth's `m.FSM` generates one internal `ongoing` boolean wire per state (`! fsm_state`, `== 1'h1`, `== 2'h2`, `== 2'h3`). Even when nothing reads them downstream, Yosys synthesis prunes unused wires cleanly.}}

### Block 2: Clocked Registers and `pwm` Submodule Instantiation

```verilog caption="Lines 54–67 of pwm_breather.v: four clocked registers and \pwm_breather.pwm instantiation"
  always @(posedge clk)
    step_timer <= \$14 ;
  always @(posedge clk)
    hold_count <= \$15 ;
  always @(posedge clk)
    fsm_state <= \$16 ;
  always @(posedge clk)
    duty <= \$17 ;
  \pwm_breather.pwm  pwm (
    .clk(clk),
    .duty(duty),
    .out(out),
    .rst(rst)
  );
```

- Four flip-flop banks update on every `posedge clk`: `step_timer` (`17` bits), `hold_count` (`6` bits), `fsm_state` (`2` bits), and `duty` (`8` bits).
- `\pwm_breather.pwm  pwm (...)` wires the 8-bit `duty` bus straight into the child PWM comparator and brings back the 1-bit `out` pulse stream via named ports.

### Block 3: Moore Output `casez` (`state_leds`) and State Transitions (`\$16`)

```verilog caption="Lines 68–81 and 132–165 of pwm_breather.v: Moore state_leds decoder and next-state fsm_state casez"
  always @* begin
    if (\$auto$verilog_backend.cc:2542:dump_module$1 ) begin end
    (* full_case = 1 *)
    casez (fsm_state)
      2'h0:
          state_leds = 4'h1;
      2'h1:
          state_leds = 4'h2;
      2'h2:
          state_leds = 4'h4;
      2'h3:
          state_leds = 4'h8;
    endcase
  end
```

```verilog caption="Lines 132–165 of pwm_breather.v: next-state transition table for fsm_state (\$16)"
  always @* begin
    if (\$auto$verilog_backend.cc:2542:dump_module$1 ) begin end
    \$16  = fsm_state;
    (* full_case = 1 *)
    casez (fsm_state)
      2'h0:
          if (step_tick) begin
            if (\$6 ) begin
              \$16  = 2'h1;
            end
          end
      2'h1:
          if (step_tick) begin
            if (\$8 ) begin
              \$16  = 2'h2;
            end
          end
      2'h2:
          if (step_tick) begin
            if (\$10 ) begin
              \$16  = 2'h3;
            end
          end
      2'h3:
          if (step_tick) begin
            if (\$12 ) begin
              \$16  = 2'h0;
            end
          end
    endcase
    if (rst) begin
      \$16  = 2'h0;
    end
  end
```

- **Why `casez` instead of `case`?** Verilog's `casez` treats `?` or `z` bits as wildcards (used heavily for instruction decoding). Even when all patterns are exact 2-bit literals (`2'h0`..`2'h3`), Yosys consistently emits `casez` for Amaranth FSMs, tagged with `(* full_case = 1 *)` so the synthesizer knows all 4 combinations (`00`, `01`, `10`, `11`) are covered with no latch.
- **State encoding table:** `2'h0` = `RAMP_UP` (`state_leds = 4'h1`), `2'h1` = `HOLD_HIGH` (`4'h2`), `2'h2` = `RAMP_DOWN` (`4'h4`), and `2'h3` = `HOLD_LOW` (`4'h8`).
- **Default hold + `rst` priority:** Line 134 (`\$16 = fsm_state;`) holds the current state on every non-transition cycle, while `if (rst) \$16 = 2'h0;` at lines 162–164 guarantees pressing `S1` always forces `fsm_state` back to `RAMP_UP`.

### Block 4: Per-Register `casez` Muxes, `/* empty */;`, and Omitted Arms

```verilog caption="Lines 166–192 of pwm_breather.v: duty next-state mux (\$17) showing an empty arm and an omitted arm"
  always @* begin
    if (\$auto$verilog_backend.cc:2542:dump_module$1 ) begin end
    \$17  = duty;
    casez (fsm_state)
      2'h0:
          if (step_tick) begin
            (* full_case = 1 *)
            if (\$6 ) begin
            end else begin
              \$17  = \$7 [7:0];
            end
          end
      2'h1:
          /* empty */;
      2'h2:
          if (step_tick) begin
            (* full_case = 1 *)
            if (\$10 ) begin
            end else begin
              \$17  = \$11 [7:0];
            end
          end
    endcase
    if (rst) begin
      \$17  = 8'h00;
    end
  end
```

- Look closely at why `2'h1` (`HOLD_HIGH`) says `/* empty */;` and `2'h3` (`HOLD_LOW`) is completely absent!
  - Line 168 sets `\$17 = duty;` **before** `casez (fsm_state)` runs.
  - Because neither `HOLD_HIGH` nor `HOLD_LOW` modifies `brightness`, falling through the `casez` leaves `\$17` equal to `duty`—no latch, and no extra mux gates!
  - Likewise, in `2'h0` (`RAMP_UP`), when `\$6` (`duty == 8'hff`) is true, `duty` stays pinned at `8'hff`, so the `if (\$6 )` branch is empty and only the `else` branch computes `\$7 [7:0]` (`duty + 1`).

### Block 5: Inside `\pwm_breather.pwm ` (`counter < duty`)

```verilog caption="Lines 196–221 of pwm_breather.v: complete PWM comparator submodule"
(* generator = "Amaranth" *)
module \pwm_breather.pwm (rst, out, duty, clk);
  reg \$auto$verilog_backend.cc:2542:dump_module$2  = 0;
  input rst;
  wire rst;
  output out;
  wire out;
  input [7:0] duty;
  wire [7:0] duty;
  input clk;
  wire clk;
  wire [8:0] \$1 ;
  reg [7:0] \$2 ;
  reg [7:0] counter = 8'h00;
  assign \$1  = counter + 1'h1;
  assign out = counter < duty;
  always @(posedge clk)
    counter <= \$2 ;
  always @* begin
    if (\$auto$verilog_backend.cc:2542:dump_module$2 ) begin end
    \$2  = \$1 [7:0];
    if (rst) begin
      \$2  = 8'h00;
    end
  end
endmodule
```

- Just 25 lines total! `counter` increments unconditionally every cycle (`\$2 = \$1 [7:0];`), wrapping `8'hff -> 8'h00` automatically unless `rst` forces `8'h00`.
- `assign out = counter < duty;` compares two 8-bit unsigned signals continuously—no clock delay inside the comparator itself.

### Block 6: Clean Human-Written Equivalent

When humans write an FSM in Verilog, they define named constants with `localparam` and group state transitions and register updates into one readable `always @(posedge clk)` block:

```verilog caption="Conceptual hand-written Verilog equivalent of pwm_breather.v"
module pwm_generator #(parameter WIDTH = 8) (
  input clk,
  input rst,
  input [WIDTH-1:0] duty,
  output out
);
  reg [WIDTH-1:0] counter = {WIDTH{1'b0}};

  always @(posedge clk) begin
    if (rst)
      counter <= {WIDTH{1'b0}};
    else
      counter <= counter + {{(WIDTH-1){1'b0}}, 1'b1};
  end

  assign out = counter < duty;
endmodule

module pwm_breather(input clk, input rst, output [5:0] leds);
  localparam [1:0]
    RAMP_UP   = 2'd0,
    HOLD_HIGH = 2'd1,
    RAMP_DOWN = 2'd2,
    HOLD_LOW  = 2'd3;

  reg [1:0] state = RAMP_UP;
  reg [7:0] duty = 8'd0;
  reg [16:0] step_timer = 17'd0;
  reg [5:0] hold_count = 6'd0;
  reg [3:0] state_leds;
  wire pwm_out;

  wire step_tick = (step_timer == 17'd105468);

  pwm_generator #(.WIDTH(8)) pwm (
    .clk(clk), .rst(rst), .duty(duty), .out(pwm_out)
  );

  always @* begin
    case (state)
      RAMP_UP:   state_leds = 4'b0001;
      HOLD_HIGH: state_leds = 4'b0010;
      RAMP_DOWN: state_leds = 4'b0100;
      HOLD_LOW:  state_leds = 4'b1000;
    endcase
  end

  always @(posedge clk) begin
    if (rst) begin
      state <= RAMP_UP;
      duty <= 8'd0;
      step_timer <= 17'd0;
      hold_count <= 6'd0;
    end else begin
      step_timer <= step_tick ? 17'd0 : step_timer + 17'd1;
      if (step_tick) begin
        case (state)
          RAMP_UP:   if (duty == 8'd255) begin hold_count <= 6'd0; state <= HOLD_HIGH; end else duty <= duty + 8'd1;
          HOLD_HIGH: if (hold_count == 6'd63) state <= RAMP_DOWN; else hold_count <= hold_count + 6'd1;
          RAMP_DOWN: if (duty == 8'd0) begin hold_count <= 6'd0; state <= HOLD_LOW; end else duty <= duty - 8'd1;
          HOLD_LOW:  if (hold_count == 6'd63) state <= RAMP_UP; else hold_count <= hold_count + 6'd1;
        endcase
      end
    end
  end

  assign leds = ~{state_leds, pwm_out, pwm_out};
endmodule
```

## 3. Complete `pwm_breather.v` Listing & Rosetta Stone {#complete-listing}

### Complete pwm_breather.v Listing

```verilog caption="apps/0006-pwm-fsm-generated-verilog/pwm_breather.v"
/* Generated by Yosys 0.71 (git sha1 b4c586fd3, Release, Clang /home/runner/work/amaranth-yosys/amaranth-yosys/wasi-sdk-34.0-x86_64-linux/bin/clang++ 23.1.0) */

(* top = 1 *)
(* generator = "Amaranth" *)
module pwm_breather(rst, leds, clk);
  reg \$auto$verilog_backend.cc:2542:dump_module$1  = 0;
  input rst;
  wire rst;
  output [5:0] leds;
  wire [5:0] leds;
  input clk;
  wire clk;
  wire \$1 ;
  wire \$10 ;
  wire [8:0] \$11 ;
  wire \$12 ;
  wire [6:0] \$13 ;
  reg [16:0] \$14 ;
  reg [5:0] \$15 ;
  reg [1:0] \$16 ;
  reg [7:0] \$17 ;
  wire \$2 ;
  wire \$3 ;
  wire \$4 ;
  wire [17:0] \$5 ;
  wire \$6 ;
  wire [8:0] \$7 ;
  wire \$8 ;
  wire [6:0] \$9 ;
  (* init = 8'h00 *)
  wire [7:0] brightness;
  reg [7:0] duty = 8'h00;
  reg [1:0] fsm_state = 2'h0;
  reg [5:0] hold_count = 6'h00;
  wire out;
  reg [3:0] state_leds;
  wire step_tick;
  reg [16:0] step_timer = 17'h00000;
  assign step_tick = step_timer == 17'h19bfc;
  assign leds = ~ { state_leds, out, out };
  assign \$1  = ! fsm_state;
  assign \$2  = fsm_state == 1'h1;
  assign \$3  = fsm_state == 2'h2;
  assign \$4  = fsm_state == 2'h3;
  assign \$5  = step_timer + 1'h1;
  assign \$6  = duty == 8'hff;
  assign \$7  = duty + 1'h1;
  assign \$8  = hold_count == 6'h3f;
  assign \$9  = hold_count + 1'h1;
  assign \$10  = ! duty;
  assign \$11  = duty - 1'h1;
  assign \$12  = hold_count == 6'h3f;
  assign \$13  = hold_count + 1'h1;
  always @(posedge clk)
    step_timer <= \$14 ;
  always @(posedge clk)
    hold_count <= \$15 ;
  always @(posedge clk)
    fsm_state <= \$16 ;
  always @(posedge clk)
    duty <= \$17 ;
  \pwm_breather.pwm  pwm (
    .clk(clk),
    .duty(duty),
    .out(out),
    .rst(rst)
  );
  always @* begin
    if (\$auto$verilog_backend.cc:2542:dump_module$1 ) begin end
    (* full_case = 1 *)
    casez (fsm_state)
      2'h0:
          state_leds = 4'h1;
      2'h1:
          state_leds = 4'h2;
      2'h2:
          state_leds = 4'h4;
      2'h3:
          state_leds = 4'h8;
    endcase
  end
  always @* begin
    if (\$auto$verilog_backend.cc:2542:dump_module$1 ) begin end
    (* full_case = 1 *)
    if (step_tick) begin
      \$14  = 17'h00000;
    end else begin
      \$14  = \$5 [16:0];
    end
    if (rst) begin
      \$14  = 17'h00000;
    end
  end
  always @* begin
    if (\$auto$verilog_backend.cc:2542:dump_module$1 ) begin end
    \$15  = hold_count;
    (* full_case = 1 *)
    casez (fsm_state)
      2'h0:
          if (step_tick) begin
            if (\$6 ) begin
              \$15  = 6'h00;
            end
          end
      2'h1:
          if (step_tick) begin
            (* full_case = 1 *)
            if (\$8 ) begin
            end else begin
              \$15  = \$9 [5:0];
            end
          end
      2'h2:
          if (step_tick) begin
            if (\$10 ) begin
              \$15  = 6'h00;
            end
          end
      2'h3:
          if (step_tick) begin
            (* full_case = 1 *)
            if (\$12 ) begin
            end else begin
              \$15  = \$13 [5:0];
            end
          end
    endcase
    if (rst) begin
      \$15  = 6'h00;
    end
  end
  always @* begin
    if (\$auto$verilog_backend.cc:2542:dump_module$1 ) begin end
    \$16  = fsm_state;
    (* full_case = 1 *)
    casez (fsm_state)
      2'h0:
          if (step_tick) begin
            if (\$6 ) begin
              \$16  = 2'h1;
            end
          end
      2'h1:
          if (step_tick) begin
            if (\$8 ) begin
              \$16  = 2'h2;
            end
          end
      2'h2:
          if (step_tick) begin
            if (\$10 ) begin
              \$16  = 2'h3;
            end
          end
      2'h3:
          if (step_tick) begin
            if (\$12 ) begin
              \$16  = 2'h0;
            end
          end
    endcase
    if (rst) begin
      \$16  = 2'h0;
    end
  end
  always @* begin
    if (\$auto$verilog_backend.cc:2542:dump_module$1 ) begin end
    \$17  = duty;
    casez (fsm_state)
      2'h0:
          if (step_tick) begin
            (* full_case = 1 *)
            if (\$6 ) begin
            end else begin
              \$17  = \$7 [7:0];
            end
          end
      2'h1:
          /* empty */;
      2'h2:
          if (step_tick) begin
            (* full_case = 1 *)
            if (\$10 ) begin
            end else begin
              \$17  = \$11 [7:0];
            end
          end
    endcase
    if (rst) begin
      \$17  = 8'h00;
    end
  end
  assign brightness = duty;
endmodule

(* generator = "Amaranth" *)
module \pwm_breather.pwm (rst, out, duty, clk);
  reg \$auto$verilog_backend.cc:2542:dump_module$2  = 0;
  input rst;
  wire rst;
  output out;
  wire out;
  input [7:0] duty;
  wire [7:0] duty;
  input clk;
  wire clk;
  wire [8:0] \$1 ;
  reg [7:0] \$2 ;
  reg [7:0] counter = 8'h00;
  assign \$1  = counter + 1'h1;
  assign out = counter < duty;
  always @(posedge clk)
    counter <= \$2 ;
  always @* begin
    if (\$auto$verilog_backend.cc:2542:dump_module$2 ) begin end
    \$2  = \$1 [7:0];
    if (rst) begin
      \$2  = 8'h00;
    end
  end
endmodule
```

Table: Amaranth-to-Verilog Rosetta Stone for `PwmBreather` and `PwmGenerator`.

| Amaranth Construct | Exact `pwm_breather.v` Line(s) | Hardware Meaning |
| :--- | :--- | :--- |
| `with m.FSM(init="RAMP_UP"):` | `reg [1:0] fsm_state = 2'h0;` & `casez (fsm_state)` | Binary-encoded 2-bit state register + combinatorial decoders |
| `m.d.comb += state_leds.eq(0b0010)` inside `m.State` | `2'h1: state_leds = 4'h2;` | Pure Moore output decoded solely from `fsm_state` |
| `m.next = "HOLD_HIGH"` | `\$16 = 2'h1;` → `fsm_state <= \$16 ;` | Synchronous next-state update on `posedge clk` |
| `~Cat(pwm.out, pwm.out, state_leds)` | `assign leds = ~ { state_leds, out, out };` | LSB-first Amaranth `Cat` reverses into MSB-first `{ ... }` |
| `counter < self.duty` | `assign out = counter < duty;` | Unsigned combinational magnitude comparator |
| `brightness == 0` | `assign \$10 = ! duty;` | Logical NOT (`!`) checks whether all bits equal zero |
| `brightness - 1` | `wire [8:0] \$11 ; assign \$11 = duty - 1'h1;` | Borrow-preserving 9-bit subtractor sliced to `[7:0]` |

:::exercise id="ex-0006" title="Interactive Lab: Comparator, Concatenation, casez & Non-Blocking FSM" badge="Skill Practice • Tight Feedback Loop"
Complete the Verilog snippet below to compare `counter` against `duty`, pack `state_leds` and `out` MSB-first, and decode `fsm_state` inside `always @*`:

```verilog
assign out = {{blank:counter < duty|Unsigned Verilog comparison for active PWM output?|??????????????|14}};
assign leds = ~ { {{blank:state_leds|4-bit upper slice placed at MSB of leds?|??????????|10}}, out, out };

always @* begin
  state_leds = 4'h0;
  {{blank:casez|Verilog case statement allowing wildcard bits?|?????|5}} (fsm_state)
    2'h0: state_leds = 4'h1;
    2'h1: state_leds = 4'h2;
    2'h2: state_leds = 4'h4;
    2'h3: state_leds = 4'h8;
  endcase
end

always @(posedge clk)
  fsm_state {{blank:<=|Non-blocking assignment for clocked state register?|??|2}} next_state;
```

:::prompts
hint: "Use `counter < duty`, place `state_leds` first (MSB) inside `{ state_leds, out, out }`, write `casez (fsm_state)`, and update `fsm_state` with `<=`."
success: "Verified! You can now map Amaranth FSMs, `Cat()`, and PWM comparators directly to Verilog `casez`, `{ ... }`, and `<`."
:::
:::

:::verify id="verify-0006" title="Verification Lab: Check Byte-for-Byte Parity & Parameter Shrinking" badge="Terminal Gate"
Run the Lesson 0006 parity test suite and linter, then shrink all widths on the CLI to inspect how `pwm_breather.v` adapts:

```bash
.venv/bin/pytest -v apps/0006-pwm-fsm-generated-verilog/
.venv/bin/ruff check apps/0006-pwm-fsm-generated-verilog/
.venv/bin/python apps/0006-pwm-fsm-generated-verilog/pwm_fsm.py --verilog --pwm-width 4 --step-cycles 4 --hold-steps 4
```

Verify in the shrunk `--pwm-width 4 --step-cycles 4 --hold-steps 4` output: `duty` and `counter` drop from `[7:0]` to `[3:0]`, `step_timer` drops from `[16:0]` to `[1:0]` (`step_timer == 2'h3`), and `hold_count` drops from `[5:0]` to `[1:0]` (`hold_count == 2'h3`), while `fsm_state` stays `[1:0]` for the 4 states.

- [ ] All 6 tests in `test_pwm_fsm_verilog.py` pass (`pwm_breather.v == emit_verilog()`, named port wiring, `{ state_leds, out, out }`, `counter < duty`, `casez`, and width shrinking).
- [ ] `ruff check` reports `All checks passed!`.
- [ ] Shrunk Verilog output preserves `casez (fsm_state)` and `assign out = counter < duty;` with reduced bus widths.
:::

:::quiz id="quiz-0006" title="Retrieval Practice: Reading FSM & PWM Verilog" badge="3 Questions • Equal-Length Options"
- question: "In `pwm_breather.v`, why does `assign leds = ~ { state_leds, out, out };` list `state_leds` first when Amaranth wrote `~Cat(pwm.out, pwm.out, state_leds)`?"
  wrong_hint: "Compare Amaranth `Cat()` bit ordering against standard Verilog `{ msb, ..., lsb }` syntax."
  options:
    - letter: "A"
      text: "Yosys always moves multi-bit signals before single-bit signals for speed"
      correct: false
      explain: "Bit ordering is governed strictly by language semantics, not signal width or routing speed."
    - letter: "B"
      text: "Verilog concatenation packs MSB-first whereas Amaranth Cat packs bits LSB-first"
      correct: true
      explain: "Amaranth `Cat` starts at bit 0 (`out` in `[0]` and `[1]`), whereas Verilog `{ ... }` starts at the MSB (`state_leds` in `[5:2]`)."
    - letter: "C"
      text: "Active-low LEDs on pins 15 through 20 reverse bit numbering"
      correct: false
      explain: "Pin mapping in `.cst` does not alter internal bus bit order; `~` simply inverts every bit in place."
    - letter: "D"
      text: "The ~ operator reverses the order of concatenated Verilog wires"
      correct: false
      explain: "Bitwise `~` inverts `0 <-> 1` per bit without swapping bit positions."
- question: "Why does `pwm_breather.v` emit `assign \\$10  = ! duty;` using `!` instead of `~` for `brightness == 0`?"
  wrong_hint: "Distinguish a 1-bit boolean zero-check (`!`) from an 8-bit bitwise inverter (`~`)."
  options:
    - letter: "A"
      text: "Logical ! returns 1 when every duty bit equals zero"
      correct: true
      explain: "Logical NOT (`!`) collapses multi-bit values to a single boolean bit (`1` if all bits are `0`, else `0`), matching `brightness == 0`."
    - letter: "B"
      text: "Bitwise ~ flips only the sign bit on 8-bit registers"
      correct: false
      explain: "Bitwise `~` inverts all 8 bits of an 8-bit bus rather than returning a 1-bit zero comparison."
    - letter: "C"
      text: "Verilog forbids bitwise ~ inside continuous assign statements with wires"
      correct: false
      explain: "Line 40 (`assign leds = ~ { state_leds, out, out };`) uses bitwise `~` inside an `assign` statement."
    - letter: "D"
      text: "Logical ! decrements duty by one on every clock edge"
      correct: false
      explain: "Decrementing is handled separately by `\\$11 = duty - 1'h1;`, not by `! duty`."
- question: "In the `\\$17` (`duty` next-state) `casez (fsm_state)` block, why does arm `2'h1` (`HOLD_HIGH`) contain `/* empty */;` while `2'h3` (`HOLD_LOW`) is omitted?"
  wrong_hint: "Look at line 168 (`\\$17 = duty;`) directly above `casez (fsm_state)`."
  options:
    - letter: "A"
      text: "Yosys deletes the duty register during both hold states completely"
      correct: false
      explain: "`duty` must stay alive and hold its value (`8'hff` or `8'h00`) throughout both hold stages."
    - letter: "B"
      text: "The default assignment above casez holds duty unchanged without latches"
      correct: true
      explain: "Because `\\$17 = duty;` runs before `casez (fsm_state)`, any state that keeps `duty` unchanged needs no extra assignment inside `casez`."
    - letter: "C"
      text: "State 2'h1 resets duty to zero while 2'h3 overflows upward"
      correct: false
      explain: "Both hold states preserve `duty` untouched while `hold_count` counts to `6'h3f`."
    - letter: "D"
      text: "Only states 2'h0 and 2'h2 are wired to the clock"
      correct: false
      explain: "`duty <= \\$17 ;` clocks `duty` on every rising edge regardless of which state `fsm_state` holds."
:::

:::teacher-prompt title="Extend This Lesson with Your Agent"
With Phase 1 complete, you can write synchronous, combinational, debounced, PWM, and FSM designs in Amaranth **and** read their multi-module Verilog fluently! Ready for **Phase 2 (USB-UART Serial)** in Lesson 0007, or want to explore more? Ask your AI teacher:
- *"What changes in `pwm_breather.v` if we add a gamma-lookup table or button `S2` to pause the breathing FSM?"*
- *"I've mastered Phase 1 — let's build Lesson 0007 (UART TX) to send text from the Tang Nano 20K to my macOS terminal!"*
:::
