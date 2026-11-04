# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

<#
.SYNOPSIS
Run the mock-backend Nuke GUI suite in an existing interactive Windows desktop.
.DESCRIPTION
Use a clean, isolated checkout. This script does not install Nuke or configure
licensing. RunDirectory must be a new directory; it holds dependencies and logs.
An automation service in Session 0 cannot run this script's GUI tests.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$RunDirectory,
    [string]$NukeExecutable = $env:NUKE_EXECUTABLE,
    [string]$NukePython = $env:NUKE_PYTHON,
    [switch]$PreflightOnly,
    [string[]]$PytestArguments = @()
)

$testExit = $null
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$sessionId = (Get-Process -Id $PID).SessionId
if ($sessionId -eq 0 -or -not [Environment]::UserInteractive) {
    throw 'Nuke GUI tests require an active interactive desktop; Session 0/SSM is unsupported.'
}

# An active WTS session can still be locked. Check access to the input desktop
# without sending keys, changing focus, or unlocking the workstation.
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class NukeGuiDesktop {
    [DllImport("user32.dll", SetLastError = true)]
    static extern IntPtr OpenInputDesktop(uint flags, bool inherit, uint access);
    [DllImport("user32.dll", SetLastError = true)]
    static extern bool SwitchDesktop(IntPtr desktop);
    [DllImport("user32.dll")]
    static extern bool CloseDesktop(IntPtr desktop);
    public static bool Available() {
        IntPtr desktop = OpenInputDesktop(0, false, 0x0100);
        if (desktop == IntPtr.Zero) return false;
        try { return SwitchDesktop(desktop); }
        finally { CloseDesktop(desktop); }
    }
}
'@
if (-not [NukeGuiDesktop]::Available()) {
    throw 'The input desktop is unavailable or locked. Connect to the test desktop before running.'
}

# Serialize this runner across sessions. Existing DCC processes are an additional
# busy-host guard for other tools that do not participate in this mutex.
$mutex = New-Object System.Threading.Mutex($false, 'Global\DeadlineNukeGuiTests')
$locked = $false
$originalEnvironment = @{}
foreach ($name in 'NUKE_EXECUTABLE', 'HATCH_DATA_DIR', 'NUKE_SUBMITTER_UI_PYTHONPATH') {
    $originalEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}
try {
    try { $locked = $mutex.WaitOne(0) }
    catch [System.Threading.AbandonedMutexException] { $locked = $true }
    if (-not $locked) { throw 'Another Nuke GUI test runner is using this workstation.' }
    $busy = @(Get-Process | Where-Object {
        $_.SessionId -ne 0 -and $_.ProcessName -match '^(Nuke.*|Cinema.*|Blender|Maya)$'
    })
    if ($busy.Count) {
        throw "A DCC session is already in use; coordinate before testing: $($busy.ProcessName -join ', ')"
    }

    if (Test-Path -LiteralPath $RunDirectory) {
        throw 'RunDirectory already exists. Choose a new path to preserve previous logs and dependencies.'
    }
    $runRoot = (New-Item -ItemType Directory -Path $RunDirectory).FullName
    Start-Transcript -Path (Join-Path $runRoot 'runner.log') | Out-Null
    try {
        Get-CimInstance Win32_OperatingSystem | Select-Object Caption, Version, BuildNumber | Format-List
        Write-Output "Interactive session: $sessionId"
        & query.exe user
        if (-not $NukeExecutable) {
            $NukeExecutable = Get-ChildItem "$env:ProgramFiles\Nuke*\Nuke*.exe" -ErrorAction SilentlyContinue |
                Where-Object Name -Match '^Nuke\d+\.\d+\.exe$' |
                Sort-Object { [version](($_.Directory.Name -replace '^Nuke', '') -replace 'v', '.') } -Descending |
                Select-Object -First 1 -ExpandProperty FullName
        }
        if (-not $NukeExecutable -or -not (Test-Path -LiteralPath $NukeExecutable -PathType Leaf)) {
            throw 'No GUI Nuke installation found. Supply a licensed Nuke install and NUKE_EXECUTABLE.'
        }
        $NukeExecutable = (Resolve-Path -LiteralPath $NukeExecutable).Path
        if (-not $NukePython) {
            $NukePython = Join-Path (Split-Path -Parent $NukeExecutable) 'python.exe'
        }
        if (-not (Test-Path -LiteralPath $NukePython -PathType Leaf)) {
            throw 'Nuke bundled Python was not found. Supply NUKE_PYTHON.'
        }
        $NukePython = (Resolve-Path -LiteralPath $NukePython).Path
        Write-Output "Nuke executable: $NukeExecutable"
        Write-Output "Nuke Python: $NukePython"
        Write-Output 'Licensing must already be configured for this desktop user; this runner does not change it.'
        if ($PreflightOnly) { return }
        $hatch = (Get-Command hatch -ErrorAction Stop).Source
        $env:NUKE_EXECUTABLE = $NukeExecutable
        $env:HATCH_DATA_DIR = Join-Path $runRoot 'hatch-data'
        $dependencies = Join-Path $runRoot 'nuke-dependencies'
        Push-Location $repoRoot
        try {
            # Install into run artifacts, never Nuke's site-packages or the user profile.
            # Continue is required: Windows PowerShell treats native stderr as errors,
            # including ordinary pip/Hatch/mock-server progress.
            $ErrorActionPreference = 'Continue'
            & $NukePython -m pip install --target $dependencies "$repoRoot[console]" *> (Join-Path $runRoot 'dependencies.log')
            $dependencyExit = $LASTEXITCODE
            if ($dependencyExit -ne 0) { throw "Dependency setup failed ($dependencyExit); see dependencies.log." }
            # Only the launched Nuke inherits this path. Passing it as pytest's
            # PYTHONPATH makes pip skip installing dependencies into Hatch and
            # bypasses pywin32's .pth initialization in the test environment.
            $env:NUKE_SUBMITTER_UI_PYTHONPATH = $dependencies
            & $hatch run integ-xa11y:test test/nuke_submitter_ui "--basetemp=$runRoot\pytest" "--junitxml=$runRoot\results.xml" @PytestArguments *> (Join-Path $runRoot 'pytest.log')
            $testExit = $LASTEXITCODE
            Write-Output "GUI suite exit code: $testExit; logs: $runRoot"
        }
        finally { Pop-Location }
    }
    finally { Stop-Transcript | Out-Null }
}
finally {
    foreach ($name in $originalEnvironment.Keys) {
        [Environment]::SetEnvironmentVariable($name, $originalEnvironment[$name], 'Process')
    }
    if ($locked) { $mutex.ReleaseMutex() }
    $mutex.Dispose()
}
if ($null -ne $testExit) { exit $testExit }
