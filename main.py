import os
import time
import requests
from flask import Flask, request, jsonify
from telebot import TeleBot
from groq import Groq

# ----------------------------------------------------
# 1. INICIALIZACIÓN DE VARIABLES Y CONFIGURACIÓN
# ----------------------------------------------------
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
GROQ_KEY = os.environ.get("GROQ_API_KEY")
OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY")

bot = TeleBot(TELEGRAM_TOKEN) if TELEGRAM_TOKEN else None
groq_client = Groq(api_key=GROQ_KEY) if GROQ_KEY else None

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot Fútbol IA activo y operativo 24/7.", 200

# ----------------------------------------------------
# 2. PROVEEDORES DE IA (HTTP DIRECTO + CASCADA NATIVA)
# ----------------------------------------------------

def consultar_openrouter(prompt):
    """Consulta a OpenRouter usando enrutamiento automático de modelos gratuitos."""
    if not OPENROUTER_KEY:
        raise Exception("OPENROUTER_API_KEY no configurada.")
    
    # Lista de modelos gratuitos globales (incluye autoswitch y modelos chinos/internacionales)
    modelos = [
        "openrouter/auto",
        "deepseek/deepseek-chat:free",
        "qwen/qwen-2.5-72b-instruct:free",
        "meta-llama/llama-3.3-70b-instruct:free",
        "google/gemini-2.0-flash-exp:free"
    ]
    
    headers = {
        "Authorization": f"Bearer {OPENROUTER_KEY.strip()}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://render.com",
        "X-Title": "Telegram Sports Bot"
    }
    
    for mod in modelos:
        try:
            payload = {
                "model": mod,
                "messages": [
                    {"role": "system", "content": "Eres un analista experto en deportes, pronósticos de fútbol y apuestas estadísticas."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7
            }
            res = requests.post("https://openrouter.ai/api/v1/chat/completions", json=payload, headers=headers, timeout=15)
            if res.status_code == 200:
                data = res.json()
                if 'choices' in data and len(data['choices']) > 0:
                    return data['choices'][0]['message']['content']
            else:
                print(f"[OpenRouter Debug] Modelo {mod} devolvió código status: {res.status_code} - {res.text}")
        except Exception as e:
            print(f"[OpenRouter Error] {mod}: {e}")
            continue
            
    raise Exception("Todos los modelos de OpenRouter fallaron.")

def consultar_groq(prompt):
    """Consulta directa a Groq Cloud."""
    if not groq_client:
        raise Exception("Groq no configurado.")
    
    modelos = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"]
    for mod in modelos:
        try:
            res = groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "Eres un analista deportivo y experto en estadísticas de fútbol."},
                    {"role": "user", "content": prompt}
                ],
                model=mod,
                temperature=0.7,
            )
            return res.choices[0].message.content
        except Exception as e:
            print(f"[Groq Error] Modelo {mod}: {e}")
            continue
    raise Exception("Groq totalmente saturado.")

def consultar_gemini_http(prompt):
    """Consulta nativa REST a la API de Google Gemini (sin librerías intermedias)."""
    if not GEMINI_KEY:
        raise Exception("GEMINI_API_KEY no configurada.")
    
    # Modelos activos en la API REST v1beta
    modelos = ["gemini-1.5-flash", "gemini-1.5-pro"]
    
    for mod in modelos:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{mod}:generateContent?key={GEMINI_KEY.strip()}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }]
        }
        try:
            res = requests.post(url, json=payload, headers=headers, timeout=15)
            if res.status_code == 200:
                data = res.json()
                return data['candidates'][0]['content']['parts'][0]['text']
            else:
                print(f"[Gemini HTTP Debug] {mod} Error {res.status_code}: {res.text}")
        except Exception as e:
            print(f"[Gemini HTTP Error] {mod}: {e}")
            continue
            
    raise Exception("Gemini REST falló.")

# ----------------------------------------------------
# 3. MOTOR DE CASCADA (FALLBACK MULTI-IA)
# ----------------------------------------------------
def obtener_respuesta_ia(prompt):
    # Intentar con OpenRouter (DeepSeek / Qwen / Llama 3.3 / Gemini via OpenRouter)
    try:
        return consultar_openrouter(prompt)
    except Exception as e:
        print(f"-> Fallback 1 (OpenRouter) falló: {e}")

    # Intentar con Groq
    try:
        return consultar_groq(prompt)
    except Exception as e:
        print(f"-> Fallback 2 (Groq) falló: {e}")

    # Intentar con Google Gemini REST
    try:
        return consultar_gemini_http(prompt)
    except Exception as e:
        print(f"-> Fallback 3 (Gemini REST) falló: {e}")

    return "⚠️ El servicio está experimentando alta demanda en todos los proveedores de IA. Por favor, reintenta tu mensaje en 10 segundos."

# ----------------------------------------------------
# 4. MANEJADORES DE TELEGRAM Y FLASK
# ----------------------------------------------------
if bot:
    @bot.message_handler(commands=['start', 'help'])
    def send_welcome(message):
        bot.reply_to(message, "¡Hola! Soy tu asistente de fútbol, estadísticas y apuestas. Hazme cualquier consulta sobre partidos o análisis.")

    @bot.message_handler(func=lambda message: True)
    def responder_usuario(message):
        bot.send_chat_action(message.chat.id, 'typing')
        respuesta = obtener_respuesta_ia(message.text)
        bot.reply_to(message, respuesta)

if __name__ == "__main__":
    import threading
    
    if bot:
        try:
            bot.remove_webhook()
        except Exception as e:
            print(f"Aviso webhook: {e}")
            
        threading.Thread(
            target=lambda: bot.infinity_polling(timeout=10, long_polling_timeout=5), 
            daemon=True
        ).start()
    
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
