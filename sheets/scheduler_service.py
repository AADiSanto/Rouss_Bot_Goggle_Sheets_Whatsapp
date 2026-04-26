# -*- coding: utf-8 -*-
# *********************************************************************************************************************
#  Created By: Ing. Antonio Alberto Di Santo.-
#  Created On: Lunes 06 de Octubre del 2025.-
#
#     Program       :   Bot de WhatsApp con Google Sheets,
#                          para Asignación de Turnos en Negocios de Coiffeur's de MEMORY   Ingeniería en Sistemas.-
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
import socket
import pytz
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from googleapiclient.errors import HttpError

# Importamos las constantes y servicios necesarios
# Nota: Quitamos 'from bot.app import DIAS, MESES' si ya los Definimos Abajo.-
# para evitar que cargue todo el bot antes de tiempo.-

from datetime import datetime

from sheets.test_sheet import data

# Diccionarios en Castellano.-
DIAS = {
    'Monday': 'Lunes', 'Tuesday': 'Martes', 'Wednesday': 'Miércoles',
    'Thursday': 'Jueves', 'Friday': 'Viernes', 'Saturday': 'Sábado', 'Sunday': 'Domingo'
}

MESES = {
    'January': 'Enero', 'February': 'Febrero', 'March': 'Marzo', 'April': 'Abril',
    'May': 'Mayo', 'June': 'Junio', 'July': 'Julio', 'August': 'Agosto',
    'September': 'Septiembre', 'October': 'Octubre', 'November': 'Noviembre', 'December': 'Diciembre'
}

from datetime import datetime, timedelta
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from googleapiclient.errors import HttpError

# Importamos Funciones de bot.app
#from bot.app import DIAS, MESES

# Importamos Funciones de sheet_service (Lectura / Actualización).-
# Asegurarse que sheets/sheet_service.py Nó Importe iniciar_scheduler al Importar Datos.-
from sheets.sheet_service import read_sheet, update_row, append_row, tz, \
    reconstruir_calendario_completo, validar_fecha_hora_turno, ordenar_hoja

import logging
logging.getLogger().handlers.clear()
logger = logging.getLogger(__name__)

# Tiempo por Defecto para Expiración de Reserva ( en Segundos ).-
RESERVA_SECONDS = 180  # ← Cambiar de 120 a 180 Segundos = 03 Minutos.-

# Scheduler Singleton para Evitar Múltiples Instancias en el Mismo Proceso.-
_SCHEDULER = None
_JOB_ID = 'liberar_reservas_expiradas'


