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
GROQ_KEY = os.environ.get("GROQ_API_KEY")
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL", "")

bot = telebot.TeleBot(TELEGRAM_TOKEN) if TELEGRAM_TOKEN else None
app = Flask(__name__)

print(f"🤖 [INICIO] Bot configurado. ¿Token presente?: {bool(TELEGRAM_TOKEN)}")
print(f"🔑 [INICIO] Llave Groq presente?: {bool(GROQ_KEY)}")

# ----------------------------------------------------
# 2. MOTOR DE GROQ
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

def generar_analisis_ia(prompt):
    print(f"\n⚡ [EJECUTANDO] Llamando a Groq con el texto: '{prompt}'")
    if not GROQ_KEY:
        print("❌ ERROR: La variable GROQ_API_KEY no está configurada.")
        return None

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
    
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        print("🚀 Conectando con la API de Groq...")
        
        with urllib.request.urlopen(req, timeout=45) as response:
            res = json.loads(response.read().decode("utf-8"))
            if res and "choices" in res:
                print("✅ ¡Groq respondió con éxito!")
                return res["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        error_detalles = e.read().decode("utf-8")
        print(f"\n🚨 [HTTP ERROR {e.code}] Groq rechazó la petición: {error_detalles}")
    except urllib.error.URLError as e:
        print(f"\n❌ [URL ERROR] Fallo de red con Groq: {e.reason}")
    except Exception as e:
        print(f"\n❌ [ERROR INESPERADO CON GROQ]: {e}")
        
    return None

# ----------------------------------------------------
# 3. MANEJADORES DE TELEGRAM DIRECTOS
# ----------------------------------------------------
if bot:
    @bot.message_handler(commands=['start', 'help'])
    def cmd_start(message):
        print(f"📩 Comando /start recibido de {message.chat.id}")
        bot.send_message(message.chat.id, "👋 **¡Bot Deportivo Activo!**\n\nEnvíame el partido que deseas analizar (ej: *Real Madrid vs Barcelona*) y generaré el informe táctico de los 11 puntos.", parse_mode="Markdown")

    @bot.message_handler(func=lambda m: True)
    def responder_consulta(message):
        print(f"📩 [MENSAJE ATRAPADO] Texto del usuario: '{message.text}'")
        texto_usuario = message.text.strip().lower()
        
        saludos = ["hola", "buenas", "saludos", "hey", "buenos dias", "buenas tardes", "buenas noches"]
        if texto_usuario in saludos:
            bot.send_message(message.chat.id, "👋 ¡Hola, hermano! Escríbeme el nombre del partido que quieres analizar.")
            return

        bot.send_chat_action(message.chat.id, "typing")
        respuesta = generar_analisis_ia(message.text)
        
        if not respuesta:
            bot.send_message(message.chat.id, "⚠️ **Groq no pudo procesar la consulta.** Revisa los Logs en vivo de Render para ver el error exacto.")
            return

        print("✅ Enviando respuesta final a Telegram...")
        if len(respuesta) > 3800:
            for i in range(0, len(respuesta), 3800):
                bot.send_message(message.chat.id, respuesta[i:i+3800])
        else:
            try:
                bot.send_message(message.chat.id, respuesta, parse_mode="Markdown")
            except Exception:
                bot.send_message(message.chat.id, respuesta)

# ----------------------------------------------------
# 4. SERVIDOR FLASK CON PROCESAMIENTO EXPLÍCITO
# ----------------------------------------------------
@app.route('/')
def home():
    return "Bot Deportivo Operativo."

@app.route(f'/{TELEGRAM_TOKEN}', methods=['POST'])
def receive_webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        print("📨 [WEBHOOK] Paquete recibido de Telegram, procesando...")
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
