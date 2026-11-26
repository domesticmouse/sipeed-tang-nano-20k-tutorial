---
title: "Dissecting UART TX Verilog"
page_title: "Lesson 0008: Dissecting UART TX Verilog — Tang Nano 20K"
nav_id: "lesson-0008"
badge: "Lesson 0008 • Shift Registers, Bit Slices & Array ROM"
subtitle: "Dissect the 326-line Yosys Verilog generated for UartBanner and UartTx—learning non-zero reset values (10'h3ff), bit-slice right shifting (shifter[9:1]), frame packing, output reg ports, and combinational Array ROMs."
card:
  title: "**Dissecting UART TX Verilog**"
  summary: "Trace how Amaranth lowers a 10-bit UART shift register, bit slices, non-zero init=0x3FF resets, and Array ROMs into uart_banner.v."
---

:::callout title="Recommended Primary Sources"
- **Companion app**: `apps/0008-uart-tx-generated-verilog/` (`.venv/bin/pytest -v apps/0008-uart-tx-generated-verilog/`)
- **Primary docs**: [Amaranth HDL Documentation](https://amaranth-lang.org/docs/amaranth/latest/) • [Project F: Verilog Primer](https://projectf.io/)
- **Course references**: [Lesson 0007: UART Transmitter: Baud Ticks & Shift Registers](0007-uart-tx.md), [Lesson 0006: Dissecting PWM & FSM Verilog](0006-pwm-fsm-generated-verilog.md), [Glossary](../reference/GLOSSARY.md), and [Tang Nano 20K Pinout & Toolchain Sheet](../reference/tang-nano-20k-pinout.md)
:::

## 1. How Amaranth Lowers Shift Registers, Bit Slices, and `Array` ROMs {#big-picture}

In [Lesson 0007](0007-uart-tx.md), we wrote `UartTx` and `UartBanner` in Python. Converting that design with `emit_verilog()` produces **326 lines** of two-module Verilog inside `uart_banner.v` (`module uart_banner` plus `module \uart_banner.uart `).

Five **brand-new Verilog constructs** appear in `uart_banner.v`:

1. **Non-zero reset & initialization (`10'h3ff`):** `Signal(10, init=0x3FF)` emits both `reg [9:0] shifter = 10'h3ff;` and `if (rst) \$7 = 10'h3ff;`, guaranteeing the UART line rests at logic `1` on startup and synchronous reset.
2. **Bit-slice selection (`shifter[9:1]`) & single-bit indexing (`shifter[0]`):** Reading a contiguous sub-range of a bus (`[MSB:LSB]`) lets Verilog drop the bottom bit and shift upper bits right in a single combinational wiring step.
3. **Frame packing & mark-refill concatenations:** Amaranth's `Cat(Const(0, 1), self.data, Const(1, 1))` becomes `{ 1'h1, data, 1'h0 }`, and `Cat(shifter[1:], Const(1, 1))` becomes `{ 1'h1, shifter[9:1] }`.
4. **Combinational `Array` ROM as `casez (char_index)`:** Our 16-byte Python `Array` lowers into a pure `always @*` `casez` lookup table mapping `4'h0..4'hf` to ASCII hex bytes (`8'h54..8'h0a`).
5. **1-bit FSM registers (`reg fsm_state = 1'h0;`) & `output reg` ports:** Both two-state FSMs fit in a single flip-flop, and `UartTx`'s combinational `ready` output is declared directly as `output ready; reg ready;` so `always @*` can drive it.

```mermaid caption="Figure 8.1: Signal flow inside uart_banner.v — 16-byte casez ROM, 1-bit SEND/PAUSE FSM, and \uart_banner.uart 10-bit shifter"
flowchart LR
  subgraph TOP["module uart_banner (top = 1)"]
    IDX["char_index[3:0]"] --> ROM["casez -> data[7:0] (8'h54..8'h0a)"]
    FSMB["fsm_state (1-bit SEND/PAUSE)"] --> VAL["casez -> valid"]
    PTMR["pause_timer[24:0]"] -->|"== 25'h19bfcbf"| FSMB
    ROM --> INST["uart instance (.data, .valid, .ready, .tx)"]
    VAL --> INST
    INST -->|"uart_tx, ready"| LEDS["assign leds = { \$1 , uart_tx, ready }"]
  end
  subgraph SUB["module \uart_banner.uart"]
    BTMR["baud_timer[7:0]"] -->|"== 8'he9 (\$3)"| SHF["shifter[9:0] (init = 10'h3ff)"]
    BCNT["bit_count[3:0]"] -->|"! bit_count (\$4)"| FSMT["fsm_state (IDLE/SHIFT)"]
    FSMT -->|"ready"| TOP
    SHF -->|"shifter[0]"| TXOUT["assign tx = shifter[0]"]
    SHF -->|"shifter[9:1]"| RSHF["\$7 = { 1'h1, shifter[9:1] }"]
    RSHF -->|"<= clk"| SHF
  end
```

