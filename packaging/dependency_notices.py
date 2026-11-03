"""Generate a public notice file without metadata paths or builder identity."""
import json
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
result = subprocess.run(
    ["cargo", "metadata", "--format-version", "1", "--locked"],
    cwd=root, capture_output=True, text=True, check=True,
)
metadata = json.loads(result.stdout)
parts = [
    "NTSC-RS for OBS - third-party dependency notices",
    "Includes runtime and build-time Rust dependencies.",
    "ntsc-rs and OBS license notices are provided as separate files.",
]
mit_terms = """Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE."""
for package in sorted(metadata["packages"], key=lambda p: p["name"]):
    if not package.get("source"):
        continue
    folder = Path(package["manifest_path"]).parent
    license_files = sorted(p for p in folder.iterdir() if p.is_file()
                           and p.name.upper().startswith(("LICENSE", "LICENCE", "COPYING")))
    parts.append("\n" + "=" * 72)
    parts.append(f"{package['name']} {package['version']} | {package.get('license', 'see license')}")
    if not license_files:
        if package.get("license") != "MIT":
            raise RuntimeError(f"No license files found for {package['name']}")
        # Some MIT crates (e.g. hifijson 0.5.0) omit a standalone license file.
        # Keep their declared license and author attribution without inventing
        # an upstream copyright year or exposing author email metadata.
        authors = ", ".join(author.split("<")[0].strip() for author in package.get("authors", []))
        parts.append("Attribution (Cargo package metadata): " + authors)
        parts.append("This crate declares MIT but ships no separate license file.\nMIT terms:\n" + mit_terms)
    for path in license_files:
        parts.append(f"\n--- {path.name} ---\n")
        parts.append(path.read_text(encoding="utf-8"))

destination = root / "packaging" / "THIRD-PARTY.txt"
destination.write_text("\n".join(parts) + "\n", encoding="utf-8")
print(f"Generated notices for {len(metadata['packages']) - 2} dependency packages")
