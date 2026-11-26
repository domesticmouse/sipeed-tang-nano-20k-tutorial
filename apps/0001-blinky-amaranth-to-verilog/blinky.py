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