## 2. Reading `uart_banner.v` Block by Block {#block-walkthrough}

### Block 1: Top-Level Ports, Submodule Wiring & Active-Low LED Packing

```verilog caption="Lines 3–57 and 186–189 of uart_banner.v: top-level declarations, \uart_banner.uart instance, and LED concatenation"
(* top = 1 *)
(* generator = "Amaranth" *)
module uart_banner(rst, uart_tx, leds, clk);
  reg \$auto$verilog_backend.cc:2542:dump_module$1  = 0;
  input rst;
  wire rst;
  output uart_tx;
  wire uart_tx;
  output [5:0] leds;
  wire [5:0] leds;
  input clk;
  wire clk;
  ...
  reg [3:0] char_index = 4'h0;
  reg [7:0] data;
  reg fsm_state = 1'h0;
  reg [3:0] msg_count = 4'h0;
  reg [24:0] pause_timer = 25'h0000000;
  wire ready;
  wire tx;
  reg valid;
  assign \$1  = ~ msg_count;
  assign \$2  = ! fsm_state;
  assign \$4  = char_index == 4'hf;
  assign \$5  = msg_count + 1'h1;
  assign \$6  = char_index + 1'h1;
  assign \$7  = pause_timer == 25'h19bfcbf;
  assign \$8  = pause_timer + 1'h1;
  ...
  \uart_banner.uart  uart (
    .clk(clk),
    .data(data),
    .ready(ready),
    .rst(rst),
    .tx(uart_tx),
    .valid(valid)
  );
  ...
  assign tx = uart_tx;
  assign leds = { \$1 , uart_tx, ready };
  assign \$3  = fsm_state;
endmodule
```

- **Why is `pause_timer` 25 bits wide (`[24:0]`)?** `27_000_000 - 1 = 26_999_999 = 0x19BFCBF`, which fits in 25 bits (`2^25 = 33,554,432`), matching line 40 (`pause_timer == 25'h19bfcbf`).
- **MSB-first LED packing (line 187):** Amaranth's `Cat(uart.ready, uart.tx, ~msg_count)` reverses into `{ \$1 , uart_tx, ready }`, putting inverted `msg_count` (`\$1`) in `leds[5:2]`, `uart_tx` in `leds[1]`, and `ready` in `leds[0]`.
- **Direct port aliasing on `.tx(uart_tx)`:** Because `self.uart_tx.eq(uart.tx)` wired the submodule port straight to the top output `uart_tx`, Yosys connected `.tx(uart_tx)` directly and left `assign tx = uart_tx;` as a harmless alias.

### Block 2: How Amaranth's `Array` Becomes a 16-Byte `casez` ROM

```verilog caption="Lines 58–95 of uart_banner.v: 16-entry ASCII lookup table generated from Array(Const(...))"
  always @* begin
    if (\$auto$verilog_backend.cc:2542:dump_module$1 ) begin end
    (* full_case = 1 *)
    casez (char_index)
      4'h0:
          data = 8'h54;
      4'h1:
          data = 8'h61;
      4'h2:
          data = 8'h6e;
      4'h3:
          data = 8'h67;
      4'h4:
          data = 8'h20;
      4'h5:
          data = 8'h4e;
      4'h6:
          data = 8'h61;
      4'h7:
          data = 8'h6e;
      4'h8:
          data = 8'h6f;
      4'h9:
          data = 8'h20;
      4'ha:
          data = 8'h32;
      4'hb:
          data = 8'h30;
      4'hc:
          data = 8'h4b;
      4'hd:
          data = 8'h21;
      4'he:
          data = 8'h0d;
      4'hf:
          data = 8'h0a;
    endcase
  end
```

