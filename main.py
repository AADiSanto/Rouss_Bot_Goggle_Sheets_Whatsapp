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
#                       para Procesamiento Automático de Reservas ( Intervalo Configurable desde .env ),
#                       y Ejecuta el Coloreo Automático de Feriados en Google Sheets,
#                       ( Intervalo Configurable desde .env ), al Iniciar la Aplicación.-
#
# *********************************************************************************************************************
#
#  *** Python v3.13.6
#
#  *** Compilar en el Directorio del Programa desde PowerShell como Administrador ( Nó es Necesario ).-
#
#  *** pyinstaller --onefile --noconsole Transistor_MosFET_Parámetros_Curva_Trabajo.py
#
#          Para Incluír un ícono en el .exe:
#
#          Buscar el Icono en: https://www.svgrepo.com/
#
#             Guardarlo como .svg
#
#          Luego Converirlo de .svg a .ico en: https://convertico.com/es/svg-a-ico/
#
#  *** pyinstaller --onefile --icon=MosFET.ico Transistor_MosFET_Parámetros_Curva_Trabajo.py
#
#  *** El .exe Compilado Estará Dentro de la Carpeta "dist".-
#
# *********************************************************************************************************************

# ---------------------------------------------------------------------------------
# IMPORTANTE en Producción ( RAILWAY ):
# En Producción Nó se usa en el Archivo "Procfile" "web: python main.py"
# Railway Debe Arrancar con Gunicorn Usando:
#     web: gunicorn -w 1 -k gthread -b 0.0.0.0:$PORT main:app
#
# Esto Evita Usar El Servidor De Desarrollo de Flask y Problemas de Concurrencia...
# ---------------------------------------------------------------------------------

"""
Punto de entrada principal del Bot de WhatsApp para turnos
Inicializa el servidor Flask y el scheduler
"""

import os
import sys
import logging
from dotenv import load_dotenv

# 1. Cargar variables de entorno inmediatamente (En Railway no hace nada, en Local carga el .env).-
load_dotenv()

logging.getLogger().handlers.clear()

# Agregar el Directorio Raíz Al Path Para Imports.-
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ✅ PASO CRÍTICO: Crear Carpeta De Logs ANTES de importar la App para evitar el FileNotFoundError.-
if not os.path.exists('logs'):
    os.makedirs('logs')

# ✅ 1. Importar Lá Aplicación de Flask (Ahora sí, con la carpeta de logs ya creada para que bot.log no falle).-
from bot.app import app, NOMBRE_EMPRESA

# ✅ 2. Importar de Tiempo y Zona Horaria ( Protección contra conflicto de carpetas en Railway ).-
try:
    # Como ahora vive en sheets/utils.py, lo llamamos desde allí
    from sheets.utils import tz, obtener_ahora

    ahora = obtener_ahora()
    # ✅ Este print Confirmará que el main.py También vé Lá Hora Correcta.-
    print(f"🌍 CONFIGURACIÓN DE RED: Zona Horaria -> {tz.zone}")
    print(f"⏰ RELOJ DEL SISTEMA: {ahora.strftime('%d/%m/%Y %H:%M:%S')}")

except Exception as e:
    print(f"⚠️ ERROR Crítico al Importar utils en main: {e}")
    # Fallback de emergencia por si algo falla en la ruta
    from pytz import timezone
    from datetime import datetime

    tz = timezone(os.getenv('TIMEZONE', 'America/Argentina/Buenos_Aires'))

    def obtener_ahora():
        return datetime.now(tz)

# ✅ 3. Importación de Servicios ( Ahora que el path está Listo )
from sheets.scheduler_service import iniciar_scheduler

# Debug para RailWay.-
print("=== VARIABLES QUE RAILWAY ME ESTÁ PASANDO ===")
# Esto imprimirá los nombres de las variables, pero no los valores secretos
print(list(os.environ.keys()))
print("=============================================")

# Importar Scheduler y Coloreo.-
from sheets.sheet_service import colorear_feriados

# Importar Obtener Año Activo.-
from sheets.sheet_service import set_active_spreadsheet, get_current_year

# 4. Definición Global de Modo y Puerto (Accesible para Railway y Local).-
SYSTEM_MODE = os.getenv("SYSTEM_MODE", "disabled").lower()
port = int(os.getenv('PORT', 5000))

print(f"🚀 Sistema Iniciado en Modo: {SYSTEM_MODE.upper()}")

