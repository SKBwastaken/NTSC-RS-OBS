"""Build the Linux plugin ZIP from an explicit allowlist and audit it."""
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from package_check import privacy_check  # noqa: E402

VERSION = re.search(r'^version = "([^"]+)"', (ROOT / "Cargo.toml").read_text(), re.M)[1]
LIBRARY = ROOT / "target/release/libobs_ntsc_rs.so"
FILES = {
    "obs-ntsc-rs/bin/64bit/obs-ntsc-rs.so": LIBRARY,
    "obs-ntsc-rs/README.txt": ROOT / "packaging/README-Linux.txt",
    "obs-ntsc-rs/LICENSE-GPL-2.0.txt": ROOT / "vendor/obs-studio/COPYING",
    "obs-ntsc-rs/LICENSE-ntsc-rs-MIT.txt": ROOT / "vendor/ntsc-rs/LICENSE-MIT",
    "obs-ntsc-rs/THIRD-PARTY.txt": ROOT / "packaging/THIRD-PARTY.txt",
    "obs-ntsc-rs/data/README.txt": ROOT / "packaging/data/README.txt",
}


def main():
    library = LIBRARY.read_bytes()
    assert library[:4] == b"\x7fELF", "Plugin library is not an ELF file"
    releases = ROOT / "dist/releases"
    releases.mkdir(parents=True, exist_ok=True)
    destination = releases / f"NTSC-RS-OBS-{VERSION}-Linux.zip"
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, source in FILES.items():
            # Fixed metadata: no build time, owner, or host-specific attributes.
            entry = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.create_system = 3
            mode = 0o755 if name.endswith(".so") else 0o644
            entry.external_attr = (0o100000 | mode) << 16
            archive.writestr(entry, source.read_bytes())
    with zipfile.ZipFile(destination) as archive:
        assert set(archive.namelist()) == set(FILES), "Unexpected ZIP contents"
        assert archive.read("obs-ntsc-rs/bin/64bit/obs-ntsc-rs.so") == library
        for entry in archive.infolist():
            privacy_check(entry.filename, archive.read(entry))
            assert not entry.comment, "Unexpected ZIP metadata"
        assert not archive.comment
    report = {
        "result": "PASS", "zip": destination.name, "zip_files": sorted(FILES),
        "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
        "library_sha256": hashlib.sha256(library).hexdigest(),
    }
    (ROOT / "test-output").mkdir(exist_ok=True)
    (ROOT / "test-output/linux-package-check.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