- Every `Const(b, 8)` byte of `b"Tang Nano 20K!\r\n"` appears verbatim in hexadecimal: `8'h54` (`'T'`), `8'h61` (`'a'`), ..., `8'h0d` (`'\r'`), `8'h0a` (`'\n'`).
- Notice `reg [7:0] data;` (line 28) is **not** clocked by `always @(posedge clk)`. Using `reg` on the left-hand side of `always @*` is standard Verilog syntax for a combinational mux—here it synthesizes into pure LUT4 truth tables with zero flip-flops!{{sidenote: A common Verilog trap for newcomers is thinking `reg` always creates a flip-flop. In Verilog, `reg` only means "assigned inside an `always` or `initial` block"—the sensitivity list (`@(posedge clk)` vs `@*`) decides whether it becomes a register or combinational logic.}}

### Block 3: Inside `\uart_banner.uart ` — Non-Zero Reset, Baud Timer & `output reg`

```verilog caption="Lines 191–242 of uart_banner.v: child transmitter module ports, registers, and ready decoder"
(* generator = "Amaranth" *)
module \uart_banner.uart (rst, data, valid, ready, tx, clk);
  reg \$auto$verilog_backend.cc:2542:dump_module$2  = 0;
  input rst;
  wire rst;
  input [7:0] data;
  wire [7:0] data;
  input valid;
  wire valid;
  output ready;
  reg ready;
  output tx;
  wire tx;
  input clk;
  wire clk;
  ...
  reg [7:0] baud_timer = 8'h00;
  reg [3:0] bit_count = 4'h0;
  reg fsm_state = 1'h0;
  reg [9:0] shifter = 10'h3ff;
  assign \$1  = ! fsm_state;
  assign \$3  = baud_timer == 8'he9;
  assign \$4  = ! bit_count;
  assign \$5  = bit_count - 1'h1;
  assign \$6  = baud_timer + 1'h1;
  always @(posedge clk)
    shifter <= \$7 ;
  always @(posedge clk)
    baud_timer <= \$8 ;
  always @(posedge clk)
    bit_count <= \$9 ;
  always @(posedge clk)
    fsm_state <= \$10 ;
  always @* begin
    if (\$auto$verilog_backend.cc:2542:dump_module$2 ) begin end
    (* full_case = 1 *)
    casez (fsm_state)
      1'h0:
          ready = 1'h1;
      1'h1:
          ready = 1'h0;
    endcase
  end
```

- **`output ready; reg ready;` (lines 200–201):** Unlike `tx` (`output tx; wire tx;`), `ready` is assigned inside `always @*` (`casez (fsm_state)`), so Yosys declares it `reg` instead of `wire`.
- **1-bit FSM encoding (`reg fsm_state = 1'h0;`):** With two states (`IDLE` and `SHIFT`), `fsm_state` needs only one flip-flop: `1'h0` (`IDLE`) drives `ready = 1'h1`, and `1'h1` (`SHIFT`) drives `ready = 1'h0`.
- **Baud threshold `8'he9` (line 221):** `0xe9 = 233 = 234 - 1`. Every 234 clock cycles, `\$3` goes high for one cycle.

### Block 4: Frame Packing (`{ 1'h1, data, 1'h0 }`) & Right-Shift Bit Slicing (`{ 1'h1, shifter[9:1] }`)

```verilog caption="Lines 243–260 and 324–326 of uart_banner.v: 10-bit shifter next-state logic and serial output"
  always @* begin
    if (\$auto$verilog_backend.cc:2542:dump_module$2 ) begin end
    \$7  = shifter;
    (* full_case = 1 *)
    casez (fsm_state)
      1'h0:
          if (valid) begin
            \$7  = { 1'h1, data, 1'h0 };
          end
      1'h1:
          if (\$3 ) begin
            \$7  = { 1'h1, shifter[9:1] };
          end
    endcase
    if (rst) begin
      \$7  = 10'h3ff;
    end
  end
  ...
  assign tx = shifter[0];
  assign \$2  = fsm_state;
endmodule
```

