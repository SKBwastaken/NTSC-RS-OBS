param(
    [switch]$ZipOnly,
    [string]$InnoCompiler,
    [string]$Python = 'python'
)
$ErrorActionPreference = 'Stop'
$source = Join-Path $PSScriptRoot 'target\release\obs_ntsc_rs.dll'
if (-not (Test-Path -LiteralPath $source)) { throw 'Release DLL missing. Run .\build-release.ps1 first.' }
$package = Join-Path $PSScriptRoot 'dist\obs-ntsc-rs'
$bin = Join-Path $package 'bin\64bit'
$data = Join-Path $package 'data'
$releases = Join-Path $PSScriptRoot 'dist\releases'
New-Item -ItemType Directory -Path $bin, $data -Force | Out-Null
New-Item -ItemType Directory -Path $releases -Force | Out-Null
Copy-Item -LiteralPath $source -Destination (Join-Path $bin 'obs-ntsc-rs.dll')
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'packaging\README.txt') -Destination (Join-Path $package 'README.txt')
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'vendor\obs-studio\COPYING') -Destination (Join-Path $package 'LICENSE-GPL-2.0.txt')
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'vendor\ntsc-rs\LICENSE-MIT') -Destination (Join-Path $package 'LICENSE-ntsc-rs-MIT.txt')
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'packaging\data\README.txt') -Destination (Join-Path $data 'README.txt')
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'packaging\THIRD-PARTY.txt') -Destination (Join-Path $package 'THIRD-PARTY.txt')
$versionLine = Select-String -LiteralPath (Join-Path $PSScriptRoot 'Cargo.toml') -Pattern '^version = "([^"]+)"' | Select-Object -First 1
if (-not $versionLine) { throw 'Package version not found.' }
$version = $versionLine.Matches[0].Groups[1].Value

# Package only explicitly named public files. Never recursively include old
# staging contents, technical docs, debug symbols, scripts, or machine paths.
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zipPath = Join-Path $releases "NTSC-RS-OBS-$version-Windows.zip"
$stream = [IO.File]::Open($zipPath, [IO.FileMode]::Create)
$zip = New-Object IO.Compression.ZipArchive($stream, [IO.Compression.ZipArchiveMode]::Create)
try {
    $files = @('bin\64bit\obs-ntsc-rs.dll', 'README.txt', 'LICENSE-GPL-2.0.txt',
               'LICENSE-ntsc-rs-MIT.txt', 'THIRD-PARTY.txt', 'data\README.txt')
    foreach ($relative in $files) {
        $entryName = 'obs-ntsc-rs/' + $relative.Replace('\', '/')
        [IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
            $zip, (Join-Path $package $relative), $entryName,
            [IO.Compression.CompressionLevel]::Optimal) | Out-Null
    }
} finally {
    $zip.Dispose()
    $stream.Dispose()
}
if (-not $ZipOnly) {
    if (-not $InnoCompiler) {
        $candidates = @(
            (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe'),
            (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'),
            (Join-Path $env:ProgramFiles 'Inno Setup 6\ISCC.exe')
        )
        $InnoCompiler = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    }
    if (-not $InnoCompiler) { throw 'Inno Setup not found. Install it or use -ZipOnly.' }
    & $InnoCompiler "/DPluginVersion=$version" (Join-Path $PSScriptRoot 'packaging\installer.iss')
    if ($LASTEXITCODE -ne 0) { throw 'Installer compilation failed.' }
}
$auditArgs = @((Join-Path $PSScriptRoot 'tests\package_check.py'))
if ($ZipOnly) { $auditArgs += '--zip-only' }
& $Python @auditArgs
if ($LASTEXITCODE -ne 0) { throw 'Package privacy/integrity checks failed. Do not publish these files.' }
Write-Host "Package: $package"
Write-Host "Downloads: $releases"
Write-Host 'Created locally only. Nothing was pushed, uploaded or released.'
Write-Host 'Publish the matching source code (GPL) alongside any public release.'
