# *********************************************************************************************************************
#  Created By: Ing. Antonio Alberto Di Santo.-
#  Created On: Lunes 06 de Octubre del 2025.-
#
#     Program: Bot de WhatsApp con Google Sheets,
#                 para Asignación de Turnos en Rouss Coiffeur's de MEMORY   Ingeniería en Sistemas.-
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
SPREADSHEET_ID = os.getenv('SPREADSHEET_ID', '1zEUerYZ20wk1fgh1s1kse_eDb4SRxptFPgesAHKrPDw')
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
    print("ERROR: La Base De Datos Nó está Disponible, Reintente Nuevamente, Gracias.-")
    print(f"(DEBUG) ERROR: Al Obtener Pestañas: {repr(e)}")
    DATA_AVAILABLE = False
else:
    if SHEET_NAME not in titles:
        # Mensaje Amigable Solicitado por el Cliente.-
        print("ERROR: La Base De Datos Nó está Disponible, Reintente Nuevamente, Gracias.-")
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


def append_row(values):
    """Agrega una Fila al Final de la Hoja"""
    if not DATA_AVAILABLE:
        print("La Base De Datos Nó Está Disponible, Reintente Nuevamente, Gracias.-")
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


def read_sheet(range_a1=None):
    """Lee Datos de la Hoja"""
    if not DATA_AVAILABLE:
        print("La Base De Datos Nó Está Disponible, Reintente Nuevamente, Gracias.-")
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


def update_row(row_index, values):
    """Actualiza una Fila Específica ( row_index Empieza en 2 )"""
    if not DATA_AVAILABLE:
        print("La Base De Datos Nó Está Disponible, Reintente Nuevamente, Gracias.-")
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


def get_available_slots(coiffeur, fecha):
    """
    Obtiene Horarios Disponibles para un Coiffeur en una Fecha Específica.-

    Args:
        coiffeur: 'Walter' o 'María'
        fecha: string en formato 'YYYY-MM-DD'

    Returns:
        Lista de Horarios Disponibles [ '10:00', '11:30', ... ]
    """
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


def check_availability(coiffeur, fecha, hora):
    """
    Verifica si un Horario Específico está Disponible.-

    Returns:
        bool: True si está Disponible, False si Está Ocupado.-
    """
    data = read_sheet()

    for row in data:
        if len(row) >= 7:
            if (row[3] == coiffeur and
                    row[4] == fecha and
                    row[5] == hora and
                    row[6] in ['Confirmado', 'Pendiente']):
                return False

    return True


def elegir_coiffeur(preferencia, fecha, hora):
    """
    Elige el oiffeur Según Preferencia y Disponibilidad.-

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

# ------------------------------------------------------------------
# Pequeño "smoke test" Local para Verificar Acceso a la Hoja de Cálculo.-
# Ejecutar Sólo Sí sé Quiere Probar Manualmente: python -m sheets.sheet_service
# ------------------------------------------------------------------
def smoke_test_read():
    """Lee Unas Filas y Muestra Cuántas Devolvió la API ( Prueba de Sólo Lectura )"""
    try:
        values = read_sheet('A1:K10')  # lectura conservadora
        print("SmokeTest: Lectura OK. Filas Devueltas:", len(values))
        # Opcional: Imprimir lá Primera Fila.-
        if values:
            print("SmokeTest: Primera Fila: ", values[0])
    except Exception as e:
        print("SmokeTest: ERROR en Lectura: ", repr(e))
        raise


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


