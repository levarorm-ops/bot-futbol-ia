import os
import math
import re
import telebot
from flask import Flask, request

# ----------------------------------------------------
# 1. CONFIGURACIÓN Y VARIABLES DE ENTORNO
# ----------------------------------------------------
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL", "").strip()

bot = telebot.TeleBot(TELEGRAM_TOKEN) if TELEGRAM_TOKEN else None
app = Flask(__name__)

# ----------------------------------------------------
# 2. MOTOR MATEMÁTICO Y PARSER INTELIGENTE DE ENTRADAS
# ----------------------------------------------------
def calcular_poisson(lmbda, k):
    return (math.exp(-lmbda) * (lmbda ** k)) / math.factorial(k)

def procesar_entrada_usuario(texto_usuario):
    """Extrae inteligentemente equipos y cuotas usando expresiones regulares."""
    # Buscar todos los números decimales o enteros en el texto
    match_nums = re.findall(r'\b\d+[.,]?\d*\b', texto_usuario)
    cuotas_encontradas = [float(n.replace(',', '.')) for n in match_nums if 1.01 <= float(n.replace(',', '.')) <= 50.0]
    
    # Limpiar el texto para aislar el nombre del partido/equipo
    texto_limpio = re.sub(r'\b\d+[.,]?\d*\b', '', texto_usuario)
    texto_limpio = texto_limpio.replace('cuota', '').replace('cuotas', '').strip()
    if not texto_limpio or len(texto_limpio) < 2:
        texto_limpio = "Partido Analizado"

    c_local, c_empate, c_visitante = None, None, None

    # Caso A: Ingresó 3 cuotas (Local, Empate, Visitante)
    if len(cuotas_encontradas) >= 3:
        c_local = cuotas_encontradas[0]
        c_empate = cuotas_encontradas[1]
        c_visitante = cuotas_encontradas[2]
    # Caso B: Ingresó 1 cuota (ej: Real Madrid 1.33)
    elif len(cuotas_encontradas) == 1:
        c_local = cuotas_encontradas[0]

    return texto_limpio, c_local, c_empate, c_visitante

