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

# ----------------------------------------------------
# 2. MOTOR DE IA (SOLO GROQ - ULTRA ESTABLE)
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
    print("\n================ [CONSULTANDO GROQ] ================")
    if not GROQ_KEY:
        print("❌ FALTA LA LLAVE GROQ_API_KEY EN RENDER")
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
    
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            res = json.loads(response.read().decode("utf-8"))
            if res and "choices" in res:
                return res["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        error_detalles = e.read().decode("utf-8")
        print(f"\n🚨 [HTTP ERROR {e.code}] Groq rechazó la petición: {error_detalles}")
    except Exception as e:
        print(f"❌ Error inesperado con Groq: {e}")
        
    return None

# ----------------------------------------------------
# 3. MANEJADORES DE TELEGRAM
# ----------------------------------------------------
if bot:
    @bot.message_handler(commands=['start', 'help'])
    def cmd_start(message):
        msj = "👋 **¡Bot de Análisis Deportivo Activo!**\n\nEscríbeme el partido que deseas analizar (ej: *Real Betis vs Barcelona*) y te generaré el informe de los 11 puntos."
        bot.send_message(message.chat.id, msj, parse_mode="Markdown")

    @bot.message_handler(func=lambda m: True)
    def responder_consulta(message):
        texto_usuario = message.text.strip().lower()
        
        saludos = ["hola", "buenas", "saludos", "hey", "buenos dias", "buenas tardes", "buenas noches"]
        if texto_usuario in saludos:
            bot.send_message(message.chat.id, "👋 ¡Hola, hermano! Escríbeme el nombre del partido que quieres analizar.")
            return

        bot.send_chat_action(message.chat.id, "typing")
        respuesta = generar_analisis_ia(message.text)
        
        if not respuesta:
            bot.send_message(message.chat.id, "⚠️ **Groq rechazó la consulta.** Revisa los Logs de Render para ver el código de error exacto de la llave.")
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
# 4. CONFIGURACIÓN DEL SERVIDOR WEB FLASK
# ----------------------------------------------------
@app.route('/')
def home():
    return "Bot Groq Deportivo Operativo."

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
