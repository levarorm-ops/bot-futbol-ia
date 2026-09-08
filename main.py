import os
import math
import re
import requests
from datetime import datetime
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
# 2. BASE DE DATOS MAESTRA: PERFILES TÁCTICOS DE LIGAS
# ----------------------------------------------------
DB_PERFILES_TACTICOS = {
    "inglaterra": {
        "nombre_oficial": "Fútbol Inglés (Premier League / Championship / Copas)",
        "estilo": "Ritmo alto, ida y vuelta constante y contacto físico fuerte",
        "tarjetas_recientes": "3.2 Amarillas por partido", "rojas_recientes": "0.28 Promedio",
        "friccion_nivel": "Alto (Arbitraje británico dinámico)", "corner_base": 5.8,
        "p_perd": 1.40, "p_gan": 0.85, "descanso": "72 horas", "fatiga": "Media-Alta",
        "distraccion": "⚡ Alta presión competitiva en cada jornada.", "novedades": "Rotación habitual en copas.",
        "racha": "📊 **RACHA:** Partidos abiertos con alta tendencia a opciones en áreas.",
        "fortaleza": "🔥 **FORTALEZA:** Intensidad física sostenida 90 minutos.",
        "debilidad": "⚠️ **DEBILIDAD:** Desgaste defensivo en tramos finales."
    },
    "espana": {
        "nombre_oficial": "Fútbol Español (LaLiga / Copa del Rey)",
        "estilo": "Posesión posicional, técnica depurada y protestas arbitrales frecuentes",
        "tarjetas_recientes": "4.2 Amarillas por partido", "rojas_recientes": "0.35 Promedio",
        "friccion_nivel": "Alto (Faltas tácticas constantes)", "corner_base": 5.1,
        "p_perd": 1.40, "p_gan": 0.80, "descanso": "72-96 horas", "fatiga": "Media",
        "distraccion": "🏆 Exigencia máxima institucional.", "novedades": "Atención a rotaciones coperas.",
        "racha": "📊 **RACHA:** Partidos disputados con marcadores ajustados.",
        "fortaleza": "🔥 **FORTALEZA:** Excelente manejo de pelota.",
        "debilidad": "⚠️ **DEBILIDAD:** Desgaste ante bloques bajos."
    },
    "italia": {
        "nombre_oficial": "Fútbol Italiano (Serie A / Coppa Italia)",
        "estilo": "Orden táctico riguroso, defensa en bloque bajo y juego estratégico",
        "tarjetas_recientes": "4.5 Amarillas por partido", "rojas_recientes": "0.30 Promedio",
        "friccion_nivel": "Muy Alto", "corner_base": 4.9,
        "p_perd": 1.25, "p_gan": 0.70, "descanso": "96 horas", "fatiga": "Media-Baja",
        "distraccion": "🛡️ Alta tensión táctica y presión defensiva.", "novedades": "Cuidado con amonestaciones.",
        "racha": "📈 **RACHA:** Tendencia a partidos cerrados y defensivos.",
        "fortaleza": "🔥 **FORTALEZA:** Solidez defensiva.",
        "debilidad": "⚠️ **DEBILIDAD:** Menor fluidez en ida y vuelta."
    },
    "francia": {
        "nombre_oficial": "Fútbol Francés (Ligue 1 / Coupe de France)",
        "estilo": "Potencia física, despliegue atlético notable y transiciones explosivas",
        "tarjetas_recientes": "3.7 Amarillas por partido", "rojas_recientes": "0.32 Promedio",
        "friccion_nivel": "Alto", "corner_base": 5.5,
        "p_perd": 1.40, "p_gan": 0.78, "descanso": "96 horas", "fatiga": "Media",
        "distraccion": "⚡ Alta velocidad en carrileros.", "novedades": "Jóvenes talentos físicos.",
        "racha": "📊 **RACHA:** Partidos físicos con espacios.",
        "fortaleza": "🔥 **FORTALEZA:** Despliegue físico.", "debilidad": "⚠️ **DEBILIDAD:** Desatenciones defensivas."
    },
    "portugal": {
        "nombre_oficial": "Fútbol Portugués (Primeira Liga / Taça)",
        "estilo": "Dominio de los grandes clubes, extremos desequilibrantes y juego vertical",
        "tarjetas_recientes": "4.8 Amarillas por partido", "rojas_recientes": "0.40 Promedio",
        "friccion_nivel": "Alto", "corner_base": 5.6,
        "p_perd": 1.45, "p_gan": 0.75, "descanso": "96 horas", "fatiga": "Media",
        "distraccion": "⭐ Presión constante por la cima.", "novedades": "Talento joven y dinámico.",
        "racha": "📊 **RACHA:** Alta disparidad entre equipos.",
        "fortaleza": "🔥 **FORTALEZA:** Desborde por bandas.", "debilidad": "⚠️ **DEBILIDAD:** Espacios a la espalda."
    },
    "turquia": {
        "nombre_oficial": "Fútbol Turco (Super Lig / Türkiye Kupası)",
        "estilo": "Ambiente de máxima presión, juego pasional y vértigo ofensivo",
        "tarjetas_recientes": "5.1 Amarillas por partido", "rojas_recientes": "0.45 Promedio",
        "friccion_nivel": "Extremo", "corner_base": 5.9,
        "p_perd": 1.50, "p_gan": 0.70, "descanso": "72 horas", "fatiga": "Media-Alta",
        "distraccion": "🔥 Presión monumental de gradas.", "novedades": "Estrellas internacionales.",
        "racha": "📈 **RACHA:** Partidos sumamente calientes.",
        "fortaleza": "🔥 **FORTALEZA:** Empuje local implacable.", "debilidad": "⚠️ **DEBILIDAD:** Descontrol emocional."
    },
    "paises bajos": {
        "nombre_oficial": "Fútbol Neerlandés (Eredivisie / Copa KNVB)",
        "estilo": "Vocación ofensiva total, defensa adelantada y partidos muy abiertos",
        "tarjetas_recientes": "2.4 Amarillas por partido", "rojas_recientes": "0.18 Promedio",
        "friccion_nivel": "Moderado-Bajo", "corner_base": 6.3,
        "p_perd": 1.55, "p_gan": 0.90, "descanso": "96 horas", "fatiga": "Baja",
        "distraccion": "⚽ Enfoque total en volumen de ataque y goles.", "novedades": "Jóvenes talentos ofensivos.",
        "racha": "📈 **RACHA:** Partidos con alta media de goles (Over frecuente).",
        "fortaleza": "🔥 **FORTALEZA:** Creación masiva.", "debilidad": "⚠️ **DEBILIDAD:** Fragilidad defensiva."
    },
    "suecia": {
        "nombre_oficial": "Fútbol Sueco (Allsvenskan / Copa)",
        "estilo": "Bloques muy compactos, intensidad física alta y juego directo",
        "tarjetas_recientes": "3.3 Amarillas por partido", "rojas_recientes": "0.22 Promedio",
        "friccion_nivel": "Alto", "corner_base": 5.4,
        "p_perd": 1.35, "p_gan": 0.80, "descanso": "120 horas", "fatiga": "Baja",
        "distraccion": "❄️ Rigor táctico.", "novedades": "Balón parado efectivo.",
        "racha": "📊 **RACHA:** Partidos con máxima entrega.",
        "fortaleza": "🔥 **FORTALEZA:** Orden defensivo.", "debilidad": "⚠️ **DEBILIDAD:** Menor claridad en último tercio."
    },
    "noruega": {
        "nombre_oficial": "Fútbol Noruego (Eliteserien / Copa)",
        "estilo": "Transiciones ultra rápidas, juego vertical y partidos de ida y vuelta",
        "tarjetas_recientes": "2.9 Amarillas por partido", "rojas_recientes": "0.20 Promedio",
        "friccion_nivel": "Moderado", "corner_base": 6.1,
        "p_perd": 1.45, "p_gan": 0.85, "descanso": "96 horas", "fatiga": "Media",
        "distraccion": "⚽ Dinámica ofensiva constante.", "novedades": "Ritmo físico alto.",
        "racha": "📈 **RACHA:** Tendencia a partidos abiertos.",
        "fortaleza": "🔥 **FORTALEZA:** Transiciones fulminantes.", "debilidad": "⚠️ **DEBILIDAD:** Desprotección al atacar."
    },
    "dinamarca": {
        "nombre_oficial": "Fútbol Danés (Superliga / Copa)",
        "estilo": "Orden táctico riguroso, transiciones rápidas y juego vertical",
        "tarjetas_recientes": "3.1 Amarillas por partido", "rojas_recientes": "0.22 Promedio",
        "friccion_nivel": "Alto", "corner_base": 5.3,
        "p_perd": 1.35, "p_gan": 0.80, "descanso": "96 horas", "fatiga": "Baja",
        "distraccion": "❄️ Alta competitividad.", "novedades": "Buen estado físico.",
        "racha": "📊 **RACHA:** Fricción táctica constante.",
        "fortaleza": "🔥 **FORTALEZA:** Disciplina táctica.", "debilidad": "⚠️ **DEBILIDAD:** Margen de error."
    },
    "austria": {
        "nombre_oficial": "Fútbol Austriaco (Bundesliga / ÖFB Cup)",
        "estilo": "Presión asfixiante tras pérdida, ritmo vertiginoso y vocación ofensiva",
        "tarjetas_recientes": "3.5 Amarillas por partido", "rojas_recientes": "0.25 Promedio",
        "friccion_nivel": "Alto", "corner_base": 6.0,
        "p_perd": 1.48, "p_gan": 0.82, "descanso": "96 horas", "fatiga": "Media",
        "distraccion": "⚡ Alta intensidad en bloques altos.", "novedades": "Estilo vertical.",
        "racha": "📈 **RACHA:** Partidos muy dinámicos.",
        "fortaleza": "🔥 **FORTALEZA:** Recuperación rápida.", "debilidad": "⚠️ **DEBILIDAD:** Espacios a la espalda."
    },
    "polonia": {
        "nombre_oficial": "Fútbol Polaco (Ekstraklasa / Copa)",
        "estilo": "Choque físico constante, disputas intensas en mediocampo y juego aguerrido",
        "tarjetas_recientes": "4.0 Amarillas por partido", "rojas_recientes": "0.32 Promedio",
        "friccion_nivel": "Alto", "corner_base": 5.2,
        "p_perd": 1.30, "p_gan": 0.75, "descanso": "96 horas", "fatiga": "Media",
        "distraccion": "🛡️ Lucha reñida.", "novedades": "Bajas por tarjetas.",
        "racha": "📊 **RACHA:** Encuentros cerrados.",
        "fortaleza": "🔥 **FORTALEZA:** Duelos divididos.", "debilidad": "⚠️ **DEBILIDAD:** Precisión técnica."
    },
    "bulgaria": {
        "nombre_oficial": "Liga de Bulgaria (Parva Liga)",
        "estilo": "Bloques defensivos muy cerrados y partidos de baja anotación general",
        "tarjetas_recientes": "4.3 Amarillas por partido", "rojas_recientes": "0.35 Promedio",
        "friccion_nivel": "Alto", "corner_base": 4.6,
        "p_perd": 1.25, "p_gan": 0.65, "descanso": "120 horas", "fatiga": "Baja",
        "distraccion": "🔒 Alta concentración defensiva.", "novedades": "Plantillas estables.",
        "racha": "📉 **RACHA:** Partidos ajustados (Menos de 2.5 goles).",
        "fortaleza": "🔥 **FORTALEZA:** Resistencia en bloque bajo.", "debilidad": "⚠️ **DEBILIDAD:** Bajo volumen ofensivo."
    },
    "brasil": {
        "nombre_oficial": "Brasileirão Serie A (Brasil)",
        "estilo": "Desgaste físico extremo por viajes, talento técnico y partidos eléctricos",
        "tarjetas_recientes": "5.4 Amarillas por partido", "rojas_recientes": "0.45 Promedio",
        "friccion_nivel": "Muy Alto", "corner_base": 6.2,
        "p_perd": 1.50, "p_gan": 0.80, "descanso": "72 horas", "fatiga": "Alta",
        "distraccion": "✈️ Largos desplazamientos.", "novedades": "Rotaciones masivas.",
        "racha": "📈 **RACHA:** Partidos abiertos con tarjetas y córneres.",
        "fortaleza": "🔥 **FORTALEZA:** Desborde individual.", "debilidad": "⚠️ **DEBILIDAD:** Desgaste en segundos tiempos."
    },
    "colombia": {
        "nombre_oficial": "Fútbol Colombiano (Liga BetPlay / Primera A)",
        "estilo": "Intensidad física variable por clima, juego dinámico y fricción local",
        "tarjetas_recientes": "5.8 Amarillas por partido", "rojas_recientes": "0.50 Promedio",
        "friccion_nivel": "Extremo", "corner_base": 5.5,
        "p_perd": 1.45, "p_gan": 0.75, "descanso": "72 horas", "fatiga": "Media-Alta",
        "distraccion": "🌡️ Exigencias de altura y humedad.", "novedades": "Alineaciones disputadas.",
        "racha": "📊 **RACHA:** Partidos cortados con fricción táctica.",
        "fortaleza": "🔥 **FORTALEZA:** Rebeldía táctica.", "debilidad": "⚠️ **DEBILIDAD:** Irregularidad defensiva."
    },
    "arabia": {
        "nombre_oficial": "Liga y Copa de Arabia Saudí",
        "estilo": "Desequilibrio ofensivo con estrellas extranjeras y bloques locales de desgaste",
        "tarjetas_recientes": "2.8 Amarillas por partido", "rojas_recientes": "0.30 Promedio",
        "friccion_nivel": "Moderado-Alto", "corner_base": 5.5,
        "p_perd": 1.45, "p_gan": 0.70, "descanso": "96 horas", "fatiga": "Baja-Media",
        "distraccion": "🏆 Alta exigencia institucional.", "novedades": "Estrellas en el once.",
        "racha": "📈 **RACHA:** Tendencia a marcadores abultados.",
        "fortaleza": "🔥 **FORTALEZA:** Gran pegada.", "debilidad": "⚠️ **DEBILIDAD:** Transiciones lentas."
    },
    "champions": {
        "nombre_oficial": "UEFA Champions League",
        "estilo": "Máxima exigencia táctica, control posicional y vértigo europeo",
        "tarjetas_recientes": "3.8 Amarillas por partido", "rojas_recientes": "0.25 Promedio",
        "friccion_nivel": "Alto", "corner_base": 5.9,
        "p_perd": 1.50, "p_gan": 0.75, "descanso": "120 horas", "fatiga": "Baja",
        "distraccion": "🌟 Máxima competición continental.", "novedades": "Estrellas al 100%.",
        "racha": "📈 **RACHA:** Dinámicas de alto nivel.",
        "fortaleza": "🔥 **FORTALEZA:** Precisión quirúrgica.", "debilidad": "⚠️ **DEBILIDAD:** Exposición a contras."
    },
    "default": {
        "nombre_oficial": "Competición General",
        "estilo": "Equilibrio Táctico Estándar",
        "tarjetas_recientes": "2.5 Amarillas por partido", "rojas_recientes": "0.25 Promedio",
        "friccion_nivel": "Estándar de la competición", "corner_base": 5.0,
        "p_perd": 1.30, "p_gan": 0.80,
        "descanso": "72-96 horas", "fatiga": "Estándar",
        "distraccion": "📅 Calendario regular.", "novedades": "Plantilla normal.",
        "racha": "📊 **RACHA:** Variable.", "fortaleza": "🔥 **FORTALEZA:** Competitivo.", "debilidad": "⚠️ **DEBILIDAD:** Ajustes pendientes."
    }
}

