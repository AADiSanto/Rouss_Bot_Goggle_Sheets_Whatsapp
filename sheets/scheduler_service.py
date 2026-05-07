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

"""
Servicio de Programación de Tareas.-
Controla Expiración de Reservas de Turnos Temporales.-
"""

import inspect
import logging
import uuid
import socket

from apscheduler.schedulers.background import BackgroundScheduler
from googleapiclient.errors import HttpError

# Importamos las constantes y servicios necesarios.-
from datetime import datetime, timedelta

# ZONAS HORARIAS CENTRALIZADAS ( MEMORY Ingeniería en Sistemas ):
from sheets.utils import logger, obtener_ahora, tz

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

# Importamos Funciones de sheet_service (Lectura / Actualización).-
# Importamos 'tz' desde sheet_service para mantener la localización del motor.-
from sheets.sheet_service import read_sheet, update_row, append_row, tz, \
    reconstruir_calendario_completo, validar_fecha_hora_turno, ordenar_hoja, \
    actualizar_calendario_dia, _invalidar_servicio_hilo

import logging
logging.getLogger().handlers.clear()
logger = logging.getLogger(__name__)

# Tiempo por Defecto para Expiración de Reserva ( en Segundos ).-
RESERVA_SECONDS = 60  # ← Cambiar de 33 a 60 Segundos = 01 Minutos.-

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

    # Usamos el Motor de Tiempo de MEMORY Ingeniería en Sistemas.-
    now = obtener_ahora()

    # Timestamp de Expiración ( Guardado Como Texto en la Hoja ).-
    ts_expira = (now + timedelta(seconds=RESERVA_SECONDS)).isoformat(sep=' ')

    # ----------------------------------------------------
    # Fecha Registro en Castellano (Momento de Creación).-
    # ----------------------------------------------------
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
    # -------------------------------------------------------------------
    try:
        data = read_sheet()
    except Exception as e:
        logger.error(f"❌ ERROR: al Leer Google Sheets: {type(e).__name__}: {e} ...")
        return False

    # Usamos el Motor de Tiempo de MEMORY Ingeniería en Sistemas.-
    ahora_confirmación = obtener_ahora()

    # -------------------------------------------------------------------------------
    # 1) BUSCAR TODAS LAS FILAS QUE COINCIDAN CON EL reservation_id.-
    # -------------------------------------------------------------------------------
    filas_encontradas = [
        (i, row) for i, row in enumerate(data, start=2)
        if len(row) >= 13 and row[11] == reservation_id
    ]

    if not filas_encontradas:
        logger.warning(f"⚠️ Reserva {reservation_id} Nó Encontrada en Ninguna Fila...")
        return False

    i, row = filas_encontradas[0]
    logger.info(f"📍 Fila Encontrada para Confirmación: {i} ...")

    estado_actual = row[6]
    activo = (row[7] or '').upper()

    # ------------------------------------------------------------------------
    # 2) SI YA FUE CONFIRMADA → ÉXITO INMEDIATO.-
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
    except Exception:
        logger.error("❌ ERROR: Timestamp de Expiración Inválido en la Hoja ...")
        return False

    if ts_expira < ahora_confirmación:
        logger.warning(f"Reserva {reservation_id} Yá Expiró...")

        # Revalidar antes de actualizar ( evitar pisar cambios ).-
        try:
            data_actualizada = read_sheet()
            fila_actual = data_actualizada[i - 2]

            if len(fila_actual) >= 7 and fila_actual[6] != 'Pendiente':
                logger.warning(f"⚠️ Fila {i} Cambió Durante Ejecución — Sé Omite Expiración...")
                return False
        except Exception as e:
            logger.error(f"ERROR Revalidando Fila {i}: {e}")
            return False

        row[6] = 'Expirada'
        row[7] = 'FALSE'
        update_row(i, row)
        return False

    # ---------------------------------------------------------------
    # 5) CONTROL DE DISPONIBILIDAD.-
    # ---------------------------------------------------------------
    coiffeur_actual = row[3]
    fecha_turno = row[4]
    hora_turno = row[5]

    from sheets.sheet_service import check_availability

    disponible = check_availability(coiffeur_actual, fecha_turno, hora_turno)

    if not disponible:
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

    # ------------------------------------------------
    # 6) REVALIDACIÓN FINAL ANTES DE CONFIRMAR (CRÍTICO).-
    # ------------------------------------------------
    try:
        data_actualizada = read_sheet()
        fila_actual = data_actualizada[i - 2]

        if len(fila_actual) >= 7:
            estado_actual_final = fila_actual[6]
            activo_final = (fila_actual[7] or '').upper()

            if estado_actual_final != 'Pendiente' or activo_final != 'TRUE':
                logger.warning(
                    f"⚠️ Fila {i} Cambió Antes Dé Confirmar ( Estado={estado_actual_final} ) — Sé Aborta..."
                )
                return False

    except Exception as e:
        logger.error(f"ERROR en ReValidación Final Fila {i}: {e}")
        return False

    # # ----------------------
    # # 7) CONFIRMAR RESERVA.-
    # # ----------------------
    logger.info(f"✅ Confirmando Reserva {reservation_id}...")

    row[6] = 'Confirmado'
    row[7] = 'FALSE'

    momento_confirmación = ahora_confirmación
    dia_ing = momento_confirmación.strftime('%A')
    mes_ing = momento_confirmación.strftime('%B')

    dia_esp = DIAS[dia_ing]
    mes_esp = MESES[mes_ing]

    row[10] = (
        f"{dia_esp}, {momento_confirmación.day} de {mes_esp} de "
        f"{momento_confirmación.year} {momento_confirmación.strftime('%H:%M:%S')}"
    )

    update_row(i, row)
    logger.info(f"✔ Reserva Actualizada en Google Sheets ( Fila {i} ) ...")

    # ------------------------------------------------
    # Ordenar Hoja.-
    # ------------------------------------------------
    try:
        logger.info(f"📊 Ordenando Hoja Principal...")
        ordenar_hoja()
        logger.info(f"✔ Hoja Ordenada Exitosamente...")
    except Exception as e:
        logger.error(f"❌ ERROR al Ordenar Hoja: {e} ...")
    #
    # # ------------------------------------------------
    # # Reconstruir Calendario COMPLETO.-
    # # ------------------------------------------------
    # try:
    #     logger.info(f"📅 Reconstruyendo Calendario Visual Completo...")
    #     reconstruir_calendario_completo()
    #     logger.info(f"✔ Calendario Visual Reconstruido Exitosamente...")
    # except Exception as e:
    #     logger.error(f"❌ ERROR Reconstruyendo Calendario: {e} ...")
    #
    # return True

    # ------------------------------------------------
    # ACTUALIZAR SOLO EL DÍA DEL TURNO CONFIRMADO.-
    # ------------------------------------------------
    try:
        logger.info(f"📅 Actualizando Calendario SOLO del Día...")

        # ⚠️ Usar FechaISO ( Columna N )
        fecha_iso = row[13] if len(row) > 13 else row[4]

        actualizar_calendario_dia(fecha_iso)

        logger.info(f"✔ Calendario del Día Actualizado Exitosamente...")

    except Exception as e:
        logger.error(f"❌ ERROR Actualizando Calendario Día: {e} ...")

    return True


