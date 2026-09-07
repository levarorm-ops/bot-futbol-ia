import os
import logging
import threading
import sqlite3
import numpy as np
import requests
import streamlit as st
from bs4 import BeautifulSoup
from google import genai
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

# Configuración de interfaz visual para Streamlit
st.set_page_config(page_title="Betano Analytics Pro", page_icon="⚽", layout="centered")
st.title("⚽ Betano Analytics Pro - Bot de Telegram Activo")
st.markdown("---")
st.write("🤖 **El bot de Telegram está ejecutándose en segundo plano y escuchando solicitudes.**")
st.info("Puedes minimizar esta ventana. El bot responderá automáticamente en tu chat de Telegram cuando le envíes un partido.")

# Configuración de Logging profesional
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Credenciales desde Secrets de Streamlit
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Inicializar cliente oficial de Google GenAI (SDK 2.22.0)
client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

# Inicialización de Base de Datos SQLite (Persistencia local de consultas)
def init_db():
    try:
        conn = sqlite3.connect("bot_betting.db")
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS queries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                query_text TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error inicializando base de datos: {e}")

init_db()

# Motor Avanzado de Simulación Monte Carlo (100k iteraciones)
def run_monte_carlo(lambda_home=1.5, lambda_away=1.2, sims=100000):
    np.random.seed(42)
    
    home_goals = np.random.poisson(lambda_home, sims)
    away_goals = np.random.poisson(lambda_away, sims)
    
    home_wins = np.mean(home_goals > away_goals) * 100
    draws = np.mean(home_goals == away_goals) * 100
    away_wins = np.mean(home_goals < away_goals) * 100
    
    total_goals = home_goals + away_goals
    under_35_goals = np.mean(total_goals < 3.5) * 100
    
    corners = np.random.poisson(9.2, sims)
    over_55_corners = np.mean(corners > 5.5) * 100
    over_85_corners = np.mean(corners > 8.5) * 100
    over_105_corners = np.mean(corners > 10.5) * 100
    
    cards = np.random.poisson(4.1, sims)
    over_35_cards = np.mean(cards > 3.5) * 100
    
    shots_on_target = np.random.poisson(8.7, sims)
    over_75_shots = np.mean(shots_on_target > 7.5) * 100
    
    return {
        "home_win_prob": round(home_wins, 1),
        "draw_prob": round(draws, 1),
        "away_win_prob": round(away_wins, 1),
        "under_35_goals_prob": round(under_35_goals, 1),
        "corners_over_55": round(over_55_corners, 1),
        "corners_over_85": round(over_85_corners, 1),
        "corners_over_105": round(over_105_corners, 1),
        "cards_over_35": round(over_35_cards, 1),
        "shots_over_75": round(over_75_shots, 1)
    }

# Web Scraping en tiempo real para contexto táctico, clima, estadio y arbitraje
def fetch_web_context(match_query):
    try:
        url = f"https://html.duckduckgo.com/html/?q={match_query}+football+stadium+referee+injuries+weather"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        response = requests.get(url, headers=headers, timeout=6)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            snippets = [a.get_text() for a in soup.find_all("a", class_="result__snippet")[:4]]
            return " ".join(snippets)
    except Exception as e:
        logger.error(f"Error en web scraping: {e}")
    return "No se capturó contexto web externo adicional; el análisis se basará en modelos estadísticos y simulación avanzada."

