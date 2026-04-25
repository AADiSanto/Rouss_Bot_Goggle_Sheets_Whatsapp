# -*- coding: utf-8 -*-
# *********************************************************************************************************************
#  Created By: Ing. Antonio Alberto Di Santo.-
#  Created On: Lunes 06 de Octubre del 2025.-
#
#     Program       :   Bot de WhatsApp con Google Sheets,
#                          para Asignación de Turnos en Negocios de Coiffeur's de MEMORY   Ingeniería en Sistemas.-
#
#    "Module Purpose:   Punto de Entrada Principal del Bot de WhatsApp para Gestión de Turnos.-
#                       Inicializa el Servidor Flask en el Puerto Especificado, Configura el Scheduler
#                       para Procesamiento Automático de Reservas cada 30 Segundos, y Ejecuta el Coloreo
#                       Automático de Feriados en Google Sheets al Iniciar la Aplicación.-
#
#
# *********************************************************************************************************************
#
#  *** Python v3.13.6
#
#  *** Compilar en el Directorio del Programa desde PowerShell como Administrador ( Nó es Necesario ).-
#
#  ***     pyinstaller --onefile --noconsole Transistor_MosFET_Parámetros_Curva_Trabajo.py
#
#          Para Incluír un ícono en el .exe:
#
#          Buscar el Icono en: https://www.svgrepo.com/
#
#             Guardarlo como .svg
#
#          Luego Converirlo de .svg a .ico en: https://convertico.com/es/svg-a-ico/
#
#  ***     pyinstaller --onefile --icon=MosFET.ico Transistor_MosFET_Parámetros_Curva_Trabajo.py
#
#  ***        El .exe Compilado Estará Dentro de la Carpeta "dist".-
#
# *********************************************************************************************************************

"""
Punto de entrada principal del Bot de WhatsApp para turnos
Inicializa el servidor Flask y el scheduler
"""

import os
import sys

import logging
logging.getLogger().handlers.clear()

# Agregar el Directorio Raíz Al Path Para Imports.-
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Crear Carpeta De Logs Sí Nó Existe.-
if not os.path.exists('logs'):
    os.makedirs('logs')

#Debug para RailWay.-
print("=== VARIABLES QUE RAILWAY ME ESTÁ PASANDO ===")
# Esto imprimirá los nombres de las variables, pero no los valores secretos
print(list(os.environ.keys()))
print("=============================================")

# Importar Lá Aplicación.-
from bot.app import app

# Importar Scheduler.-
from sheets.scheduler_service import iniciar_scheduler
from sheets.sheet_service import colorear_feriados

# Importar Obtener Año Activo.-
from sheets.sheet_service import set_active_spreadsheet, get_current_year

SYSTEM_MODE = os.getenv("SYSTEM_MODE", "disabled").lower()

print(f"🚀 Sistema Iniciado en Modo: {SYSTEM_MODE.upper()}")

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))

    print(f"🚀 Iniciando Bot de WhatsApp en Puerto {port}...")
    print(f"📋 Webhook URL: http://localhost:{port}/webhook")
    print(f"❤️  Health Check: http://localhost:{port}/health")

    # Iniciar scheduler SOLO sí nó Estamos en el Proceso de Reload de Flask.-
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        print("⏰ Iniciando Scheduler de Reservas...")

        # --------------------------------------------------------
        # Configurar Hoja del Año Actual al Iniciar.-
        # --------------------------------------------------------
        try:
            current_year = get_current_year()
            set_active_spreadsheet(current_year)
            print(f"📅 Hoja del Año {current_year} Configurada...")
        except Exception as e:
            print(f"⚠️  ERROR: al Configurar Hoja del Año: {e}")

        # --------------------------------------------------------
        # Colorear Hoja de Feriados Automáticamente al Iniciar.-
        # --------------------------------------------------------
        try:
            colorear_feriados()
            print("🎨 Coloreo Automático de Feriados Completado...")
        except Exception as e:
            print(f"⚠️  ERROR: al Colorear Feriados: {e}")

        # Iniciar Scheduler ( Verificar Cada 10 Segundos... ).-
        scheduler = iniciar_scheduler(interval_seconds=30)  # ← Cambiar de 10 a 30.-
        print(f"⏰ Scheduler Iniciado - Job Activo: {scheduler.get_jobs()}")

    # Ejecutar Flask sin debug para producción
    app.run(host='0.0.0.0', port=port, debug=True)  # ✅ Usa True para desarrollo


