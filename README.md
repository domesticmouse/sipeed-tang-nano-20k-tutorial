# Sipeed Tang Nano 20K Tutorial — Amaranth HDL & Verilog by Assimilation

Interactive, test-verified FPGA course targeting the **Sipeed Tang Nano 20K** (`GW2AR-LV18QN88C8/I7`) on macOS Apple Silicon (`arm64`).

**Live Course Site:** https://domesticmouse.github.io/sipeed-tang-nano-nano-20k-tutorial/

## Progression
- **LEDs & Buttons → USB-UART → HDMI Video → Retro Gaming**
- Every lesson pairs a runnable Amaranth HDL project in `apps/` (verified with `pytest` and `ruff`) with a line-by-line dissection of its generated Verilog and open-source bitstream flashing (`yosys` + `nextpnr-himbaechel` + `gowin_pack` + `openFPGALoader`).

## Published Course Pages
- [Course Index](index.md)
- [Lesson 0001: Blinky in Amaranth & Verilog Dissection](lessons/0001-blinky-amaranth-to-verilog.md)
- [Reference: Glossary of FPGA & Amaranth Terms](reference/GLOSSARY.md)
- [Reference: Tang Nano 20K Pinout & Toolchain Sheet](reference/tang-nano-20k-pinout.md)

## Quick Start

```bash
# Run Lesson 0001 simulation tests and linter
.venv/bin/pytest -v apps/0001-blinky-amaranth-to-verilog/
.venv/bin/ruff check apps/0001-blinky-amaranth-to-verilog/ build.py

# Build and validate the HTML site
.venv/bin/python .agents/skills/teach-code/scripts/sync_listing.py --check
.venv/bin/python build.py --check
```

## License

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) for the full license text.

## Disclaimer

This is not an officially supported Google product.
