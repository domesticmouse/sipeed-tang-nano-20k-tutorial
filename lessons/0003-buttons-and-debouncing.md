---
title: "Buttons, Synchronizers & Debouncing"
page_title: "Lesson 0003: Buttons, Synchronizers & Debouncing — Tang Nano 20K"
nav_id: "lesson-0003"
badge: "Lesson 0003 • Mechanical Switches & Metastability"
subtitle: "Tame noisy mechanical buttons on the Tang Nano 20K with a 2-flop metastability synchronizer, counter-based debouncer, and rising-edge detector in Amaranth HDL."
card:
  title: "**Buttons, Synchronizers & Debouncing**"
  summary: "Synchronize asynchronous button S2, filter out 10 ms of contact bounce, and emit clean 1-cycle trigger pulses to count presses on the LEDs."
---

:::callout title="Recommended Primary Sources"
- **Companion app**: `apps/0003-buttons-and-debouncing/` (`.venv/bin/pytest -v apps/0003-buttons-and-debouncing/`)
- **Primary docs**: [Amaranth HDL Documentation](https://amaranth-lang.org/docs/amaranth/latest/) • [Sipeed Tang Nano 20K Wiki](https://wiki.sipeed.com/hardware/en/tang/tang-nano-20k/nano-20k.html)
- **Course references**: [Lesson 0002: Dissecting Generated Verilog](0002-dissecting-generated-verilog.md), [Glossary](../reference/GLOSSARY.md), and [Tang Nano 20K Pinout & Toolchain Sheet](../reference/tang-nano-20k-pinout.md)
:::

## 1. Why Real Switches Break Naive Digital Logic {#mental-model}

In [Lesson 0001](0001-blinky-amaranth-to-verilog.md), button `S1` (pin `88`) drove our synchronous `rst` input directly. That worked fine for reset: if a finger press bounces five times before settling, resetting a zeroed counter five times still leaves it at `0`.

Wire button `S2` (pin `87`) straight to a counter increment, though, and pressing `S2` once makes the LEDs jump by 4, 9, or 17! Real mechanical tactile switches collide with two physical realities the instant they enter a 27 MHz FPGA:

1. **Metastability (unclocked fingers vs. 27 MHz edges):** Your finger moves whenever it wants, completely asynchronous to the 27 MHz crystal. If `S2`'s voltage is mid-transition right at the rising clock edge, a single input flip-flop can stall halfway between `0` and `1`—just like a comparator hovering near threshold before snapping randomly—causing downstream logic to disagree on what value it saw. Passing `raw` through **two cascaded flip-flops** (`sync_0` → `sync_1`) gives any metastable wobble one full $37\text{ ns}$ clock period to resolve before any logic reads `sync_1`.
2. **Contact bounce (spring chatter):** Inside a tactile switch, tiny metal springs physically bounce apart and slap back together for roughly $1\text{--}5\text{ ms}$ on every press and release. At 27 MHz, $5\text{ ms}$ is $135{,}000$ clock ticks! A stability counter requiring `sync_1` to hold steady for $270{,}000$ ticks ($10\text{ ms}$) ignores every short bounce and accepts a transition only once the metal has settled.{{sidenote: Why $270{,}000$? At $27{,}000{,}000\text{ Hz}$, one tick is $37.04\text{ ns}$, so $270{,}000$ ticks equals $0.01\text{ s}$ ($10\text{ ms}$)—long enough to swallow switch chatter, short enough to feel instant to a human finger.}}
3. **Level vs. edge (gate-to-trigger):** Even after debouncing, `stable` stays `1` for hundreds of milliseconds while you hold `S2` down. If you incremented `count` whenever `stable == 1`, the counter would sprint at 27 MHz! Comparing `stable` against a 1-cycle-delayed copy (`prev_stable`) builds an analog-style **gate-to-trigger** converter: `pressed = stable & ~prev_stable` fires for **one clock tick** per press.

```mermaid caption="Figure 3.1: ButtonCounter pipeline — 2-flop sync, 10 ms stability filter, gate-to-trigger, and active-low LED counter"
flowchart LR
  S2["S2 Button (Pin 87)"] --> F1["sync_0 (m.d.sync)"]
  F1 --> F2["sync_1 (m.d.sync)"]
  F2 -->|"differs from stable"| CNT["counter[18:0] (10 ms window)"]
  CNT -->|"270,000 ticks steady"| STB["stable (m.d.sync)"]
  STB --> PREV["prev_stable (m.d.sync)"]
  STB --> EDGE["pressed = stable & ~prev_stable"]
  PREV --> EDGE
  EDGE -->|"1-tick strobe"| ACC["count[5:0] (m.d.sync)"]
  ACC --> INV["~count (m.d.comb)"]
  INV --> LEDS["leds[5:0] (Pins 15..20)"]
  S1["S1 rst (Pin 88)"] -.->|"resets sync flops"| STB
```

## 2. Building `ButtonDebouncer` and `ButtonCounter` Block by Block {#block-walkthrough}

Instead of cramming everything into one giant `elaborate()`, we separate the reusable switch conditioner (`ButtonDebouncer`) from the LED counter (`ButtonCounter`) and compose them with `m.submodules`.

### Block 1: Two-Flop Metastability Synchronizer

```python caption="Port signature and 2-flop synchronizer inside ButtonDebouncer"
class ButtonDebouncer(wiring.Component):
    raw: In(1)
    level: Out(1)
    pressed: Out(1)

    def __init__(self, debounce_cycles: int = 270_000):
        if debounce_cycles < 2:
            raise ValueError("debounce_cycles must be at least 2")
        self.debounce_cycles = debounce_cycles
        super().__init__()

    def elaborate(self, platform):
        m = Module()

        sync_0 = Signal()
        sync_1 = Signal()
        m.d.sync += [
            sync_0.eq(self.raw),
            sync_1.eq(sync_0),
        ]
```

- `raw: In(1)` is our first input port (`In(1)` is a 1-bit incoming pin; `Out(1)` emits `level` and `pressed`).
- Why require `debounce_cycles >= 2`? A counter `Signal(range(1))` has zero bits (`0..0`), which leaves no room to count ticks. Requiring at least `2` keeps tests fast (`debounce_cycles=4`) while guaranteeing a valid register width.
- Notice `sync_0.eq(self.raw)` and `sync_1.eq(sync_0)` are both inside `m.d.sync`. Because synchronous flip-flops sample simultaneously at the rising edge, `sync_1` always lags `sync_0` by exactly one clock cycle—turning `self.raw` into a clean, glitch-free signal before the debounce counter ever touches it.{{sidenote: In larger multi-clock designs, Amaranth also provides `amaranth.lib.cdc.FFSynchronizer` in the standard library. Writing the two `Signal()` flip-flops explicitly here lets you see every wire when we dissect the Verilog in Lesson 0004.}}

### Block 2: Counter-Based Stability Filter

```python caption="Stability timer requiring debounce_cycles consecutive matching ticks"
        stable = Signal()
        counter = Signal(range(self.debounce_cycles))

        with m.If(sync_1 == stable):
            m.d.sync += counter.eq(0)
        with m.Else():
            with m.If(counter == self.debounce_cycles - 1):
                m.d.sync += [
                    stable.eq(sync_1),
                    counter.eq(0),
                ]
            with m.Else():
                m.d.sync += counter.eq(counter + 1)
```

- Think of `counter` as a leaky timer watching whether `sync_1` disagrees with `stable`:
  - **Whenever `sync_1 == stable`:** the button hasn't changed (or bounced right back to its old state), so `counter` resets immediately to `0`. Every chatter spike restarts the timer from scratch.
  - **Whenever `sync_1 != stable`:** `counter` counts up `0, 1, 2, ..., self.debounce_cycles - 1`. Only after reaching `self.debounce_cycles - 1` uninterrupted does `stable` snapshot `sync_1` and reset `counter` to `0`.
- For `debounce_cycles = 270_000`, `Signal(range(270_000))` allocates a 19-bit register ($2^{18} = 262{,}144 < 270{,}000 \le 524{,}288 = 2^{19}$). Notice the same symmetry filters **both** pressing (`0 -> 1`) and releasing (`1 -> 0`).

### Block 3: Rising-Edge Detector (Gate-to-Trigger)

```python caption="One-cycle rising-edge detector driving level and pressed outputs"
        prev_stable = Signal()
        m.d.sync += prev_stable.eq(stable)

        m.d.comb += [
            self.level.eq(stable),
            self.pressed.eq(stable & ~prev_stable),
        ]
        return m
```

- `prev_stable` holds the value `stable` had on the **previous** clock cycle.
- On the exact clock cycle `stable` transitions from `0` to `1`, `stable` is `1` while `prev_stable` is still `0`, so `stable & ~prev_stable` evaluates to `1` immediately in `m.d.comb`.
- On the very next clock edge, `prev_stable` updates to `1`, dropping `pressed` back to `0` even if you keep holding `S2` down for ten seconds. When you release `S2` (`stable` drops `1 -> 0`), `stable & ~prev_stable` evaluates `0 & 1 == 0`, so release never triggers a false count.

### Block 4: Wiring Submodules in `ButtonCounter`

```python caption="Top-level ButtonCounter composing ButtonDebouncer via m.submodules"
class ButtonCounter(wiring.Component):
    s2: In(1)
    leds: Out(6)

    def __init__(self, debounce_cycles: int = 270_000):
        if debounce_cycles < 2:
            raise ValueError("debounce_cycles must be at least 2")
        self.debounce_cycles = debounce_cycles
        super().__init__()

    def elaborate(self, platform):
        m = Module()
        m.submodules.debouncer = debouncer = ButtonDebouncer(
            debounce_cycles=self.debounce_cycles
        )
        count = Signal(6)

        m.d.comb += debouncer.raw.eq(self.s2)

        with m.If(debouncer.pressed):
            m.d.sync += count.eq(count + 1)

        m.d.comb += self.leds.eq(~count)
        return m
```

- `m.submodules.debouncer = debouncer = ButtonDebouncer(...)` instantiates our debouncer as a named hardware submodule inside `ButtonCounter`. Both modules automatically share the default `sync` clock (`clk`) and reset (`rst`).
- `m.d.comb += debouncer.raw.eq(self.s2)` solders pin `s2` straight into the debouncer's `raw` input.
- Because `debouncer.pressed` is high for a single tick per button press, `with m.If(debouncer.pressed): m.d.sync += count.eq(count + 1)` increments the 6-bit LED pattern cleanly once per press, and `self.leds.eq(~count)` keeps the Tang Nano 20K's active-low LED polarity intact.

### Complete buttons.py Listing

```python caption="apps/0003-buttons-and-debouncing/buttons.py"
import argparse
from pathlib import Path

from amaranth import Module, Signal
from amaranth.back import verilog
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out
from amaranth.sim import Simulator


class ButtonDebouncer(wiring.Component):
    raw: In(1)
    level: Out(1)
    pressed: Out(1)

    def __init__(self, debounce_cycles: int = 270_000):
        if debounce_cycles < 2:
            raise ValueError("debounce_cycles must be at least 2")
        self.debounce_cycles = debounce_cycles
        super().__init__()

    def elaborate(self, platform):
        m = Module()

        sync_0 = Signal()
        sync_1 = Signal()
        m.d.sync += [
            sync_0.eq(self.raw),
            sync_1.eq(sync_0),
        ]

        stable = Signal()
        counter = Signal(range(self.debounce_cycles))

        with m.If(sync_1 == stable):
            m.d.sync += counter.eq(0)
        with m.Else():
            with m.If(counter == self.debounce_cycles - 1):
                m.d.sync += [
                    stable.eq(sync_1),
                    counter.eq(0),
                ]
            with m.Else():
                m.d.sync += counter.eq(counter + 1)

        prev_stable = Signal()
        m.d.sync += prev_stable.eq(stable)

        m.d.comb += [
            self.level.eq(stable),
            self.pressed.eq(stable & ~prev_stable),
        ]
        return m


class ButtonCounter(wiring.Component):
    s2: In(1)
    leds: Out(6)

    def __init__(self, debounce_cycles: int = 270_000):
        if debounce_cycles < 2:
            raise ValueError("debounce_cycles must be at least 2")
        self.debounce_cycles = debounce_cycles
        super().__init__()

    def elaborate(self, platform):
        m = Module()
        m.submodules.debouncer = debouncer = ButtonDebouncer(
            debounce_cycles=self.debounce_cycles
        )
        count = Signal(6)

        m.d.comb += debouncer.raw.eq(self.s2)

        with m.If(debouncer.pressed):
            m.d.sync += count.eq(count + 1)

        m.d.comb += self.leds.eq(~count)
        return m


def emit_verilog(debounce_cycles: int = 270_000) -> str:
    dut = ButtonCounter(debounce_cycles=debounce_cycles)
    return verilog.convert(dut, name="button_counter", emit_src=False)


def run_vcd(output_path: Path, debounce_cycles: int = 4) -> None:
    dut = ButtonCounter(debounce_cycles=debounce_cycles)

    async def testbench(ctx):
        sequence = [
            0, 0,
            1, 0, 1, 1, 0,
            1, 1, 1, 1, 1, 1, 1, 1,
            0, 1, 0, 0, 0, 0, 0, 0, 0,
            1, 1, 1, 1, 1, 1, 1, 1,
            0, 0,
        ]
        for level in sequence:
            ctx.set(dut.s2, level)
            await ctx.tick()

    sim = Simulator(dut)
    sim.add_clock(1 / 27_000_000)
    sim.add_testbench(testbench)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with sim.write_vcd(str(output_path)):
        sim.run()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Tang Nano 20K Debounced Button Counter in Amaranth HDL"
    )
    parser.add_argument(
        "--verilog", action="store_true", help="Write build/buttons.v and print it"
    )
    parser.add_argument(
        "--vcd", action="store_true", help="Simulate button bounce to build/buttons.vcd"
    )
    parser.add_argument(
        "--debounce-cycles",
        type=int,
        default=270_000,
        help="Clock cycles required for a stable button transition",
    )
    args = parser.parse_args()

    build_dir = Path(__file__).parent / "build"
    if args.verilog or not args.vcd:
        code = emit_verilog(debounce_cycles=args.debounce_cycles)
        build_dir.mkdir(parents=True, exist_ok=True)
        out_file = build_dir / "buttons.v"
        out_file.write_text(code, encoding="utf-8")
        print(code)

    if args.vcd:
        vcd_file = build_dir / "buttons.vcd"
        run_vcd(vcd_file)
        print(f"Wrote simulation waveform to {vcd_file}")


if __name__ == "__main__":
    main()
```

## 3. Mapping `S1` and `S2` in `tangnano20k.cst` {#constraints}

Button `S2` sits on package pin `87` right beside `S1` on pin `88`. Both tactile switches connect their pin to $+3.3\text{ V}$ when pressed, so both require `PULL_MODE=DOWN` to idle cleanly at logic `0` while released:

```text caption="Excerpt from apps/0003-buttons-and-debouncing/tangnano20k.cst"
IO_LOC "clk" 4;
IO_PORT "clk" IO_TYPE=LVCMOS33 PULL_MODE=UP;

IO_LOC "rst" 88;
IO_PORT "rst" IO_TYPE=LVCMOS33 PULL_MODE=DOWN;

IO_LOC "s2" 87;
IO_PORT "s2" IO_TYPE=LVCMOS33 PULL_MODE=DOWN;

IO_LOC "leds[0]" 15;
IO_PORT "leds[0]" IO_TYPE=LVCMOS33 PULL_MODE=UP DRIVE=8;
```

:::callout title="Ready to Read the Multi-Module Verilog?"
Running `buttons.py --verilog` emits **two** Verilog modules (`button_counter` and `\button_counter.debouncer `) into `build/buttons.v`, complete with named port connections and nested muxes. Head straight to [Lesson 0004: Dissecting Button & Debouncer Verilog](0004-buttons-generated-verilog.md) to trace every line of that generated hardware!
:::

:::exercise id="ex-0003" title="Interactive Lab: Synchronizer, Debounce Threshold & Edge Pulse" badge="Skill Practice • Tight Feedback Loop"
Fill in the missing signals and submodule hookup so `ButtonDebouncer` synchronizes `raw` across two flip-flops, detects a rising edge without counting held presses, and plugs into `ButtonCounter`:

```python
sync_0 = Signal()
sync_1 = Signal()
m.d.sync += [
    sync_0.eq(self.raw),
    sync_1.eq({{blank:sync_0|First synchronizer flip-flop feeding sync_1?|??????|6}}),
]

with m.If(counter == {{blank:self.debounce_cycles - 1|Last valid counter index before rolling stable?|self.debounce_cycles - 1|23}}):
    m.d.sync += [
        stable.eq(sync_1),
        counter.eq(0),
    ]

m.d.comb += self.pressed.eq(stable & {{blank:~prev_stable|Invert prev_stable for a 0 -> 1 rising-edge pulse?|????????????|12}})
m.{{blank:submodules|Amaranth Module attribute holding child components?|??????????|10}}.debouncer = debouncer = ButtonDebouncer()
```

:::prompts
hint: "Feed `sync_0` into `sync_1`, compare `counter` against `self.debounce_cycles - 1`, mask `stable` with `~prev_stable`, and attach child components on `m.submodules`."
success: "Verified! Two-stage synchronization (`sync_0` -> `sync_1`), a `debounce_cycles - 1` counter check, `stable & ~prev_stable`, and `m.submodules` are the core building blocks for any FPGA switch input."
:::
:::

:::verify id="verify-0003" title="Verification Lab: Simulate Bounce Rejection, Lint, and Flash" badge="Terminal Gate"
Run the 6 simulation unit tests, lint with `ruff`, and emit both `build/buttons.v` and a bounce-test waveform (`build/buttons.vcd`):

```bash
.venv/bin/pytest -v apps/0003-buttons-and-debouncing/
.venv/bin/ruff check apps/0003-buttons-and-debouncing/
.venv/bin/python apps/0003-buttons-and-debouncing/buttons.py --verilog --vcd
```

If you have OSS CAD Suite installed on macOS, flash the design to your breadboarded Tang Nano 20K and test both buttons physically:

```bash
export PATH="$HOME/oss-cad-suite/bin:$PATH"
make -C apps/0003-buttons-and-debouncing flash
```

- [ ] All 6 tests in `test_buttons.py` pass (bounce rejection, 1-cycle `pressed` strobe, chatter-proof counting, and Verilog generation).
- [ ] `ruff check` reports `All checks passed!`.
- [ ] On hardware, each press of `S2` (`pin 87`) increments the 6-bit binary LED pattern by **exactly one**, and pressing `S1` (`pin 88`) resets all LEDs back off.
:::

:::quiz id="quiz-0003" title="Retrieval Practice: Synchronizers, Debouncing & Edge Pulses" badge="3 Questions • Equal-Length Options"
- question: "Why does `ButtonDebouncer` pass `self.raw` through two flip-flops (`sync_0` then `sync_1`) before reading it?"
  wrong_hint: "Think about what happens when an asynchronous button edge hits a 27 MHz flip-flop mid-transition."
  options:
    - letter: "A"
      text: "Two flip-flops give metastable voltages one full cycle to settle"
      correct: true
      explain: "An asynchronous button transition can violate setup/hold timing on `sync_0`; waiting one clock cycle for `sync_1` lets any metastable mid-rail voltage resolve cleanly."
    - letter: "B"
      text: "Mechanical switch contacts always bounce exactly twice per button press"
      correct: false
      explain: "Switch bounce can last millions of nanoseconds and oscillate many times; the 2-flop synchronizer solves metastability, while `counter` filters bounce."
    - letter: "C"
      text: "Two stages double the 27 MHz clock into 54 MHz"
      correct: false
      explain: "Flip-flops sample at the existing 27 MHz clock rate without multiplying frequency (that takes a PLL)."
    - letter: "D"
      text: "Amaranth requires two registers before inverting any active-low LED pin"
      correct: false
      explain: "LED inversion (`~count`) is purely combinational and needs no synchronizer; only asynchronous external inputs like `S2` need synchronization."
- question: "Why does `ButtonDebouncer` include `self.pressed.eq(stable & ~prev_stable)` instead of incrementing `count` whenever `stable` is `1`?"
  wrong_hint: "Compare holding a button down for 500 milliseconds against counting at 27 MHz."
  options:
    - letter: "A"
      text: "Bitwise inversion slows the counter down by half a second"
      correct: false
      explain: "`~prev_stable` takes nanoseconds in combinational logic and acts as a 1-cycle edge mask, not a time delay."
    - letter: "B"
      text: "Rising-edge detection fires one clock pulse instead of counting continuously"
      correct: true
      explain: "Because `stable` stays `1` the entire time `S2` is held, `stable & ~prev_stable` turns that long gate into a single 1-clock-cycle trigger."
    - letter: "C"
      text: "Button S2 drives pin 87 low whenever held down firmly"
      correct: false
      explain: "Button `S2` is active-high with `PULL_MODE=DOWN`, so holding it drives pin 87 high (`1`)."
    - letter: "D"
      text: "Submodules in Amaranth can only transfer one bit per second"
      correct: false
      explain: "Submodule wires run at full fabric speed on every 27 MHz tick; the edge detector prevents multi-million-counts per press."
- question: "In `ButtonDebouncer`, what happens to `counter` if a mechanical bounce toggles `sync_1` back to match `stable` before `270_000` ticks elapse?"
  wrong_hint: "Check the `with m.If(sync_1 == stable):` branch inside `ButtonDebouncer.elaborate()`."
  options:
    - letter: "A"
      text: "The count register increments anyway because `prev_stable` already flipped high"
      correct: false
      explain: "`stable` (and therefore `prev_stable` and `pressed`) does not change until `counter` reaches `debounce_cycles - 1`."
    - letter: "B"
      text: "Yosys removes the counter during elaboration and outputs raw `sync_1`"
      correct: false
      explain: "The stability counter is synthesized into real flip-flops and comparators—it is never optimized away."
    - letter: "C"
      text: "The counter resets to zero and waits for steady input"
      correct: true
      explain: "Whenever `sync_1 == stable`, `m.d.sync += counter.eq(0)` clears the counter so only an uninterrupted `270_000`-tick change updates `stable`."
    - letter: "D"
      text: "The chip asserts synchronous `rst` across every register in hardware"
      correct: false
      explain: "`rst` comes only from button `S1` (pin 88); `counter` resets itself locally via `counter.eq(0)`."
:::

:::teacher-prompt title="Extend This Lesson with Your Agent"
Once `S2` increments your LEDs cleanly in simulation or on hardware, move on to [Lesson 0004: Dissecting Button & Debouncer Verilog](0004-buttons-generated-verilog.md) or ask your AI teacher:
- *"Can we inspect `build/buttons.vcd` together and trace how `sync_0`, `sync_1`, `counter`, `stable`, and `pressed` line up cycle by cycle?"*
- *"I've verified Lesson 0003 — let's open `buttons.v` in Lesson 0004 and dissect multi-module Verilog!"*
:::