- **Look closely at lines 250, 254, 258, and 324—that single block is the entire UART serializer:**
  - **Line 250 (`{ 1'h1, data, 1'h0 }`):** Concatenates MSB-first: `1'h1` at bit `[9]` (stop bit), `data[7:0]` at bits `[8:1]`, and `1'h0` at bit `[0]` (start bit).
  - **Line 254 (`{ 1'h1, shifter[9:1] }`):** Slices the upper 9 bits `shifter[9:1]` into bits `[8:0]` (shifting every bit right by 1) and feeds `1'h1` into bit `[9]`. Bit `shifter[0]` simply drops off after it has been held on `tx` for 234 cycles.
  - **Line 258 (`if (rst) \$7 = 10'h3ff;`):** Synchronous reset overrides `\$7` back to ten `1`s—matching `reg [9:0] shifter = 10'h3ff;` on line 219.
  - **Line 324 (`assign tx = shifter[0];`):** Wires bit `0` of `shifter` straight out to the pin.

### Block 5: Clean Human-Written Equivalent

When engineers author a UART transmitter directly in Verilog, they parameterize `DIVISOR`, use `localparam` state names, and combine the next-state logic directly inside `always @(posedge clk)`:

```verilog caption="Conceptual hand-written Verilog equivalent of uart_banner.v"
module uart_tx #(parameter DIVISOR = 234) (
  input        clk,
  input        rst,
  input  [7:0] data,
  input        valid,
  output       ready,
  output       tx
);
  localparam IDLE  = 1'b0,
             SHIFT = 1'b1;

  reg       state      = IDLE;
  reg [9:0] shifter    = 10'h3ff;
  reg [7:0] baud_timer = 8'd0;
  reg [3:0] bit_count  = 4'd0;

  assign ready = (state == IDLE);
  assign tx    = shifter[0];

  always @(posedge clk) begin
    if (rst) begin
      state      <= IDLE;
      shifter    <= 10'h3ff;
      baud_timer <= 8'd0;
      bit_count  <= 4'd0;
    end else if (state == IDLE) begin
      if (valid) begin
        shifter    <= {1'b1, data, 1'b0};
        baud_timer <= 8'd0;
        bit_count  <= 4'd9;
        state      <= SHIFT;
      end
    end else begin
      if (baud_timer == DIVISOR - 1) begin
        baud_timer <= 8'd0;
        shifter    <= {1'b1, shifter[9:1]};
        if (bit_count == 4'd0)
          state <= IDLE;
        else
          bit_count <= bit_count - 4'd1;
      end else begin
        baud_timer <= baud_timer + 8'd1;
      end
    end
  end
endmodule
```

## 3. Complete `uart_banner.v` Listing & Rosetta Stone {#complete-listing}

### Complete uart_banner.v Listing

