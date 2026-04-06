# -*- coding: utf-8 -*-
# *********************************************************************************************************************
#  Created By: Ing. Antonio Alberto Di Santo.-
#  Created On: Lunes 06 de Octubre del 2025.-
#
#     Program       :   Bot de WhatsApp con Google Sheets,
#                          para Asignación de Turnos en Negocios de Coiffeur's de MEMORY   Ingeniería en Sistemas.-
#
#    "Module Purpose:   Servicio de Comunicación con WhatsApp Cloud API.-
#                       Gestiona el Envío de Mensajes de Texto y Listas Interactivas a través de la API
#                       de WhatsApp Business. Implementa Autenticación mediante Token, Manejo de Errores
#                       Específicos ( Código 131030 para Números No Autorizados ), Logging Detallado de
#                       Operaciones, y Validación de Credenciales de Configuración.-
#
#
# *********************************************************************************************************************

""""
Servicio de Comunicación con WhatsApp Cloud API
Envía y Procesa Mensajes.-
"""
import requests
import os
import logging
from dotenv import load_dotenv

load_dotenv()

SYSTEM_MODE = os.getenv("SYSTEM_MODE", "disabled").lower()

logger = logging.getLogger(__name__)

# Usar las Variables Correctas Desde .env.-
WHATSAPP_TOKEN = os.getenv('WHATSAPP_ACCESS_TOKEN')
PHONE_NUMBER_ID = os.getenv('WHATSAPP_PHONE_NUMBER_ID')

# Verificar que las Credenciales Estén Configuradas.-
if not WHATSAPP_TOKEN:
    logger.error("ERROR: WHATSAPP_ACCESS_TOKEN    Nó Está Configurado en .env...")
if not PHONE_NUMBER_ID:
    logger.error("ERROR: WHATSAPP_PHONE_NUMBER_ID Nó Está Configurado en .env...")

WHATSAPP_API_URL = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"


#Envía un Mensaje de Texto a un Número de WhatsApp.-
def send_message(to_phone, message):
    """
    Envía un Mensaje de Texto a un Número de WhatsApp

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

    # Prefijo Según Modo Del Sistema.-
    prefix = ""

    if SYSTEM_MODE == "demo":
        prefix = "💈 *MODO DEMO ACTIVO*\n\n"
    elif SYSTEM_MODE == "disabled":
        message = "⚠️ El Sistema Nó Está Disponible en éste Momento...\nPor Favor Comuníquese con el Soporte de MEMORY   Ingeniería en Sistemas.-\n Soporte@MEMORY.com.ar"

    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "text",
        "text": {"body": prefix + message}
    }

    try:
        logger.info(f"Enviándo Mensaje a: {to_phone}")
        print(f"\n=== DEBUG INFO ===")
        print(f"Token: {WHATSAPP_TOKEN[:20]}...")
        print(f"Phone ID: {PHONE_NUMBER_ID}")
        print(f"URL: {WHATSAPP_API_URL}")
        print(f"To: {to_phone}")
        print(f"==================\n")

        response = requests.post(WHATSAPP_API_URL, headers=headers, json=payload)
        response.raise_for_status()
        logger.info(f"Mensaje Enviádo Exitosamente a: {to_phone}")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"ERROR al Enviar Mensaje a: {to_phone}: {e}")

        # AGREGAR: Manejo específico del ERROR: 131030
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_data = e.response.json()
                error_code = error_data.get('error', {}).get('code')
                error_msg = error_data.get('error', {}).get('message', '')

                if error_code == 131030:
                    print(f"\n⚠️  ATENCIÓN: El Número {to_phone} NO está en la Lista de Permitidos...")
                    print(f"    👉 Solución: Agregar el Número en Meta for Developers...")
                    print(f"    📱 URL: https://developers.facebook.com/apps\n")
            except:
                pass

        print(f"\n=== ERROR DETALLADO ===")
        print(f"Tipo de ERROR: {type(e).__name__}")
        print(f"Mensaje: {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Status: {e.response.status_code}")
            print(f"Body: {e.response.text}")
        else:
            print(f"Response: None ( ERROR: de Conexión o Solicitud Malformada...)")
        print(f"======================\n")
        return False


#Envía un Mensaje con Lista Interactiva (Para Horarios Disponibles).-
def send_list_message(to_phone, body_text, button_text, sections):
    """
    Envía un Mensaje con Lista Interactiva (Para Horarios Disponibles)

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

    prefix = ""

    if SYSTEM_MODE == "demo":
        prefix = "💈 *MODO DEMO ACTIVO*\n\n"
    elif SYSTEM_MODE == "disabled":
        body_text = "⚠️ El Sistema Nó Está Disponible en éste Momento...\nPor Favor Comuníquese con el Soporte de MEMORY   Ingeniería en Sistemas.-\n Soporte@MEMORY.com.ar"

    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {"text": prefix + body_text},
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

        # Manejo específico del error 131030
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_data = e.response.json()
                error_code = error_data.get('error', {}).get('code')

                if error_code == 131030:
                    print(f"\n⚠️  ATENCIÓN: El Número {to_phone} NO está en la Lista de Permitidos...")
                    print(f"    👉 Solución: Agregar el Número en Meta for Developers...")
                    print(f"    📱 URL: https://developers.facebook.com/apps\n")
            except:
                pass

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


