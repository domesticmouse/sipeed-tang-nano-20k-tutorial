# Long-Term Targets: Game Boy (DMG) then Commodore 64 (C64)

The learner set two long-term capstone targets in [MISSION.md](../MISSION.md) and [NOTES.md](../NOTES.md): implementing a **Game Boy (DMG)** core first, followed by a **Commodore 64 (C64)** core, keeping all active authoring in Amaranth HDL (`amaranth.lib.wiring.Component`) while continuing to build Verilog reading fluency through the paired even-numbered dissection lessons. Reading, simulating, and porting existing third-party Verilog cores is intentionally deferred as a potential later phase after building the Amaranth-authored systems.

**Implications:**
- Bridge Phase 4 (retro-gaming building blocks) into the Game Boy via microSD/SPI ROM loading and an onboard 64 Mbit SDRAM controller before tackling the SM83 CPU, bus/MBCs, 160×144 PPU, and 4-channel APU.
- Leverage the learner's analog-synth background directly in Phase 6 when implementing the C64's SID (6581/8580) digital synthesizer (oscillators, ADSR envelopes, ring modulation/sync, and resonant filter DSP).
- Keep the odd/even two-lesson cadence across Phases 5–6 so every new subsystem is both simulated/flashed in Amaranth and dissected in generated Verilog, preparing for future third-party Verilog core study.
