import os
import sqlite3
import threading
from flask import Flask
import numpy as np
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from google import genai

# ==========================================
# 1. SERVIDOR WEB SECUNDARIO (KEEP-ALIVE)
# ==========================================
web_app = Flask(__name__)

@web_app.route('/')
def health_check():
    return "Bot de Telegram activo y respondiendo 24/7", 200

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port)

# ==========================================
# 2. CONFIGURACIÓN Y BASE DE DATOS
# ==========================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

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
    except Exception as e:
        print(f"Error inicializando BD: {e}")

init_db()

# ==========================================
# 3. LÓGICA DE MONTE CARLO E IA
# ==========================================
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
        "home_win_prob": round(float(home_wins), 1),
        "draw_prob": round(float(draws), 1),
        "away_win_prob": round(float(away_wins), 1),
        "under_35_goals_prob": round(float(under_35), 1),
        "corners_over_85": round(float(over_85_corners), 1),
        "cards_over_35": round(float(over_35_cards), 1)
    }

def generate_ai_report(match_name, mc_data):
    if not client:
        return "⚠️ Error crítico: API Key de Gemini no configurada en las variables de entorno."
    
    prompt = f"""
    Actúa como un tipster profesional de élite, científico de datos y analista financiero especializado en fútbol internacional. 
    Analiza con máximo rigor táctico el evento solicitado: '{match_name}'.
    Resultados de Simulación Monte Carlo (100k iteraciones): {mc_data}

    Genera strictly un **Informe Técnico de Apuestas de los 11 Puntos Oficiales**:
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
    
    models_to_try = ['gemini-2.5-flash', 'gemini-2.0-flash']
    for model in models_to_try:
        try:
            response = client.models.generate_content(model=model, contents=prompt)
            if response and response.text:
                return response.text
        except Exception as e:
            print(f"Error con modelo {model}: {e}")
            continue
    return "⚠️ Servidores temporalmente saturados. Intenta de nuevo en unos segundos."

# ==========================================
# 4. HANDLERS Y LÓGICA DE TELEGRAM
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_message = (
        "⚽ *ELITE BETTING HUB - TELEGRAM BOT*\n\n"
        "¡Bienvenido! Escribe directamente el partido que deseas analizar.\n"
        "Ejemplo: `Real Madrid vs Manchester City`\n\n"
        "El bot procesará la simulación Monte Carlo y el informe táctico para ti."
    )
    await update.message.reply_text(welcome_message, parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    match_input = update.message.text
    await update.message.reply_text("🔄 Ejecutando simulación Monte Carlo y redactando informe táctico con IA... Por favor espera.")
    
    mc_data = run_monte_carlo()
    report = generate_ai_report(match_input, mc_data)
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO queries (league, query_text, report) VALUES (?, ?, ?)", ("Telegram User", match_input, report))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error al guardar consulta: {e}")
    
    # Manejo seguro de límite de caracteres de Telegram (4096)
    max_length = 4000
    if len(report) > max_length:
        chunks = [report[i:i+max_length] for i in range(0, len(report), max_length)]
        for chunk in chunks:
            await update.message.reply_text(chunk)
    else:
        await update.message.reply_text(report)

if __name__ == "__main__":
    if not TELEGRAM_BOT_TOKEN:
        print("❌ Error: Debes configurar la variable de entorno TELEGRAM_BOT_TOKEN.")
        exit(1)
        
    # Iniciar servidor web en hilo secundario
    threading.Thread(target=run_web_server, daemon=True).start()
    
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    print("🤖 Bot de Telegram e hilo Web iniciados correctamente...")
    app.run_polling()
