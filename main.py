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
OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY")
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL", "")

bot = telebot.TeleBot(TELEGRAM_TOKEN) if TELEGRAM_TOKEN else None
app = Flask(__name__)

print(f"🤖 [INICIO] Bot activo. Token Telegram: {bool(TELEGRAM_TOKEN)}")
print(f"🔑 [INICIO] Estado de APIs en Render -> Groq: {bool(GROQ_KEY)} | Gemini: {bool(GEMINI_KEY)} | OpenRouter: {bool(OPENROUTER_KEY)}")

# ----------------------------------------------------
# 2. BÚSQUEDA WEB AUTÓNOMA (DUCKDUCKGO)
# ----------------------------------------------------
def buscar_informacion_partido(partido):
    print(f"🔍 [SCRAPER] Buscando noticias para: '{partido}'")
    query = f"{partido} alineaciones bajas lesionados noticias recientes futbol"
    contexto_web = ""
    
    try:
        results = list(DDGS().text(query, max_results=5))
        if results:
            for r in results:
                contexto_web += f"- {r.get('title', '')}: {r.get('body', '')}\n"
            print("✅ [SCRAPER] Datos web recopilados con éxito.")
        else:
            print("⚠️ [SCRAPER] No se encontraron datos web directos.")
    except Exception as e:
        print(f"❌ [SCRAPER ERROR] Fallo al consultar DuckDuckGo: {e}")
        
    return contexto_web if contexto_web else "No se obtuvo información web reciente. Usa conocimiento general."

