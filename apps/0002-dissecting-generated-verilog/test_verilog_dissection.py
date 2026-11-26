import re
from pathlib import Path

from blinky import emit_verilog

APP_DIR = Path(__file__).parent


def test_saved_verilog_matches_fresh_amaranth_output():
    saved = (APP_DIR / "blinky.v").read_text(encoding="utf-8").rstrip("\n")
    fresh = emit_verilog(half_period=13_500_000).rstrip("\n")
    assert saved == fresh


def test_ports_and_bus_widths():
    code = (APP_DIR / "blinky.v").read_text(encoding="utf-8")
    assert "module blinky(rst, leds, clk);" in code
    assert "input rst;" in code
    assert "input clk;" in code
    assert "output [5:0] leds;" in code
    assert "reg [5:0] pattern = 6'h00;" in code
    assert "reg [23:0] timer = 24'h000000;" in code


def test_carry_preserving_adder_widths_and_threshold():
    code = (APP_DIR / "blinky.v").read_text(encoding="utf-8")
    assert r"wire [6:0] \$2 ;" in code
    assert r"wire [24:0] \$3 ;" in code
    assert "timer == 24'hcdfe5f" in code
    assert 0xCDFE5F == 13_500_000 - 1


def test_clocked_nonblocking_vs_combinational_blocking():
    code = (APP_DIR / "blinky.v").read_text(encoding="utf-8")
    assert re.search(r"always @\(posedge clk\)\s+timer <= \\\$4 ;", code)
    assert re.search(r"always @\(posedge clk\)\s+pattern <= \\\$5 ;", code)
    assert "assign leds = ~ pattern;" in code
    always_star_blocks = re.findall(
        r"^  always @\* begin(.*?)^  end$", code, re.DOTALL | re.MULTILINE
    )
    assert len(always_star_blocks) == 2
    assert r"\$4  =" in always_star_blocks[0]
    assert r"\$5  =" in always_star_blocks[1]


def test_reset_override_has_highest_priority():
    code = (APP_DIR / "blinky.v").read_text(encoding="utf-8")
    pattern_block = re.findall(
        r"^  always @\* begin(.*?)^  end$", code, re.DOTALL | re.MULTILINE
    )[1]
    hold_pos = pattern_block.index(r"\$5  = pattern;")
    inc_pos = pattern_block.index(r"if (\$1 )")
    rst_pos = pattern_block.index("if (rst)")
    assert hold_pos < inc_pos < rst_pos


def test_small_half_period_shrinks_timer_width():
    code = emit_verilog(half_period=4)
    assert "reg [1:0] timer = 2'h0;" in code
    assert "timer == 2'h3" in code
