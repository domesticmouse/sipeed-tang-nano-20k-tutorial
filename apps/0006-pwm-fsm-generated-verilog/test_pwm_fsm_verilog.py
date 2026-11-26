import re
from pathlib import Path

from pwm_fsm import emit_verilog

APP_DIR = Path(__file__).parent


def test_saved_verilog_matches_fresh_amaranth_output():
    saved = (APP_DIR / "pwm_breather.v").read_text(encoding="utf-8").rstrip("\n")
    fresh = emit_verilog().rstrip("\n")
    assert saved == fresh


def test_top_module_and_pwm_submodule_ports_and_registers():
    code = (APP_DIR / "pwm_breather.v").read_text(encoding="utf-8")
    assert "(* top = 1 *)" in code
    assert "module pwm_breather(rst, leds, clk);" in code
    assert r"module \pwm_breather.pwm (rst, out, duty, clk);" in code
    assert "output [5:0] leds;" in code
    assert "reg [1:0] fsm_state = 2'h0;" in code
    assert "reg [7:0] duty = 8'h00;" in code
    assert "reg [16:0] step_timer = 17'h00000;" in code
    assert "reg [5:0] hold_count = 6'h00;" in code
    assert "reg [7:0] counter = 8'h00;" in code


def test_named_port_instantiation_and_msb_first_concatenation():
    code = (APP_DIR / "pwm_breather.v").read_text(encoding="utf-8")
    assert re.search(
        r"\\pwm_breather\.pwm\s+pwm\s*\(\s*"
        r"\.clk\(clk\),\s*\.duty\(duty\),\s*\.out\(out\),\s*\.rst\(rst\)\s*\);",
        code,
    )
    assert "assign leds = ~ { state_leds, out, out };" in code


def test_pwm_comparator_thresholds_and_carry_preserving_arithmetic():
    code = (APP_DIR / "pwm_breather.v").read_text(encoding="utf-8")
    assert "assign out = counter < duty;" in code
    assert "step_timer == 17'h19bfc" in code
    assert 0x19BFC == 105_469 - 1
    assert "hold_count == 6'h3f" in code
    assert 0x3F == 64 - 1
    assert "duty + 1'h1;" in code
    assert "duty - 1'h1;" in code
    assert "! duty;" in code


def test_fsm_casez_lowering_and_moore_state_leds():
    code = (APP_DIR / "pwm_breather.v").read_text(encoding="utf-8")
    assert "casez (fsm_state)" in code
    for state_hex, led_hex in [
        ("2'h0", "4'h1"),
        ("2'h1", "4'h2"),
        ("2'h2", "4'h4"),
        ("2'h3", "4'h8"),
    ]:
        assert re.search(rf"{state_hex}:\s+state_leds = {led_hex};", code)
    assert "/* empty */;" in code


def test_small_parameters_shrink_register_widths():
    code = emit_verilog(pwm_width=4, step_cycles=4, hold_steps=4)
    assert "reg [3:0] duty = 4'h0;" in code
    assert "reg [3:0] counter = 4'h0;" in code
    assert "reg [1:0] step_timer = 2'h0;" in code
    assert "step_timer == 2'h3" in code
    assert "reg [1:0] hold_count = 2'h0;" in code
    assert "hold_count == 2'h3" in code
