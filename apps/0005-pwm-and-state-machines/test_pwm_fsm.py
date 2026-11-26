import gc
import warnings

import pytest
from amaranth import ClockDomain, Module, UnusedElaboratable
from amaranth.sim import Simulator
from pwm_fsm import PwmBreather, PwmGenerator, emit_verilog


def test_pwm_generator_duty_cycles():
    dut = PwmGenerator(width=4)
    observed: dict[int, int] = {}

    async def testbench(ctx):
        for duty in (0, 8, 15):
            ctx.set(dut.duty, duty)
            high_ticks = 0
            for _ in range(16):
                high_ticks += ctx.get(dut.out)
                await ctx.tick()
            observed[duty] = high_ticks

    sim = Simulator(dut)
    sim.add_clock(1 / 27_000_000)
    sim.add_testbench(testbench)
    sim.run()

    assert observed == {0: 0, 8: 8, 15: 15}


def test_pwm_breather_traverses_all_four_fsm_states():
    dut = PwmBreather(pwm_width=2, step_cycles=2, hold_steps=2)
    state_history: list[int] = []

    async def testbench(ctx):
        # 24 ticks = RAMP_UP(8) + HOLD_HIGH(4) + RAMP_DOWN(8) + HOLD_LOW(4)
        for _ in range(25):
            state_bits = (ctx.get(dut.leds) >> 2) ^ 0xF
            state_history.append(state_bits)
            await ctx.tick()

    sim = Simulator(dut)
    sim.add_clock(1 / 27_000_000)
    sim.add_testbench(testbench)
    sim.run()

    assert state_history[0:8] == [0b0001] * 8
    assert state_history[8:12] == [0b0010] * 4
    assert state_history[12:20] == [0b0100] * 8
    assert state_history[20:24] == [0b1000] * 4
    assert state_history[24] == 0b0001


def test_pwm_breather_brightness_peaks_in_hold_high_and_zero_in_hold_low():
    dut = PwmBreather(pwm_width=2, step_cycles=4, hold_steps=2)
    hold_high_pwm: list[int] = []
    hold_low_pwm: list[int] = []

    async def testbench(ctx):
        for _ in range(48):
            leds = ctx.get(dut.leds)
            pwm_pair = leds & 0b11
            assert pwm_pair in (0b00, 0b11)
            state_bits = (leds >> 2) ^ 0xF
            if state_bits == 0b0010:
                hold_high_pwm.append(0 if pwm_pair == 0b00 else 1)
            elif state_bits == 0b1000:
                hold_low_pwm.append(0 if pwm_pair == 0b00 else 1)
            await ctx.tick()

    sim = Simulator(dut)
    sim.add_clock(1 / 27_000_000)
    sim.add_testbench(testbench)
    sim.run()

    assert len(hold_high_pwm) == 8
    assert hold_high_pwm.count(0) == 6  # max_duty=3 out of 4 ticks per PWM period
    assert hold_low_pwm == [1] * 8  # active-low LEDs stay off (1) throughout HOLD_LOW


def test_pwm_breather_sync_reset_returns_to_ramp_up():
    top = Module()
    cd_sync = ClockDomain("sync")
    top.domains += cd_sync
    top.submodules.dut = dut = PwmBreather(pwm_width=2, step_cycles=2, hold_steps=2)
    observed: list[int] = []

    async def testbench(ctx):
        for _ in range(8):
            await ctx.tick()
        assert ((ctx.get(dut.leds) >> 2) ^ 0xF) == 0b0010  # reached HOLD_HIGH

        ctx.set(cd_sync.rst, 1)
        await ctx.tick()
        observed.append((ctx.get(dut.leds) >> 2) ^ 0xF)

        ctx.set(cd_sync.rst, 0)
        await ctx.tick()
        observed.append((ctx.get(dut.leds) >> 2) ^ 0xF)

    sim = Simulator(top)
    sim.add_clock(1 / 27_000_000)
    sim.add_testbench(testbench)
    sim.run()

    assert observed == [0b0001, 0b0001]


def test_invalid_parameters_raise():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UnusedElaboratable)
        with pytest.raises(ValueError, match="at least 2"):
            PwmGenerator(width=1)
        with pytest.raises(ValueError, match="at least 2"):
            PwmBreather(pwm_width=1)
        with pytest.raises(ValueError, match="at least 2"):
            PwmBreather(step_cycles=1)
        with pytest.raises(ValueError, match="at least 2"):
            PwmBreather(hold_steps=1)
        gc.collect()


def test_verilog_generation_contains_expected_modules_and_fsm():
    code = emit_verilog(pwm_width=4, step_cycles=4, hold_steps=4)
    assert "module pwm_breather(" in code
    assert r"module \pwm_breather.pwm (" in code
    assert "casez (fsm_state)" in code
    assert "counter < duty" in code
