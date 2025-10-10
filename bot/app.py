"""
Servidor Flask principal - Webhook de WhatsApp
Maneja la lógica conversacional y flujo de turnos
"""
import logging

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
from sheets.sheet_service import (
    get_available_slots, check_availability, 
    elegir_coiffeur
)
from sheets.scheduler_service import (
    crear_reserva_provisional, confirmar_reserva, 
    iniciar_scheduler
)
from bot.whatsapp_service import send_message, send_list_message

load_dotenv()

app = Flask(__name__)
VERIFY_TOKEN = os.getenv('WEBHOOK_VERIFY_TOKEN')

# Diccionario para mantener estado de conversaciones (en producción usar Redis/DB)
conversations = {}

@app.route('/webhook', methods=['GET'])
def verify_webhook():
    """Verificación del webhook por parte de Meta"""
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    
    if mode == 'subscribe' and token == VERIFY_TOKEN:
        return challenge, 200
    else:
        return 'Forbidden', 403


@app.route('/webhook', methods=['POST'])
def receive_message():
    """Recibe mensajes entrantes de WhatsApp"""
    try:
        data = request.get_json()
        
        if not data or 'entry' not in data:
            return 'OK', 200
        
        # Extraer mensaje
        entry = data['entry'][0]
        changes = entry.get('changes', [])
        
        if not changes:
            return 'OK', 200
        
        value = changes[0].get('value', {})
        messages = value.get('messages', [])
        
        if not messages:
            return 'OK', 200
        
        message = messages[0]
        sender = message['from']
        
        # Procesar diferentes tipos de mensaje
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


