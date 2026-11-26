from amaranth.sim import Simulator
from blinky import Blinky, emit_verilog


def test_initial_state_all_leds_off():
    dut = Blinky(half_period=4)

    async def testbench(ctx):
        assert ctx.get(dut.leds) == 0b111111

    sim = Simulator(dut)
    sim.add_clock(1 / 27_000_000)
    sim.add_testbench(testbench)
    sim.run()


def test_pattern_increments_every_half_period():
    dut = Blinky(half_period=4)

    async def testbench(ctx):
        for expected_pattern in range(4):
            expected_leds = (~expected_pattern) & 0x3F
            for _ in range(4):
                assert ctx.get(dut.leds) == expected_leds
                await ctx.tick()

    sim = Simulator(dut)
    sim.add_clock(1 / 27_000_000)
    sim.add_testbench(testbench)
    sim.run()


def test_six_bit_wraparound():
    dut = Blinky(half_period=1)

    async def testbench(ctx):
        for _ in range(64):
            await ctx.tick()
        assert ctx.get(dut.leds) == 0b111111

    sim = Simulator(dut)
    sim.add_clock(1 / 27_000_000)
    sim.add_testbench(testbench)
    sim.run()


def test_verilog_generation_contains_expected_ports():
    code = emit_verilog(half_period=4)
    assert "module blinky(" in code
    assert "clk" in code
    assert "rst" in code
    assert "leds" in code
    assert "always @(posedge clk)" in code