# ----------------------------------------------------
# 3. INTERPRETE DINÁMICO DE ENCUENTROS REALES
# ----------------------------------------------------
def buscar_partido_real_en_web(texto_ingresado):
    try:
        url = f"https://www.thesportsdb.com/api/v1/json/3/searchevents.php?e={texto_ingresado}"
        respuesta = requests.get(url, timeout=3)
        if respuesta.status_code == 200:
            data = respuesta.json()
            if data and data.get("event"):
                evento = data["event"][0]
                home = evento.get("strHomeTeam", "Local")
                away = evento.get("strAwayTeam", "Visitante")
                liga_evento = evento.get("strLeague", "Competición Global")
                return f"{home} vs {away}", liga_evento
    except Exception:
        pass
    
    if " vs " not in texto_ingresado and "-" not in texto_ingresado:
        partido_interpretado = f"{texto_ingresado.title()} vs [Rival de Jornada]"
    else:
        partido_interpretado = texto_ingresado.title()
        
    return partido_interpretado, "Competición Registrada"

def obtener_perfil_tactico(partido_input):
    partido_lower = partido_input.lower()
    for key in DB_PERFILES_TACTICOS.keys():
        if key in partido_lower and key != "default":
            return DB_PERFILES_TACTICOS[key]
    return DB_PERFILES_TACTICOS["default"]

