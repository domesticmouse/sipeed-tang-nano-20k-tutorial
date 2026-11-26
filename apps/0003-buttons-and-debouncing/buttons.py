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
