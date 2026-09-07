import os
import sqlite3
import numpy as np
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from google import genai

# Configuración de credenciales (asegúrate de ponerlas en las variables de entorno de Render o aquí)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AQ.Ab8RN6Jo81flfXoPq_GNMrK6en-xQl70mm0vo0LCQerIuCPgGA")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "TU_TOKEN_DE_TELEGRAM_AQUI")

client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

BASE_DIR = os.path.dirname(os.path.abspath(__file__)) if '__file__' in locals() else "."
DB_PATH = os.path.join(BASE_DIR, "bot_betting.db")

def init_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS queries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                league TEXT,
                query_text TEXT,
                report TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()
    except Exception:
        pass

init_db()

def run_monte_carlo(lambda_home=1.5, lambda_away=1.2, sims=100000):
    np.random.seed(42)
    home_goals = np.random.poisson(lambda_home, sims)
    away_goals = np.random.poisson(lambda_away, sims)
    home_wins = np.mean(home_goals > away_goals) * 100
    draws = np.mean(home_goals == away_goals) * 100
    away_wins = np.mean(home_goals < away_goals) * 100
    total_goals = home_goals + away_goals
    under_35 = np.mean(total_goals < 3.5) * 100
    corners = np.random.poisson(9.5, sims)
    over_85_corners = np.mean(corners > 8.5) * 100
    cards = np.random.poisson(4.5, sims)
    over_35_cards = np.mean(cards > 3.5) * 100
    return {
        "home_win_prob": round(home_wins, 1),
        "draw_prob": round(draws, 1),
        "away_win_prob": round(away_wins, 1),
        "under_35_goals_prob": round(under_35, 1),
        "corners_over_85": round(over_85_corners, 1),
        "cards_over_35": round(over_35_cards, 1)
    }

def generate_ai_report(match_name, mc_data):
    if not client:
        return "⚠️ Error crítico: API Key no configurada."
    
    prompt = f"""
    Actúa como un tipster profesional de élite, científico de datos y analista financiero especializado en fútbol internacional. 
    Analiza con máximo rigor táctico el evento solicitado: '{match_name}'.
    Resultados de Simulación Monte Carlo (100k iteraciones): {mc_data}

    Genera estrictamente un **Informe Técnico de Apuestas de los 11 Puntos Oficiales**:
    1. Análisis de Estado de Forma y Localía.
    2. Impacto Meteorológico y Clima.
    3. Estadísticas Avanzadas y xG específicos.
    4. Resultados de Simulaciones Monte Carlo.
    5. Mercados Secundarios (Esquinas, Tarjetas, Tiros).
    6. Factores Tácticos y Árbitro.
    7. Valor Esperado (EV) y Cuotas Estimadas.
    8. Criterio de Kelly (Gestión de Bankroll).
    9. Apuesta Principal "Single".
    10. Apuesta "Combinada Escalada".
    11. Conclusión, Veredicto y Advertencia de Riesgo.
    """
    
    models_to_try = ['gemini-2.0-flash', 'gemini-3.7-flash']
    for model in models_to_try:
        try:
            response = client.models.generate_content(model=model, contents=prompt)
            return response.text
        except Exception:
            continue
    return "⚠️ Servidores temporalmente saturados. Intenta de nuevo en unos segundos."

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_message = (
        "⚽ *ELITE BETTING HUB - TELEGRAM BOT*\n\n"
        "¡Bienvenido! Escribe directamente el partido que deseas analizar.\n"
        "Ejemplo: `Real Madrid vs Manchester City`\n\n"
        "El bot procesará la simulación Monte Carlo y el informe táctico de 11 puntos para ti."
    )
    await update.message.reply_text(welcome_message, parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    match_input = update.message.text
    await update.message.reply_text("🔄 Ejecutando simulación Monte Carlo y redactando informe táctico con IA... Por favor espera un momento.")
    
    # Procesamiento cuantitativo y de IA
    mc_data = run_monte_carlo()
    report = generate_ai_report(match_input, mc_data)
    
    # Guardar en base de datos SQLite local
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO queries (league, query_text, report) VALUES (?, ?, ?)", ("Telegram User", match_input, report))
        conn.commit()
        conn.close()
    except Exception:
        pass
    
    # Telegram tiene un límite de 4096 caracteres por mensaje. Si el informe es muy largo, lo partimos o lo enviamos por bloques.
    if len(report) > 4000:
        for i in range(0, len(report), 4000):
            await update.message.reply_text(report[i:i+4000])
    else:
        await update.message.reply_text(report)

if __name__ == "__main__":
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "TU_TOKEN_DE_TELEGRAM_AQUI":
        print("❌ Error: Debes configurar tu TELEGRAM_BOT_TOKEN.")
        exit(1)
        
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    print("🤖 Bot de Telegram iniciado correctamente...")
    app.run_polling()
