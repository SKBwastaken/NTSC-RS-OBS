# ntsc-rs für OBS

Nativer NTSC-/VHS-Effektfilter für **OBS Studio 32, Windows**.
Verwendet den echten Rust-Effektkern von [ntsc-rs](https://github.com/valadaptive/ntsc-rs),
keine Browserquelle und keine Shader-Nachbildung.

## Benutzen

Standardpfad nach Installation:

`C:\ProgramData\obs-studio\plugins\obs-ntsc-rs\bin\64bit\obs-ntsc-rs.dll`

1. OBS starten oder neu starten.
2. Rechtsklick auf eine Videoquelle → **Filter**.
3. Unter **Effektfilter** auf **+** → **ntsc-rs (NTSC / VHS)**.
4. Zunächst **Maximum processing height = 480**, **Maximum effect FPS = 30** verwenden.
5. Effekt über die normalen ntsc-rs-Regler anpassen. Gruppen lassen sich per Checkbox abschalten.

Die Oberfläche übernimmt die englischen Bezeichnungen und Beschreibungen von ntsc-rs.
Es gibt 68 OBS-Eigenschaften einschließlich Gruppen, Preset- und Leistungsoptionen.
Die Originalauflösung der Quelle und des OBS-Canvas bleibt unverändert.

### Presets

- Auf web.ntsc.rs oder in ntsc-rs ein **ntsc-rs-JSON-Preset** exportieren.
- Im Filter unter **ntsc-rs preset (.json)** auswählen und **Import preset** drücken.
- Zum Speichern unter **Export preset to (.json)** einen neuen Dateinamen wählen,
  dann **Export preset (new file only)** drücken.
- Vorhandene Dateien werden absichtlich **nicht überschrieben**.
- Einstellungen werden direkt in der OBS-Szene gespeichert. Die importierte Datei
  muss für spätere OBS-Starts nicht vorhanden sein.
- ntscQT-Presets und andere JSON-Formate sind nicht kompatibel.
- Bei Fehlern die Statuszeile im Filter und den OBS-Logeintrag `[obs-ntsc-rs]` prüfen.

### Grenzen

- **CPU-Effekt:** Die GPU skaliert die Quelle herunter. Ein Hintergrundthread
  verarbeitet das Bild, anschließend lädt OBS das Ergebnis wieder auf die GPU.
- Standard: maximal **480 Zeilen / 30 Effekt-FPS**. Bei 16:9 sind das etwa 853 × 480 Pixel.
  Bei hoher Last zunächst auf 240 oder 360 Zeilen reduzieren.
- Die OBS-Ausgabe kann weiterhin mit 60 FPS laufen; Effektbilder werden dann wiederholt.
  Eine begrenzte Warteschlange verwirft ältere Bilder statt immer mehr Verzögerung aufzubauen.
- **Zusätzliche, variable Videoverzögerung:** Readback und Verarbeitung brauchen Zeit.
  Audio wird nicht verzögert. Für Lippen-/Audio-Synchronität gegebenenfalls OBS-Sync-Offset
  anhand einer Testaufnahme einstellen. Eine feste Latenz wurde nicht vermessen.
- **Nur SDR.** HDR bzw. nicht unterstützte Farbräume werden unverändert durchgereicht.
- Transparenz bleibt erhalten; der Effekt verschiebt nicht die Alpha-Maske selbst.
- Kein Dauertest mit Spieleaufnahme, Kamera, HDR oder mehreren parallelen Filtern.
  Die vorhandenen OBS-Szenen wurden nicht verändert.

## Installation / Entfernen

Für eine erneute Installation aus dem Projektordner:

```powershell
.\install.ps1
```

Das Skript prüft den SHA-256-Hash. Eine andere bereits vorhandene Plugin-DLL
wird nicht ersetzt. Bei einem Update OBS schließen und die alte DLL zunächst selbst sichern.
Falls der Pluginordner nicht beschreibbar ist, das Skript als Administrator ausführen.
Portable OBS-Installationen brauchen ihren eigenen Pluginpfad, nicht diesen ProgramData-Pfad.

Zum Entfernen OBS schließen und nur den Ordner
`C:\ProgramData\obs-studio\plugins\obs-ntsc-rs` entfernen.
Keine anderen Pluginordner oder OBS-Einstellungen löschen.

## Bauen

Voraussetzungen: Rust/Cargo mit Edition-2024-Unterstützung, Visual Studio 2022
mit C++-/Windows-SDK-Tools und C11-Atomics-Unterstützung sowie OBS 32 x64.
Getestet mit Rust 1.93.1 und MSVC 14.38.

```powershell
Set-Location 'path\to\NTSC-RS-OBS'
.\build-release.ps1
```

Ausgabe: `target\release\obs_ntsc_rs.dll`.
Bei abweichender OBS-Installation vorher `$env:OBS_DIR = 'D:\Pfad\obs-studio'` setzen.
`build.rs` erzeugt die Importbibliothek aus der installierten `obs.dll`.
Die offiziellen OBS-Header liegen fest versioniert unter `vendor\obs-studio`.
OBS selbst wird nicht gebaut und nicht verändert.
Die gesperrten Rust-Abhängigkeiten sind unter `vendor/cargo` enthalten.
Mit `$env:CARGO_NET_OFFLINE = 'true'` baut Cargo ohne Netzwerkzugriff.

Lokale Downloadpakete (Inno Setup 6 und Python erforderlich):

```powershell
.\package.ps1
```

Ausgabe unter `dist\releases`:

- `NTSC-RS-OBS-0.1.0-Windows-Setup.exe`: Installer mit Deinstallation.
- `NTSC-RS-OBS-0.1.0-Windows.zip`: manuelles Kopieren des Pluginordners.

Die separate öffentliche Anleitung `packaging\README.txt` enthält den
Proof-of-Concept-/Vibe-Coding-Hinweis. Die Downloads enthalten dieselbe DLL,
Lizenzhinweise und keine lokalen technischen Handoffs oder PDB-Dateien.
EXE und DLL sind nicht codesigniert; Windows kann eine SmartScreen-Warnung anzeigen.
Der Installer verlangt Administratorrechte und installiert nur dieses Plugin nach
ProgramData. Er beendet OBS niemals automatisch.

`build-release.ps1` anonymisiert eingebettete Benutzer-/Buildpfade.
`package.ps1` verwendet eine feste Dateiliste und prüft die fertigen Pakete auf
bekannte persönliche Kennungen, lokale Pfade und gängige Secret-Muster.
Diese Prüfung ist heuristisch, keine absolute Garantie.
`-ZipOnly` baut und prüft nur das ZIP.
Für eine öffentliche Weitergabe müssen passende Quellen und Lizenzhinweise
bereitstehen. Es wird nichts automatisch hochgeladen oder auf GitHub veröffentlicht.

Zusätzliche Pakettests:

```powershell
python .\tests\package_check.py
python .\tests\installer_check.py
```

Der Installertest verwendet ausschließlich eigene Testordner, keine
Administratorrechte und keinen Windows-Deinstallationseintrag. Die OBS-Prozesssperre
ist nur in diesem separaten Testbuild ausgenommen; die öffentliche EXE prüft sie immer.
Der produktive UAC-Dialog wurde nicht automatisiert getestet.

## Tests

```powershell
$env:PATH = "$env:OBS_DIR\bin\64bit;C:\Program Files\obs-studio\bin\64bit;$env:PATH"
cargo test --release --locked
cargo clippy --release --all-targets -- -D warnings
cargo fmt --check
python .\tests\obs_smoke.py
```

Der Python-Test startet einen eigenen **libobs-/D3D11-Kontext** mit einem erzeugten
Farbbalkenbild. Er öffnet keine Benutzerprofile, Szenen, Geräte oder Websocket-Verbindung.
Mit `NTSC_PLUGIN_DLL` lässt sich eine andere DLL, beispielsweise die installierte, testen.
Ergebnisse: `test-output\report.json`, `before.png`, `after.png`.
Für jeden Test wird eine neue Presetdatei erstellt.

Verifiziert mit der anonymisierten Release-DLL und OBS **32.2.2**:

- 4 Rust-Tests, Clippy und Formatprüfung bestanden.
- Plugin lädt, verarbeitet echte GPU-Bilder und erzeugt animiertes Rauschen.
- 30 verschiedene Effektbilder in 60 Ausgabe-Frames bei 640 × 480 / 60 FPS.
- Mittlere OBS-Renderzeit im letzten Test etwa **0,49 ms**.
  Das ist weder CPU-Verarbeitungszeit noch Ende-zu-Ende-Latenz.
- Bypass, interne Auflösungsänderung, Unicode-Presetpfad, Import/Export,
  Überschreibschutz und sauberes Beenden bestanden.
- Kein automatisierter Test der Qt-Filteroberfläche im normalen OBS-Fenster.

## Aufbau und Lizenzen

- `native/filter.c`: OBS-Registrierung, Eigenschaften, Downscale, doppelter GPU-Readback, Upload.
- `src/lib.rs`: Effektkern-Anbindung, Worker, Einstellungsvalidierung, JSON-Presets und Rust-Tests.
- `native/bridge.h`: kleine C-/Rust-Schnittstelle.
- `vendor/ntsc-rs`: unveränderter Effektkern, Commit `8cfc51014092a6dc1da5eb0217bb9ae6516b124e`.
- `vendor/obs-studio`: unveränderte OBS-32.0.4-Header, Commit `dcdbd2e9048ae66237fdab32dbba72b745b1b9c5`.

Plugin-Anbindung: **GPL-2.0-or-later**, siehe `LICENSE`.
ntsc-rs-Kern: MIT / ISC / Apache-2.0 nach Wahl, Lizenztexte im Vendorordner.
Die GUI-, OpenFX- und After-Effects-Anwendungen von ntsc-rs werden nicht mitgebaut.
Weitere Rust-Abhängigkeiten und Versionen stehen in `Cargo.lock`; deren eigene Lizenzen gelten zusätzlich.
Dies ist ein lokales, inoffizielles Integrationsprojekt.