# Crea una Reserva Temporal del Turno, con Expiración de RESERVA_SECONDS Segundos.-
def crear_reserva_provisional(nombre, telefono, servicio, coiffeur, fecha, hora):
    """
    Crea una Reserva Temporal del Turno, con Expiración de RESERVA_SECONDS Segundos.-

    Returns:
        str: ReservationID único
    """

    # --------------------------------------------------
    # Extraer Año de la Fecha y Configurar Hoja Activa.-
    # --------------------------------------------------
    try:
        # Normalizar Fecha Sí Viene en Formato Largo Español.-
        if ',' in fecha:
            # Formato: "Miércoles, 26 de Noviembre de 2025"
            partes = fecha.split(',')[1].strip().split(' ')
            year = int(partes[4])
        else:
            # Formato ISO: "2025-11-26"
            year = int(fecha.split('-')[0])

        from sheets.sheet_service import set_active_spreadsheet
        set_active_spreadsheet(year)

    except Exception as e:
        logger.warning(f"Nó Sé Pudo Cambiar Hoja para Año en Fecha {fecha}: {e} ...")

    # ----------------------------------------
    # VALIDACIONES DEL NEGOCIO: Fecha y Hora.-
    # ----------------------------------------
    try:
        validar_fecha_hora_turno(fecha, hora)
    except ValueError as e:
        raise ValueError(str(e))

    # --------------------------------------------------------------
    # CONTROL: Nó Permitir Turnos en Días Nó Laborables o Feriados.-
    # --------------------------------------------------------------
    from sheets.sheet_service import es_feriado

    if es_feriado(fecha):
        logger.warning(f"Intento de Reserva en Fecha Nó Laborable o Feriado: {fecha} ...")
        raise ValueError(
            f"❌ ERROR: Nó sé Pueden Agendar Turnos en Días Nó Laborables o Feriados ({fecha}) ..."
        )

    # ----------------------------------------------------
    # Generar Identificador Único de la Reserva Temporal.-
    # ----------------------------------------------------
    reservation_id = str(uuid.uuid4())

    # Timestamp de Expiración ( Guardado Como Texto en la Hoja ).-
    ts_expira = (datetime.now(tz) + timedelta(seconds=RESERVA_SECONDS)).isoformat(sep=' ')

    # ----------------------------------------------------
    # Fecha Registro en Castellano (Momento de Creación).-
    # ----------------------------------------------------
    now = datetime.now(tz)
    dia_ing = now.strftime('%A')
    mes_ing = now.strftime('%B')

    dia_esp = DIAS[dia_ing]
    mes_esp = MESES[mes_ing]

    fecha_registro = (
        f"{dia_esp}, {now.day} de {mes_esp} de "
        f"{now.year} {now.strftime('%H:%M:%S')}"
    )

    # --------------------------------------------------
    # Extraer FechaISO ( YYYY-MM-DD ) Para Columna N.-
    # --------------------------------------------------
    meses_num = {
        'Enero': 1, 'Febrero': 2, 'Marzo': 3, 'Abril': 4,
        'Mayo': 5, 'Junio': 6, 'Julio': 7, 'Agosto': 8,
        'Septiembre': 9, 'Octubre': 10, 'Noviembre': 11, 'Diciembre': 12
    }
    try:
        if ',' in fecha:
            partes = fecha.split(',')[1].strip().split(' ')
            fecha_iso = f"{int(partes[4])}-{meses_num[partes[2]]:02d}-{int(partes[0]):02d}"
        else:
            fecha_iso = fecha  # ← Ya Viene en Formato ISO.-
    except Exception:
        fecha_iso = ''

    # ----------------------------------------------
    # Fila Completa Para Insertar en Google Sheets.-
    # ----------------------------------------------
    values = [
        nombre,            # A
        telefono,          # B
        servicio,          # C
        coiffeur,          # D
        fecha,             # E
        hora,              # F
        'Pendiente',       # G
        'TRUE',            # H ← Activo
        '',                # I - Valor_del_Servicio
        '',                # J - SubTOTALES
        fecha_registro,    # K
        reservation_id,    # L
        ts_expira,         # M - Expira
        fecha_iso          # N ← FechaISO para Ordenar ( YYYY-MM-DD ).-
    ]

    # Escritura en Google Sheets.-
    append_row(values)

    return reservation_id


