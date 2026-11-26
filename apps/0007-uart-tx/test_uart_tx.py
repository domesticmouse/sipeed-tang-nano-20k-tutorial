import gc
import warnings

import pytest
from amaranth import ClockDomain, Module, UnusedElaboratable
from amaranth.sim import Simulator
from uart_tx import UartBanner, UartTx, emit_verilog


def test_uart_tx_idle_high_and_8n1_frame_bits():
    dut = UartTx(divisor=4)
    frames: dict[int, list[int]] = {}

    async def testbench(ctx):
        assert ctx.get(dut.tx) == 1
        assert ctx.get(dut.ready) == 1

        for byte in (0x55, 0xA3):
            ctx.set(dut.data, byte)
            ctx.set(dut.valid, 1)
            await ctx.tick()
            ctx.set(dut.valid, 0)

            assert ctx.get(dut.ready) == 0
            sampled_bits: list[int] = []
            for _ in range(10):
                bit_ticks = []
                for _ in range(4):
                    bit_ticks.append(ctx.get(dut.tx))
                    await ctx.tick()
                assert len(set(bit_ticks)) == 1
                sampled_bits.append(bit_ticks[0])
            frames[byte] = sampled_bits
            assert ctx.get(dut.ready) == 1
            assert ctx.get(dut.tx) == 1

    sim = Simulator(dut)
    sim.add_clock(1 / 27_000_000)
    sim.add_testbench(testbench)
    sim.run()

    for byte in (0x55, 0xA3):
        expected = [0] + [(byte >> i) & 1 for i in range(8)] + [1]
        assert frames[byte] == expected


def test_uart_tx_latches_data_on_handshake():
    dut = UartTx(divisor=3)
    decoded_byte = 0

    async def testbench(ctx):
        nonlocal decoded_byte
        ctx.set(dut.data, 0x41)
        ctx.set(dut.valid, 1)
        await ctx.tick()

        # Immediately mutate external inputs while UartTx is shifting
        ctx.set(dut.data, 0xFF)
        ctx.set(dut.valid, 0)

        # Skip start bit (3 ticks), then sample 8 data bits at mid-bit
        for _ in range(3):
            await ctx.tick()
        await ctx.tick()
        for i in range(8):
            decoded_byte |= ctx.get(dut.tx) << i
            for _ in range(3):
                await ctx.tick()

    sim = Simulator(dut)
    sim.add_clock(1 / 27_000_000)
    sim.add_testbench(testbench)
    sim.run()

    assert decoded_byte == 0x41


