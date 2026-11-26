import gc
import warnings

import pytest
from amaranth import UnusedElaboratable
from amaranth.sim import Simulator
from buttons import ButtonCounter, ButtonDebouncer, emit_verilog


def test_initial_state_all_leds_off():
    dut = ButtonCounter(debounce_cycles=4)

    async def testbench(ctx):
        assert ctx.get(dut.leds) == 0b111111

    sim = Simulator(dut)
    sim.add_clock(1 / 27_000_000)
    sim.add_testbench(testbench)
    sim.run()


def test_debouncer_rejects_short_bounces():
    dut = ButtonDebouncer(debounce_cycles=4)

    async def testbench(ctx):
        bounces = [1, 1, 0, 1, 1, 1, 0, 0, 1, 0, 0, 0]
        for raw_val in bounces:
            ctx.set(dut.raw, raw_val)
            await ctx.tick()
            assert ctx.get(dut.level) == 0
            assert ctx.get(dut.pressed) == 0

    sim = Simulator(dut)
    sim.add_clock(1 / 27_000_000)
    sim.add_testbench(testbench)
    sim.run()


def test_debouncer_emits_single_cycle_rising_pulse():
    dut = ButtonDebouncer(debounce_cycles=4)

    async def testbench(ctx):
        samples: list[tuple[int, int]] = []
        ctx.set(dut.raw, 1)
        for _ in range(12):
            await ctx.tick()
            samples.append((ctx.get(dut.level), ctx.get(dut.pressed)))

        ctx.set(dut.raw, 0)
        for _ in range(10):
            await ctx.tick()
            samples.append((ctx.get(dut.level), ctx.get(dut.pressed)))

        levels = [lvl for lvl, _ in samples]
        pulses = [prs for _, prs in samples]
        assert levels[0] == 0
        assert 1 in levels
        assert levels[-1] == 0
        assert sum(pulses) == 1
        pulse_idx = pulses.index(1)
        assert levels[pulse_idx - 1] == 0
        assert levels[pulse_idx] == 1

    sim = Simulator(dut)
    sim.add_clock(1 / 27_000_000)
    sim.add_testbench(testbench)
    sim.run()


def test_button_counter_counts_clean_presses_and_ignores_chatter():
    dut = ButtonCounter(debounce_cycles=4)

    async def testbench(ctx):
        # Short chatter below debounce window leaves count at 0
        for raw_val in [1, 0, 1, 1, 0, 0]:
            ctx.set(dut.s2, raw_val)
            await ctx.tick()
        assert ctx.get(dut.leds) == (~0) & 0x3F

        # Clean press 1 (held long enough to settle) -> count becomes 1
        ctx.set(dut.s2, 1)
        for _ in range(10):
            await ctx.tick()
        assert ctx.get(dut.leds) == (~1) & 0x3F

        # Bouncy release -> count remains 1
        for raw_val in [0, 1, 0, 0, 0, 0, 0, 0, 0, 0]:
            ctx.set(dut.s2, raw_val)
            await ctx.tick()
        assert ctx.get(dut.leds) == (~1) & 0x3F

        # Clean press 2 -> count becomes 2
        ctx.set(dut.s2, 1)
        for _ in range(10):
            await ctx.tick()
        assert ctx.get(dut.leds) == (~2) & 0x3F

    sim = Simulator(dut)
    sim.add_clock(1 / 27_000_000)
    sim.add_testbench(testbench)
    sim.run()


def test_invalid_debounce_cycles_raises():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UnusedElaboratable)
        with pytest.raises(ValueError, match="at least 2"):
            ButtonDebouncer(debounce_cycles=1)
        with pytest.raises(ValueError, match="at least 2"):
            ButtonCounter(debounce_cycles=0)
        gc.collect()


def test_verilog_generation_contains_expected_modules_and_ports():
    code = emit_verilog(debounce_cycles=4)
    assert "module button_counter(" in code
    assert r"module \button_counter.debouncer (" in code
    assert "clk" in code
    assert "rst" in code
    assert "s2" in code
    assert "leds" in code
    assert "always @(posedge clk)" in code
