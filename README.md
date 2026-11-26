# Sipeed Tang Nano 20K Tutorial — Amaranth HDL & Verilog by Assimilation

Interactive, test-verified FPGA course targeting the **Sipeed Tang Nano 20K** (`GW2AR-LV18QN88C8/I7`) on macOS Apple Silicon (`arm64`).

**Live Course Site:** https://domesticmouse.github.io/sipeed-tang-nano-20k-tutorial/

## Progression
- **LEDs & Buttons → USB-UART → HDMI Video → Retro Gaming → Game Boy (DMG) → Commodore 64 → Eurorack Video Synth**
- Lessons follow a paired two-lesson cadence: each odd-numbered lesson introduces a hardware concept in Amaranth HDL (verified with `pytest`, `ruff`, and open-source flashing via `yosys` + `nextpnr-himbaechel` + `gowin_pack` + `openFPGALoader`), and the following even-numbered lesson dissects its generated Verilog line by line.

## Published Course Pages
- [Course Index](index.md)
- [Lesson 0001: Blinky in Amaranth HDL](lessons/0001-blinky-amaranth-to-verilog.md)
- [Lesson 0002: Dissecting Generated Verilog](lessons/0002-dissecting-generated-verilog.md)
- [Lesson 0003: Buttons, Synchronizers & Debouncing](lessons/0003-buttons-and-debouncing.md)
- [Lesson 0004: Dissecting Button & Debouncer Verilog](lessons/0004-buttons-generated-verilog.md)
- [Lesson 0005: PWM Brightness & Finite State Machines](lessons/0005-pwm-and-state-machines.md)
- [Lesson 0006: Dissecting PWM & FSM Verilog](lessons/0006-pwm-fsm-generated-verilog.md)
- [Lesson 0007: UART Transmitter: Baud Ticks & Shift Registers](lessons/0007-uart-tx.md)
- [Lesson 0008: Dissecting UART TX Verilog](lessons/0008-uart-tx-generated-verilog.md)
- [Reference: Glossary of FPGA & Amaranth Terms](reference/GLOSSARY.md)
- [Reference: Tang Nano 20K Pinout & Toolchain Sheet](reference/tang-nano-20k-pinout.md)

## Quick Start

```bash
# Run all simulation and generated-Verilog tests and linter
.venv/bin/pytest -v apps/0001-blinky-amaranth-to-verilog/ apps/0002-dissecting-generated-verilog/ apps/0003-buttons-and-debouncing/ apps/0004-buttons-generated-verilog/ apps/0005-pwm-and-state-machines/ apps/0006-pwm-fsm-generated-verilog/ apps/0007-uart-tx/ apps/0008-uart-tx-generated-verilog/
.venv/bin/ruff check apps/0001-blinky-amaranth-to-verilog/ apps/0002-dissecting-generated-verilog/ apps/0003-buttons-and-debouncing/ apps/0004-buttons-generated-verilog/ apps/0005-pwm-and-state-machines/ apps/0006-pwm-fsm-generated-verilog/ apps/0007-uart-tx/ apps/0008-uart-tx-generated-verilog/ build.py

# Build and validate the HTML site
.venv/bin/python .agents/skills/teach-code/scripts/sync_listing.py --check
.venv/bin/python build.py --check
```

## License

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) for the full license text.

## Disclaimer

This is not an officially supported Google product.
