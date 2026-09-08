import os
import gc
import sqlite3
import threading
from flask import Flask
import numpy as np
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, 
    ContextTypes, 
    CommandHandler, 
    MessageHandler, 
    CallbackQueryHandler,
    filters
)
from google import genai
import requests

# ==========================================
# 1. BASE DE DATOS PERSONALIZADA DE LIGAS
# ==========================================
LEAGUES_DATABASE = {
    "LIGAS_FOCO_PERSONALIZADAS": [
        "🇸🇦 Arabia Saudita: Saudi Pro League",
        "🇪🇺 Internacionales: UEFA Champions League, Copa Libertadores, Copa Sudamericana",
        "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Inglaterra: Premier League, EFL Championship, EFL Cup & FA Cup",
        "🇪🇸 España: LaLiga & Copa del Rey",
        "🇮🇹 Italia: Serie A & Coppa Italia",
        "🇩🇪 Alemania: Bundesliga 2",
        "🇫🇷 Francia: Ligue 1 & Coupe de France",
        "🇨🇴 Colombia: Liga BetPlay Dimayor",
        "🇳🇴 Noruega: Eliteserien & Copa",
        "🇳🇱 Países Bajos: Eredivisie & Copa",
        "🇩🇰 Dinamarca: Superliga & Copa",
        "🇵🇱 Polonia: Ekstraklasa & Copa",
        "🇵🇹 Portugal: Primeira Liga & Copa",
        "🇸🇪 Suecia: Allsvenskan & Copa",
        "🇹🇷 Turquía: Süper Lig & Copa",
        "🇨🇭 Suiza: Super League & Copa",
        "🇭🇷 Croacia: HNL & Copa",
        "🏴󠁧󠁢󠁳󠁣󠁴󠁿 Escocia: Premiership & Copa",
        "🇧🇬 Bulgaria: Primera Liga",
        "🇦🇹 Austria: Bundesliga",
        "🇧🇪 Bélgica: Jupiler Pro League",
        "🇨🇳 China: Super League"
    ]
}

# ==========================================
# 2. SERVIDOR WEB KEEP-ALIVE (RENDER)
# ==========================================
web_app = Flask(__name__)

@web_app.route('/')
def health_check():
    return "Bot de Telegram activo y respondiendo 24/7", 200

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port)

# ==========================================
# 3. CONFIGURACIÓN DE APIS Y BASE DE DATOS
# ==========================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

client_gemini = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

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
# 4. MONTE CARLO OPTIMIZADO EN MEMORIA (512MB RAM)
# ==========================================
def run_monte_carlo(lambda_home=1.5, lambda_away=1.2, sims=100000):
    np.random.seed(42)
    # Uso de float32 e uint8 para minimizar el consumo de memoria en Render
    home_goals = np.random.poisson(lambda_home, sims).astype(np.uint8)
    away_goals = np.random.poisson(lambda_away, sims).astype(np.uint8)
    
    home_wins = np.mean(home_goals > away_goals) * 100
    draws = np.mean(home_goals == away_goals) * 100
    away_wins = np.mean(home_goals < away_goals) * 100
    
    total_goals = home_goals + away_goals
    under_35 = np.mean(total_goals < 3.5) * 100
    
    corners = np.random.poisson(9.5, sims).astype(np.uint8)
    over_85_corners = np.mean(corners > 8.5) * 100
    
    cards = np.random.poisson(4.5, sims).astype(np.uint8)
    over_35_cards = np.mean(cards > 3.5) * 100
    
    # Liberar memoria explícitamente
    del home_goals, away_goals, total_goals, corners, cards
    gc.collect()
    
    return {
        "home_win_prob": round(float(home_wins), 1),
        "draw_prob": round(float(draws), 1),
        "away_win_prob": round(float(away_wins), 1),
        "under_35_goals_prob": round(float(under_35), 1),
        "corners_over_85": round(float(over_85_corners), 1),
        "cards_over_35": round(float(over_35_cards), 1)
    }

# ==========================================
# 5. SISTEMA MULTI-IA FALLBACK (GEMINI + GROQ)
# ==========================================
def call_groq_api(prompt):
    if not GROQ_API_KEY:
        return None
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7
    }
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=25)
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
    except Exception as e:
        print(f"Error llamando a Groq: {e}")
    return None

