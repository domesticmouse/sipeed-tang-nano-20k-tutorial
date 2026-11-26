import re
from pathlib import Path

from buttons import emit_verilog

APP_DIR = Path(__file__).parent


def test_saved_verilog_matches_fresh_amaranth_output():
    saved = (APP_DIR / "buttons.v").read_text(encoding="utf-8").rstrip("\n")
    fresh = emit_verilog(debounce_cycles=270_000).rstrip("\n")
    assert saved == fresh


def test_top_module_and_submodule_ports():
    code = (APP_DIR / "buttons.v").read_text(encoding="utf-8")
    assert "(* top = 1 *)" in code
    assert "module button_counter(clk, rst, leds, s2);" in code
    assert r"module \button_counter.debouncer (clk, rst, pressed, raw);" in code
    assert "input s2;" in code
    assert "output [5:0] leds;" in code
    assert "reg [5:0] count = 6'h00;" in code
    assert "reg [18:0] counter = 19'h00000;" in code
    assert "reg sync_0 = 1'h0;" in code
    assert "reg sync_1 = 1'h0;" in code
    assert "reg stable = 1'h0;" in code
    assert "reg prev_stable = 1'h0;" in code


def test_named_port_submodule_instantiation():
    code = (APP_DIR / "buttons.v").read_text(encoding="utf-8")
    assert re.search(
        r"\\button_counter\.debouncer\s+debouncer\s*\(\s*"
        r"\.clk\(clk\),\s*\.pressed\(pressed\),\s*\.raw\(s2\),\s*\.rst\(rst\)\s*\);",
        code,
    )


def test_debounce_threshold_and_carry_preserving_adders():
    code = (APP_DIR / "buttons.v").read_text(encoding="utf-8")
    assert r"wire [6:0] \$1 ;" in code
    assert r"wire [19:0] \$3 ;" in code
    assert "counter == 19'h41eaf" in code
    assert 0x41EAF == 270_000 - 1


def test_two_flop_synchronizer_and_rising_edge_logic():
    code = (APP_DIR / "buttons.v").read_text(encoding="utf-8")
    assert re.search(r"always @\(posedge clk\)\s+sync_0 <= \\\$5 ;", code)
    assert re.search(r"always @\(posedge clk\)\s+sync_1 <= \\\$6 ;", code)
    assert re.search(r"always @\(posedge clk\)\s+prev_stable <= \\\$9 ;", code)
    assert r"assign \$4  = ~ prev_stable;" in code
    assert r"assign pressed = stable & \$4 ;" in code


def test_small_debounce_cycles_shrinks_counter_width():
    code = emit_verilog(debounce_cycles=4)
    assert "reg [1:0] counter = 2'h0;" in code
    assert r"wire [2:0] \$3 ;" in code
    assert "counter == 2'h3" in code