# Confirma una Reserva Temporal del Turno y Actualiza Sú Estado.-
def confirmar_reserva(reservation_id):
    """
    Confirma una Reserva Temporal del Turno y Actualiza Sú Estado.-

    Returns:
        bool: True Sí Sé Confirmó Exitosamente, False Sí Nó Sé Encontró o Expiró.-
    """

    logger.info(f"🔍 Iniciando Confirmación de Reserva {reservation_id} ...")

    # -------------------------------------------------------------------
    # LECTURA SEGURA DE LA HOJA.
    # El timeout está configurado a nivel httplib2 en sheet_service.
    # -------------------------------------------------------------------
    try:
        data = read_sheet()
    except Exception as e:
        logger.error(f"❌ ERROR: al Leer Google Sheets: {type(e).__name__}: {e} ...")
        return False

    ahora_confirmación = datetime.now(tz)

    # -------------------------------------------------------------------------------
    # 1) BUSCAR TODAS LAS FILAS QUE COINCIDAN CON EL reservation_id (1 sola pasada).-
    # -------------------------------------------------------------------------------
    filas_encontradas = [
        (i, row) for i, row in enumerate(data, start=2)
        if len(row) >= 13 and row[11] == reservation_id
    ]

    # Sí Nó Hay Ninguna Fila → Nó Existe.-
    if not filas_encontradas:
        logger.warning(f"⚠️ Reserva {reservation_id} Nó Encontrada en Ninguna Fila...")
        return False

    # Sólo Debe Existir Una Fila, Sí Hubiera Más, Igual Tomamos La Primera.-
    i, row = filas_encontradas[0]
    logger.info(f"📍 Fila Encontrada para Confirmación: {i} ...")

    estado_actual = row[6]
    activo = row[7].upper()

    # ------------------------------------------------------------------------
    # 2) SI YA FUE CONFIRMADA → ÉXITO INMEDIATO (evitar duplicados WhatsApp).-
    # ------------------------------------------------------------------------
    if estado_actual == 'Confirmado':
        logger.info(f"✔ Reserva {reservation_id} Yá Estaba Confirmada. Evitando Duplicado...")
        return True

    # ------------------------------------------------
    # 3) SI ESTÁ EXPIRADA O CANCELADA → NO CONFIRMAR.-
    # ------------------------------------------------
    if estado_actual in ['Expirada', 'Cancelada'] or activo == 'FALSE':
        logger.warning(f"Reserva {reservation_id} Nó Activa (Estado: {estado_actual}) ...")
        return False

    # ---------------------------------------
    # 4) VERIFICAR EXPIRACIÓN DEL TIMESTAMP.-
    # ---------------------------------------
    try:
        ts_expira = datetime.fromisoformat(row[12])
        if ts_expira.tzinfo is None:
            ts_expira = tz.localize(ts_expira)
    except:
        logger.error("❌ ERROR: Timestamp de Expiración Inválido en la Hoja ...")
        return False

    if ts_expira < ahora_confirmación:
        logger.warning(f"Reserva {reservation_id} Yá Expiró...")
        row[6] = 'Expirada'
        row[7] = 'FALSE'
        update_row(i, row)
        return False

    # ---------------------------------------------------------------
    # 5) CONTROL DE DISPONIBILIDAD (EVITANDO BLOQUEARSE A SÍ MISMA).-
    # ---------------------------------------------------------------
    coiffeur_actual = row[3]
    fecha_turno = row[4]
    hora_turno = row[5]

    from sheets.sheet_service import check_availability

    # Primero Chequeamos Disponibilidad General.-
    disponible = check_availability(coiffeur_actual, fecha_turno, hora_turno)

    if not disponible:
        # Confirmamos Sí Hay OTRO Turno Real Confirmado en Ese Horario.-
        for j, otra in enumerate(data, start=2):
            if j != i and len(otra) >= 13:
                if (
                    otra[3] == coiffeur_actual and
                    otra[4] == fecha_turno and
                    otra[5] == hora_turno and
                    otra[6] == 'Confirmado'
                ):
                    logger.warning(
                        f"❌ ERROR: Choque Real con Otra Reserva Confirmada en: "
                        f"{fecha_turno} {hora_turno} ..."
                    )
                    return False
        # Sí Nó Hay Choques Reales → Permitir Confirmación.-

    # ----------------------
    # 6) CONFIRMAR RESERVA.-
    # ----------------------
    logger.info(f"✅ Confirmando Reserva {reservation_id}...")

    row[6] = 'Confirmado'
    row[7] = 'FALSE'   # Activo Desde Aquí Pasa a FALSE.-

    momento_confirmación = datetime.now(tz)
    dia_ing = momento_confirmación.strftime('%A')
    mes_ing = momento_confirmación.strftime('%B')

    dia_esp = DIAS[dia_ing]
    mes_esp = MESES[mes_ing]

    row[10] = (
        f"{dia_esp}, {momento_confirmación.day} de {mes_esp} de "
        f"{momento_confirmación.year} {momento_confirmación.strftime('%H:%M:%S')}"
    )

    update_row(i, row)
    logger.info(f"✔ Reserva Actualizada en Google Sheets (Fila {i}) ...")

    # ------------------------------------------------
    # Ordenar Hoja por FechaISO ( Col N ) y Hora ( Col F ).-
    # ------------------------------------------------
    try:
        logger.info(f"📊 Ordenando Hoja Principal...")
        ordenar_hoja()
        logger.info(f"✔ Hoja Ordenada Exitosamente...")
    except Exception as e:
        logger.error(f"❌ ERROR al Ordenar Hoja: {e} ...")

    # ------------------------------------------------
    # 7) RECONSTRUIR CALENDARIO VISUAL COMPLETO.-
    #    Regenera TODAS las fechas confirmadas, no solo la del turno nuevo.
    # ------------------------------------------------
    try:
        logger.info(f"📅 Reconstruyendo Calendario Visual Completo...")
        reconstruir_calendario_completo()
        logger.info(f"✔ Calendario Visual Reconstruido Exitosamente...")
    except Exception as e:
        logger.error(f"❌ ERROR Reconstruyendo Calendario: {e} ...")

    return True


