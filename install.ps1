param(
    [string]$PluginRoot = (Join-Path $env:ProgramData 'obs-studio\plugins')
)
$ErrorActionPreference = 'Stop'
$source = Join-Path $PSScriptRoot 'target\release\obs_ntsc_rs.dll'
if (-not (Test-Path -LiteralPath $source)) {
    throw 'Release-DLL fehlt. Zuerst im Projektordner .\build-release.ps1 ausfuehren.'
}
$plugin = Join-Path $PluginRoot 'obs-ntsc-rs'
$bin = Join-Path $plugin 'bin\64bit'
$destination = Join-Path $bin 'obs-ntsc-rs.dll'
$same = $false
if (Test-Path -LiteralPath $destination) {
    $same = (Get-FileHash -LiteralPath $source).Hash -eq (Get-FileHash -LiteralPath $destination).Hash
    if (-not $same) {
        throw "Andere DLL vorhanden: $destination. OBS schliessen und die vorhandene Version selbst sichern. Nichts wurde ueberschrieben."
    }
}
New-Item -ItemType Directory -Path $bin -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $plugin 'data') -Force | Out-Null
if (-not $same) {
    Copy-Item -LiteralPath $source -Destination $destination
}
if ((Get-FileHash -LiteralPath $source).Hash -ne (Get-FileHash -LiteralPath $destination).Hash) {
    throw 'Hashvergleich nach Installation fehlgeschlagen.'
}
Write-Host "Installiert: $destination"
Write-Host 'OBS neu starten. Quelle > Filter > Effektfilter > ntsc-rs (NTSC / VHS).'
if (Get-Process obs64 -ErrorAction SilentlyContinue) {
    Write-Warning 'OBS laeuft noch. Es wurde nicht beendet und keine Szene wurde veraendert.'
}