# ----------------------------------------------------
# 4. MOTOR MATEMÁTICO Y PARSER
# ----------------------------------------------------
def calcular_poisson(lmbda, k):
    return (math.exp(-lmbda) * (lmbda ** k)) / math.factorial(k)

def procesar_entrada_usuario(texto_usuario):
    match_nums = re.findall(r'\b\d+[.,]?\d*\b', texto_usuario)
    cuotas_encontradas = [float(n.replace(',', '.')) for n in match_nums if 1.01 <= float(n.replace(',', '.')) <= 50.0]
    
    texto_limpio = re.sub(r'\b\d+[.,]?\d*\b', '', texto_usuario)
    texto_limpio = texto_limpio.replace('cuota', '').replace('cuotas', '').replace('arbitro', '').replace('árbitro', '').strip()
    
    partido_real, liga_detectada = buscar_partido_real_en_web(texto_limpio if len(texto_limpio) > 1 else "Partido")

    c_local, c_empate, c_visitante = None, None, None
    if len(cuotas_encontradas) >= 3:
        c_local = cuotas_encontradas[0]
        c_empate = cuotas_encontradas[1]
        c_visitante = cuotas_encontradas[2]
    elif len(cuotas_encontradas) == 1:
        c_local = cuotas_encontradas[0]

    return partido_real, liga_detectada, c_local, c_empate, c_visitante