def generate_ai_report(user_prompt_input, mc_data):
    leagues_formatted = "\n- ".join(LEAGUES_DATABASE['LIGAS_FOCO_PERSONALIZADAS'])
    
    prompt = f"""
    Actúa como un tipster profesional de élite, científico de datos y analista financiero especializado en fútbol internacional. 
    Analiza con máximo rigor táctico la consulta ingresada por el usuario: '{user_prompt_input}'.
    
    Toma en cuenta las siguientes ligas y copas prioritarias del usuario para contextualizar adecuadamente la competición:
    - {leagues_formatted}

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
    
    # Intento 1: Gemini 2.5 Flash
    if client_gemini:
        try:
            res = client_gemini.models.generate_content(model='gemini-2.5-flash', contents=prompt)
            if res and res.text:
                return res.text
        except Exception as e:
            print(f"Gemini 2.5 saturado o con error: {e}. Probando Groq...")

    # Intento 2: Groq (Llama 3.3 70B)
    groq_res = call_groq_api(prompt)
    if groq_res:
        return groq_res

    # Intento 3: Gemini 2.0 Flash (Respaldo final)
    if client_gemini:
        try:
            res = client_gemini.models.generate_content(model='gemini-2.0-flash', contents=prompt)
            if res and res.text:
                return res.text
        except Exception as e:
            print(f"Gemini 2.0 saturado: {e}")

    return "⚠️ Todos los proveedores de IA están temporalmente saturados. Intenta de nuevo en unos segundos."

# ==========================================
# 6. HANDLERS Y LÓGICA DE TELEGRAM
# ==========================================
def get_main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("⚽ ¿Cómo analizar un partido?", callback_data="help_analyze")],
        [InlineKeyboardButton("📊 Formatos y Cuotas admitidos", callback_data="help_formats")],
        [InlineKeyboardButton("🏆 Ver Mis Ligas y Copas Foco", callback_data="help_leagues")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "⚽ *ELITE BETTING HUB - BOT ANALISTA DE FÚTBOL*\n\n"
        "¡Hola! Soy tu asistente de análisis cuantitativo e IA. Puedes comunicarte conmigo de múltiples formas:\n\n"
        "• *Por equipo:* `Bodø/Glimt` o `¿Cómo viene Dinamo Zagreb?`\n"
        "• *Por partido:* `Celtic vs Rangers`\n"
        "• *Con Cuotas:* `Galatasaray vs Fenerbahce L:2.10 E:3.20 V:3.50`\n\n"
        "¿Qué deseas realizar hoy? Elige una opción o escribe directamente tu consulta:"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=get_main_menu_keyboard())

async def handle_button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "help_analyze":
        text = (
            "📌 *¿Cómo analizar?*\n\n"
            "Escribe directamente el nombre del partido o equipo en el chat.\n"
            "Ejemplo: `Real Madrid vs Barcelona` o solo `Al Hilal`."
        )
    elif query.data == "help_formats":
        text = (
            "📊 *Formatos Aceptados*\n\n"
            "Puedes incluir cuotas explícitas para calcular el Valor Esperado (EV):\n"
            "• `Copenhagen vs Brøndby`\n"
            "• `Copenhagen vs Brøndby local 2.10 empate 3.50 visita 2.90`\n"
            "• `Analiza al Malmö para este fin de semana`"
        )
    elif query.data == "help_leagues":
        foco_str = "\n".join([f"• {item}" for item in LEAGUES_DATABASE["LIGAS_FOCO_PERSONALIZADAS"]])
        text = f"🔥 *LIGAS Y COPAS FOCO CONFIGURADAS*\n\n{foco_str}"
    else:
        text = "Selecciona una opción válida."

    await query.message.reply_text(text, parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw_text = update.message.text.strip()
    text_lower = raw_text.lower()
    
    greeting_triggers = ["hola", "buenas", "hello", "hi", "inicio", "start", ".", "ayuda", "menu", "opciones"]
    
    if text_lower in greeting_triggers or len(raw_text) <= 2:
        await update.message.reply_text(
            "👋 ¡Hola! ¿En qué puedo ayudarte hoy? Selecciona una opción o escribe directamente tu consulta:",
            reply_markup=get_main_menu_keyboard()
        )
        return

    await update.message.reply_text("🔄 Procesando datos, ejecutando simulación Monte Carlo y redactando informe táctico... Por favor espera.")
    
    mc_data = run_monte_carlo()
    report = generate_ai_report(raw_text, mc_data)
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO queries (league, query_text, report) VALUES (?, ?, ?)", ("Telegram User", raw_text, report))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error al guardar consulta: {e}")
    
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
        
    threading.Thread(target=run_web_server, daemon=True).start()
    
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_button_click))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    print("🤖 Bot de Telegram e hilo Web iniciados correctamente...")
    app.run_polling()
