import asyncio
import json
import os
import sqlite3
import threading
import aiohttp
import nest_asyncio
import numpy as np
import streamlit as st
from openai import AsyncOpenAI
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

nest_asyncio.apply()

# Configuración de credenciales
TELEGRAM_TOKEN = st.secrets.get("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")

client_ai = AsyncOpenAI(api_key=OPENAI_API_KEY)
DB_PATH = "betano_analytics.db"

# ==========================================
# 1. BASE DE DATOS Y MEMORIA CONVERSACIONAL
# ==========================================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS historial_chat (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            role TEXT,
            content TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def guardar_mensaje(user_id: int, role: str, content: str):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO historial_chat (user_id, role, content) VALUES (?, ?, ?)", (user_id, role, content))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error BBDD: {e}")

def obtener_historial(user_id: int, limit: int = 8) -> list:
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT role, content FROM historial_chat WHERE user_id = ? ORDER BY id DESC LIMIT ?", (user_id, limit))
        filas = cursor.fetchall()
        conn.close()
        return [{"role": r, "content": c} for r, c in reversed(filas)]
    except Exception:
        return []

# ==========================================
# 2. RASTREO WEB COMPLETO (AFORO, PLANTILLA, ÁRBITRO, REACCIÓN Y TIROS)
# ==========================================
async def buscar_contexto_ampliado(partido: str) -> str:
    """Busca capacidad/aforo de estadios, bajas, árbitro asignado, comportamiento ganando/perdiendo, remates y estilo de juego."""
    query = f"{partido} estadio aforo capacidad espectadores alineaciones bajas arbitro promedio tarjetas comportamiento ganando perdiendo tiros al arco"
    url = f"https://html.duckduckgo.com/html/?q={query}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=6)) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(html, "html.parser")
                    snippets = [a.get_text() for a in soup.find_all("a", class_="result__snippet")[:8]]
                    if snippets:
                        return "\n".join(snippets)
    except Exception:
        pass
    return "Analizar bajo contexto de estadio local, capacidad habitual, plantilla actual, arbitraje estándar y tendencias de liga."

