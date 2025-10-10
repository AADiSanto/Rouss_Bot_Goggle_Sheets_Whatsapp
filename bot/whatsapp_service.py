""""
Servicio de comunicación con WhatsApp Cloud API
Envía y procesa mensajes
"""

import requests
import os
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Usar las variables correctas desde .env
WHATSAPP_TOKEN = os.getenv('WHATSAPP_ACCESS_TOKEN')
PHONE_NUMBER_ID = os.getenv('WHATSAPP_PHONE_NUMBER_ID')

# Verificar que las credenciales estén configuradas
if not WHATSAPP_TOKEN:
    logger.error("ERROR: WHATSAPP_ACCESS_TOKEN    Nó Está Configurado en .env...")
if not PHONE_NUMBER_ID:
    logger.error("ERROR: WHATSAPP_PHONE_NUMBER_ID Nó Está Configurado en .env...")

WHATSAPP_API_URL = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"


def send_message(to_phone, message):
    """
    Envía un mensaje de texto a un número de WhatsApp

    Args:
        to_phone: Número con código de país (ej: +5491122233344)
        message: Texto del mensaje
    """
    if not WHATSAPP_TOKEN or not PHONE_NUMBER_ID:
        logger.error("Credenciales de WhatsApp Nó Configuradas...")
        return False

    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "text",
        "text": {"body": message}
    }

    try:
        logger.info(f"Enviándo Mensaje a: {to_phone}")
        print(f"\n=== DEBUG INFO ===")
        print(f"Token: {WHATSAPP_TOKEN[:20]}...")
        print(f"Phone ID: {PHONE_NUMBER_ID}")
        print(f"URL: {WHATSAPP_API_URL}")
        print(f"Headers: {headers}")
        print(f"Payload: {payload}")
        print(f"==================\n")

        response = requests.post(WHATSAPP_API_URL, headers=headers, json=payload)
        response.raise_for_status()
        logger.info(f"Mensaje Enviádo Exitosamente a: {to_phone}")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"ERROR al Enviar Mensaje a: {to_phone}: {e}")
        print(f"\n=== ERROR DETALLADO ===")
        print(f"Tipo de ERROR: {type(e).__name__}")
        print(f"Mensaje: {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Status: {e.response.status_code}")
            print(f"Headers respuesta: {e.response.headers}")
            print(f"Body: {e.response.text}")
        else:
            print(f"Response: None ( ERROR: de Conexión o Solicitud Malformada...)")
        print(f"======================\n")
        return False


def send_list_message(to_phone, body_text, button_text, sections):
    """
    Envía un mensaje con lista interactiva (para horarios disponibles)

    Args:
        to_phone: Número destinatario
        body_text: Texto principal del mensaje
        button_text: Texto del botón
        sections: Lista de secciones con opciones
    """
    if not WHATSAPP_TOKEN or not PHONE_NUMBER_ID:
        logger.error("Credenciales de WhatsApp Nó Configuradas...")
        return False

    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {"text": body_text},
            "action": {
                "button": button_text,
                "sections": sections
            }
        }
    }

    try:
        logger.info(f"Enviándo Lista a: {to_phone}")
        print(f"\n=== DEBUG INFO ( LIST ) ===")
        print(f"URL: {WHATSAPP_API_URL}")
        print(f"Payload: {payload}")
        print(f"========================\n")

        response = requests.post(WHATSAPP_API_URL, headers=headers, json=payload)
        response.raise_for_status()
        logger.info(f"Lista Enviada Exitosamente a: {to_phone}")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"ERROR al Enviar Lista a {to_phone}: {e}")
        print(f"\n=== ERROR DETALLADO ( LIST ) ===")
        print(f"Tipo de ERROR: {type(e).__name__}")
        print(f"Mensaje: {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Status: {e.response.status_code}")
            print(f"Body: {e.response.text}")
        else:
            print(f"Response: None ( ERROR: de Conexión o Solicitud Malformada...)")
        print(f"==============================\n")
        return False


