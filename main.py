import os
import json
import threading
import requests
import telebot
from flask import Flask, request

# ----------------------------------------------------
# 1. CONFIGURACIÓN Y VARIABLES DE ENTORNO
# ----------------------------------------------------
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GROQ_KEY = os.environ.get("GROQ_API_KEY", "").strip()
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY", "").strip()
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL", "")

bot = telebot.TeleBot(TELEGRAM_TOKEN) if TELEGRAM_TOKEN else None
app = Flask(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}

# ----------------------------------------------------
# 2. PROMPTS ESTRUCTURADOS
# ----------------------------------------------------
PROMPTS = {
    1: """Eres un analista táctico de fútbol. Analiza el partido indicado.
Escribe ÚNICAMENTE los puntos del 1 al 4 de forma clara y sin florituras:
1. Contexto y momento actual de ambos equipos.
2. Alineaciones probables y bajas confirmadas.
3. Análisis táctico del partido y propuesta de juego.
4. Historial reciente (H2H) y tendencias.""",

    2: """Eres un analista estadístico de fútbol. Con base en el partido indicado, redacta ÚNICAMENTE los puntos del 5 al 8:
5. Estadísticas clave (goles, posesión, tiros a puerta, córners).
6. Factores externos (clima, estadio, presión del público, árbitro).
7. Fortalezas y debilidades individuales/colectivas.
8. Mercados sugeridos de apuestas (Línea principal, Over/Under, Córners/Tarjetas).""",

    3: """Eres un experto en Value Bets y gestión de riesgo en apuestas deportivas. Redacta ÚNICAMENTE los puntos del 9 al 11:
9. Evaluación del valor en las cuotas (Value Bet).
10. Nivel de riesgo asignado a la predicción (Bajo/Medio/Alto).
11. Conclusión y pronóstico final recomendado."""
}

# ----------------------------------------------------
# 3. MOTORES DE IA RESILIENTES
# ----------------------------------------------------
def call_gemini(prompt_sistema, prompt_usuario):
    if not GEMINI_KEY:
        return None
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"
    payload = {
        "contents": [{"parts": [{"text": f"{prompt_sistema}\n\n[PARTIDO]: {prompt_usuario}"}]}]
    }
    try:
        r = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=12)
        if r.status_code == 200:
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]
        print(f"❌ Gemini Status: {r.status_code}")
    except Exception as e:
        print(f"❌ Gemini Excepción: {e}")
    return None

def call_groq(prompt_sistema, prompt_usuario):
    if not GROQ_KEY:
        return None
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {**HEADERS, "Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"}
    modelos = ["llama-3.3-70b-versatile", "llama3-8b-8192"]
    
    for mod in modelos:
        payload = {
            "model": mod,
            "messages": [
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": f"Partido: {prompt_usuario}"}
            ],
            "temperature": 0.4,
            "max_tokens": 1000
        }
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=12)
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"]
        except Exception:
            continue
    return None

def call_openrouter(prompt_sistema, prompt_usuario):
    if not OPENROUTER_KEY:
        return None
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        **HEADERS,
        "Authorization": f"Bearer {OPENROUTER_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "meta-llama/llama-3.3-70b-instruct:free",
        "messages": [
            {"role": "system", "content": prompt_sistema},
            {"role": "user", "content": f"Partido: {prompt_usuario}"}
        ]
    }
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=15)
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"❌ OpenRouter Excepción: {e}")
    return None

# ----------------------------------------------------
# 4. ENVIAR MENSAJE SEGURO A TELEGRAM
# ----------------------------------------------------
def enviar_telegram_seguro(chat_id, texto):
    """Intenta enviar con formato Markdown, si falla envía como texto plano para evitar caídas."""
    try:
        bot.send_message(chat_id, texto, parse_mode="Markdown")
    except Exception:
        try:
            bot.send_message(chat_id, texto)
        except Exception as e:
            print(f"❌ Error crítico enviando a Telegram: {e}")

# ----------------------------------------------------
# 5. GENERACIÓN ASINCRÓNICA
# ----------------------------------------------------
def obtener_bloque(num_bloque, prompt_sistema, partido):
    motores = [("Gemini", call_gemini), ("Groq", call_groq), ("OpenRouter", call_openrouter)]
    if num_bloque == 2:
        motores = [("Groq", call_groq), ("Gemini", call_gemini), ("OpenRouter", call_openrouter)]
    elif num_bloque == 3:
        motores = [("OpenRouter", call_openrouter), ("Gemini", call_gemini), ("Groq", call_groq)]

    for nombre, funcion in motores:
        print(f"⚡ Probando Bloque {num_bloque} con {nombre}...")
        res = funcion(prompt_sistema, partido)
        if res and len(res.strip()) > 40:
            print(f"✅ Bloque {num_bloque} generado con {nombre}")
            return res, nombre
    return None, "Ninguno"

def procesar_y_responder_async(chat_id, partido):
    titulos = {
        1: "📊 **PARTE 1: Contexto e Historial (Puntos 1-4)**",
        2: "📈 **PARTE 2: Estadísticas y Mercados (Puntos 5-8)**",
        3: "🎯 **PARTE 3: Pronóstico y Value Bet (Puntos 9-11)**"
    }

    exito = False
    for bloque in [1, 2, 3]:
        texto, motor = obtener_bloque(bloque, PROMPTS[bloque], partido)
        if texto:
            exito = True
            mensaje = f"{titulos[bloque]}\n_Motor: {motor}_\n\n{texto}"
            enviar_telegram_seguro(chat_id, mensaje)
        else:
            enviar_telegram_seguro(chat_id, f"⚠️ No se pudo generar la Parte {bloque}.")

    if not exito:
        enviar_telegram_seguro(chat_id, "⚠️ No fue posible conectar con los servidores de IA en este momento. Reintenta en unos instantes.")

# ----------------------------------------------------
# 6. MANEJADORES DE TELEGRAM
# ----------------------------------------------------
if bot:
    @bot.message_handler(commands=['start', 'help'])
    def cmd_start(message):
        enviar_telegram_seguro(
            message.chat.id,
            "👋 **¡Bot Deportivo Activo!**\n\nEscríbeme el nombre de un partido (ej: *Real Madrid vs Barcelona*) para iniciar el análisis."
        )

    @bot.message_handler(func=lambda m: True)
    def responder_consulta(message):
        texto_usuario = message.text.strip()
        if texto_usuario.lower() in ["hola", "buenas", "saludos", "hey"]:
            enviar_telegram_seguro(message.chat.id, "👋 ¡Hola! Escríbeme el nombre del partido que quieres analizar hoy.")
            return

        enviar_telegram_seguro(message.chat.id, f"🔎 *Iniciando análisis de {texto_usuario}... Te enviaré los reportes a continuación.*")
        bot.send_chat_action(message.chat.id, "typing")

        threading.Thread(target=procesar_y_responder_async, args=(message.chat.id, texto_usuario)).start()

# ----------------------------------------------------
# 7. SERVIDOR FLASK Y WEBHOOK
# ----------------------------------------------------
@app.route('/')
def home():
    return "Bot Deportivo Operativo."

@app.route(f'/{TELEGRAM_TOKEN}', methods=['POST'])
def receive_webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "OK", 200
    return "Invalid request", 403

if __name__ == "__main__":
    if bot and RENDER_EXTERNAL_URL:
        webhook_url = f"{RENDER_EXTERNAL_URL.strip('/')}/{TELEGRAM_TOKEN}"
        bot.remove_webhook()
        bot.set_webhook(url=webhook_url)
        print(f"🔗 [Webhook] Registrado en: {webhook_url}")

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
