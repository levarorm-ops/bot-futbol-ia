import os
import time
import requests
from flask import Flask, request, jsonify
from telebot import TeleBot
import google.generativeai as genai
from groq import Groq

# ----------------------------------------------------
# 1. INICIALIZACIÓN DE VARIABLES Y CLIENTES
# ----------------------------------------------------
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
GROQ_KEY = os.environ.get("GROQ_API_KEY")

bot = TeleBot(TELEGRAM_TOKEN) if TELEGRAM_TOKEN else None

# Configuración Gemini
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)

# Configuración Groq
groq_client = Groq(api_key=GROQ_KEY) if GROQ_KEY else None

# Configuración Servidor Web Flask (para el Keep-Alive de Render/UptimeRobot)
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot Fútbol IA está activo 24/7.", 200

# ----------------------------------------------------
# 2. LÓGICA DE CONSULTA A IA CON REINTENTOS Y FALLBACK
# ----------------------------------------------------
def consultar_groq(prompt):
    """Consulta a Groq con reintentos en modelos de alta velocidad."""
    if not groq_client:
        raise Exception("Groq no está configurado.")
    
    # Lista de modelos Groq ordenados por velocidad y disponibilidad
    modelos_groq = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"]
    
    for modelo in modelos_groq:
        for intento in range(2): # 2 reintentos por modelo
            try:
                chat_completion = groq_client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model=modelo,
                    temperature=0.7,
                )
                return chat_completion.choices[0].message.content
            except Exception as e:
                time.sleep(1.5 * (intento + 1)) # Espera antes de reintentar
                continue
    raise Exception("Groq totalmente saturado.")

def consultar_gemini(prompt):
    """Consulta a Gemini con modelo ultrarrápido y reintentos."""
    if not GEMINI_KEY:
        raise Exception("Gemini no está configurado.")
    
    # Usamos gemini-2.5-flash / gemini-1.5-flash por su alta tolerancia a tráfico
    modelos_gemini = ['gemini-2.5-flash', 'gemini-1.5-flash']
    
    for mod in modelos_gemini:
        for intento in range(2):
            try:
                model = genai.GenerativeModel(mod)
                response = model.generate_content(prompt)
                return response.text
            except Exception as e:
                time.sleep(1.5 * (intento + 1))
                continue
    raise Exception("Gemini totalmente saturado.")

def obtener_respuesta_ia(prompt):
    """
    Sistema Multi-IA con Fallback:
    Intenta con Groq primero. Si falla o está ocupado, conmuta automáticamente a Gemini.
    """
    # Intentar con Groq
    try:
        return consultar_groq(prompt)
    except Exception as e_groq:
        print(f"[Aviso] Groq falló o está ocupado. Cambiando a Gemini... Error: {e_groq}")
        
    # Fallback: Intentar con Gemini
    try:
        return consultar_gemini(prompt)
    except Exception as e_gemini:
        print(f"[Aviso] Gemini también falló: {e_gemini}")
        
    return "⚠️ En este momento los servidores de IA reciben alto tráfico. Por favor intenta enviarme tu mensaje de nuevo en 10 segundos."

# ----------------------------------------------------
# 3. MANEJADORES DE TELEGRAM
# ----------------------------------------------------
if bot:
    @bot.message_handler(commands=['start', 'help'])
    def send_welcome(message):
        bot.reply_to(message, "¡Hola! Soy tu bot asistente de apuestas y fútbol con IA. Envíame tu consulta sobre partidos, estadísticas o pronósticos.")

    @bot.message_handler(func=lambda message: True)
    def responder_usuario(message):
        bot.send_chat_action(message.chat.id, 'typing')
        respuesta = obtener_respuesta_ia(message.text)
        bot.reply_to(message, respuesta)

    # Configuración de Webhook / Polling según entorno Render
    @app.route('/' + TELEGRAM_TOKEN, methods=['POST'])
    def getMessage():
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "!", 200

# ----------------------------------------------------
# 4. ARRANCAR EL SERVIDOR Y EL BOT
# ----------------------------------------------------
if __name__ == "__main__":
    import threading
    
    # Iniciar polling de Telegram en un hilo secundario si no hay Webhook activo
    if bot:
        bot.remove_webhook()
        threading.Thread(target=lambda: bot.infinity_polling(timeout=10, long_polling_timeout=5), daemon=True).start()
    
    # Iniciar servidor Flask en el puerto que asigna Render
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
