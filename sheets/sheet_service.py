"""
Servicio de integración con Google Sheets
Gestiona lectura, escritura y actualización de turnos
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

# Construye la ruta al archivo credentials.json relativo a este archivo (sheets/)
HERE = Path(__file__).resolve().parent
SERVICE_ACCOUNT_FILE = HERE / 'credentials.json'

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SPREADSHEET_ID = os.getenv('SPREADSHEET_ID', '1zEUerYZ20wk1fgh1s1kse_eDb4SRxptFPgesAHKrPDw')
SHEET_NAME = 'Rouss_Turnos_Coiffeur'
TIMEZONE = 'America/Argentina/Buenos_Aires'

# Verificación: archivo de credenciales presente
if not SERVICE_ACCOUNT_FILE.exists():
    raise FileNotFoundError(f"ERROR: El Archivo de Credenciales Nó Fué Encontrado: {SERVICE_ACCOUNT_FILE}")

# Inicializar cliente de Google Sheets
creds = service_account.Credentials.from_service_account_file(
    str(SERVICE_ACCOUNT_FILE), scopes=SCOPES)
service = build('sheets', 'v4', credentials=creds)
sheets = service.spreadsheets()
tz = pytz.timezone(TIMEZONE)

# Normalizar nombre de hoja
SHEET_NAME = (SHEET_NAME or '').strip()

# --- Verificación de la existencia de la hoja en el spreadsheet ---
def _get_sheet_titles(spreadsheet_id):
    """Devuelve la lista de títulos (tabs) del spreadsheet."""
    try:
        meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id,
                                         includeGridData=False).execute()
    except HttpError as e:
        raise RuntimeError(f"ERROR: Nó Fué Posible Obtener Metadatos del Spreadsheet: {e}") from e

    sheets_meta = meta.get('sheets', []) or []
    titles = [s.get('properties', {}).get('title', '') for s in sheets_meta]
    return titles

# Comprobar que la hoja existe (ejecutar después de inicializar `service`)
try:
    titles = _get_sheet_titles(SPREADSHEET_ID)
except Exception as e:
    # Si no podemos obtener títulos por un fallo en la API, marcamos como no disponible
    print("ERROR: La Base De Datos Nó está Disponible, Reintente Nuevamente, Gracias.-")
    print(f"(DEBUG) ERROR: Al Obtener Pestañas: {repr(e)}")
    DATA_AVAILABLE = False
else:
    if SHEET_NAME not in titles:
        # Mensaje amigable solicitado por el usuario
        print("ERROR: La Base De Datos Nó está Disponible, Reintente Nuevamente, Gracias.-")
        # Log adicional opcional para debugging:
        print(f"(DEBUG) Pestañas Disponibles: {titles}")
        DATA_AVAILABLE = False
    else:
        # opcional: confirmar en log que la hoja fue encontrada
        print(f"(DEBUG) Hoja Encontrada: '{SHEET_NAME}' en Spreadsheet {SPREADSHEET_ID}")
        DATA_AVAILABLE = True

# --- Helper para construir rangos seguros ---
def _safe_range(sheet_name, a1_range):
    # envuelve el nombre con comillas simples para evitar errores si tiene espacios/símbolos
    return f"'{sheet_name}'!{a1_range}"


def append_row(values):
    """Agrega una fila al final de la hoja"""
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
    """Lee datos de la hoja"""
    if not DATA_AVAILABLE:
        print("La Base De Datos Nó Está Disponible, Reintente Nuevamente, Gracias.-")
        return []  # lectura no destructiva: devolvemos lista vacía

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
    """Actualiza una fila específica (row_index empieza en 2)"""
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
    Obtiene horarios disponibles para un coiffeur en una fecha específica

    Args:
        coiffeur: 'Walter' o 'María'
        fecha: string en formato 'YYYY-MM-DD'

    Returns:
        Lista de horarios disponibles ['10:00', '11:30', ...]
    """
    # Horarios Posibles del Salón ( Cada 30 Minutos ).-
    all_slots = [
        '09:00', '09:30', '10:00', '10:30', '11:00', '11:30',
        '12:00', '12:30', '13:00', '14:00', '14:30', '15:00',
        '15:30', '16:00', '16:30', '17:00', '17:30', '18:00', '18:30'
    ]

    # Obtener Turnos Ocupados
    data = read_sheet()
    occupied_slots = set()

    for row in data:
        if len(row) >= 7:
            # Verificar si el turno es del mismo coiffeur, fecha y está Confirmado o Pendiente
            if (row[3] == coiffeur and
                    row[4] == fecha and
                    row[6] in ['Confirmado', 'Pendiente']):
                occupied_slots.add(row[5])

    # Retornar horarios disponibles
    available = [slot for slot in all_slots if slot not in occupied_slots]
    return available


