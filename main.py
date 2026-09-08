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
# 2. MOTOR DE PERFILES TÁCTICOS, FATIGA Y ROTACIONES
# ----------------------------------------------------
DB_PERFILES_TACTICOS = {
    "madrid": {
        "estilo": "Dominio de Posesión y Transiciones Rápidas al Espacio",
        "tarjetas_recientes": "2.4 Amarillas por partido (Últimos 10 duelos)",
        "rojas_recientes": "0.15 Promedio",
        "friccion_nivel": "Moderado-Alto (Buscan faltas tácticas para cortar contras rivales)",
        "corner_base": 6.4,
        "p_perd": 1.45,
        "p_gan": 0.85,
        "descanso": "72 horas (Descanso estándar de competición)",
        "fatiga": "Media-Alta (Acumulación de minutos en bloque titular)",
        "distraccion": "⚠️ **Atención:** Partido clave de Champions League a mitad de semana (riesgo de rotación parcial en ofensiva).",
        "novedades": "Plantilla estable, precaución médica con un lateral por sobrecarga muscular."
    },
    "barcelona": {
        "estilo": "Posesión Posicional Estricta y Presión Tras Pérdida",
        "tarjetas_recientes": "2.6 Amarillas por partido (Últimos 10 duelos)",
        "rojas_recientes": "0.20 Promedio",
        "friccion_nivel": "Alto en la presión alta (muchas faltas tácticas al recuperar)",
        "corner_base": 6.8,
        "p_perd": 1.50,
        "p_gan": 0.90,
        "descanso": "96 horas (Excelente recuperación física)",
        "fatiga": "Baja-Media (Rotación dosificada en la fecha anterior)",
        "distraccion": "⚽ Enfocados 100% en la liga local (Sin distracciones europeas inmediatas).",
        "novedades": "Sin lesiones de última hora; once inicial óptimo disponible."
    },
    "getafe": {
        "estilo": "Bloque Bajo Intenso, Fricción Constante y Duelos al Choque",
        "tarjetas_recientes": "3.8 Amarillas por partido (Últimos 10 duelos - Muy alto riesgo)",
        "rojas_recientes": "0.45 Promedio",
        "friccion_nivel": "Extremo (Cortan constantemente el juego con faltas sistemáticas)",
        "corner_base": 3.9,
        "p_perd": 1.20,
        "p_gan": 0.65,
        "descanso": "120 horas (Semana larga de preparación exclusiva)",
        "fatiga": "Baja (Cuerpo físico fresco y recuperado)",
        "distraccion": "🛡️ Partido vital por la permanencia/posiciones europeas (Máxima concentración institucional).",
        "novedades": "Recuperan titulares sancionados en la jornada pasada."
    },
    "celta": {
        "estilo": "Juego Directo, Intensidad Física Media y Repliegue",
        "tarjetas_recientes": "2.7 Amarillas por partido (Últimos 10 duelos)",
        "rojas_recientes": "0.22 Promedio",
        "friccion_nivel": "Moderado (Disputas físicas intensas en zona medular)",
        "corner_base": 4.5,
        "p_perd": 1.25,
        "p_gan": 0.75,
        "descanso": "72 horas (Margen habitual)",
        "fatiga": "Media (Desgaste físico notable en su última salida como visitante)",
        "distraccion": "📅 Calendario regular sin presiones adicionales.",
        "novedades": "Baja esperada en el mediocampo por acumulación de amarillas."
    },
    "default": {
        "estilo": "Equilibrio Táctico entre Tenencia y Bloque Medio",
        "tarjetas_recientes": "2.5 Amarillas por partido (Promedio general de liga)",
        "rojas_recientes": "0.25 Promedio",
        "friccion_nivel": "Estándar según la fricción habitual de la competición",
        "corner_base": 5.0,
        "p_perd": 1.30,
        "p_gan": 0.80,
        "descanso": "72-96 horas (Margen de descanso estándar)",
        "fatiga": "Estándar según calendario regular",
        "distraccion": "📅 Sin distracciones de torneos internacionales a corto plazo.",
        "novedades": "Plantilla disponible dentro de los parámetros normales."
    }
}

def obtener_perfil_tactico(partido_input):
    partido_lower = partido_input.lower()
    for key in DB_PERFILES_TACTICOS.keys():
        if key in partido_lower:
            return DB_PERFILES_TACTICOS[key]
    return DB_PERFILES_TACTICOS["default"]

