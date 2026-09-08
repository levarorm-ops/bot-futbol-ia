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
# 2. PROMPTS SUBDIVIDIDOS (11 PUNTOS TÁCTICOS)
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
# 3. SCRAPER RESILIENTE (NATIVE HTTP)
# ----------------------------------------------------
def buscar_informacion_partido(partido):
    print(f"🔍 [SCRAPER] Buscando noticias para: '{partido}'")
    query = f"{partido} alineaciones bajas noticias futbol"
    contexto = ""
    try:
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        resp = requests.get(url, headers=HEADERS, timeout=5)
        if resp.status_code == 200 and "result__snippet" in resp.text:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, 'html.parser')
            snippets = soup.find_all('a', class_='result__snippet')
            for s in snippets[:4]:
                contexto += f"- {s.get_text().strip()}\n"
            print("✅ [SCRAPER] Noticias obtenidas correctamente.")
        else:
            print("⚠️ [SCRAPER] Sin resultados directos. Se usará conocimiento previo de IA.")
    except Exception as e:
        print(f"⚠️ [SCRAPER WARNING] Búsqueda omitida ({e}). Usando base de datos interna...")
    
    return contexto if contexto else "Procesa con la información general de tu base de datos."

# ----------------------------------------------------
# 4. MOTORES DE IA CON BÚSQUEDA DINÁMICA DE MODELOS GRATIS
# ----------------------------------------------------

def call_gemini(prompt_sistema, prompt_usuario):
    """Utiliza el endpoint oficial v1 de Google Gemini con la capa gratuita."""
    if not GEMINI_KEY:
        return None
    
    # Endpoint v1 oficial (más estable que v1beta)
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"
    payload = {
        "contents": [{"parts": [{"text": f"{prompt_sistema}\n\n[DATOS PARTIDO]:\n{prompt_usuario}"}]}]
    }
    try:
        r = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=20)
        if r.status_code == 200:
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]
        print(f"❌ Gemini Error {r.status_code}: {r.text[:120]}")
    except Exception as e:
        print(f"❌ Gemini Exception: {e}")
    return None

def call_groq(prompt_sistema, prompt_usuario):
    """Consulta Groq usando los modelos activos en su tier gratuito."""
    if not GROQ_KEY:
        return None
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {**HEADERS, "Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"}
    
    # Probamos de forma secuencial modelos del Free Tier oficial de Groq
    modelos_groq = ["llama-3.3-70b-versatile", "llama3-70b-8192", "mixtral-8x7b-32768"]
    
    for modelo in modelos_groq:
        payload = {
            "model": modelo,
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
        except Exception:
            continue
    print("❌ Groq: Ningún modelo gratuito respondió correctamente.")
    return None

def obtener_modelo_gratis_openrouter():
    """Descubre dinámicamente qué modelos 100% GRATUITOS están disponibles en OpenRouter hoy."""
    try:
        r = requests.get("https://openrouter.ai/api/v1/models", timeout=5)
        if r.status_code == 200:
            data = r.json().get("data", [])
            # Filtrar solo modelos que contengan ':free' y tengan costo 0
            modelos_free = [
                m["id"] for m in data 
                if m["id"].endswith(":free") or 
                (float(m.get("pricing", {}).get("prompt", "1")) == 0 and float(m.get("pricing", {}).get("completion", "1")) == 0)
            ]
            if modelos_free:
                print(f"💡 [OpenRouter] Modelos gratuitos detectados activos: {modelos_free[:3]}")
                return modelos_free[0] # Retorna el primero completamente gratis
    except Exception as e:
        print(f"⚠️ No se pudo obtener la lista dinámica de OpenRouter: {e}")
    
    # Fallback predeterminado por si falla la lista
    return "google/gemini-2.0-flash-lite-preview-02-05:free"

def call_openrouter(prompt_sistema, prompt_usuario):
    """Utiliza el modelo gratis autodetectado para evitar errores 404/402."""
    if not OPENROUTER_KEY:
        return None
    
    modelo_gratis = obtener_modelo_gratis_openrouter()
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        **HEADERS,
        "Authorization": f"Bearer {OPENROUTER_KEY}",
        "HTTP-Referer": "https://render.com",
        "X-Title": "SportsBot",
        "Content-Type": "application/json"
    }
    payload = {
        "model": modelo_gratis,
        "messages": [
            {"role": "system", "content": prompt_sistema},
            {"role": "user", "content": prompt_usuario}
        ]
    }
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=20)
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"]
        print(f"❌ OpenRouter Error {r.status_code} ({modelo_gratis}): {r.text[:120]}")
    except Exception as e:
        print(f"❌ OpenRouter Exception: {e}")
    return None

# ----------------------------------------------------
# 5. ORQUESTADOR Y RESPALDO CRUZADO
# ----------------------------------------------------
def obtener_bloque_con_respaldo(num_bloque, prompt_sistema, prompt_usuario):
    # Asignación de prioridad rotativa entre proveedores
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
        print(f"⚠️ {nombre_motor} falló para el Bloque {num_bloque}. Probando siguiente proveedor...")

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
            "👋 **¡Bot Deportivo Gratuito Activo!**\n\nEnvíame cualquier partido (ej: *Real Madrid vs Barcelona*) y generaré el informe táctico de 11 puntos.",
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
                "⚠️ Los proveedores gratuitos están temporalmente saturados. Por favor intenta en un par de minutos."
            )

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
    print("\n==================================================")
    print("🛠️ DIAGNÓSTICO DE CREDENCIALES")
    print(f"• Telegram Token Presente: {bool(TELEGRAM_TOKEN)}")
    print(f"• Gemini Key Presente: {bool(GEMINI_KEY)}")
    print(f"• Groq Key Presente: {bool(GROQ_KEY)}")
    print(f"• OpenRouter Key Presente: {bool(OPENROUTER_KEY)}")
    print("==================================================\n")

    if bot and RENDER_EXTERNAL_URL:
        webhook_url = f"{RENDER_EXTERNAL_URL.strip('/')}/{TELEGRAM_TOKEN}"
        bot.remove_webhook()
        bot.set_webhook(url=webhook_url)
        print(f"🔗 [Webhook] Registrado en: {webhook_url}")

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