# ----------------------------------------------------
# 3. PROMPTS SUBDIVIDIDOS
# ----------------------------------------------------
PROMPT_BLOQUE_1 = """
Eres un analista táctico y estadístico profesional de fútbol. Analiza el partido utilizando la INFORMACIÓN EN TIEMPO REAL provista.
Escribe ÚNICAMENTE los puntos del 1 al 6 de forma clara y detallada:

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

# ----------------------------------------------------
# 4. MOTORES DE IA CON MANEJO DE ERRORES DETALLADO
# ----------------------------------------------------
def consultar_gemini(prompt_sistema, prompt_usuario):
    if not GEMINI_KEY:
        print("⚠️ [GEMINI SKIPPED] Clave GEMINI_API_KEY no presente en las variables de Render.")
        return None
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_KEY}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{
            "parts": [{"text": f"{prompt_sistema}\n\n[DATOS DEL PARTIDO]:\n{prompt_usuario}"}]
        }]
    }
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=25) as response:
            res = json.loads(response.read().decode("utf-8"))
            print("✅ [IA] Respuesta exitosa con Gemini.")
            return res["candidates"][0]["content"]["parts"][0]["text"]
    except urllib.error.HTTPError as e:
        print(f"🚨 [GEMINI HTTP ERROR {e.code}]: {e.read().decode('utf-8')}")
    except Exception as e:
        print(f"🚨 [GEMINI ERROR]: {e}")
    return None

def consultar_groq(prompt_sistema, prompt_usuario, modelo="llama-3.1-8b-instant"):
    if not GROQ_KEY:
        print("⚠️ [GROQ SKIPPED] Clave GROQ_API_KEY no presente.")
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
        with urllib.request.urlopen(req, timeout=25) as response:
            res = json.loads(response.read().decode("utf-8"))
            print(f"✅ [IA] Respuesta exitosa con Groq ({modelo}).")
            return res["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        print(f"🚨 [GROQ HTTP ERROR {e.code}]: {e.read().decode('utf-8')}")
    except Exception as e:
        print(f"🚨 [GROQ ERROR]: {e}")
    return None

def consultar_openrouter(prompt_sistema, prompt_usuario):
    if not OPENROUTER_KEY:
        print("⚠️ [OPENROUTER SKIPPED] Clave OPENROUTER_API_KEY no presente.")
        return None
        
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENROUTER_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "deepseek/deepseek-r1:free",
        "messages": [
            {"role": "system", "content": prompt_sistema},
            {"role": "user", "content": prompt_usuario}
        ]
    }
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=25) as response:
            res = json.loads(response.read().decode("utf-8"))
            print("✅ [IA] Respuesta exitosa con OpenRouter.")
            return res["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        print(f"🚨 [OPENROUTER HTTP ERROR {e.code}]: {e.read().decode('utf-8')}")
    except Exception as e:
        print(f"🚨 [OPENROUTER ERROR]: {e}")
    return None

# ----------------------------------------------------
# 5. ORQUESTADOR DE FALLBACKS
# ----------------------------------------------------
def ejecutar_con_fallbacks(prompt_sistema, prompt_usuario, modelo_groq):
    # Intenta Gemini -> luego Groq -> luego OpenRouter
    respuesta = consultar_gemini(prompt_sistema, prompt_usuario)
    if not respuesta:
        respuesta = consultar_groq(prompt_sistema, prompt_usuario, modelo=modelo_groq)
    if not respuesta:
        respuesta = consultar_openrouter(prompt_sistema, prompt_usuario)
    return respuesta

def generar_analisis_subdividido(partido):
    datos_web = buscar_informacion_partido(partido)
    prompt_usuario = f"Partido a analizar: {partido}\n\n[INFORMACIÓN RECIENTE DE LA WEB]:\n{datos_web}"

    print("\n⚡ [EJECUTANDO] Generando Parte 1 (Puntos 1-6)...")
    parte_1 = ejecutar_con_fallbacks(PROMPT_BLOQUE_1, prompt_usuario, modelo_groq="llama-3.1-8b-instant")

    print("\n⚡ [EJECUTANDO] Generando Parte 2 (Puntos 7-11)...")
    parte_2 = ejecutar_con_fallbacks(PROMPT_BLOQUE_2, prompt_usuario, modelo_groq="llama-3.3-70b-versatile")

    return parte_1, parte_2

# ----------------------------------------------------
# 6. HANDLERS DE TELEGRAM
# ----------------------------------------------------
if bot:
    @bot.message_handler(commands=['start', 'help'])
    def cmd_start(message):
        bot.send_message(
            message.chat.id,
            "👋 **¡Bot Deportivo Activo!**\n\nEnvíame el partido que deseas analizar (ej: *Real Madrid vs Barcelona*) y generaré el informe táctico de 11 puntos con datos en tiempo real.",
            parse_mode="Markdown"
        )

    @bot.message_handler(func=lambda m: True)
    def responder_consulta(message):
        texto_usuario = message.text.strip()
        saludos = ["hola", "buenas", "saludos", "hey", "buenos dias", "buenas tardes", "buenas noches"]
        
        if texto_usuario.lower() in saludos:
            bot.send_message(message.chat.id, "👋 ¡Hola! Escríbeme el nombre del partido que quieres analizar hoy.")
            return

        bot.send_message(message.chat.id, f"🔎 *Consultando datos web en tiempo real para {texto_usuario}...*", parse_mode="Markdown")
        bot.send_chat_action(message.chat.id, "typing")

        parte_1, parte_2 = generar_analisis_subdividido(texto_usuario)

        if not parte_1 and not parte_2:
            bot.send_message(message.chat.id, "⚠️ No fue posible conectar con los servidores de IA en este momento. Revisa los logs de Render para ver la razón exacta.")
            return

        if parte_1:
            try:
                bot.send_message(message.chat.id, f"📊 **ANÁLISIS PARTE 1 (Puntos 1-6)**\n\n{parte_1}", parse_mode="Markdown")
            except Exception:
                bot.send_message(message.chat.id, f"📊 ANÁLISIS PARTE 1 (Puntos 1-6)\n\n{parte_1}")

        if parte_2:
            try:
                bot.send_message(message.chat.id, f"🎯 **PRONÓSTICO Y MERCADOS (Puntos 7-11)**\n\n{parte_2}", parse_mode="Markdown")
            except Exception:
                bot.send_message(message.chat.id, f"🎯 PRONÓSTICO Y MERCADOS (Puntos 7-11)\n\n{parte_2}")

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
