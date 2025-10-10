"""
Servicio de programación de tareas
Controla expiración de reservas temporales
"""

import inspect
import logging
import uuid
from datetime import datetime, timedelta
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from googleapiclient.errors import HttpError

# Importamos funciones de sheet_service (lectura/actualización)
# Asegurarse que sheets/sheet_service.py NO importe iniciar_scheduler al importar
from sheets.sheet_service import read_sheet, update_row, append_row, tz

logger = logging.getLogger(__name__)

# Tiempo por defecto para expiración de reserva (en segundos)
RESERVA_SECONDS = 60

# Scheduler singleton para evitar múltiples instancias en el mismo proceso
_SCHEDULER = None
_JOB_ID = 'liberar_reservas_expiradas'


def crear_reserva_provisional(nombre, telefono, servicio, coiffeur, fecha, hora):
    """
    Crea una reserva temporal con expiración de RESERVA_SECONDS segundos.

    Returns:
        str: ReservationID único
    """
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


def confirmar_reserva(reservation_id):
    """
    Confirma una reserva temporal y actualiza su estado

    Returns:
        bool: True si se confirmó exitosamente, False si no se encontró o expiró
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
                    return True
        except Exception as e:
            logger.exception(f"Error al confirmar reserva en fila {i}: {e}")
            return False

    return False


def liberar_reservas_expiradas():
    """
    Busca y marca como expiradas las reservas que superaron el tiempo límite.
    Se ejecuta periódicamente según la configuración del scheduler.
    """
    try:
        data = read_sheet()
    except HttpError as e:
        logger.error(f"Error leyendo sheet en liberar_reservas_expiradas: {e}")
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
                    logger.info(f"Reserva {row[8]} expirada automáticamente (fila {i})")
        except Exception as e:
            logger.exception(f"Error al procesar expiración en fila {i}: {e}")
            continue


def iniciar_scheduler(interval_seconds: int = 6):
    """
    Inicia (o retorna) el scheduler de tareas en segundo plano.
    - Evita crear múltiples schedulers en el mismo proceso (singleton).
    - Añade el job 'liberar_reservas_expiradas' con id para prevenir duplicados.
    - Loguea el módulo/función que solicitó el inicio (archivo:línea).
    - Por defecto usa 6s para testing; pasá otro valor si querés cambiarlo.
    """
    global _SCHEDULER, _JOB_ID

    # Registrar el "caller" para depuración
    stack = inspect.stack()
    caller_info = "<unknown>"
    if len(stack) > 1:
        frame = stack[1]
        caller_info = f"{frame.filename}:{frame.lineno} ({frame.function})"

    logger.info(f"(scheduler) iniciar_scheduler llamada por {caller_info} con intervalo={interval_seconds}s")

    # Si ya existe y está en ejecución, devolverlo y asegurar job único
    if _SCHEDULER is not None:
        try:
            running = getattr(_SCHEDULER, "running", None)
            if running is True:
                existing_job = _SCHEDULER.get_job(_JOB_ID)
                if existing_job:
                    logger.info(f"(scheduler) Scheduler ya en ejecución y job '{_JOB_ID}' ya presente — no se agrega.")
                    return _SCHEDULER
                else:
                    logger.info(f"(scheduler) Scheduler en ejecución pero job '{_JOB_ID}' no existe — se agregará.")
                    _SCHEDULER.add_job(liberar_reservas_expiradas, 'interval',
                                       seconds=interval_seconds, id=_JOB_ID)
                    return _SCHEDULER
        except Exception:
            logger.exception("(scheduler) Error comprobando scheduler existente; se recreará")

    # Crear nuevo scheduler
    _SCHEDULER = BackgroundScheduler(timezone=tz.zone)

    # Agregar job si no existe
    if not _SCHEDULER.get_job(_JOB_ID):
        _SCHEDULER.add_job(liberar_reservas_expiradas, 'interval',
                           seconds=interval_seconds, id=_JOB_ID)
        logger.info(f"(scheduler) Job '{_JOB_ID}' agregado al scheduler")

    _SCHEDULER.start()
    logger.info(f"(scheduler) Iniciado con job id='{_JOB_ID}', intervalo {interval_seconds}s, tz={tz.zone}")
    return _SCHEDULER


