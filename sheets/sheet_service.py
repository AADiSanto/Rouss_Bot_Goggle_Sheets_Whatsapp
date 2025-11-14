# -*- coding: utf-8 -*-
# *********************************************************************************************************************
#  Created By: Ing. Antonio Alberto Di Santo.-
#  Created On: Lunes 06 de Octubre del 2025.-
#
#     Program       :   Bot de WhatsApp con Google Sheets,
#                          para Asignación de Turnos en Rouss Coiffeur's de MEMORY   Ingeniería en Sistemas.-
#
#    "Module Purpose:   Proporciona la integración completa con Google Sheets, permitiendo leer, escribir y actualizar
#                       datos de turnos, feriados y calendarios visuales, además de aplicar formato automático a las hojas."

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
Servicio de Integración con Google Sheets.-
Gestiona Lectura, Escritura y Actualización de Turnos.-
"""

import logging

logger = logging.getLogger(__name__)
import os
from pathlib import Path

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2 import service_account
from datetime import datetime
import pytz

# Construye la Ruta al Archivo credentials.json Relativo a éste Archivo ( sheets/ ).-
HERE = Path(__file__).resolve().parent
SERVICE_ACCOUNT_FILE = HERE / 'credentials.json'

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# SPREADSHEET_ID se Obtendrá Dinámicamente según el Año del Turno.-
# Base ID desde .env (opcional, para Compatibilidad).-
BASE_SPREADSHEET_ID = os.getenv('SPREADSHEET_ID_2025', '1zEUerYZ20wk1fgh1s1kse_eDb4SRxptFPgesAHKrPDw')
SPREADSHEET_ID = BASE_SPREADSHEET_ID  # Se Actualizará Dinámicamente.-

# Mapeo Manual de IDs por Año (Mientras Nó Implementemos Búsqueda en Google Drive).-
SPREADSHEET_IDS_BY_YEAR = {
    2025: os.getenv('SPREADSHEET_ID_2025', '1zEUerYZ20wk1fgh1s1kse_eDb4SRxptFPgesAHKrPDw'),
    # 2026: 'ID_cuando_lo_crees', Se debe Copiar la Hoja de una Existente,
    #                                Cambiar el Nombre y Asignar Permisos de Editor al EMaiL en
    #                                'credentials.json'
    # '"client_email": "rouss-whatsapp-bot-turnos-serv@rouss-whatsapp-bot-turnos.iam.gserviceaccount.com"'.-
}


# Función para Guardar Nuevos IDs (persistencia simple en archivo).-
def save_spreadsheet_id_for_year(year, spreadsheet_id):
    """Guarda el ID de una Nueva Hoja para Referencia Futura"""
    SPREADSHEET_IDS_BY_YEAR[year] = spreadsheet_id

    # Opcional: Guardar en Archivo para Persistencia entre Reinicios.-
    try:
        config_file = HERE / 'spreadsheet_ids.json'
        import json

        # Leer IDs existentes.-
        if config_file.exists():
            with open(config_file, 'r') as f:
                ids = json.load(f)
        else:
            ids = {}

        # Agregar Nuevo ID.-
        ids[str(year)] = spreadsheet_id

        # Guardar.-
        with open(config_file, 'w') as f:
            json.dump(ids, f, indent=2)

        logger.info(f"💾 ID Guardado para Año: {year}: {spreadsheet_id}")
    except Exception as e:
        logger.error(f"ERROR: Guardando ID: {e}")


# Nombre de la Pestaña Principal.-
SHEET_NAME = 'Rouss_Turnos_Coiffeur'

TIMEZONE = 'America/Argentina/Buenos_Aires'

# Verificación: Archivo de Credenciales Presente.-
if not SERVICE_ACCOUNT_FILE.exists():
    raise FileNotFoundError(f"ERROR: El Archivo de Credenciales Nó Fué Encontrado: {SERVICE_ACCOUNT_FILE}")

# Inicializar Cliente de Google Sheets.-
creds = service_account.Credentials.from_service_account_file(
    str(SERVICE_ACCOUNT_FILE), scopes=SCOPES)
service = build('sheets', 'v4', credentials=creds)
sheets = service.spreadsheets()

tz = pytz.timezone(TIMEZONE)

# Generar el Nombre de la Hoja de Cálculo para un Año Específico.-
def get_spreadsheet_name_for_year(year):
    """Genera el Nombre de la Hoja de Cálculo para un Año Específico"""
    return f"{year}_Rouss_Turnos_Coiffeur"


#Obtiene el Año Actual en la Zona Horaria Configurada.-
def get_current_year():
    """Obtiene el Año Actual en la Zona Horaria Configurada"""
    return datetime.now(tz).year


# Obtiene el ID de la Hoja de Cálculo para un Año Específico.-
def get_or_create_spreadsheet_for_year(year):
    """
    Obtiene el ID de la Hoja de Cálculo para un Año Específico.-
    Si NO Existe, la Crea con las Pestañas Necesarias.-

    Returns:
        str: ID de la Hoja de Cálculo
    """
    # Cargar IDs Guardados al Inicio.-
    try:
        config_file = HERE / 'spreadsheet_ids.json'
        if config_file.exists():
            import json
            with open(config_file, 'r') as f:
                saved_ids = json.load(f)
                # Filtrar Sólo las Claves Numéricas ( Años Válidos ).-
                valid_ids = {int(k): v for k, v in saved_ids.items() if k.isdigit()}
                SPREADSHEET_IDS_BY_YEAR.update(valid_ids)

                if year in SPREADSHEET_IDS_BY_YEAR:
                    return SPREADSHEET_IDS_BY_YEAR[year]

    except Exception as e:
        logger.warning(f"Nó Sé Pudieron Cargar ID's Guardados: {e}")


    # Si Ya Tenemos el ID, Devolverlo.-
    if year in SPREADSHEET_IDS_BY_YEAR:
        logger.info(f"📊 Usando Hoja Existente para el Año {year}: {SPREADSHEET_IDS_BY_YEAR[year]}")
        return SPREADSHEET_IDS_BY_YEAR[year]

    # Si NÓ Existe, Crear Nueva Hoja.-
    spreadsheet_name = get_spreadsheet_name_for_year(year)

    try:
        # Intentar Crear Nueva Hoja.-
        spreadsheet = {
            'properties': {
                'title': spreadsheet_name
            },
            'sheets': [
                {'properties': {'title': 'Rouss_Turnos_Coiffeur'}},
                {'properties': {'title': 'Rouss_Turnos_Calendario_Visual'}},
                {'properties': {'title': 'Rouss_Turnos_Feriados'}}
            ]
        }

        result = service.spreadsheets().create(body=spreadsheet).execute()
        new_id = result['spreadsheetId']

        logger.info(f"✅ Nueva Hoja Creada para el Año {year}: {new_id}")

        # Inicializar Encabezados en las Pestañas.-
        inicializar_encabezados(new_id, 'Rouss_Turnos_Coiffeur')
        inicializar_encabezados(new_id, 'Rouss_Turnos_Calendario_Visual', tipo='calendario')
        inicializar_encabezados(new_id, 'Rouss_Turnos_Feriados', tipo='feriados')

        # Guardar el Nuevo ID para Referencia Futura.-
        save_spreadsheet_id_for_year(year, new_id)

        return new_id

    except Exception as e:
        logger.error(f"ERROR al Crear / Obtener Hoja para el Año {year}: {e}")
        # Fallback al ID Base.-
        return BASE_SPREADSHEET_ID


#Inicializa los Encabezados de una Pestaña Nueva.-
def inicializar_encabezados(spreadsheet_id, sheet_name, tipo='turnos'):
    """Inicializa los Encabezados de una Pestaña Nueva"""
    if tipo == 'turnos':
        headers = [['Nombre', 'Telefono', 'Servicio', 'Coiffeur', 'Fecha',
                    'Hora', 'Estado', 'FechaRegistro', 'ReservationID',
                    'TimestampExpiracion', 'Activo']]
    elif tipo == 'calendario':
        headers = [['Fecha', 'Hora', 'Walter', 'María', 'Detalles']]
    elif tipo == 'feriados':
        headers = [['Fecha', 'Motivo', 'Tipo', 'Activo']]
    else:
        return

    try:
        full_range = f"'{sheet_name}'!A1:K1"
        body = {'values': headers}
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=full_range,
            valueInputOption='USER_ENTERED',
            body=body
        ).execute()
        logger.info(f"✅ Encabezados Inicializados en: '{sheet_name}'")
    except Exception as e:
        logger.error(f"ERROR Inicializando Encabezados en: '{sheet_name}': {e}")


# Configura la Hoja de Cálculo Activa según el Año.-
def set_active_spreadsheet(year=None):
    """
    Configura la Hoja de Cálculo Activa según el Año.-
    Si NO se Proporciona Año, Usa el Actual.-
    """
    global SPREADSHEET_ID

    if year is None:
        year = get_current_year()

    SPREADSHEET_ID = get_or_create_spreadsheet_for_year(year)
    logger.info(f"📊 Hoja Activa Cambiada al Año: {year}: {SPREADSHEET_ID}")
    return SPREADSHEET_ID


# Normalizar Nombre de Hoja.-
SHEET_NAME = (SHEET_NAME or '').strip()


# --- Verificación de la Existencia de la Hoja en el Spreadsheet.-
def _get_sheet_titles(spreadsheet_id):
    """Devuelve la Lista de Títulos ( tabs ) del Spreadsheet."""
    try:
        meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id,
                                         includeGridData=False).execute()
    except HttpError as e:
        raise RuntimeError(f"ERROR: Nó Fué Posible Obtener Metadatos del Spreadsheet: {e}") from e

    sheets_meta = meta.get('sheets', []) or []
    titles = [s.get('properties', {}).get('title', '') for s in sheets_meta]
    return titles

# Comprobar que la Hoja Existe ( Ejecutar Después de Inicializar `service` ).-
try:
    titles = _get_sheet_titles(SPREADSHEET_ID)
except Exception as e:
    # Si Nó Podemos Obtener Títulos por un Fallo en la API, Marcamos como Nó Disponible.-
    print("ERROR: La Hoja de Cálculo Nó está Disponible, Reintente Nuevamente, Gracias.-")
    print(f"(DEBUG) ERROR: Al Obtener Pestañas: {repr(e)}")
    DATA_AVAILABLE = False
else:
    if SHEET_NAME not in titles:
        # Mensaje Amigable Solicitado por el Cliente.-
        print("ERROR: La Hoja de Cálculo Nó está Disponible, Reintente Nuevamente, Gracias.-")
        # Log adicional opcional para debugging:
        print(f"(DEBUG) Pestañas Disponibles: {titles}")
        DATA_AVAILABLE = False
    else:
        # Opcional: Confirmar en Log que la Hoja fué Encontrada.-
        print(f"(DEBUG) Hoja Encontrada: '{SHEET_NAME}' en Spreadsheet {SPREADSHEET_ID}")
        DATA_AVAILABLE = True


# --- Helper para Construir Rangos Seguros ---
def _safe_range(sheet_name, a1_range):
    # Envuelve el Nombre con Comillas Simples para Evitar Errores sí Tiene Espacios / Símbolos.-
    return f"'{sheet_name}'!{a1_range}"


#Agrega una Fila al Final de la Hoja.-
def append_row(values):
    """Agrega una Fila al Final de la Hoja"""
    if not DATA_AVAILABLE:
        print("La Hoja de Cálculo Nó Está Disponible, Reintente Nuevamente, Gracias.-")
        return None

    body = {'values': [values]}
    full_range = _safe_range(SHEET_NAME, 'A:K')
    try:
        sheets.values().append(
            spreadsheetId=SPREADSHEET_ID,
            range=full_range,
            valueInputOption='USER_ENTERED',
            insertDataOption='INSERT_ROWS',
            body=body
        ).execute()
    except HttpError as e:
        print("ERROR: al append_row. Spreadsheet ID:", SPREADSHEET_ID)
        print("Rango Pedido:", full_range)
        print("HttpError:", e)
        raise


#Lee Datos de la Hoja.-
def read_sheet(range_a1=None):
    """Lee Datos de la Hoja"""
    if not DATA_AVAILABLE:
        print("La Hoja de Cálculo Nó Está Disponible, Reintente Nuevamente, Gracias.-")
        return []  # Lectura Nó Destructiva: Devolvemos Lista Vacía.-

    if not range_a1:
        range_a1 = 'A2:K1000'
    full_range = _safe_range(SHEET_NAME, range_a1)
    try:
        result = sheets.values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=full_range
        ).execute()
    except HttpError as e:
        print("ERROR al read_sheet. Spreadsheet ID:", SPREADSHEET_ID)
        print("Rango Pedido:", full_range)
        print("HttpError:", e)
        raise
    return result.get('values', [])

# *********************************************************************************************************************
#  Función: es_feriado(fecha)
#  Autor  : Ing. Antonio Alberto Di Santo
#  Fecha  : Martes 11 de Noviembre de 2025
#
#  Descripción:
#     Verifica si una Fecha corresponde a un Día Nó Laborable o Feriado, según la Pestaña:
#        "Rouss_Turnos_Feriados"
#
#     • Acepta fechas en formato Texto (YYYY-MM-DD o DD/MM/YYYY).
#     • Interpreta una Segunda Columna opcional:
#           TRUE  → Feriado Activo.
#           FALSE → Feriado Desactivado (Ignorado).
#     • Retorna True sí la Fecha está marcada como Feriado Activo.
#
# *********************************************************************************************************************

#Verifica si la Fecha Indicada está Marcada como Feriado Activo en la Hoja: 'Rouss_Turnos_Feriados'.-
def es_feriado(fecha):
    """
    Verifica si la Fecha Indicada está Marcada como Feriado Activo en la Hoja: 'Rouss_Turnos_Feriados'.-
    • Solo considera filas donde la columna 'Activo' (D) NO sea FALSE / NO / 0.
    """
    FERIADOS_SHEET = 'Rouss_Turnos_Feriados'
    try:
        full_range = _safe_range(FERIADOS_SHEET, 'A2:D100')
        result = sheets.values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=full_range
        ).execute()
        rows = result.get('values', []) or []
    except HttpError as e:
        logger.error(f"ERROR al Leer Pestaña de Feriados: {e}")
        return False

    # Normalizar la Fecha de Entrada (por Seguridad).-
    fecha = str(fecha).strip()

    feriados_activos = []
    for row in rows:
        if not row or len(row) < 1:
            continue

        fecha_feriado = str(row[0]).strip()
        valor_activo = str(row[3]).strip().upper() if len(row) >= 4 else ""

        # Solo agregar si está activo (TRUE o vacío)
        if valor_activo not in ['FALSE', 'NO', '0']:
            feriados_activos.append(fecha_feriado)

    logger.info(f"(DEBUG) Feriados Activos Detectados: {feriados_activos}")
    return fecha in feriados_activos


#Actualiza una Fila Específica (row_index Empieza en 2).-
def update_row(row_index, values):
    """Actualiza una Fila Específica ( row_index Empieza en 2 )"""
    if not DATA_AVAILABLE:
        print("La Hoja de Cálculo Nó Está Disponible, Reintente Nuevamente, Gracias.-")
        return None

    body = {'values': [values]}
    full_range = _safe_range(SHEET_NAME, f'A{row_index}:K{row_index}')
    try:
        sheets.values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=full_range,
            valueInputOption='USER_ENTERED',
            body=body
        ).execute()
    except HttpError as e:
        print("ERROR al Update_row. Spreadsheet ID:", SPREADSHEET_ID)
        print("Rango Pedido:", full_range)
        print("HttpError:", e)
        raise


#Obtiene Horarios Disponibles para un Coiffeur en una Fecha Específica.-
def get_available_slots(coiffeur, fecha):
    """
    Obtiene Horarios Disponibles para un Coiffeur en una Fecha Específica.-

    Args:
        Coiffeur: 'Walter' o 'María'
        fecha: string en formato 'YYYY-MM-DD'

    Returns:
        Lista de Horarios Disponibles [ '10:00', '11:30', ... ]
    """

    # Extraer Año de la Fecha y Configurar Hoja Activa.-
    try:
        year = int(fecha.split('-')[0])
        set_active_spreadsheet(year)
    except Exception as e:
        logger.warning(f"Nó Sé Pudo Cambiar hoja para Año en Fecha: {fecha}: {e}")

    # Horarios Posibles del Salón ( Cada 30 Minutos ).-
    all_slots = [
        '09:00', '09:30', '10:00', '10:30', '11:00', '11:30',
        '12:00', '12:30', '13:00', '14:00', '14:30', '15:00',
        '15:30', '16:00', '16:30', '17:00', '17:30', '18:00', '18:30'
    ]

    # Obtener Turnos Ocupados.-
    data = read_sheet()
    occupied_slots = set()

    for row in data:
        if len(row) >= 7:
            # Verificar si el Turno es del Mismo Coiffeur, Fecha y está Confirmado o Pendiente.-
            if (row[3] == coiffeur and
                    row[4] == fecha and
                    row[6] in ['Confirmado', 'Pendiente']):
                occupied_slots.add(row[5])

    # Retornar Horarios Disponibles.-
    available = [slot for slot in all_slots if slot not in occupied_slots]
    return available


#Verifica si un Horario Específico está Disponible.-
def check_availability(coiffeur, fecha, hora):
    """
    Verifica si un Horario Específico está Disponible.-

    Returns:
        bool: True si está Disponible, False si Está Ocupado.-
    """

    # Extraer Año de la Fecha y Configurar Hoja Activa.-
    try:
        year = int(fecha.split('-')[0])
        set_active_spreadsheet(year)
    except Exception as e:
        logger.warning(f"Nó Sé Pudo Cambiar Hoja para Año en Fecha: {fecha}: {e}")

    data = read_sheet()

    for row in data:
        if len(row) >= 7:
            if (row[3] == coiffeur and
                    row[4] == fecha and
                    row[5] == hora and
                    row[6] in ['Confirmado', 'Pendiente']):
                return False

    return True


#Elige el Coiffeur Según Preferencia y Disponibilidad.-
def elegir_coiffeur(preferencia, fecha, hora):
    """
    Elige el Coiffeur Según Preferencia y Disponibilidad.-

    Args:
        preferencia: 'walter', 'maría', 'maria' o None
        fecha: fecha en formato 'YYYY-MM-DD'
        hora: hora en formato 'HH:MM'

    Returns:
        str: Nombre del Coiffeur ( 'Walter' o 'María' ) o None Sí Ninguno Disponible.-
    """
    # Normalizar Nombres.-
    if preferencia:
        preferencia = preferencia.lower()
        if preferencia in ['walter']:
            return 'Walter' if check_availability('Walter', fecha, hora) else None
        elif preferencia in ['maría', 'maria']:
            return 'María' if check_availability('María', fecha, hora) else None

    # Sin Preferencia: Aplicar round-robin o Menor Carga.-
    walter_available = check_availability('Walter', fecha, hora)
    maria_available = check_availability('María', fecha, hora)

    if walter_available and maria_available:
        # Aplicar Estrategia de Menor Carga.-
        data = read_sheet()
        walter_count = sum(1 for row in data if len(row) >= 7 and
                           row[3] == 'Walter' and row[4] == fecha and
                           row[6] == 'Confirmado')
        maria_count = sum(1 for row in data if len(row) >= 7 and
                          row[3] == 'María' and row[4] == fecha and
                          row[6] == 'Confirmado')

        return 'Walter' if walter_count <= maria_count else 'María'
    elif walter_available:
        return 'Walter'
    elif maria_available:
        return 'María'
    else:
        return None


#Genera o Actualiza el Calendario Visual Completo para una Fecha Específica.-
def actualizar_calendario_dia(fecha):
    """
    Genera o Actualiza el Calendario Visual Completo para una Fecha Específica.-
    Muestra TODOS los Horarios del Día (09:00 a 18:30) con Estado Libre/Ocupado.-

    Args:
        fecha: Fecha en formato 'YYYY-MM-DD'
    """

    # Extraer Año de la Fecha y Configurar Hoja Activa.-
    try:
        year = int(fecha.split('-')[0])
        set_active_spreadsheet(year)
    except Exception as e:
        logger.warning(f"Nó Sé Pudo Cambiar Hoja para Año en Fecha: {fecha}: {e}")

    CALENDARIO_SHEET = 'Rouss_Turnos_Calendario_Visual'

    # Horarios del Salón (cada 30 minutos).-
    horarios = [
        '09:00', '09:30', '10:00', '10:30', '11:00', '11:30',
        '12:00', '12:30', '13:00', '14:00', '14:30', '15:00',
        '15:30', '16:00', '16:30', '17:00', '17:30', '18:00', '18:30'
    ]

    try:
        # Leer Turnos Confirmados con Reintentos.-
        max_intentos = 3
        for intento in range(max_intentos):
            try:
                data = read_sheet()
                break
            except Exception as e:
                if intento < max_intentos - 1:
                    logger.warning(f"Intento {intento + 1}/{max_intentos} fallido al leer sheet: {e}")
                    import time
                    time.sleep(2)  # Esperar 2 segundos antes de reintentar
                else:
                    raise

        # Crear Diccionario: {hora: {walter: nombre, maria: nombre}}.-
        turnos_del_dia = {}
        for row in data:
            if len(row) >= 7 and row[4] == fecha and row[6] == 'Confirmado':
                hora = row[5]
                coiffeur = row[3]
                nombre = row[0]
                servicio = row[2]

                if hora not in turnos_del_dia:
                    turnos_del_dia[hora] = {'Walter': 'Libre', 'María': 'Libre', 'detalles': ''}

                turnos_del_dia[hora][coiffeur] = nombre

                # Agregar a Detalles.-
                if turnos_del_dia[hora]['detalles']:
                    turnos_del_dia[hora]['detalles'] += f" | {nombre} - {servicio}"
                else:
                    turnos_del_dia[hora]['detalles'] = f"{nombre} - {servicio}"

        # Generar Filas del Calendario.-
        filas_calendario = []
        for hora in horarios:
            if hora in turnos_del_dia:
                fila = [
                    fecha,
                    hora,
                    turnos_del_dia[hora]['Walter'],
                    turnos_del_dia[hora]['María'],
                    turnos_del_dia[hora]['detalles']
                ]
            else:
                fila = [fecha, hora, 'Libre', 'Libre', '']

            filas_calendario.append(fila)

            # Líneas de Debug:
            logger.info(f"(DEBUG) Fecha: {fecha}, Turnos Encontrados: {len(turnos_del_dia)}, Filas Calendario: {len(filas_calendario)}")
            logger.info(f"(DEBUG) Primeras 3 filas: {filas_calendario[:3]}")

        # Escribir en el Calendario (Sobrescribir Todo el Bloque de Esta Fecha).-
        # Buscar Primera Fila Disponible o Actualizar si Ya Existe.-
        try:
            full_range = _safe_range(CALENDARIO_SHEET, 'A2:E1000')
            result = sheets.values().get(
                spreadsheetId=SPREADSHEET_ID,
                range=full_range
            ).execute()
            filas_existentes = result.get('values', [])
        except:
            filas_existentes = []

        # Buscar si Ya Existe Esta Fecha.-
        inicio_fecha = None
        for idx, fila in enumerate(filas_existentes):
            if len(fila) >= 1 and fila[0] == fecha:
                inicio_fecha = idx + 2  # +2 Porque Empieza en Fila 2.-
                break

        if inicio_fecha:
            # Actualizar Filas Existentes ( 19 Horarios Exactos ).-
            fin_fecha = inicio_fecha + 18  # Son 19 Horarios (0-18), por eso +18.-
            update_range = _safe_range(CALENDARIO_SHEET, f'A{inicio_fecha}:E{fin_fecha}')
            body = {'values': filas_calendario}
            sheets.values().update(
                spreadsheetId=SPREADSHEET_ID,
                range=update_range,
                valueInputOption='USER_ENTERED',
                body=body
            ).execute()
            logger.info(f"Calendario Actualizado para Fecha: {fecha}")
        else:
            # Insertar Nueva Fecha al Principio (Después de Encabezados).-
            # Primero Leer Todas las Filas Existentes para Nó Borrarlas.-
            todas_las_filas = filas_calendario + [[''] * 5]  # Nueva fecha + Fila en Blanco (Lista Plana)

            # Agregar Fechas Existentes Después.-
            todas_las_filas.extend(filas_existentes)

            # Escribir Todo Junto.-
            total_filas = len(todas_las_filas)
            write_range = _safe_range(CALENDARIO_SHEET, f'A2:E{1 + total_filas}')
            body = {'values': todas_las_filas}
            sheets.values().update(
                spreadsheetId=SPREADSHEET_ID,
                range=write_range,
                valueInputOption='USER_ENTERED',
                body=body
            ).execute()
            logger.info(
                f"Calendario Creado para Nueva Fecha: {fecha} ( Preservando {len(filas_existentes)} Filas Anteriores...)")

            logger.info(f"(DEBUG) Total de Filas Escritas: {total_filas}, Rango: {write_range}")

        # --- Marcar Días Nó Laborables o Feriados en el Calendario ---
        from sheets.sheet_service import es_feriado
        if es_feriado(fecha):
            try:
                # Crear un Bloque completo de 19 horarios Con Texto Fijo de "Día Nó Laborable o Feriado"
                filas_feriado = [
                    [fecha, hora, 'FERIADO', 'FERIADO', 'FERIADO — NO DISPONIBLE']
                    for hora in horarios
                ]

                full_range = _safe_range(CALENDARIO_SHEET, 'A2:E1000')
                result = sheets.values().get(
                    spreadsheetId=SPREADSHEET_ID,
                    range=full_range
                ).execute()
                filas_existentes = result.get('values', [])

                # Buscar si yá Existe esa Fecha.-
                inicio_fecha = None
                for idx, fila in enumerate(filas_existentes):
                    if len(fila) >= 1 and fila[0] == fecha:
                        inicio_fecha = idx + 2
                        break

                if inicio_fecha:
                    fin_fecha = inicio_fecha + 18
                    update_range = _safe_range(CALENDARIO_SHEET, f'A{inicio_fecha}:E{fin_fecha}')
                    body = {'values': filas_feriado}
                    sheets.values().update(
                        spreadsheetId=SPREADSHEET_ID,
                        range=update_range,
                        valueInputOption='USER_ENTERED',
                        body=body
                    ).execute()
                    logger.info(f"Calendario Marcado como Día Nó Laborable o Feriado para la Fecha: {fecha}")

                else:
                    # Insertar al Inicio
                    todas = filas_feriado + [[''] * 5]
                    todas.extend(filas_existentes)
                    total_filas = len(todas)
                    write_range = _safe_range(CALENDARIO_SHEET, f'A2:E{1 + total_filas}')
                    body = {'values': todas}
                    sheets.values().update(
                        spreadsheetId=SPREADSHEET_ID,
                        range=write_range,
                        valueInputOption='USER_ENTERED',
                        body=body
                    ).execute()
                    logger.info(f"Calendario Creado con Días Nó Laborables o Feriados para Nueva Fecha: {fecha}")

                    from sheets.sheet_service import es_feriado
                    logger.info(f"(DEBUG) Resultado de es_feriado({fecha}) = {es_feriado(fecha)}")

            except Exception as e:
                logger.error(f"ERROR: al Marcar Día Nó Laborable o Feriado en Calendario: {e}")

        return True

    except HttpError as e:
        logger.error(f"ERROR: al Actualizar Calendario con Horarios: {e}")
        return False


#Devuelve el SheetId (Numérico) de una Pestaña, Requerido para BatchUpdate.-
def obtener_sheet_id(nombre_hoja):
    """Devuelve el SheetId (numérico) de una Pestaña, Requerido para BatchUpdate..."""
    try:
        spreadsheet = service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()

        for sheet in spreadsheet.get('sheets', []):
            props = sheet.get("properties", {})
            if props.get("title") == nombre_hoja:
                return props.get("sheetId")

    except Exception as e:
        logger.error(f"ERROR al Obtener sheetId Para: '{nombre_hoja}': {e}")

    return None


#Colorea Automáticamente las Filas de la Pestaña 'Rouss_Turnos_Feriados'.-
def colorear_feriados():
    """
    Colorea Automáticamente las Filas de la Pestaña 'Rouss_Turnos_Feriados'.-
    • Feriados Activos (TRUE o vacío): Fondo Rojo Claro y texto Negrita.
    • Feriados Desactivados (FALSE / NO / 0): Fondo Blanco y texto normal.
    """
    FERIADOS_SHEET = 'Rouss_Turnos_Feriados'

    try:
        full_range = _safe_range(FERIADOS_SHEET, 'A2:D100')
        result = sheets.values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=full_range
        ).execute()
        rows = result.get('values', []) or []
    except HttpError as e:
        logger.error(f"ERROR al Leer Pestaña de Feriados (colorear): {e}")
        return

    sheet_id = obtener_sheet_id(FERIADOS_SHEET)
    if sheet_id is None:
        logger.error(f"ERROR: sheet_id no encontrado para '{FERIADOS_SHEET}'")
        return

    requests = []

    for i, row in enumerate(rows):
        # Obtener Valor de Columna 'Activo' (columna D → índice 3)
        valor_activo = ""
        if len(row) >= 4:
            valor_activo = str(row[3]).strip().upper()
        elif len(row) >= 1:
            # Si hay Datos pero Falta la Columna 'Activo', sé Asume Activo (rojo)
            valor_activo = ""
        else:
            # Fila Completamente Vacía
            continue

        # Determinar Estado del Día Nó Laborable o Feriado
        activo = valor_activo not in ['FALSE', 'NO', '0']

        # Definir Formato de Color y Texto
        if activo:
            color = {"red": 1, "green": 0.8, "blue": 0.8}   # Rojo Claro
            text_format = {"bold": True}
        else:
            color = {"red": 1, "green": 1, "blue": 1}       # Blanco
            text_format = {"bold": False}

        if activo:
            logger.info(f"(INFO) Día {row[0] if row else '?'} ACTIVADO — Marcado como Día Nó Laborable o Feriado...")
        else:
            logger.info(f"(INFO) Día {row[0] if row else '?'} DESACTIVADO — Se Quitó Formato de Día Nó Laborable o Feriado...")

        # Aplicar Formato a Columnas A, B, C y D (índices 0–3)
        requests.append({
            "updateCells": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": i + 1,  # +1 Porque Empieza en A2
                    "endRowIndex": i + 2,
                    "startColumnIndex": 0,
                    "endColumnIndex": 4      # Hasta Columna D (nó Inclusivo)
                },
                "rows": [{
                    "values": [
                        {"userEnteredFormat": {"backgroundColor": color, "textFormat": text_format}},
                        {"userEnteredFormat": {"backgroundColor": color, "textFormat": text_format}},
                        {"userEnteredFormat": {"backgroundColor": color, "textFormat": text_format}},
                        {"userEnteredFormat": {"backgroundColor": color, "textFormat": text_format}},
                    ]
                }],
                "fields": "userEnteredFormat(backgroundColor,textFormat)"
            }
        })

    # Ejecutar Actualización Masiva (Sólo si Hay Algo que Aplicar)
    if requests:
        body = {"requests": requests}
        try:
            service.spreadsheets().batchUpdate(
                spreadsheetId=SPREADSHEET_ID,
                body=body
            ).execute()
            logger.info(f"(DEBUG) Coloreado de {len(requests)} Filas en '{FERIADOS_SHEET}' Completado...")
        except HttpError as e:
            logger.error(f"ERROR al Colorear Feriados: {e}")


# --------------------------------------------------------------------------------
# Pequeño "smoke test" Local para Verificar Acceso a la Hoja de Cálculo.-
# Ejecutar Sólo Sí sé Quiere Probar Manualmente: python -m sheets.sheet_service
# --------------------------------------------------------------------------------

#Lee Unas Filas y Muestra Cuántas Devolvió la API (Prueba de Solo Lectura).-
def smoke_test_read():
    """Lee Unas Filas y Muestra Cuántas Devolvió la API (Prueba de Solo Lectura)"""
    try:
        values = read_sheet('A1:K10')  # lectura conservadora
        print("SmokeTest: Lectura OK. Filas Devueltas:", len(values))
        # Opcional: Imprimir lá Primera Fila.-
        if values:
            print("SmokeTest: Primera Fila: ", values[0])
    except Exception as e:
        print("SmokeTest: ERROR en Lectura: ", repr(e))
        raise


#Intenta Agregar una Fila de Prueba Identificable al Final de la Hoja
def smoke_test_append():
    """Intenta Agregar una Fila de Prueba Identificable al Final de la Hoja"""
    ts = datetime.now(tz).astimezone(tz).isoformat()
    test_row = ['__SMOKE_TEST__', ts]
    try:
        append_row(test_row)
        print("SmokeTest: Append OK. Fila Añadida: ", test_row)
    except Exception as e:
        print("SmokeTest: ERROR en Append: ", repr(e))
        raise


#Ejecuta los Tests de Lectura y Append (Append es Opcional).-
def smoke_test():
    """Ejecuta los Tests de Lectura y Append ( Append es Opcional )"""
    print("=== Iniciando Smoke Test de Google Sheets ===")
    print("Spreadsheet ID:", SPREADSHEET_ID)
    print("Sheet Name ( Normalizado ): ", SHEET_NAME)
    try:
        # Verificar Títulos para Confirmar la Existencia de la Hoja de Cálculo.-
        titles = _get_sheet_titles(SPREADSHEET_ID)
        print("Pestañas Disponibles:", titles)
    except Exception as e:
        print("Nó Sé Pudieron Obtener Pestañas: ", repr(e))
        return

    # Lectura ( Non-Destructive ).-
    smoke_test_read()

    # Append de Prueba: Comentarlo Sí Nó Sé Quiere Escribir en la Hoja.-
    smoke_test_append()
    print("=== Smoke Test Completado ===")


if __name__ == "__main__":
    # Se Ejecuta Sólo Sí Sé Corre El Archivo Directamente:
    # Desde La Raíz Del Proyecto: python -m sheets.sheet_service
    smoke_test()


