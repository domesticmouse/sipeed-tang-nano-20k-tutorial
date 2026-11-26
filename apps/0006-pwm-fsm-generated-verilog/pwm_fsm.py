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