#Busca y Marca como Expiradas Las Reservas que Superaron el Tiempo Límite.-
def liberar_reservas_expiradas():
    """
    Busca y Marca como Expiradas las Reservas que Superaron el Tiempo Límite.
    Ejecutado periódicamente por el scheduler.
    """
    logger.info(">>> 🔄 Ejecutando: 'liberar_reservas_expiradas()'...")

    # El timeout ya está configurado en el cliente httplib2 dentro de sheet_service.
    # NO usar socket.setdefaulttimeout() aquí: no es thread-safe con APScheduler.
    try:
        data = read_sheet()
    except HttpError as e:
        logger.error(f"ERROR Leyendo Sheet en 'liberar_reservas_expiradas': {e}")
        return
    except Exception as e:
        # Captura también TimeoutError, httplib2.ServerNotFoundError, etc.
        logger.error(f"ERROR / TIMEOUT al Leer Sheet: {type(e).__name__}: {e}")
        return

    now = datetime.now(tz)

    for i, row in enumerate(data, start=2):
        try:
            if len(row) >= 13 and row[6] == 'Pendiente' and row[7].upper() == 'TRUE':
                timestamp_str = row[12].strip()

                logger.debug(
                    f"(DEBUG) Procesando Fila {i}: Estado={row[6]}, Activo={row[7]}, Timestamp={timestamp_str}")

                try:
                    # Parsear timestamp que YA tiene Zona Horaria.-
                    ts = datetime.fromisoformat(timestamp_str)

                    # Si por Alguna Razón Nó Tiene Zona Horaria, Agregarla.-
                    if ts.tzinfo is None:
                        ts = tz.localize(ts)

                    logger.debug(f"(DEBUG) Timestamp Parseado: {ts}, Comparando con: {now}")

                    if ts < now:
                        # Marcar como Expirada.-
                        logger.info(f"⚠️ Marcando Reserva {row[11]} como EXPIRADA...")
                        row[6] = 'Expirada'  # Cambiar Estado
                        row[7] = 'FALSE'  # Desactivar

                        # Asegurarse de que la Fila tenga Todas las Columnas.-
                        while len(row) < 13:
                            row.append('')

                        update_row(i, row)
                        logger.info(f"✅ Reserva {row[11]} Expirada Automáticamente (Fila {i})")

                    else:
                        tiempo_restante = (ts - now).total_seconds()
                        logger.debug(f"(DEBUG) Reserva {row[11]} aún Válida - Expira en {tiempo_restante:.0f}s")

                except ValueError as ve:
                    logger.error(f"ERROR: Parseando timestamp en Fila {i}: {timestamp_str} - {ve}")
                    continue

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
    # Nuevo Job: Actualiza Colores de Feriados Cada 15 Minutos ( Sólo Formato Visual ).-
    # -------------------------------------------------------------------------------------
    try:
        from sheets.sheet_service import colorear_feriados

        _SCHEDULER.add_job(colorear_feriados, 'interval',
                           minutes=15, id='colorear_feriados')
        logger.info(f"(scheduler) Job 'colorear_feriados' Agregado (cada 15 Minutos)...")

    except Exception as e:
        logger.error(f"(scheduler) ERROR: al Agregar Job colorear_feriados: {e}")

    _SCHEDULER.start()

    logger.info(f"(scheduler) Iniciado con Job id='{_JOB_ID}', Intervalo {interval_seconds}s, tz={tz.zone}")

    return _SCHEDULER


