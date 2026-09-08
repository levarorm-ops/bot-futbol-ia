import os
import json
import urllib.request
import urllib.error
import telebot
from flask import Flask, request
from duckduckgo_search import DDGS

# ----------------------------------------------------
# 1. CONFIGURACIÓN Y VARIABLES DE ENTORNO
# ----------------------------------------------------
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GROQ_KEY = os.environ.get("GROQ_API_KEY")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL", "")

bot = telebot.TeleBot(TELEGRAM_TOKEN) if TELEGRAM_TOKEN else None
app = Flask(__name__)

print(f"🤖 [INICIO] Bot configurado. ¿Token presente?: {bool(TELEGRAM_TOKEN)}")
print(f"🔑 [INICIO] Llave Groq presente?: {bool(GROQ_KEY)}")
print(f"🔑 [INICIO] Llave Gemini presente?: {bool(GEMINI_KEY)}")

# ----------------------------------------------------
# 2. BÚSQUEDA WEB AUTÓNOMA (DUCKDUCKGO)
# ----------------------------------------------------
def buscar_informacion_partido(partido):
    print(f"🔍 [SCRAPER] Buscando información fresca en la web para: {partido}")
    query = f"{partido} alineaciones bajas lesionados noticias recientes futbol"
    contexto_web = ""
    
    try:
        results = list(DDGS().text(query, max_results=5))
        if results:
            for r in results:
                contexto_web += f"- {r.get('title', '')}: {r.get('body', '')}\n"
            print("✅ [SCRAPER] Información en tiempo real recopilada con éxito.")
        else:
            print("⚠️ [SCRAPER] No se encontraron resultados web directos.")
    except Exception as e:
        print(f"❌ [SCRAPER ERROR] Fallo al consultar DuckDuckGo: {e}")
        
    return contexto_web if contexto_web else "No se obtuvo información web reciente. Usa conocimiento general."

# ----------------------------------------------------
# 3. MOTOR DE INTELIGENCIA ARTIFICIAL (MULTI-PROVEEDOR)
# ----------------------------------------------------
PROMPT_BLOQUE_1 = """
Eres un analista táctico y estadístico profesional de fútbol. Analiza el partido utilizando la INFORMACIÓN EN TIEMPO REAL provista.
Escribe ÚNICAMENTE los puntos del 1 al 6 de forma clara, concisa y directa:

1. Contexto y momento actual de ambos equipos.
2. Alineaciones probables y bajas confirmadas.
3. Análisis táctico del partido y propuesta de juego.
4. Historial reciente (H2H) y tendencias.
5. Estadísticas clave (goles, posesión, tiros a puerta, córners).
6. Factores externos (clima, estadio, presión del público, árbitro).
"""

PROMPT_BLOQUE_2 = """
Eres un analista táctico y experto en mercados deportivos de apuestas. Con base en el partido, redacta ÚNICAMENTE los puntos del 7 al 11:

7. Fortalezas y debilidades individuales/colectivas.
8. Mercados sugeridos de apuestas (Línea principal, Over/Under, Córners/Tarjetas).
9. Evaluación del valor en las cuotas (Value Bet).
10. Nivel de riesgo asignado a la predicción (Bajo/Medio/Alto).
11. Conclusión y pronóstico final recomendado.
"""

