# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

# The user accepted the Foundry EULA and authorized this verified installer.
# This script is for ephemeral GitHub runners, not an existing DCC workstation.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
foreach ($name in 'INSTALLER_BUCKET', 'INSTALLER_BUCKET_EXPECTED_OWNER', 'NUKE_INSTALLER_S3_KEY') {
    if (-not [Environment]::GetEnvironmentVariable($name, 'Process')) { throw "Missing installer configuration: $name" }
}
if ($env:INSTALLER_BUCKET_EXPECTED_OWNER -notmatch '^\d{12}$') {
    throw 'INSTALLER_BUCKET_EXPECTED_OWNER must be a 12-digit account ID.'
}
if ($env:NUKE_INSTALLER_S3_KEY -ne 'nuke/17/Nuke17.1v2-win-x86_64.zip') {
    throw 'Select the verified Nuke 17.1v2 Windows archive key.'
}
$directory = Join-Path $env:RUNNER_TEMP 'nuke-installer'
New-Item -ItemType Directory -Path $directory | Out-Null
$archive = Join-Path $directory 'Nuke17.1v2-win-x86_64.zip'
& aws s3api get-object --bucket $env:INSTALLER_BUCKET --key $env:NUKE_INSTALLER_S3_KEY `
    --expected-bucket-owner $env:INSTALLER_BUCKET_EXPECTED_OWNER $archive > $null
if ($LASTEXITCODE -ne 0) { throw 'Installer download from the shared CI bucket failed.' }
$expected = 'A0EC0C8D3A3B22E209FCCD3CE0F66748AF1BE412C55A88DC843D9DBDF6155D65'
if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash -ne $expected) {
    throw 'Installer checksum differs from the verified workstation archive.'
}
Expand-Archive -LiteralPath $archive -DestinationPath $directory
Remove-Item -LiteralPath $archive
$installer = Join-Path $directory 'Nuke17.1v2-win-x86_64.msi'
$signature = Get-AuthenticodeSignature -LiteralPath $installer
if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'Foundry') {
    throw 'The Nuke MSI does not have a valid Foundry signature.'
}
$log = Join-Path $directory 'install.log'
$process = Start-Process msiexec.exe -ArgumentList @(
    '/i', "`"$installer`"", '/qn', '/norestart', 'ACCEPT_FOUNDRY_EULA=ACCEPT',
    '/L*v', "`"$log`""
) -Wait -PassThru
if ($process.ExitCode -notin 0, 3010) {
    throw "Nuke installation failed ($($process.ExitCode)); see $log."
}
$executable = 'C:\Program Files\Nuke17.1v2\Nuke17.1.exe'
$python = 'C:\Program Files\Nuke17.1v2\python.exe'
if (-not (Test-Path -LiteralPath $executable) -or -not (Test-Path -LiteralPath $python)) {
    throw 'Nuke installation did not produce the expected executable and bundled Python.'
}
"NUKE_EXECUTABLE=$executable" | Out-File $env:GITHUB_ENV -Append -Encoding utf8
"NUKE_PYTHON=$python" | Out-File $env:GITHUB_ENV -Append -Encoding utf8
Write-Output 'Verified Nuke 17.1v2 installed.'
exit 0
