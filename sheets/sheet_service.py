# -*- coding: utf-8 -*-
# *********************************************************************************************************************
#  Created By: Ing. Antonio Alberto Di Santo.-
#  Created On: Lunes 06 de Octubre del 2025.-
#
#     Program       :   Bot de WhatsApp con Google Sheets,
#                          para Asignación de Turnos en Negocios de Coiffeur's de MEMORY   Ingeniería en Sistemas.-
#
#    "Module Purpose:   Proporciona la integración completa con Google Sheets, permitiendo leer, escribir y actualizar
#                       datos de turnos, feriados y calendarios visuales, además de aplicar formato automático a las hojas."

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
Servicio de Integración con Google Sheets.-
Gestiona Lectura, Escritura y Actualización de Turnos.-
"""

import logging

from dotenv import load_dotenv

logger = logging.getLogger(__name__)
#Nó Imprimir los 'Emojis'.-
logging.getLogger(__name__).handlers.clear()

import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

from pathlib import Path

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2 import service_account

from datetime import datetime

# ZONAS HORARIAS CENTRALIZADAS ( MEMORY Ingeniería en Sistemas ):
# Al Estar Ambos Archivos en la Misma Carpeta 'sheets/', sé Importa Directamente.-
from sheets.utils import obtener_ahora, tz

import json

# Aquí También sé Puede Usar la Misma Lógica sí es el mismo archivo.-
from sheets.utils import normalizar_hora

# Forzar La Carga de Variables Sí Existe un .env Local,
# pero Railway Las Inyectará Directamente.-
load_dotenv()

# Construye la Ruta al Archivo credentials.json Relativo a éste Archivo ( sheets/ ).-
HERE = Path(__file__).resolve().parent
SERVICE_ACCOUNT_FILE = HERE / 'credentials.json'

# ✅ Permisos desde Raíz de Google Drive:
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'  # Acceso completo para mover archivos a carpetas compartidas.-
]

# SPREADSHEET_ID se Obtendrá Dinámicamente según el Año del Turno.-
# Base ID desde .env (opcional, para Compatibilidad).-
BASE_SPREADSHEET_ID = os.getenv('SPREADSHEET_ID_2026', '1tz0n1qkfOOLg2HkAMdK_sYfz-aQZsJxBuMCTu_FNWXo')

# Nombre de la Empresa desde .env para Construir el Nombre de las Hojas.-
NOMBRE_EMPRESA = os.getenv('Nombre_de_la_Empresa', 'Rouss').strip()

# ID de la Carpeta de Google Drive donde se Crean las Hojas Anuales.-
DRIVE_FOLDER_ID = os.getenv('DRIVE_FOLDER_ID', '')

SPREADSHEET_ID = BASE_SPREADSHEET_ID  # Se Actualizará Dinámicamente.-

# Mapeo Manual de IDs por Año (Mientras Nó Implementemos Búsqueda en Google Drive).-
SPREADSHEET_IDS_BY_YEAR = {
    2026: os.getenv('SPREADSHEET_ID_2026', '1tz0n1qkfOOLg2HkAMdK_sYfz-aQZsJxBuMCTu_FNWXo'),
}

# Cargar Dinámicamente IDs de Años Futuros Desde .env ( Local ) o Variables de Railway.-
# Usamos obtener_ahora() para que el cálculo del año respete la zona horaria configurada.-
_ahora_local = obtener_ahora()
_año_actual = _ahora_local.year
_año_siguiente = _año_actual + 1

# Intentar Cargar ID del Año Actual Sí Nó Está en el Diccionario.-
_id_año_actual = os.getenv(f'SPREADSHEET_ID_{_año_actual}', '').strip()
if _id_año_actual:
    SPREADSHEET_IDS_BY_YEAR[_año_actual] = _id_año_actual

# Agrega Automáticamente el Año Siguiente Sí Está Configurado en las Variables de Entorno.-
_id_año_siguiente = os.getenv(f'SPREADSHEET_ID_{_año_siguiente}', '').strip()
if _id_año_siguiente:
    SPREADSHEET_IDS_BY_YEAR[_año_siguiente] = _id_año_siguiente


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
SHEET_NAME = 'Turnos_Coiffeur'

TIMEZONE = 'America/Argentina/Buenos_Aires'

# Verificación: Archivo de Credenciales Presente para Prueba en Modo Local con NGrok.-
# Leer variable UNA sola vez
import os
from google.oauth2 import service_account

print("🔥 MODO CARGA CREDENCIALES")

if os.getenv("RAILWAY_ENVIRONMENT"):
    print("🔵 Usando Credenciales Desde VARIABLE DE ENTORNO ( Railway )...")

    credentials_json = os.getenv("GOOGLE_CREDENTIALS_JSON")

    if not credentials_json:
        raise RuntimeError("GOOGLE_CREDENTIALS_JSON Nó Encontrado en Railway...")

    import json
    credentials_info = json.loads(credentials_json)

    credentials = service_account.Credentials.from_service_account_info(
        credentials_info
    )

else:
    print("🟢 Usando credentials.json LOCAL")

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    cred_path = os.path.join(BASE_DIR, "credentials.json")

    print(f"📄 Ruta Buscada: {cred_path}")

    if not os.path.exists(cred_path):
        raise RuntimeError(f"Archivo credentials.json Nó Encontrado en: {cred_path}")

    credentials = service_account.Credentials.from_service_account_file(
        cred_path
    )


GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON")
# Credenciales
if GOOGLE_CREDENTIALS_JSON:
    creds_dict = json.loads(GOOGLE_CREDENTIALS_JSON)
    creds = service_account.Credentials.from_service_account_info(
        creds_dict, scopes=SCOPES
    )
    creds_data = creds_dict

else:
    if not SERVICE_ACCOUNT_FILE.exists():
        logger.error(f"❌ ERROR: Nó Hay Credenciales Ní Variable en RailWay Ní Archivo Local: {SERVICE_ACCOUNT_FILE}")
        raise RuntimeError("Credenciales de Google Nó Configuradas Correctamente...")

    with open(SERVICE_ACCOUNT_FILE, 'r') as f:
        creds_data = json.load(f)

    creds = service_account.Credentials.from_service_account_file(
        str(SERVICE_ACCOUNT_FILE), scopes=SCOPES
    )

# Email del Service Account.-
service_account_email = creds_data.get('client_email')

if not service_account_email:
    logger.warning("⚠️ ERROR: Nó Sé Pudo Obtener él EMaiL del Service Account")

#Debug para RailWay.-
print("✅ Credenciales EMaiL del Service Account, Cargadas Correctamente")

import httplib2
import google_auth_httplib2

# Http con Timeout para Evitar Cuelgues SSL en Railway / Python 3.13.-
_http = httplib2.Http(timeout=30)
_authorized_http = google_auth_httplib2.AuthorizedHttp(creds, http=_http)

# Cliente Sheets con Transport Controlado ( Timeout SSL para Railway / Python 3.13 ).-
service = build('sheets', 'v4', http=_authorized_http)
sheets = service.spreadsheets()

import threading
# Storage por Hilo — Cada Hilo Flask / APScheduler Tiene su Propio Cliente SSL.-
_thread_local = threading.local()

# Lock Global — Serializa Llamadas a Google API.-
# Previene Segmentation Fault SSL en Python 3.13 con httplib2 Multi-Hilo.-
_api_lock = threading.Lock()

# ------------------------------------------------------------------------------
# Construye un Cliente Google Sheets Exclusivo para Cada Hilo.-
# Evita la Condición de Carrera SSL entre Flask y APScheduler.-
# httplib2.Http() NO es Thread-Safe — un Singleton Compartido Corrompe la
# Capa SSL cuando dos Hilos lo Usan Simultáneamente ( [SSL] record layer failure ).-
# ------------------------------------------------------------------------------
def _build_service():
    """
    Retorna un Cliente de Google Sheets Exclusivo para Cada Hilo.-
    Si el Hilo Nó Tiene Uno, lo Crea con su Propio httplib2.Http().-
    Si Ocurre un Error SSL, sé Limpia para Forzar Reconexión en el Próximo Llamado.-
    """
    if not hasattr(_thread_local, 'service') or _thread_local.service is None:
        _http_local = httplib2.Http(timeout=30)
        _auth_local  = google_auth_httplib2.AuthorizedHttp(creds, http=_http_local)
        _thread_local.service = build('sheets', 'v4', http=_auth_local)
    return _thread_local.service

tz = pytz.timezone(TIMEZONE)


def _invalidar_servicio_hilo():
    """Fuerza Reconexión en el Próximo Llamado a _build_service().-"""
    _thread_local.service = None


# Generar el Nombre de la Hoja de Cálculo para un Año Específico.-
def get_spreadsheet_name_for_year(year):
    """Genera el Nombre de la Hoja de Cálculo para un Año Específico"""
    return f"{year}_{NOMBRE_EMPRESA}_Turnos_Coiffeur"


#Obtiene el Año Actual en la Zona Horaria Configurada.-
def get_current_year():
    """Obtiene el Año Actual en la Zona Horaria Configurada"""
    return datetime.now(tz).year


def normalizar_fecha_a_iso(fecha):
    """
    Convierte cualquier Formato de Fecha a ISO (YYYY-MM-DD).-

    Args:
        fecha: Fecha en Formato ISO o largo Español.-

    Returns:
        str: Fecha en Formato ISO (YYYY-MM-DD).-
    """
    try:
        # Si Yá Está en Formato ISO.-
        if '-' in fecha and len(fecha.split('-')[0]) == 4:
            datetime.strptime(fecha, "%Y-%m-%d")  # Validar
            return fecha

        # Si Está en Formato Largo: "Miércoles, 26 de Noviembre de 2025"
        if ',' in fecha:
            partes = fecha.split(',')[1].strip().split(' ')
            dia = int(partes[0])
            mes_esp = partes[2]
            año = int(partes[4])
            meses = {
                'Enero': 1, 'Febrero': 2, 'Marzo': 3, 'Abril': 4,
                'Mayo': 5, 'Junio': 6, 'Julio': 7, 'Agosto': 8,
                'Septiembre': 9, 'Octubre': 10, 'Noviembre': 11, 'Diciembre': 12
            }
            return f"{año}-{meses[mes_esp]:02d}-{dia:02d}"

        return fecha  # Devolver Sin Cambios Sí Nó Coincide.-

    except Exception as e:
        logger.error(f"Error normalizando fecha '{fecha}': {e}")
        return fecha


# --------------------------------------------------------------------------------
# Validación de Fecha y Hora para Reglas del Negocio ( Turnos Permitidos ).-
# --------------------------------------------------------------------------------
def validar_fecha_hora_turno(fecha, hora=None):
    """
    Valida que:
      • La Fecha Pertenezca al Año Actual.-
      • La Fecha Nó sea de Días Pasados.-
      • La Hora Nó sea de Horas Pasadas (Sólo sí la Fecha es Hoy).-
      • La Hora esté Dentro del Rango Permitido del Negocio.-
    Lanza ValueError con Mensajes Claros sí Viola Lá Regla.-
    """

    tz_local = tz
    hoy = datetime.now(tz_local).date()

    try:
        # Intentar Primero Formato ISO (YYYY-MM-DD).-
        if '-' in fecha and len(fecha.split('-')[0]) == 4:
            fecha_dt = datetime.strptime(fecha, "%Y-%m-%d").date()
        # Si viene en Formato Largo Español: "Miércoles, 26 de Noviembre de 2025"
        elif ',' in fecha:
            partes = fecha.split(',')[1].strip().split(' ')
            dia = int(partes[0])
            mes_esp = partes[2]
            año = int(partes[4])
            meses = {
                'Enero': 1, 'Febrero': 2, 'Marzo': 3, 'Abril': 4,
                'Mayo': 5, 'Junio': 6, 'Julio': 7, 'Agosto': 8,
                'Septiembre': 9, 'Octubre': 10, 'Noviembre': 11, 'Diciembre': 12
            }
            fecha_dt = datetime(año, meses[mes_esp], dia).date()
        else:
            raise ValueError(f"❌ ERROR: Formato de Fecha Inválido: {fecha}")
    except Exception as e:
        raise ValueError(f"❌ ERROR: Formato de Fecha Inválido: {fecha}. Detalle: {str(e)}")

    # Validar Año Permitido Según Modo del Sistema.-
    # En Modo DEMO se Permite el Año Siguiente para Pruebas.-
    # En Producción Solo se Permite el Año Actual.-
    modo = os.getenv("SYSTEM_MODE", "production").lower()
    año_siguiente = hoy.year + 1

    if fecha_dt.year == hoy.year:
        pass  # Año Actual → Siempre Permitido.-

    elif fecha_dt.year == año_siguiente and modo == "demo":
        pass  # Año Siguiente → Permitido Sólo en Modo DEMO.-

    else:
        raise ValueError(
            f"❌ ERROR: Sólo sé Permiten Turnos del Año Actual ({hoy.year}). "
            f"Fecha Recibida: {fecha_dt.year}"
        )

    # Fecha Pasada.-
    if fecha_dt < hoy:
        raise ValueError(
            f"❌ ERROR: Nó sé Permiten Turnos en Días Anteriores. "
            f"Fecha Recibida: {fecha}"
        )

    # Validar Hora sí fué Pasada y Rango Permitido.-
    if hora is not None:
        # --- VALIDACIÓN DE FORMATO DE HORA ---
        try:
            hora_obj = datetime.strptime(hora, "%H:%M").time()
        except ValueError:
            raise ValueError(f"❌ ERROR: Formato de Hora Inválido: {hora}. Use formato HH:MM")

        # --- VALIDACIÓN DE HORA PASADA (si es hoy) ---
        if fecha_dt == hoy:
            ahora = datetime.now(tz_local).strftime("%H:%M")
            if hora < ahora:
                raise ValueError(
                    f"❌ ERROR: La Hora Indicada ({hora}) Yá Pasó. "
                    f"Hora Actual: {ahora}"
                )

        # --- VALIDACIÓN DE HORARIOS DEL NEGOCIO ---
        try:
            validar_horario_negocio(fecha_dt.strftime("%Y-%m-%d"), hora)
        except ValueError:
            # Re-lanzar el error con el mensaje personalizado de validar_horario_negocio
            raise

    return True


# --------------------------------------------------------------------------------
# Aplicar Formatos y Alineaciones a las Pestañas Recien Creadas.-
# --------------------------------------------------------------------------------
def aplicar_formatos_hoja(service, spreadsheet_id, sheet_title):
    """
        Aplica Alineación General y Formatos Especiales para las Columnas
        de la Pestaña indicada. NO se llama recursivamente.
        """
    # Obtener sheetId numérico
    sheets_info = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    sheet_id = None

    for sh in sheets_info.get("sheets", []):
        if sh["properties"]["title"] == sheet_title:
            sheet_id = sh["properties"]["sheetId"]
            break

    if sheet_id is None:
        print(f"⚠️  ERROR: No se Encontró la Pestaña: {sheet_title}")
        return

    requests = []

    # -----------------------------------------------------------------
    # 1) Alineación al Centro para TODAS LAS COLUMNAS de la Pestaña.-
    # -----------------------------------------------------------------
    requests.append({
        "repeatCell": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": 0,
                "startColumnIndex": 0
            },
            "cell": {
                "userEnteredFormat": {
                    "horizontalAlignment": "CENTER"
                }
            },
            "fields": "userEnteredFormat.horizontalAlignment"
        }
    })

    # -----------------------------------------------------------------
    # 2) Formato Moneda (Sólo Pestaña Turnos_Coiffeur).-
    # -----------------------------------------------------------------
    if sheet_title == "Turnos_Coiffeur":
        # Valor_del_Servicio (Columna I — índice 8)
        requests.append({
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startColumnIndex": 8,
                    "endColumnIndex": 9
                },
                "cell": {
                    "userEnteredFormat": {
                        "numberFormat": {
                            "type": "CURRENCY",
                            "pattern": "$#,##0.00"
                        }
                    }
                },
                "fields": "userEnteredFormat.numberFormat"
            }
        })

        # SubTOTALES (Columna J — índice 9)
        requests.append({
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startColumnIndex": 9,
                    "endColumnIndex": 10
                },
                "cell": {
                    "userEnteredFormat": {
                        "numberFormat": {
                            "type": "CURRENCY",
                            "pattern": "$#,##0.00"
                        }
                    }
                },
                "fields": "userEnteredFormat.numberFormat"
            }
        })

    # -----------------------------------------------------------------
    # Ejecutar los Formatos Solicitados.-
    # -----------------------------------------------------------------
    if requests:
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": requests}
        ).execute()

    print(f"🎨 Formatos Aplicados Correctamente a la Pestaña: {sheet_title}")


# --------------------------------------------------------------------------------
# Gestión de Carpeta en Google Drive para Organizar Hojas.-
# --------------------------------------------------------------------------------
def get_or_create_folder():
    """
    Obtiene o Crea la Carpeta en Google Drive para Organizar Hojas Anuales.-
    • Si DRIVE_FOLDER_ID Está Configurado en .env o Railway, lo Usa Directamente.-
    • Si Nó Está Configurado, Busca la Carpeta por Nombre o la Crea Automáticamente.-
    • Comparte la Carpeta con el Service Account si es Nueva.-

    Returns:
        str: ID de la Carpeta
    """
    # ✅ Si Yá Está Configurado en .env ( Local ) o en Railway, Usarlo Directamente.-
    # Evita Búsqueda en Drive y el Error 403 por Permisos Insuficientes.-
    if DRIVE_FOLDER_ID:
        logger.info(f"📁 Usando Carpeta Configurada en Variable de Entorno: {DRIVE_FOLDER_ID}")
        return DRIVE_FOLDER_ID

    FOLDER_NAME = f"{NOMBRE_EMPRESA}_Turnos_Coiffeur"

    try:
        # Crear cliente de Drive API
        drive_service = build('drive', 'v3', credentials=creds)

        # Buscar si la carpeta ya existe
        query = f"name='{FOLDER_NAME}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        results = drive_service.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name)'
        ).execute()

        folders = results.get('files', [])

        if folders:
            folder_id = folders[0]['id']
            logger.info(f"📁 Usando Carpeta Existente: '{FOLDER_NAME}' (ID: {folder_id})")
            return folder_id

        # Si no existe, crear la carpeta
        file_metadata = {
            'name': FOLDER_NAME,
            'mimeType': 'application/vnd.google-apps.folder'
        }

        folder = drive_service.files().create(
            body=file_metadata,
            fields='id'
        ).execute()

        folder_id = folder.get('id')
        logger.info(f"📁 Nueva Carpeta Creada: '{FOLDER_NAME}' (ID: {folder_id})")

        # Compartir la Carpeta con el Service Account.-
        try:
            service_account_email = creds_data.get('client_email')

            if not service_account_email:
                logger.warning("⚠️ ERROR: Nó Sé Pudo Obtener El EMaiL Del Service Account de Google Sheet's...")

            if service_account_email:
                permission = {
                    'type': 'user',
                    'role': 'writer',
                    'emailAddress': service_account_email
                }

                drive_service.permissions().create(
                    fileId=folder_id,
                    body=permission,
                    fields='id'
                ).execute()

                logger.info(f"🔐 Carpeta Compartida con: {service_account_email}")

        except Exception as e:
            logger.warning(f"⚠️ Nó sé Pudo Compartir Carpeta Automáticamente: {e}")

        return folder_id

    except Exception as e:
        logger.error(f"ERROR al Obtener / Crear Carpeta: {e}")
        return None


def find_spreadsheet_in_folder(folder_id, spreadsheet_name):
    """
    Busca una Hoja de Cálculo Específica Dentro de la Carpeta.-

    Args:
        folder_id: ID de la Carpeta donde Buscar
        spreadsheet_name: Nombre de la Hoja a Buscar

    Returns:
        str: ID de la Hoja si se Encuentra, None si no Existe
    """
    try:
        drive_service = build('drive', 'v3', credentials=creds)

        # Buscar archivos de tipo Google Sheets en la carpeta
        query = (
            f"name='{spreadsheet_name}' and "
            f"'{folder_id}' in parents and "
            f"mimeType='application/vnd.google-apps.spreadsheet' and "
            f"trashed=false"
        )

        results = drive_service.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name)'
        ).execute()

        files = results.get('files', [])

        if files:
            logger.info(f"📊 Hoja Encontrada en Carpeta: '{spreadsheet_name}' (ID: {files[0]['id']})")
            return files[0]['id']

        return None

    except Exception as e:
        logger.error(f"ERROR al Buscar Hoja en Carpeta: {e}")
        return None


# Obtiene el ID de la Hoja de Cálculo para un Año Específico.-
def get_or_create_spreadsheet_for_year(year):
    """
    Obtiene el ID de la Hoja de Cálculo para un Año Específico.-
    Si NO Existe, la Crea con las Pestañas Necesarias.-

    Returns:
        str: ID de la Hoja de Cálculo
    """
    # ✅ Definir Nombre Acá para que Esté Disponible en Todo el Scope de la Función.-
    spreadsheet_name = get_spreadsheet_name_for_year(year)

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

                # ----------------------------------------------------------------
                # Verificar que la Hoja Realmente Existe Antes de Retornarla.-
                # ----------------------------------------------------------------
                if year in SPREADSHEET_IDS_BY_YEAR:
                    sheet_id = SPREADSHEET_IDS_BY_YEAR[year]
                    try:
                        # Intentar acceder a la hoja para verificar que existe
                        service.spreadsheets().get(spreadsheetId=sheet_id).execute()
                        logger.info(f"📊 Usando Hoja Existente para el Año {year}: {sheet_id}")
                        return sheet_id
                    except HttpError as e:
                        # La hoja Nó Existe, Eliminar del caché y Continuar para Crearla.-
                        logger.warning(f"⚠️ Hoja del Año {year} con ID {sheet_id} Nó existe. Se Creará Una Nueva...")
                        del SPREADSHEET_IDS_BY_YEAR[year]
                        # También eliminar del JSON
                        del saved_ids[str(year)]
                        with open(config_file, 'w') as f:
                            json.dump(saved_ids, f, indent=2)
                # ----------------------------------------------------------------

    except Exception as e:
        logger.warning(f"Nó Sé Pudieron Cargar ID's Guardados: {e}")

        # Si Ya Tenemos el ID, Verificar que Existe y está en la Carpeta Correcta.-
        if year in SPREADSHEET_IDS_BY_YEAR:
            sheet_id = SPREADSHEET_IDS_BY_YEAR[year]
            try:
                # Intentar acceder a la hoja para verificar que existe
                service.spreadsheets().get(spreadsheetId=sheet_id).execute()
                logger.info(f"📊 Usando Hoja Existente para el Año {year}: {sheet_id}")
                return sheet_id
            except HttpError as e:
                # La hoja Nó Existe, Eliminar del Caché y Buscar en Carpeta.-
                logger.warning(f"⚠️ Hoja del año {year} con ID {sheet_id} Nó Existe. Buscando en Carpeta...")
                del SPREADSHEET_IDS_BY_YEAR[year]
                # Intentar eliminar del JSON también
                try:
                    config_file = HERE / 'spreadsheet_ids.json'
                    if config_file.exists():
                        with open(config_file, 'r') as f:
                            saved_ids = json.load(f)
                        if str(year) in saved_ids:
                            del saved_ids[str(year)]
                            with open(config_file, 'w') as f:
                                json.dump(saved_ids, f, indent=2)
                except:
                    pass

        # Buscar la Hoja en la Carpeta Antes de Crear Una Nueva.-
        folder_id = get_or_create_folder()
        if folder_id:
            existing_sheet_id = find_spreadsheet_in_folder(folder_id, spreadsheet_name)
            if existing_sheet_id:
                # Guardar el ID encontrado
                save_spreadsheet_id_for_year(year, existing_sheet_id)
                return existing_sheet_id

    # Si NÓ Existe, Crear Nueva Hoja.-
    spreadsheet_name = get_spreadsheet_name_for_year(year)

    try:
        # ----------------------------------------------------------------
        # Obtener ID de la Carpeta (se crea si no existe).-
        # ----------------------------------------------------------------
        folder_id = get_or_create_folder()

        # ----------------------------------------------------------------
        # Crear Nueva Hoja Copiando la Hoja Base del Año Actual.-
        # Usar files().copy() en Lugar de spreadsheets().create() Para Evitar
        # el Error 403 ( Los Service Accounts Nó Tienen Drive Propio Para Crear ).-
        # ----------------------------------------------------------------
        drive_service = build('drive', 'v3', credentials=creds)

        # Metadatos de la Copia: Nombre y Carpeta Destino.-
        copy_metadata = {'name': spreadsheet_name}
        if folder_id:
            copy_metadata['parents'] = [folder_id]

        # Copiar la Hoja Base ( BASE_SPREADSHEET_ID ) Como Plantilla.-
        copied = drive_service.files().copy(
            fileId=BASE_SPREADSHEET_ID,
            body=copy_metadata,
            fields='id'
        ).execute()

        new_id = copied['id']
        logger.info(f"📋 Hoja Copiada Desde Base: {BASE_SPREADSHEET_ID} → Nueva: {new_id}")

        # ----------------------------------------------------------------
        # Limpiar Datos de las Pestañas ( Mantener Sólo Encabezados ).-
        # La Copia Trae Todos los Datos del Año Anterior, hay que Borrarlos.-
        # ----------------------------------------------------------------
        tabs_to_clear = [
            'Turnos_Coiffeur',
            'Turnos_Calendario_Visual',
            'Turnos_Feriados',
        ]
        for tab in tabs_to_clear:
            try:
                service.spreadsheets().values().clear(
                    spreadsheetId=new_id,
                    range=f"'{tab}'!A2:Z10000"
                ).execute()
                logger.info(f"🧹 Datos Limpiados en Pestaña: '{tab}'")
            except Exception as e:
                logger.warning(f"⚠️ Nó sé Pudieron Limpiar Datos de '{tab}': {e}")
        # ----------------------------------------------------------------

        logger.info(f"✅ Nueva Hoja Creada para el Año {year}: {new_id}")

        # ----------------------------------------------------------------
        # Compartir Automáticamente con Service Account.-
        # ----------------------------------------------------------------
        try:
            # Leer Email del Service Account desde credentials.json o en RailWay.-
            service_account_email = creds_data.get('client_email')

            if not service_account_email:
                logger.warning("⚠️ ERROR: Nó Sé Pudo Obtener él EMaiL Del Service Account de Google Sheet's...")

            if service_account_email:
                # Crear cliente de Drive API usando las mismas credenciales
                drive_service = build('drive', 'v3', credentials=creds)

                # Compartir con permisos de Editor
                permission = {
                    'type': 'user',
                    'role': 'writer',
                    'emailAddress': service_account_email
                }

                drive_service.permissions().create(
                    fileId=new_id,
                    body=permission,
                    fields='id'
                ).execute()

                logger.info(f"🔐 Permisos Compartidos Automáticamente con: {service_account_email}")
            else:
                logger.warning("⚠️ Nó se Encontró 'client_email' en el Archivo 'credentials.json'...")

        except Exception as e:
            logger.error(f"❌ ERROR al Compartir Permisos Automáticamente: {e}")
            logger.warning(f"   sé DEBE Compartir MANUALMENTE la Hoja con el Service Account:")
            logger.warning(f"   URL: https://docs.google.com/spreadsheets/d/{new_id}")
            logger.warning(
                f"   Email: {service_account_email if 'service_account_email' in locals() else 'Ver credentials.json'}")
        # ----------------------------------------------------------------

        # Inicializar Encabezados.-
        inicializar_encabezados(new_id, 'Turnos_Coiffeur')
        inicializar_encabezados(new_id, 'Turnos_Calendario_Visual', tipo='calendario')
        inicializar_encabezados(new_id, 'Turnos_Feriados', tipo='feriados')
        inicializar_encabezados(new_id, 'Turnos_Horarios_Negocio', tipo='horarios')
        inicializar_encabezados(new_id, 'Turnos_Staff_Negocio', tipo='staff')

        # Aplicar Formatos a las 3 Pestañas (Sín Recursión).-
        aplicar_formatos_hoja(service, new_id, "Turnos_Coiffeur")
        aplicar_formatos_hoja(service, new_id, "Turnos_Calendario_Visual")
        aplicar_formatos_hoja(service, new_id, "Turnos_Feriados")

        # Guardar el Nuevo ID para Referencia Futura.-
        save_spreadsheet_id_for_year(year, new_id)

        return new_id

    except Exception as e:
        logger.error(f"ERROR al Crear / Obtener Hoja para el Año {year}: {e}")
        # Fallback al ID Base.-
        return BASE_SPREADSHEET_ID


# --------------------------------------------------------------------------------
# Generar la Hoja del Próximo Año ( Independiente del Año Actual ).-
# --------------------------------------------------------------------------------
def generar_hoja_del_proximo_año():
    """
    Genera y Prueba la Hoja del Próximo Año ( Año Actual + 1 ).-
    • Detecta el Año Actual.-
    • Calcula el Año Próximo.-
    • Crea la Nueva Hoja sí nó Existe.-
    • Guarda el Nuevo SPREADSHEET_ID en JSON y en el Archivo .env.
    • Devuelve el SPREADSHEET_ID Generado.-
    """

    tz_local = tz
    año_actual = datetime.now(tz_local).year
    año_proximo = año_actual + 1

    print(f"\n📄 Generando Hoja del Año Próximo: {año_proximo}...\n")

    # 1) Obtener o Crear Hoja para el Año Próximo.-
    try:
        spreadsheet_id = get_or_create_spreadsheet_for_year(año_proximo)
    except Exception as e:
        raise RuntimeError(f"❌ ERROR al Crear Hoja del Año {año_proximo}: {e}")

    print(f"✔ Hoja del Año {año_proximo} Creada / Verificada Correctamente.")
    print(f"🆔 SPREADSHEET_ID_{año_proximo} = {spreadsheet_id}")

    # 2) Guardar en .env (compatibilidad igual a SPREADSHEET_ID_2025).-
    env_path = os.path.join(os.getcwd(), '.env')

    try:
        # Leer Contenido Actual.-
        with open(env_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        entry = f"SPREADSHEET_ID_{año_proximo}={spreadsheet_id}\n"

        # Si nó existe, Agregarlo.-
        if not any(f"SPREADSHEET_ID_{año_proximo}" in line for line in lines):
            with open(env_path, 'a', encoding='utf-8') as f:
                f.write("\n# ID de la Hoja del Próximo Año Generada Automáticamente.-\n")
                f.write(entry)

        print(f"✔ SPREADSHEET_ID_{año_proximo} Guardado en .env Correctamente.-")

    except Exception as e:
        print(f"⚠️ Advertencia: Nó sé Pudo Guardar SPREADSHEET_ID en .env: {e}")

    return spreadsheet_id


#Inicializa los Encabezados de una Pestaña Nueva.-
def inicializar_encabezados(spreadsheet_id, sheet_name, tipo='turnos'):
    """Inicializa los Encabezados de una Pestaña Nueva"""
    if tipo == 'turnos':
        headers = [[
            'Nombre',
            'Teléfono',
            'Servicio',
            'Coiffeur',
            'Fecha',
            'Hora',
            'Estado',
            'Activo',
            'Valor_del_Servicio',
            'SubTOTALES',
            'FechaRegistro',
            'ReservationID',
            'TimestampExpiración'
        ]]

    elif tipo == 'calendario':
        # Generar Encabezados Dinámicos Basados en el Staff.-
        try:
            staff_names = obtener_staff_negocio()
            reserva_columns = [f'Reserva - {name}' for name in staff_names]
        except:
            # Fallback Sí Falla la Lectura.-
            reserva_columns = ['Reserva - Walter', 'Reserva - María']

        headers = [['Fecha', 'Hora'] + reserva_columns + ['Coiffeur - Servicio']]

    elif tipo == 'feriados':
        headers = [['Fecha', 'Motivo', 'Tipo', 'Activo']]

    elif tipo == 'horarios':
        headers = [['Día', 'Hora_Inicio_Mañana', 'Hora_Fin_Mañana', 'Hora_Inicio_Tarde', 'Hora_Fin_Tarde', 'Activo']]

    elif tipo == 'staff':
        headers = [['Staff_Nombres']]

    else:
        return

    try:
        # Seleccionar Rango Según Pestaña.-
        if tipo == 'turnos':
            full_range = f"'{sheet_name}'!A1:M1"  # 13 Columnas.-

        elif tipo == 'calendario':
            full_range = f"'{sheet_name}'!A1:E1"  # 05 Columnas.-

        elif tipo == 'feriados':
            full_range = f"'{sheet_name}'!A1:D1"  # 04 Columnas.-

        elif tipo == 'horarios':
            full_range = f"'{sheet_name}'!A1:F1"  # 06 Columnas.-

        else:
            return

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
def set_active_spreadsheet(year):
    global SPREADSHEET_ID

    if year in SPREADSHEET_IDS_BY_YEAR:
        SPREADSHEET_ID = SPREADSHEET_IDS_BY_YEAR[year]
        print(f"✅ Usando Hoja del Mapping Para {year}: {SPREADSHEET_ID}")
        return SPREADSHEET_ID

    # 👇 USAR VALIDACIÓN CORRECTA
    if puede_crear_hoja(year):
        print(f"📂 Creando o Buscando Hoja Para {year}...")

        new_id = get_or_create_spreadsheet_for_year(year)

        SPREADSHEET_ID = new_id
        return new_id

    raise Exception(
        f"🚫 ERROR: Nó Hay Hoja Configurada Ní Permitido Crearla Para él Año {year}"
    )


# Normalizar Nombre de Hoja.-
SHEET_NAME = (SHEET_NAME or '').strip()

# =========================================================
# 🧠 VALIDACIONES DE NEGOCIO  ← 👈 NUEVO BLOQUE
# =========================================================

def puede_pedir_turno(year):
    ahora = datetime.now(tz)
    año_actual = ahora.year
    mes_actual = ahora.month

    modo = os.getenv("SYSTEM_MODE", "production").lower()

    # Año Actual → Siempre Permitido.-
    if year == año_actual:
        return True

    # Año Siguiente a la Fecha Actual.-
    if year == año_actual + 1:
        # Producción → Sólo Desde el Mes de Diciembre.-
        if modo == "production":
            return mes_actual == 12

        # Demo → Permitir.-
        if modo == "demo":
            return True

        # Disabled → Núnca Crear.-
        if modo == "disabled":
            return False

    return False


def puede_crear_hoja(year):
    if os.getenv("AUTO_CREATE_YEARLY_SHEETS", "false").lower() != "true":
        return False

    ahora = datetime.now(tz)
    año_actual = ahora.year
    mes_actual = ahora.month

    # Solo Permitir Año Siguiente a la Fecha Actual.-
    if year != año_actual + 1:
        return False

    modo = os.getenv("SYSTEM_MODE", "production").lower()

    # Producción → Sólo Desde el Mes de Diciembre.-
    if modo == "production":
        return mes_actual == 12

    # Demo → Permitir.-
    if modo == "demo":
        return True

    # Disabled → Núnca Crear.-
    if modo == "disabled":
        return False

    return False


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
    full_range = _safe_range(SHEET_NAME, 'A:N')  # ← CAMBIO: Hasta Columna N ( La N oculta es la Fecha para la Ordenación ).-

    try:
        with _api_lock:
            _build_service().spreadsheets().values().append(
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

    # Leer TODAS las Columnas Reales de la Hoja: A hasta M.-
    if not range_a1:
        range_a1 = 'A2:N1000'  # ← Lee las 13 Columnas Reales, Incluír Columna N FechaISO para Ordenar Fechas.-.-

    full_range = _safe_range(SHEET_NAME, range_a1)  # ← MANTENER ESTA INDENTACIÓN.-
    try:
        with _api_lock:
            result = _build_service().spreadsheets().values().get(
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
#        "Turnos_Feriados"
#
#     • Acepta fechas en formato Texto (YYYY-MM-DD o DD/MM/YYYY).
#     • Interpreta una Segunda Columna opcional:
#           TRUE  → Feriado Activo.
#           FALSE → Feriado Desactivado (Ignorado).
#     • Retorna True sí la Fecha está marcada como Feriado Activo.
#
# *********************************************************************************************************************

#Verifica si la Fecha Indicada está Marcada como Feriado Activo en la Hoja: 'Turnos_Feriados'.-
def es_feriado(fecha):
    """
    Verifica si la Fecha Indicada está Marcada como Feriado Activo en la Hoja: 'Turnos_Feriados'.-
    • Solo considera filas donde la columna 'Activo' (D) NO sea FALSE / NO / 0.
    """
    FERIADOS_SHEET = 'Turnos_Feriados'
    try:
        full_range = _safe_range(FERIADOS_SHEET, 'A2:D100')
        with _api_lock:
            result = _build_service().spreadsheets().values().get(
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
    full_range = _safe_range(SHEET_NAME, f'A{row_index}:N{row_index}')  # ← Columna N = FechaISO para la Ordenación de Fechas.-

    try:
        with _api_lock:
            _build_service().spreadsheets().values().update(
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


#Ordena la Hoja Principal por FechaISO ( Col N ) y Hora ( Col F ) Ascendente.-
def ordenar_hoja():
    """
    Ordena 'Turnos_Coiffeur' por FechaISO ( Columna N ) y Hora ( Columna F )
    Ascendente después de Cada Confirmación de Turno.-
    """
    try:
        sheet_id = obtener_sheet_id(SHEET_NAME)

        requests_body = [{
            'sortRange': {
                'range': {
                    'sheetId': sheet_id,
                    'startRowIndex': 1,   # ← Fila 2 ( Saltear Encabezado ).-
                    'startColumnIndex': 0,
                    'endColumnIndex': 14  # ← Columnas A a N.-
                },
                'sortSpecs': [
                    {'dimensionIndex': 13, 'sortOrder': 'DESCENDING'},  # ← Col N FechaISO ( Fecha Mayor Primero ).-
                    {'dimensionIndex': 5,  'sortOrder': 'ASCENDING'},  # ← Col F Hora.-
                ]
            }
        }]

        service.spreadsheets().batchUpdate(
            spreadsheetId=SPREADSHEET_ID,
            body={'requests': requests_body}
        ).execute()

        logger.info("✔ Hoja Ordenada por FechaISO y Hora Ascendente...")

    except Exception as e:
        logger.error(f"ERROR al Ordenar Hoja: {e}")


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

    # Validar Reglas del Negocio (Año, Día y Hora Actual)
    try:
        validar_fecha_hora_turno(fecha)
    except ValueError as e:
        print(str(e))
        return []

    # Generar Horarios Según Configuración del Negocio.-
    all_slots = generar_horarios_disponibles_dia(fecha)

    if not all_slots:
        return []  # Día Completo Cerrado.-

    # Obtener Turnos Ocupados.-
    data = read_sheet()
    occupied_slots = set()

    for row in data:
        if len(row) >= 7:
            # Verificar si el Turno es del Mismo Coiffeur, Fecha y está Confirmado o Pendiente.-
            # Convertir Fecha Larga ( "Miércoles, 19 de Noviembre de 2025" ).-
            try:
                partes = row[4].split(',')[1].strip().split(' ')  # Fecha Sigue en E (índice 4) ✓
                dia = int(partes[0])
                mes_esp = partes[2]
                año = int(partes[4])
                meses = {
                    'Enero': 1, 'Febrero': 2, 'Marzo': 3, 'Abril': 4,
                    'Mayo': 5, 'Junio': 6, 'Julio': 7, 'Agosto': 8,
                    'Septiembre': 9, 'Octubre': 10, 'Noviembre': 11, 'Diciembre': 12
                }
                fecha_normalizada = f"{año}-{meses[mes_esp]:02d}-{dia:02d}"
            except:
                fecha_normalizada = row[4]

            if (row[3] == coiffeur and  # Coiffeur en D (índice 3) ✓
                    fecha_normalizada == fecha and
                    row[6] in ['Confirmado', 'Pendiente']):  # Estado en Columna G ( índice  6 ) ✓

                occupied_slots.add(row[5])  # Hora en Columna F (índice 5) ✓

    # Retornar Horarios Disponibles.-
    available = [slot for slot in all_slots if slot not in occupied_slots]
    return available


def generar_horarios_disponibles_dia(fecha):
    """
    Genera los horarios disponibles Según la Configuración de Turnos_Horarios_Negocio.-

    Args:
        fecha: Fecha en formato ISO (YYYY-MM-DD)

    Returns:
        Lista de horarios disponibles: ['09:00', '09:30', ...]
    """
    from datetime import datetime as dt, timedelta

    # Obtener día de la semana
    fecha_obj = dt.strptime(fecha, "%Y-%m-%d")
    dia_semana_ing = fecha_obj.strftime('%A')

    dias_es = {
        'Monday': 'Lunes',
        'Tuesday': 'Martes',
        'Wednesday': 'Miércoles',
        'Thursday': 'Jueves',
        'Friday': 'Viernes',
        'Saturday': 'Sábado',
        'Sunday': 'Domingo'
    }

    dia_semana = dias_es[dia_semana_ing]

    HORARIOS_SHEET = 'Turnos_Horarios_Negocio'

    try:
        full_range = _safe_range(HORARIOS_SHEET, 'A2:F10')
        with _api_lock:
            result = _build_service().spreadsheets().values().get(
                spreadsheetId=SPREADSHEET_ID,
                range=full_range
            ).execute()

        rows = result.get('values', []) or []
    except HttpError as e:
        logger.error(f"ERROR al Leer Horarios del Negocio: {e}")
        # Fallback a Horarios por Defecto.-
        return [
            '09:00', '09:30', '10:00', '10:30', '11:00', '11:30',
            '12:00', '12:30', '13:00', '14:00', '14:30', '15:00',
            '15:30', '16:00', '16:30', '17:00', '17:30', '18:00', '18:30'
        ]

    # Buscar Configuración del Día.-
    for row in rows:
        if not row or len(row) < 1:
            continue

        if row[0].strip() == dia_semana:
            # Verificar Sí Está Activo.-
            activo = row[5].strip().upper() if len(row) >= 6 else 'TRUE'

            if activo == 'FALSE':
                return []  # Día Completo Cerrado.-

            # Obtener horarios
            hora_inicio_manana = row[1].strip() if len(row) >= 2 and row[1].strip() else None
            hora_fin_manana = row[2].strip() if len(row) >= 3 and row[2].strip() else None
            hora_inicio_tarde = row[3].strip() if len(row) >= 4 and row[3].strip() else None
            hora_fin_tarde = row[4].strip() if len(row) >= 5 and row[4].strip() else None

            horarios = []

            # Generar Horarios de Mañana.-
            if hora_inicio_manana and hora_fin_manana:
                hora_actual = dt.strptime(hora_inicio_manana, "%H:%M")
                hora_limite = dt.strptime(hora_fin_manana, "%H:%M")

                while hora_actual < hora_limite:
                    horarios.append(hora_actual.strftime("%H:%M"))
                    hora_actual += timedelta(minutes=30)

            # Generar Horarios de Tarde.-
            if hora_inicio_tarde and hora_fin_tarde:
                hora_actual = dt.strptime(hora_inicio_tarde, "%H:%M")
                hora_limite = dt.strptime(hora_fin_tarde, "%H:%M")

                while hora_actual <= hora_limite:
                    horarios.append(hora_actual.strftime("%H:%M"))
                    hora_actual += timedelta(minutes=30)

            return horarios

    # Sí Nó Encuentra Configuración, Usar Horarios por Defecto.-
    return [
        '09:00', '09:30', '10:00', '10:30', '11:00', '11:30',
        '12:00', '12:30', '13:00', '14:00', '14:30', '15:00',
        '15:30', '16:00', '16:30', '17:00', '17:30', '18:00', '18:30'
    ]


# Valida los Horarios de Atención del Negocio.-
def validar_horario_negocio(fecha, hora):
    """
    Valida si el horario está dentro de los horarios de apertura del negocio.

    Args:
        fecha: Fecha en formato ISO (YYYY-MM-DD)
        hora: Hora en formato HH:MM (puede venir como 9:00 o 09:00)

    Returns:
        bool: True si está abierto

    Raises:
        ValueError: Si el negocio está cerrado
    """
    from datetime import datetime as dt

    HORARIOS_SHEET = 'Turnos_Horarios_Negocio'

    # -----------------------------
    # Helper local (robusto)
    # -----------------------------
    def _hora_a_time(h):
        try:
            hh, mm = h.strip().split(':')
            return dt.strptime(f"{int(hh):02d}:{mm}", "%H:%M").time()
        except:
            return None

    # -----------------------------
    # Día de la semana
    # -----------------------------
    fecha_obj = dt.strptime(fecha, "%Y-%m-%d")
    dia_semana_ing = fecha_obj.strftime('%A')

    dias_es = {
        'Monday': 'Lunes',
        'Tuesday': 'Martes',
        'Wednesday': 'Miércoles',
        'Thursday': 'Jueves',
        'Friday': 'Viernes',
        'Saturday': 'Sábado',
        'Sunday': 'Domingo'
    }

    dia_semana = dias_es[dia_semana_ing]

    # -----------------------------
    # Convertir hora de entrada
    # -----------------------------
    hora_t = _hora_a_time(hora)
    if not hora_t:
        raise ValueError("Hora inválida.")

    # -----------------------------
    # Leer configuración
    # -----------------------------
    try:
        full_range = _safe_range(HORARIOS_SHEET, 'A2:F10')
        with _api_lock:
            result = _build_service().spreadsheets().values().get(
                spreadsheetId=SPREADSHEET_ID,
                range=full_range
            ).execute()

        rows = result.get('values', []) or []
    except HttpError as e:
        logger.error(f"ERROR al Leer Horarios del Negocio: {e}")
        return True  # fallback permisivo

    # -----------------------------
    # Buscar día
    # -----------------------------
    for row in rows:
        if not row or len(row) < 1:
            continue

        if row[0].strip() == dia_semana:

            activo = row[5].strip().upper() if len(row) >= 6 else 'TRUE'

            if activo == 'FALSE':
                raise ValueError(
                    f"⚠️ Lo Siento, El Salón Permanece Cerrado los {dia_semana}s.\n\n"
                    f"Por Favor Elegí Otra Fecha Disponible..."
                )

            # -----------------------------
            # Convertir bloques a time
            # -----------------------------
            inicio_m = _hora_a_time(row[1]) if len(row) >= 2 and row[1].strip() else None
            fin_m    = _hora_a_time(row[2]) if len(row) >= 3 and row[2].strip() else None
            inicio_t = _hora_a_time(row[3]) if len(row) >= 4 and row[3].strip() else None
            fin_t    = _hora_a_time(row[4]) if len(row) >= 5 and row[4].strip() else None

            hora_valida = False

            # -----------------------------
            # Bloque mañana
            # -----------------------------
            if inicio_m and fin_m:
                if inicio_m <= hora_t < fin_m:
                    hora_valida = True

            # -----------------------------
            # Bloque tarde
            # -----------------------------
            if inicio_t and fin_t:
                if inicio_t <= hora_t <= fin_t:
                    hora_valida = True

            # -----------------------------
            # Fuera de horario
            # -----------------------------
            if not hora_valida:

                # Detectar horario de almuerzo
                if fin_m and inicio_t and fin_m <= hora_t < inicio_t:
                    raise ValueError(
                        f"⚠️ Lo Siento, El Salón está Cerrado por Hora de Almuerzo...\n\n"
                        f"📅 Horarios de Atención {dia_semana}:\n"
                        f"🌅 Mañana: {row[1]} a {row[2]}\n"
                        f"🌆 Tarde: {row[3]} a {row[4]}\n\n"
                        f"Por Favor Elegí Otro Horario..."
                    )

                # Fuera de rango total
                raise ValueError(
                    f"⚠️ Lo Siento, El Salón está Cerrado en ese Horario...\n\n"
                    f"📅 Horarios de Atención {dia_semana}:\n"
                    f"🌅 Mañana: {row[1] or 'Cerrado'} a {row[2] or 'Cerrado'}\n"
                    f"🌆 Tarde: {row[3] or 'Cerrado'} a {row[4] or 'Cerrado'}\n\n"
                    f"Por Favor Elegí Otro Horario..."
                )

            return True

    # Si no hay config → permitir
    return True


#Verifica si un Horario Específico está Disponible.-
def check_availability(coiffeur, fecha, hora):
    """
    Verifica si un Horario Específico está Disponible.-

    Returns:
        bool: True si está Disponible, False si Está Ocupado.-
    """

    # Función auxiliar para normalizar tildes y espacios.-
    def _norm(texto):
        import unicodedata
        texto = texto.strip()
        texto = ''.join(
            c for c in unicodedata.normalize('NFD', texto)
            if unicodedata.category(c) != 'Mn'
        )
        return texto.lower()

    # Normalizar coiffeur y hora (🔥 FIX IMPORTANTE)
    coiffeur_norm = _norm(coiffeur)
    hora_norm = normalizar_hora(hora)

    # Extraer Año de la Fecha y Configurar Hoja Activa.-
    try:
        fecha_iso = normalizar_fecha_a_iso(fecha)
        year = int(fecha_iso.split('-')[0])
        set_active_spreadsheet(year)
    except Exception as e:
        logger.warning(f"Nó Sé Pudo Cambiar Hoja para Año en Fecha: {fecha}: {e}")

    # Validaciones del Negocio.-
    try:
        validar_fecha_hora_turno(fecha, hora_norm)
    except ValueError as e:
        print(str(e))
        return False

    # Leer datos UNA sola vez
    try:
        data = read_sheet()
    except Exception as e:
        logger.error(f"ERROR al Leer Turnos: {e}")
        return False

    # Mapa meses (evita redefinir en cada loop)
    meses = {
        'Enero': 1, 'Febrero': 2, 'Marzo': 3, 'Abril': 4,
        'Mayo': 5, 'Junio': 6, 'Julio': 7, 'Agosto': 8,
        'Septiembre': 9, 'Octubre': 10, 'Noviembre': 11, 'Diciembre': 12
    }

    for row in data:
        if len(row) < 7:
            continue

        # Convertir Fecha Larga del Registro.-
        try:
            partes = row[4].split(',')[1].strip().split(' ')
            dia = int(partes[0])
            mes_esp = partes[2]
            año = int(partes[4])
            fecha_normalizada = f"{año}-{meses[mes_esp]:02d}-{dia:02d}"
        except Exception:
            fecha_normalizada = row[4].strip()

        # Normalizar Coiffeur Desde la Hoja.-
        row_coiffeur_norm = _norm(row[3])

        # Normalizar Estado.-
        estado = row[6].strip().lower()

        # Sólo 'confirmado' Significa Ocupado.-
        if estado != 'confirmado':
            continue

        # Normalizar Hora de la Fila.-
        row_hora = normalizar_hora(row[5])

        # Evaluar Disponibilidad.-
        if (
            row_coiffeur_norm == coiffeur_norm and
            fecha_normalizada == fecha and
            row_hora == hora_norm
        ):
            return False

    return True


#Elige el Coiffeur Según Preferencia y Disponibilidad.-
def elegir_coiffeur(preferencia, fecha, hora):
    """
    Elige el Coiffeur Según Preferencia y Disponibilidad.-

    Args:
        preferencia: nombre del Coiffeur Elegido o None.-
        fecha: 'YYYY-MM-DD'
        hora: 'HH:MM'

    Returns:
        str: Nombre del Coiffeur o None Sí Ninguno Disponible.-
    """

    # Función Auxiliar para Normalizar Tildes y Espacios.-
    def _norm(texto):
        import unicodedata
        texto = texto.strip()
        texto = ''.join(
            c for c in unicodedata.normalize('NFD', texto)
            if unicodedata.category(c) != 'Mn'
        )
        return texto.lower()

    hora_norm = hora.strip()

    # Leer STAFF Desde la Hoja Turnos_Staff_Negocio.-
    try:
        with _api_lock:
            staff_data = _build_service().spreadsheets().values().get(
                spreadsheetId=SPREADSHEET_ID,
                range=_safe_range('Turnos_Staff_Negocio', 'A1:A50')
            ).execute().get('values', [])

        staff_list = [
            fila[0].strip()
            for fila in staff_data
            if fila
               and fila[0].strip() != ""
               and fila[0].strip().lower() != "staff_nombres"
        ]
    except:
        staff_list = []

    # Sin Staff Nó Sé Puede Asignar.-
    if not staff_list:
        return None

    # Si el Cliente Eligió un Coiffeur Específico.-
    if preferencia:
        pref_norm = _norm(preferencia)
        for staff in staff_list:
            if _norm(staff) == pref_norm:
                return staff if check_availability(staff, fecha, hora_norm) else None
        return None

    # Sin Preferencia: Buscar el Primero Disponible.-
    disponibles = []

    for staff in staff_list:
        if check_availability(staff, fecha, hora_norm):
            disponibles.append(staff)

    # Si Nó Hay Ninguno Disponible.-
    if not disponibles:
        return None

    # Estrategia: Menor Cantidad de Turnos Confirmados ese Día.-
    data = read_sheet()
    carga = {}

    for staff in disponibles:
        count = 0
        staff_norm = _norm(staff)

        for row in data:
            if len(row) >= 7:

                # Normalizar Fecha Larga.-
                try:
                    partes = row[4].split(',')[1].strip().split(' ')
                    dia = int(partes[0])
                    mes_esp = partes[2]
                    año = int(partes[4])
                    meses = {
                        'Enero': 1, 'Febrero': 2, 'Marzo': 3, 'Abril': 4,
                        'Mayo': 5, 'Junio': 6, 'Julio': 7, 'Agosto': 8,
                        'Septiembre': 9, 'Octubre': 10, 'Noviembre': 11, 'Diciembre': 12
                    }
                    fecha_normalizada = f"{año}-{meses[mes_esp]:02d}-{dia:02d}"
                except:
                    fecha_normalizada = row[4].strip()

                estado = row[6].strip().lower()
                row_coiffeur_norm = _norm(row[3])

                # Solo Contar CONFIRMADO.-
                if (
                    row_coiffeur_norm == staff_norm and
                    fecha_normalizada == fecha and
                    estado == 'confirmado'
                ):
                    count += 1

        carga[staff] = count

    asignado = min(carga, key=carga.get)
    return asignado


# Genera o Actualiza el Calendario Visual Completo para una Fecha Específica.-
def reconstruir_calendario_completo():
    """
    Reconstruye el Calendario Visual COMPLETO desde cero basándose en TODOS
    los Turnos Confirmados de la Hoja 'Turnos_Coiffeur'.

    Se llama cada vez que se confirma un turno, garantizando que TODAS las
    fechas siempre estén reflejadas sin importar el orden de confirmación.

    Estrategia:
      1) Leer todos los turnos confirmados.
      2) Agrupar por fecha y ordenar cronológicamente.
      3) Limpiar el calendario existente.
      4) Escribir todos los bloques de una sola vez (una llamada a la API).
    """
    CALENDARIO_SHEET = 'Turnos_Calendario_Visual'

    horarios = [
        '09:00', '09:30', '10:00', '10:30', '11:00', '11:30',
        '12:00', '12:30', '13:00', '14:00', '14:30', '15:00',
        '15:30', '16:00', '16:30', '17:00', '17:30', '18:00', '18:30'
    ]

    # Leer STAFF desde "Turnos_Staff_Negocio".-
    try:
        with _api_lock:
            staff_data = _build_service().spreadsheets().values().get(
                spreadsheetId=SPREADSHEET_ID,
                range=_safe_range('Turnos_Staff_Negocio', 'A1:A50')
            ).execute().get('values', [])

        staff_list = [
            fila[0].strip()
            for fila in staff_data
            if fila
            and fila[0].strip() != ""
            and fila[0].strip().lower() != "staff_nombres"
        ]
    except Exception as e:
        logger.error(f"ERROR al Leer Staff: {e}")
        return False

    if not staff_list:
        logger.error("ERROR: No Hay STAFF Definido en 'Turnos_Staff_Negocio'...")
        return False

    # Leer todos los Turnos Confirmados.-
    try:
        data = read_sheet()
    except Exception as e:
        logger.error(f"ERROR al Leer Turnos para Reconstruir Calendario: {e}")
        return False

    meses_num = {
        'Enero': 1, 'Febrero': 2, 'Marzo': 3, 'Abril': 4,
        'Mayo': 5, 'Junio': 6, 'Julio': 7, 'Agosto': 8,
        'Septiembre': 9, 'Octubre': 10, 'Noviembre': 11, 'Diciembre': 12
    }

    #Definidos Localmente para Evitar Import Circular con bot.app.-
    DIAS = {
        'Monday': 'Lunes', 'Tuesday': 'Martes', 'Wednesday': 'Miércoles',
        'Thursday': 'Jueves', 'Friday': 'Viernes', 'Saturday': 'Sábado',
        'Sunday': 'Domingo'
    }
    MESES = {
        'January': 'Enero', 'February': 'Febrero', 'March': 'Marzo',
        'April': 'Abril', 'May': 'Mayo', 'June': 'Junio',
        'July': 'Julio', 'August': 'Agosto', 'September': 'Septiembre',
        'October': 'Octubre', 'November': 'Noviembre', 'December': 'Diciembre'
    }

    from datetime import datetime as _dt

    # ----------------------------------------------------------------------------------
    # 🔥 OPTIMIZACIÓN: AGRUPAR TURNOS CONFIRMADOS POR FECHA (UNA SOLA PASADA)
    # ----------------------------------------------------------------------------------
    turnos_por_fecha = {}

    for row in data:
        if len(row) < 7:
            continue
        if row[6].strip().lower() != 'confirmado':
            continue
        try:
            partes = row[4].split(',')[1].strip().split(' ')
            dia_n = int(partes[0])
            mes_esp = partes[2]
            anio_n = int(partes[4])
            fecha_iso = f"{anio_n}-{meses_num[mes_esp]:02d}-{dia_n:02d}"
        except Exception:
            continue

        if fecha_iso not in turnos_por_fecha:
            turnos_por_fecha[fecha_iso] = []

        turnos_por_fecha[fecha_iso].append(row)

    # ----------------------------------------------------------------------------------

    if not turnos_por_fecha:
        logger.info("Calendario: No hay turnos confirmados, nada que reconstruir.")
        return True

    # Ordenar Descendente: Fecha Más Próxima / Futura Primero.-
    fechas_ordenadas = sorted(turnos_por_fecha.keys(), reverse=True)

    num_columnas = 2 + len(staff_list)
    letra_fin = chr(64 + num_columnas)

    # Construir Todas Las Filas en Memoria.-
    todas_las_filas = []

    for idx, fecha_iso in enumerate(fechas_ordenadas):

        # Generar Fecha Larga en Castellano.-
        _fecha_obj = _dt.strptime(fecha_iso, "%Y-%m-%d")
        _dia_ing = _fecha_obj.strftime("%A")
        _mes_ing = _fecha_obj.strftime("%B")
        _fecha_larga = (
            f"{DIAS[_dia_ing]}, {_fecha_obj.day} "
            f"de {MESES[_mes_ing]} de {_fecha_obj.year}"
        )

        # Inicializar grilla de horarios para esta fecha.-
        turnos_del_dia = {h: {s: 'Libre' for s in staff_list} for h in horarios}

        # ----------------------------------------------------------------------------------
        # 🔥 USAMOS SOLO LOS TURNOS DE ESA FECHA (YA FILTRADOS)
        # ----------------------------------------------------------------------------------
        for row in turnos_por_fecha[fecha_iso]:

            hora = normalizar_hora(row[5])
            coiffeur = row[3].strip()

            if hora in horarios and coiffeur in staff_list:
                nombre = row[0].strip()
                servicio = row[2].strip()
                turnos_del_dia[hora][coiffeur] = f"{nombre} – {coiffeur} – {servicio}"

        # ----------------------------------------------------------------------------------

        # Fila separadora entre fechas (excepto antes de la primera).-
        if idx > 0:
            todas_las_filas.append([''] * num_columnas)

        # Agregar las filas de esta fecha.-
        for hora in horarios:
            fila = [_fecha_larga, hora]
            for staff in staff_list:
                fila.append(turnos_del_dia[hora][staff])
            todas_las_filas.append(fila)

    # Limpiar el calendario completo.-
    try:
        sheets.values().clear(
            spreadsheetId=SPREADSHEET_ID,
            range=_safe_range(CALENDARIO_SHEET, 'A1:Z5000')
        ).execute()

    except Exception as e:
        logger.error(f"ERROR al Limpiar Calendario Visual: {e}")
        return False

    # Escribir todo el calendario de una sola vez.-
    try:
        rango_total = _safe_range(
            CALENDARIO_SHEET,
            f"A1:{letra_fin}{len(todas_las_filas)}"
        )

        sheets.values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=rango_total,
            valueInputOption='USER_ENTERED',
            body={'values': todas_las_filas}
        ).execute()

        logger.info(
            f"Calendario Reconstruido: {len(fechas_ordenadas)} fecha(s), "
            f"{len(todas_las_filas)} filas totales."
        )
        return True

    except HttpError as e:
        logger.error(f"ERROR al Escribir Calendario Visual: {e}")
        return False


# Mantener alias para compatibilidad con cualquier llamada existente.-
def actualizar_calendario_dia(fecha_objetivo):
    """
    Delegá a reconstruir_calendario_completo para Garantizar
    Orden Correcto ( Hoy Primero ) y Separadores entre Fechas en Cada Confirmación.-
    """
    logger.info(f"(calendario) Delegando a reconstruir_calendario_completo para: {fecha_objetivo}")
    return reconstruir_calendario_completo()


def obtener_sheet_id(nombre_hoja):
    """Devuelve el SheetId ( numérico ) de una Pestaña, Requerido para BatchUpdate..."""
    try:
        spreadsheet = service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()

        for sheet in spreadsheet.get('sheets', []):
            props = sheet.get("properties", {})
            if props.get("title") == nombre_hoja:
                return props.get("sheetId")

    except Exception as e:
        logger.error(f"ERROR al Obtener sheetId Para: '{nombre_hoja}': {e}")

    return None


#Colorea Automáticamente las Filas de la Pestaña 'Turnos_Feriados'.-
def colorear_feriados():
    """
    Colorea Automáticamente las Filas de la Pestaña 'Turnos_Feriados'.-
    • Feriados Activos (TRUE o vacío): Fondo Rojo Claro y texto Negrita.
    • Feriados Desactivados (FALSE / NO / 0): Fondo Blanco y texto normal.
    """
    # ----------------------------------------------------------------
    # Protección contra Timeouts: Limitar Ejecución.-
    # ----------------------------------------------------------------
    import time
    _ultimo_coloreado = getattr(colorear_feriados, '_ultimo_coloreado', 0)
    ahora = time.time()

    # Solo ejecutar si pasaron al menos 5 minutos (300 segundos)
    if ahora - _ultimo_coloreado < 300:
        logger.debug(f"Coloreado omitido (última ejecución hace {int(ahora - _ultimo_coloreado)}s)")
        return

    colorear_feriados._ultimo_coloreado = ahora
    # ----------------------------------------------------------------

    FERIADOS_SHEET = 'Turnos_Feriados'

    try:
        full_range = _safe_range(FERIADOS_SHEET, 'A2:D100')

        result = _build_service().spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=full_range
        ).execute()

        rows = result.get('values', []) or []

    except HttpError as e:
        logger.error(f"ERROR al Leer Pestaña de Feriados (colorear): {e}")
        return

    except Exception as e:
        logger.error(f"ERROR / TIMEOUT al Leer Feriados (colorear): {type(e).__name__}: {e}")
        _invalidar_servicio_hilo()
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
            valor_activo = ""
        else:
            continue

        # Determinar Estado del Día Nó Laborable o Feriado
        activo = valor_activo not in ['FALSE', 'NO', '0']

        # Definir Formato de Color y Texto
        if activo:
            color = {"red": 1, "green": 0.8, "blue": 0.8}  # Rojo Claro
            text_format = {"bold": True}
        else:
            color = {"red": 1, "green": 1, "blue": 1}  # Blanco
            text_format = {"bold": False}

        if activo:
            logger.info(f"(INFO) Día {row[0] if row else '?'} ACTIVADO — Marcado como Día Nó Laborable o Feriado...")
        else:
            logger.info(
                f"(INFO) Día {row[0] if row else '?'} DESACTIVADO — Se Quitó Formato de Día Nó Laborable o Feriado...")

        # Aplicar Formato a Columnas A, B, C y D (índices 0—3)
        requests.append({
            "updateCells": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": i + 1,
                    "endRowIndex": i + 2,
                    "startColumnIndex": 0,
                    "endColumnIndex": 4
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

    # Ejecutar Actualización Masiva ( Sólo si Hay Algo que Aplicar ).-
    if requests:
        body = {"requests": requests}
        try:
            _build_service().spreadsheets().batchUpdate(
                spreadsheetId=SPREADSHEET_ID,
                body=body
            ).execute()

            logger.info(f"(DEBUG) Coloreado de {len(requests)} Filas en '{FERIADOS_SHEET}' Completado...")

        except HttpError as e:
            logger.error(f"ERROR al Colorear Feriados: {e}")
        except Exception as e:               # ← Captura SSL, Timeout y Cualquier Otro Error.-
            logger.error(f"ERROR / TIMEOUT al Colorear Feriados: {type(e).__name__}: {e}")


# --------------------------------------------------------------------------------
# Lectura Dinámica del Staff desde Google Sheets.-
# --------------------------------------------------------------------------------
def obtener_staff_negocio():
    """
    Lee los Nombres del Staff desde la Pestaña 'Turnos_Staff_Negocio'.-

    Returns:
        list: Lista de Nombres del Staff (ej.: ['Walter', 'María'])
    """
    STAFF_SHEET = 'Turnos_Staff_Negocio'

    try:
        full_range = _safe_range(STAFF_SHEET, 'A2:A100')
        result = _build_service().spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=full_range
        ).execute()
        rows = result.get('values', []) or []

        # Filtrar nombres vacíos y normalizar.-
        staff_names = [row[0].strip() for row in rows if row and row[0].strip()]

        if not staff_names:
            logger.warning("⚠️ Nó Sé Encontraron Nombres en 'Turnos_Staff_Negocio', Usando Valores por Defecto...")
            return ['Walter', 'María']  # Fallback.-

        logger.info(f"✅ Staff Cargado desde Google Sheets: {staff_names}")
        return staff_names

    except HttpError as e:
        logger.error(f"ERROR: al Leer Pestaña de Staff en 'Turnos_Staff_Negocio': {e}")
        return ['Walter', 'María']  # Fallback en caso de error.-


# ------------------------------------------------------------------------------------------
# Lectura Dinámica de Servicios Desde la Hoja Turnos_Servicios_Negocio desde Google Sheets.-
# Ahora Filtra por Columna "Activo" (B) y Devuelve Sólo los Servicios con Activo = TRUE.-
# y los Iconos Correspondientes.-
# ------------------------------------------------------------------------------------------
def obtener_servicios_negocio():
    """
    Lee los Servicios Disponibles Desde la Hoja Turnos_Servicios_Negocio.-
    Devuelve una lista de diccionarios:
        [{'servicio': 'Color', 'icono': '🎨'}, ...]
    Solo incluye servicios donde 'Activo' == TRUE.-
    """

    try:
        # Leer Columnas A (Servicio), B (Activo), C (Icono)
        service_data = _build_service().spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=_safe_range('Turnos_Servicios_Negocio', 'A2:C100')
        ).execute().get('values', [])

        servicios = []

        for fila in service_data:
            if len(fila) < 3:
                continue

            nombre = fila[0].strip()
            activo = fila[1].strip().upper()
            icono = fila[2].strip()

            # Filtrar Vacíos y Sólo Incluir Activos.-
            if nombre != "" and activo == "TRUE":
                servicios.append({
                    'servicio': nombre,
                    'icono': icono if icono else '✂️'
                })

        return servicios

    except Exception as e:
        logger.error(f"ERROR: al Leer Servicios del Negocio: {e}")
        return []


# --------------------------------------------------------------------------------
# Pequeño "smoke test" Local para Verificar Acceso a la Hoja de Cálculo.-
# Ejecutar Sólo Sí sé Quiere Probar Manualmente: python -m sheets.sheet_service
# --------------------------------------------------------------------------------

#Lee Unas Filas y Muestra Cuántas Devolvió la API (Prueba de Solo Lectura).-
def smoke_test_read():
    """Lee Unas Filas y Muestra Cuántas Devolvió la API (Prueba de Solo Lectura)"""
    try:
        values = read_sheet('A1:M10')  # ← CAMBIO: Hasta Columna M.-
        print("SmokeTest: Lectura OK. Filas Devueltas:", len(values))
        # Opcional: Imprimir lá Primera Fila.-
        if values:
            print("SmokeTest: Primera Fila: ", values[0])
    except Exception as e:
        print("SmokeTest: ERROR en Lectura: ", repr(e))
        raise


# Intenta Agregar una Fila de Prueba Identificable al Final de la Hoja
def smoke_test_append():
    """Intenta Agregar una Fila de Prueba Identificable al Final de la Hoja"""
    # Usamos el Motor de Tiempo de MEMORY Ingeniería en Sistemas.-
    # obtener_ahora() ya devuelve el objeto localizado según el .env.-
    ts = obtener_ahora().isoformat()

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


