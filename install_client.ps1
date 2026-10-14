<#
.SYNOPSIS
    Instalador automático del Hook Global de Telemetría de Antigravity para desarrolladores.
.DESCRIPTION
    1. Instala las dependencias Python necesarias (google-cloud-bigquery, tiktoken).
    2. Copia el script telemetry_hook.py a la ruta global ~/.gemini/scripts/
    3. Configura el archivo global ~/.gemini/config/hooks.json con la ruta del usuario actual.
#>

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " Instalador de Telemetría Global de Antigravity (BigQuery)" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Instalar librerías de Python
Write-Host "`n[1/3] Instalando dependencias de Python (google-cloud-bigquery, tiktoken)..." -ForegroundColor Yellow
pip install -r "$PSScriptRoot\requirements.txt"

# 2. Crear directorios globales en el perfil del usuario
$GeminiBase = Join-Path $env:USERPROFILE ".gemini"
$ScriptsDir = Join-Path $GeminiBase "scripts"
$ConfigDir  = Join-Path $GeminiBase "config"

Write-Host "`n[2/3] Configurando directorios globales en $GeminiBase..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path $ScriptsDir | Out-Null
New-Item -ItemType Directory -Force -Path $ConfigDir  | Out-Null

# Copiar script de telemetría
$TargetScript = Join-Path $ScriptsDir "telemetry_hook.py"
Copy-Item -Path "$PSScriptRoot\.agents\scripts\telemetry_hook.py" -Destination $TargetScript -Force
Write-Host "  [OK] Script copiado en: $TargetScript" -ForegroundColor Green

# 3. Generar archivo hooks.json global
$HooksFile = Join-Path $ConfigDir "hooks.json"
$EscapedPath = $TargetScript.Replace("\", "\\")

$HooksJson = @"
{
  "antigravity-token-telemetry": {
    "enabled": true,
    "PostInvocation": [
      {
        "type": "command",
        "command": "python $EscapedPath",
        "timeout": 30
      }
    ]
  }
}
"@

Set-Content -Path $HooksFile -Value $HooksJson -Encoding UTF8
Write-Host "  [OK] Hook global configurado en: $HooksFile" -ForegroundColor Green

Write-Host "`n[3/3] Verificando credenciales de Google Cloud..." -ForegroundColor Yellow
$AdcPath = Join-Path $env:APPDATA "gcloud\application_default_credentials.json"
if (Test-Path $AdcPath) {
    Write-Host "  [OK] Credenciales ADC detectadas en el equipo." -ForegroundColor Green
} else {
    Write-Host "  [!] No se encontraron credenciales ADC. Ejecutando inicio de sesión..." -ForegroundColor Yellow
    gcloud auth application-default login
}

Write-Host "`n==========================================================" -ForegroundColor Cyan
Write-Host " [OK] Instalación completada exitosamente." -ForegroundColor Green
Write-Host " Antigravity enviará automáticamente las métricas de tokens y modelos a BigQuery." -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
