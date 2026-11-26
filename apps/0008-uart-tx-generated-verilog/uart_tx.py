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
