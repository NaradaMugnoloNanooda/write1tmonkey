# ============================================================
#  ClipboardTyper — PowerShell Setup & Launcher
#  Run this ONCE as Administrator to install + start silently
# ============================================================
#  Usage:
#    Right-click → "Run with PowerShell"
#    OR in terminal: powershell -ExecutionPolicy Bypass -File setup_and_run.ps1
# ============================================================

$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonFile = Join-Path $ScriptDir "clipboard_typer.py"
$ExeFile    = Join-Path $ScriptDir "dist\clipboard_typer.exe"

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "   ClipboardTyper Setup & Launcher" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# ── Step 1: Check Python ────────────────────────────────────
Write-Host "[1/4] Checking Python installation..." -ForegroundColor Yellow
try {
    $pyVersion = python --version 2>&1
    Write-Host "      Found: $pyVersion" -ForegroundColor Green
} catch {
    Write-Host "      ERROR: Python not found. Install from https://python.org" -ForegroundColor Red
    Pause; exit 1
}

# ── Step 2: Install dependencies ────────────────────────────
Write-Host "[2/4] Installing dependencies (pynput, pyperclip)..." -ForegroundColor Yellow
pip install pynput pyperclip pystray Pillow --quiet
if ($LASTEXITCODE -eq 0) {
    Write-Host "      Dependencies installed (pynput, pyperclip, pystray, Pillow)." -ForegroundColor Green
} else {
    Write-Host "      WARNING: pip install may have had issues." -ForegroundColor Yellow
}

# ── Step 3: Ask user — Run as script OR compile to EXE ──────
Write-Host ""
Write-Host "[3/4] How would you like to run ClipboardTyper?" -ForegroundColor Yellow
Write-Host "      [1] Run as Python script now (quick start)"
Write-Host "      [2] Compile to silent .EXE and run (recommended for daily use)"
Write-Host "      [3] Compile to .EXE only (don't run yet)"
Write-Host ""
$choice = Read-Host "Enter choice (1/2/3)"

if ($choice -eq "2" -or $choice -eq "3") {
    Write-Host "[3/4] Installing PyInstaller + compiling EXE..." -ForegroundColor Yellow
    pip install pyinstaller --quiet

    Push-Location $ScriptDir
    pyinstaller --noconsole --onefile --name "ClipboardTyper" clipboard_typer.py
    Pop-Location

    if (Test-Path $ExeFile) {
        Write-Host "      EXE created: $ExeFile" -ForegroundColor Green
    } else {
        Write-Host "      Build may be at: $ScriptDir\dist\ClipboardTyper.exe" -ForegroundColor Yellow
        $ExeFile = Join-Path $ScriptDir "dist\ClipboardTyper.exe"
    }
}

# ── Step 4: Launch ───────────────────────────────────────────
Write-Host ""
Write-Host "[4/4] Launching ClipboardTyper..." -ForegroundColor Yellow

if ($choice -eq "1") {
    # Run script in a new visible window (shows status/logs)
    Start-Process "python" -ArgumentList "`"$PythonFile`"" -WindowStyle Normal
    Write-Host "      Running as Python script (window open for logs)." -ForegroundColor Green
}
elseif ($choice -eq "2") {
    # Run silent EXE — no window, background only
    Start-Process $ExeFile -WindowStyle Hidden
    Write-Host "      Running silently in background as EXE." -ForegroundColor Green
}
elseif ($choice -eq "3") {
    Write-Host "      EXE compiled. Run manually: $ExeFile" -ForegroundColor Green
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  ClipboardTyper is ACTIVE!" -ForegroundColor Green
Write-Host ""
Write-Host "  Hotkey   : ALT + Z + X"
Write-Host "  Action   : Types your clipboard at human speed"
Write-Host "  Interrupt: Press any key while typing to stop"
Write-Host "  To Kill  : Open Task Manager → ClipboardTyper"
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Optional: Add to Windows Startup (runs on every login)
Write-Host "  Add to Windows Startup so it runs on every login?" -ForegroundColor Yellow
$startup = Read-Host "  (y/n)"
if ($startup -eq "y") {
    $startupFolder = [System.Environment]::GetFolderPath("Startup")

    if ($choice -eq "1") {
        # Create a .bat shortcut in startup for Python script
        $batPath = Join-Path $startupFolder "ClipboardTyper.bat"
        Set-Content -Path $batPath -Value "@echo off`npython `"$PythonFile`""
        Write-Host "  Startup shortcut created (script): $batPath" -ForegroundColor Green
    } else {
        # Copy EXE shortcut to startup
        $shell = New-Object -ComObject WScript.Shell
        $shortcut = $shell.CreateShortcut("$startupFolder\ClipboardTyper.lnk")
        $shortcut.TargetPath = $ExeFile
        $shortcut.WindowStyle = 7  # Minimized/hidden
        $shortcut.Save()
        Write-Host "  Startup shortcut created (EXE): $startupFolder\ClipboardTyper.lnk" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "  Setup complete. You're good to go!" -ForegroundColor Green
Write-Host ""
Pause
