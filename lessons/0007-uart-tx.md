---
title: "UART Transmitter: Baud Ticks & Shift Registers"
page_title: "Lesson 0007: UART Transmitter in Amaranth HDL — Tang Nano 20K"
nav_id: "lesson-0007"
badge: "Lesson 0007 • UART TX, Shift Registers & Array ROM"
subtitle: "Send 115,200-baud 8N1 serial text from pin 69 to your macOS terminal using a 10-bit shift register, baud prescaler, valid/ready handshake, and combinational ASCII ROM."
card:
  title: "**UART Transmitter: Baud Ticks & Shift Registers**"
  summary: "Build a reusable UartTx 8N1 serializer and stream an ASCII banner over the BL616 USB-UART bridge to macOS."
---

:::callout title="Recommended Primary Sources"
- **Companion app**: `apps/0007-uart-tx/` (`.venv/bin/pytest -v apps/0007-uart-tx/`)
- **Primary docs**: [Amaranth HDL Documentation](https://amaranth-lang.org/docs/amaranth/latest/) • [Sipeed Tang Nano 20K Wiki](https://wiki.sipeed.com/hardware/en/tang/tang-nano-20k/nano-20k.html)
- **Course references**: [Lesson 0006: Dissecting PWM & FSM Verilog](0006-pwm-fsm-generated-verilog.md), [Glossary](../reference/GLOSSARY.md), and [Tang Nano 20K Pinout & Toolchain Sheet](../reference/tang-nano-20k-pinout.md)
:::

## 1. Asynchronous Serial Framing & Shift Registers {#mental-model}

Until now, our FPGA only communicated through six blinking LEDs. The Tang Nano 20K also carries a Bouffalo Lab `BL616` USB bridge wired directly to FPGA pin `69` (`uart_tx`) and pin `70` (`uart_rx`), giving us a 115,200-baud serial link straight to a macOS terminal with zero external jumper wires.

Unlike SPI or I2C, **UART (Universal Asynchronous Receiver-Transmitter)** sends no shared clock wire. Both sides agree on a bit rate—**115,200 baud**—and a **10-bit 8N1 frame** (8 data bits, No parity, 1 stop bit):

1. **Idle high (`1`), Start bit (`0`), Data LSB-first (`bit 0`..`bit 7`), Stop bit (`1`):** A UART line rests at logic `1` (`3.3 V`). When a byte begins, the transmitter pulls the wire to `0` for one bit period (the start bit), shifts out the 8 payload bits starting with the **least-significant bit** (`data[0]`), and returns the wire to `1` for at least one bit period (the stop bit).
2. **Baud-rate divider (`divisor = 234`):** At `27 MHz`, one bit at `115,200` baud lasts:
   $$
   \frac{27{,}000{,}000}{115{,}200} = 234.375 \approx 234\text{ clock cycles}
   $$
   With `divisor = 234`, our actual bit rate is $27{,}000{,}000 / 234 \approx 115{,}384.6\text{ baud}$—only $+0.16\%$ off target ($+1.6\%$ drift across a 10-bit frame, comfortably inside UART's $\pm 2\%$ sampling window).{{sidenote: Because `UartTx` spends 10 × 234 cycles shifting and 1 cycle in `IDLE` accepting the next byte when `valid` is held high, back-to-back bytes naturally get 1.004 stop bits, keeping frames clean for any receiver.}}
3. **Shift register = clocked bucket-brigade:** Think of `shifter` (`Signal(10, init=0x3FF)`) as a 10-stage analog shift register / bucket-brigade delay line. Its rightmost stage (`shifter[0]`) drives `tx` continuously; on every baud tick, every stage shifts one step right while `1` enters at the top (`shifter[9]`), automatically leaving the wire idling high once all 10 bits finish.
4. **Valid/Ready handshake = trigger/busy gate:** `UartBanner` streams bytes out of an Amaranth `Array` ROM using a classic hardware handshake: `valid` says *"a byte is waiting on `data`"*, and `ready` says *"I am idle and latching it on this rising clock edge."*

```mermaid caption="Figure 7.1: UartBanner + UartTx hardware datapath — 16-byte Array ROM feeds 10-bit 8N1 shift register onto pin 69 (BL616 USB bridge)"
flowchart LR
  subgraph BANNER["UartBanner (Top Component)"]
    IDX["char_index[3:0]"] --> ROM["Array ROM (16 ASCII bytes)"]
    FSMB["Banner FSM (SEND / PAUSE)"] -->|"valid"| TXMOD
    FSMB --> IDX
    PTMR["pause_timer (27M ticks = 1 s)"] --> FSMB
    ROM -->|"data[7:0]"| TXMOD
  end
  subgraph TXMOD["UartTx (divisor = 234)"]
    BTMR["baud_timer (0..233)"] -->|"tick"| SHF["shifter[9:0] (init = 0x3FF)"]
    BCNT["bit_count (9..0)"] --> FSMT["TX FSM (IDLE / SHIFT)"]
    FSMT -->|"ready"| FSMB
    FSMT --> SHF
    SHF -->|"shifter[0]"| PIN["uart_tx (Pin 69 -> BL616 -> macOS)"]
  end
  TXMOD -->|"ready, tx"| LEDS["~msg_count + telemetry -> leds[5:0]"]
```

## 2. Building `UartTx` and `UartBanner` Block by Block {#block-walkthrough}

### Block 1: `UartTx` Ports, Idle-High Shifter & Glitch-Free Output

```python caption="UartTx signature, registers, and glitch-free serial output"
class UartTx(wiring.Component):
    data: In(8)
    valid: In(1)
    ready: Out(1)
    tx: Out(1)

    def __init__(self, divisor: int = 234):
        if divisor < 2:
            raise ValueError("divisor must be at least 2")
        self.divisor = divisor
        super().__init__()

    def elaborate(self, platform):
        m = Module()
        shifter = Signal(10, init=0x3FF)
        baud_timer = Signal(range(self.divisor))
        bit_count = Signal(range(10))

        m.d.comb += self.tx.eq(shifter[0])
```

- **Non-zero `init=0x3FF`:** Passing `init=0x3FF` (all ten bits set to `1`: `0b11_1111_1111`) ensures `shifter[0]` starts at `1` on FPGA configuration **and** snaps right back to `1` whenever synchronous reset `rst` (`S1`) is pressed—never emitting a spurious `0` glitch on the serial line.
- **Why drive `self.tx` from `shifter[0]`?** Because `shifter` is a synchronous register (`m.d.sync`), `self.tx` only changes cleanly on rising clock edges with zero combinational mux glitches.

### Block 2: Loading & Shifting the 10-Bit 8N1 Frame

```python caption="IDLE/SHIFT FSM packing {stop=1, data, start=0} and shifting right LSB-first"
        with m.FSM(init="IDLE"):
            with m.State("IDLE"):
                m.d.comb += self.ready.eq(1)
                with m.If(self.valid):
                    m.d.sync += [
                        shifter.eq(Cat(Const(0, 1), self.data, Const(1, 1))),
                        baud_timer.eq(0),
                        bit_count.eq(9),
                    ]
                    m.next = "SHIFT"

            with m.State("SHIFT"):
                m.d.comb += self.ready.eq(0)
                with m.If(baud_timer == self.divisor - 1):
                    m.d.sync += [
                        baud_timer.eq(0),
                        shifter.eq(Cat(shifter[1:], Const(1, 1))),
                    ]
                    with m.If(bit_count == 0):
                        m.next = "IDLE"
                    with m.Else():
                        m.d.sync += bit_count.eq(bit_count - 1)
                with m.Else():
                    m.d.sync += baud_timer.eq(baud_timer + 1)
```

- **Packing the frame with LSB-first `Cat(...)`:** Remember from [Lesson 0005](0005-pwm-and-state-machines.md) that `Cat()` places its first argument at bit `0`:
  - `shifter[0]` ← `Const(0, 1)` (start bit, transmitted first!)
  - `shifter[8:1]` ← `self.data` (payload bits `0..7` in LSB-first order)
  - `shifter[9]` ← `Const(1, 1)` (stop bit, transmitted tenth!)
- **Shifting right with `Cat(shifter[1:], Const(1, 1))`:** On every baud tick (`baud_timer == self.divisor - 1`), bits `[9:1]` drop down into `[8:0]`—putting the next bit onto `shifter[0]`—while `Const(1, 1)` refills the empty MSB at `shifter[9]` so the line naturally rests at mark (`1`).
- **Counting 10 bit periods:** Initializing `bit_count.eq(9)` and transitioning back to `"IDLE"` when `bit_count == 0` holds each of the 10 bits (`9, 8, ..., 0`) for exact `self.divisor` cycles.

### Block 3: Combinational ASCII ROM (`Array`) & Valid/Ready Handshake

```python caption="Instantiating UartTx, building a 16-byte Array ROM, and streaming bytes in SEND"
        m = Module()
        m.submodules.uart = uart = UartTx(divisor=self.divisor)

        rom = Array(Const(b, 8) for b in self.message)
        char_index = Signal(range(len(self.message)))
        pause_timer = Signal(range(self.pause_cycles))
        msg_count = Signal(4)

        m.d.comb += [
            uart.data.eq(rom[char_index]),
            self.uart_tx.eq(uart.tx),
            self.leds.eq(Cat(uart.ready, uart.tx, ~msg_count)),
        ]

        with m.FSM(init="SEND"):
            with m.State("SEND"):
                m.d.comb += uart.valid.eq(1)
                with m.If(uart.ready):
                    with m.If(char_index == len(self.message) - 1):
                        m.d.sync += [
                            char_index.eq(0),
                            pause_timer.eq(0),
                            msg_count.eq(msg_count + 1),
                        ]
                        m.next = "PAUSE"
                    with m.Else():
                        m.d.sync += char_index.eq(char_index + 1)
```

- **Dynamic indexing with `Array`:** Plain Python lists cannot be indexed by an Amaranth `Signal` (`char_index`). Wrapping `Const(b, 8)` entries in `amaranth.Array` lets `rom[char_index]` elaborate into a combinational hardware lookup multiplexer.
- **Why guard index updates with `with m.If(uart.ready):`?** `UartBanner` only advances `char_index` on the single clock cycle where both `uart.valid` and `uart.ready` are `1`—meaning `UartTx` actually latched `rom[char_index]` into `shifter` on that clock edge.

### Block 4: Pacing Messages (`PAUSE` State) & Active-Low LED Telemetry

```python caption="Waiting for the last byte's stop bit before counting the 1-second pause"
            with m.State("PAUSE"):
                m.d.comb += uart.valid.eq(0)
                with m.If(uart.ready):
                    with m.If(pause_timer == self.pause_cycles - 1):
                        m.d.sync += pause_timer.eq(0)
                        m.next = "SEND"
                    with m.Else():
                        m.d.sync += pause_timer.eq(pause_timer + 1)
```

- **Why check `with m.If(uart.ready):` inside `PAUSE`?** When `SEND` hands off the final `\n` byte, `UartTx` is just **starting** to shift those 10 bits out! Waiting for `uart.ready` ensures the final stop bit finishes cleanly before `pause_timer` starts counting one full second (`27_000_000` ticks).
- **Onboard LED telemetry (`Cat(uart.ready, uart.tx, ~msg_count)`):**
  - `leds[0]` (`uart.ready`): active-low `0` while transmitting, `1` while paused.
  - `leds[1]` (`uart.tx`): flickers briefly whenever `0` bits travel down the serial line.
  - `leds[5:2]` (`~msg_count`): 4-bit binary counter incrementing every time a full `"Tang Nano 20K!\r\n"` line finishes.

### Complete uart_tx.py Listing

```python caption="apps/0007-uart-tx/uart_tx.py"
import argparse
from pathlib import Path

from amaranth import Array, Cat, Const, Module, Signal
from amaranth.back import verilog
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out
from amaranth.sim import Simulator


class UartTx(wiring.Component):
    data: In(8)
    valid: In(1)
    ready: Out(1)
    tx: Out(1)

    def __init__(self, divisor: int = 234):
        if divisor < 2:
            raise ValueError("divisor must be at least 2")
        self.divisor = divisor
        super().__init__()

    def elaborate(self, platform):
        m = Module()
        shifter = Signal(10, init=0x3FF)
        baud_timer = Signal(range(self.divisor))
        bit_count = Signal(range(10))

        m.d.comb += self.tx.eq(shifter[0])

        with m.FSM(init="IDLE"):
            with m.State("IDLE"):
                m.d.comb += self.ready.eq(1)
                with m.If(self.valid):
                    m.d.sync += [
                        shifter.eq(Cat(Const(0, 1), self.data, Const(1, 1))),
                        baud_timer.eq(0),
                        bit_count.eq(9),
                    ]
                    m.next = "SHIFT"

            with m.State("SHIFT"):
                m.d.comb += self.ready.eq(0)
                with m.If(baud_timer == self.divisor - 1):
                    m.d.sync += [
                        baud_timer.eq(0),
                        shifter.eq(Cat(shifter[1:], Const(1, 1))),
                    ]
                    with m.If(bit_count == 0):
                        m.next = "IDLE"
                    with m.Else():
                        m.d.sync += bit_count.eq(bit_count - 1)
                with m.Else():
                    m.d.sync += baud_timer.eq(baud_timer + 1)

        return m


class UartBanner(wiring.Component):
    uart_tx: Out(1)
    leds: Out(6)

    def __init__(
        self,
        divisor: int = 234,
        pause_cycles: int = 27_000_000,
        message: bytes = b"Tang Nano 20K!\r\n",
    ):
        if divisor < 2:
            raise ValueError("divisor must be at least 2")
        if pause_cycles < 2:
            raise ValueError("pause_cycles must be at least 2")
        if len(message) < 2:
            raise ValueError("message must have at least 2 bytes")
        self.divisor = divisor
        self.pause_cycles = pause_cycles
        self.message = message
        super().__init__()

    def elaborate(self, platform):
        m = Module()
        m.submodules.uart = uart = UartTx(divisor=self.divisor)

        rom = Array(Const(b, 8) for b in self.message)
        char_index = Signal(range(len(self.message)))
        pause_timer = Signal(range(self.pause_cycles))
        msg_count = Signal(4)

        m.d.comb += [
            uart.data.eq(rom[char_index]),
            self.uart_tx.eq(uart.tx),
            self.leds.eq(Cat(uart.ready, uart.tx, ~msg_count)),
        ]

        with m.FSM(init="SEND"):
            with m.State("SEND"):
                m.d.comb += uart.valid.eq(1)
                with m.If(uart.ready):
                    with m.If(char_index == len(self.message) - 1):
                        m.d.sync += [
                            char_index.eq(0),
                            pause_timer.eq(0),
                            msg_count.eq(msg_count + 1),
                        ]
                        m.next = "PAUSE"
                    with m.Else():
                        m.d.sync += char_index.eq(char_index + 1)

            with m.State("PAUSE"):
                m.d.comb += uart.valid.eq(0)
                with m.If(uart.ready):
                    with m.If(pause_timer == self.pause_cycles - 1):
                        m.d.sync += pause_timer.eq(0)
                        m.next = "SEND"
                    with m.Else():
                        m.d.sync += pause_timer.eq(pause_timer + 1)

        return m


def emit_verilog(
    divisor: int = 234,
    pause_cycles: int = 27_000_000,
    message: bytes = b"Tang Nano 20K!\r\n",
) -> str:
    dut = UartBanner(
        divisor=divisor,
        pause_cycles=pause_cycles,
        message=message,
    )
    return verilog.convert(dut, name="uart_banner", emit_src=False)


def run_vcd(
    output_path: Path,
    divisor: int = 4,
    pause_cycles: int = 8,
    message: bytes = b"Hi\r\n",
) -> None:
    dut = UartBanner(
        divisor=divisor,
        pause_cycles=pause_cycles,
        message=message,
    )

    async def testbench(ctx):
        for _ in range(250):
            await ctx.tick()

    sim = Simulator(dut)
    sim.add_clock(1 / 27_000_000)
    sim.add_testbench(testbench)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with sim.write_vcd(str(output_path)):
        sim.run()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Tang Nano 20K 115200-Baud UART TX Banner in Amaranth HDL"
    )
    parser.add_argument(
        "--verilog", action="store_true", help="Write build/uart_banner.v and print it"
    )
    parser.add_argument(
        "--vcd",
        action="store_true",
        help="Simulate UART TX banner to build/uart_banner.vcd",
    )
    parser.add_argument(
        "--divisor",
        type=int,
        default=234,
        help="Clock cycles per UART bit (27 MHz / 234 ≈ 115,385 baud)",
    )
    parser.add_argument(
        "--pause-cycles",
        type=int,
        default=27_000_000,
        help="Idle clock cycles between repeated messages",
    )
    parser.add_argument(
        "--message",
        type=str,
        default="Tang Nano 20K!\r\n",
        help="ASCII message string to transmit repeatedly",
    )
    args = parser.parse_args()

    message_bytes = args.message.encode("utf-8")
    build_dir = Path(__file__).parent / "build"
    if args.verilog or not args.vcd:
        code = emit_verilog(
            divisor=args.divisor,
            pause_cycles=args.pause_cycles,
            message=message_bytes,
        )
        build_dir.mkdir(parents=True, exist_ok=True)
        out_file = build_dir / "uart_banner.v"
        out_file.write_text(code, encoding="utf-8")
        print(code)

    if args.vcd:
        vcd_file = build_dir / "uart_banner.vcd"
        run_vcd(vcd_file)
        print(f"Wrote simulation waveform to {vcd_file}")


if __name__ == "__main__":
    main()
```

## 3. Pin Constraints & Opening the macOS Serial Terminal {#constraints}

In addition to `clk` (`pin 4`), `rst` (`pin 88`), and `leds[0..5]` (`pins 15..20`), we constrain `uart_tx` to package pin `69` (`IO_TYPE=LVCMOS33`), which connects straight to the onboard `BL616` USB-UART bridge:

```text caption="Excerpt from apps/0007-uart-tx/tangnano20k.cst"
IO_LOC "clk" 4;
IO_PORT "clk" IO_TYPE=LVCMOS33 PULL_MODE=UP;

IO_LOC "rst" 88;
IO_PORT "rst" IO_TYPE=LVCMOS33 PULL_MODE=DOWN;

IO_LOC "uart_tx" 69;
IO_PORT "uart_tx" IO_TYPE=LVCMOS33;
```

:::callout title="Ready to Dissect the Generated UART Verilog?"
When `uart_tx.py --verilog` compiles `UartBanner`, Amaranth lowers `init=0x3FF`, `shifter[1:]`, `{ 1'h1, data, 1'h0 }`, and `Array` into `uart_banner.v`. Continue to [Lesson 0008: Dissecting UART TX Verilog](0008-uart-tx-generated-verilog.md) to read every line of that generated hardware!
:::

:::exercise id="ex-0007" title="Interactive Lab: Idle-High Reset, 8N1 Frame Packing & Right Shifting" badge="Skill Practice • Tight Feedback Loop"
Complete the `UartTx` snippet below to initialize `shifter` idle-high, pack the 10-bit 8N1 frame LSB-first, shift bits right on each baud tick, and drive the serial output pin:

```python
shifter = Signal(10, {{blank:init=0x3FF|Parameter setting shifter to all 1s on power-up and reset?|??????????|10}})
m.d.comb += self.tx.eq({{blank:shifter[0]|LSB bit of the 10-bit shift register?|??????????|10}})

with m.If(self.valid):
    m.d.sync += shifter.eq({{blank:Cat(Const(0, 1), self.data, Const(1, 1))|Pack start=0, data, stop=1 LSB-first?|???????????????????????????????????????|39}})

with m.If(baud_timer == self.divisor - 1):
    m.d.sync += shifter.eq(Cat({{blank:shifter[1:]|Upper 9 bits of shifter shifted down by one position?|???????????|11}}, Const(1, 1)))
```

:::prompts
hint: "Use `init=0x3FF` for the 10-bit idle-high register, `shifter[0]` for TX, `Cat(Const(0, 1), self.data, Const(1, 1))` for LSB-first 8N1 framing, and `shifter[1:]` to shift right."
success: "Verified! You have mastered the core Amaranth idioms for UART 8N1 framing and shift registers."
:::
:::

:::verify id="verify-0007" title="Verification Lab: Simulate 8N1 Frames, Flash, and Read Serial on macOS" badge="Terminal Gate"
Run all 7 simulation tests, lint with `ruff`, and emit `build/uart_banner.v` plus a fast simulation waveform (`build/uart_banner.vcd`):

```bash
.venv/bin/pytest -v apps/0007-uart-tx/
.venv/bin/ruff check apps/0007-uart-tx/
.venv/bin/python apps/0007-uart-tx/uart_tx.py --verilog --vcd
```

If you have OSS CAD Suite installed on macOS, flash the Tang Nano 20K and open the USB-UART stream at `115200` baud:

```bash
export PATH="$HOME/oss-cad-suite/bin:$PATH"
make -C apps/0007-uart-tx flash
ls /dev/cu.usbserial*
screen /dev/cu.usbserial-<id> 115200
```

On macOS, the `BL616` bridge exposes two `/dev/cu.usbserial*` ports (one for JTAG, one for UART—typically the higher-numbered device, e.g. `1` vs `0`). Exit `screen` anytime with `Ctrl-A` then `k` (`y`), or use `tio -b 115200 /dev/cu.usbserial-<id>` if installed.

- [ ] All 7 tests in `test_uart_tx.py` pass (idle-high & 8N1 bit timing, input latching on handshake, repeated ASCII decoding, post-stop pause, sync reset, invalid parameters, and Verilog generation).
- [ ] `ruff check` reports `All checks passed!`.
- [ ] Your macOS serial terminal prints `Tang Nano 20K!` once per second while LED `0` pulses during transmission and LEDs `2–5` count completed lines.
:::

:::quiz id="quiz-0007" title="Retrieval Practice: UART 8N1 Framing & Shift Registers" badge="3 Questions • Equal-Length Options"
- question: "Why does `UartTx` initialize `shifter = Signal(10, init=0x3FF)` instead of leaving `init=0`?"
  wrong_hint: "Think about what voltage level a UART line rests at when no byte is being transmitted."
  options:
    - letter: "A"
      text: "UART lines idle low so starting at zero saves power"
      correct: false
      explain: "UART idles high (logic `1`), not low; a `0` level is interpreted as a start bit."
    - letter: "B"
      text: "UART lines idle high so all-ones prevents false start bits"
      correct: true
      explain: "`0x3FF` sets all 10 bits of `shifter` to `1`, keeping `shifter[0]` (`uart_tx`) high at power-up and reset."
    - letter: "C"
      text: "Gowin flip-flops cannot synthesize registers initialized to zero on startup"
      correct: false
      explain: "Gowin registers default to zero naturally; we explicitly set `0x3FF` so the serial line idles high."
    - letter: "D"
      text: "Amaranth shifts bit nine out first toward the serial pin"
      correct: false
      explain: "`self.tx` reads `shifter[0]`, so bits leave from bit `0` upward (`shifter[1:]` moves downward)."
- question: "In `shifter.eq(Cat(Const(0, 1), self.data, Const(1, 1)))`, in what order do the bits leave `shifter[0]`?"
  wrong_hint: "Remember `Cat()` packs LSB-first and `shifter` shifts right toward `shifter[0]`."
  options:
    - letter: "A"
      text: "Stop bit first, then MSB-first data bits, then start bit"
      correct: false
      explain: "The stop bit (`Const(1, 1)`) sits at `shifter[9]` and leaves last, after all 8 data bits."
    - letter: "B"
      text: "Start bit first, then MSB-first data bits, then stop bit"
      correct: false
      explain: "`self.data[0]` sits at `shifter[1]` and shifts to `shifter[0]` right after the start bit, so data leaves LSB-first."
    - letter: "C"
      text: "Start bit first, then LSB-first data bits, then stop bit"
      correct: true
      explain: "UART 8N1 transmits the `0` start bit (`[0]`), then `data[0]..data[7]` (`[8:1]`), and finally the `1` stop bit (`[9]`)."
    - letter: "D"
      text: "All ten bits leave pin 69 simultaneously on one edge"
      correct: false
      explain: "UART is serial over one wire (`uart_tx`), shifting one bit per `divisor` clock cycles."
- question: "Why does `UartBanner`'s `PAUSE` state check `with m.If(uart.ready):` before incrementing `pause_timer`?"
  wrong_hint: "Consider what `UartTx` is still doing on the clock cycle immediately after `SEND` hands off the final byte."
  options:
    - letter: "A"
      text: "Waiting ensures the last byte's stop bit finishes before pausing"
      correct: true
      explain: "When `SEND` enters `PAUSE`, `UartTx` still needs `10 × divisor` cycles to shift out the final `\\n` frame."
    - letter: "B"
      text: "The BL616 USB bridge requires dropping `uart_tx` low between bytes"
      correct: false
      explain: "UART lines must remain high (`1`) between bytes; pulling `uart_tx` low triggers a false start bit."
    - letter: "C"
      text: "Amaranth's `Array` ROM cannot reset `char_index` while `uart.ready` equals zero"
      correct: false
      explain: "`char_index` resets cleanly on the transition out of `SEND` regardless of `uart.ready`."
    - letter: "D"
      text: "Checking `uart.ready` doubles the baud rate from 57,600 to 115,200"
      correct: false
      explain: "Baud rate is set solely by `UartTx.divisor`, not by `UartBanner`'s `PAUSE` state."
:::

:::teacher-prompt title="Extend This Lesson with Your Agent"
Once your simulation passes and `"Tang Nano 20K!"` prints cleanly in your terminal, continue to [Lesson 0008: Dissecting UART TX Verilog](0008-uart-tx-generated-verilog.md) or ask your AI teacher:
- *"Why does `divisor = 234` give +0.16% baud error, and how small can a UART receiver tolerate?"*
- *"I've verified Lesson 0007 — let's dissect `uart_banner.v` in Lesson 0008!"*
:::
