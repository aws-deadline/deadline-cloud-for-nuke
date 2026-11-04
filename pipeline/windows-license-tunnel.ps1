# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

param([switch]$Cleanup)
$ErrorActionPreference = 'Stop'
$config = Join-Path $env:RUNNER_TEMP 'nuke-windows-license-config'
$log = Join-Path $env:RUNNER_TEMP 'nuke-windows-license-ssm.log'
$state = Join-Path $env:RUNNER_TEMP 'nuke-windows-license-state.json'
$env:AWS_CONFIG_FILE = $config
$env:AWS_PAGER = ''

function Write-TunnelFailureCategory {
    # Keep private SSM connection details out of uploaded GUI evidence.
    $text = (Get-Content -LiteralPath $log, "$log.error" -Raw -ErrorAction SilentlyContinue) -join "`n"
    $category = 'No recognized SSM error; inspect the private runner tunnel logs.'
    foreach ($known in 'AccessDenied', 'ExpiredToken', 'TargetNotConnected', 'InvalidDocument', 'SessionManagerPlugin', 'UnauthorizedOperation') {
        if ($text -match [regex]::Escape($known)) { $category = $known; break }
    }
    "License tunnel failure: $category" |
        Tee-Object -FilePath (Join-Path $env:RUNNER_TEMP 'nuke-windows-license-status.txt') |
        Write-Output
}

if ($Cleanup) {
    try {
        if (Test-Path -LiteralPath $log) {
            $match = [regex]::Match((Get-Content -LiteralPath $log -Raw), 'SessionId: ([A-Za-z0-9._-]+)')
            if ($match.Success) {
                & aws ssm terminate-session --session-id $match.Groups[1].Value --profile license *> $null
                if ($LASTEXITCODE -ne 0) { throw 'Remote license-session termination failed.' }
            }
        }
    } finally {
        if (Test-Path -LiteralPath $state) {
            $owned = Get-Content -LiteralPath $state -Raw | ConvertFrom-Json
            $process = Get-Process -Id $owned.pid -ErrorAction SilentlyContinue
            # Never kill a PID that has been reused since the owned process started.
            if ($process -and $process.StartTime.ToUniversalTime().Ticks -eq $owned.start_ticks) {
                & taskkill.exe /PID $owned.pid /T /F *> $null
            }
        }
    }
    Remove-Item -LiteralPath $config, $log, "$log.error", $state -ErrorAction SilentlyContinue
    exit 0
}

foreach ($name in 'AWS_REGION', 'LICENSE_ROLE_ARN', 'BASTION_INSTANCE_TAG') {
    if (-not [Environment]::GetEnvironmentVariable($name, 'Process')) {
        throw "Missing license configuration: $name"
    }
}
if ($env:AWS_REGION -match '[\r\n]' -or $env:LICENSE_ROLE_ARN -match '[\r\n]') {
    throw 'License configuration must be single-line.'
}
Get-Command session-manager-plugin -ErrorAction Stop | Out-Null
@"
[profile license]
role_arn = $env:LICENSE_ROLE_ARN
credential_source = Environment
region = $env:AWS_REGION
"@ | Set-Content -LiteralPath $config
# Use the existing CI license role, bastion, document and Foundry RLM port.
$instances = & aws ec2 describe-instances --profile license `
    --filters "Name=tag:Name,Values=$env:BASTION_INSTANCE_TAG" 'Name=instance-state-name,Values=running' `
    --query 'Reservations[].Instances[].InstanceId' --output json 2>"$log.error"
if ($LASTEXITCODE -ne 0) { Write-TunnelFailureCategory; throw 'License bastion lookup failed.' }
$bastions = @($instances | ConvertFrom-Json)
if ($bastions.Count -ne 1 -or $bastions[0] -notmatch '^i-[0-9a-f]{8}([0-9a-f]{9})?$') {
    throw 'Expected exactly one running license bastion.'
}
if (Get-NetTCPConnection -State Listen -LocalPort 6101 -ErrorAction SilentlyContinue) {
    throw 'The Foundry license port is already in use.'
}
$process = Start-Process aws -ArgumentList @(
    'ssm', 'start-session', '--target', $bastions[0],
    '--document-name', 'DccInteg-PortForwardToLicenseServer',
    '--parameters', 'portNumber=6101,localPortNumber=6101', '--profile', 'license'
) -WindowStyle Hidden -RedirectStandardOutput $log -RedirectStandardError "$log.error" -PassThru
@{pid = $process.Id; start_ticks = $process.StartTime.ToUniversalTime().Ticks} |
    ConvertTo-Json | Set-Content -LiteralPath $state
$deadline = [DateTime]::UtcNow.AddSeconds(60)
while ([DateTime]::UtcNow -lt $deadline) {
    if ($process.HasExited) {
        Write-TunnelFailureCategory
        throw 'License tunnel exited before readiness.'
    }
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        if ($client.ConnectAsync('127.0.0.1', 6101).Wait(1000) -and $client.Connected) {
            Write-Output 'Foundry local license forwarder is listening.'
            exit 0
        }
    } catch {
        # A faulted ConnectAsync task wraps the socket error in AggregateException.
    } finally {
        $client.Dispose()
    }
    Start-Sleep -Milliseconds 250
}
Write-TunnelFailureCategory
throw 'The Foundry license tunnel did not become ready within 60 seconds.'
