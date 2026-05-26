# -*- coding: utf-8 -*-
# *********************************************************************************************************************
#  Created By: Ing. Antonio Alberto Di Santo.-
#  Created On: Lunes 06 de Octubre del 2025.-
#
#     Program       :   Bot de WhatsApp con Google Sheets,
#                          para Asignación de Turnos en Negocios de Coiffeur's de MEMORY   Ingeniería en Sistemas.-
#
#    "Module Purpose:   Servidor Flask Principal - Gestión del Webhook de WhatsApp.-
#                       Maneja la Recepción y Procesamiento de Mensajes Entrantes, Implementa el Flujo
#                       Conversacional Completo para Reserva de Turnos ( Selección de Coiffeur, Nombre,
#                       Servicio, Fecha y Hora ), Valida Disponibilidad en Tiempo Real, Crea Reservas
#                       Provisionales con Timeout de 60 Segundos, y Gestiona la Confirmación Final de Turnos.
#                       Mantiene el Estado de Conversaciones de Múltiples Usuarios Simultáneos.-
#
#
# *********************************************************************************************************************

"""
Servidor Flask principal - Webhook de WhatsApp
Maneja la Lógica Conversacional y Flujo de Turnos.-
"""
import logging

import os

from sheets.sheet_service import obtener_staff_negocio, obtener_staff_con_ids
from sheets.utils import log_throttled

# --- Cargar Variables de Entorno ---
NOMBRE_EMPRESA = os.getenv('Nombre_de_la_Empresa', 'Negocio') # 'Nombre del Negocio...'

print("🔍 SYSTEM_MODE         :", os.getenv("SYSTEM_MODE"))
print("🔍 FLASK_ENV           :", os.getenv("FLASK_ENV"))
print("🔍 Nombre de la Empresa:", os.getenv("Nombre_de_la_Empresa"))


# Diccionarios para Días y Meses en Castellano.-
DIAS = {
    'Monday': 'Lunes',
    'Tuesday': 'Martes',
    'Wednesday': 'Miércoles',
    'Thursday': 'Jueves',
    'Friday': 'Viernes',
    'Saturday': 'Sábado',
    'Sunday': 'Domingo'
}

MESES = {
    'January': 'Enero',
    'February': 'Febrero',
    'March': 'Marzo',
    'April': 'Abril',
    'May': 'Mayo',
    'June': 'Junio',
    'July': 'Julio',
    'August': 'Agosto',
    'September': 'Septiembre',
    'October': 'Octubre',
    'November': 'Noviembre',
    'December': 'Diciembre'
}

# Importar Función de Lectura de Staff.-
from sheets.sheet_service import obtener_staff_negocio

# Importar Servicios del Negocio.-
from sheets.sheet_service import obtener_servicios_negocio

# Cache para Nombres del Staff (evita leer Google Sheets en cada mensaje).-
_STAFF_CACHE = None
_STAFF_CACHE_TIME = 0

# --------------------------------------------------------------------------------------
# Íconos Globales de Servicios del Negocio (Centralizado - Keys con Mayúscula Inicial) -
# --------------------------------------------------------------------------------------
SERVICE_ICONS = {
    'Color': '🎨',
    'Corte': '✂️',
    'Manicura': '💅',
    'Mechas': '🌟',
    'Peinado': '💇',
    'Permanente': '🌀'
}


def get_staff_names():
    """Obtiene Nombres del Staff con caché de 05 Minutos"""
    global _STAFF_CACHE, _STAFF_CACHE_TIME
    import time

    now = time.time()
    # Refrescar Caché Cada 05 minutos (300 Segundos).-
    if _STAFF_CACHE is None or (now - _STAFF_CACHE_TIME) > 300:
        _STAFF_CACHE = obtener_staff_negocio()
        _STAFF_CACHE_TIME = now

        log_throttled('info', f"🔄 Caché de Staff Actualizado: {_STAFF_CACHE}", logger)

    return _STAFF_CACHE

# Cache para Staff con IDs ( Evita Leer Google Sheets en Cada Mensaje ).-
_STAFF_IDS_CACHE = None
_STAFF_IDS_CACHE_TIME = 0