```verilog caption="apps/0008-uart-tx-generated-verilog/uart_banner.v"
/* Generated by Yosys 0.71 (git sha1 b4c586fd3, Release, Clang /home/runner/work/amaranth-yosys/amaranth-yosys/wasi-sdk-34.0-x86_64-linux/bin/clang++ 23.1.0) */

(* top = 1 *)
(* generator = "Amaranth" *)
module uart_banner(rst, uart_tx, leds, clk);
  reg \$auto$verilog_backend.cc:2542:dump_module$1  = 0;
  input rst;
  wire rst;
  output uart_tx;
  wire uart_tx;
  output [5:0] leds;
  wire [5:0] leds;
  input clk;
  wire clk;
  wire [3:0] \$1 ;
  reg [24:0] \$10 ;
  reg [3:0] \$11 ;
  reg \$12 ;
  wire \$2 ;
  wire \$3 ;
  wire \$4 ;
  wire [4:0] \$5 ;
  wire [4:0] \$6 ;
  wire \$7 ;
  wire [25:0] \$8 ;
  reg [3:0] \$9 ;
  reg [3:0] char_index = 4'h0;
  reg [7:0] data;
  reg fsm_state = 1'h0;
  reg [3:0] msg_count = 4'h0;
  reg [24:0] pause_timer = 25'h0000000;
  wire ready;
  wire tx;
  reg valid;
  assign \$1  = ~ msg_count;
  assign \$2  = ! fsm_state;
  assign \$4  = char_index == 4'hf;
  assign \$5  = msg_count + 1'h1;
  assign \$6  = char_index + 1'h1;
  assign \$7  = pause_timer == 25'h19bfcbf;
  assign \$8  = pause_timer + 1'h1;
  always @(posedge clk)
    char_index <= \$9 ;
  always @(posedge clk)
    pause_timer <= \$10 ;
  always @(posedge clk)
    msg_count <= \$11 ;
  always @(posedge clk)
    fsm_state <= \$12 ;
  \uart_banner.uart  uart (
    .clk(clk),
    .data(data),
    .ready(ready),
    .rst(rst),
    .tx(uart_tx),
    .valid(valid)
  );
  always @* begin
    if (\$auto$verilog_backend.cc:2542:dump_module$1 ) begin end
    (* full_case = 1 *)
    casez (char_index)
      4'h0:
          data = 8'h54;
      4'h1:
          data = 8'h61;
      4'h2:
          data = 8'h6e;
      4'h3:
          data = 8'h67;
      4'h4:
          data = 8'h20;
      4'h5:
          data = 8'h4e;
      4'h6:
          data = 8'h61;
      4'h7:
          data = 8'h6e;
      4'h8:
          data = 8'h6f;
      4'h9:
          data = 8'h20;
      4'ha:
          data = 8'h32;
      4'hb:
          data = 8'h30;
      4'hc:
          data = 8'h4b;
      4'hd:
          data = 8'h21;
      4'he:
          data = 8'h0d;
      4'hf:
          data = 8'h0a;
    endcase
  end
  always @* begin
    if (\$auto$verilog_backend.cc:2542:dump_module$1 ) begin end
    (* full_case = 1 *)
    casez (fsm_state)
      1'h0:
          valid = 1'h1;
      1'h1:
          valid = 1'h0;
    endcase
  end
  always @* begin
    if (\$auto$verilog_backend.cc:2542:dump_module$1 ) begin end
    \$9  = char_index;
    casez (fsm_state)
      1'h0:
          if (ready) begin
            (* full_case = 1 *)
            if (\$4 ) begin
              \$9  = 4'h0;
            end else begin
              \$9  = \$6 [3:0];
            end
          end
    endcase
    if (rst) begin
      \$9  = 4'h0;
    end
  end
  always @* begin
    if (\$auto$verilog_backend.cc:2542:dump_module$1 ) begin end
    \$10  = pause_timer;
    (* full_case = 1 *)
    casez (fsm_state)
      1'h0:
          if (ready) begin
            if (\$4 ) begin
              \$10  = 25'h0000000;
            end
          end
      1'h1:
          if (ready) begin
            (* full_case = 1 *)
            if (\$7 ) begin
              \$10  = 25'h0000000;
            end else begin
              \$10  = \$8 [24:0];
            end
          end
    endcase
    if (rst) begin
      \$10  = 25'h0000000;
    end
  end
  always @* begin
    if (\$auto$verilog_backend.cc:2542:dump_module$1 ) begin end
    \$11  = msg_count;
    casez (fsm_state)
      1'h0:
          if (ready) begin
            if (\$4 ) begin
              \$11  = \$5 [3:0];
            end
          end
    endcase
    if (rst) begin
      \$11  = 4'h0;
    end
  end
  always @* begin
    if (\$auto$verilog_backend.cc:2542:dump_module$1 ) begin end
    \$12  = fsm_state;
    (* full_case = 1 *)
    casez (fsm_state)
      1'h0:
          if (ready) begin
            if (\$4 ) begin
              \$12  = 1'h1;
            end
          end
      1'h1:
          if (ready) begin
            if (\$7 ) begin
              \$12  = 1'h0;
            end
          end
    endcase
    if (rst) begin
      \$12  = 1'h0;
    end
  end
  assign tx = uart_tx;
  assign leds = { \$1 , uart_tx, ready };
  assign \$3  = fsm_state;
endmodule

(* generator = "Amaranth" *)
module \uart_banner.uart (rst, data, valid, ready, tx, clk);
  reg \$auto$verilog_backend.cc:2542:dump_module$2  = 0;
  input rst;
  wire rst;
  input [7:0] data;
  wire [7:0] data;
  input valid;
  wire valid;
  output ready;
  reg ready;
  output tx;
  wire tx;
  input clk;
  wire clk;
  wire \$1 ;
  reg \$10 ;
  wire \$2 ;
  wire \$3 ;
  wire \$4 ;
  wire [4:0] \$5 ;
  wire [8:0] \$6 ;
  reg [9:0] \$7 ;
  reg [7:0] \$8 ;
  reg [3:0] \$9 ;
  reg [7:0] baud_timer = 8'h00;
  reg [3:0] bit_count = 4'h0;
  reg fsm_state = 1'h0;
  reg [9:0] shifter = 10'h3ff;
  assign \$1  = ! fsm_state;
  assign \$3  = baud_timer == 8'he9;
  assign \$4  = ! bit_count;
  assign \$5  = bit_count - 1'h1;
  assign \$6  = baud_timer + 1'h1;
  always @(posedge clk)
    shifter <= \$7 ;
  always @(posedge clk)
    baud_timer <= \$8 ;
  always @(posedge clk)
    bit_count <= \$9 ;
  always @(posedge clk)
    fsm_state <= \$10 ;
  always @* begin
    if (\$auto$verilog_backend.cc:2542:dump_module$2 ) begin end
    (* full_case = 1 *)
    casez (fsm_state)
      1'h0:
          ready = 1'h1;
      1'h1:
          ready = 1'h0;
    endcase
  end
  always @* begin
    if (\$auto$verilog_backend.cc:2542:dump_module$2 ) begin end
    \$7  = shifter;
    (* full_case = 1 *)
    casez (fsm_state)
      1'h0:
          if (valid) begin
            \$7  = { 1'h1, data, 1'h0 };
          end
      1'h1:
          if (\$3 ) begin
            \$7  = { 1'h1, shifter[9:1] };
          end
    endcase
    if (rst) begin
      \$7  = 10'h3ff;
    end
  end
  always @* begin
    if (\$auto$verilog_backend.cc:2542:dump_module$2 ) begin end
    \$8  = baud_timer;
    (* full_case = 1 *)
    casez (fsm_state)
      1'h0:
          if (valid) begin
            \$8  = 8'h00;
          end
      1'h1:
          (* full_case = 1 *)
          if (\$3 ) begin
            \$8  = 8'h00;
          end else begin
            \$8  = \$6 [7:0];
          end
    endcase
    if (rst) begin
      \$8  = 8'h00;
    end
  end
  always @* begin
    if (\$auto$verilog_backend.cc:2542:dump_module$2 ) begin end
    \$9  = bit_count;
    (* full_case = 1 *)
    casez (fsm_state)
      1'h0:
          if (valid) begin
            \$9  = 4'h9;
          end
      1'h1:
          if (\$3 ) begin
            (* full_case = 1 *)
            if (\$4 ) begin
            end else begin
              \$9  = \$5 [3:0];
            end
          end
    endcase
    if (rst) begin
      \$9  = 4'h0;
    end
  end
  always @* begin
    if (\$auto$verilog_backend.cc:2542:dump_module$2 ) begin end
    \$10  = fsm_state;
    (* full_case = 1 *)
    casez (fsm_state)
      1'h0:
          if (valid) begin
            \$10  = 1'h1;
          end
      1'h1:
          if (\$3 ) begin
            if (\$4 ) begin
              \$10  = 1'h0;
            end
          end
    endcase
    if (rst) begin
      \$10  = 1'h0;
    end
  end
  assign tx = shifter[0];
  assign \$2  = fsm_state;
endmodule
```

