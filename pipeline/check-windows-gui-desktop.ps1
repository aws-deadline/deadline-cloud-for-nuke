# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

# Inspect desktop access without sending synthetic input or changing focus.
$ErrorActionPreference = 'Stop'
$sessionId = (Get-Process -Id $PID).SessionId
Get-CimInstance Win32_OperatingSystem | Select-Object Caption, Version, BuildNumber | Format-List
Write-Output "Process session: $sessionId"
Write-Output "UserInteractive: $([Environment]::UserInteractive)"
& query.exe user

Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class WindowsGuiDesktopProbe {
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
$available = [WindowsGuiDesktopProbe]::Available()
Write-Output "Unlocked input desktop available: $available"
if ($sessionId -eq 0 -or -not [Environment]::UserInteractive -or -not $available) {
    throw 'This runner cannot drive real xa11y GUI tests. An unlocked interactive Windows runner is required.'
}
Write-Output 'Desktop preflight passed. Nuke installation and licensed GUI test execution are still required.'
# GitHub's PowerShell wrapper otherwise returns a native command's stale exit code.
exit 0