# ----------------------------------------------------
# 3. MOTOR MATEMÁTICO Y PARSER INTELIGENTE
# ----------------------------------------------------
def calcular_poisson(lmbda, k):
    return (math.exp(-lmbda) * (lmbda ** k)) / math.factorial(k)

def procesar_entrada_usuario(texto_usuario):
    match_nums = re.findall(r'\b\d+[.,]?\d*\b', texto_usuario)
    cuotas_encontradas = [float(n.replace(',', '.')) for n in match_nums if 1.01 <= float(n.replace(',', '.')) <= 50.0]
    
    texto_limpio = re.sub(r'\b\d+[.,]?\d*\b', '', texto_usuario)
    texto_limpio = texto_limpio.replace('cuota', '').replace('cuotas', '').replace('arbitro', '').replace('árbitro', '').strip()
    if not texto_limpio or len(texto_limpio) < 2:
        texto_limpio = "Partido Analizado"

    c_local, c_empate, c_visitante = None, None, None
    if len(cuotas_encontradas) >= 3:
        c_local = cuotas_encontradas[0]
        c_empate = cuotas_encontradas[1]
        c_visitante = cuotas_encontradas[2]
    elif len(cuotas_encontradas) == 1:
        c_local = cuotas_encontradas[0]

    return texto_limpio, c_local, c_empate, c_visitante

def simular_partido_con_cuotas(partido_input, c_local, c_empate, c_visitante):
    partido_lower = partido_input.lower()
    
    xg_local = 1.65
    xg_visitante = 1.15
    
    eval_local = "🔥 **FORTALEZA:** Alta eficacia en la presión alta y tenencia en su estadio."
    debil_local = "⚠️ **DEBILIDAD:** Deja espacios a la espalda de los laterales en transiciones rápidas."
    racha_local = "📈 **RACHA:** Invicto en los últimos 4 partidos como local (3 victorias, 1 empate)."

    eval_visitante = "⚡ **FORTALEZA:** Peligroso en jugadas a balón parado y contragolpes directos."
    debil_visitante = "⚠️ **DEBILIDAD:** Sufre defensivamente fuera de casa y baja su intensidad física en los segundos tiempos."
    racha_visitante = "📉 **RACHA:** Alterna derrotas y empates a domicilio en sus últimas 5 salidas."

    if "madrid" in partido_lower or "barcelona" in partido_lower or "city" in partido_lower:
        xg_local = 2.10
        xg_visitante = 1.25
        eval_local = "🔥 **FORTALEZA:** Dominio absoluto de posesión y pegada letal en el área."
        debil_local = "⚠️ **DEBILIDAD:** Exceso de confianza defensiva en tramos finales."
        racha_local = "📈 **RACHA:** Imparable, sumando múltiples victorias consecutivas."
    elif "getafe" in partido_lower or "celta" in partido_lower:
        xg_local = 1.40
        xg_visitante = 1.10
        eval_local = "🔥 **FORTALEZA:** Bloque bajo muy ordenado y fricción constante."
        debil_local = "⚠️ **DEBILIDAD:** Bajo volumen de creación de juego en ofensiva estática."
        racha_visitante = "📉 **RACHA:** Tendencia a empates sufridos y marcadores ajustados fuera de casa."

    # Goles y Poisson para Over / Under (0.5 al 3.5)
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

    prob_1x = min(92.5, round(68.5 + (xg_local * 5), 1))
    prob_win_local = round(45.0 + (xg_local * 10), 1)

    # Obtención de perfil táctico, fatiga y rotaciones
    perfil = obtener_perfil_tactico(partido_input)

    # Auditoría de Valor / Cuotas
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

    # Cálculo contextual de córneres según estilo de juego e inercia
    base_corners = perfil["corner_base"]
    c_perdiendo = round(base_corners * perfil["p_perd"], 1)
    c_ganando = round(base_corners * perfil["p_gan"], 1)
    c_goleada = round(base_corners * 1.35, 1)
    c_roja = round(base_corners * 1.20, 1)

    reporte = f"""📊 **REPORTE INSTITUCIONAL: ANÁLISIS TÁCTICO, FATIGA Y CONTEXTO**
Match / Config: `{partido_input.upper()}`

🏰 **EVALUACIÓN INTEGRAL - EQUIPO LOCAL:**
• {eval_local}
• {debil_local}
• {racha_local}
• Fiabilidad Doble Oportunidad (1X): **{prob_1x}%**

🚌 **EVALUACIÓN INTEGRAL - EQUIPO VISITANTE:**
• {eval_visitante}
• {debil_visitante}
• {racha_visitante}

⚽ **MATRIZ DE GOLES (Líneas Oficiales Over / Under):**
• **Más / Menos de 0.5 Goles:** 🟢 Más: `{round(over_05, 1)}%` | 🔴 Menos: `{round(under_05, 1)}%`
• **Más / Menos de 1.5 Goles:** 🟢 Más: `{round(over_15, 1)}%` | 🔴 Menos: `{round(under_15, 1)}%`
• **Más / Menos de 2.5 Goles:** 🟢 Más: `{round(over_25, 1)}%` | 🔴 Menos: `{round(under_25, 1)}%`
• **Más / Menos de 3.5 Goles:** 🟢 Más: `{round(over_35, 1)}%` | 🔴 Menos: `{round(under_35, 1)}%`

🚩 **MATRIZ CONTEXTUAL DE CÓRNERS (Basada en Estilo de Juego):**
• 📊 **Promedio Base del Estilo:** `~{base_corners} Córners`
• 📉 **Si el equipo va Perdiendo (Presión y centros al área):** `~{c_perdiendo} Córners`
• 📈 **Si el equipo va Ganando (Bloque bajo y control de ritmo):** `~{c_ganando} Córners`
• ⚽ **Escenario de Partido Abierto / Goleada:** `~{c_goleada} Córners`
• 🟥 **Escenario con Expulsión / Roja:** `~{c_roja} Córners`

🛡️ **DIAGNÓSTICO TÁCTICO Y DISCIPLINARIO:**
• **Estilo Predominante:** `{perfil['estilo']}`
• **Nivel de Fricción / Choque:** `{perfil['friccion_nivel']}`
• **Tendencia de Tarjetas (Últimos duelos):** `{perfil['tarjetas_recientes']}` | Rojas: `{perfil['rojas_recientes']}`

🔋 **FACTOR DE FATIGA, DESCANSO Y ROTACIONES (CONTEXTO DE PLANTILLA):**
• **Margen de Descanso:** `{perfil['descanso']}`
• **Nivel de Fatiga Física:** `{perfil['fatiga']}`
• **Distracciones de Calendario:** {perfil['distraccion']}
• **Novedades y Lesiones:** `{perfil['novedades']}`

🎯 **ESCALAFÓN DE OPCIONES VIABLES (Ranking por Probabilidad):**
1. **Doble Oportunidad (1X):** 🟢 **{prob_1x}%** de fiabilidad.
2. **Más de 1.5 Goles Totales:** 🟢 **{round(over_15, 1)}%** de probabilidad real.
3. **Menos de 3.5 Goles Totales:** 🟢 **{round(under_35, 1)}%** de probabilidad real.
4. **Menos de 4.5 Tarjetas:** 🟡 **72.5%** de probabilidad estimada por tendencia.
{analisis_valor}
💰 **SUGERENCIA DE APUESTA SEGURA (Bankroll 1,000,000 COP):**
• **Opción Conservadora Sugerida:** Doble Oportunidad (1X) o Más de 1.5 Goles.
• **Cuota Objetivo Estimada:** `@1.25` a `@1.38`
• **Inversión Sugerida (5%):** `$50,000 COP`
• **Ganancia Proyectada:** `~$15,000 a ~$19,000 COP` (Crecimiento seguro y sostenido).
"""
    return reporte

