---
title: "Glossary of FPGA & Amaranth Terms"
page_title: "Glossary — Tang Nano 20K with Amaranth HDL"
nav_id: "glossary"
nav_label: "Glossary"
badge: "Mission: Tang Nano 20K with Amaranth HDL"
subtitle: "Canonical definitions used across all lessons and reference sheets. Designed for quick screen lookup and clean printing."
card:
  title: "**Glossary of FPGA & Amaranth Terms**"
  summary: "Canonical definitions for Amaranth HDL, Verilog equivalents, and Gowin FPGA toolchain stages."
---

## 1. Amaranth & Digital Logic

**Component**:
A reusable hardware module subclassing `amaranth.lib.wiring.Component` with typed `In(...)` and `Out(...)` ports and an `elaborate(self, platform)` method that builds its internal circuit graph.
_Avoid_: Calling a hardware module a "class that executes at runtime"

**Signal**:
A named multi-bit electrical wire or register (`Signal(width)` or `Signal(range(n))`) carrying binary state inside an Amaranth design.
_Avoid_: Treating `Signal` as a mutable Python variable

**Combinational Domain (`comb`)**:
The continuous, unclocked hardware domain (`m.d.comb`) whose outputs react immediately to input changes through logic gates, equivalent to `assign` or `always @*` in Verilog.
_Avoid_: Confusing combinational logic with sequential statements

**Synchronous Domain (`sync`)**:
The clocked hardware domain (`m.d.sync`) whose registers latch new values only on the rising edge of the domain clock, equivalent to `always @(posedge clk)` with non-blocking `<=` in Verilog.
_Avoid_: Thinking `m.d.sync +=` updates a signal immediately within the same cycle

**Active-Low**:
A hardware convention where logic `0` (0 V / ground) enables a peripheral—such as sinking current through the Tang Nano 20K's six onboard LEDs—and logic `1` (3.3 V) turns it off.
_Avoid_: Assuming logic `1` always means "on"

## 2. FPGA Build Pipeline

**Elaboration**:
The Python execution step where Amaranth runs `elaborate()` to construct an RTL netlist graph and emit synthesizable Verilog or simulation models.
_Avoid_: Confusing Python elaboration time with hardware clock time

**Synthesis**:
Translation of RTL Verilog into technology-mapped FPGA primitives (LUT4 logic cells and flip-flops) for the Gowin `GW2AR-18` fabric using `yosys` (`synth_gowin`).
_Avoid_: Treating synthesis as software compilation into CPU machine code

**Place and Route**:
Physical assignment of synthesized LUTs and registers to specific FPGA fabric coordinates and routing tracks (`nextpnr-himbaechel`) guided by pin constraints (`.cst`).
_Avoid_: Skipping pin constraint verification before packing

**Bitstream**:
The binary configuration image (`.fs`) packed by `gowin_pack` and loaded over JTAG into the FPGA (`openFPGALoader`) to wire its programmable logic fabric.
_Avoid_: Calling a bitstream "firmware" (it configures physical gates rather than instructions for a CPU)

## 3. Generated Verilog Constructs

**Non-Blocking Assignment (`<=`)**:
The Verilog assignment operator used inside `always @(posedge clk)` blocks so every flip-flop samples its right-hand expression at the clock edge before updating simultaneously.
_Avoid_: Using `<=` inside combinational `always @*` blocks

**Blocking Assignment (`=`)**:
The Verilog assignment operator used inside combinational `always @*` blocks to express top-to-bottom priority mux logic where the last matching assignment wins.
_Avoid_: Using `=` to update clocked registers inside `always @(posedge clk)`

**Escaped Identifier (`\name `)**:
A Verilog identifier starting with a backslash (`\`) and terminated by whitespace (such as `\$1 ;`), used by tools like Yosys to emit names containing `$` or punctuation.
_Avoid_: Omitting the trailing space before `;` or operators after an escaped identifier

**Sized Literal (`<width>'<base><value>`)**:
An explicit-width Verilog constant specifying bit width, radix (`'b` binary, `'d` decimal, `'h` hex), and value (for example `24'hcdfe5f` or `6'h00`).
_Avoid_: Leaving large literals unsized (which defaults to 32 bits in Verilog)
