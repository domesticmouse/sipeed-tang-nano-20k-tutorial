import re
from pathlib import Path

from uart_tx import emit_verilog

APP_DIR = Path(__file__).parent


def test_saved_verilog_matches_fresh_amaranth_output():
    saved = (APP_DIR / "uart_banner.v").read_text(encoding="utf-8").rstrip("\n")
    fresh = emit_verilog().rstrip("\n")
    assert saved == fresh


def test_top_module_and_uart_submodule_ports_and_registers():
    code = (APP_DIR / "uart_banner.v").read_text(encoding="utf-8")
    assert "(* top = 1 *)" in code
    assert "module uart_banner(rst, uart_tx, leds, clk);" in code
    assert r"module \uart_banner.uart (rst, data, valid, ready, tx, clk);" in code
    assert "output [5:0] leds;" in code
    assert "reg [3:0] char_index = 4'h0;" in code
    assert "reg [24:0] pause_timer = 25'h0000000;" in code
    assert "reg [3:0] msg_count = 4'h0;" in code
    assert "reg [7:0] baud_timer = 8'h00;" in code
    assert "reg [3:0] bit_count = 4'h0;" in code
    assert "reg [9:0] shifter = 10'h3ff;" in code


def test_named_port_instantiation_and_bit_concatenation():
    code = (APP_DIR / "uart_banner.v").read_text(encoding="utf-8")
    assert re.search(
        r"\\uart_banner\.uart\s+uart\s*\(\s*"
        r"\.clk\(clk\),\s*\.data\(data\),\s*\.ready\(ready\),\s*"
        r"\.rst\(rst\),\s*\.tx\(uart_tx\),\s*\.valid\(valid\)\s*\);",
        code,
    )
    assert r"assign leds = { \$1 , uart_tx, ready };" in code
    assert "assign tx = shifter[0];" in code
    assert "{ 1'h1, data, 1'h0 }" in code
    assert "{ 1'h1, shifter[9:1] }" in code


def test_baud_rate_and_pause_thresholds_and_nonzero_reset():
    code = (APP_DIR / "uart_banner.v").read_text(encoding="utf-8")
    assert "baud_timer == 8'he9" in code
    assert 0xE9 == 234 - 1
    assert "pause_timer == 25'h19bfcbf" in code
    assert 0x19BFCBF == 27_000_000 - 1
    assert "char_index == 4'hf" in code
    assert re.search(r"if \(rst\) begin\s*\\\$7\s*=\s*10'h3ff;\s*end", code)


def test_ascii_rom_casez_lookup_table():
    code = (APP_DIR / "uart_banner.v").read_text(encoding="utf-8")
    assert "casez (char_index)" in code
    expected_bytes = b"Tang Nano 20K!\r\n"
    for idx, byte in enumerate(expected_bytes):
        assert re.search(rf"4'h{idx:x}:\s+data = 8'h{byte:02x};", code)


def test_small_parameters_shrink_register_widths():
    code = emit_verilog(divisor=4, pause_cycles=4, message=b"Hi")
    assert "reg [7:0] baud_timer" not in code
    assert "reg [1:0] baud_timer = 2'h0;" in code
    assert "baud_timer == 2'h3" in code
    assert "reg [1:0] pause_timer = 2'h0;" in code
    assert "pause_timer == 2'h3" in code
    assert "reg char_index = 1'h0;" in code
    assert "reg [9:0] shifter = 10'h3ff;" in code
