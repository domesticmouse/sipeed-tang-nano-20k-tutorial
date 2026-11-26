# Sipeed Tang Nano 20K & Amaranth HDL Resources

## Knowledge

- [Amaranth HDL Official Documentation](https://amaranth-lang.org/docs/amaranth/latest/)
  Primary language, standard library (`amaranth.lib.wiring`), and simulator (`amaranth.sim`) reference by the Amaranth maintainers. Use for: authoritative explanations of signals, clock domains, components, testbenches, and Verilog conversion.
- [Sipeed Tang Nano 20K Wiki & Hardware Schematics](https://wiki.sipeed.com/hardware/en/tang/tang-nano-20k/nano-20k.html)
  Official board documentation, pinout diagrams, and KiCad schematics for the `GW2AR-LV18QN88C8/I7` board. Use for: verifying physical pin numbers, voltage levels (`LVCMOS33`), and active-low/active-high peripheral wiring.
- [YosysHQ OSS CAD Suite Releases](https://github.com/YosysHQ/oss-cad-suite-build)
  Prebuilt open-source FPGA toolchain binaries for macOS Apple Silicon (`darwin-arm64`), bundling `yosys`, `nextpnr-himbaechel`, `gowin_pack`, and `openFPGALoader`. Use for: installing and updating the local synthesis, place-and-route, and flashing pipeline.
- [Project Apicula](https://github.com/YosysHQ/apicula)
  Open-source bitstream documentation and packing tools (`gowin_pack`) for Gowin FPGAs. Use for: understanding Gowin `GW2AR-18` device constraints, PLL/IO primitives, and open-source bitstream generation.
- [Lushay Labs Tang Nano Series Tutorials](https://learn.lushaylabs.com/)
  Practical step-by-step Tang Nano hardware tutorials covering UART, displays, and open-source Gowin workflows. Use for: cross-checking board-level wiring, pin constraints, and peripheral bring-up patterns.
- [Project F: FPGA Graphics & Hardware Notes](https://projectf.io/)
  High-signal hardware engineering series covering FPGA video timing, framebuffers, sprites, and digital design fundamentals. Use for: architectural patterns when progressing from LEDs and UART into HDMI graphics and retro gaming.

## Wisdom (Communities)

- [Amaranth GitHub Discussions](https://github.com/amaranth-lang/amaranth/discussions)
  Official Q&A and design forum monitored by Amaranth maintainers and experienced FPGA practitioners. Use for: idiomatic `wiring.Component` patterns, simulator usage, and Verilog interop questions.
- [r/FPGA](https://www.reddit.com/r/FPGA/)
  Active engineering community covering FPGA architecture, timing, synthesis debugging, and board bring-up. Use for: real-world hardware debugging and toolchain troubleshooting.
- [1BitSquared / Open-Source FPGA Discord](https://1bitsquared.com/pages/chat)
  Community chat frequented by open-source FPGA toolchain (Yosys, nextpnr, Amaranth) developers and hobbyists. Use for: live discussion on open-source Gowin support and retro-gaming hardware design.