# ==========================================
# 3. MOTOR MONTECARLO AMPLIADO
# ==========================================
def simular_poisson_completo(lambda_l: float = 1.65, lambda_v: float = 1.15, simulaciones: int = 100000):
    goles_local = np.random.poisson(lambda_l, simulaciones)
    goles_visita = np.random.poisson(lambda_v, simulaciones)
    total_goles = goles_local + goles_visita

    # Ganadores, Empates y Doble Oportunidad
    p_l = float(np.mean(goles_local > goles_visita) * 100)
    p_e = float(np.mean(goles_local == goles_visita) * 100)
    p_v = float(np.mean(goles_visita > goles_local) * 100)
    p_1x = float(np.mean(goles_local >= goles_visita) * 100)
    p_x2 = float(np.mean(goles_visita >= goles_local) * 100)
    p_12 = float(np.mean(goles_local != goles_visita) * 100)
    p_btts = float(np.mean((goles_local > 0) & (goles_visita > 0)) * 100)

    # Marcadores Exactos Frecuentes
    marcadores = {}
    for i in range(simulaciones):
        m = f"{goles_local[i]}-{goles_visita[i]}"
        marcadores[m] = marcadores.get(m, 0) + 1
    
    top_marcadores = sorted(marcadores.items(), key=lambda x: x[1], reverse=True)[:4]
    top_marcadores_fmt = [f"{m[0]} ({round((m[1]/simulaciones)*100, 1)}%)" for m in top_marcadores]

    # Escala Completa de Goles
    escala_goles = {
        "over_0_5": round(float(np.mean(total_goles > 0.5) * 100), 1),
        "over_1_5": round(float(np.mean(total_goles > 1.5) * 100), 1),
        "over_2_5": round(float(np.mean(total_goles > 2.5) * 100), 1),
        "over_3_5": round(float(np.mean(total_goles > 3.5) * 100), 1),
        "under_1_5": round(float(np.mean(total_goles < 1.5) * 100), 1),
        "under_2_5": round(float(np.mean(total_goles < 2.5) * 100), 1),
        "under_3_5": round(float(np.mean(total_goles < 3.5) * 100), 1)
    }

    # Escala Completa de Córners (5.5 a 10.5)
    lambda_corners_totales = (lambda_l * 3.3) + (lambda_v * 2.8)
    corners_totales = np.random.poisson(lambda_corners_totales, simulaciones)
    escala_corners = {
        "over_5_5": round(float(np.mean(corners_totales > 5.5) * 100), 1),
        "over_6_5": round(float(np.mean(corners_totales > 6.5) * 100), 1),
        "over_7_5": round(float(np.mean(corners_totales > 7.5) * 100), 1),
        "over_8_5": round(float(np.mean(corners_totales > 8.5) * 100), 1),
        "over_9_5": round(float(np.mean(corners_totales > 9.5) * 100), 1),
        "over_10_5": round(float(np.mean(corners_totales > 10.5) * 100), 1),
        "promedio": round(float(np.mean(corners_totales)), 1)
    }

    # Simulación de Tarjetas
    lambda_tarjetas = 4.8
    tarjetas_totales = np.random.poisson(lambda_tarjetas, simulaciones)
    escala_tarjetas = {
        "over_3_5": round(float(np.mean(tarjetas_totales > 3.5) * 100), 1),
        "over_4_5": round(float(np.mean(tarjetas_totales > 4.5) * 100), 1),
        "over_5_5": round(float(np.mean(tarjetas_totales > 5.5) * 100), 1),
        "over_6_5": round(float(np.mean(tarjetas_totales > 6.5) * 100), 1)
    }

    # Simulación de Tiros al Arco
    lambda_tiros_l = lambda_l * 2.7
    lambda_tiros_v = lambda_v * 2.4
    tiros_totales = np.random.poisson(lambda_tiros_l + lambda_tiros_v, simulaciones)
    escala_tiros = {
        "over_6_5": round(float(np.mean(tiros_totales > 6.5) * 100), 1),
        "over_7_5": round(float(np.mean(tiros_totales > 7.5) * 100), 1),
        "over_8_5": round(float(np.mean(tiros_totales > 8.5) * 100), 1),
        "over_9_5": round(float(np.mean(tiros_totales > 9.5) * 100), 1),
        "promedio_local": round(float(np.mean(lambda_tiros_l)), 1),
        "promedio_visita": round(float(np.mean(lambda_tiros_v)), 1)
    }

    # Mercados Recomendados
    candidatos_top = [
        ("Doble Oportunidad Local (1X)", round(p_1x, 1)),
        ("Doble Oportunidad Visitante (X2)", round(p_x2, 1)),
        ("Más de 1.5 Goles", escala_goles["over_1_5"]),
        ("Menos de 3.5 Goles", escala_goles["under_3_5"]),
        ("Más de 6.5 Córners", escala_corners["over_6_5"]),
        ("Más de 7.5 Córners", escala_corners["over_7_5"]),
        ("Más de 3.5 Tarjetas", escala_tarjetas["over_3_5"]),
    ]
    mercados_variados = [c for c in candidatos_top if 80.0 <= c[1] <= 95.0]
    if not mercados_variados:
        mercados_variados = sorted(candidatos_top, key=lambda x: x[1], reverse=True)[:3]

    return {
        "resultados": {
            "p_local": round(p_l, 1),
            "p_empate": round(p_e, 1),
            "p_visitante": round(p_v, 1),
            "p_1x": round(p_1x, 1),
            "p_x2": round(p_x2, 1),
            "p_12": round(p_12, 1),
            "p_btts": round(p_btts, 1),
            "cuota_justa_local": round(100 / max(p_l, 1.0), 2),
            "cuota_justa_empate": round(100 / max(p_e, 1.0), 2),
            "cuota_justa_visita": round(100 / max(p_v, 1.0), 2)
        },
        "marcadores_probables": top_marcadores_fmt,
        "mercados_top_recomendados": mercados_variados,
        "escala_goles": escala_goles,
        "escala_corners": escala_corners,
        "escala_tarjetas": escala_tarjetas,
        "escala_tiros": escala_tiros
    }

def calcular_criterio_kelly(p_prob: float, cuota: float, fraccion_kelly: float = 0.25) -> float:
    p = p_prob / 100.0
    q = 1.0 - p
    b = cuota - 1.0
    if b <= 0:
        return 0.0
    f = (b * p - q) / b
    return max(0.0, round(f * fraccion_kelly * 100, 2))

# ==========================================
# 4. CAPA DE INTELIGENCIA NPL Y PROMPTING MULTIDIMENSIONAL
# ==========================================
async def analizar_intencion_usuario(mensaje: str) -> dict:
    prompt = """
    Analiza la intención del usuario y responde en JSON estricto:
    {
      "menciona_partido": bool,
      "partido": "Local vs Visitante" o null,
      "cuota_local": float o null,
      "cuota_empate": float o null,
      "cuota_visita": float o null,
      "pide_kelly": bool
    }
    """
    try:
        resp = await client_ai.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": prompt}, {"role": "user", "content": mensaje}],
            temperature=0.0
        )
        return json.loads(resp.choices[0].message.content)
    except Exception:
        return {"menciona_partido": False, "partido": None, "cuota_local": None, "cuota_empate": None, "cuota_visita": None, "pide_kelly": False}