def check_availability(coiffeur, fecha, hora):
    """
    Verifica si un horario específico está disponible

    Returns:
        bool: True si está disponible, False si está ocupado
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
    Elige el coiffeur según preferencia y disponibilidad

    Args:
        preferencia: 'walter', 'maría', 'maria' o None
        fecha: fecha en formato 'YYYY-MM-DD'
        hora: hora en formato 'HH:MM'

    Returns:
        str: Nombre del coiffeur ('Walter' o 'María') o None si ninguno disponible
    """
    # Normalizar nombres
    if preferencia:
        preferencia = preferencia.lower()
        if preferencia in ['walter']:
            return 'Walter' if check_availability('Walter', fecha, hora) else None
        elif preferencia in ['maría', 'maria']:
            return 'María' if check_availability('María', fecha, hora) else None

    # Sin preferencia: aplicar round-robin o menor carga
    walter_available = check_availability('Walter', fecha, hora)
    maria_available = check_availability('María', fecha, hora)

    if walter_available and maria_available:
        # Aplicar estrategia de menor carga
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
# Pequeño "smoke test" local para verificar acceso a la hoja.
# Ejecutar sólo si quieres probar manualmente: python -m sheets.sheet_service
# ------------------------------------------------------------------
def smoke_test_read():
    """Lee unas filas y muestra cuántas devolvió la API (prueba de solo lectura)."""
    try:
        values = read_sheet('A1:K10')  # lectura conservadora
        print("SmokeTest: lectura OK. Filas devueltas:", len(values))
        # opcional: imprimir la primera fila
        if values:
            print("SmokeTest: primera fila:", values[0])
    except Exception as e:
        print("SmokeTest: ERROR en lectura:", repr(e))
        raise


def smoke_test_append():
    """Intenta agregar una fila de prueba identificable al final de la hoja."""
    ts = datetime.now(tz).astimezone(tz).isoformat()
    test_row = ['__SMOKE_TEST__', ts]
    try:
        append_row(test_row)
        print("SmokeTest: append OK. Fila añadida:", test_row)
    except Exception as e:
        print("SmokeTest: ERROR en append:", repr(e))
        raise


def smoke_test():
    """Ejecuta los tests de lectura y append (append es opcional)."""
    print("=== Iniciando Smoke Test de Google Sheets ===")
    print("Spreadsheet ID:", SPREADSHEET_ID)
    print("Sheet name (normalizado):", SHEET_NAME)
    try:
        # Verificar títulos para confirmar la existencia de la hoja
        titles = _get_sheet_titles(SPREADSHEET_ID)
        print("Pestañas disponibles:", titles)
    except Exception as e:
        print("No se pudieron obtener pestañas:", repr(e))
        return

    # Lectura (non-destructive)
    smoke_test_read()

    # Append de prueba: comentalo si NO querés escribir en la hoja
    smoke_test_append()
    print("=== Smoke Test completado ===")


if __name__ == "__main__":
    # Se ejecuta solo si corres el archivo directamente:
    # desde la raíz del proyecto: python -m sheets.sheet_service
    smoke_test()


