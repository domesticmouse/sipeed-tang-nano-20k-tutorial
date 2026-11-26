---
title: "Tang Nano 20K Pinout & Toolchain Sheet"
page_title: "Pinout & Toolchain — Tang Nano 20K with Amaranth HDL"
nav_id: "pinout"
nav_label: "Pinout & CLI"
badge: "Reference • GW2AR-LV18QN88C8/I7"
subtitle: "Verified QN88 onboard pin mappings, electrical levels, and macOS OSS CAD Suite commands for quick desk lookup."
card:
  title: "**Tang Nano 20K Pinout & Toolchain Sheet**"
  summary: "Board specs, verified QN88 pin numbers (clock, LEDs, buttons, UART), and OSS CAD Suite commands."
---

## 1. Board & Silicon Specs {#specs}

Table: Tang Nano 20K core hardware specifications.

| Parameter | Specification | Notes |
| :--- | :--- | :--- |
| **FPGA Part** | `GW2AR-LV18QN88C8/I7` | Gowin Arora `GW2A-18C` family (`QN88` package) |
| **Logic Fabric** | 20,736 LUT4 • 15,552 Flip-Flops | Integrated 64 Mbit SDRAM on-chip |
| **System Clock** | 27 MHz onboard crystal | Package pin `4` (`LVCMOS33`) |
| **USB Bridge** | Bouffalo Lab `BL616` | Provides USB-JTAG flashing and 115200-baud USB-UART |

## 2. Verified Onboard Pinout {#pinout}

Table: Verified `QN88` pin assignments used across Phases 1–2 (LEDs, Buttons, and USB-UART).

| Signal | Pin | Polarity | `IO_PORT` Attributes | Peripheral |
| :--- | :--- | :--- | :--- | :--- |
| `clk` | `4` | Rising edge | `IO_TYPE=LVCMOS33 PULL_MODE=UP` | 27 MHz crystal oscillator |
| `rst` / `s1` | `88` | Active-high (`1` = pressed) | `IO_TYPE=LVCMOS33 PULL_MODE=DOWN` | User button `S1` (`KEY1`) |
| `s2` | `87` | Active-high (`1` = pressed) | `IO_TYPE=LVCMOS33 PULL_MODE=DOWN` | User button `S2` (`KEY2`) |
| `leds[0]` | `15` | Active-low (`0` = lit) | `IO_TYPE=LVCMOS33 PULL_MODE=UP DRIVE=8` | Onboard LED 0 |
| `leds[1]` | `16` | Active-low (`0` = lit) | `IO_TYPE=LVCMOS33 PULL_MODE=UP DRIVE=8` | Onboard LED 1 |
| `leds[2]` | `17` | Active-low (`0` = lit) | `IO_TYPE=LVCMOS33 PULL_MODE=UP DRIVE=8` | Onboard LED 2 |
| `leds[3]` | `18` | Active-low (`0` = lit) | `IO_TYPE=LVCMOS33 PULL_MODE=UP DRIVE=8` | Onboard LED 3 |
| `leds[4]` | `19` | Active-low (`0` = lit) | `IO_TYPE=LVCMOS33 PULL_MODE=UP DRIVE=8` | Onboard LED 4 |
| `leds[5]` | `20` | Active-low (`0` = lit) | `IO_TYPE=LVCMOS33 PULL_MODE=UP DRIVE=8` | Onboard LED 5 |
| `uart_tx` | `69` | Idle high | `IO_TYPE=LVCMOS33` | FPGA TX → BL616 RX |
| `uart_rx` | `70` | Idle high | `IO_TYPE=LVCMOS33` | BL616 TX → FPGA RX |

## 3. Open-Source Build & Flash Pipeline (macOS `arm64`) {#pipeline}

Every lesson exports Verilog via `amaranth.back.verilog`, synthesizes with `yosys`, places and routes with `nextpnr-himbaechel`, packs with `gowin_pack`, and loads SRAM over USB-C via `openFPGALoader`:

```bash caption="Four-step open-source Gowin bitstream pipeline"
yosys -p "read_verilog build/blinky.v; synth_gowin -top blinky -json build/blinky.json"
nextpnr-himbaechel \
  --json build/blinky.json \
  --write build/blinky_pnr.json \
  --device GW2AR-LV18QN88C8/I7 \
  --vopt family=GW2A-18C \
  --vopt cst=tangnano20k.cst
gowin_pack -d GW2A-18C -o build/blinky.fs build/blinky_pnr.json
openFPGALoader -b tangnano20k build/blinky.fs
```
