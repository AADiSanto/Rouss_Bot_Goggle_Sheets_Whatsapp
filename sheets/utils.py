# -*- coding: utf-8 -*-
# *********************************************************************************************************************
#  Created By: Ing. Antonio Alberto Di Santo.-
#  Created On: Lunes 06 de Octubre del 2025.-
#
#     Program       :   Bot de WhatsApp con Google Sheets,
#                          para Asignación de Turnos en Negocios de Coiffeur's de MEMORY   Ingeniería en Sistemas.-
#
#    "Module Purpose:   utils.py | Funciones Helper's y Gestión Centralizada de Zona Horaria.-
#
# *********************************************************************************************************************

import os
import logging

from datetime import datetime, timedelta # <--- Agregar timedelta

from dotenv import load_dotenv
from pytz import timezone, UnknownTimeZoneError

# Configuración de Logger.-
logger = logging.getLogger(__name__)

load_dotenv()

# -------------------------------------------------------------------------
# GESTIÓN DE ZONA HORARIA ( Localización Argentina / España / Mallorca )
# -------------------------------------------------------------------------

# Leer la Zona Horaria desde .env o Railway ( Ej: 'Europe/Madrid' o 'America/Argentina/Buenos_Aires' ).-
TZ_NAME = os.getenv('TIMEZONE', 'America/Argentina/Buenos_Aires')

try:
    # Definición Global del Objeto Timezone.-
    tz = timezone(TZ_NAME)
except UnknownTimeZoneError:
    logger.error(f"(utils) Zona Horaria '{TZ_NAME}' Inválida en .env. Usando UTC por Defecto.-")
    tz = timezone('UTC')

# ✅ LOG DE VERIFICACIÓN DE ZONA HORARIA
# Este Mensaje Saldrá en PyCharm y en los Logs de RailWay.-
print(f"🌍 CONFIGURACIÓN DE RED: Zona Horaria Detectada -> {tz.zone}")
logger.info(f"Reloj del Sistema Sincronizado con: {tz.zone}")


def obtener_ahora():
    """Retorna el Objeto Datetime Actual Siempre con la Zona Horaria Correcta.-"""
    return datetime.now(tz)


# -------------------------------------------------------------------------
# HELPERS / NORMALIZACIÓN
# -------------------------------------------------------------------------

def normalizar_hora(hora_str):
    """Asegura el Formato HH:MM ( Agrega Cero a la Izquierda Sí es Necesario ).-"""
    try:
        h, m = hora_str.strip().split(':')
        return f"{int(h):02d}:{m}"
    except:
        return hora_str.strip()


def hora_a_time(hora_str):
    """Convierte un String HH:MM a un Objeto Time de Python.-"""
    try:
        h, m = hora_str.strip().split(':')
        # Usamos un objeto datetime temporal para la conversión.-
        return datetime.strptime(f"{int(h):02d}:{m}", "%H:%M").time()
    except:
        return None

def formatear_fecha_leible(fecha_dt):
    """Helper para Mostrar Fechas en los Mensajes de WhatsApp ( Ej: Lunes 06/10 ).-"""
    # Útil para el Feedback al Usuario.-
    return fecha_dt.strftime("%d/%m/%Y %H:%M")


# -------------------------------------------------------------------------
# CONTROL DE LOGS ( Throttle para Reducir Costos en Railway )
# -------------------------------------------------------------------------

# Diccionario Global para Registrar la Última vez que Salió cada Mensaje.-
_ultimo_log: dict = {}

# Leer el Flag desde .env.-
LOGS_CADA_HORA = os.getenv('LOGS_CADA_HORA', 'false').lower() == 'true'


def log_throttled(nivel: str, mensaje: str, logger_ref=None):
    """
    Emite un Log Respetando el Flag LOGS_CADA_HORA del .env.-
        - Si LOGS_CADA_HORA=false : Siempre Muestra el Log.-
        - Si LOGS_CADA_HORA=true  : Muestra el Log Solo 1 Vez por Cada 03 Horas ( Errores Siempre Salen ).-

    Args:
        nivel     : 'info' | 'warning' | 'error' | 'debug'
        mensaje   : Texto del log.-
        logger_ref: Logger del Módulo que Llama ( Opcional ).-
    """
    nivel = nivel.lower()
    es_error = nivel == 'error'

    # Los Errores SIEMPRE Salen Sin Importar el Flag.-
    if es_error or not LOGS_CADA_HORA:
        _emitir_log(nivel, mensaje, logger_ref)
        return

    # Throttle: Sólo Emitir si Pasó más de 360 Segundos ( 06 Minutos ), desde la última Vez.-
    ahora = datetime.now(tz)
    ultima = _ultimo_log.get(mensaje)

     # Cada 3 Horas el Log.-
    if ultima is None or (ahora - ultima) >= timedelta(hours=3):
        _ultimo_log[mensaje] = ahora
        _emitir_log(nivel, mensaje, logger_ref)


def _emitir_log(nivel: str, mensaje: str, logger_ref=None):
    """Función Interna que Despacha el Log al Logger Correcto.-"""
    ref = logger_ref or logger
    getattr(ref, nivel, ref.info)(mensaje)


