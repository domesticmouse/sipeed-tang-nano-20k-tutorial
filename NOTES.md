# Course Working Notes & Curriculum Roadmap

## Learner Profile & Preferences
- **Background:** Strong high-level programming experience, past C experience, dabbled with microcontrollers (MCUs), and builds analog op-amp synthesizer circuits (TL074 buffered mults, envelope followers).
- **HDL Experience:** Knows HDLs exist, brand new to writing HDL code.
- **Learning Strategy:** Write hardware modules in **Amaranth HDL** (`amaranth.lib.wiring.Component`), test them in Python with `amaranth.sim` + `pytest`, and **dissect the generated Verilog** in every lesson to learn Verilog by assimilation.
- **Hardware & Host:** Sipeed Tang Nano 20K (`GW2AR-LV18QN88C8/I7`) mounted on a breadboard; macOS Apple Silicon (`arm64`) using `uv` and OSS CAD Suite (`yosys`, `nextpnr-himbaechel`, `gowin_pack`, `openFPGALoader`).
- **Analogy Anchor:** Frame combinational (`m.d.comb`) vs synchronous (`m.d.sync`) logic around parallel continuous analog signal paths and sample-and-hold/clocked latches rather than sequential CPU loops.

## Curriculum Roadmap
- **Phase 1 — LEDs & Buttons**
  - `0001-blinky-amaranth-to-verilog`: First Amaranth `wiring.Component`, `m.d.sync` vs `m.d.comb`, active-low LEDs, `pytest` simulation, and dissecting generated Verilog + `.cst` constraints.
  - `0002-buttons-and-debouncing`: Active-high buttons `S1`/`S2`, 2-flop metastability synchronizers, edge detection, and counter-based debouncing.
  - `0003-pwm-and-state-machines`: Pulse-width modulation (PWM) LED brightness control and Finite State Machines (FSMs).
- **Phase 2 — USB-UART Serial**
  - `0004-uart-tx`: Baud-rate tick generator, shift registers, and streaming text from the FPGA to the macOS terminal via pin 69.
  - `0005-uart-rx-and-echo`: Oversampling UART receiver (pin 70), framing, and interactive terminal control of onboard LEDs.
- **Phase 3 — HDMI Video**
  - `0006-pll-and-video-timing`: Gowin PLL clock multiplication (27 MHz → 125 MHz / 25 MHz) and 640×480 video sync/coordinate generator.
  - `0007-tmds-and-hdmi-output`: TMDS 8b/10b encoding, `OSER10` / `ELVDS_OBUF` primitives, and live HDMI color bars & test patterns.
- **Phase 4 — Retro Gaming**
  - `0008-sprites-and-tilemaps`: Block RAM tilemaps, sprite blitting, and button/UART player input.
  - `0009-i2s-audio-and-playable-game`: MAX98357A I2S chiptune audio synthesis and a complete playable retro game core.