# Busca y Marca como Expiradas Las Reservas que Superaron el Tiempo Límite.-
def liberar_reservas_expiradas():
    """
    Busca y Marca como Expiradas las Reservas que Superaron el Tiempo Límite.
    Ejecutado periódicamente por el scheduler.
    """
    logger.info(">>> 🔄 Ejecutando: 'liberar_reservas_expiradas()'...")

    # Importaciones Locales para evitar circularidad y asegurar acceso a servicios.-
    from sheets.sheet_service import read_sheet, update_row, _invalidar_servicio_hilo
    from bot.whatsapp_service import send_message
    from bot.app import conversations

    # El timeout ya está configurado en el cliente httplib2 dentro de sheet_service.
    # NO usar socket.setdefaulttimeout() aquí: no es thread-safe con APScheduler.
    try:
        data = read_sheet()

    except HttpError as e:
        logger.error(f"ERROR Leyendo Sheet en: 'liberar_reservas_expiradas': {e}")
        return

    except Exception as e:
        logger.error(f"ERROR / TIMEOUT al Leer Sheet: {type(e).__name__}: {e}")
        _invalidar_servicio_hilo()
        return

    # Usamos el Motor de Tiempo de MEMORY Ingeniería en Sistemas.-
    now = obtener_ahora()

    for i, row in enumerate(data, start=2):
        try:
            if len(row) >= 13 and row[6] == 'Pendiente' and (row[7] or '').upper() == 'TRUE':

                timestamp_str = (row[12] or '').strip()

                # Evitar filas corruptas o incompletas.-
                if not timestamp_str:
                    logger.warning(f"⚠️ Fila {i} Sín TimeStamp Válido — Sé Omite...")
                    continue

                logger.debug(
                    f"(DEBUG) Procesando Fila {i}: Estado={row[6]}, Activo={row[7]}, Timestamp={timestamp_str}")

                try:
                    # Parsear timestamp de la hoja.-
                    ts = datetime.fromisoformat(timestamp_str)
                    if ts.tzinfo is None:
                        ts = tz.localize(ts)

                    # ✅ CAMBIO: Calculamos el punto exacto de expiración usando la variable global
                    limite_expiracion = ts + timedelta(seconds=RESERVA_SECONDS)

                    # ✅ COMPARACIÓN: Si el límite ya pasó respecto a 'now'
                    if limite_expiracion < now:
                        logger.info(f"⚠️ Marcando Reserva {row[11]} como EXPIRADA (Superó los {RESERVA_SECONDS}s)...")

                        # -------------------------------------------------------
                        # REVALIDACIÓN ANTES DE ACTUALIZAR (CRÍTICO).-
                        # -------------------------------------------------------
                        try:
                            data_actualizada = read_sheet()
                            fila_actual = data_actualizada[i - 2]

                            if len(fila_actual) >= 7:
                                estado_actual = fila_actual[6]
                                activo_actual = (fila_actual[7] or '').upper()

                                if estado_actual != 'Pendiente' or activo_actual != 'TRUE':
                                    logger.warning(
                                        f"⚠️ Fila {i} Cambió Durante Ejecución "
                                        f"(Estado={estado_actual}) — Sé Omite Expiración..."
                                    )
                                    continue

                        except Exception as e:
                            logger.error(f"ERROR Revalidando Fila {i}: {e}")
                            continue

                        # Datos del cliente para notificación.-
                        telefono_cliente = row[0]
                        id_reserva = row[11]

                        # Marcar como Expirada.-
                        row[6] = 'Expirada'  # Cambiar Estado
                        row[7] = 'FALSE'  # Desactivar

                        # Asegurarse de que la Fila tenga Todas las Columnas.-
                        while len(row) < 13:
                            row.append('')

                        update_row(i, row)
                        logger.info(f"✅ Reserva {id_reserva} Expirada Automáticamente (Fila {i})")

                        # ✅ NOTIFICACIÓN ACTIVA AL CLIENTE ( MEMORY Ingeniería en Sistemas ).-
                        try:
                            # 1. Resetear el estado de la conversación para que el bot no quede trabado.-
                            if telefono_cliente in conversations:
                                conversations[telefono_cliente] = {'step': 0}

                            # 2. Enviar mensaje de aviso de tiempo agotado.-
                            mensaje_aviso = (
                                "⏰ *TIEMPO AGOTADO*: Tú Reserva Provisional há Expirado por Falta dé Confirmación.\n\n"
                                "El Turno Vuelve a éstar Disponible. Sí Todavía Ló Querés, Escribí *'Turno'* Nuevamente para Empezar, Gracias.-"
                            )
                            send_message(telefono_cliente, mensaje_aviso)
                            logger.info(f"📲 Notificación de Expiración Enviada a: {telefono_cliente}")

                        except Exception as e_msg:
                            logger.error(f"ERROR: Enviándo Notificación dé Expiración al Teléfono: {e_msg}")

                    else:
                        tiempo_restante = (ts - now).total_seconds()
                        logger.debug(f"( DEBUG ) Reserva {row[11]} aún Válida - Expira en {tiempo_restante:.0f}s")

                except ValueError as ve:
                    logger.error(f"ERROR: Parseando TimeStamp en Fila {i}: {timestamp_str} - {ve}")
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
    """Inicializa y Configura el Scheduler de Tareas en Segundo Plano."""

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
    _SCHEDULER = BackgroundScheduler(timezone=tz)

    # Agregar Job Sí Nó Existe.-
    if not _SCHEDULER.get_job(_JOB_ID):
        _SCHEDULER.add_job(
            liberar_reservas_expiradas, 'interval',
            seconds=interval_seconds,
            id=_JOB_ID,
            max_instances=1,          # ← Evita ejecuciones paralelas.-
            coalesce=True,            # ← Unifica ejecuciones atrasadas.-
            misfire_grace_time=30     # ← Tolerancia a retrasos ( segundos ).-
        )

        logger.info(f"(scheduler) Job '{_JOB_ID}' Agregado al Scheduler")

        # -------------------------------------------------------------------------------------
        # Nuevo Job: Actualiza Colores de Feriados Cada 15 Minutos ( Sólo Formato Visual ).-
        # -------------------------------------------------------------------------------------
        try:
            from sheets.sheet_service import colorear_feriados

            # AGREGAR: Wrapper para que Errores SSL Nó Crasheen el Job.-
            def colorear_feriados_safe():
                """Wrapper Seguro — Errores Transitorios Nó Detienen el Scheduler.-"""
                try:
                    colorear_feriados()
                except Exception as e:
                    logger.error(
                        f"(scheduler) ERROR Transitorio en colorear_feriados "
                        f"( Reintento en Próximo Ciclo ): {type(e).__name__}: {e}"
                    )

            _SCHEDULER.add_job(
                colorear_feriados_safe, 'interval',   # ← Usar wrapper.-
                minutes=15,
                id='colorear_feriados',
                max_instances=1,          # ← Evita Ejecuciones Paralelas.-
                coalesce=True,            # ← Unifica Ejecuciones Atrasadas.-
                misfire_grace_time=60     # ← Mayor Tolerancia ( Tarea Menos Crítica ).-
            )

            logger.info(f"(scheduler) Job 'colorear_feriados' Agregado ( Cada 15 Minutos )...")

        except Exception as e:
            logger.error(f"(scheduler) ERROR: al Agregar Job colorear_feriados: {e}")

    # --- Iniciar el Objeto ---
    _SCHEDULER.start()

    # ✅ LOG DE PRECISIÓN (Movido aquí para evitar el AttributeError)
    try:
        job = _SCHEDULER.get_job(_JOB_ID)
        if job:
            proxima_ejecucion = job.next_run_time
            logger.info(f"(scheduler) ✅ Reloj Sincronizado. Próximo Proceso de Reservas a Las: {proxima_ejecucion}")
    except Exception as e:
        logger.warning(f"(scheduler) Nó sé pudo obtener la próxima ejecución para el log: {e}")

    return _SCHEDULER


