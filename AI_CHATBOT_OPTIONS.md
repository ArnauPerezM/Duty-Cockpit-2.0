# AI Chatbot — Opciones de implementación

Análisis de las alternativas para añadir un chatbot de IA a Duty Cockpit 2.0 que responda preguntas sobre los datos filtrados y funcione como user guide interactiva.

---

## Capacidades comunes a todas las opciones

Independientemente del proveedor, el chatbot tendría:

- **Insights de datos**: responde preguntas sobre los datos visibles (respetando filtros COO/COI/HS activos). El contexto que se envía al modelo son estadísticas agregadas, no filas individuales.
- **User guide interactiva**: responde dudas sobre cómo usar el tool (cómo subir ficheros, qué significan los KPIs, cómo editar datos, diferencia UAT/PRO, etc.).
- **Ubicación en UI**: panel fijo al pie del sidebar de Streamlit.
- **Historial de conversación**: últimos 20 mensajes, se borra al desconectar.

**Dependencia de código común**: `openai>=1.0` en `requirements.txt` + nuevo fichero `src/chatbot.py`.

---

## Opción 1 — Ollama (local, sin API key)

**Qué es**: servidor LLM local. Descarga y corre modelos open-source (Llama, Mistral, Gemma…) completamente en la máquina del usuario, sin que los datos salgan a ningún servidor externo.

### Setup del usuario

```bash
# 1. Instalar desde https://ollama.com (ejecutable Windows ~130 MB)
# 2. Descargar un modelo (una sola vez):
ollama pull llama3.2        # ~2 GB, recomendado para CPU
ollama pull phi3            # ~2 GB, más rápido en CPU
# 3. Ollama arranca como servicio en Windows automáticamente
```

### Implementación en código

```python
# requirements.txt
openai>=1.0   # el SDK de OpenAI habla con Ollama directamente

# src/chatbot.py
from openai import OpenAI

client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
response = client.chat.completions.create(
    model="llama3.2",          # nombre del modelo descargado
    messages=messages,
    max_tokens=800,
    temperature=0.3,
)
```

**Formulario en sidebar**: campo "Nombre del modelo" + "Base URL (opcional, default localhost:11434)".

### Ventajas
- Sin API key ni cuenta externa
- Datos 100% locales, no salen del equipo
- Gratis
- Compatible con el SDK `openai` ya instalado

### Desventajas
- Requiere instalar Ollama y descargar modelos (~2–8 GB por modelo)
- Lento en CPU (10–30 s por respuesta sin GPU)
- Calidad inferior a modelos cloud para razonamiento complejo
- Puede requerir aprobación IT en entornos corporativos (abre puerto local)

### Modelos recomendados

| Modelo | Tamaño | Para |
|---|---|---|
| `phi3` / `phi3.5` | ~2 GB | CPU, respuestas rápidas |
| `llama3.2` | ~2 GB | CPU, buena calidad general |
| `llama3.1:8b` | ~5 GB | Balance calidad/velocidad |
| `qwen2.5:7b` | ~5 GB | Multilingual (español) |
| `mistral` | ~4 GB | Buena calidad en inglés |

---

## Opción 2 — LM Studio (local, sin API key, con UI)

**Qué es**: aplicación de escritorio Windows/Mac que gestiona modelos LLM locales con interfaz gráfica y expone el mismo endpoint OpenAI-compatible que Ollama.

### Setup del usuario

