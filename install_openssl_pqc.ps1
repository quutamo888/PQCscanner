#requires -Version 5.1
[CmdletBinding()]
param(
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
$PackageId = "ShiningLight.OpenSSL.LTS.Light"
$MinimumVersion = [version]"3.5.0"

function Get-OpenSslVersion {
    param([Parameter(Mandatory)][string]$Executable)
    $output = & $Executable version 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) { return $null }
    $match = [regex]::Match($output, 'OpenSSL\s+(\d+)\.(\d+)\.(\d+)')
    if (-not $match.Success) { return $null }
    [pscustomobject]@{
        Text = $output.Trim()
        Version = [version]::new([int]$match.Groups[1].Value, [int]$match.Groups[2].Value, [int]$match.Groups[3].Value)
    }
}

function Test-OpenSslPqcGroup {
    param([Parameter(Mandatory)][string]$Executable)
    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $output = & $Executable s_client -groups X25519MLKEM768 -connect 127.0.0.1:1 2>&1 | Out-String
    } finally {
        $ErrorActionPreference = $previousPreference
    }
    $unsupported = $output -match 'invalid group|unknown group|cannot be set|SSL_CONF_cmd.*failed|no such group'
    return -not $unsupported
}

function Find-OpenSsl {
    $candidates = @()
    if ($env:PQC_OPENSSL_PATH) { $candidates += $env:PQC_OPENSSL_PATH }
    $pathCommand = Get-Command openssl.exe -ErrorAction SilentlyContinue
    if ($pathCommand) { $candidates += $pathCommand.Source }
    $candidates += @(
        "$env:ProgramFiles\OpenSSL-Win64\bin\openssl.exe",
        "$env:ProgramFiles\OpenSSL-Win64\openssl.exe"
    )
    foreach ($candidate in ($candidates | Where-Object { $_ } | Select-Object -Unique)) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            $version = Get-OpenSslVersion $candidate
            if ($version -and $version.Version -ge $MinimumVersion -and (Test-OpenSslPqcGroup $candidate)) {
                return [pscustomobject]@{ Path = (Resolve-Path -LiteralPath $candidate).Path; Version = $version }
            }
        }
    }
    return $null
}

Write-Host "PQC OpenSSL installer" -ForegroundColor Cyan
Write-Host "Required: OpenSSL >= $MinimumVersion with X25519MLKEM768 support"

$engine = Find-OpenSsl
if (-not $engine -and -not $SkipInstall) {
    if (-not (Get-Command winget.exe -ErrorAction SilentlyContinue)) {
        throw "winget not found. Install App Installer, then rerun this script."
    }
    Write-Host "Installing $PackageId from WinGet..." -ForegroundColor Yellow
    & winget install --id $PackageId --exact --source winget --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -ne 0) { throw "WinGet installation failed with exit code $LASTEXITCODE." }
    $engine = Find-OpenSsl
}

if (-not $engine) {
    throw "No usable OpenSSL 3.5+ PQC engine found. Set PQC_OPENSSL_PATH or rerun without -SkipInstall."
}

[Environment]::SetEnvironmentVariable("PQC_OPENSSL_PATH", $engine.Path, "User")
$env:PQC_OPENSSL_PATH = $engine.Path
Write-Host "Installed engine: $($engine.Version.Text)" -ForegroundColor Green
Write-Host "PQC_OPENSSL_PATH=$($engine.Path)" -ForegroundColor Green
Write-Host "Named group accepted: X25519MLKEM768" -ForegroundColor Green
Write-Host "Open a new terminal before running run.bat." -ForegroundColor Yellow