def process_text_message(sender, text):
    """Procesa mensajes de texto según el estado de la conversación"""
    text_lower = text.lower()
    
    # Obtener o crear estado de conversación
    if sender not in conversations:
        conversations[sender] = {'step': 0}
    
    state = conversations[sender]
    step = state['step']
    
    # Flujo de conversación
    if step == 0 or 'turno' in text_lower or 'hola' in text_lower:
        # Inicio
        #send_message(sender, "¡Hola! 👋 Bienvenido al Salón. ¿Con Quién Querés Tú Turno?\n\1️⃣ Walter\n2️⃣ María\n\nEscribí el Nombre del Coiffeur de Tú Preferencia.-")
        send_message(sender, "¡Hola! 👋 Bienvenido a Rouss Coiffeur's - ¿Con Quién Querés Tú Turno?...\n1️⃣ Walter\n2️⃣ María\n\nEscribí el Nombre del Coiffeur de Tú Preferencia.-")
        state['step'] = 1

    elif step == 1:
        # Selección de coiffeur
        if 'walter' in text_lower:
            state['coiffeur'] = 'Walter'
            send_message(sender, "Perfecto, Elegiste a Walter.\n\n¿Cuál és Tú Nombre?")
            state['step'] = 1.5
        elif 'maría' in text_lower or 'maria' in text_lower:
            state['coiffeur'] = 'María'
            send_message(sender, "Perfecto, Elegiste a María.\n\n¿Cuál és Tú Nombre?")
            state['step'] = 1.5
        else:
            send_message(sender, "Nó Entendí Tú Respuesta. Por Favor Escribí 'Walter' o 'María'...")

    elif step == 1.5:
        # Captura del nombre
        state['nombre'] = text.strip()
        state['telefono'] = sender
        send_message(sender, f"Gracias {state['nombre']}. ¿Qué Servicio Necesitás?\n\n✂️ Color\n🎨 Corte\n💇 Peinado")
        state['step'] = 2
    elif step == 2:
        # Selección de servicio
        if 'color' in text_lower:
            state['servicio'] = 'Color'
        elif 'corte' in text_lower:
            state['servicio'] = 'Corte'
        elif 'peinado' in text_lower:
            state['servicio'] = 'Peinado'
        else:
            send_message(sender, "Por Favor Elegí Uno de éstos Servicios: Color, Corte o Peinado...")
            return
        
        send_message(sender, f"Servicio: {state['servicio']} ✅\n\n¿Qué Día Té Gustaría Venir?\n\nPor Favor Escribí La Fecha en Formato: DD-MM-AAAA\nEj.: 15-10-2025")
        state['step'] = 3
        
    elif step == 3:
        # Selección de fecha
        try:
            # Parsear fecha (DD-MM-AAAA)
            from datetime import datetime
            fecha_obj = datetime.strptime(text, '%d-%m-%Y')
            fecha_formatted = fecha_obj.strftime('%Y-%m-%d')
            state['fecha'] = fecha_formatted
            state['fecha_display'] = text
            
            # Obtener horarios disponibles
            horarios = get_available_slots(state['coiffeur'], fecha_formatted)
            
            if horarios:
                horarios_text = '\n'.join([f"⏰ {h}" for h in horarios])
                send_message(sender, f"Horarios Disponibles para: {state['coiffeur']} el {text}:\n\n{horarios_text}\n\n⚠️ Tenés 1 Minuto para Elegir y Confirmar Tú Reserva.\n\nEscribí el Horario que Preferís ( Ej.: 11:00 )...")
                state['step'] = 4
            else:
                send_message(sender, f"Lo Siento, Nó Hay Horarios Disponibles para: {state['coiffeur']} ese Día. ¿Querés Probar con Otra Fecha?...")
                state['step'] = 3
                
        except ValueError:
            send_message(sender, "ERROR: Formato de Fecha Incorrecto. Por Favor usá: DD-MM-AAAA\nEj.: 15-10-2025")
            
    elif step == 4:
        # Selección de horario
        hora = text.strip()
        
        # Validar formato de hora
        if not hora.replace(':', '').isdigit() or len(hora) not in [4, 5]:
            send_message(sender, "ERROR: Por Favor Escribí la Hora en Formato HH:MM ( Ej.: 11:00)")
            return
        
        # Verificar disponibilidad
        if check_availability(state['coiffeur'], state['fecha'], hora):
            state['hora'] = hora
            
            # Crear reserva provisional
            nombre = state.get('nombre', 'Cliente')
            telefono = state.get('telefono', sender)
            reservation_id = crear_reserva_provisional(
                nombre, telefono, state['servicio'],
                state['coiffeur'], state['fecha'], hora
            )

            state['reservation_id'] = reservation_id
            
            send_message(sender, f"🔒 Reserva Temporal Creada:\n\n👤 Coiffeur: {state['coiffeur']}\n📅 Fecha: {state['fecha_display']}\n⏰ Hora: {hora}\n✂️ Servicio: {state['servicio']}\n\n⚠️ IMPORTANTE: Escribí 'CONFIRMAR' en los Próximos 60 Segundos para Asegurar Tú Turno...")
            state['step'] = 5
        else:
            send_message(sender, f"Lo Siento, ese Horario Yá Fue Reservado... Por Favor Elegí Otro de la Lista...")
            
    elif step == 5:
        # Confirmación final
        if 'confirmar' in text_lower:
            success = confirmar_reserva(state['reservation_id'])
            
            if success:
                send_message(sender, f"✅ ¡ TURNO CONFIRMADO !\n\n👤 Coiffeur: {state['coiffeur']}\n📅 Fecha: {state['fecha_display']}\n⏰ Hora: {state['hora']}\n✂️ Servicio: {state['servicio']}\n\n¡ Té Esperamos ! Si Necesitás Cancelar o Modificar Tú Turno, Contactános, Gracias...")
                # Reiniciar conversación
                conversations[sender] = {'step': 0}
            else:
                send_message(sender, "⏰ Lo Siento, Tú Reserva Expiró... Por Favor Comenzá de Nuevo Escribiendo 'turno'...")
                conversations[sender] = {'step': 0}
        elif 'cancelar' in text_lower:
            send_message(sender, "Reserva Cancelada. Sí Querés Agendar Otro Turno, Escribí 'turno'...")
            conversations[sender] = {'step': 0}
        else:
            send_message(sender, "Por Favor Escribí 'CONFIRMAR' Para Asegurar Tú Turno o 'CANCELAR' para Cancelar la Reserva...")


def process_interactive_response(sender, selected_id):
    """Procesa respuestas de mensajes interactivos (listas, botones)"""
    # Implementar lógica para mensajes interactivos si se usan
    pass


@app.route('/health', methods=['GET'])
def health_check():
    """Endpoint de health check para el servidor"""
    return jsonify({"status": "healthy"}), 200


if __name__ == '__main__':
    # Permite ejecutar directamente: python bot/app.py
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)


    