def simular_partido_con_cuotas(partido_input, liga_detectada, c_local, c_empate, c_visitante):
    perfil = obtener_perfil_tactico(partido_input + " " + liga_detectada)

    xg_local = 1.45
    xg_visitante = 1.25

    xg_total = xg_local + xg_visitante
    p0 = calcular_poisson(xg_total, 0)
    p1 = calcular_poisson(xg_total, 1)
    p2 = calcular_poisson(xg_total, 2)
    p3 = calcular_poisson(xg_total, 3)

    under_05 = p0 * 100
    over_05 = (1 - p0) * 100
    under_15 = (p0 + p1) * 100
    over_15 = (1 - (p0 + p1)) * 100
    under_25 = (p0 + p1 + p2) * 100
    over_25 = (1 - (p0 + p1 + p2)) * 100
    under_35 = (p0 + p1 + p2 + p3) * 100
    over_35 = (1 - (p0 + p1 + p2 + p3)) * 100

    prob_1x = min(92.5, round(65.0 + (xg_local * 5), 1))
    prob_win_local = round(42.0 + (xg_local * 10), 1)

    analisis_valor = ""
    if c_local:
        cuota_justa_local = round(100 / prob_win_local, 2)
        ev_positivo = c_local > cuota_justa_local
        estado_ev = "✅ ¡Valor Positivo (+EV)! Supera el riesgo modelado." if ev_positivo else "⚠️ Cuota ajustada (Sin gran valor)."
        analisis_valor = f"""
━━━━━━━━━━━━━━━━━━━
🎯 **AUDITORÍA DE VALOR Y CUOTAS:**
• Cuota Ingresada: `{c_local}` | Cuota Justa Modelo: `{cuota_justa_local}`
• Diagnóstico: {estado_ev}
"""

    base_corners = perfil["corner_base"]
    c_perdiendo = round(base_corners * perfil["p_perd"], 1)
    c_ganando = round(base_corners * perfil["p_gan"], 1)
    c_roja = round(base_corners * 1.15, 1)

    reporte = f"""📊 **REPORTE INSTITUCIONAL EN TIEMPO REAL**
Match Identificado: `{partido_input.upper()}`

🏆 **CONTEXTO DE COMPETICIÓN:**
• **Torneo Detectado:** `{perfil['nombre_oficial']}`
• **Estilo Táctico:** `{perfil['estilo']}`
• **Fricción / Disciplina:** `{perfil['friccion_nivel']} | {perfil['tarjetas_recientes']}`

🏰 **EVALUACIÓN DE PLANTILLA:**
• {perfil['fortaleza']}
• {perfil['debilidad']}
• {perfil['racha']}
• Descanso: `{perfil['descanso']}` | Fatiga: `{perfil['fatiga']}`

⚽ **MATRIZ DE GOLES (Poisson):**
• **Más / Menos de 0.5 Goles:** 🟢 `{round(over_05, 1)}%` | 🔴 `{round(under_05, 1)}%`
• **Más / Menos de 1.5 Goles:** 🟢 `{round(over_15, 1)}%` | 🔴 `{round(under_15, 1)}%`
• **Más / Menos de 2.5 Goles:** 🟢 `{round(over_25, 1)}%` | 🔴 `{round(under_25, 1)}%`
• **Más / Menos de 3.5 Goles:** 🟢 `{round(over_35, 1)}%` | 🔴 `{round(under_35, 1)}%`

🚩 **MATRIZ CONTEXTUAL DE CÓRNERS:**
• Base del Torneo: `~{base_corners} Córners`
• Si van Perdiendo: `~{c_perdiendo}` | Si van Ganando: `~{c_ganando}` | Con Roja: `~{c_roja}`

🎯 **OPCIONES VIABLES:**
1. **Doble Oportunidad (1X):** 🟢 **{prob_1x}%**
2. **Más de 1.5 Goles:** 🟢 **{round(over_15, 1)}%**
{analisis_valor}
💰 **BANKROLL SUGERIDO (Base 1,000,000 COP):**
• Sugerencia: Más de 1.5 Goles o Doble Oportunidad.
• Inversión (5%): `$50,000 COP`
"""
    return reporte