async def responder_usuario(user_id: int, mensaje: str, intencion: dict) -> str:
    bloque_datos = ""
    bloque_contexto = ""

    if intencion.get("menciona_partido") and intencion.get("partido"):
        partido = intencion["partido"]
        bloque_contexto = await buscar_contexto_ampliado(partido)
        stats = simular_poisson_completo()

        evaluacion_cuotas = ""
        cl, ce, cv = intencion.get("cuota_local"), intencion.get("cuota_empate"), intencion.get("cuota_visita")
        if cl or ce or cv:
            evaluacion_cuotas = "\n* AUDITORÍA DE VALOR ESPERADO (EV) Y CRITERIO DE KELLY:\n"
            if cl:
                ev_l = (((stats['resultados']['p_local']/100)*cl)-1)*100
                kelly_l = calcular_criterio_kelly(stats['resultados']['p_local'], cl)
                evaluacion_cuotas += f"  - Local (@{cl}): EV = {ev_l:.1f}% | Stake Sugerido (Kelly): {kelly_l}%\n"
            if ce:
                ev_e = (((stats['resultados']['p_empate']/100)*ce)-1)*100
                kelly_e = calcular_criterio_kelly(stats['resultados']['p_empate'], ce)
                evaluacion_cuotas += f"  - Empate (@{ce}): EV = {ev_e:.1f}% | Stake Sugerido (Kelly): {kelly_e}%\n"
            if cv:
                ev_v = (((stats['resultados']['p_visitante']/100)*cv)-1)*100
                kelly_v = calcular_criterio_kelly(stats['resultados']['p_visitante'], cv)
                evaluacion_cuotas += f"  - Visitante (@{cv}): EV = {ev_v:.1f}% | Stake Sugerido (Kelly): {kelly_v}%\n"

        bloque_datos = f"""
        [MATRIZ ESTADÍSTICA COMPLETA DE MONTECARLO PARA {partido}]:

        1. MERCADOS DE GANADORES Y DOBLE OPORTUNIDAD:
           - Gana Local Directo: {stats['resultados']['p_local']}% (Cuota Justa: @{stats['resultados']['cuota_justa_local']})
           - Empate Directo: {stats['resultados']['p_empate']}% (Cuota Justa: @{stats['resultados']['cuota_justa_empate']})
           - Gana Visitante Directo: {stats['resultados']['p_visitante']}% (Cuota Justa: @{stats['resultados']['cuota_justa_visita']})
           - Doble Oportunidad 1X: {stats['resultados']['p_1x']}%
           - Doble Oportunidad X2: {stats['resultados']['p_x2']}%
           - Doble Oportunidad 12 (Sin Empate): {stats['resultados']['p_12']}%
           - Ambos Anotan (BTTS): {stats['resultados']['p_btts']}%

        2. MARCADORES EXACTOS MÁS PROBABLES:
           - {', '.join(stats['marcadores_probables'])}

        3. ESCALA COMPLETA DE GOLES:
           - Over 0.5: {stats['escala_goles']['over_0_5']}% | Over 1.5: {stats['escala_goles']['over_1_5']}%
           - Over 2.5: {stats['escala_goles']['over_2_5']}% | Over 3.5: {stats['escala_goles']['over_3_5']}%
           - Under 1.5: {stats['escala_goles']['under_1_5']}% | Under 2.5: {stats['escala_goles']['under_2_5']}% | Under 3.5: {stats['escala_goles']['under_3_5']}%

        4. ESCALA COMPLETA DE CÓRNERS (DESDE 5.5 HASTA 10.5):
           - Over 5.5: {stats['escala_corners']['over_5_5']}%
           - Over 6.5: {stats['escala_corners']['over_6_5']}%
           - Over 7.5: {stats['escala_corners']['over_7_5']}%
           - Over 8.5: {stats['escala_corners']['over_8_5']}%
           - Over 9.5: {stats['escala_corners']['over_9_5']}%
           - Over 10.5: {stats['escala_corners']['over_10_5']}%
           - Promedio Estimado: {stats['escala_corners']['promedio']} córners

        5. ESCALA DE TARJETAS (ÁRBITRO Y DISCIPLINA):
           - Over 3.5 Tarjetas: {stats['escala_tarjetas']['over_3_5']}%
           - Over 4.5 Tarjetas: {stats['escala_tarjetas']['over_4_5']}%
           - Over 5.5 Tarjetas: {stats['escala_tarjetas']['over_5_5']}%
           - Over 6.5 Tarjetas: {stats['escala_tarjetas']['over_6_5']}%

        6. TIROS AL ARCO (REMATES A PUERTA):
           - Over 6.5 Tiros a Puerta Totales: {stats['escala_tiros']['over_6_5']}%
           - Over 7.5 Tiros a Puerta Totales: {stats['escala_tiros']['over_7_5']}%
           - Over 8.5 Tiros a Puerta Totales: {stats['escala_tiros']['over_8_5']}%
           - Over 9.5 Tiros a Puerta Totales: {stats['escala_tiros']['over_9_5']}%
           - Promedios Proyectados: Local {stats['escala_tiros']['promedio_local']} tiros a puerta | Visitante {stats['escala_tiros']['promedio_visita']} tiros a puerta

        7. MERCADOS RECOMENDADOS (RANGO 80% - 95%):
           - {', '.join([f"{m[0]}: {m[1]}%" for m in stats['mercados_top_recomendados']])}
        {evaluacion_cuotas}
        """

    historial = obtener_historial(user_id)

    system_instruction = f"""
    Eres 'BETANO Analytics AI', el asistente táctico y cuantitativo definitivo para análisis de fútbol.

    ESTRUCTURA OBLIGATORIA DEL REPORTE AL ANALIZAR UN PARTIDO:

    1. ANÁLISIS DE ESTADIO Y AFORO (LOCAL VS VISITANTE):
       - Informa explícitamente el nombre del estadio del partido, la capacidad/aforo del recinto local y la capacidad/aforo del estadio habitual del equipo visitante.
       - Explica la influencia de la presión ambiental según el aforo y la asistencia proyectada.

    2. AUDITORÍA DE PLANTILLAS Y CALENDARIO REAL:
       - Estado actual de plantillas (fichajes, bajas, ventas recientes, nivel de recién ascendidos o reforzados).
       - Desgaste físico o rotaciones por próximos compromisos internacionales/copas.

    3. COMPORTAMIENTO SEGÚN EL MARCADOR (GANANDO Y PERDIENDO):
       - Explica la reacción táctica y mental de cada equipo cuando va GANANDO (si se repliega o busca la contra) y cuando va PERDIENDO (si adelanta líneas o expone su defensa).

    4. PERFIL DEL ÁRBITRO Y MERCADO DE TARJETAS:
       - Nombre o perfil del juez asignado, nivel de rigurosidad/radicalidad.
       - Presenta la escala de probabilidad de tarjetas (Over 3.5, 4.5, 5.5, 6.5).

    5. ANÁLISIS TÁCTICO DE CÓRNERS (DESGLOSE COMPLETO 5.5 A 10.5):
       - Presenta la lista COMPLETA de probabilidades desde +5.5 hasta +10.5 córners.
       - Explica el análisis táctico por bandas y volumen de centros.

    6. TIROS AL ARCO (REMATES A PUERTA):
       - Desglose de promedios de remates a puerta y opciones Over 6.5, 7.5, 8.5, 9.5.

    7. OPCIONES DE GANADORES, EMPATES Y ESCALA DE GOLES:
       - Porcentajes directos para 1, X, 2, Doble Oportunidad y escala Over/Under de Goles.

    8. MARCADORES PROBABLES Y COHERENCIA NARRATIVA:
       - Marcadores calculados coherentes con la lectura del partido.

    9. EVALUACIÓN FINANCIERA (SI HAY CUOTAS):
       - Valor Esperado (EV%) y Criterio de Kelly si el usuario incluyó cuotas.

    INFORMACIÓN WEB RASTREADA:
    {bloque_contexto}

    MATRIZ MONTECARLO MULTIDIMENSIONAL:
    {bloque_datos}
    """

    messages = [{"role": "system", "content": system_instruction}]
    messages.extend(historial)
    messages.append({"role": "user", "content": mensaje})

    response = await client_ai.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.6
    )

    respuesta_final = response.choices[0].message.content
    guardar_mensaje(user_id, "user", mensaje)
    guardar_mensaje(user_id, "assistant", respuesta_final)

    return respuesta_final

# ==========================================
# 5. HANDLER TELEGRAM Y STREAMLIT
# ==========================================
async def procesar_mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    texto = update.message.text.strip()

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    intencion = await analizar_intencion_usuario(texto)
    respuesta = await responder_usuario(user_id, texto, intencion)

    await update.message.reply_text(respuesta, parse_mode="Markdown")

def arrancar_bot(token):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    init_db()
    app = ApplicationBuilder().token(token).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), procesar_mensaje))
    app.run_polling(drop_pending_updates=True, stop_signals=None)

st.set_page_config(page_title="BETANO Analytics Pro", page_icon="⚽")
st.title("⚽ BETANO Analytics AI - Motor Conversacional Integrado")

if not TELEGRAM_TOKEN or not OPENAI_API_KEY:
    st.error("⚠️ Agrega TELEGRAM_TOKEN y OPENAI_API_KEY en los Secrets de Streamlit.")
else:
    if "bot_iniciado" not in st.session_state:
        st.session_state["bot_iniciado"] = True
        threading.Thread(target=arrancar_bot, args=(TELEGRAM_TOKEN,), daemon=True).start()
        st.success("🚀 Bot interactivo escuchando en Telegram.")
    else:
        st.info("🟢 El sistema conversacional está activo.")
