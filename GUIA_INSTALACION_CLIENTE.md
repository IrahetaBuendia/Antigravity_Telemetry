# Guía de Instalación en Equipo de Desarrollador (Copia de Archivos y Configuración)

Esta guía describe los pasos para configurar un equipo nuevo de desarrollo asumiendo que **ya se cuenta con la carpeta de archivos del proyecto** (compartida por red, ZIP o carpeta local), indicando exactamente **qué archivos copiar, en qué rutas pegarlos y qué comandos de `gcloud` ejecutar**.

---

## 1. Archivos que debe tener a la mano

Desde la carpeta compartida del proyecto, ubicará los siguientes archivos listos para usar:

| Archivo en la carpeta del proyecto | ¿Para qué sirve? |
| :--- | :--- |
| `.agents\scripts\telemetry_hook.py` | Script que captura tokens y modelo en cada respuesta y los envía a BigQuery. |
| `.agents\hooks.json` | Archivo de configuración que activa el disparo automático del script. |
| `.agents\scripts\backfill_token_usage.py` | *(Opcional)* Script para enviar a BigQuery conversaciones antiguas del equipo. |
| `requirements.txt` | Lista de librerías de Python requeridas (`google-cloud-bigquery`, `tiktoken`). |

---

## 2. Paso 1: Instalar Librerías de Python

Abra una ventana de **PowerShell** en la carpeta donde tiene los archivos y ejecute:

```powershell
pip install -r requirements.txt
```
*(O directamente: `pip install google-cloud-bigquery tiktoken`)*

---

## 3. Paso 2: Autenticación con Google Cloud (`gcloud`)

En el equipo del desarrollador, ejecute los siguientes comandos en **PowerShell** para autenticar su cuenta corporativa y habilitar el envío de datos a BigQuery:

```powershell
# 1. Iniciar sesión con el correo del desarrollador en Google Cloud CLI
gcloud auth login

# 2. Generar las credenciales locales por defecto (ADC) que utiliza el script de Python
gcloud auth application-default login

# 3. Verificar que aparezca el correo correcto del desarrollador
gcloud config get-value account
```

> [!IMPORTANT]
> **Permiso en GCP:** El correo del desarrollador autenticado debe tener asignado el rol **Editor de datos de BigQuery** (`roles/bigquery.dataEditor`) en el proyecto donde se aloja el dataset `antigravity_telemetry`.

---

## 4. Paso 3:Dónde Copiar los Archivos en la Carpeta `.gemini` del Desarrollador

En el equipo del desarrollador, diríjase a su carpeta de usuario de Windows:
`C:\Users\<nombre.usuario>\.gemini\`

*(Truco: Puede abrirla directamente presionando `Win + R`, escribiendo `%USERPROFILE%\.gemini` y presionando Enter).*

Dentro de `.gemini`, asegúrese de que existan las carpetas **`scripts`** y **`config`** (si no existen, créelas) y copie los archivos así:

### 1. Copiar `telemetry_hook.py`
* **Origen:** `.agents\scripts\telemetry_hook.py`
* **Destino donde debe pegarlo:**
  ```text
  C:\Users\<nombre.usuario>\.gemini\scripts\telemetry_hook.py
  ```
  *(Este archivo no requiere ninguna modificación).*

### 2. Copiar `hooks.json`
* **Origen:** `.agents\hooks.json`
* **Destino donde debe pegarlo:**
  ```text
  C:\Users\<nombre.usuario>\.gemini\config\hooks.json
  ```
* **Único ajuste dentro de `hooks.json`:** Abra el archivo `C:\Users\<nombre.usuario>\.gemini\config\hooks.json` con el Bloc de notas y asegúrese de que la ruta de `command` apunte al usuario de esa máquina (usando doble barra `\\`):
  ```json
  {
    "antigravity-token-telemetry": {
      "enabled": true,
      "PostInvocation": [
        {
          "type": "command",
          "command": "python C:\\Users\\<nombre.usuario>\\.gemini\\scripts\\telemetry_hook.py",
          "timeout": 30
        }
      ]
    }
  }
  ```

> [!TIP]
> **Alternativa Automática:** Si en lugar de copiar los archivos manualmente ejecuta el archivo **`.\install_client.ps1`** incluido en la carpeta, este creará las carpetas `scripts` y `config`, copiará `telemetry_hook.py` y ajustará automáticamente el `<nombre.usuario>` dentro de `hooks.json`.

---

## 5. Paso 4: Verificación y Carga de Historial Previo (Opcional)

### A. Verificar que ya está enviando métricas en vivo
1. Abra **Antigravity** y envíe cualquier consulta en el chat.
2. Cuando el agente termine de responder, verifique en la carpeta:
   ```text
   C:\Users\<nombre.usuario>\.gemini\antigravity\.telemetry_state.json
   ```
   Si ese archivo `.telemetry_state.json` se creó automáticamente, el equipo ya está reportando tokens y modelos en tiempo real a BigQuery.

### B. Cargar conversaciones históricas previas del desarrollador (Opcional)
Si el desarrollador ya usaba Antigravity antes y desea subir su historial pasado a BigQuery por única vez, ejecute desde la carpeta compartida:

```powershell
python .agents\scripts\backfill_token_usage.py
```