# Generación del Informe de 11 Puntos mediante Google Gemini 2.5 Flash
def generate_ai_report(match_name, context, mc_data):
    if not client:
        return "⚠️ Error crítico: La API Key de Gemini não está configurada correctamente en el sistema."
    
    prompt = f"""
    Actúa como un tipster profesional de élite, científico de datos deportivos y analista táctico financiero. 
    Analiza con máximo rigor el siguiente evento: '{match_name}'.
    
    Contexto web, estadio, arbitraje y actualidad reciente: {context}
    Resultados del Motor de Simulación Monte Carlo (100,000 iteraciones): {mc_data}

    Debes generar estrictamente un **Informe Técnico de Apuestas de 11 Puntos** orientado a encontrar las opciones más viables y rentables, considerando obligatoriamente la localía profunda, el aforo/presión del estadio y la conducta arbitral:

    1. **Análisis de Estado de Forma y Tendencia de Localía**: Dinámica reciente evaluando qué equipo se "crece" o hace un fortín en su estadio (rendimiento como local) frente al comportamiento del visitante (si es un equipo sólido fuera de casa o si le afecta severamente la presión del aforo contrario).
    2. **Impacto Meteorológico y Clima (Incidencia Directa)**: Temperatura, lluvia, viento o humedad y su efecto físico en el césped y ritmo del encuentro.
    3. **Estadísticas Avanzadas y xG (Goles Esperados)**: Producción ofensiva subyacente y solidez defensiva real.
    4. **Resultados de Simulaciones Monte Carlo**: Probabilidades matemáticas brutas (1X2, distribución de goles y viabilidad de mercados como Under 3.5).
    5. **Mercados Secundarios (Esquinas 5.5 - 10.5, Tarjetas y Tiros a Puerta)**: Evaluación cuantitativa estricta basada en las simulaciones secundarias.
    6. **Factores Tácticos, Presión de Estadio, Lesiones y Árbitro**: Análisis del peso del aforo del estadio, perfil disciplinario y tendencia de amonestaciones del **árbitro** designado, ausencias y pizarra de los cuerpos técnicos.
    7. **Valor Esperado (EV) y Cuotas Estimadas**: Cálculo matemático del Value Bet cruzando probabilidades reales vs mercado.
    8. **Criterio de Kelly (Gestión de Bankroll Profesional)**: Porcentaje exacto de stake institucional recomendado para asegurar rentabilidad a largo plazo.
    9. **Apuesta Principal "Single" (Alta Viabilidad y Probabilidad)**: Selección quirúrgica de la opción más sólida y rentable detectada en todo el análisis (ej: Menos de 3.5 goles, Doble Oportunidad, etc.).
    10. **Apuesta "Combinada Escalada" (Diversificación Estable)**: Propuesta de combinada de baja o media correlación diseñada para potenciar beneficios protegiendo el bankroll.
    11. **Conclusión, Veredicto y Advertencia de Riesgo Profesional**: Sentencia final de inversión con directrices estrictas de control de varianza.

    Mantén un formato impecable, estructurado con negritas, viñetas y un lenguaje formal, analítico y directo a la rentabilidad.
    """
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        return response.text
    except Exception as e:
        logger.error(f"Error al invocar a Gemini API: {e}")
        return "⚠️ Ocurrió un error al procesar el análisis con la IA. Por favor intenta de nuevo en unos segundos."

# Interfaz y Manejador de Mensajes en Telegram
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_id = str(update.message.from_user.id)
    
    if len(text) < 3 or text.lower() in [".", "/start", "hola", "ayuda", "menu"]:
        welcome_message = (
            "⚽ **¡Sistema Profesional de Apuestas de Fútbol Activo!**\n\n"
            "Para ejecutar el motor completo de análisis (100k Simulaciones Monte Carlo + Web Scraping de Estadio/Árbitro + IA Gemini 2.5 Flash), "
            "por favor escribe directamente el enfrentamiento que deseas analizar.\n\n"
            "📋 **Ejemplos recomendados:**\n"
            "• *Getafe vs Celta de Vigo*\n"
            "• *Real Madrid vs Barcelona*\n"
            "• *Manchester City vs Arsenal*\n\n"
            "💡 *Tip profesional:* El bot evalúa localía, peso del aforo, árbitro, clima, viabilidad de mercados y Criterio de Kelly."
        )
        await update.message.reply_text(welcome_message, parse_mode="Markdown")
        return

    try:
        conn = sqlite3.connect("bot_betting.db")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO queries (user_id, query_text) VALUES (?, ?)", (user_id, text))
        conn.commit()
        conn.close()
    except Exception as db_err:
        logger.error(f"Error guardando consulta en BD: {db_err}")

    await update.message.reply_text(f"⚙️ **Iniciando pipeline analítico para:** _{text}_\n🔄 Recopilando clima, estadio, árbitro y ejecutando 100,000 simulaciones...")

    web_ctx = fetch_web_context(text)
    mc_results = run_monte_carlo()
    report = generate_ai_report(text, web_ctx, mc_results)

    if len(report) > 4000:
        for i in range(0, len(report), 4000):
            await update.message.reply_text(report[i:i+4000], parse_mode="Markdown")
    else:
        await update.message.reply_text(report, parse_mode="Markdown")

def run_telegram_bot():
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN no configurado en el entorno.")
        return
    
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    logger.info("Bot de Telegram iniciado correctamente en hilo secundario.")
    application.run_polling(drop_pending_updates=True)

# Lanzar el bot en un hilo secundario para no bloquear el servidor web de Streamlit
if "bot_thread" not in st.session_state:
    st.session_state.bot_thread = True
    threading.Thread(target=run_telegram_bot, daemon=True).s_start()
