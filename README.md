# NTSC-RS for OBS

**Disclaimer:** This is a vibe-coded proof of concept. Compatibility, stability and performance have not been fully tested. Use at your own risk.

A native Windows OBS filter powered by **ntsc-rs**, bringing live NTSC/VHS effects to your video sources. Includes ntsc-rs controls, JSON preset import/export, and adjustable processing resolution and frame rate.

Currently CPU-based and SDR-only. Adds video latency without delaying audio. Tested with OBS 32.2.2 on Windows.

## Downloads

Get the **Windows installer** or **manual ZIP** from [Releases](https://github.com/SKBwastaken/NTSC-RS-OBS/releases).
Both contain the same plugin. They are unsigned, so Windows may show a warning.

Close OBS before installing. In OBS: **Source → Filters → Effect Filters → + → ntsc-rs (NTSC / VHS)**.
The ZIP includes manual installation instructions.

## Source and licenses

[Build instructions and limitations](docs/BUILD.md). Plugin integration: GPL-2.0-or-later.
The ntsc-rs core and Rust dependencies retain their own licenses; see [vendor notes](vendor/README.md) and [third-party notices](packaging/THIRD-PARTY.txt).
