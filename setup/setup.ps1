# quran-video-kit — one-time machine setup (Windows 10/11, PowerShell 5.1+)
# Run from the kit root:   powershell -ExecutionPolicy Bypass -File setup\setup.ps1
# Safe to re-run: every step checks before installing.

$ErrorActionPreference = "Stop"
$Kit = Split-Path -Parent $PSScriptRoot
Write-Host "Kit: $Kit"

# 1) Python
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) {
    Write-Host "Installing Python 3.12 (winget)…"
    winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
    Write-Host "Re-open the terminal so 'python' is on PATH, then run this script again."; exit 1
}
python --version

# 2) ffmpeg with libass (Gyan full build has it)
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Write-Host "Installing ffmpeg (Gyan.FFmpeg full build)…"
    winget install -e --id Gyan.FFmpeg --accept-source-agreements --accept-package-agreements
    Write-Host "Re-open the terminal so 'ffmpeg' is on PATH, then run this script again."; exit 1
}
$filters = ffmpeg -hide_banner -filters 2>$null | Out-String
if ($filters -notmatch " ass ") { throw "This ffmpeg has no libass. Install Gyan.FFmpeg (full build)." }

# 3) Python packages
python -m pip install --upgrade pip
python -m pip install -r "$Kit\setup\requirements.txt"

# 4) Vendor repos (only if the folders are missing, e.g. after a shallow git clone)
$vendor = Join-Path $Kit "vendor"
if (-not (Test-Path "$vendor\quran-data-kfgqpc\hafs\data")) {
    git clone --depth 1 https://github.com/thetruetruth/quran-data-kfgqpc "$vendor\quran-data-kfgqpc"
}
if (-not (Test-Path "$vendor\tafsir-mcp\README.md")) {
    git clone --depth 1 https://github.com/tafsircenter/tafsir-mcp "$vendor\tafsir-mcp"
}

# 5a) Thmanyah fonts are not in the repo (license forbids redistribution).
#     Copy them from the installed Windows fonts if present; otherwise explain where to get them.
$thDir = Join-Path $Kit "assets\fonts\thmanyah"
New-Item -ItemType Directory -Force $thDir | Out-Null
foreach ($src in @((Join-Path $env:LOCALAPPDATA "Microsoft\Windows\Fonts"), "$env:WINDIR\Fonts")) {
    Get-ChildItem $src -Filter "thmanyah*.otf" -ErrorAction SilentlyContinue | ForEach-Object {
        $dst = Join-Path $thDir $_.Name
        if (-not (Test-Path $dst)) { Copy-Item $_.FullName $dst; Write-Host "thmanyah: $($_.Name)" }
    }
}
$needTh = @("thmanyahsans12_medium.otf", "thmanyahsans12_bold.otf", "thmanyahsans12_black.otf") |
    Where-Object { -not (Test-Path (Join-Path $thDir $_)) }
if ($needTh) {
    Write-Warning ("Thmanyah fonts missing: " + ($needTh -join ", "))
    Write-Warning "Download (free) from https://ask.thmanyah.com/hc/en-001/articles/45993930027281-Thmanyah-Font-for-Everyone"
    Write-Warning "then put the .otf files in $thDir and run this script again."
}

# 5b) Install fonts for the current user (so video editors can use the SRT files too)
$userFonts = Join-Path $env:LOCALAPPDATA "Microsoft\Windows\Fonts"
New-Item -ItemType Directory -Force $userFonts | Out-Null
$reg = "HKCU:\Software\Microsoft\Windows NT\CurrentVersion\Fonts"
Get-ChildItem "$Kit\assets\fonts" -Recurse -Include *.ttf,*.otf | ForEach-Object {
    $dst = Join-Path $userFonts $_.Name
    if (-not (Test-Path $dst)) {
        Copy-Item $_.FullName $dst
        New-ItemProperty -Path $reg -Name ($_.BaseName + " (TrueType)") -Value $dst -PropertyType String -Force | Out-Null
        Write-Host "font installed: $($_.Name)"
    }
}

# 6) Claude Code skills (copied into the user's skills folder)
$skills = Join-Path $env:USERPROFILE ".claude\skills"
New-Item -ItemType Directory -Force $skills | Out-Null
foreach ($s in Get-ChildItem "$Kit\skills" -Directory) {
    $dst = Join-Path $skills $s.Name
    if (-not (Test-Path $dst)) { Copy-Item $s.FullName $dst -Recurse; Write-Host "skill installed: $($s.Name)" }
    else { Write-Host "skill exists (left untouched): $($s.Name)" }
}
# tell the Quran skill where this kit lives
Set-Content -Encoding utf8 (Join-Path $skills "quran-recitation-video\KIT_PATH.txt") $Kit

# 7) Browser for headless rendering
$edge = "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe"
if (-not (Test-Path $edge) -and -not (Test-Path "$env:ProgramFiles\Google\Chrome\Application\chrome.exe")) {
    Write-Warning "No Edge/Chrome found. Install one, or set QVK_BROWSER to a Chromium executable."
}
Write-Host "`nSetup finished. Next:  python -I pipeline\s00_check.py projects\kahf-alhassan\config.json"