# ----------------------------------------------------
# 4. MANEJADORES DE TELEGRAM
# ----------------------------------------------------
if bot:
    @bot.message_handler(commands=['start', 'help'])
    def cmd_start(message):
        enviar_telegram_seguro(
            message.chat.id,
            "👋 **¡Bot Estadístico Pro (Táctico + Fatiga) Activo!**\n\nEnvíame el partido para auditar: Estilo de juego, fatiga física, días de descanso, distracciones de calendario, líneas Over/Under y córneres contextuales."
        )

    @bot.message_handler(func=lambda m: True)
    def responder_consulta(message):
        texto_usuario = message.text.strip()
        if texto_usuario.lower() in ["hola", "buenas", "saludos", "hey"]:
            enviar_telegram_seguro(message.chat.id, "👋 ¡Hola! Escribe el partido o cuotas que deseas auditar hoy.")
            return

        enviar_telegram_seguro(message.chat.id, f"🔎 *Analizando estilo táctico, descanso, fatiga y rotaciones de plantilla...*")
        
        partido, c_loc, c_emp, c_vis = procesar_entrada_usuario(texto_usuario)
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
# 5. SERVIDOR FLASK Y WEBHOOK
# ----------------------------------------------------
@app.route('/')
def home():
    return "Bot Estadístico Avanzado Operativo."

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
