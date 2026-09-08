import os
import json
import urllib.parse
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
# 2. PROMPT DE LOS 11 PUNTOS (SUBDIVIDIDO)
# ----------------------------------------------------
PROMPTS = {
    1: """Eres un analista táctico de fútbol. Analiza el partido con los datos provistos.
Escribe ÚNICAMENTE los puntos del 1 al 4 de forma clara y profesional:
1. Contexto y momento actual de ambos equipos.
2. Alineaciones probables y bajas confirmadas.
3. Análisis táctico del partido y propuesta de juego.
4. Historial reciente (H2H) y tendencias.""",

    2: """Eres un analista estadístico de fútbol. Con base en el partido, redacta ÚNICAMENTE los puntos del 5 al 8:
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
# 3. SCRAPER LIGERO Y SEGURO (NATIVE HTTP)
# ----------------------------------------------------
def buscar_informacion_partido(partido):
    print(f"🔍 [SCRAPER] Buscando noticias para: '{partido}'")
    query = f"{partido} alineaciones bajas noticias futbol"
    contexto = ""
    try:
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        resp = requests.get(url, headers=HEADERS, timeout=8)
        if resp.status_code == 200 and "result__snippet" in resp.text:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, 'html.parser')
            snippets = soup.find_all('a', class_='result__snippet')
            for s in snippets[:4]:
                contexto += f"- {s.get_text().strip()}\n"
            print("✅ [SCRAPER] Noticias obtenidas correctamente.")
        else:
            print("⚠️ [SCRAPER] Sin resultados directos. Se usará conocimiento general.")
    except Exception as e:
        print(f"⚠️ [SCRAPER WARNING] Fallo menor en búsqueda web ({e}). Continuando con base de datos de IA...")
    
    return contexto if contexto else "No hay noticias recientes de última hora. Procesa con tu base de datos previa."

# ----------------------------------------------------
# 4. MOTORES ATÓMICOS DE IA
# ----------------------------------------------------
def call_gemini(prompt_sistema, prompt_usuario):
    if not GEMINI_KEY:
        return None
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"
    payload = {
        "contents": [{"parts": [{"text": f"{prompt_sistema}\n\n[DATOS PARTIDO]:\n{prompt_usuario}"}]}]
    }
    try:
        r = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=20)
        if r.status_code == 200:
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]
        print(f"❌ Gemini Error {r.status_code}: {r.text[:100]}")
    except Exception as e:
        print(f"❌ Gemini Exception: {e}")
    return None

def call_groq(prompt_sistema, prompt_usuario):
    if not GROQ_KEY:
        return None
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {**HEADERS, "Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [
            {"role": "system", "content": prompt_sistema},
            {"role": "user", "content": prompt_usuario}
        ],
        "temperature": 0.5,
        "max_tokens": 1000
    }
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=20)
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"]
        print(f"❌ Groq Error {r.status_code}: {r.text[:100]}")
    except Exception as e:
        print(f"❌ Groq Exception: {e}")
    return None

def call_openrouter(prompt_sistema, prompt_usuario):
    if not OPENROUTER_KEY:
        return None
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        **HEADERS,
        "Authorization": f"Bearer {OPENROUTER_KEY}",
        "HTTP-Referer": "https://render.com",
        "X-Title": "SportsBot",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "meta-llama/llama-3-8b-instruct:free",
        "messages": [
            {"role": "system", "content": prompt_sistema},
            {"role": "user", "content": prompt_usuario}
        ]
    }
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=20)
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"]
        print(f"❌ OpenRouter Error {r.status_code}: {r.text[:100]}")
    except Exception as e:
        print(f"❌ OpenRouter Exception: {e}")
    return None

# ----------------------------------------------------
# 5. ORQUESTADOR RESILIENTE (CADA BLOQUE TIENE 3 VIDAS)
# ----------------------------------------------------
def obtener_bloque_con_respaldo(num_bloque, prompt_sistema, prompt_usuario):
    # Asignación de motores prioritarios según el bloque
    if num_bloque == 1:
        motores = [("Gemini", call_gemini), ("Groq", call_groq), ("OpenRouter", call_openrouter)]
    elif num_bloque == 2:
        motores = [("Groq", call_groq), ("Gemini", call_gemini), ("OpenRouter", call_openrouter)]
    else:
        motores = [("OpenRouter", call_openrouter), ("Gemini", call_gemini), ("Groq", call_groq)]

    for nombre_motor, funcion_motor in motores:
        res = funcion_motor(prompt_sistema, prompt_usuario)
        if res and len(res.strip()) > 50:
            print(f"✅ Bloque {num_bloque} generado exitosamente vía {nombre_motor}")
            return res, nombre_motor
        print(f"⚠️ {nombre_motor} falló para el Bloque {num_bloque}. Reintentando con siguiente motor...")

    return None, "Ninguno"

def generar_analisis_completo(partido):
    datos_web = buscar_informacion_partido(partido)
    prompt_usuario = f"Partido a analizar: {partido}\n\n[CONTEXTO WEB]:\n{datos_web}"

    partes = {}
    motores_usados = {}

    for bloque in [1, 2, 3]:
        print(f"\n⚡ Procesando Bloque {bloque}...")
        texto, motor = obtener_bloque_con_respaldo(bloque, PROMPTS[bloque], prompt_usuario)
        partes[bloque] = texto
        motores_usados[bloque] = motor

    return partes, motores_usados

# ----------------------------------------------------
# 6. MANEJADORES DE TELEGRAM
# ----------------------------------------------------
if bot:
    @bot.message_handler(commands=['start', 'help'])
    def cmd_start(message):
        bot.send_message(
            message.chat.id,
            "👋 **¡Bot Deportivo Profesional Activo!**\n\nEnvíame cualquier partido (ej: *Lille vs Betis*) y generaré el informe táctico de 11 puntos.",
            parse_mode="Markdown"
        )

    @bot.message_handler(func=lambda m: True)
    def responder_consulta(message):
        texto_usuario = message.text.strip()
        if texto_usuario.lower() in ["hola", "buenas", "saludos", "hey"]:
            bot.send_message(message.chat.id, "👋 ¡Hola! Escríbeme el nombre del partido que quieres analizar hoy.")
            return

        bot.send_message(message.chat.id, f"🔎 *Analizando {texto_usuario} en tiempo real...*", parse_mode="Markdown")
        bot.send_chat_action(message.chat.id, "typing")

        partes, motores = generar_analisis_completo(texto_usuario)

        # Si al menos un bloque respondió, se lo mostramos al usuario
        al_menos_uno = False

        if partes[1]:
            al_menos_uno = True
            bot.send_message(message.chat.id, f"📊 **PARTE 1: Contexto e Historial (Puntos 1-4)**\n_Motor: {motores[1]}_\n\n{partes[1]}", parse_mode="Markdown")

        if partes[2]:
            al_menos_uno = True
            bot.send_message(message.chat.id, f"📈 **PARTE 2: Estadísticas y Mercados (Puntos 5-8)**\n_Motor: {motores[2]}_\n\n{partes[2]}", parse_mode="Markdown")

        if partes[3]:
            al_menos_uno = True
            bot.send_message(message.chat.id, f"🎯 **PARTE 3: Pronóstico y Value Bet (Puntos 9-11)**\n_Motor: {motores[3]}_\n\n{partes[3]}", parse_mode="Markdown")

        if not al_menos_uno:
            bot.send_message(
                message.chat.id, 
                "⚠️ Todas las APIs de IA rechazaron las peticiones en este momento. Revisa el log de inicio en Render para validar las credenciales."
            )

# ----------------------------------------------------
# 7. SERVIDOR FLASK, WEBHOOK Y DIAGNÓSTICO AL ARRANCAR
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
    print("\n==================================================")
    print("🛠️  DIAGNÓSTICO AUTOMÁTICO DE CREDENCIALES EN RENDER")
    print(f"• Telegram Token Presente: {bool(TELEGRAM_TOKEN)}")
    print(f"• Gemini Key Presente: {bool(GEMINI_KEY)} (Longitud: {len(GEMINI_KEY)})")
    print(f"• Groq Key Presente: {bool(GROQ_KEY)} (Longitud: {len(GROQ_KEY)})")
    print(f"• OpenRouter Key Presente: {bool(OPENROUTER_KEY)} (Longitud: {len(OPENROUTER_KEY)})")
    print("==================================================\n")

    if bot and RENDER_EXTERNAL_URL:
        webhook_url = f"{RENDER_EXTERNAL_URL.strip('/')}/{TELEGRAM_TOKEN}"
        bot.remove_webhook()
        bot.set_webhook(url=webhook_url)
        print(f"🔗 [Webhook] Registrado en: {webhook_url}")

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