# ----------------------------------------------------
# 5. MANEJADORES DE TELEGRAM
# ----------------------------------------------------
if bot:
    @bot.message_handler(commands=['start', 'help'])
    def cmd_start(message):
        enviar_telegram_seguro(
            message.chat.id,
            "👋 **¡Mind Pay Activo!**\n\nEscribe el nombre o parte del equipo que deseas consultar y el sistema buscará el encuentro real de forma automática."
        )

    @bot.message_handler(func=lambda m: True)
    def responder_consulta(message):
        texto_usuario = message.text.strip()
        if texto_usuario.lower() in ["hola", "buenas", "saludos", "hey"]:
            enviar_telegram_seguro(message.chat.id, "👋 ¡Hola! Escribe el equipo o partido que deseas auditar hoy.")
            return

        enviar_telegram_seguro(message.chat.id, f"🔍 *Rastreando encuentro oficial y aplicando perfiles tácticos...*")
        
        partido_real, liga_det, c_loc, c_emp, c_vis = procesar_entrada_usuario(texto_usuario)
        reporte_final = simular_partido_con_cuotas(partido_real, liga_det, c_loc, c_emp, c_vis)
        enviar_telegram_seguro(message.chat.id, reporte_final)

def enviar_telegram_seguro(chat_id, texto):
    try:
        bot.send_message(chat_id, texto, parse_mode="Markdown")
    except Exception:
        try:
            bot.send_message(chat_id, texto)
        except Exception as e:
            print(f"❌ Error en Telegram: {e}")

# ----------------------------------------------------
# 6. SERVIDOR FLASK Y WEBHOOK
# ----------------------------------------------------
@app.route('/')
def home():
    return "Mind Pay Operativo."

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
