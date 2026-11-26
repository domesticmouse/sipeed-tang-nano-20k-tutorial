# Verilog Dissection Needs Its Own Dedicated Lesson

Combining first-time Amaranth HDL authoring (`m.d.sync` vs. `m.d.comb`, `wiring.Component`, `.cst` pin constraints) and raw Yosys-generated Verilog dissection in Lesson 0001 exceeded working-memory limits—the learner reported having "no idea what is going on" when reading `blinky.v`.

Verilog dissection was split into Lesson 0002 (`0002-dissecting-generated-verilog.md`) to unpack Yosys compiler artifacts (`\$1` escaped identifiers, `$auto$` sim-init guards, `reg`-typed combinational muxes, carry-preserving `[N:0]` widths, sized literals, and `<=` vs. `=`) systematically. Future lessons should keep each unit tightly scoped to one primary mental leap and build incrementally on these Verilog constructs rather than introducing multiple unfamiliar compiler idioms simultaneously.
