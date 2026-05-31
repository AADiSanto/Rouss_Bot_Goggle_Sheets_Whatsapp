# Documentación del Procfile

## Comando actual
web: gunicorn -w 1 --threads 4 --timeout 120 -b 0.0.0.0:$PORT main:app

## Parámetros
- `-w 1`          : 1 solo worker — evita múltiples instancias del scheduler
- `--threads 4`   : 4 hilos por worker — mantiene concurrencia sin gthread
- `--timeout 120` : 120 segundos antes de matar un request colgado ( Google Sheets puede ser lento )
- `-b 0.0.0.0:$PORT` : escucha en todas las interfaces, puerto inyectado por Railway
- `main:app`      : módulo main.py, variable Flask llamada app