def get_staff_with_ids():
    """Obtiene Staff con IDStaff con caché de 05 Minutos.-"""
    global _STAFF_IDS_CACHE, _STAFF_IDS_CACHE_TIME
    import time

    now = time.time()
    # Refrescar Caché Cada 05 Minutos ( 300 Segundos ).-
    if _STAFF_IDS_CACHE is None or (now - _STAFF_IDS_CACHE_TIME) > 300:
        _STAFF_IDS_CACHE = obtener_staff_con_ids()
        _STAFF_IDS_CACHE_TIME = now

        log_throttled('info', f"🔄 Caché de Staff con IDs Actualizado: {_STAFF_IDS_CACHE}", logger)

    return _STAFF_IDS_CACHE


# ---------------------------------------------------------------------------------
# CONFIGURACIÓN DE LOGS ( MEMORY Ingeniería en Sistemas ).-
# ---------------------------------------------------------------------------------
# Obtenemos él Modo Dé Ejecución Para Definir él Nivel de Logs.-
SYSTEM_MODE = os.getenv("SYSTEM_MODE", "disabled").lower()

# En Producción ( RailWay ) Usamos WARNING Para Evitar Saturar Registros.-
# En Desarrollo ( PyCharm / NGrok ) Mantenemos INFO Para Supervisar él Flujo.-
LOG_LEVEL = logging.WARNING if SYSTEM_MODE == "production" else logging.INFO

logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# ✅ Silenciar los Pings y Peticiones HTTP Rutinarias de Flask/Werkzeug, sólo Los ERRORES.-
logging.getLogger('werkzeug').setLevel(logging.ERROR)

from flask import Flask, request, jsonify

import os

from pathlib import Path

if os.getenv("RAILWAY_ENVIRONMENT") is None:
    from dotenv import load_dotenv

    BASE_DIR = Path(__file__).resolve().parent.parent
    env_path = BASE_DIR / ".env"

    print(f"📄 Cargando .env Desde: {env_path}")

    load_dotenv(env_path)

from datetime import datetime  # ← AGREGADO PARA TIMESTAMP

from sheets.sheet_service import (
    get_available_slots, check_availability,
    elegir_coiffeur, tz, validar_fecha_hora_turno  # ← AGREGADO validar_fecha_hora_turno
)

from sheets.scheduler_service import (
    crear_reserva_provisional, confirmar_reserva,
    iniciar_scheduler, RESERVA_SECONDS
)

from bot.whatsapp_service import send_message, send_list_message

app = Flask(__name__)
VERIFY_TOKEN = os.getenv('WEBHOOK_VERIFY_TOKEN')

# Diccionario para Mantener Estado de Conversaciones ( En Producción Usar Redis / DB ).-
conversations = {}


@app.route('/webhook', methods=['GET'])
# Verificación del webhook por Parte de Meta.-
def verify_webhook():
    """Verificación del webhook por Parte de Meta"""
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')

    if mode == 'subscribe' and token == VERIFY_TOKEN:
        return challenge, 200
    else:
        return 'Forbidden', 403