1. Descargar desde [lmstudio.ai](https://lmstudio.ai) (~400 MB instalador)
2. Buscar y descargar un modelo desde la UI (mismo catálogo GGUF que Ollama)
3. Activar el servidor local: pestaña "Local Server" → Start

### Implementación en código

Idéntica a Ollama — mismo SDK, mismo endpoint:

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")
response = client.chat.completions.create(
    model="lmstudio-community/llama-3.2-3b-instruct",
    messages=messages,
    max_tokens=800,
)
```

**Formulario en sidebar**: campo "Base URL" (default `http://localhost:1234/v1`) — el modelo activo se detecta automáticamente.

### Ventajas
- Sin API key
- Datos 100% locales
- Gratis
- UI gráfica para gestionar modelos (más fácil que Ollama CLI)
- No instala servicio de background — el servidor solo corre cuando la app está abierta

### Desventajas
- Mismo problema de velocidad en CPU que Ollama
- El usuario debe arrancar LM Studio manualmente antes de usar el chatbot
- Aplicación más pesada que Ollama
- Puede requerir aprobación IT

---

## Opción 3 — Azure OpenAI (cloud corporativo)

**Qué es**: servicio de Microsoft Azure que hospeda modelos GPT-4o/GPT-4 con SLA empresarial. Muy adecuado para entornos Accenture con infraestructura Azure existente.

### Setup

Requiere un recurso Azure OpenAI activo con un deployment (GPT-4o recomendado). Las credenciales se introducen en el sidebar de la app y se guardan en `session_state` (nunca en disco).

### Implementación en código

```python
# requirements.txt
openai>=1.0

# src/chatbot.py
from openai import AzureOpenAI

client = AzureOpenAI(
    azure_endpoint="https://xxx.openai.azure.com/",
    api_key="<API_KEY>",
    api_version="2024-02-01",
)
response = client.chat.completions.create(
    model="gpt-4o",    # nombre del deployment en Azure
    messages=messages,
    max_tokens=800,
)
```

**Formulario en sidebar**: Endpoint + API Key + Deployment name.

### Ventajas
- Alta calidad de respuesta (GPT-4o)
- Rápido (cloud)
- Cumple normativas enterprise de Microsoft/Accenture
- Datos cifrados en tránsito, no usados para entrenar modelos (contrato enterprise)

### Desventajas
- Los datos (resúmenes agregados) salen del equipo hacia Azure
- Requiere credenciales Azure y permisos IAM
- Coste por token (~$2–$5 por cada millón de tokens de entrada con GPT-4o)
- Dependencia de conectividad

---

## Opción 4 — AWS Bedrock (cloud corporativo)

**Qué es**: servicio AWS que da acceso a múltiples modelos (Claude de Anthropic, Llama, Mistral, Titan…) bajo la infraestructura y contratos corporativos de AWS.

### Setup

Requiere cuenta AWS con acceso a Bedrock habilitado + credenciales IAM con permisos `bedrock:InvokeModel`.

### Implementación en código

```python
# requirements.txt
boto3>=1.34

# src/chatbot.py — API diferente, NO compatible con el SDK openai
import boto3, json

client = boto3.client("bedrock-runtime", region_name="us-east-1")
body = json.dumps({
    "anthropic_version": "bedrock-2023-05-31",
    "max_tokens": 800,
    "messages": messages,
})
response = client.invoke_model(
    modelId="anthropic.claude-3-5-sonnet-20241022-v2:0",
    body=body,
)
reply = json.loads(response["body"].read())["content"][0]["text"]
```

**Formulario en sidebar**: AWS Access Key ID + Secret Access Key + Region.

### Ventajas
- Acceso a modelos muy potentes (Claude 3.5 Sonnet, Llama 3.1 70B…)
- Cumple normativas AWS enterprise
- Si Accenture ya tiene contrato AWS, puede no suponer coste adicional

### Desventajas
- Los datos salen al cloud AWS
- API completamente distinta al SDK `openai` (requiere `boto3`, más código)
- Configuración IAM más compleja
- Coste por token

---

## Comparativa resumen

| | Ollama | LM Studio | Azure OpenAI | AWS Bedrock |
|---|:---:|:---:|:---:|:---:|
| **Sin API key** | ✅ | ✅ | ❌ | ❌ |
| **Datos locales** | ✅ | ✅ | ❌ | ❌ |
| **Gratis** | ✅ | ✅ | ❌ | ❌ |
| **Calidad respuesta** | Media | Media | Alta | Alta |
| **Velocidad** | Lenta (CPU) | Lenta (CPU) | Rápida | Rápida |
| **Setup complejidad** | Baja | Muy baja | Media | Alta |
| **Riesgo IT/compliance** | Bajo* | Bajo* | Bajo | Bajo |
| **Compatible openai SDK** | ✅ | ✅ | ✅ | ❌ |

*Verificar política de software de terceros en Accenture.

---

## Recomendación

- **MVP / demo rápida** → **LM Studio** (UI gráfica, zero config de código, mismo endpoint)
- **Producción sin cloud** → **Ollama** (más ligero, pensado para uso programático)
- **Producción con cloud Accenture** → **Azure OpenAI** (mejor calidad, ya en ecosistema Microsoft)
- **Si ya hay infraestructura AWS** → **AWS Bedrock** (acceso a Claude y otros modelos potentes)