Table: Amaranth-to-Verilog Rosetta Stone for `UartBanner` and `UartTx`.

| Amaranth Construct | Exact `uart_banner.v` Line(s) | Hardware Meaning |
| :--- | :--- | :--- |
| `Signal(10, init=0x3FF)` | `reg [9:0] shifter = 10'h3ff;` & `if (rst) \$7 = 10'h3ff;` | Non-zero power-up and synchronous reset value (idle-high UART) |
| `self.tx.eq(shifter[0])` | `assign tx = shifter[0];` | Single-bit wire tap from LSB flip-flop of shift register |
| `Cat(Const(0, 1), self.data, Const(1, 1))` | `\$7 = { 1'h1, data, 1'h0 };` | Pack stop bit `[9]`, payload `[8:1]`, start bit `[0]` |
| `Cat(shifter[1:], Const(1, 1))` | `\$7 = { 1'h1, shifter[9:1] };` | Bit-slice right shift filling MSB `[9]` with mark (`1`) |
| `rom = Array(...)` & `rom[char_index]` | `casez (char_index) 4'h0: data = 8'h54; ...` | Combinational 16-byte ROM synthesized into LUT muxes |
| `with m.FSM(init="IDLE"):` | `reg fsm_state = 1'h0;` | Single flip-flop encoding two FSM states (`IDLE` / `SHIFT`) |
| `self.leds.eq(Cat(uart.ready, uart.tx, ~msg_count))` | `assign leds = { \$1 , uart_tx, ready };` | MSB-first bit packing across top-level output pins |

