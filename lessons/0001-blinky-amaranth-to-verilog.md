---
title: "Blinky in Amaranth & Verilog Dissection"
page_title: "Lesson 0001: Blinky in Amaranth & Verilog Dissection — Tang Nano 20K"
nav_id: "lesson-0001"
badge: "Lesson 0001 • LEDs & Verilog Assimilation"
subtitle: "Build a 6-bit hardware binary counter in Amaranth HDL, test it cycle-by-cycle in pytest, dissect every line of the generated Verilog, and flash it to your Tang Nano 20K."
card:
  title: "**Blinky in Amaranth & Verilog Dissection**"
  summary: "Wire your first synchronous counter in Amaranth, verify active-low LED output in pytest, and map the generated Verilog back to Python."
---

:::callout title="Recommended Primary Sources"
- **Companion app**: `apps/0001-blinky-amaranth-to-verilog/` (`../../.venv/bin/pytest -v`)
- **Primary docs**: [Amaranth HDL Documentation](https://amaranth-lang.org/docs/amaranth/latest/) • [Sipeed Tang Nano 20K Wiki](https://wiki.sipeed.com/hardware/en/tang/tang-nano-20k/nano-20k.html)
- **Course references**: [Glossary](../reference/GLOSSARY.md) and [Tang Nano 20K Pinout & Toolchain Sheet](../reference/tang-nano-20k-pinout.md)
:::

## 1. Thinking in Parallel Circuits, Not Sequential Loops {#mental-model}

If you have built analog circuits around a TL074 quad op-amp—say a buffered mult feeding an envelope follower—you already understand the hardest conceptual leap in FPGA design. On a breadboard, every op-amp stage is **always powered and always running in parallel**. The buffer does not wait for the rectifier to "return" before it can act; signals flow simultaneously along physical copper traces.

An FPGA works the same way, except instead of op-amps and capacitors, its fabric contains 20,736 programmable 4-input lookup tables (`LUT4`) and 15,552 D-type flip-flops inside the `GW2AR-LV18QN88C8/I7`.{{sidenote: In C on a microcontroller, `while (1)` executes one instruction after another. In an FPGA, your Python code runs *once* during **elaboration** to wire physical gates and flip-flops together, and once flashed, every block runs continuously on every tick of the 27 MHz crystal.}}

Amaranth separates hardware into two distinct domains so you never confuse continuous wires with clocked memory:

1. **Combinational domain (`m.d.comb`)**: Pure logic gates (inverters, comparators, adders) whose outputs react immediately whenever their inputs change—just like an op-amp inverter or comparator stage.
2. **Synchronous domain (`m.d.sync`)**: Edge-triggered D flip-flops that hold their voltage steady until the rising edge of the `clk` signal, when every register snapshots its next value simultaneously—just like a fleet of clocked sample-and-hold stages.

```mermaid caption="Figure 1.1: Blinky hardware datapath — synchronous registers feed combinational logic continuously"
flowchart LR
  CLK["27 MHz Crystal (Pin 4)"] --> TIMER["timer register (m.d.sync)"]
  TIMER -->|"timer == half_period - 1"| PAT["pattern[5:0] register (m.d.sync)"]
  PAT --> INV["Bitwise ~pattern (m.d.comb)"]
  INV --> LEDS["leds[5:0] (Pins 15..20, Active-Low)"]
```

## 2. Building `Blinky` Block by Block {#block-walkthrough}

On the Tang Nano 20K, the 27 MHz crystal drives pin `4`, button `S1` drives pin `88` (active-high when pressed), and the six single-color LEDs on pins `15`–`20` are **active-low**.{{sidenote: Each LED's anode connects to $+3.3\text{ V}$ through a resistor and its cathode connects to an FPGA pin. Driving `0` sinks current and lights the LED; driving `1` turns it off.}} At 27 MHz, counting $13{,}500{,}000$ clock ticks gives exactly $0.5\text{ s}$ per step ($27{,}000{,}000 / 2 = 13{,}500{,}000$).

### Block 1: Declaring the Component Boundary and Parameters

```python caption="Component signature and constructor in blinky.py"
class Blinky(wiring.Component):
    leds: Out(6)

    def __init__(self, half_period: int = 13_500_000):
        if half_period < 1:
            raise ValueError("half_period must be at least 1")
        self.half_period = half_period
        super().__init__()
```

- `wiring.Component` declares a reusable hardware block whose external pins are described by type annotations.
- `leds: Out(6)` creates a 6-bit output bus (`leds[5:0]`). You do not declare `clk` or `rst` manually—Amaranth provides them automatically through the default `sync` clock domain.
- `half_period` is a plain Python build-time parameter (`13_500_000` for real hardware, or `4` in fast unit tests). Calling `super().__init__()` reads the `leds: Out(6)` signature and constructs the port object.

### Block 2: Clocked State in `m.d.sync`

```python caption="Clocked timer and 6-bit binary counter inside elaborate()"
    def elaborate(self, platform):
        m = Module()

        timer = Signal(range(self.half_period))
        pattern = Signal(6)

        with m.If(timer == self.half_period - 1):
            m.d.sync += [
                timer.eq(0),
                pattern.eq(pattern + 1),
            ]
        with m.Else():
            m.d.sync += timer.eq(timer + 1)
```

- `Signal(range(self.half_period))` automatically computes the minimum bit width needed to hold `0` through `self.half_period - 1`. For $13{,}500{,}000$, Amaranth allocates a 24-bit register ($2^{24} = 16{,}777{,}216$).
- Both `timer` and `pattern` default to reset value `0` when the `rst` signal is asserted.
- Inside `with m.If(...)`, Amaranth uses `m.If` / `m.Else` (not Python's `if` / `else`) because we are building a hardware multiplexer inside the FPGA rather than branching in Python right now.{{sidenote: Think of Python `if` as deciding *which hardware to build* at compile time, and `m.If` as building a *live hardware comparator + mux* inside the chip.}}
- Because `timer.eq(0)` and `pattern.eq(pattern + 1)` live in `m.d.sync`, both registers update in lockstep on the exact same rising clock edge.

### Block 3: Continuous Active-Low Output in `m.d.comb`

```python caption="Combinational inversion driving the active-low LED pins"
        m.d.comb += self.leds.eq(~pattern)
        return m
```

- `m.d.comb += self.leds.eq(~pattern)` wires six hardware inverters directly from the `pattern` flip-flops to the `leds` output pins.
- When `pattern` is `6'b000000` after reset, `~pattern` is `6'b111111`, keeping all six LEDs dark until the first half-second tick turns LED 0 on (`~6'b000001 == 6'b111110`).

### Complete blinky.py Listing

```python caption="apps/0001-blinky-amaranth-to-verilog/blinky.py"
import argparse
from pathlib import Path

from amaranth import Module, Signal
from amaranth.back import verilog
from amaranth.lib import wiring
from amaranth.lib.wiring import Out
from amaranth.sim import Simulator


class Blinky(wiring.Component):
    leds: Out(6)

    def __init__(self, half_period: int = 13_500_000):
        if half_period < 1:
            raise ValueError("half_period must be at least 1")
        self.half_period = half_period
        super().__init__()

    def elaborate(self, platform):
        m = Module()

        timer = Signal(range(self.half_period))
        pattern = Signal(6)

        with m.If(timer == self.half_period - 1):
            m.d.sync += [
                timer.eq(0),
                pattern.eq(pattern + 1),
            ]
        with m.Else():
            m.d.sync += timer.eq(timer + 1)

        m.d.comb += self.leds.eq(~pattern)
        return m


def emit_verilog(half_period: int = 13_500_000) -> str:
    dut = Blinky(half_period=half_period)
    return verilog.convert(dut, name="blinky", emit_src=False)


def run_vcd(output_path: Path, half_period: int = 4, ticks: int = 40) -> None:
    dut = Blinky(half_period=half_period)

    async def testbench(ctx):
        for _ in range(ticks):
            await ctx.tick()

    sim = Simulator(dut)
    sim.add_clock(1 / 27_000_000)
    sim.add_testbench(testbench)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with sim.write_vcd(str(output_path)):
        sim.run()


def main() -> None:
    parser = argparse.ArgumentParser(description="Tang Nano 20K Blinky in Amaranth HDL")
    parser.add_argument("--verilog", action="store_true", help="Write build/blinky.v and print it")
    parser.add_argument("--vcd", action="store_true", help="Simulate fast counter to build/blinky.vcd")
    parser.add_argument("--half-period", type=int, default=13_500_000, help="Clock cycles per step")
    args = parser.parse_args()

    build_dir = Path(__file__).parent / "build"
    if args.verilog or not args.vcd:
        code = emit_verilog(half_period=args.half_period)
        build_dir.mkdir(parents=True, exist_ok=True)
        out_file = build_dir / "blinky.v"
        out_file.write_text(code, encoding="utf-8")
        print(code)

    if args.vcd:
        vcd_file = build_dir / "blinky.vcd"
        run_vcd(vcd_file)
        print(f"Wrote simulation waveform to {vcd_file}")


if __name__ == "__main__":
    main()
```

## 3. Dissecting the Generated Verilog {#verilog-dissection}

Running `python blinky.py --verilog` elaborates `Blinky` and invokes Yosys's Verilog backend (`emit_src=False`) to produce `build/blinky.v`. Even if you have never written Verilog before, you can already read every single line below by matching it to the three blocks you just wrote:

```verilog caption="Exact generated Verilog output from apps/0001-blinky-amaranth-to-verilog/blinky.v"
(* top = 1 *)
(* generator = "Amaranth" *)
module blinky(rst, leds, clk);
  reg \$auto$verilog_backend.cc:2542:dump_module$1  = 0;
  input rst;
  wire rst;
  output [5:0] leds;
  wire [5:0] leds;
  input clk;
  wire clk;
  wire \$1 ;
  wire [6:0] \$2 ;
  wire [24:0] \$3 ;
  reg [23:0] \$4 ;
  reg [5:0] \$5 ;
  reg [5:0] pattern = 6'h00;
  reg [23:0] timer = 24'h000000;
  always @(posedge clk)
    timer <= \$4 ;
  always @(posedge clk)
    pattern <= \$5 ;
  assign \$1  = timer == 24'hcdfe5f;
  assign \$2  = pattern + 1'h1;
  assign \$3  = timer + 1'h1;
  assign leds = ~ pattern;
  always @* begin
    if (\$auto$verilog_backend.cc:2542:dump_module$1 ) begin end
    (* full_case = 1 *)
    if (\$1 ) begin
      \$4  = 24'h000000;
    end else begin
      \$4  = \$3 [23:0];
    end
    if (rst) begin
      \$4  = 24'h000000;
    end
  end
  always @* begin
    if (\$auto$verilog_backend.cc:2542:dump_module$1 ) begin end
    \$5  = pattern;
    if (\$1 ) begin
      \$5  = \$2 [5:0];
    end
    if (rst) begin
      \$5  = 6'h00;
    end
  end
endmodule
```

Table: Mapping Amaranth constructs to their generated Verilog equivalents.

| Amaranth Code | Generated Verilog | Hardware Meaning |
| :--- | :--- | :--- |
| `class Blinky` + `leds: Out(6)` | `module blinky(rst, leds, clk);` and `output [5:0] leds;` | Module ports; `[5:0]` is a 6-bit MSB-to-LSB bus |
| `timer = Signal(range(13_500_000))` | `reg [23:0] timer = 24'h000000;` | 24-bit flip-flop bank initialized to hex `0` (`13_499_999` is `24'hcdfe5f`) |
| `m.d.sync += ...` | `always @(posedge clk) timer <= \$4 ;` | Non-blocking (`<=`) latch updating on every rising clock edge |
| `m.d.comb += self.leds.eq(~pattern)` | `assign leds = ~ pattern;` | Continuous combinational wire inversion |
| `with m.If(...)` / `rst` | `always @* begin ... if (rst) ... end` | Combinational next-state mux (`\$4`, `\$5`) feeding the flip-flops |

Notice the crucial Verilog distinction that trips up beginners when writing raw Verilog by hand: inside `always @(posedge clk)` the generated code uses **`<=`** (non-blocking flip-flop assignment), whereas inside `always @*` it uses **`=`** (combinational next-state mux evaluation). Amaranth enforces that split for you automatically through `m.d.sync` and `m.d.comb` while teaching you to spot the pattern in Verilog!

## 4. Mapping Pins with `tangnano20k.cst` {#constraints}

The generated Verilog has three top-level ports: `clk`, `rst`, and `leds[5:0]`. The physical constraints file (`tangnano20k.cst`) binds those logical names to physical pins on the QN88 package:

```text caption="Excerpt from apps/0001-blinky-amaranth-to-verilog/tangnano20k.cst"
IO_LOC "clk" 4;
IO_PORT "clk" IO_TYPE=LVCMOS33 PULL_MODE=UP;

IO_LOC "rst" 88;
IO_PORT "rst" IO_TYPE=LVCMOS33 PULL_MODE=DOWN;

IO_LOC "leds[0]" 15;
IO_PORT "leds[0]" IO_TYPE=LVCMOS33 PULL_MODE=UP DRIVE=8;
```

Notice `rst` on pin `88` (`S1` button) uses `PULL_MODE=DOWN` because pressing `S1` pulls the pin high (`1`), resetting `timer` and `pattern` back to `0` while held.

:::exercise id="ex-0001" title="Interactive Lab: Blinky Domains & Active-Low Polarity" badge="Skill Practice • Tight Feedback Loop"
Fill in the missing Amaranth domain names and bitwise operator so `pattern` updates on the clock edge and `leds` lights active-low:

```python
with m.If(timer == self.half_period - 1):
    m.d.{{blank:sync|Which domain holds clocked registers?|???|4}} += [
        timer.eq(0),
        pattern.eq(pattern + 1),
    ]
with m.Else():
    m.d.sync += timer.eq(timer + 1)

m.d.{{blank:comb|Which domain wires continuous logic gates?|???|4}} += self.leds.eq({{blank:~|Which Python bitwise operator inverts all bits?|?|1}}pattern)
```

:::prompts
hint: "Use `sync` for clocked flip-flops, `comb` for continuous wires, and `~` for bitwise inversion."
success: "Verified! Clocked registers live in `m.d.sync`, continuous inversion lives in `m.d.comb`, and `~pattern` maps to `assign leds = ~ pattern;` in Verilog."
:::
:::

:::verify id="verify-0001" title="Verification Lab: Simulate, Lint, and Flash to Tang Nano 20K" badge="Terminal Gate"
First, verify the simulation unit tests, linter, and Verilog generation inside your Python virtual environment:

```bash
.venv/bin/pytest -v apps/0001-blinky-amaranth-to-verilog/
.venv/bin/ruff check apps/0001-blinky-amaranth-to-verilog/
.venv/bin/python apps/0001-blinky-amaranth-to-verilog/blinky.py --verilog --vcd
```

Next, to synthesize and flash onto your breadboarded Tang Nano 20K on macOS Apple Silicon (`arm64`), install the YosysHQ **OSS CAD Suite** (`oss-cad-suite-darwin-arm64-*.tgz` from the [OSS CAD Suite Releases](https://github.com/YosysHQ/oss-cad-suite-build/releases)), clear Gatekeeper quarantine, add its `bin/` directory to your `PATH`, and run `make flash`:

```bash
# Example after extracting oss-cad-suite to ~/oss-cad-suite:
xattr -dr com.apple.quarantine ~/oss-cad-suite
export PATH="$HOME/oss-cad-suite/bin:$PATH"
make -C apps/0001-blinky-amaranth-to-verilog flash
```

- [ ] All 4 tests in `test_blinky.py` pass with zero errors.
- [ ] `ruff check` reports `All checks passed!`.
- [ ] `blinky.py --verilog` emits `module blinky(rst, leds, clk);` into `build/blinky.v`.
- [ ] On the breadboarded Tang Nano 20K, the 6 LEDs count upward in binary every $0.5\text{ s}$, and holding `S1` (`pin 88`) holds `rst` high and turns all LEDs off.
:::

:::quiz id="quiz-0001" title="Retrieval Practice: Amaranth & Generated Verilog" badge="3 Questions • Equal-Length Options"
- question: "In Amaranth HDL, what hardware circuit does an assignment inside `m.d.sync` synthesize into compared with `m.d.comb`?"
  wrong_hint: "Compare edge-triggered flip-flops against unclocked combinational gates."
  options:
    - letter: "A"
      text: "Flip-flops updating synchronously on every rising clock"
      correct: true
      explain: "Statements in `m.d.sync` become clocked D flip-flops (`always @(posedge clk)`), updating together on the rising edge."
    - letter: "B"
      text: "Combinational gates changing immediately without waiting clocks"
      correct: false
      explain: "That describes `m.d.comb`, not `m.d.sync`."
    - letter: "C"
      text: "Sequential Python instructions executed inside one thread"
      correct: false
      explain: "Python elaboration builds a parallel hardware netlist; the FPGA does not execute Python at runtime."
    - letter: "D"
      text: "External pull-up resistors driving the output header"
      correct: false
      explain: "Pull resistors are configured in `.cst` pin attributes, not `m.d.sync`."
- question: "On the Tang Nano 20K, why does `Blinky` drive `self.leds.eq(~pattern)` instead of `self.leds.eq(pattern)`?"
  wrong_hint: "Check how the onboard LED cathodes and anodes are wired on the schematic."
  options:
    - letter: "A"
      text: "The FPGA clock runs backwards on odd cycles"
      correct: false
      explain: "The 27 MHz clock simply triggers rising edges; it does not invert output polarity."
    - letter: "B"
      text: "The six onboard LEDs sink current active-low style"
      correct: true
      explain: "Each LED connects between +3.3 V and an FPGA pin, so driving `0` sinks current and lights the LED."
    - letter: "C"
      text: "Yosys automatically inverts every output port during synthesis"
      correct: false
      explain: "Yosys preserves your exact logic polarity; the inversion comes from `~pattern`."
    - letter: "D"
      text: "Amaranth stores all unsigned counters in one's complement"
      correct: false
      explain: "Amaranth `Signal` arithmetic uses standard binary/two's-complement representation."
- question: "In the generated Verilog from `Blinky`, what does `always @(posedge clk)` followed by `timer <= $4;` express?"
  wrong_hint: "Think about what `posedge clk` and non-blocking `<=` mean in digital logic."
  options:
    - letter: "A"
      text: "A continuous wire connecting the crystal to pins"
      correct: false
      explain: "Continuous wires use `assign`, whereas `always @(posedge clk)` describes clocked storage."
    - letter: "B"
      text: "A software while-loop polling the button state repeatedly"
      correct: false
      explain: "`always @(posedge clk)` models hardware flip-flops triggered by clock edges, not a CPU loop."
    - letter: "C"
      text: "A combinational mux evaluated whenever any input changes"
      correct: false
      explain: "That describes the `always @*` block that computes `$4`, not the `posedge clk` flip-flop."
    - letter: "D"
      text: "A synchronous register latching next-state on clock edges"
      correct: true
      explain: "`always @(posedge clk)` with `<=` describes flip-flops latching `$4` at each rising edge of `clk`."
:::

:::teacher-prompt title="Extend This Lesson with Your Agent"
Once you've inspected `build/blinky.v` or flashed your board, ask your AI teacher:
- *"Can we walk through why `$2` is 7 bits wide (`[6:0]`) and `$3` is 25 bits wide (`[24:0]`) in the generated Verilog?"*
- *"I've flashed Lesson 0001 and confirmed the LEDs count in binary — let's move on to Lesson 0002 (Buttons & Debouncing)!"*
:::
