# Setup: listener de Google Chat (Pub/Sub)

Checklist para conectar el listener (`listener/main.py`) al Space real
"Customer support". El código ya está construido y probado con un evento
sintético — esto es la parte de infraestructura que falta para que reciba
mensajes reales. Algunos pasos pueden requerir un administrador de Workspace.

## 1. Crear el proyecto GCP

```sh
gcloud projects create cs-ticket-agents-prod --name="CS Ticket Agents"
gcloud config set project cs-ticket-agents-prod
```

(O reusar un proyecto existente si preferís — no hace falta que sea el mismo del tier gratis de Gemini.)

## 2. Habilitar las APIs necesarias

```sh
gcloud services enable chat.googleapis.com pubsub.googleapis.com
```

## 3. Crear el topic y la suscripción pull

```sh
gcloud pubsub topics create cs-tickets-chat
gcloud pubsub subscriptions create cs-tickets-chat-sub --topic=cs-tickets-chat
```

## 4. Crear la service account de la Chat app

```sh
gcloud iam service-accounts create cs-tickets-chat-app --display-name="CS Ticket Chat App"
gcloud iam service-accounts keys create ./chat-app-key.json \
  --iam-account=cs-tickets-chat-app@cs-ticket-agents-prod.iam.gserviceaccount.com
```

**Guardar `chat-app-key.json` fuera del repo** (está en `.gitignore` por patrón, pero
verificar). Referenciarlo en `.env` como `CHAT_SERVICE_ACCOUNT_FILE=/ruta/absoluta/chat-app-key.json`.

Darle permiso de suscriptor de Pub/Sub:

```sh
gcloud pubsub subscriptions add-iam-policy-binding cs-tickets-chat-sub \
  --member="serviceAccount:cs-tickets-chat-app@cs-ticket-agents-prod.iam.gserviceaccount.com" \
  --role="roles/pubsub.subscriber"
```

## 5. Registrar la Chat app (⚠️ puede requerir admin de Workspace)

En [Google Cloud Console → APIs & Services → Google Chat API → Configuration](https://console.cloud.google.com/apis/api/chat.googleapis.com):

1. **App name**: "CS Ticket Agents" (o el que prefieras).
2. **Avatar URL**: cualquier ícono temporal.
3. **Description**: "Diagnostica tickets de soporte automáticamente."
4. **Interactive features**: activar.
5. **Connection settings** → elegir **Cloud Pub/Sub** (no HTTP endpoint) → especificar el topic: `projects/cs-ticket-agents-prod/topics/cs-tickets-chat`.
6. **Visibility**: restringir a tu dominio (Runa) para que solo miembros de la organización puedan agregarla a Spaces.
7. **Authentication audience**: usar la service account creada en el paso 4.

Si esta pantalla pide permisos de administrador que no tenés, este es el paso a coordinar con IT — el resto (código, topic, subscription, service account) ya podés tenerlo listo antes de esa conversación.

## 6. Agregar la Chat app al Space "Customer support"

Desde Google Chat (no la consola de GCP): abrir el Space → **Agregar personas y apps** → buscar el nombre de la app registrada en el paso 5 → agregar.

Esto también puede requerir permisos de administrador del Space o del Workspace, según la política de la organización sobre apps de terceros/custom.

## 7. Probar

```sh
cd ~/code/cs-ticket-agents
uv run python -m listener.main
```

Y desde el Space real, escribir un mensaje de prueba. Debería aparecer el log
`--- Nuevo ticket (...) ---` seguido de la respuesta del orquestador.

## Notas

- **Adjuntos**: el método de descarga en `listener/attachments.py`
  (`client.media().download(resourceName=...)`) está documentado por la API
  pero no se pudo verificar contra un Space real todavía — probar con un
  mensaje que tenga un adjunto y ajustar si el nombre del método/recurso difiere.
- **Cuota de Gemini (tier gratis)**: durante el desarrollo nos topamos con el
  límite de 20 requests/día para `gemini-3.5-flash` en AI Studio. Si vas a
  probar el flujo real con el Space, considerá pasar a la API paga de Gemini
  antes (barata, y evita interrupciones a mitad de una prueba).
