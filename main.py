"""
Punto de entrada principal del Bot de WhatsApp para turnos
Inicializa el servidor Flask y el scheduler
"""

import os
import sys

# Agregar el directorio raíz al path para imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Crear carpeta de logs si no existe
if not os.path.exists('logs'):
    os.makedirs('logs')

# Importar la aplicación
from bot.app import app

# Importar scheduler
from sheets.scheduler_service import iniciar_scheduler

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))

    print(f"🚀 Iniciando Bot de WhatsApp en Puerto {port}...")
    print(f"📋 Webhook URL: http://localhost:{port}/webhook")
    print(f"❤️  Health Check: http://localhost:{port}/health")

    # Iniciar scheduler SOLO si no estamos en el proceso de reload de Flask
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        print("⏰ Iniciando Scheduler de Reservas...")
        iniciar_scheduler(interval_seconds=10)

    # Ejecutar Flask sin debug para producción
    # Para PROBAR y ver logs detallados
    app.run(host='0.0.0.0', port=port, debug=True)  # ✅ Usa True para desarrollo

    # Para PRODUCCIÓN (cuando uses ngrok y conectes con WhatsApp)
    #app.run(host='0.0.0.0', port=port, debug=False)  # ✅ Usa False para producción



