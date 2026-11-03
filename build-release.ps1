$ErrorActionPreference = 'Stop'
$previous = $env:CARGO_ENCODED_RUSTFLAGS
try {
    $flags = @()
    if ($previous) { $flags += $previous.Split([char]31) }
    $flags += "--remap-path-prefix=$env:USERPROFILE=builder"
    # Rust applies the last matching remap first. Keep the specific project
    # prefix after the general home prefix so desktop/project paths disappear.
    $flags += "--remap-path-prefix=$PSScriptRoot=ntsc-rs-obs"
    $flags += '-Clink-arg=/PDBALTPATH:obs_ntsc_rs.pdb'
    $env:CARGO_ENCODED_RUSTFLAGS = $flags -join [char]31
    Push-Location $PSScriptRoot
    try {
        cargo build --release --locked
        if ($LASTEXITCODE -ne 0) { throw 'Release build failed.' }
    } finally {
        Pop-Location
    }
} finally {
    $env:CARGO_ENCODED_RUSTFLAGS = $previous
}
