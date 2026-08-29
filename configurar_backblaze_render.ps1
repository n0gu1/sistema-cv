<#
.SYNOPSIS
    Configura Backblaze B2 como almacenamiento privado del servicio Render.

.DESCRIPTION
    Actualiza solamente las variables BACKBLAZE_* del servicio indicado y
    solicita un nuevo despliegue. Las credenciales se guardan localmente como
    SecureString protegido por DPAPI para el usuario actual de Windows.

    El script nunca escribe las claves en el repositorio ni las muestra en la
    consola. La primera ejecucion solicita las credenciales; las siguientes
    las reutilizan desde %LOCALAPPDATA%\SistemaCV\render-b2-credentials.xml.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\configurar_backblaze_render.ps1

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\configurar_backblaze_render.ps1 -SkipDeploy

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\configurar_backblaze_render.ps1 -ForgetLocalCredentials
#>

[CmdletBinding()]
param(
    [string]$ServiceId = "srv-d9tug4fqj5pc738h3i9g",
    [string]$BucketName,
    [string]$EndpointUrl,
    [string]$ObjectPrefix,
    [int]$PresignedUrlExpiry = 300,
    [switch]$SkipDeploy,
    [switch]$ForgetLocalCredentials
)

$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$localApplicationData = [Environment]::GetFolderPath("LocalApplicationData")
$credentialDirectory = Join-Path $localApplicationData "SistemaCV"
$credentialPath = Join-Path $credentialDirectory "render-b2-credentials.xml"
$apiBaseUrl = "https://api.render.com/v1"

function ConvertTo-ProtectedString {
    param([AllowNull()][string]$Value)

    if ([string]::IsNullOrEmpty($Value)) {
        return $null
    }

    return ConvertTo-SecureString -String $Value -AsPlainText -Force
}

function ConvertFrom-ProtectedString {
    param([AllowNull()][System.Security.SecureString]$Value)

    if ($null -eq $Value) {
        return ""
    }

    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Value)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    }
}

function Read-SecretValue {
    param(
        [string]$CurrentValue,
        [AllowNull()][System.Security.SecureString]$StoredValue,
        [string]$Prompt
    )

    if (-not [string]::IsNullOrWhiteSpace($CurrentValue)) {
        return $CurrentValue
    }

    if ($null -ne $StoredValue) {
        $storedPlainValue = ConvertFrom-ProtectedString $StoredValue
        if (-not [string]::IsNullOrWhiteSpace($storedPlainValue)) {
            return $storedPlainValue
        }
    }

    $secureValue = Read-Host -Prompt $Prompt -AsSecureString
    $plainValue = ConvertFrom-ProtectedString $secureValue
    if ([string]::IsNullOrWhiteSpace($plainValue)) {
        throw "La credencial solicitada no puede estar vacia."
    }

    return $plainValue
}

function Read-TextValue {
    param(
        [string]$CurrentValue,
        [AllowNull()][string]$StoredValue,
        [string]$Prompt,
        [string]$DefaultValue
    )

    if (-not [string]::IsNullOrWhiteSpace($CurrentValue)) {
        return $CurrentValue.Trim()
    }

    if (-not [string]::IsNullOrWhiteSpace($StoredValue)) {
        return $StoredValue.Trim()
    }

    $value = Read-Host -Prompt "$Prompt [$DefaultValue]"
    if ([string]::IsNullOrWhiteSpace($value)) {
        return $DefaultValue
    }

    return $value.Trim()
}

function Invoke-RenderApi {
    param(
        [ValidateSet("Get", "Post", "Put")]
        [string]$Method,
        [string]$Uri,
        [AllowNull()][string]$Body
    )

    try {
        $requestParameters = @{
            Method      = $Method
            Uri         = $Uri
            Headers     = @{ Authorization = "Bearer $renderApiKey" }
            ContentType = "application/json"
        }

        if (-not [string]::IsNullOrEmpty($Body)) {
            $requestParameters.Body = $Body
        }

        return Invoke-RestMethod @requestParameters
    }
    catch {
        $statusCode = $null
        if ($null -ne $_.Exception.Response) {
            $statusCode = [int]$_.Exception.Response.StatusCode
        }

        if ($null -ne $statusCode) {
            throw "Render rechazo la solicitud $Method $Uri (HTTP $statusCode)."
        }

        throw "No se pudo contactar la API de Render: $($_.Exception.Message)"
    }
}

if ($ForgetLocalCredentials) {
    if (Test-Path -LiteralPath $credentialPath) {
        Remove-Item -LiteralPath $credentialPath -Force
        Write-Host "Credenciales locales eliminadas de $credentialPath."
    }
    else {
        Write-Host "No habia credenciales locales guardadas."
    }
    exit 0
}

$storedCredentials = $null
if (Test-Path -LiteralPath $credentialPath) {
    try {
        $storedCredentials = Import-Clixml -LiteralPath $credentialPath
    }
    catch {
        Write-Warning "No se pudieron leer las credenciales locales; se solicitaran nuevamente."
    }
}

$renderApiKey = Read-SecretValue `
    -CurrentValue $env:RENDER_API_KEY `
    -StoredValue $(if ($null -ne $storedCredentials) { $storedCredentials.RenderApiKey }) `
    -Prompt "Render API key"

$backblazeKeyId = Read-SecretValue `
    -CurrentValue $env:BACKBLAZE_APPLICATION_KEY_ID `
    -StoredValue $(if ($null -ne $storedCredentials) { $storedCredentials.BackblazeApplicationKeyId }) `
    -Prompt "Backblaze application key ID"

