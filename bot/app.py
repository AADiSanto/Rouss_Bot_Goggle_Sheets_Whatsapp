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
        logger.info(f"🔄 Caché de Staff Actualizado: {_STAFF_CACHE}")

    return _STAFF_CACHE


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/bot.log'),
        logging.StreamHandler()

    ]

)

logger = logging.getLogger(__name__)

from flask import Flask, request, jsonify
import os
from dotenv import load_dotenv
from datetime import datetime  # ← AGREGADO PARA TIMESTAMP

from sheets.sheet_service import (
    get_available_slots, check_availability,
    elegir_coiffeur, tz, validar_fecha_hora_turno  # ← AGREGADO validar_fecha_hora_turno
)

from sheets.scheduler_service import (
    crear_reserva_provisional, confirmar_reserva,
    iniciar_scheduler
)

from bot.whatsapp_service import send_message, send_list_message

load_dotenv()

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
    text_lower = text.lower()

    # Obtener o crear estado de conversación
    if sender not in conversations:
        conversations[sender] = {'step': 0}

    state = conversations[sender]
    step = state['step']

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
        # Inicio - Obtener Staff Dinámicamente.-
        staff_names = get_staff_names()

        # Generar Mensaje con Numeración Dinámica.-
        staff_list = '\n'.join([f"{i + 1}️⃣ {name}" for i, name in enumerate(staff_names)])

        send_message(sender,
                     f"¡Hola! 👋 Bienvenido a Melany Coiffeur's - ¿Con Qué Coiffeur Querés Tú Turno?...\n\n{staff_list}\n\nEscribí el Nombre del Coiffeur de Tú Preferencia.-")
                            #f"¡Hola! 👋 Bienvenido a Rouss Coiffeur's - ¿Con Qué Coiffeur Querés Tú Turno?...\n\n{staff_list}\n\nEscribí el Nombre del Coiffeur de Tú Preferencia.-")
        state['step'] = 1

    elif step == 1:
        # Selección de Coiffeur - Validación Dinámica.-
        staff_names = get_staff_names()

        # Normalizar Entrada del Usuario.-
        coiffeur_selected = None
        for name in staff_names:
            # Comparación Flexible (sin tildes, mayúsculas/minúsculas).-
            if name.lower().replace('í', 'i').replace('á', 'a') in text_lower.replace('í', 'i').replace('á', 'a'):
                coiffeur_selected = name
                break

        if coiffeur_selected:
            state['coiffeur'] = coiffeur_selected
            send_message(sender, f"Perfecto, Elegiste a {coiffeur_selected}.\n\n¿Cuál es Tú Nombre?:")
            state['step'] = 1.5
        else:
            # Mensaje de error dinámico
            staff_list = ', '.join([f"'{name}'" for name in staff_names])
            send_message(sender, f"No Entendí Tú Respuesta. Por Favor Escribí Uno de éstos Nombres: {staff_list}")

    elif step == 1.5:
        # Captura del Nombre del Cliente.-
        state['nombre'] = text.strip()
        state['telefono'] = sender

        # --- Obtener Servicios desde la Hoja del Negocio ---
        try:
            servicios_disponibles = obtener_servicios_negocio()  # ← Lista de dicts: {'servicio': 'Color', 'icono': '🎨'}
        except Exception as e:
            logger.error(f"ERROR: al Leer Servicios del Negocio: {e}")
            # Fallback de Seguridad (con iconos básicos)
            servicios_disponibles = [
                {'servicio': 'Color', 'icono': '🎨'},
                {'servicio': 'Corte', 'icono': '✂️'},
                {'servicio': 'Peinado', 'icono': '💇'}
            ]

        # Generar Lista de Servicios con Íconos.-
        lista_servicios = ""
        for item in servicios_disponibles:
            nombre_servicio = item.get('servicio', '')
            icono_servicio = item.get('icono', '✂️')
            lista_servicios += f"{icono_servicio} {nombre_servicio}\n"

        send_message(
            sender,
            f"Gracias {state['nombre']}. ¿Qué Servicio Necesitás?...:\n\n{lista_servicios}"
        )
        state['step'] = 2

    elif step == 2:
        # Selección de Servicio (Dinámico desde Google Sheets).-

        # Leer Servicios Disponibles del Negocio (Lista de dicts).-
        servicios_data = obtener_servicios_negocio()

        if not servicios_data:
            send_message(sender,
                         "⚠️ ERROR: No Hay Servicios Definidos en el Negocio...\n"
                         "Por Favor Comunicáte con el Salón, Gracias...")
            return

        # Normalizar Texto del Usuario para Comparación Flexible.-
        texto_norm = text_lower.replace('á','a').replace('é','e').replace('í','i') \
                               .replace('ó','o').replace('ú','u')

        servicio_elegido = None

        # Buscar Coincidencia contra la Lista de Servicios.-
        for item in servicios_data:
            nombre_srv = item.get('servicio', '')
            if not nombre_srv:
                continue

            srv_norm = nombre_srv.lower().replace('á','a').replace('é','e').replace('í','i') \
                                         .replace('ó','o').replace('ú','u')

            if srv_norm in texto_norm:
                servicio_elegido = nombre_srv   # ← Guardamos el Nombre Exacto Como Aparece en Sheets.-
                break

        # Sí el Servicio no Coincide con Ninguno del Listado.-
        if servicio_elegido is None:
            lista_srv = '\n'.join([f"• {item.get('servicio','')}" for item in servicios_data])
            send_message(sender,
                         "⚠️ No Entendí el Servicio Elegido...\n\n"
                         "Por Favor Elegí Uno de Estos Servicios:\n\n"
                         f"{lista_srv}")
            return

        # Servicio Válido Seleccionado.-
        state['servicio'] = servicio_elegido

        send_message(sender,
                     f"Servicio: {state['servicio']} ✓\n\n"
                     "¿Qué Día Té Gustaría Venir?\n\n"
                     "Por Favor Escribí La Fecha en Formato: DD-MM-AAAA\n"
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

            # --- Control de Días Nó Laborables o Feriados ---
            from sheets.sheet_service import es_feriado
            if es_feriado(fecha_formatted):
                send_message(sender,
                             f"⚠️ Lo Siento, El Salón Permanece Cerrado el {text} por Día Nó Laborable o Feriado,\n\nPor Favor Elegí Otra Fecha Disponible, Gracias...")
                return

            # Obtener Horarios Disponibles para la Fecha del Turno Elegida por el Cliente.-
            horarios = get_available_slots(state['coiffeur'], fecha_formatted)

            # Obtener Icono del Servicio Para Mostrar en el Mensaje (si existe).-
            icono_srv = SERVICE_ICONS.get(state['servicio'], '')

            if horarios:
                horarios_text = '\n'.join([f"⏰ {h}" for h in horarios])
                send_message(sender,
                             f"Horarios Disponibles para: {state['coiffeur']} ({icono_srv} {state['servicio']}) el {text}:\n\n"
                             f"{horarios_text}\n\n"
                             "⚠️ Tenés 03 Minutos para Elegir y Confirmar Tú Reserva...\n\n"
                             "Escribí el Horario que Preferís ( Ej.: 11:00 )...")
                state['step'] = 4
            else:
                send_message(sender,
                             f"Lo Siento, Nó Hay Horarios Disponibles para: {state['coiffeur']} ({icono_srv} {state['servicio']}) ese Día. ¿Querés Probar con Otra Fecha?...")
                state['step'] = 3

        except ValueError:
            send_message(sender,
                         "ERROR: Formato de Fecha Incorrecto, Por Favor usá: DD-MM-AAAA\nEj.: 15-10-2025")


    elif step == 4:
        # Selección del Horario para la Fecha del Turno Elegida por el Cliente.-
        hora = text.strip()

        # Validar Formato de la Hora Elegida.-
        if not hora.replace(':', '').isdigit() or len(hora) not in [4, 5]:
            send_message(sender, "ERROR: Por Favor Escribí la Hora en Formato HH:MM ( Ej.: 11:00 )")
            return

        # --- VALIDACIÓN COMPLETA DE FECHA Y HORA (Incluye Rango 09:00-18:30).-
        try:
            validar_fecha_hora_turno(state['fecha'], hora)
        except ValueError as e:
            send_message(sender, str(e))
            return

        # Verificar Disponibilidad de la Hora Elegida.-
        # Antes de Crear la Reserva Verificar Nuevamente Sí és Feriado.-
        from sheets.sheet_service import es_feriado

        if es_feriado(state['fecha']):
            send_message(sender,
                         f"⚠️ Lo Siento, El Salón Permanece Cerrado el {state['fecha_display']} por Día Nó Laborable o Feriado,\n\nPor Favor Elegí Otra Fecha Disponible...")
            return

        if check_availability(state['coiffeur'], state['fecha'], hora):
            state['hora'] = hora

            # Crear Reserva Provisional del Turno elegido por el Cliente.-
            nombre = state.get('nombre', 'Cliente')
            telefono = state.get('telefono', sender)

            reservation_id = crear_reserva_provisional(
                nombre, telefono, state['servicio'],
                state['coiffeur'], state['fecha_larga'], hora
            )

            state['reservation_id'] = reservation_id

            # Importar datetime Localmente.-
            from datetime import datetime as dt_now
            state['timestamp_reserva'] = dt_now.now(tz)

            # Obtener Icono Dinámico del Servicio desde Google Sheet.-
            icono_srv = SERVICE_ICONS.get(state['servicio'], '✂️')

            send_message(sender,
                         f"📋 *Reserva Temporal Creada:*\n\n"
                         f"👤 Coiffeur: {state['coiffeur']}\n"
                         f"📅 Fecha: {state['fecha_display']}\n"
                         f"⏰ Hora: {hora}\n"
                         f"{icono_srv} Servicio: {state['servicio']}\n\n"
                         f"⚠️ *IMPORTANTE:* Escribí 'CONFIRMAR' en los Próximos 60 Segundos para Asegurar Tú Turno...")
            state['step'] = 5

        else:
            send_message(sender,
                         f"⚠️ Lo Siento, ese Horario Yá Fue Reservado...\nPor Favor Elegí Otro de la Lista...")

    elif step == 5:
        # ← ← ← ANTI-DUPLICADOS / REENVÍO AUTOMÁTICO DE WHATSAPP ← ← ←
        # Si ya se confirmó anteriormente, NO volver a procesar.
        if state.get('confirmado') is True:
            return

        # Sí Por Alguna Razón Nó Existe ID, Cancelar Proceso Silenciosamente.-
        if 'reservation_id' not in state:
            return
        # ← ← ← FIN ANTI-DUPLICADOS ← ← ←

        # Confirmación Final del Turno Elegido por el Cliente.-
        if 'confirmar' in text_lower:
            from datetime import datetime as dt_now

            # Validar timeout de 60 segundos.-
            if 'timestamp_reserva' in state:
                tiempo_transcurrido = (dt_now.now(tz) - state['timestamp_reserva']).total_seconds()
                logger.info(f"(DEBUG) Tiempo Transcurrido: {tiempo_transcurrido:.1f}s")

                if tiempo_transcurrido > 60:
                    try:
                        from sheets.sheet_service import read_sheet, update_row
                        data = read_sheet()

                        for i, row in enumerate(data, start=2):
                            if len(row) >= 13 and row[11] == state['reservation_id']:
                                row[6] = 'Expirada'
                                row[7] = 'FALSE'
                                update_row(i, row)
                                logger.info(f"Reserva {state['reservation_id']} Expirada por Timeout de Usuario/a...")
                                break
                    except Exception as e:
                        logger.error(f"ERROR: al Marcar Reserva como Expirada: {e}")

                    send_message(sender,
                                 "⚠️ ⏰ Lo Siento, Tú Reserva del Turno, Expiró ( Pasaron Más De 03 Minutos ),\n\nPor Favor Comenzá de Nuevo Escribiendo 'Turno'...")
                    conversations[sender] = {'step': 0}
                    return

            # Confirmar la Reserva en Google Sheets.-
            success = confirmar_reserva(state['reservation_id'])

            if success:
                # ← ← ← BLOQUEAR DUPLICADOS PARA SIEMPRE ← ← ←
                state['confirmado'] = True

                icono_srv = SERVICE_ICONS.get(state['servicio'], '✂️')

                conversations[sender] = {'step': 0}
                send_message(sender,
                             f"✔ ¡ TURNO CONFIRMADO !\n\n"
                             f"👤 Coiffeur  : {state['coiffeur']}\n"
                             f"📅 Fecha     : {state['fecha_display']}\n"
                             f"⏰ Hora      : {state['hora']}\n"
                             f"{icono_srv} Servicio: {state['servicio']}\n\n"
                             f"¡ Té Esperamos ! Si Necesitás Cancelar o Modificar Tú Turno, Contactános, Gracias...")
                return

            else:
                conversations[sender] = {'step': 0}
                send_message(sender,
                             "⚠️ ⏰ Lo Siento, Tú Reserva Expiró... Por Favor Comenzá de Nuevo Escribiendo 'Turno'...")
                return

        elif 'cancelar' in text_lower:
            # Marcar Reserva Temporal Como Cancelada.-
            if 'reservation_id' in state:
                try:
                    from sheets.sheet_service import read_sheet, update_row
                    data = read_sheet()

                    for i, row in enumerate(data, start=2):
                        if len(row) >= 13 and row[11] == state['reservation_id']:
                            row[6] = 'Cancelada'
                            row[7] = 'FALSE'
                            update_row(i, row)
                            logger.info(f"Reserva {state['reservation_id']} Cancelada por Usuario/a...")
                            break
                except Exception as e:
                    logger.error(f"ERROR: al Cancelar Reserva: {e}")

            send_message(sender, "Reserva Cancelada. Sí Querés Agendar Otro Turno, Escribí 'Turno'...")
            conversations[sender] = {'step': 0}
            return

        else:
            send_message(sender,
                         "Por Favor Escribí 'CONFIRMAR' Para Asegurar Tú Turno o 'CANCELAR' para Cancelar la Reserva...")


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
    # Permite Ejecutar Directamente el Módulo Python: python bot/app.py
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
