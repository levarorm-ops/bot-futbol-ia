import os
import json
import urllib.request
import urllib.error
import telebot
from flask import Flask, request

# ----------------------------------------------------
# 1. CONFIGURACIÓN Y VARIABLES DE ENTORNO
# ----------------------------------------------------
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY")
GROQ_KEY = os.environ.get("GROQ_API_KEY")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL", "")

bot = telebot.TeleBot(TELEGRAM_TOKEN) if TELEGRAM_TOKEN else None
app = Flask(__name__)

# ----------------------------------------------------
# 2. MOTOR DE IA MULTIPROVEEDOR CON DEPURACIÓN TOTAL
# ----------------------------------------------------
PROMPT_SISTEMA = """
Eres un analista táctico y estadístico profesional de fútbol. Entrega un análisis detallado, profundo y fundamentado estructurado obligatoriamente en estos 11 puntos clave para apuestas:
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
"""

def hacer_peticion_http(url, headers, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_detalles = e.read().decode("utf-8")
        print(f"\n🚨 [HTTP ERROR {e.code}] La IA rechazó la petición: {error_detalles}")
        return None
    except urllib.error.URLError as e:
        print(f"\n❌ [URL ERROR] Fallo de red: {e.reason}")
        return None
    except Exception as e:
        print(f"\n❌ [ERROR INESPERADO]: {e}")
        return None

def generar_analisis_ia(prompt):
    print("\n================ [INICIANDO CASCADA DE IAs] ================")

    # 1. Intento con OpenRouter (Claude 3.5 Sonnet)
    if OPENROUTER_KEY:
        print("🔍 Intentando con OpenRouter (Claude 3.5 Sonnet)...")
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {"Authorization": f"Bearer {OPENROUTER_KEY}", "Content-Type": "application/json"}
        payload = {
            "model": "anthropic/claude-3.5-sonnet",
            "messages": [{"role": "system", "content": PROMPT_SISTEMA}, {"role": "user", "content": prompt}]
        }
        res = hacer_peticion_http(url, headers, payload)
        if res and "choices" in res:
            print("✅ ¡OpenRouter respondió con éxito!")
            return res["choices"][0]["message"]["content"]
        print("⚠️ OpenRouter falló o no dio respuesta válida, pasando al siguiente...")

    # 2. Intento con Groq (Llama 3.3 70B)
    if GROQ_KEY:
        print("🔍 Intentando con Groq (Llama 3.3 70B)...")
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"}
        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "system", "content": PROMPT_SISTEMA}, {"role": "user", "content": prompt}]
        }
        res = hacer_peticion_http(url, headers, payload)
        if res and "choices" in res:
            print("✅ ¡Groq respondió con éxito!")
            return res["choices"][0]["message"]["content"]
        print("⚠️ Groq falló o no dio respuesta válida, pasando al siguiente...")

    # 3. Intento con Gemini Directo (Gemini 1.5 Flash)
    if GEMINI_KEY:
        print("🔍 Intentando con Gemini 1.5 Flash...")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"
        headers = {"Content-Type": "application/json"}
        payload = {"contents": [{"parts": [{"text": f"{PROMPT_SISTEMA}\n\nConsulta:\n{prompt}"}]}]}
        
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=45) as response:
                res = json.loads(response.read().decode("utf-8"))
                if res and "candidates" in res:
                    print("✅ ¡Gemini respondió con éxito!")
                    return res["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            print(f"❌ Gemini falló: {e}")

    print("❌ TODAS LAS IAs FALLARON O NO TIENEN LLAVES VÁLIDAS.")
    return None

# ----------------------------------------------------
# 3. MANEJADORES DE TELEGRAM (WEBHOOK + FILTRO DE SALUDOS)
# ----------------------------------------------------
if bot:
    @bot.message_handler(commands=['start', 'help'])
    def cmd_start(message):
        msj = "👋 **¡Bot Deportivo Multi-IA Activo!**\n\nEnvíame el partido que deseas analizar (ej: *Real Madrid vs Barcelona*) y generaré el informe táctico de los 11 puntos."
        bot.send_message(message.chat.id, msj, parse_mode="Markdown")

    @bot.message_handler(func=lambda m: True)
    def responder_consulta(message):
        texto_usuario = message.text.strip().lower()
        
        saludos = ["hola", "buenas", "saludos", "hey", "buenos dias", "buenas tardes", "buenas noches"]
        if texto_usuario in saludos:
            bot.send_message(message.chat.id, "👋 ¡Hola, hermano! Escríbeme el nombre del partido que quieres analizar para desplegar el informe.")
            return

        bot.send_chat_action(message.chat.id, "typing")
        respuesta = generar_analisis_ia(message.text)
        
        if not respuesta:
            bot.send_message(message.chat.id, "⚠️ **Ninguna IA pudo procesar la consulta.** Revisa los Logs en vivo de Render para ver el detalle de cuál proveedor falló.")
            return

        if len(respuesta) > 3800:
            for i in range(0, len(respuesta), 3800):
                bot.send_message(message.chat.id, respuesta[i:i+3800])
        else:
            try:
                bot.send_message(message.chat.id, respuesta, parse_mode="Markdown")
            except Exception:
                bot.send_message(message.chat.id, respuesta)

# ----------------------------------------------------
# 4. CONFIGURACIÓN DEL SERVIDOR WEB FLASK (WEBHOOK ROUTE)
# ----------------------------------------------------
@app.route('/')
def home():
    return "Bot Deportivo Multi-IA Operativo."

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
