# Building NTSC-RS for OBS

Native NTSC/VHS effect filter for **OBS Studio 32+** on Windows and Linux.
It uses the real Rust effect core of [ntsc-rs](https://github.com/valadaptive/ntsc-rs),
not a browser source or a shader imitation.

## Usage

1. Install the plugin (see the release downloads) and start OBS.
2. Right-click a video source → **Filters**.
3. Under **Effect Filters** click **+** → **ntsc-rs (NTSC / VHS)**.
4. Start with **Maximum processing height = 480** and **Maximum effect FPS = 30**.
5. Adjust the effect with the regular ntsc-rs controls. Groups can be toggled by checkbox.

The filter exposes 68 OBS properties, including groups, preset and performance options.
The original resolution of the source and the OBS canvas is unchanged.

### Presets

- Export an **ntsc-rs JSON preset** from web.ntsc.rs or ntsc-rs.
- Select it under **ntsc-rs preset (.json)** and press **Import preset**.
- To save, choose a new file under **Export preset to (.json)**, then press
  **Export preset (new file only)**. Existing files are never overwritten.
- Settings are stored in the OBS scene; the imported file is not needed later.
- ntscQT presets and other JSON formats are not compatible.
- On errors, check the filter's status line and OBS log entries tagged `[obs-ntsc-rs]`.

### Limitations

- **CPU effect:** the GPU downscales the source, a background thread processes it,
  and the result is uploaded back to the GPU.
- Default limit: **480 lines / 30 effect FPS** (about 853 × 480 for 16:9).
  Under heavy load, try 240 or 360 lines.
- OBS output can still run at 60 FPS; effect frames are then repeated. A bounded
  queue drops old frames instead of building up delay.
- **Additional, variable video latency.** Audio is not delayed; set an OBS sync
  offset if needed. Latency has not been measured.
- **SDR only.** HDR and unsupported color spaces pass through unchanged.
- Transparency is preserved.
- No long-running tests with game capture, cameras, HDR or many parallel filters.

## Build on Windows

Requirements: Rust with edition 2024 support, Visual Studio 2022 C++ build tools
with the Windows SDK, and OBS Studio 32 installed. Tested with Rust 1.93.1 and MSVC 14.38.

```powershell
.\build-release.ps1
```

Output: `target\release\obs_ntsc_rs.dll`. For a non-default OBS location, set
`$env:OBS_DIR = 'D:\path\to\obs-studio'` first. `build.rs` generates the import
library from the installed `obs.dll`. `build-release.ps1` removes local user and
build paths from the binary.

### Windows packages

Requires Inno Setup 6 and Python:

```powershell
.\package.ps1
```

Output in `dist\releases`: `NTSC-RS-OBS-<version>-Windows-Setup.exe` and
`NTSC-RS-OBS-<version>-Windows.zip`. Both use an explicit file allowlist and are
scanned for local paths and common secret patterns (heuristic, not a guarantee).
`-ZipOnly` builds only the ZIP. The script never uploads anything.

The installer requires administrator rights, installs only this plugin into
ProgramData and never closes OBS. EXE and DLL are not code-signed.

## Build on Linux

The workflow `.github/workflows/linux.yml` builds and tests the Linux version on
Ubuntu 24.04 with OBS from the official OBS PPA. Locally you need OBS 32+ as a
system package, Rust, GCC, Python 3.12 and the SIMDe headers (`libsimde-dev` on Ubuntu):

```sh
cargo build --release --locked --offline
xvfb-run -a python3 tests/obs_smoke.py
python3 packaging/package_linux.py
```

Output: `target/release/libobs_ntsc_rs.so` and
`dist/releases/NTSC-RS-OBS-<version>-Linux.zip`. If `libobs.so.0` is not in the
default library path, set `OBS_LIB_DIR`. Flatpak and Snap OBS are not supported.

## Tests

```powershell
$env:PATH = "C:\Program Files\obs-studio\bin\64bit;$env:PATH"
cargo test --release --locked
cargo clippy --release --all-targets -- -D warnings
cargo fmt --check
python .\tests\obs_smoke.py
python .\tests\package_check.py
python .\tests\installer_check.py
```

`tests/obs_smoke.py` starts its own isolated libobs context (D3D11 on Windows,
OpenGL on Linux) with a generated color-bar image. It never opens user profiles,
scenes, devices or the websocket server. It checks plugin loading, animated
processing, bypass, resolution changes, preset import/export with a Unicode path,
export overwrite protection and clean shutdown. Set `NTSC_PLUGIN_DLL` to test
another plugin file.

`tests/installer_check.py` uses a test-only installer build in isolated folders,
without administrator rights or an uninstall registry entry. The production UAC
flow is not tested automatically.

All Rust dependencies are vendored in `vendor/cargo`; with `CARGO_NET_OFFLINE=true`
Cargo builds without network access.

## Layout and licenses

- `native/filter.c`: OBS registration, properties, downscale, double-buffered GPU readback, upload.
- `src/lib.rs`: effect core binding, worker thread, settings validation, JSON presets, Rust tests.
- `native/bridge.h`: small C/Rust interface.
- `vendor/ntsc-rs`: unmodified ntsc-rs core, commit `8cfc51014092a6dc1da5eb0217bb9ae6516b124e`.
- `vendor/obs-studio`: unmodified OBS 32.0.4 libobs headers, commit `dcdbd2e9048ae66237fdab32dbba72b745b1b9c5`.

Plugin integration: **GPL-2.0-or-later**, see `LICENSE`.
ntsc-rs core: MIT / ISC / Apache-2.0 at your option; license texts are in the vendor folder.
Other Rust dependencies keep their own licenses, see `packaging/THIRD-PARTY.txt`.
This is an unofficial integration project.