:::exercise id="ex-0008" title="Interactive Lab: Non-Zero Reset, Frame Concatenation & Bit Slicing" badge="Skill Practice • Tight Feedback Loop"
Complete the Verilog snippet below for `UartTx`: initialize `shifter` to all-ones, pack the 8N1 frame MSB-first, shift bits right on each baud tick, and drive `tx` from bit `0`:

```verilog
reg [9:0] shifter = {{blank:10'h3ff|10-bit hexadecimal literal with all bits set to 1?|??????|7}};

assign tx = {{blank:shifter[0]|Bit 0 tap of the shift register?|??????????|10}};

always @* begin
  next_shifter = shifter;
  casez (fsm_state)
    1'h0: if (valid) next_shifter = {{blank:{ 1'h1, data, 1'h0 }|MSB-first Verilog concatenation for stop=1, data, start=0?|????????????????????|20}};
    1'h1: if (baud_tick) next_shifter = { 1'h1, {{blank:shifter[9:1]|Upper 9-bit slice shifted right by one bit?|?????????????|13}} };
  endcase
  if (rst) next_shifter = 10'h3ff;
end
```

:::prompts
hint: "Use `10'h3ff` for the 10-bit all-ones literal, `shifter[0]` for `tx`, `{ 1'h1, data, 1'h0 }` for MSB-first frame packing, and `shifter[9:1]` to drop bit `0`."
success: "Verified! You can now read and write Verilog shift registers, bit slices, and non-zero reset logic."
:::
:::

:::verify id="verify-0008" title="Verification Lab: Check Byte-for-Byte Parity & Parameter Shrinking" badge="Terminal Gate"
Run the Lesson 0008 parity test suite and linter, then shrink `divisor`, `pause_cycles`, and `message` on the CLI to watch the generated Verilog adapt:

```bash
.venv/bin/pytest -v apps/0008-uart-tx-generated-verilog/
.venv/bin/ruff check apps/0008-uart-tx-generated-verilog/
.venv/bin/python apps/0008-uart-tx-generated-verilog/uart_tx.py --verilog --divisor 4 --pause-cycles 4 --message Hi
```

Inspect the shrunk output: `baud_timer` shrinks from `[7:0]` to `[1:0]` (`baud_timer == 2'h3`), `pause_timer` shrinks from `[24:0]` to `[1:0]` (`pause_timer == 2'h3`), `char_index` collapses to 1 bit (`reg char_index = 1'h0;`) with a 2-entry ROM (`4'h48`, `4'h69`), while `shifter` stays `[9:0]` (`10'h3ff`) because every UART 8N1 frame is always 10 bits wide.

- [ ] All 6 tests in `test_uart_tx_verilog.py` pass (`uart_banner.v == emit_verilog()`, ports & registers, named port wiring & `{ 1'h1, shifter[9:1] }`, `8'he9` / `25'h19bfcbf` / `10'h3ff` reset, all 16 `casez (char_index)` ASCII entries, and parameter shrinking).
- [ ] `ruff check` reports `All checks passed!`.
- [ ] Shrunk Verilog keeps `shifter` at `[9:0]` while compressing `baud_timer`, `pause_timer`, and `char_index`.
:::

