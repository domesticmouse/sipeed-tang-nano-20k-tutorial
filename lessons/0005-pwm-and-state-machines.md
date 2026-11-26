---
title: "PWM Brightness & Finite State Machines"
page_title: "Lesson 0005: PWM Brightness & Finite State Machines — Tang Nano 20K"
nav_id: "lesson-0005"
badge: "Lesson 0005 • PWM & m.FSM"
subtitle: "Dim onboard LEDs smoothly with an 8-bit sawtooth comparator and choreograph a four-stage breathing envelope using Amaranth's m.FSM state machine."
card:
  title: "**PWM Brightness & Finite State Machines**"
  summary: "Build a reusable PwmGenerator comparator and drive a 4-stage LED breathing envelope with m.FSM, Cat(), and one-hot state LEDs."
---

:::callout title="Recommended Primary Sources"
- **Companion app**: `apps/0005-pwm-and-state-machines/` (`.venv/bin/pytest -v apps/0005-pwm-and-state-machines/`)
- **Primary docs**: [Amaranth HDL Documentation](https://amaranth-lang.org/docs/amaranth/latest/) • [Sipeed Tang Nano 20K Wiki](https://wiki.sipeed.com/hardware/en/tang/tang-nano-20k/nano-20k.html)
- **Course references**: [Lesson 0004: Dissecting Button & Debouncer Verilog](0004-buttons-generated-verilog.md), [Glossary](../reference/GLOSSARY.md), and [Tang Nano 20K Pinout & Toolchain Sheet](../reference/tang-nano-20k-pinout.md)
:::

## 1. Sawtooth Comparators & Hardware Envelope Generators {#mental-model}

So far, every LED on our Tang Nano 20K has been strictly binary: full on (`0`) or full off (`1`). FPGA pins are digital—they only output `0 V` or `3.3 V`, with no built-in DAC—yet we can smoothly dim an LED across 256 brightness levels using **Pulse-Width Modulation (PWM)**.

If you have built analog synthesizer circuits, you already know how triangle-core or sawtooth PWM works:

1. **PWM = Sawtooth oscillator + op-amp comparator (`counter < duty`):** A free-running 8-bit register `counter` counts `0, 1, 2, ..., 255` and wraps cleanly back to `0`—a digital **sawtooth ramp** running at $27{,}000{,}000 / 256 \approx 105.47\text{ kHz}$. A combinational comparator asks `counter < duty` continuously. When `duty = 0`, the output stays `0` (`0%` on); when `duty = 128`, it stays `1` for half the ramp (`50%` on); when `duty = 255`, it stays `1` for 255 of every 256 ticks (`99.6%` on). At $105.47\text{ kHz}$, your eyes integrate those pulses into steady, flicker-free brightness.{{sidenote: Notice why we use an 8-bit counter (`0..255`) at 27 MHz: `27 MHz / 256` is roughly `105.5 kHz`, well past human flicker perception and even above audio frequencies.}}
2. **FSM = Clocked envelope sequencer (`m.FSM`):** To make the LEDs breathe smoothly rather than jumping straight to a fixed duty cycle, we build an analog-style **4-stage envelope generator** (`RAMP_UP` → `HOLD_HIGH` → `RAMP_DOWN` → `HOLD_LOW`). In Amaranth, `with m.FSM(...)` turns named stages (`with m.State("RAMP_UP"):`) into a clocked state register plus next-state transition logic (`m.next = ...`).
3. **Moore state indicators:** Each `m.State` drives a 4-bit one-hot `state_leds` bus (`0001`, `0010`, `0100`, `1000`) depending solely on the current state—a classic **Moore machine**—so LEDs `2..5` let you watch the state machine step through every phase in real time while LEDs `0..1` breathe smoothly.

```mermaid caption="Figure 5.1: PwmBreather architecture — 256 Hz step prescaler, 4-state Moore envelope FSM, 105.5 kHz PWM comparator, and active-low LED packing"
flowchart LR
  TMR["step_timer (105,469 ticks ≈ 3.9 ms)"] -->|"step_tick"| FSM["4-State Envelope m.FSM"]
  subgraph STATES["Envelope Cycle"]
    RU["RAMP_UP (state_leds = 0001)"] -->|"brightness == 255"| HH["HOLD_HIGH (state_leds = 0010)"]
    HH -->|"hold_count == 63"| RD["RAMP_DOWN (state_leds = 0100)"]
    RD -->|"brightness == 0"| HL["HOLD_LOW (state_leds = 1000)"]
    HL -->|"hold_count == 63"| RU
  end
  FSM -->|"brightness[7:0]"| PWM["PwmGenerator (counter < duty)"]
  FSM -->|"state_leds[3:0]"| CAT["~Cat(pwm.out, pwm.out, state_leds)"]
  PWM -->|"pwm.out"| CAT
  CAT --> LEDS["leds[5:0] (Pins 15..20)"]
```

## 2. Building `PwmGenerator` and `PwmBreather` Block by Block {#block-walkthrough}

### Block 1: Reusable `PwmGenerator` Sawtooth Comparator

```python caption="PwmGenerator component with parameterized duty width"
class PwmGenerator(wiring.Component):
    def __init__(self, width: int = 8):
        if width < 2:
            raise ValueError("width must be at least 2")
        self.width = width
        super().__init__({"duty": In(width), "out": Out(1)})

    def elaborate(self, platform):
        m = Module()
        counter = Signal(self.width)
        m.d.sync += counter.eq(counter + 1)
        m.d.comb += self.out.eq(counter < self.duty)
        return m
```

- **Dynamic port signatures via `super().__init__({...})`:** Unlike `ButtonDebouncer` whose ports were fixed 1-bit flags, `PwmGenerator` takes a runtime `width` parameter. Passing a signature dictionary (`{"duty": In(width), "out": Out(1)}`) to `super().__init__()` lets us instantiate an 8-bit PWM on hardware or a tiny 2-bit / 4-bit PWM in fast unit tests.
- **Natural binary wraparound:** `counter = Signal(8)` rolls cleanly from `255` back to `0` on `counter + 1`, giving an effortless 256-tick sawtooth period with zero extra reset comparator.
- **Combinational comparator:** `m.d.comb += self.out.eq(counter < self.duty)` continuously compares the sawtooth `counter` against `duty`. When `duty == 0`, `counter < 0` is impossible for an unsigned signal, so `out` stays `0` for all 256 ticks.

### Block 2: Modulation Step Prescaler (`step_timer` & `step_tick`)

```python caption="Deriving a 1-cycle modulation tick every 105,469 clock cycles (~3.91 ms)"
        max_duty = (1 << self.pwm_width) - 1
        brightness = Signal(self.pwm_width)
        step_timer = Signal(range(self.step_cycles))
        step_tick = Signal()
        hold_count = Signal(range(self.hold_steps))
        state_leds = Signal(4)

        m.d.comb += step_tick.eq(step_timer == self.step_cycles - 1)
        with m.If(step_tick):
            m.d.sync += step_timer.eq(0)
        with m.Else():
            m.d.sync += step_timer.eq(step_timer + 1)
```

- **Why a prescaler?** Updating `brightness` at 27 MHz would finish a full fade in 9.5 microseconds—invisible to human eyes. Counting `105_469` ticks produces one `step_tick` pulse every $3.906\text{ ms}$ ($\approx 256\text{ Hz}$).
- Across 256 `RAMP_UP` steps, 64 `HOLD_HIGH` steps, 256 `RAMP_DOWN` steps, and 64 `HOLD_LOW` steps, one complete breath lasts $(256 + 64 + 256 + 64) \times 3.906\text{ ms} \approx 2.50\text{ s}$.
- **Single-cycle combinational strobe:** Writing `m.d.comb += step_tick.eq(step_timer == self.step_cycles - 1)` keeps `step_tick` high for exactly the one clock cycle where `step_timer` hits its terminal value, then resets `step_timer` to `0` on that rising edge.

### Block 3: Four-Stage Envelope with `m.FSM`

```python caption="Four-state breathing envelope inside PwmBreather.elaborate()"
        with m.FSM(init="RAMP_UP"):
            with m.State("RAMP_UP"):
                m.d.comb += state_leds.eq(0b0001)
                with m.If(step_tick):
                    with m.If(brightness == max_duty):
                        m.d.sync += hold_count.eq(0)
                        m.next = "HOLD_HIGH"
                    with m.Else():
                        m.d.sync += brightness.eq(brightness + 1)

            with m.State("HOLD_HIGH"):
                m.d.comb += state_leds.eq(0b0010)
                with m.If(step_tick):
                    with m.If(hold_count == self.hold_steps - 1):
                        m.next = "RAMP_DOWN"
                    with m.Else():
                        m.d.sync += hold_count.eq(hold_count + 1)

            with m.State("RAMP_DOWN"):
                m.d.comb += state_leds.eq(0b0100)
                with m.If(step_tick):
                    with m.If(brightness == 0):
                        m.d.sync += hold_count.eq(0)
                        m.next = "HOLD_LOW"
                    with m.Else():
                        m.d.sync += brightness.eq(brightness - 1)

            with m.State("HOLD_LOW"):
                m.d.comb += state_leds.eq(0b1000)
                with m.If(step_tick):
                    with m.If(hold_count == self.hold_steps - 1):
                        m.next = "RAMP_UP"
                    with m.Else():
                        m.d.sync += hold_count.eq(hold_count + 1)
```

- **`with m.FSM(init="RAMP_UP"):`** allocates a synchronous state register initialized to `"RAMP_UP"` on power-up and whenever `rst` (`S1`) is asserted.
- **`m.next = "HOLD_HIGH"` schedules the next state:** Just like `m.d.sync +=`, assigning `m.next` does **not** jump mid-cycle—the FSM finishes the current cycle in `"RAMP_UP"` and enters `"HOLD_HIGH"` on the next rising clock edge.
- **No accidental latches on `state_leds`:** Every `m.State` drives `m.d.comb += state_leds.eq(...)` unconditionally, making `state_leds` a pure Moore output decoded directly from the current state.
- **Clearing `hold_count` before entering `HOLD_*`:** Resetting `hold_count.eq(0)` on the transition out of `RAMP_UP` and `RAMP_DOWN` guarantees each hold stage starts cleanly at `0`.

### Block 4: Packing Bits with LSB-First `Cat()`

```python caption="Driving two PWM LEDs and four state-indicator LEDs with ~Cat(...)"
        m.d.comb += [
            pwm.duty.eq(brightness),
            self.leds.eq(~Cat(pwm.out, pwm.out, state_leds)),
        ]
        return m
```

- **`Cat(...)` packs LSB-first!** In Amaranth, the **first** argument to `Cat(a, b, c)` sits at bit `0` (the least-significant bit), and each subsequent argument stacks upward toward the MSB:
  - `leds[0]` ← `~pwm.out` (pin `15`)
  - `leds[1]` ← `~pwm.out` (pin `16`)
  - `leds[5:2]` ← `~state_leds` (pins `17..20`)
- Keep this LSB-first ordering in mind: when we inspect the generated Verilog in [Lesson 0006](0006-pwm-fsm-generated-verilog.md), Verilog's `{ ... }` operator flips the order to MSB-first!{{sidenote: Amaranth chose LSB-first order for `Cat(lo, ..., hi)` so bit indices (`0, 1, 2...`) match argument order left-to-right, whereas Verilog `{hi, ..., lo}` matches written binary MSB-to-LSB order.}}

### Complete pwm_fsm.py Listing

```python caption="apps/0005-pwm-and-state-machines/pwm_fsm.py"
import argparse
from pathlib import Path

from amaranth import Cat, Module, Signal
from amaranth.back import verilog
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out
from amaranth.sim import Simulator


class PwmGenerator(wiring.Component):
    def __init__(self, width: int = 8):
        if width < 2:
            raise ValueError("width must be at least 2")
        self.width = width
        super().__init__({"duty": In(width), "out": Out(1)})

    def elaborate(self, platform):
        m = Module()
        counter = Signal(self.width)
        m.d.sync += counter.eq(counter + 1)
        m.d.comb += self.out.eq(counter < self.duty)
        return m


class PwmBreather(wiring.Component):
    leds: Out(6)

    def __init__(
        self,
        pwm_width: int = 8,
        step_cycles: int = 105_469,
        hold_steps: int = 64,
    ):
        if pwm_width < 2:
            raise ValueError("pwm_width must be at least 2")
        if step_cycles < 2:
            raise ValueError("step_cycles must be at least 2")
        if hold_steps < 2:
            raise ValueError("hold_steps must be at least 2")
        self.pwm_width = pwm_width
        self.step_cycles = step_cycles
        self.hold_steps = hold_steps
        super().__init__()

    def elaborate(self, platform):
        m = Module()
        m.submodules.pwm = pwm = PwmGenerator(width=self.pwm_width)

        max_duty = (1 << self.pwm_width) - 1
        brightness = Signal(self.pwm_width)
        step_timer = Signal(range(self.step_cycles))
        step_tick = Signal()
        hold_count = Signal(range(self.hold_steps))
        state_leds = Signal(4)

        m.d.comb += step_tick.eq(step_timer == self.step_cycles - 1)
        with m.If(step_tick):
            m.d.sync += step_timer.eq(0)
        with m.Else():
            m.d.sync += step_timer.eq(step_timer + 1)

        with m.FSM(init="RAMP_UP"):
            with m.State("RAMP_UP"):
                m.d.comb += state_leds.eq(0b0001)
                with m.If(step_tick):
                    with m.If(brightness == max_duty):
                        m.d.sync += hold_count.eq(0)
                        m.next = "HOLD_HIGH"
                    with m.Else():
                        m.d.sync += brightness.eq(brightness + 1)

            with m.State("HOLD_HIGH"):
                m.d.comb += state_leds.eq(0b0010)
                with m.If(step_tick):
                    with m.If(hold_count == self.hold_steps - 1):
                        m.next = "RAMP_DOWN"
                    with m.Else():
                        m.d.sync += hold_count.eq(hold_count + 1)

            with m.State("RAMP_DOWN"):
                m.d.comb += state_leds.eq(0b0100)
                with m.If(step_tick):
                    with m.If(brightness == 0):
                        m.d.sync += hold_count.eq(0)
                        m.next = "HOLD_LOW"
                    with m.Else():
                        m.d.sync += brightness.eq(brightness - 1)

            with m.State("HOLD_LOW"):
                m.d.comb += state_leds.eq(0b1000)
                with m.If(step_tick):
                    with m.If(hold_count == self.hold_steps - 1):
                        m.next = "RAMP_UP"
                    with m.Else():
                        m.d.sync += hold_count.eq(hold_count + 1)

        m.d.comb += [
            pwm.duty.eq(brightness),
            self.leds.eq(~Cat(pwm.out, pwm.out, state_leds)),
        ]
        return m


def emit_verilog(
    pwm_width: int = 8,
    step_cycles: int = 105_469,
    hold_steps: int = 64,
) -> str:
    dut = PwmBreather(
        pwm_width=pwm_width,
        step_cycles=step_cycles,
        hold_steps=hold_steps,
    )
    return verilog.convert(dut, name="pwm_breather", emit_src=False)


def run_vcd(
    output_path: Path,
    pwm_width: int = 3,
    step_cycles: int = 4,
    hold_steps: int = 2,
) -> None:
    dut = PwmBreather(
        pwm_width=pwm_width,
        step_cycles=step_cycles,
        hold_steps=hold_steps,
    )

    async def testbench(ctx):
        for _ in range(120):
            await ctx.tick()

    sim = Simulator(dut)
    sim.add_clock(1 / 27_000_000)
    sim.add_testbench(testbench)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with sim.write_vcd(str(output_path)):
        sim.run()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Tang Nano 20K PWM Breather & FSM in Amaranth HDL"
    )
    parser.add_argument(
        "--verilog", action="store_true", help="Write build/pwm_breather.v and print it"
    )
    parser.add_argument(
        "--vcd",
        action="store_true",
        help="Simulate breathing cycle to build/pwm_breather.vcd",
    )
    parser.add_argument(
        "--pwm-width",
        type=int,
        default=8,
        help="Bit width of the PWM sawtooth counter",
    )
    parser.add_argument(
        "--step-cycles",
        type=int,
        default=105_469,
        help="Clock cycles per brightness/hold step",
    )
    parser.add_argument(
        "--hold-steps",
        type=int,
        default=64,
        help="Number of step ticks spent in HOLD_HIGH and HOLD_LOW",
    )
    args = parser.parse_args()

    build_dir = Path(__file__).parent / "build"
    if args.verilog or not args.vcd:
        code = emit_verilog(
            pwm_width=args.pwm_width,
            step_cycles=args.step_cycles,
            hold_steps=args.hold_steps,
        )
        build_dir.mkdir(parents=True, exist_ok=True)
        out_file = build_dir / "pwm_breather.v"
        out_file.write_text(code, encoding="utf-8")
        print(code)

    if args.vcd:
        vcd_file = build_dir / "pwm_breather.vcd"
        run_vcd(vcd_file)
        print(f"Wrote simulation waveform to {vcd_file}")


if __name__ == "__main__":
    main()
```

## 3. Pin Constraints & Next Steps {#constraints}

This design uses the 27 MHz clock (`pin 4`), synchronous reset button `S1` (`pin 88`), and all six active-low LEDs (`pins 15..20`). Button `S2` is omitted because the breathing envelope runs autonomously:

```text caption="Excerpt from apps/0005-pwm-and-state-machines/tangnano20k.cst"
IO_LOC "clk" 4;
IO_PORT "clk" IO_TYPE=LVCMOS33 PULL_MODE=UP;

IO_LOC "rst" 88;
IO_PORT "rst" IO_TYPE=LVCMOS33 PULL_MODE=DOWN;

IO_LOC "leds[0]" 15;
IO_PORT "leds[0]" IO_TYPE=LVCMOS33 PULL_MODE=UP DRIVE=8;
```

:::callout title="Ready to Dissect the Generated FSM Verilog?"
Running `pwm_fsm.py --verilog` lowers `m.FSM`, `Cat(...)`, and `counter < self.duty` into `casez (fsm_state)` decoders, `{ state_leds, out, out }`, and logical `! duty` checks. Continue to [Lesson 0006: Dissecting PWM & FSM Verilog](0006-pwm-fsm-generated-verilog.md) to read every line of that generated hardware!
:::

:::exercise id="ex-0005" title="Interactive Lab: PWM Comparator, m.FSM Transitions & Cat()" badge="Skill Practice • Tight Feedback Loop"
Complete the Amaranth snippet below to build the sawtooth PWM comparator, transition the FSM to `"HOLD_HIGH"`, and pack `pwm.out` and `state_leds` into active-low `leds`:

```python
m.d.comb += self.out.eq({{blank:counter < self.duty|Compare sawtooth counter against duty threshold?|?????????????????|17}})

with m.{{blank:FSM|Amaranth context manager for finite state machines?|???|3}}(init="RAMP_UP"):
    with m.State("RAMP_UP"):
        m.d.comb += state_leds.eq(0b0001)
        with m.If(step_tick & (brightness == max_duty)):
            m.d.sync += hold_count.eq(0)
            m.{{blank:next|Amaranth attribute scheduling the next state?|????|4}} = "HOLD_HIGH"

m.d.comb += self.leds.eq(~{{blank:Cat|Amaranth helper packing signals LSB-first?|???|3}}(pwm.out, pwm.out, state_leds))
```

:::prompts
hint: "Use `counter < self.duty` for the comparator, `m.FSM(...)` for the state machine, `m.next = \"HOLD_HIGH\"` for state transitions, and `Cat(...)` for LSB-first concatenation."
success: "Verified! You now have the core Amaranth idioms for PWM duty comparators, Moore/Mealy FSMs, and bit packing."
:::
:::

:::verify id="verify-0005" title="Verification Lab: Simulate PWM Duty, FSM States, Lint, and Flash" badge="Terminal Gate"
Run the 6 simulation unit tests, lint with `ruff`, and generate both `build/pwm_breather.v` and a fast breathing waveform (`build/pwm_breather.vcd`):

```bash
.venv/bin/pytest -v apps/0005-pwm-and-state-machines/
.venv/bin/ruff check apps/0005-pwm-and-state-machines/
.venv/bin/python apps/0005-pwm-and-state-machines/pwm_fsm.py --verilog --vcd
```

If you have OSS CAD Suite installed on macOS, synthesize and flash the bitstream onto your Tang Nano 20K:

```bash
export PATH="$HOME/oss-cad-suite/bin:$PATH"
make -C apps/0005-pwm-and-state-machines flash
```

- [ ] All 6 tests in `test_pwm_fsm.py` pass (duty ratios `0/8/15`, 4-state traversal, peak/zero duty in `HOLD_HIGH`/`HOLD_LOW`, sync reset, parameter validation, and Verilog generation).
- [ ] `ruff check` reports `All checks passed!`.
- [ ] On hardware, LEDs `0–1` breathe smoothly over a 2.5-second cycle while LEDs `2–5` step sequentially through the four envelope states, and pressing `S1` (`pin 88`) restarts at `RAMP_UP`.
:::

:::quiz id="quiz-0005" title="Retrieval Practice: PWM Comparators, m.FSM & Cat()" badge="3 Questions • Equal-Length Options"
- question: "Why does an 8-bit `PwmGenerator` clocked at 27 MHz produce smooth dimming without visible LED flicker?"
  wrong_hint: "Divide 27 MHz by 256 sawtooth steps and compare that frequency to human flicker fusion."
  options:
    - letter: "A"
      text: "The 105.5 kHz PWM carrier switches faster than human vision"
      correct: true
      explain: "An 8-bit counter overflows every 256 ticks (27 MHz / 256 ≈ 105.5 kHz), far faster than the eye can track individual pulses."
    - letter: "B"
      text: "Amaranth automatically inserts an analog RC low-pass filter on pins"
      correct: false
      explain: "FPGA outputs stay purely digital square waves; your eyes and the LED phosphor visually integrate the duty ratio."
    - letter: "C"
      text: "The sawtooth counter pauses for one millisecond between every pulse"
      correct: false
      explain: "`counter.eq(counter + 1)` increments continuously on every 27 MHz rising clock edge without pausing."
    - letter: "D"
      text: "Active-low Tang Nano LEDs latch brightness internally across clock cycles"
      correct: false
      explain: "Active-low just means `0` turns the LED on; brightness comes from the ratio of `0` time to `1` time."
- question: "Inside `with m.FSM(init=\"RAMP_UP\"):`, what happens on the clock edge when `m.next = \"HOLD_HIGH\"` executes?"
  wrong_hint: "Remember that FSM state registers update synchronously on `m.d.sync` clock edges."
  options:
    - letter: "A"
      text: "Both `RAMP_UP` and `HOLD_HIGH` stay active for two extra ticks"
      correct: false
      explain: "A single-hot/encoded state register holds exactly one state per clock cycle—two states are never active at once."
    - letter: "B"
      text: "The FSM transitions into `HOLD_HIGH` on the next rising edge"
      correct: true
      explain: "`m.next = ...` schedules the next value of the synchronous `fsm_state` register, taking effect on the next `posedge clk`."
    - letter: "C"
      text: "Amaranth switches to `HOLD_HIGH` immediately inside the same clock cycle"
      correct: false
      explain: "State transitions are synchronous (`m.d.sync`), so `state_leds` remains `0b0001` until the next rising clock edge."
    - letter: "D"
      text: "The synchronous reset signal clears `brightness` back down to zero"
      correct: false
      explain: "Transitioning to `HOLD_HIGH` leaves `brightness` at `max_duty` while resetting only `hold_count`."
- question: "In `self.leds.eq(~Cat(pwm.out, pwm.out, state_leds))`, which physical bits receive `state_leds` (where `state_leds` is 4 bits wide)?"
  wrong_hint: "Recall whether Amaranth's `Cat()` packs arguments starting from bit 0 (LSB) or the highest bit (MSB)."
  options:
    - letter: "A"
      text: "Lower `leds[0..3]` carry `state_leds` because `Cat` places final arguments lowest"
      correct: false
      explain: "`Cat()` packs its first arguments at the lowest indices (`leds[0]` and `leds[1]`), pushing later arguments upward."
    - letter: "B"
      text: "Only `leds[5]` gets `state_leds` because Amaranth truncates all extra bits"
      correct: false
      explain: "`Cat(1-bit, 1-bit, 4-bit)` totals 6 bits, matching `leds: Out(6)` with zero truncation."
    - letter: "C"
      text: "Upper `leds[2..5]` receive inverted `state_leds` because `Cat` packs bits LSB-first"
      correct: true
      explain: "`Cat` places the two 1-bit `pwm.out` signals in bits `[0]` and `[1]` and `state_leds` in bits `[5:2]`, then `~` inverts all 6 bits."
    - letter: "D"
      text: "Even pins `leds[0]`, `leds[2]`, and `leds[4]` interleave `state_leds` with `pwm.out`"
      correct: false
      explain: "`Cat` concatenates contiguous slices back-to-back rather than interleaving individual bits."
:::

:::teacher-prompt title="Extend This Lesson with Your Agent"
Once your simulation and bitstream pass, continue to [Lesson 0006: Dissecting PWM & FSM Verilog](0006-pwm-fsm-generated-verilog.md) or ask your AI teacher:
- *"Can we inspect `build/pwm_breather.vcd` or explain why gamma correction would make LED dimming look even more linear?"*
- *"I've verified Lesson 0005 — let's dissect `pwm_breather.v` in Lesson 0006!"*
:::
