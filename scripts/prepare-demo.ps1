[CmdletBinding()]
param(
    [string]$OutputDirectory = (Join-Path (Resolve-Path (Join-Path $PSScriptRoot "..")) "data\demo-certs")
)

$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null

$rsa = [System.Security.Cryptography.RSA]::Create(2048)
try {
    $request = [System.Security.Cryptography.X509Certificates.CertificateRequest]::new(
        "CN=quantumgenie-demo.contoso-test.com",
        $rsa,
        [System.Security.Cryptography.HashAlgorithmName]::SHA256,
        [System.Security.Cryptography.RSASignaturePadding]::Pkcs1
    )
    $san = [System.Security.Cryptography.X509Certificates.SubjectAlternativeNameBuilder]::new()
    $san.AddDnsName("quantumgenie-demo.contoso-test.com")
    $request.CertificateExtensions.Add($san.Build())

    $certificate = $request.CreateSelfSigned(
        [DateTimeOffset]::UtcNow.AddDays(-1),
        [DateTimeOffset]::UtcNow.AddDays(90)
    )
    try {
        $der = $certificate.Export(
            [System.Security.Cryptography.X509Certificates.X509ContentType]::Cert
        )
        $derPath = Join-Path $OutputDirectory "quantumgenie-demo.cer"
        [System.IO.File]::WriteAllBytes($derPath, $der)

        $base64 = [Convert]::ToBase64String($der, [Base64FormattingOptions]::InsertLineBreaks)
        $pem = "-----BEGIN CERTIFICATE-----`r`n$base64`r`n-----END CERTIFICATE-----`r`n"
        $pemPath = Join-Path $OutputDirectory "quantumgenie-demo-copy.pem"
        [System.IO.File]::WriteAllText($pemPath, $pem, [System.Text.Encoding]::ASCII)

        [PSCustomObject]@{
            ScanRoot = (Resolve-Path $OutputDirectory).Path
            Files = 2
            ExpectedUniqueCertificates = 1
            PrivateKeyExported = $false
        } | Format-List
    }
    finally {
        $certificate.Dispose()
    }
}
finally {
    $rsa.Dispose()
}