@app.route('/webhook', methods=['POST'])
# Recibe Mensajes Entrantes de WhatsApp.-
def receive_message():
    """Recibe Mensajes Entrantes de WhatsApp"""
    try:
        data = request.get_json()

        if not data or 'entry' not in data:
            return 'OK', 200

        # Extraer Mensaje.-
        entry = data['entry'][0]
        changes = entry.get('changes', [])

        if not changes:
            return 'OK', 200

        value = changes[0].get('value', {})
        messages = value.get('messages', [])

        if not messages:
            return 'OK', 200

        message = messages[0]

        # Obtener número del Remitente y Limpiar Formato Argentino.-
        sender_raw = message['from']

        # Si el número es Argentino (549...), Quitar el 9 del Celular.-
        if sender_raw.startswith('549'):
            sender = '54' + sender_raw[3:]  # Quita el '9' Después de '54'.-
        else:
            sender = sender_raw

        # -------------------------------
        # CONTROL DE MODO DEL SISTEMA
        # -------------------------------
        import os
        SYSTEM_MODE = os.getenv("SYSTEM_MODE", "disabled").lower()

        if SYSTEM_MODE == "disabled":
            from bot.whatsapp_service import send_message

            send_message(
                sender,
                "⚠️ Sistema Nó Disponible en éste Momento...\n\n"
                "Por Favor Comunicate con MEMORY   Ingeniería en Sistemas... Soporte@MEMORY.com.ar"
            )
            return 'OK', 200

        # Procesar Diferentes Tipos de Mensaje.-
        if message['type'] == 'text':
            text = message['text']['body'].strip()
            process_text_message(sender, text)
        elif message['type'] == 'interactive':
            interactive = message['interactive']
            if interactive['type'] == 'list_reply':
                selected_id = interactive['list_reply']['id']
                process_interactive_response(sender, selected_id)

        return 'OK', 200

    except Exception as e:
        print(f"ERROR Procesando Mensaje del Cliente: {e}")
        return 'OK', 200