# -------------------------------------------------------------------------
# 5. Inicialización Global (Fuera del __main__ para que Gunicorn lo vea)
# -------------------------------------------------------------------------
try:
    current_year = get_current_year()
    set_active_spreadsheet(current_year)
    print(f"📅 Hoja del Año {current_year} Configurada...")
except Exception as e:
    print(f"⚠️  ERROR: al Configurar Hoja del Año: {e}")

# ✅ Pre-Carga de Caché de Datos Estáticos del Negocio al Iniciar.-
try:
    from sheets.sheet_service import refrescar_cache_negocio
    from sheets.sheet_service import obtener_staff_negocio, obtener_staff_con_ids
    from sheets.sheet_service import obtener_servicios_negocio
    from sheets.sheet_service import generar_horarios_disponibles_dia, es_feriado
    from sheets.utils import obtener_ahora as _ahora_cache
    refrescar_cache_negocio()
    obtener_staff_negocio()
    obtener_staff_con_ids()
    obtener_servicios_negocio()
    generar_horarios_disponibles_dia(_ahora_cache().strftime('%Y-%m-%d'))
    es_feriado(_ahora_cache().strftime('%Y-%m-%d'))
    print("✅ Caché de Datos Estáticos del Negocio Pre-Cargado Correctamente al Iniciar...")
    
except Exception as e:
    print(f"⚠️  ERROR: al Pre-Cargar Caché del Negocio: {e}")


# ---------------------------------------------------------------------------------
# INICIO DEL SISTEMA ( MEMORY Ingeniería en Sistemas )
# ---------------------------------------------------------------------------------

# Iniciar Scheduler - Intervalo Configurable desde .env ( TIEMPO_LIBERAR_RESERVAS_SEGUNDOS ).-
if SYSTEM_MODE != "production":
    print("⏰ Iniciando Scheduler de Reservas...")

try:
    # Iniciar Scheduler.-
    scheduler = iniciar_scheduler()

    # ✅ Verificación de Seguridad y Confirmación de Jobs.-
    if scheduler:
        if SYSTEM_MODE != "production":
            print(f"⏰ Scheduler Iniciado - Jobs Activos: {[j.id for j in scheduler.get_jobs()]}")
        else:
            # En Producción un único mensaje limpio.-
            print("🚀 Sistema de Gestión de Turnos: SCHEDULER ACTIVO.-")
    else:
        print("⚠️  ADVERTENCIA: El Scheduler Nó sé Pudo Iniciar Correctamente...")
except Exception as e:
    print(f"⚠️  ERROR Crítico al Arrancar el Scheduler: {e}")
    scheduler = None

if __name__ == '__main__':
    # Mensaje de Bienvenida Profesional.-
    print(f"\n***********************************************************************")
    print(f"  BOT DE WHATSAPP - {NOMBRE_EMPRESA.upper()}")
    print(f"  Modo de Ejecución: {SYSTEM_MODE.upper()}")
    print(f"***********************************************************************\n")

    # Import Único de la Variable de Control de Logs.-
    from sheets.utils import LOGS_INTERVALO_HORAS

    # Este Bloque Sólo Muestra Detalles Técnicos én Desarrollo Local ( PyCharm ).-
    # MODO Desarrollo.-
    if SYSTEM_MODE != "production":
        print(f"🚀 Servidor Activo en Puerto        : {port}")
        print(f"📋 Webhook URL: http://localhost    :{port}/webhook")
        print(f"❤️  Health Check: http://localhost  :{port}/health")
        print(f"🔍 LOGS_INTERVALO_HORAS - Desarrollo: {LOGS_INTERVALO_HORAS}")
        print("🧪 Ejecutando en MODO DESARROLLO ( Flask Debug )...")
        # ✅ En Railway ( demo ) debug=False para Evitar Doble Carga de Módulos.-
        # En PyCharm Local ( sin RAILWAY_ENVIRONMENT ) debug=True para Desarrollo.-
        en_railway = bool(os.getenv("RAILWAY_ENVIRONMENT"))
        app.run(host='0.0.0.0', port=port, debug=not en_railway, use_reloader=False)

    else:
        # MODO production.-
        print(f"🔍 LOGS_INTERVALO_HORAS - production: {LOGS_INTERVALO_HORAS}")
        # En Producción ( RailWay ) Arrancamos Sín Debug Para Estabilidad Absoluta.-
        app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)


