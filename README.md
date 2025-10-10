# Rouss_Bot_Goggle_Sheets_Whatsapp

Bot para Cliente Rouss usando Google Sheets, Python y Meta WhatsApp.

## Archivos incluidos
- `app.py` - Flask/ASGI app que expone el webhook para WhatsApp.
- `worker.py` - Entrypoint para el Background Worker que ejecuta el scheduler (no correr en Gunicorn).
- `sheets/credentials.json` - NO INCLUIR en el repo. Subir como Secret File en Render o usar GitHub Secrets.
- `.env.example` - Variables de entorno necesarias (no contiene valores reales).
- `Dockerfile` - Imagen para producción (usada por Render).
- `render.yaml` - Declaración de servicios (web + worker) para Render (opcional).

## Variables de entorno (ejemplo)
Define en Render Dashboard (Environment -> Environment Variables) o en tu entorno local usando `.env` (solo para desarrollo):

- `WHATSAPP_ACCESS_TOKEN`
- `WHATSAPP_PHONE_NUMBER_ID`
- `WEBHOOK_VERIFY_TOKEN`
- `SPREADSHEET_ID`
- `GOOGLE_CREDENTIALS_PATH` (por ejemplo `/app/sheets/credentials.json`)
- `FLASK_ENV=production`

## Cómo subir secretos a Render
1. En tu servicio → Environment → Secret Files -> subir `credentials.json` y montarlo en `/app/sheets/credentials.json`.
2. Añadir las Environment Variables en la sección Environment del servicio.

## Ejecutar localmente (desarrollo)
1. Copiar `.env.example` a `.env` y completar valores (NO subir `.env` al repo).
2. Instalar dependencias: `pip install -r requirements.txt`
3. Ejecutar la app (ejemplo):
   ```bash
   export FLASK_ENV=development
   flask run --host=0.0.0.0 --port=5000
   ```
4. Para probar el worker localmente:
   ```bash
   python worker.py
   ```

## Notas de seguridad
- Nunca subir `credentials.json` ni `.env` con valores reales al repo.
- Si accidentalmente subiste secrets: rota las claves inmediatamente.