:::quiz id="quiz-0008" title="Retrieval Practice: Reading UART TX Verilog" badge="3 Questions • Equal-Length Options"
- question: "Why does `uart_banner.v` emit `reg [9:0] shifter = 10'h3ff;` and `if (rst) \\$7 = 10'h3ff;` inside `\\uart_banner.uart`?"
  wrong_hint: "Check what happens on `assign tx = shifter[0];` at power-up and when `S1` (`rst`) is pressed."
  options:
    - letter: "A"
      text: "All-one reset ensures the serial TX output stays idle high"
      correct: true
      explain: "Because `tx` reads `shifter[0]`, setting `shifter` to `10'h3ff` guarantees `tx == 1` on power-up and reset."
    - letter: "B"
      text: "Hexadecimal 3FF marks an uninitialized register that Yosys leaves floating"
      correct: false
      explain: "`10'h3ff` is an explicit 10-bit binary constant (`10'b11_1111_1111`), never an uninitialized or high-impedance state."
    - letter: "C"
      text: "Gowin BRAM blocks require ten-bit counters to start at 1023"
      correct: false
      explain: "`shifter` is synthesized in regular fabric flip-flops rather than BRAM and represents a 10-bit shift register, not a counter."
    - letter: "D"
      text: "Yosys automatically sets every Amaranth signal to all-ones on reset"
      correct: false
      explain: "Every other register in `uart_banner.v` (`baud_timer`, `bit_count`, `char_index`) resets to `0`; only `shifter` resets to `10'h3ff` due to `init=0x3FF`."
- question: "What hardware operation does `\\$7 = { 1'h1, shifter[9:1] };` perform on each baud tick in `SHIFT` state?"
  wrong_hint: "Remember Verilog brace concatenation `{ msb, ..., lsb }` places the left expression in the highest bits."
  options:
    - letter: "A"
      text: "It shifts bits left and inserts zero into bit zero"
      correct: false
      explain: "Left-shifting would read `shifter[8:0]`; reading `shifter[9:1]` drops bit `0` and moves bits `9..1` down into `8..0`."
    - letter: "B"
      text: "It shifts bits right and fills bit nine with one"
      correct: true
      explain: "`shifter[9:1]` shifts bits right by one position toward `shifter[0]` (`tx`), while `1'h1` fills bit `[9]` with the idle mark state."
    - letter: "C"
      text: "It reverses bit order and writes data directly to leds"
      correct: false
      explain: "`{ 1'h1, shifter[9:1] }` preserves bit order while shifting down by one bit inside `\\uart_banner.uart`."
    - letter: "D"
      text: "It duplicates bit nine across all ten bits of shifter"
      correct: false
      explain: "Only bit `[9]` receives `1'h1`; bits `[8:0]` receive the previous values of `shifter[9:1]`."
- question: "How does Amaranth's `rom = Array(Const(b, 8) for b in self.message)` appear in `uart_banner.v`?"
  wrong_hint: "Inspect lines 58–95 of `uart_banner.v` where `data` gets assigned from `char_index`."
  options:
    - letter: "A"
      text: "As a clocked dual-port block RAM updated on negedge clk"
      correct: false
      explain: "Small `Array` tables of `Const` bytes elaborate into pure combinational `always @*` logic, not clocked memory."
    - letter: "B"
      text: "As ten separate external shift registers instantiated inside uart submodule"
      correct: false
      explain: "The `Array` lookup lives inside top-level `uart_banner` and feeds the 8-bit `data` input of `uart`."
    - letter: "C"
      text: "As a combinational casez lookup decoding char_index into 8-bit data"
      correct: true
      explain: "`always @*` runs `casez (char_index)` over `4'h0..4'hf` to drive `data` with the corresponding ASCII byte."
    - letter: "D"
      text: "As a Python runtime dictionary queried over USB during execution"
      correct: false
      explain: "Python elaboration finishes before synthesis; the 16 ASCII bytes are permanently baked into FPGA LUTs."
:::

:::teacher-prompt title="Extend This Lesson with Your Agent"
You can now transmit 115,200-baud serial text from the Tang Nano 20K **and** read the shift-register, bit-slice, and ROM Verilog behind it! Ready for **Lesson 0009 (UART RX & Interactive Echo)** so your macOS keyboard can control the FPGA's LEDs? Ask your AI teacher:
- *"How does `UartBanner`'s `casez` ROM synthesize into Gowin LUT4s if the message is 16 bytes vs 1,024 bytes?"*
- *"I've mastered Lesson 0008 — let's build Lesson 0009 (UART RX & Echo) to receive keystrokes from my macOS terminal on pin 70!"*
:::
