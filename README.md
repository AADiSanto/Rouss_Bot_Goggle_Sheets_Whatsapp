# Rouss_Bot_Goggle_Sheets_Whatsapp.-

Bot para Cliente Rouss Usando Google Sheets, Python y Meta WhatsApp.-

## Archivos Incluídos.-
- `app.py`                  - Flask/ASGI app que Expone el Webhook para WhatsApp.-
- `worker.py`               - Entrypoint para el Background Worker que Ejecuta el scheduler ( Nó Correr en Gunicorn ).-
- `sheets/credentials.json` - Nó INCLUIR en el Repo, Subir Como Secret File en Render o Usar GitHub Secrets.-
- `.env.example`            - Variables de Entorno Necesarias ( Nó Contiene Valores  Reales ).-
- `Dockerfile`              - Imagen para Producción ( Usada por Render ).-
- `render.yaml`             - Declaración de Servicios ( WEB + Worker ) para Render ( Opcional ).-

## Variables de Entorno ( Ejemplo ).-
Define en Render Dashboard ( Environment -> Environment Variables) o en Tú Entorno Local Usando `.env` ( Sólo Para Desarrollo ):

- `WHATSAPP_ACCESS_TOKEN`
- `WHATSAPP_PHONE_NUMBER_ID`
- `WEBHOOK_VERIFY_TOKEN`
- `SPREADSHEET_ID`
- `GOOGLE_CREDENTIALS_PATH` ( Por Ejemplo `/app/sheets/credentials.json` ).-
- `FLASK_ENV=production`

## Cómo Subir Secretos a Render.-
1. En El Servicio → Environment → Secret Files -> Subir `credentials.json` y Montarlo en: `/app/sheets/credentials.json`.-
2. Añadir las Environment Variables en lá Sección Environment del Servicio.-

## Ejecutar Localmente ( Desarrollo ).-
1. Copiar `.env.example` a `.env` y Completar Valores ( Nó Subir `.env` al Repo ).-
2. Instalar Dependencias: `pip install -r requirements.txt`
3. Ejecutar la App ( Ejemplo ):
   ```bash
   export FLASK_ENV=development
   flask run --host=0.0.0.0 --port=5000
   ```
4. Para Probar el Worker Localmente:
   ```bash
   python worker.py
   ```

## Notas de Seguridad.-
- Nunca Subir `credentials.json` ní `.env` con Valores Reales al Repo.-
- Si Accidentalmente sé Subieron Secrets: Rotar las Claves Inmediatamente.-


