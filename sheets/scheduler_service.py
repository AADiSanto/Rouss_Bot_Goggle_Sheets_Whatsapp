# -*- coding: utf-8 -*-
# *********************************************************************************************************************
#  Created By: Ing. Antonio Alberto Di Santo.-
#  Created On: Lunes 06 de Octubre del 2025.-
#
#     Program       :   Bot de WhatsApp con Google Sheets,
#                          para Asignación de Turnos en Rouss Coiffeur's de MEMORY   Ingeniería en Sistemas.-
#
#    "Module Purpose:   Gestiona la creación, confirmación y expiración automática de reservas temporales de turnos,
#                       utilizando un scheduler en segundo plano para controlar tiempos límite y actualizar en Google Sheets."

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
Servicio de Programación de Tareas.-
Controla Expiración de Reservas de Turnos Temporales.-
"""

import inspect
import logging
import uuid
from datetime import datetime, timedelta
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from googleapiclient.errors import HttpError

# Importamos Funciones de sheet_service (Lectura / Actualización).-
# Asegurarse que sheets/sheet_service.py Nó Importe iniciar_scheduler al Importar Datos.-
from sheets.sheet_service import read_sheet, update_row, append_row, tz, actualizar_calendario_dia

logger = logging.getLogger(__name__)

# Tiempo por Defecto para Expiración de Reserva (en Segundos).-
RESERVA_SECONDS = 60

# Scheduler Singleton para Evitar Múltiples Instancias en el Mismo Proceso.-
_SCHEDULER = None
_JOB_ID = 'liberar_reservas_expiradas'


#Crea una Reserva Temporal del Turno, con Expiración de RESERVA_SECONDS Segundos.-
def crear_reserva_provisional(nombre, telefono, servicio, coiffeur, fecha, hora):
    """
    Crea una Reserva Temporal del Turno, con Expiración de RESERVA_SECONDS Segundos.-

    Returns:
        str: ReservationID único
    """
    # Extraer Año de la Fecha y Configurar Hoja Activa.-
    try:
        year = int(fecha.split('-')[0])
        from sheets.sheet_service import set_active_spreadsheet
        set_active_spreadsheet(year)
    except Exception as e:
        logger.warning(f"No se pudo cambiar hoja para año en fecha {fecha}: {e}")

    # --- CONTROL: Nó Permitir Turnos en Días Nó Laborables o Feriados ---
    from sheets.sheet_service import es_feriado

    if es_feriado(fecha):
        logger.warning(f"Intento de Reserva en Fecha Nó Laborable o Feriado: {fecha}")
        raise ValueError(f"❌ ERROR: Nó sé Pueden Agendar Turnos en Días Nó Laborables o Feriados ({fecha}).")

    reservation_id = str(uuid.uuid4())
    timestamp_reserva = (datetime.now(tz) + timedelta(seconds=RESERVA_SECONDS)).isoformat(sep=' ')
    fecha_registro = datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')

    values = [
        nombre,
        telefono,
        servicio,
        coiffeur,
        fecha,
        hora,
        'Pendiente',
        fecha_registro,
        reservation_id,
        timestamp_reserva,
        'TRUE'
    ]

    append_row(values)
    return reservation_id


#Confirma una Reserva Temporal del Turno y Actualiza Sú Estado.-
def confirmar_reserva(reservation_id):
    """
    Confirma una Reserva Temporal del Turno y Actualiza Sú Estado.-

    Returns:
        bool: True Sí Sé Confirmó Exitosamente, False Sí Nó Sé Encontró o Expiró.-
    """
    data = read_sheet()
    now = datetime.now(tz)

    for i, row in enumerate(data, start=2):
        try:
            if len(row) >= 11 and row[8] == reservation_id:
                # Verificar si no expiró
                # row[9] es el timestamp de expiración (string)
                ts = datetime.fromisoformat(row[9])
                if ts < now:
                    # Ya expiró
                    row[6] = 'Expirada'
                    row[10] = 'FALSE'
                    update_row(i, row)
                    return False
                else:
                    # Confirmar
                    row[6] = 'Confirmado'
                    row[7] = datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')
                    row[10] = 'FALSE'
                    update_row(i, row)
                    # Actualizar Calendario Visual, Pestaña: Rouss_Turnos_Calendario_Visual.-
                    try:
                        fecha_turno = row[4]  # Fecha del Turno
                        actualizar_calendario_dia(fecha_turno)
                        logger.info(f"Calendario Actualizado para Fecha: {fecha_turno}")
                    except Exception as e:
                        logger.error(f"ERROR al Actualizar Calendario: {e}")

                    return True

        except Exception as e:
            logger.exception(f"ERROR: al Confirmar Reserva del Turno, en Fila {i}: {e}")
            return False

    return False


#Busca y Marca como Expiradas Las Reservas que Superaron el Tiempo Límite.-
def liberar_reservas_expiradas():
    """
    Busca y Marca como Expiradas Las Reservas que Superaron el Tiempo Límite.-
    Se Ejecuta Periódicamente Según la Configuración del Scheduler.-
    """
    try:
        data = read_sheet()
    except HttpError as e:
        logger.error(f"ERROR: Leyendo Sheet en liberar_reservas_expiradas: {e}")
        return

    now = datetime.now(tz)

    for i, row in enumerate(data, start=2):
        try:
            if len(row) >= 11 and row[6] == 'Pendiente' and row[10].upper() == 'TRUE':
                ts = datetime.fromisoformat(row[9])
                if ts < now:
                    # Marcar como expirada
                    row[6] = 'Expirada'
                    row[10] = 'FALSE'
                    update_row(i, row)
                    logger.info(f"Reserva {row[8]} Expirada Automáticamente (fila {i})")
        except Exception as e:
            logger.exception(f"ERROR: al Procesar Expiración en Fila {i}: {e}")
            continue


#Inicia ( o Retorna ) el Scheduler de Tareas en Segundo Plano.-
def iniciar_scheduler(interval_seconds: int = 6):
    """
    Inicia ( o Retorna ) el Scheduler de Tareas en Segundo Plano.-
    - Evita Crear Múltiples Schedulers en el Mismo Proceso ( singleton ).-
    - Añade el Job ' liberar_reservas_expiradas ' con ' id ' para Prevenir Duplicados.-
    - Loguea el Módulo / Función que Solicitó el Inicio ( archivo:línea ).-
    - Por Defecto usa 6s para Testing; Pasár Otro Valor si sé Quiere Cambiarlo.-
    """
    global _SCHEDULER, _JOB_ID

    # Registrar el "caller" para depuración
    stack = inspect.stack()
    caller_info = "<unknown>"
    if len(stack) > 1:
        frame = stack[1]
        caller_info = f"{frame.filename}:{frame.lineno} ({frame.function})"

    logger.info(f"(scheduler) iniciar_scheduler Llamada por: {caller_info} con Intervalo={interval_seconds}s")

    # Si Yá Existe y Está en Ejecución, Devolverlo y Asegurar Job único.-
    if _SCHEDULER is not None:
        try:
            running = getattr(_SCHEDULER, "running", None)
            if running is True:
                existing_job = _SCHEDULER.get_job(_JOB_ID)
                if existing_job:
                    logger.info(f"(scheduler) Scheduler Yá en Ejecución y Job '{_JOB_ID}' Yá Presente — Nó sé Agrega...")
                    return _SCHEDULER
                else:
                    logger.info(f"(scheduler) Scheduler en Ejecución pero Job '{_JOB_ID}' Nó Existe — sé Agregará...")
                    _SCHEDULER.add_job(liberar_reservas_expiradas, 'interval',
                                       seconds=interval_seconds, id=_JOB_ID)
                    return _SCHEDULER
        except Exception:
            logger.exception("(scheduler) ERROR: Comprobando scheduler Existente; sé Recreará...")

    # Crear Nuevo Scheduler.-
    _SCHEDULER = BackgroundScheduler(timezone=tz.zone)

    # Agregar Job sí nó Existe.-
    if not _SCHEDULER.get_job(_JOB_ID):
        _SCHEDULER.add_job(liberar_reservas_expiradas, 'interval',
                           seconds=interval_seconds, id=_JOB_ID)

        logger.info(f"(scheduler) Job '{_JOB_ID}' Agregado al scheduler")

    # -------------------------------------------------------------------------------------
    # Nuevo Job: Actualiza Colores de Feriados Cada 05 Minutos (solo formato visual).-
    # -------------------------------------------------------------------------------------
    try:
        from sheets.sheet_service import colorear_feriados

        _SCHEDULER.add_job(colorear_feriados, 'interval',
                           minutes=3, id='colorear_feriados')
        logger.info(f"(scheduler) Job 'colorear_feriados' Agregado (cada 03 Minutos)...")

    except Exception as e:
        logger.error(f"(scheduler) ERROR: al Agregar Job colorear_feriados: {e}")

    _SCHEDULER.start()

    logger.info(f"(scheduler) Iniciado con Job id='{_JOB_ID}', Intervalo {interval_seconds}s, tz={tz.zone}")

    return _SCHEDULER