def test_uart_banner_streams_and_repeats_ascii_message():
    divisor = 2
    dut = UartBanner(divisor=divisor, pause_cycles=4, message=b"Hi!\r\n")
    received = bytearray()
    msg_counts: list[int] = []

    async def testbench(ctx):
        prev_tx = ctx.get(dut.uart_tx)
        msg_counts.append((ctx.get(dut.leds) >> 2) ^ 0xF)

        ticks = 0
        while len(received) < 10 and ticks < 400:
            await ctx.tick()
            ticks += 1
            cur_tx = ctx.get(dut.uart_tx)
            if prev_tx == 1 and cur_tx == 0:
                # Start bit detected; advance to center of first data bit
                for _ in range(divisor // 2 + divisor):
                    await ctx.tick()
                    ticks += 1
                byte_val = 0
                for bit_idx in range(8):
                    byte_val |= ctx.get(dut.uart_tx) << bit_idx
                    for _ in range(divisor):
                        await ctx.tick()
                        ticks += 1
                assert ctx.get(dut.uart_tx) == 1  # valid stop bit
                received.append(byte_val)
                msg_counts.append((ctx.get(dut.leds) >> 2) ^ 0xF)
                cur_tx = ctx.get(dut.uart_tx)
            prev_tx = cur_tx

    sim = Simulator(dut)
    sim.add_clock(1 / 27_000_000)
    sim.add_testbench(testbench)
    sim.run()

    assert bytes(received) == b"Hi!\r\nHi!\r\n"
    assert max(msg_counts) >= 2


def test_uart_banner_enforces_idle_pause_after_last_stop_bit():
    divisor = 2
    pause_cycles = 6
    dut = UartBanner(divisor=divisor, pause_cycles=pause_cycles, message=b"AB")
    ready_during_pause: list[int] = []

    async def testbench(ctx):
        # Wait until 'A' (20 ticks) + handshake (1 tick) + 'B' start+8 data bits (18 ticks)
        # Then observe stop bit of 'B' (2 ticks) + pause (6 ticks) + SEND reload (1 tick)
        saw_idle_ticks = 0
        frames_seen = 0
        prev_tx = ctx.get(dut.uart_tx)
        for _ in range(120):
            await ctx.tick()
            cur_tx = ctx.get(dut.uart_tx)
            if prev_tx == 1 and cur_tx == 0:
                frames_seen += 1
                if frames_seen == 3:
                    break
                # Advance past start + 8 data bits = 9 * divisor ticks to reach the stop bit
                for _ in range(9 * divisor):
                    await ctx.tick()
                if frames_seen == 2:
                    # Now right at the start of 'B' stop bit; count idle-high cycles
                    while ctx.get(dut.uart_tx) == 1 and saw_idle_ticks < 20:
                        ready_during_pause.append(ctx.get(dut.leds) & 1)
                        saw_idle_ticks += 1
                        await ctx.tick()
                    break
                cur_tx = ctx.get(dut.uart_tx)
            prev_tx = cur_tx

        assert saw_idle_ticks == divisor + pause_cycles + 1

    sim = Simulator(dut)
    sim.add_clock(1 / 27_000_000)
    sim.add_testbench(testbench)
    sim.run()

    # First `divisor` ticks are the stop bit (ready=0), followed by `pause_cycles + 1` idle ticks (ready=1)
    assert ready_during_pause[:divisor] == [0] * divisor
    assert ready_during_pause[divisor:] == [1] * (pause_cycles + 1)


def test_uart_banner_sync_reset_restores_idle_high():
    top = Module()
    cd_sync = ClockDomain("sync")
    top.domains += cd_sync
    top.submodules.dut = dut = UartBanner(divisor=4, pause_cycles=4, message=b"AB")
    decoded = 0

    async def testbench(ctx):
        nonlocal decoded
        # Advance 2 ticks into 'A' start bit (uart_tx is 0)
        await ctx.tick()
        await ctx.tick()
        assert ctx.get(dut.uart_tx) == 0

        ctx.set(cd_sync.rst, 1)
        await ctx.tick()
        assert ctx.get(dut.uart_tx) == 1
        assert ((ctx.get(dut.leds) >> 2) ^ 0xF) == 0

        ctx.set(cd_sync.rst, 0)
        # First tick after deasserting reset enters SEND and triggers 'A'; next tick starts start bit
        await ctx.tick()
        await ctx.tick()
        assert ctx.get(dut.uart_tx) == 0

        # Skip start bit (4 ticks) and sample 'A' (0x41)
        for _ in range(4 + 2):
            await ctx.tick()
        for i in range(8):
            decoded |= ctx.get(dut.uart_tx) << i
            for _ in range(4):
                await ctx.tick()

    sim = Simulator(top)
    sim.add_clock(1 / 27_000_000)
    sim.add_testbench(testbench)
    sim.run()

    assert decoded == ord("A")


def test_invalid_parameters_raise():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UnusedElaboratable)
        with pytest.raises(ValueError, match="at least 2"):
            UartTx(divisor=1)
        with pytest.raises(ValueError, match="at least 2"):
            UartBanner(divisor=1)
        with pytest.raises(ValueError, match="at least 2"):
            UartBanner(pause_cycles=1)
        with pytest.raises(ValueError, match="at least 2 bytes"):
            UartBanner(message=b"A")
        with pytest.raises(ValueError, match="at least 2 bytes"):
            UartBanner(message=b"")
        gc.collect()


def test_verilog_generation_contains_expected_modules_and_shifter():
    code = emit_verilog(divisor=4, pause_cycles=4, message=b"Hi")
    assert "module uart_banner(" in code
    assert r"module \uart_banner.uart (" in code
    assert "shifter[9:1]" in code
    assert "shifter[0]" in code
    assert "casez (char_index)" in code