# Procesa Mensajes de Texto Según el Estado de la Conversación.-
def process_text_message(sender, text):
    """Procesa Mensajes de Texto Según el Estado de la Conversación"""
    # ✅ VALIDACIÓN INICIAL:
    # Sí él Texto está Vacío o es None ( Notificaciones dé Estado de Meta ), Salimos de la Función.-
    if not text or not str(text).strip():
        # logger.info(f"Ignorando mensaje vacío o notificación de estado de: {sender}")
        return

    text_lower = text.lower()

    # Obtener o crear estado de conversación
    if sender not in conversations:
        conversations[sender] = {'step': 0}

    state = conversations[sender]

    step = state['step']

    # -----------------------------------------------------------------------
    # RESET GLOBAL: El Cliente Puede Empezar de Nuevo en Cualquier Momento.-
    # -----------------------------------------------------------------------
    if 'error' in text_lower:
        conversations[sender] = {'step': 0}
        send_message(sender,
                     "🔄 *Proceso Cancelado*. Cuando Quieras Empezar de Nuevo Escribí *'Turno'*...")
        return
    # -----------------------------------------------------------------------

    # Íconos Por Servicio.-
    service_icons = {
        'Color': '🎨',
        'Corte': '✂️',
        'Manicura': '💅',
        'Mechas': '🌟',
        'Peinado': '💇',
        'Permanente': '🌀'
    }

    # Flujo de Conversación.-
    if step == 0 and any(p in text_lower for p in ['cita', 'reserva', 'turno']):
        # Inicio - Obtener Staff con IDs Dinámicamente.-
        staff_data = get_staff_with_ids()

        # Emojis Numéricos para los IDs del Staff.-
        num_emojis = {'1': '1️⃣', '2': '2️⃣', '3': '3️⃣', '4': '4️⃣', '5': '5️⃣',
                      '6': '6️⃣', '7': '7️⃣', '8': '8️⃣', '9': '9️⃣'}

        # Generar Mensaje con IDStaff Dinámico desde Google Sheets.-
        staff_list = '\n'.join([
            f"{num_emojis.get(item['id'], item['id'] + '.')} {item['nombre']}"
            for item in staff_data
        ])

        # ✅ Uso de Variable Dinámica NOMBRE_EMPRESA ( MEMORY Ingeniería en Sistemas ).-
        send_message(sender,
                     f"¡Hola! 👋 Bienvenido a {NOMBRE_EMPRESA} Coiffeur's - ¿Con Qué Coiffeur Querés Tú Turno?...\n\n{staff_list}\n\nEscribí el Número del Coiffeur de Tú Preferencia.\n\n💡 *Tip:* Sí en Algún Momento Te Equivocás, Escribí *'Error'* para Empezar de Nuevo, Gracias.-")

        state['step'] = 1

    elif step == 1:
        # Selección de Coiffeur por IDStaff - Validación Dinámica.-
        staff_data = get_staff_with_ids()

        # Buscar el IDStaff que Coincida con lo que Escribió el Cliente.-
        coiffeur_selected = None
        for item in staff_data:
            if text.strip() == item['id']:
                coiffeur_selected = item['nombre']
                break

        if coiffeur_selected:
            state['coiffeur'] = coiffeur_selected
            send_message(sender, f"Perfecto, Elegiste a {coiffeur_selected}.\n\n¿Cuál és Tú Nombre y Apellido?:")
            state['step'] = 1.5
        else:
            # Mensaje de Error con Lista de IDs Disponibles.-
            staff_list = '\n'.join([f"  {item['id']} → {item['nombre']}" for item in staff_data])
            send_message(sender,
                         f"⚠️ Nó Entendí Tú Respuesta. Por Favor Escribí el Número del Coiffeur:\n\n{staff_list}")

    elif step == 1.5:
        # Captura del Nombre y Apellido del Cliente.-
        state['nombre'] = text.strip()
        state['telefono'] = sender

        # --- Obtener Servicios con IDs desde la Hoja del Negocio ---
        try:
            servicios_disponibles = obtener_servicios_negocio()
        except Exception as e:
            logger.error(f"ERROR: al Leer Servicios del Negocio: {e}")
            servicios_disponibles = [
                {'servicio': 'Corte', 'icono': '✂️', 'id': '1', 'costo': ''},
                {'servicio': 'Flequillo', 'icono': '💇', 'id': '2', 'costo': ''},
                {'servicio': 'Recorte Barba', 'icono': '🪒', 'id': '3', 'costo': ''}
            ]

        # Emojis Numéricos para los IDs de Servicios.-
        num_emojis = {'1': '1️⃣', '2': '2️⃣', '3': '3️⃣', '4': '4️⃣', '5': '5️⃣',
                      '6': '6️⃣', '7': '7️⃣', '8': '8️⃣', '9': '9️⃣', '10': '🔟',
                      '11': '1️⃣1️⃣', '12': '1️⃣2️⃣'}

        # Generar Lista de Servicios con IDServicio e Ícono.-
        lista_servicios = ""
        for item in servicios_disponibles:
            id_srv = item.get('id', '')
            icono = item.get('icono', '✂️')
            nombre = item.get('servicio', '')
            emoji = num_emojis.get(id_srv, f"{id_srv}.")
            lista_servicios += f"{emoji} {icono} {nombre}\n"

        send_message(
            sender,
            f"Gracias {state['nombre']}. ¿Qué Servicio Necesitás?...:\n\n{lista_servicios}\n"
            f"Escribí el Número del Servicio de Tú Preferencia...\n\n"
            f"💡 *Tip:* Sí Té Equivocás, Escribí *'Error'* para Empezar de Nuevo.-"
        )
        state['step'] = 2

    elif step == 2:
        # Selección de Servicio por IDServicio - Validación Dinámica.-
        # Leer Servicios Disponibles del Negocio ( Lista de dicts ).-
        servicios_data = obtener_servicios_negocio()

        if not servicios_data:
            send_message(sender,
                         "❌ ERROR: Nó Háy Servicios Definidos én él Negocio...\n"
                         "Por Favor Comunicáte con él Salón, Gracias...")
            return

        # Buscar el IDServicio que Coincida con lo que Escribió el Cliente.-
        servicio_elegido = None
        costo_elegido = ''

        for item in servicios_data:
            if text.strip() == item.get('id', ''):
                servicio_elegido = item.get('servicio', '')
                costo_elegido = item.get('costo', '')
                break

        # Sí el ID nó Coincide con Ninguno del Listado.-
        if servicio_elegido is None:
            num_emojis = {'1': '1️⃣', '2': '2️⃣', '3': '3️⃣', '4': '4️⃣', '5': '5️⃣',
                          '6': '6️⃣', '7': '7️⃣', '8': '8️⃣', '9': '9️⃣', '10': '🔟',
                          '11': '1️⃣1️⃣', '12': '1️⃣2️⃣'}
            lista_srv = '\n'.join([
                f"  {num_emojis.get(item.get('id', ''), item.get('id', '') + '.')} "
                f"{item.get('icono', '✂️')} {item.get('servicio', '')}"
                for item in servicios_data
            ])
            send_message(sender,
                         f"⚠️ {state['nombre']}, Nó Entendí Tú Respuesta. Por Favor Escribí él Número del Servicio:\n\n{lista_srv}")
            return

        # Servicio Válido Seleccionado - Guardar Nombre y Costo en el Estado.-
        state['servicio'] = servicio_elegido
        state['costo'] = costo_elegido

        send_message(sender,
                     f"Servicio : {state['servicio']} ✓\n\n"
                             f"Cliente/a: {state['nombre']} ✓\n\n"
                     "¿Qué Día Té Gustaría Venir?\n\n"
                     "Por Favor Escribí Lá Fecha én Formato: DD-MM-AAAA\n"
                     "Ej.: 15-10-2025")
        state['step'] = 3

    elif step == 3:
        # Selección de Fecha Elegida por el Cliente para el Turno.-
        try:
            # Parsear Fecha ( DD-MM-AAAA ).-
            from datetime import datetime, date
            fecha_obj = datetime.strptime(text, '%d-%m-%Y')

            # Validaciones de Fecha.-
            hoy = date.today()
            año_actual = hoy.year

            # Validar que la Fecha NO sea Anterior a Hoy.-
            if fecha_obj.date() < hoy:
                send_message(sender,
                             "❌ ERROR: Nó Podés Reservar Turnos en Fechas Pasadas,\n\nPor Favor Elegí una Fecha desde Hoy en Adelante, \n\nPor Favor Escribí La Fecha en Formato: DD-MM-AAAA\nEj.: 15-10-2025.-")
                return

            # Validar que el Año sea el Actual.-
            if fecha_obj.year != año_actual:
                send_message(sender,
                             f"❌ ERROR: Sólo Podés Reservar Turnos para el Año 📅 {año_actual},\n\nPor Favor Ingresá una Fecha Válida, \n\nPor Favor Escribí La Fecha en Formato: DD-MM-AAAA\nEj.: 15-10-2025.-")
                return

            # Validar que el Mes NO sea Anterior al Mes Actual (sí es el Mismo Año).-
            if fecha_obj.year == año_actual and fecha_obj.month < hoy.month:
                send_message(sender,
                             f"❌ ERROR: Nó Podés Reservar Turnos en Meses Anteriores,\n\nPor Favor Elegí una Fecha Desde el Mes Actual en Adelante, \n\nPor Favor Escribí La Fecha en Formato: DD-MM-AAAA\nEj.: 15-10-2025.-")
                return

            # Si Todo OK, Formatear y Continuar.-
            fecha_formatted = fecha_obj.strftime('%Y-%m-%d')
            state['fecha'] = fecha_formatted
            state['fecha_display'] = text

            # Fecha Larga para Grabar como Texto Completo
            dia_ing = fecha_obj.strftime('%A')
            mes_ing = fecha_obj.strftime('%B')

            dia_esp = DIAS[dia_ing]
            mes_esp = MESES[mes_ing]

            state['fecha_larga'] = f"{dia_esp}, {fecha_obj.day} de {mes_esp} de {fecha_obj.year}"
            state['fecha_dia_esp'] = dia_esp  # ← Guardar Día en Castellano para Usar en Steps Siguientes.-

            # --- Control de Días Nó Laborables o Feriados ---
            from sheets.sheet_service import es_feriado
            if es_feriado(fecha_formatted):
                send_message(sender,
                             f"⚠️ Lo Siento {state['nombre']}, El Salón Permanece Cerrado él {text} por Día Nó Laborable o Feriado,\n\n"
                                         "Por Favor Elegí Otra Fecha Disponible, Gracias...")
                return

            # Obtener Horarios Disponibles para la Fecha del Turno Elegida por el Cliente.-
            horarios = get_available_slots(state['coiffeur'], fecha_formatted)

            # Obtener Icono del Servicio Para Mostrar en el Mensaje (si existe).-
            icono_srv = SERVICE_ICONS.get(state['servicio'], '')

            if horarios:
                num_emojis = {1: '1️⃣', 2: '2️⃣', 3: '3️⃣', 4: '4️⃣', 5: '5️⃣', 6: '6️⃣', 7: '7️⃣',
                              8: '8️⃣', 9: '9️⃣', 10: '🔟', 11: '1️⃣1️⃣', 12: '1️⃣2️⃣', 13: '1️⃣3️⃣',
                              14: '1️⃣4️⃣', 15: '1️⃣5️⃣', 16: '1️⃣6️⃣', 17: '1️⃣7️⃣', 18: '1️⃣8️⃣'}
                state['horarios_map'] = {str(i + 1): h for i, h in enumerate(horarios)}
                horarios_text = '\n'.join([f"{num_emojis.get(i + 1, str(i + 1) + '.')} {h}"
                                           for i, h in enumerate(horarios)])
                send_message(sender,
                             f"Horarios Disponibles para: ..."
                             f"{horarios_text}\n\n"
                             f"⚠️ {state['nombre']}, Tenés 01 Minuto para Elegir y Confirmar Tú Reserva...\n\n"
                             "Escribí el Número del Horario que Preferís...")

                state['step'] = 4
            else:
                send_message(sender,
                             f"Lo Siento {state['nombre']}, Nó Hay Horarios Disponibles para: {state['coiffeur']} ({icono_srv} {state['servicio']}) el {dia_esp} {text}. ¿Querés Probar con Otra Fecha?...")
                state['step'] = 3

        except ValueError:
            send_message(sender,
                         "ERROR: Formato de Fecha Incorrecto, Por Favor usá: DD-MM-AAAA\nEj.: 15-10-2025")

    elif step == 4:
        # Selección del Horario por Número - Validación Dinámica.-
        horarios_map = state.get('horarios_map', {})

        # Buscar el Número Escrito por el Cliente en el Mapa de Horarios.-
        hora = horarios_map.get(text.strip())

        if not hora:
            # Regenerar Lista para Mostrar al Cliente.-
            num_emojis = {1: '1️⃣', 2: '2️⃣', 3: '3️⃣', 4: '4️⃣', 5: '5️⃣', 6: '6️⃣', 7: '7️⃣',
                          8: '8️⃣', 9: '9️⃣', 10: '🔟', 11: '1️⃣1️⃣', 12: '1️⃣2️⃣', 13: '1️⃣3️⃣',
                          14: '1️⃣4️⃣', 15: '1️⃣5️⃣', 16: '1️⃣6️⃣', 17: '1️⃣7️⃣', 18: '1️⃣8️⃣'}
            lista_horarios = '\n'.join([
                f"{num_emojis.get(int(k), k + '.')} {v}"
                for k, v in sorted(horarios_map.items(), key=lambda x: int(x[0]))
            ])
            send_message(sender,
                         f"⚠️ {state['nombre']}, Nó Entendí Tú Respuesta. Por Favor Escribí él Número del Horario:\n\n{lista_horarios}")
            return

        # -----------------------------------------------------------------------
        # BLOQUE PROTEGIDO: Errores de Red / SSL Nó Deben Silenciar al Bot.-
        # -----------------------------------------------------------------------
        try:
            disponible = check_availability(state['coiffeur'], state['fecha'], hora)

        except Exception as e:
            logger.error(f"ERROR: al Verificar Disponibilidad ( check_availability ): {type(e).__name__}: {e}")
            send_message(sender,
                         f"⚠️ {state['nombre']}, Hubo un Problema dé Conexión ál Verificar él Horario...\n\n"
                                     "Por Favor Intentá Nuevamente Escribiendo él Mismo Horario...")
            return

        if disponible:
            state['hora'] = hora

            # Crear Reserva Provisional del Turno elegido por el Cliente.-
            nombre = state.get('nombre', 'Cliente')
            telefono = state.get('telefono', sender)

            try:
                reservation_id = crear_reserva_provisional(
                    nombre, telefono, state['servicio'],
                    state['coiffeur'], state['fecha_larga'], hora,
                    costo=state.get('costo', '')
                )

            except Exception as e:
                logger.error(f"ERROR: al Crear Reserva Provisional: {type(e).__name__}: {e}")
                send_message(sender,
                             f"⚠️ {state['nombre']}, Hubo un Problema de Conexión al Generar Tú Reserva...\n\n"
                                         "Por Favor Intentá Nuevamente Escribiendo el Mismo Horario...")
                return

            state['reservation_id'] = reservation_id

            # Importar datetime Localmente.-
            from datetime import datetime as dt_now
            state['timestamp_reserva'] = dt_now.now(tz)

            # Obtener Icono Dinámico del Servicio desde Google Sheet.-
            icono_srv = SERVICE_ICONS.get(state['servicio'], '✂️')

            send_message(sender,
                         f"📋 *Reserva Temporal Creada:*\n\n"
                         f"👤 Cliente/a: {state['nombre']}\n"
                         f"👤 Coiffeur : {state['coiffeur']}\n"
                         f"📅 Fecha    : {state.get('fecha_dia_esp', '')} {state['fecha_display']}\n"
                         f"⏰ Hora     : {hora}\n"
                         f"{icono_srv} Servicio: {state['servicio']}\n\n"
                         f"⚠️ *IMPORTANTE:* Escribí 'CONFIRMAR' en los Próximos 60 Segundos ( 01 Minuto ), para Asegurar Tú Turno...")
            state['step'] = 5

        else:
            send_message(sender,
                         f"⚠️ Lo Siento {state['nombre']}, ese Horario Yá Fué Reservado...\n"
                                      "Por Favor Elegí Otro de la Lista...")

    elif step == 5:
        # ← ← ← ANTI-DUPLICADOS / REENVÍO AUTOMÁTICO DE WHATSAPP ← ← ←
        if state.get('confirmado') is True:
            return

        if 'reservation_id' not in state:
            return
        # ← ← ← FIN ANTI-DUPLICADOS ← ← ←

        # ✅ NUEVA VALIDACIÓN: Verificar si el tiempo ya expiró antes de procesar cualquier texto
        if 'timestamp_reserva' in state:
            from datetime import datetime as dt_now
            tiempo_transcurrido = (dt_now.now(tz) - state['timestamp_reserva']).total_seconds()

            if tiempo_transcurrido > RESERVA_SECONDS:
                try:
                    from sheets.sheet_service import read_sheet, update_row
                    data = read_sheet()
                    for i, row in enumerate(data, start=2):
                        if len(row) >= 13 and row[11] == state['reservation_id']:
                            row[6] = 'Expirada'
                            row[7] = 'FALSE'
                            update_row(i, row)
                            logger.info(f"Reserva {state['reservation_id']} Expirada Detectada en app.py")
                            break
                except Exception as e:
                    logger.error(f"ERROR: al Marcar Reserva como Expirada: {e}")

                send_message(sender,
                             f"⚠️ ⏰ Lo Siento: {state['nombre']}, Tú Reserva del Turno, Expiró ( Pasó Más De 01 Minuto ),\n\n"
                                          "Por Favor Comenzá de Nuevo Escribiendo 'Turno'...")

                conversations[sender] = {'step': 0}

                return

        # --- Procesar las palabras clave ---
        if 'confirmar' in text_lower:
            # Confirmar la Reserva en Google Sheets.-
            success = confirmar_reserva(state['reservation_id'])

            if success:
                state['confirmado'] = True
                icono_srv = SERVICE_ICONS.get(state['servicio'], '✂️')

                conversations[sender] = {'step': 0}

                send_message(sender,
                             f"✔ ¡ TURNO CONFIRMADO !...\n\n"
                             f"👤 Cliente/a : {state['nombre']}\n"
                             f"👤 Coiffeur  : {state['coiffeur']}\n"
                             f"📅 Fecha     : {state.get('fecha_dia_esp', '')} {state['fecha_display']}\n"
                             f"⏰ Hora      : {state['hora']}\n"
                             f"{icono_srv} Servicio: {state['servicio']}\n\n"
                             f"¡ Té Esperamos ! Si Necesitás Cancelar o Modificar Tú Turno, Contactános, Gracias...")
                return
            else:
                conversations[sender] = {'step': 0}

                send_message(sender,
                             f"⚠️ ⏰ Lo Siento: {state['nombre']}, Tú Reserva Expiró... Por Favor Comenzá de Nuevo Escribiendo 'Turno', Gracias...")
                return

        elif 'cancelar' in text_lower:
            if 'reservation_id' in state:
                try:
                    from sheets.sheet_service import read_sheet, update_row
                    data = read_sheet()
                    for i, row in enumerate(data, start=2):
                        if len(row) >= 13 and row[11] == state['reservation_id']:
                            row[6] = 'Cancelada'
                            row[7] = 'FALSE'
                            update_row(i, row)
                            break
                except Exception as e:
                    logger.error(f"ERROR: al Cancelar Reserva: {e}")

            send_message(sender, f"{state['nombre']}, Reserva Cancelada. Sí Querés Agendar Otro Turno, Escribí 'Turno'...")

            conversations[sender] = {'step': 0}

            return

        else:
            # Si llegó aquí, es porque NO expiró y NO escribió confirmar/cancelar
            send_message(sender,
                         f"⚠️ {state['nombre']}, Tenés una Reserva Pendiente!!!\n\n"
              "Por Favor, Respondé *'CONFIRMAR'* para Asegurar Tú Lugar o *'CANCELAR'*.\n"
              "¡Recordá qué Sólo Tenés 01 Minuto desde qué Elegiste él Horario!...")


