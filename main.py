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
# 2. MOTOR PRINCIPAL DE IA CON 11 PUNTOS Y DIAGNÓSTICO HTTP
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

def hacer_peticion_http(url, headers, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_detalles = e.read().decode("utf-8")
        print(f"\n🚨 [HTTP ERROR {e.code}] Respuesta del servidor de IA: {error_detalles}")
        raise e

# OpenRouter (Claude 3.5 Sonnet)
def consultar_openrouter(prompt, modelo="anthropic/claude-3.5-sonnet"):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://render.com",
        "X-Title": "Futbol-IA-Bot"
    }
    payload = {
        "model": modelo,
        "messages": [
            {"role": "system", "content": PROMPT_SISTEMA},
            {"role": "user", "content": prompt}
        ]
    }
    res = hacer_peticion_http(url, headers, payload)
    return res["choices"][0]["message"]["content"]

# Groq (Llama 3.3 70B Versatile)
def consultar_groq(prompt):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": PROMPT_SISTEMA},
            {"role": "user", "content": prompt}
        ]
    }
    res = hacer_peticion_http(url, headers, payload)
    return res["choices"][0]["message"]["content"]

# Google Gemini Directo
def consultar_gemini(prompt, modelo="gemini-1.5-flash"):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent?key={GEMINI_KEY}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": f"{PROMPT_SISTEMA}\n\nConsulta del usuario:\n{prompt}"}
                ]
            }
        ]
    }
    res = hacer_peticion_http(url, headers, payload)
    return res["candidates"][0]["content"]["parts"][0]["text"]

def generar_analisis_ia(prompt):
    print("\n================ [INICIANDO CONSULTA A LAS IAs] ================")
    
    # 1. OpenRouter - Claude 3.5 Sonnet
    if OPENROUTER_KEY:
        try:
            print("[IA Engine] Intentando con OpenRouter (Claude 3.5 Sonnet)...")
            return consultar_openrouter(prompt, "anthropic/claude-3.5-sonnet")
        except Exception as e:
            print(f"[IA Engine] ❌ OpenRouter falló: {e}")

    # 2. Groq - Llama 3.3 70B
    if GROQ_KEY:
        try:
            print("[IA Engine] Intentando con Groq (Llama 3.3 70B)...")
            return consultar_groq(prompt)
        except Exception as e:
            print(f"[IA Engine] ❌ Groq falló: {e}")

    # 3. Gemini Directo
    if GEMINI_KEY:
        try:
            print("[IA Engine] Intentando con Gemini Directo (1.5 Flash)...")
            return consultar_gemini(prompt, "gemini-1.5-flash")
        except Exception as e:
            print(f"[IA Engine] ❌ Gemini falló: {e}")

    print("================ [TODAS LAS IAs RECHAZARON LA PETICIÓN] ================")
    return "⚠️ Error crítico: Todas las APIs de IA rechazaron la consulta. Revisa los códigos de error detallados en los Logs de Render."

# ----------------------------------------------------
# 3. ENVÍO INTELIGENTE (FRACCIONAMIENTO DE MENSAJES)
# ----------------------------------------------------
def enviar_mensaje_inteligente(chat_id, texto):
    MAX_LIMIT = 3800  
    if len(texto) <= MAX_LIMIT:
        try:
            bot.send_message(chat_id, texto, parse_mode="Markdown")
        except Exception:
            bot.send_message(chat_id, texto)
        return

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
        msj = "👋 **¡Bienvenido al Bot de Análisis Deportivo!**\n\nEnvíame el partido o la consulta que deseas analizar y generaré un informe completo estructurado en 11 puntos."
        bot.send_message(message.chat.id, msj, parse_mode="Markdown")

    @bot.message_handler(func=lambda m: True)
    def responder_consulta(message):
        bot.send_chat_action(message.chat.id, "typing")
        respuesta = generar_analisis_ia(message.text)
        enviar_mensaje_inteligente(message.chat.id, respuesta)

# ----------------------------------------------------
# 5. EJECUCIÓN DEL SERVIDOR WEB FLASK
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
            print(f"[Polling Error] Reconectando: {e}...")
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
