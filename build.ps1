# Build Dynamic Island for Windows: portable folder/zip + installer.
#   powershell -ExecutionPolicy Bypass -File build.ps1
# Requires Python 3.10+. The installer step needs Inno Setup 6 (https://jrsoftware.org/isdl.php).
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$version = (python -c "from version import __version__; print(__version__)").Trim()
Write-Host "Building Dynamic Island $version" -ForegroundColor Cyan

python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller

Remove-Item -Recurse -Force build, dist, installer_output -ErrorAction SilentlyContinue

python -m PyInstaller --noconfirm --clean --windowed `
    --name DynamicIsland `
    --icon assets\icon.ico `
    --add-data "assets;assets" `
    --hidden-import winsdk.windows.media.control `
    --hidden-import winsdk.windows.foundation `
    --exclude-module tkinter `
    app.py

# Make sure the packaged app actually starts
$p = Start-Process -FilePath "dist\DynamicIsland\DynamicIsland.exe" -ArgumentList "--selftest" -PassThru
$null = $p.Handle  # keep a handle so ExitCode is available afterwards
if (-not $p.WaitForExit(90000)) { $p.Kill(); throw "Packaged app did not exit within 90s during self-test" }
if ($p.ExitCode -ne 0) { throw "Self-test of the packaged app failed (exit $($p.ExitCode))" }
Write-Host "Packaged app self-test passed" -ForegroundColor Green

New-Item -ItemType Directory -Force installer_output | Out-Null
Compress-Archive -Path "dist\DynamicIsland\*" -DestinationPath "installer_output\DynamicIsland-$version-portable.zip" -Force

$iscc = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($iscc) {
    & $iscc "/DAppVersion=$version" "packaging\DynamicIsland.iss"
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed" }
} else {
    Write-Warning "Inno Setup not found - skipped the installer. The portable zip is in installer_output\."
}

Get-ChildItem installer_output
