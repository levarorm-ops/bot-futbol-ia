import os
import time
import json
import urllib.request
import urllib.error
import telebot

# ----------------------------------------------------
# 1. CONFIGURACIÓN Y VARIABLES DE ENTORNO
# ----------------------------------------------------
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY")
GROQ_KEY = os.environ.get("GROQ_API_KEY")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")

bot = telebot.TeleBot(TELEGRAM_TOKEN) if TELEGRAM_TOKEN else None

# ----------------------------------------------------
# 2. MOTOR PRINCIPAL DE IA (CASCADA DE PROVEEDORES)
# ----------------------------------------------------
PROMPT_SISTEMA = """
Eres un analista táctico y estadístico profesional de fútbol. Tu objetivo es entregar análisis profundos, detallados y fundamentados sin escatimar en texto ni omitir detalles clave.

Estructura tu análisis cubriendo obligatoriamente los siguientes 11 puntos:
1. Contexto y momento actual de ambos equipos.
2. Alineaciones probables y bajas confirmadas.
3. Análisis táctico del partido y propuesta de juego.
4. Historial reciente (H2H) y tendencias.
5. Estadísticas clave (goles, posesión, tiros a puerta, córners).
6. Factores externos (clima, estadio, presión del público, árbitro).
7. Fortalezas y debilidades individuales/colectivas.
8. Mercados sugeridos de apuestas (Línea principal, Over/Under, Córners/Tarjetas).
9. Evaluación del valor en las cuotas (Value Bet).
10. Nivel de riesgo asignado a la predicción (Bajo/Medio/Alto).
11. Conclusión y pronóstico final recomendado.

Proporciona explicaciones amplias, objetivas y fundamentadas.
"""

def consultar_openrouter(prompt):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "google/gemini-2.0-flash-001",
        "messages": [
            {"role": "system", "content": PROMPT_SISTEMA},
            {"role": "user", "content": prompt}
        ]
    }
    req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), headers=headers)
    with urllib.request.urlopen(req, timeout=45) as response:
        res = json.loads(response.read().decode("utf-8"))
        return res["choices"][0]["message"]["content"]

def consultar_groq(prompt):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": PROMPT_SISTEMA},
            {"role": "user", "content": prompt}
        ]
    }
    req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), headers=headers)
    with urllib.request.urlopen(req, timeout=45) as response:
        res = json.loads(response.read().decode("utf-8"))
        return res["choices"][0]["message"]["content"]

def consultar_gemini(prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"
    headers = {"Content-Type": "application/json"}
    data = {
        "contents": [
            {"role": "user", "parts": [{"text": f"{PROMPT_SISTEMA}\n\nConsulta del usuario: {prompt}"}]}
        ]
    }
    req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), headers=headers)
    with urllib.request.urlopen(req, timeout=45) as response:
        res = json.loads(response.read().decode("utf-8"))
        return res["candidates"][0]["content"]["parts"][0]["text"]

def generar_analisis_ia(prompt):
    if OPENROUTER_KEY:
        try:
            return consultar_openrouter(prompt)
        except Exception as e:
            print(f"[IA Engine] Error en OpenRouter: {e}. Intentando proveedor de respaldo...")

    if GROQ_KEY:
        try:
            return consultar_groq(prompt)
        except Exception as e:
            print(f"[IA Engine] Error en Groq: {e}. Intentando proveedor de respaldo...")

    if GEMINI_KEY:
        try:
            return consultar_gemini(prompt)
        except Exception as e:
            print(f"[IA Engine] Error en Gemini: {e}.")

    return "⚠️ Error: No se pudo generar el análisis. Todos los servicios de IA fallaron temporalmente."

# ----------------------------------------------------
# 3. ENVÍO INTELIGENTE (FRACCIONAMIENTO DE MENSAJES)
# ----------------------------------------------------
def enviar_mensaje_inteligente(chat_id, texto):
    MAX_LIMIT = 3800  # Límite seguro por debajo de los 4096 caracteres de Telegram
    
    if len(texto) <= MAX_LIMIT:
        try:
            bot.send_message(chat_id, texto, parse_mode="Markdown")
        except Exception:
            bot.send_message(chat_id, texto)
        return

    # Si supera el límite, fragmentamos respetando párrafos enteros o ideas
    parrafos = texto.split('\n')
    bloque_actual = ""

    for parrafo in parrafos:
        if len(parrafo) > MAX_LIMIT:
            palabras = parrafo.split(' ')
            for palabra in palabras:
                if len(bloque_actual) + len(palabra) + 1 > MAX_LIMIT:
                    try:
                        bot.send_message(chat_id, bloque_actual, parse_mode="Markdown")
                    except Exception:
                        bot.send_message(chat_id, bloque_actual)
                    bloque_actual = palabra + " "
                else:
                    bloque_actual += palabra + " "
        else:
            if len(bloque_actual) + len(parrafo) + 1 > MAX_LIMIT:
                try:
                    bot.send_message(chat_id, bloque_actual, parse_mode="Markdown")
                except Exception:
                    bot.send_message(chat_id, bloque_actual)
                bloque_actual = parrafo + "\n"
            else:
                bloque_actual += parrafo + "\n"

    if bloque_actual.strip():
        try:
            bot.send_message(chat_id, bloque_actual, parse_mode="Markdown")
        except Exception:
            bot.send_message(chat_id, bloque_actual)

# ----------------------------------------------------
# 4. MANEJADORES DE TELEGRAM
# ----------------------------------------------------
if bot:
    @bot.message_handler(commands=['start', 'help'])
    def cmd_start(message):
        msj = "👋 **¡Bienvenido al Bot de Análisis Deportivo!**\n\nEnvíame el partido o la consulta que deseas analizar y generaréc un informe completo estructurado en 11 puntos."
        bot.send_message(message.chat.id, msj, parse_mode="Markdown")

    @bot.message_handler(func=lambda m: True)
    def responder_consulta(message):
        bot.send_chat_action(message.chat.id, "typing")
        respuesta = generar_analisis_ia(message.text)
        enviar_mensaje_inteligente(message.chat.id, respuesta)

# ----------------------------------------------------
# 5. EJECUCIÓN DEL SERVIDOR
# ----------------------------------------------------
def iniciar_telegram_polling():
    if not bot:
        return
    time.sleep(2)
    while True:
        try:
            bot.remove_webhook()
            bot.infinity_polling(timeout=20, long_polling_timeout=10, skip_pending=True)
        except Exception as e:
            print(f"[Polling Error] Se detectó colisión o reconexión: {e}. Reintentando en 5s...")
            time.sleep(5)

if __name__ == "__main__":
    from flask import Flask
    import threading

    app = Flask(__name__)

    @app.route('/')
    def home():
        return "Bot Deportivo Activo y Ejecutándose."

    if bot:
        threading.Thread(target=iniciar_telegram_polling, daemon=True).start()

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
