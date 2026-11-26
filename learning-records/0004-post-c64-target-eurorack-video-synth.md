# Post-C64 Target: Eurorack Audio-to-Video Synthesizer

The learner added a Phase 7 post-C64 capstone target in [MISSION.md](../MISSION.md) and [NOTES.md](../NOTES.md): building a Eurorack module that generates HDMI video from audio (and optional CV) signals on the Tang Nano 20K, retaining the paired Amaranth-to-Verilog two-lesson cadence.

**Implications:**
- Because the GW2AR-18 has no internal ADC and uses strictly 3.3 V digital I/O, audio input uses an external stereo I2S ADC (`PCM1808`, AC-coupled, MCLK derived from 27 MHz) and DC-coupled Eurorack CV/knobs use an external SPI ADC (`MCP3208`), both protected and scaled by a TL074 analog front-end powered from Eurorack ±12 V (with a dedicated 12 V → 5 V buck rail for the Tang Nano 20K and PCM1808 analog supply).
- Directly unifies the learner's analog-synth circuit experience with Phases 3–6 FPGA building blocks (HDMI TMDS video, SPI, Block RAM ring buffers, DSP envelopes, and 64 Mbit SDRAM framebuffers for video feedback/phosphor persistence).
- Sequencing it after Phase 6 (C64) lets Phase 7 reuse proven HDMI, SPI, DSP, and SDRAM modules while focusing on analog-to-digital interfacing and real-time video synthesis.
