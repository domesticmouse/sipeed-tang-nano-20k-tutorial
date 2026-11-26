# Mission: Sipeed Tang Nano 20K FPGA Development with Amaranth HDL

## Why
Go from software, microcontroller, and analog-synth tinkering to designing, simulating, and flashing real FPGA hardware on a breadboarded Sipeed Tang Nano 20K — progressing from onboard LEDs to USB-UART serial communication, HDMI video generation, and retro-gaming hardware — by writing Amaranth HDL in Python and dissecting the generated Verilog to learn Verilog by assimilation.

## Success looks like
- Design, simulate with `pytest`, and flash Amaranth modules driving the Tang Nano 20K's 6 onboard LEDs and buttons, while reading and explaining every line of the generated Verilog.
- Build and verify a USB-UART transceiver communicating bidirectionally with the macOS terminal over the onboard BL616 bridge.
- Drive compliant HDMI video timing and pixel graphics from the 27 MHz crystal, PLL, and Gowin TMDS primitives.
- Combine video, controls, memory, and audio into a playable retro-style game/core on the Tang Nano 20K.

## Constraints
- Hardware: Sipeed Tang Nano 20K (`GW2AR-LV18QN88C8/I7`, QN88 package) mounted on a breadboard.
- Host: macOS Apple Silicon (`arm64`) using open-source tooling (`uv`, Python + Amaranth HDL, `pytest`, OSS CAD Suite: `yosys`, `nextpnr-himbaechel`, `gowin_pack`, `openFPGALoader`).
- Learning strategy: Author in Amaranth HDL (`amaranth.lib.wiring.Component`), dissect generated Verilog in every lesson.

## Out of scope
- Proprietary Gowin EDA IDE workflows (Windows/Linux GUI).
- VHDL or High-Level Synthesis (HLS).
- Deep ASIC static timing closure before completing the core retro-gaming progression.
