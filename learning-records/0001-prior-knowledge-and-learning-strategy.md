# Prior Knowledge and HDL Learning Strategy

The learner has strong experience with high-level programming, prior C, microcontroller tinkering, and analog op-amp synth circuits (TL074 buffered mults and envelope followers), with no prior HDL coding experience.

**Learning strategy:** Author modules in Amaranth HDL (`amaranth.lib.wiring.Component`), verify behavior with `amaranth.sim` and `pytest`, and dissect the generated Verilog in every lesson to acquire Verilog reading fluency by assimilation.

**Implications for future sessions:**
- Introduce hardware concurrency (`m.d.comb` vs `m.d.sync`) using parallel continuous signal-path analogies (op-amp stages running simultaneously) rather than sequential MCU loops.
- Always present both the Amaranth source and the actual `amaranth.back.verilog` output side-by-side so syntax mappings (`m.d.sync` → `always @(posedge clk)`, `m.d.comb` → `assign`/`always @(*)`, non-blocking `<=`) compound across lessons.
