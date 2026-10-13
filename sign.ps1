# Put beside Lumen VPN.exe. Also accepts -FilePath '.\Lumen VPN.msi'.
# For a publisher certificate: -Thumbprint ABC... -TimestampServer https://...
[CmdletBinding()]
param(
    [string]$FilePath,
    [string]$Thumbprint,
    [string]$TimestampServer
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
try {
    if ($env:OS -ne 'Windows_NT') { throw 'Run this script on Windows.' }
    if (-not $FilePath) {
        $FilePath = Join-Path $PSScriptRoot 'Lumen VPN.exe'
        if (-not (Test-Path -LiteralPath $FilePath -PathType Leaf)) {
            $FilePath = Join-Path $PSScriptRoot 'LumenVPN.exe'
        }
    } elseif (-not [IO.Path]::IsPathRooted($FilePath)) {
        $FilePath = Join-Path $PSScriptRoot $FilePath
    }
    $target = (Get-Item -LiteralPath $FilePath).FullName
    if ([IO.Path]::GetExtension($target) -notin @('.exe', '.msi')) {
        throw 'Select a Lumen VPN .exe or .msi file.'
    }
    if ($TimestampServer -and $TimestampServer -notmatch '^https?://') {
        throw 'TimestampServer must be an HTTP or HTTPS timestamp service URL.'
    }
    if ($Thumbprint) {
        $id = $Thumbprint -replace '\s', ''
        if ($id -notmatch '^[0-9a-fA-F]+$') { throw 'Invalid certificate thumbprint.' }
        $cert = Get-Item -LiteralPath "Cert:\CurrentUser\My\$id" -ErrorAction SilentlyContinue
        if (-not $cert) {
            $cert = Get-Item -LiteralPath "Cert:\LocalMachine\My\$id" -ErrorAction SilentlyContinue
        }
        if (-not $cert) { throw 'The certificate was not found in the Windows Personal certificate stores.' }
    } else {
        $cert = Get-ChildItem Cert:\CurrentUser\My -CodeSigningCert |
            Where-Object { $_.Subject -eq 'CN=LumenVPN' -and $_.Issuer -eq $_.Subject -and
                $_.FriendlyName -eq 'Lumen VPN local test signing' -and $_.HasPrivateKey -and
                $_.NotBefore -le (Get-Date) -and $_.NotAfter -gt (Get-Date).AddDays(7) } |
            Sort-Object NotAfter -Descending | Select-Object -First 1
        if (-not $cert) {
            $cert = New-SelfSignedCertificate -Type CodeSigningCert -Subject 'CN=LumenVPN' `
                -FriendlyName 'Lumen VPN local test signing' -CertStoreLocation 'Cert:\CurrentUser\My' `
                -KeyAlgorithm RSA -KeyLength 3072 -HashAlgorithm SHA256 -KeyExportPolicy NonExportable `
                -NotAfter (Get-Date).AddYears(2)
        }
        Write-Warning 'Using a self-signed local test certificate. Other computers will not automatically trust this publisher. No trust-store changes are made.'
    }
    if (-not $cert.HasPrivateKey) { throw 'The certificate has no accessible private key.' }
    if ($cert.NotBefore -gt (Get-Date) -or $cert.NotAfter -le (Get-Date)) {
        throw 'The signing certificate is not currently valid.'
    }
    if (-not ($cert.EnhancedKeyUsageList | Where-Object { $_.ObjectId -eq '1.3.6.1.5.5.7.3.3' })) {
        throw 'The certificate is not authorized for code signing.'
    }
    $options = @{ FilePath = $target; Certificate = $cert; HashAlgorithm = 'SHA256' }
    if ($TimestampServer) { $options.TimestampServer = $TimestampServer }
    $result = Set-AuthenticodeSignature @options
    $check = Get-AuthenticodeSignature -LiteralPath $target
    if (-not $check.SignerCertificate -or $check.SignerCertificate.Thumbprint -ne $cert.Thumbprint) {
        throw "Signature could not be verified: $($result.StatusMessage)"
    }
    if ($check.Status -ne 'Valid' -and $check.Status -ne 'NotTrusted') {
        throw "Signing failed: $($check.Status): $($check.StatusMessage)"
    }
    if ($TimestampServer -and -not $check.TimeStamperCertificate) {
        throw 'The requested timestamp was not applied. Check the timestamp service URL.'
    }
    Write-Host "Signed: $target"
    Write-Host "Publisher: $($cert.Subject) | Windows trust: $($check.Status)"
    exit 0
} catch {
    Write-Error $_ -ErrorAction Continue
    exit 1
}