def consultar_groq(prompt_sistema, prompt_usuario, modelo="llama-3.1-8b-instant"):
    if not GROQ_KEY:
        return None
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": modelo,
        "messages": [
            {"role": "system", "content": prompt_sistema},
            {"role": "user", "content": prompt_usuario}
        ],
        "temperature": 0.5,
        "max_tokens": 1200
    }
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=30) as response:
            res = json.loads(response.read().decode("utf-8"))
            return res["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"🚨 [GROQ ERROR] {e}")
        return None

def consultar_gemini(prompt_sistema, prompt_usuario):
    if not GEMINI_KEY:
        return None
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{
            "parts": [{"text": f"{prompt_sistema}\n\n[DATOS DEL PARTIDO]:\n{prompt_usuario}"}]
        }]
    }
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=30) as response:
            res = json.loads(response.read().decode("utf-8"))
            return res["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        print(f"🚨 [GEMINI ERROR] {e}")
        return None

def generar_analisis_subdividido(partido):
    # Paso 1: Obtener datos web en tiempo real
    datos_web = buscar_informacion_partido(partido)
    prompt_usuario = f"Partido a analizar: {partido}\n\nDatos recientes de la web:\n{datos_web}"

    # Paso 2: Generar Bloque 1 (Puntos 1 al 6) - Probamos con Gemini o Groq (Modelo rápido)
    print("⚡ [EJECUTANDO] Generando Parte 1 (Puntos 1-6)...")
    parte_1 = consultar_gemini(PROMPT_BLOQUE_1, prompt_usuario)
    if not parte_1:
        parte_1 = consultar_groq(PROMPT_BLOQUE_1, prompt_usuario, modelo="llama-3.1-8b-instant")

    # Paso 3: Generar Bloque 2 (Puntos 7 al 11) - Probamos con Groq (Modelo preciso) o Gemini
    print("⚡ [EJECUTANDO] Generando Parte 2 (Puntos 7-11)...")
    parte_2 = consultar_groq(PROMPT_BLOQUE_2, prompt_usuario, modelo="llama-3.3-70b-versatile")
    if not parte_2:
        parte_2 = consultar_gemini(PROMPT_BLOQUE_2, prompt_usuario)

    return parte_1, parte_2

# ----------------------------------------------------
# 4. MANEJADORES DE TELEGRAM
# ----------------------------------------------------
if bot:
    @bot.message_handler(commands=['start', 'help'])
    def cmd_start(message):
        bot.send_message(
            message.chat.id,
            "👋 **¡Bot Deportivo en Tiempo Real Activo!**\n\nEnvíame el partido que deseas analizar (ej: *Real Madrid vs Barcelona*) y buscaré datos de la web para darte un análisis de 11 puntos.",
            parse_mode="Markdown"
        )

    @bot.message_handler(func=lambda m: True)
    def responder_consulta(message):
        texto_usuario = message.text.strip()
        saludos = ["hola", "buenas", "saludos", "hey", "buenos dias", "buenas tardes", "buenas noches"]
        
        if texto_usuario.lower() in saludos:
            bot.send_message(message.chat.id, "👋 ¡Hola! Escríbeme el partido que quieres analizar hoy.")
            return

        bot.send_message(message.chat.id, f"🔎 *Buscando noticias recientes y analizando {texto_usuario}...*", parse_mode="Markdown")
        bot.send_chat_action(message.chat.id, "typing")

        parte_1, parte_2 = generar_analisis_subdividido(texto_usuario)

        if not parte_1 and not parte_2:
            bot.send_message(message.chat.id, "⚠️ No fue posible conectar con los servidores de IA en este momento. Revisa las cuotas de tus API keys.")
            return

        # Envío de la Parte 1
        if parte_1:
            try:
                bot.send_message(message.chat.id, f"📊 **ANÁLISIS PARTE 1 (Puntos 1-6)**\n\n{parte_1}", parse_mode="Markdown")
            except Exception:
                bot.send_message(message.chat.id, f"📊 ANÁLISIS PARTE 1 (Puntos 1-6)\n\n{parte_1}")

        # Envío de la Parte 2
        if parte_2:
            try:
                bot.send_message(message.chat.id, f"🎯 **PRONÓSTICO Y MERCADOS (Puntos 7-11)**\n\n{parte_2}", parse_mode="Markdown")
            except Exception:
                bot.send_message(message.chat.id, f"🎯 PRONÓSTICO Y MERCADOS (Puntos 7-11)\n\n{parte_2}")

# ----------------------------------------------------
# 5. SERVIDOR FLASK Y WEBHOOK
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
    else:
        return "Invalid request", 403

if __name__ == "__main__":
    if bot and RENDER_EXTERNAL_URL:
        webhook_url = f"{RENDER_EXTERNAL_URL.strip('/')}/{TELEGRAM_TOKEN}"
        bot.remove_webhook()
        bot.set_webhook(url=webhook_url)
        print(f"[Webhook] Conectado exitosamente a: {webhook_url}")

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