$backblazeKey = Read-SecretValue `
    -CurrentValue $env:BACKBLAZE_APPLICATION_KEY `
    -StoredValue $(if ($null -ne $storedCredentials) { $storedCredentials.BackblazeApplicationKey }) `
    -Prompt "Backblaze application key"

$BucketName = Read-TextValue `
    -CurrentValue $(if ($null -ne $env:BACKBLAZE_BUCKET_NAME) { $env:BACKBLAZE_BUCKET_NAME } else { $BucketName }) `
    -StoredValue $(if ($null -ne $storedCredentials) { $storedCredentials.BucketName }) `
    -Prompt "Backblaze bucket name" `
    -DefaultValue "sistema-cv-curriculos-privados"

$EndpointUrl = Read-TextValue `
    -CurrentValue $(if ($null -ne $env:BACKBLAZE_ENDPOINT_URL) { $env:BACKBLAZE_ENDPOINT_URL } else { $EndpointUrl }) `
    -StoredValue $(if ($null -ne $storedCredentials) { $storedCredentials.EndpointUrl }) `
    -Prompt "Backblaze S3 endpoint URL, por ejemplo https://s3.us-west-004.backblazeb2.com" `
    -DefaultValue "https://s3.REGION.backblazeb2.com"

$ObjectPrefix = Read-TextValue `
    -CurrentValue $(if ($null -ne $env:BACKBLAZE_OBJECT_PREFIX) { $env:BACKBLAZE_OBJECT_PREFIX } else { $ObjectPrefix }) `
    -StoredValue $(if ($null -ne $storedCredentials) { $storedCredentials.ObjectPrefix }) `
    -Prompt "Prefijo de objetos" `
    -DefaultValue "curriculos"

$EndpointUrl = $EndpointUrl.TrimEnd("/")
$endpointUri = $null
if (-not [Uri]::TryCreate($EndpointUrl, [UriKind]::Absolute, [ref]$endpointUri) -or
    $endpointUri.Scheme -ne "https" -or
    $endpointUri.Host -notlike "*.backblazeb2.com") {
    throw "EndpointUrl debe ser una URL HTTPS de Backblaze, por ejemplo https://s3.us-west-004.backblazeb2.com."
}

if ($BucketName -notmatch "^[a-z0-9][a-z0-9.-]{4,48}[a-z0-9]$") {
    throw "El nombre del bucket no tiene un formato B2 valido."
}

$ObjectPrefix = $ObjectPrefix.Trim("/")
if ([string]::IsNullOrWhiteSpace($ObjectPrefix) -or $ObjectPrefix -match "[\\\s]") {
    throw "ObjectPrefix debe contener un prefijo sin espacios ni barras invertidas."
}

if ($PresignedUrlExpiry -lt 1 -or $PresignedUrlExpiry -gt 604800) {
    throw "PresignedUrlExpiry debe estar entre 1 y 604800 segundos."
}

$variables = @(
    @{ Key = "BACKBLAZE_ENABLED"; Value = "True" },
    @{ Key = "BACKBLAZE_APPLICATION_KEY_ID"; Value = $backblazeKeyId },
    @{ Key = "BACKBLAZE_APPLICATION_KEY"; Value = $backblazeKey },
    @{ Key = "BACKBLAZE_BUCKET_NAME"; Value = $BucketName },
    @{ Key = "BACKBLAZE_ENDPOINT_URL"; Value = $EndpointUrl },
    @{ Key = "BACKBLAZE_OBJECT_PREFIX"; Value = $ObjectPrefix },
    @{ Key = "BACKBLAZE_PRESIGNED_URL_EXPIRY"; Value = [string]$PresignedUrlExpiry }
)

Write-Host "Actualizando variables B2 del servicio $ServiceId..."
foreach ($variable in $variables) {
    $encodedKey = [Uri]::EscapeDataString($variable.Key)
    $variableUri = "$apiBaseUrl/services/$ServiceId/env-vars/$encodedKey"
    $body = @{ value = [string]$variable.Value } | ConvertTo-Json -Compress
    $null = Invoke-RenderApi -Method Put -Uri $variableUri -Body $body
    Write-Host "  OK: $($variable.Key)"
}

$storedCredentialObject = [PSCustomObject]@{
    RenderApiKey              = ConvertTo-ProtectedString $renderApiKey
    BackblazeApplicationKeyId = ConvertTo-ProtectedString $backblazeKeyId
    BackblazeApplicationKey   = ConvertTo-ProtectedString $backblazeKey
    BucketName                = $BucketName
    EndpointUrl               = $EndpointUrl
    ObjectPrefix              = $ObjectPrefix
}

New-Item -ItemType Directory -Path $credentialDirectory -Force | Out-Null
$storedCredentialObject | Export-Clixml -LiteralPath $credentialPath

if ($SkipDeploy) {
    Write-Host "Variables actualizadas. Se omitio el despliegue por -SkipDeploy."
    exit 0
}

$deployUri = "$apiBaseUrl/services/$ServiceId/deploys"
$deployBody = @{ deployMode = "build_and_deploy" } | ConvertTo-Json -Compress
$deploy = Invoke-RenderApi -Method Post -Uri $deployUri -Body $deployBody

if ($null -ne $deploy.id) {
    Write-Host "Despliegue solicitado correctamente: $($deploy.id)"
}
else {
    Write-Host "Despliegue solicitado correctamente."
}

Write-Host "Las credenciales locales quedaron protegidas en $credentialPath."