# Procesa Respuestas de Mensajes Interactivos ( Listas, Botones ).-
def process_interactive_response(sender, selected_id):
    """Procesa Respuestas de Mensajes Interactivos (Listas, Botones)"""
    # Implementar Lógica Para Mensajes Interactivos Si Sé Usan.-
    pass


@app.route('/health', methods=['GET'])
# EndPoint de Health Check Para el Servidor.-
def health_check():
    """EndPoint de Health Check Para el Servidor"""
    return jsonify({"status": "healthy"}), 200


if __name__ == '__main__':
    # Obtención Del Puerto Desde él Entorno ( RailWay Asigna Uno Automáticamente ).-
    port = int(os.getenv('PORT', 5000))

    # ---------------------------------------------------------------------------------
    # INICIO DEL SCHEDULER ( MEMORY Ingeniería en Sistemas )
    # ---------------------------------------------------------------------------------
    # El Scheduler es VITAL: és él Encargado de Liberar Los Turnos Si el Cliente
    # No Escribe "CONFIRMAR" en 60 Segundos.-
    try:
        # Se Inicia el Scheduler Para Limpiar Reservas Expiradas Cada 30 Segundos.-
        iniciar_scheduler(interval_seconds=30)
        logger.info("⏰ Scheduler Sincronizado Correctamente.-")
    except Exception as e:
        logger.error(f"❌ ERROR al Iniciar Scheduler: {e}")

    # ---------------------------------------------------------------------------------
    # EJECUCIÓN DE FLASK ( MEMORY Ingeniería en Sistemas )
    # ---------------------------------------------------------------------------------
    # Obtenemos él Modo Dé Ejecución Desde Las Variables de Entorno.-
    SYSTEM_MODE = os.getenv("SYSTEM_MODE", "disabled").lower()

    # IMPORTANTE: Para RailWay y Meta en Modo Desarrollo Usamos él Bloque "else".-
    # Cuando Meta Valide la App y Pase a Producción, Cambiar Lá Variable Dé Entorno
    # SYSTEM_MODE a "production".-

    if SYSTEM_MODE == "production":
        # Bloque para Despliegue Final Absoluto ( App de Meta Activa ).-
        # En Producción Desactivamos el 'use_reloader' y 'debug' Para Evitar Qué él
        # Scheduler Sé Ejecute Dos Veces Por ERROR y Sé Pierdan los Imports.-
        app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
    else:
        # ✅ CONFIGURACIÓN ACTUAL ( Modo Demo / Debug ):
        # Mantenemos debug=True para compatibilidad con el modo Desarrollo de Meta,
        # pero forzamos use_reloader=False para evitar el error de "No module named".-
        app.run(host='0.0.0.0', port=port, debug=True, use_reloader=False)


