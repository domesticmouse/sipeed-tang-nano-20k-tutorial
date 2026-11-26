---
title: "Sipeed Tang Nano 20K with Amaranth HDL"
page_title: "Sipeed Tang Nano 20K Course — Amaranth HDL & Verilog by Assimilation"
nav_id: "index"
badge: "Interactive Hardware Course"
subtitle: "Learn FPGA design from scratch on a breadboarded Tang Nano 20K: write clean hardware in Amaranth HDL, verify with pytest, and dissect the generated Verilog."
---

Welcome! This hands-on course takes you from software, C/MCU tinkering, and analog synth circuits to building real FPGA hardware on the **Sipeed Tang Nano 20K** (`GW2AR-LV18QN88C8/I7`). Each lesson builds a runnable, tested companion design under `apps/` following a concrete hardware progression: **LEDs & Buttons → USB-UART → HDMI Video → Retro Gaming → Game Boy (DMG) → Commodore 64**.

:::callout title="Course Workflow: Amaranth First, Verilog by Assimilation"
1. **Write** hardware modules in Python using Amaranth's `wiring.Component` and explicit `m.d.sync` / `m.d.comb` domains.
2. **Simulate & verify** clock-cycle behavior locally with `amaranth.sim` and `pytest`.
3. **Dissect** the generated Verilog (`amaranth.back.verilog`) line-by-line so you learn to read real Verilog naturally before studying external cores.
4. **Synthesize & flash** onto your breadboarded Tang Nano 20K using OSS CAD Suite (`yosys`, `nextpnr-himbaechel`, `gowin_pack`, `openFPGALoader`).
:::

## Lessons

{{widget:lesson-cards}}

## Reference Sheets

{{widget:reference-cards}}