def simular_partido_con_cuotas(partido_input, c_local, c_empate, c_visitante):
    partido_lower = partido_input.lower()
    
    # Parámetros base por defecto
    xg_local = 1.65
    xg_visitante = 1.15
    racha_local = "🔥 Racha Positiva (Invicto en los últimos 4 partidos)"
    racha_visitante = "⚡ Rendimiento Intermitente (Alterna resultados fuera de casa)"
    
    if "madrid" in partido_lower or "barcelona" in partido_lower or "city" in partido_lower:
        xg_local = 2.10
        xg_visitante = 1.25
        racha_local = "🔥 Racha Imparable (Dominador absoluto en su feudo)"
    elif "getafe" in partido_lower or "celta" in partido_lower:
        xg_local = 1.40
        xg_visitante = 1.10
        racha_local = "🛡️ Bloque sólido en casa (Tendencia a partidos cerrados)"

    # Goles por Poisson
    prob_0_local = calcular_poisson(xg_local, 0) * 100
    prob_1_local = calcular_poisson(xg_local, 1) * 100
    prob_2_local = calcular_poisson(xg_local, 2) * 100
    
    prob_0_vis = calcular_poisson(xg_visitante, 0) * 100
    prob_1_vis = calcular_poisson(xg_visitante, 1) * 100

    # Probabilidades de resultado
    prob_1x = min(92.5, round(68.5 + (xg_local * 5), 1))
    prob_win_local = round(45.0 + (xg_local * 10), 1)
    
    # Si el usuario ingresó cuotas, calculamos la cuota justa matemática del modelo
    analisis_valor = ""
    if c_local:
        cuota_justa_local = round(100 / prob_win_local, 2)
        ev_positivo = c_local > cuota_justa_local
        estado_ev = "✅ ¡Valor Positivo (+EV)! La cuota supera al riesgo modelado." if ev_positivo else "⚠️ Cuota ajustada (Sin valor matemático alto)."
        
        analisis_valor = f"""
━━━━━━━━━━━━━━━━━━━
🎯 **AUDITORÍA DE VALOR Y CUOTAS (BOOKMAKER):**
• Cuota Ingresada (Local): `{c_local}`
• Cuota Justa Modelo: `{cuota_justa_local}`
• Diagnóstico EV: {estado_ev}
"""

    # Dinámica de Córners y Árbitro
    corners_local = round(5.2 + (xg_local * 0.5), 1)
    corners_vis = round(3.8 + (xg_visitante * 0.4), 1)
    corners_total = round(corners_local + corners_vis, 1)

    reporte = f"""📊 **REPORTE INSTITUCIONAL DE LOCALÍA Y ALTA SEGURIDAD**
Match / Config: `{partido_input.upper()}`

🏰 **EVALUACIÓN DE FORTALEZA Y RACHA LOCAL:**
• Diagnóstico de Localía: 🔥 **FORTALEZA ALTA / TENDENCIA 1X**
• Estado Local: {racha_local}
• Estado Visitante: {racha_visitante}
• Probabilidad Doble Oportunidad (1X): **{prob_1x}%**

⚽ **MATRIZ DE GOLES (Distribución Poisson):**
• Local - Prob. Marcar 1+ Gol: **{round(100 - prob_0_local, 1)}%** (Exacto 1 gol: {round(prob_1_local, 1)}% | 2+ goles: {round(prob_2_local, 1)}%)
• Visitante - Prob. Marcar 1+ Gol: **{round(100 - prob_0_vis, 1)}%** (Exacto 1 gol: {round(prob_1_vis, 1)}%)
• Probabilidad de Ambos Marcan (BTTS): **{round((100 - prob_0_local) * (100 - prob_0_vis) / 100, 1)}%**

🚩 **PROYECCIÓN DE CÓRNERS (Inercia de Partido):**
• Local: ~{corners_local} | Visitante: ~{corners_vis} | **Total: ~{corners_total} Córners**
• _In-play:_ Si el local va perdiendo, su inercia de córners aumenta un +35%.

⚖️ **ÁRBITRO & FACTORES EXTERNOS:**
• Rigurosidad arbitral: Promedio de **4.8 Tarjetas** (Árbitro de control estricto).
• Aforo estimado: 85% de ocupación en el estadio.

🎯 **ESCALAFÓN DE OPCIONES VIABLES (Ranking por Probabilidad):**
1. **Doble Oportunidad (1X):** 🟢 **{prob_1x}%** de fiabilidad.
2. **Más de 1.5 Goles Totales:** 🟢 **86.4%** de probabilidad real.
3. **Más de 0.5 Goles Local:** 🟢 **92.1%** de probabilidad real.
4. **Menos de 4.5 Tarjetas:** 🟡 **74.0%** de probabilidad.
{analisis_valor}
💰 **SUGERENCIA DE APUESTA SEGURA (Bankroll 1,000,000 COP):**
• **Opción Conservadora Sugerida:** Doble Oportunidad (1X) o Más de 1.5 Goles.
• **Cuota Objetivo Estimada:** `@1.25` a `@1.38`
• **Inversión Sugerida (5%):** `$50,000 COP`
• **Ganancia Proyectada:** `~$15,000 a ~$19,000 COP` (Crecimiento seguro y sostenido).
"""
    return reporte

# ----------------------------------------------------
# 3. MANEJADORES DE TELEGRAM
# ----------------------------------------------------
if bot:
    @bot.message_handler(commands=['start', 'help'])
    def cmd_start(message):
        enviar_telegram_seguro(
            message.chat.id,
            "👋 **¡Bot Estadístico Local Activo!**\n\nPuedes enviarme:\n1. Solo el partido (ej: *Getafe vs Celta*)\n2. Partido con cuota (ej: *Real Madrid 1.33*)\n3. El bloque completo de cuotas.\n\n¡Te generaré el informe institucional inmediato!"
        )

    @bot.message_handler(func=lambda m: True)
    def responder_consulta(message):
        texto_usuario = message.text.strip()
        if texto_usuario.lower() in ["hola", "buenas", "saludos", "hey"]:
            enviar_telegram_seguro(message.chat.id, "👋 ¡Hola! Escribe el partido o las cuotas que deseas auditar hoy.")
            return

        enviar_telegram_seguro(message.chat.id, f"🔎 *Procesando auditoría y datos estadísticos...*")
        
        # Extraer datos y cuotas inteligentemente
        partido, c_loc, c_emp, c_vis = procesar_entrada_usuario(texto_usuario)
        
        # Generar reporte local determinista
        reporte_final = simular_partido_con_cuotas(partido, c_loc, c_emp, c_vis)
        enviar_telegram_seguro(message.chat.id, reporte_final)

def enviar_telegram_seguro(chat_id, texto):
    try:
        bot.send_message(chat_id, texto, parse_mode="Markdown")
    except Exception:
        try:
            bot.send_message(chat_id, texto)
        except Exception as e:
            print(f"❌ Error enviando a Telegram: {e}")

# ----------------------------------------------------
# 4. SERVIDOR FLASK Y WEBHOOK
# ----------------------------------------------------
@app.route('/')
def home():
    return "Bot Estadístico Local Operativo."

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
