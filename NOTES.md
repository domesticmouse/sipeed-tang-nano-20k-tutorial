# Course Working Notes & Curriculum Roadmap

## Learner Profile & Preferences
- **Background:** Strong high-level programming experience, past C experience, dabbled with microcontrollers (MCUs), and builds analog op-amp synthesizer circuits (TL074 buffered mults, envelope followers).
- **HDL Experience:** Knows HDLs exist, brand new to writing HDL code.
- **Learning Strategy:** Follow a paired **two-lesson cadence**: introduce each hardware concept in **Amaranth HDL** (`amaranth.lib.wiring.Component`) with `amaranth.sim` + `pytest` verification in an odd-numbered lesson, then dedicate the following even-numbered lesson to dissecting its generated Verilog line by line.
- **Hardware & Host:** Sipeed Tang Nano 20K (`GW2AR-LV18QN88C8/I7`) mounted on a breadboard; macOS Apple Silicon (`arm64`) using `uv` and OSS CAD Suite (`yosys`, `nextpnr-himbaechel`, `gowin_pack`, `openFPGALoader`).
- **Analogy Anchor:** Frame combinational (`m.d.comb`) vs synchronous (`m.d.sync`) logic around parallel continuous analog signal paths and sample-and-hold/clocked latches rather than sequential CPU loops.

## Curriculum Roadmap
- **Phase 1 — LEDs, Verilog Literacy & Buttons**
  - `0001-blinky-amaranth-to-verilog`: First Amaranth `wiring.Component`, `m.d.sync` vs `m.d.comb`, active-low LEDs, `pytest` simulation, `.cst` pin constraints, and flashing.
  - `0002-dissecting-generated-verilog`: Line-by-line breakdown of Yosys-generated `blinky.v` (escaped identifiers, `[MSB:LSB]` buses, carry-preserving widths, sized literals, `reg` vs `wire`, `always @(posedge clk)` `<=` vs `always @*` `=`, and `$auto$` sim guards).
  - `0003-buttons-and-debouncing`: Active-high buttons `S1`/`S2`, 2-flop metastability synchronizers, edge detection, and counter-based debouncing in Amaranth.
  - `0004-buttons-generated-verilog`: Dissecting the generated Verilog for `S1`/`S2` synchronizers, edge detectors, and debounce counters.
  - `0005-pwm-and-state-machines`: Pulse-width modulation (PWM) LED brightness control and Finite State Machines (FSMs) in Amaranth.
  - `0006-pwm-fsm-generated-verilog`: Dissecting how Amaranth lowers FSM states (`case`, one-hot/binary encoding) and PWM comparators into Verilog.
- **Phase 2 — USB-UART Serial**
  - `0007-uart-tx`: Baud-rate tick generator, shift registers, and streaming text from the FPGA to the macOS terminal via pin 69 in Amaranth.
  - `0008-uart-tx-generated-verilog`: Dissecting UART TX shift-register, bit-slice, and baud-counter Verilog.
  - `0009-uart-rx-and-echo`: Oversampling UART receiver (pin 70), framing, and interactive terminal control of onboard LEDs in Amaranth.
  - `0010-uart-rx-generated-verilog`: Dissecting oversampling RX state-machine and framing Verilog.
- **Phase 3 — HDMI Video**
  - `0011-pll-and-video-timing`: Gowin PLL clock multiplication (27 MHz → 125 MHz / 25 MHz) and 640×480 video sync/coordinate generator in Amaranth.
  - `0012-pll-video-timing-generated-verilog`: Dissecting black-box vendor `Instance` instantiation, multi-clock domains, and video timing counters in Verilog.
  - `0013-tmds-and-hdmi-output`: TMDS 8b/10b encoding, `OSER10` / `ELVDS_OBUF` primitives, and live HDMI color bars & test patterns in Amaranth.
  - `0014-tmds-hdmi-generated-verilog`: Dissecting TMDS combinational encoders and differential I/O primitive wiring in Verilog.
- **Phase 4 — Retro Gaming**
  - `0015-sprites-and-tilemaps`: Block RAM tilemaps, sprite blitting, and button/UART player input in Amaranth.
  - `0016-sprites-tilemaps-generated-verilog`: Dissecting inferred/explicit Gowin Block RAM (`Memory`) and sprite pipeline Verilog.
  - `0017-i2s-audio-and-playable-game`: MAX98357A I2S chiptune audio synthesis and a complete playable retro game core in Amaranth.
  - `0018-i2s-game-generated-verilog`: Dissecting the full multi-module retro-gaming core and I2S audio Verilog.
