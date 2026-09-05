import os
import random
import math
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

def calcular_kelly(probabilidad: float, cuota: float) -> float:
    """Calcula el porcentaje óptimo del bankroll usando el Criterio de Kelly."""
    p = probabilidad / 100.0
    q = 1.0 - p
    b = cuota - 1.0
    if b <= 0:
        return 0.0
    kelly = (p * cuota - 1.0) / b
    return max(0.0, kelly)

def simular_y_analizar_kelly(lambda_local: float, lambda_visitante: float, simulaciones: int = 100000):
    def poisson_val(lmbda):
        L = math.exp(-lmbda)
        k = 0
        p = 1.0
        while p > L:
            k += 1
            p *= random.random()
        return k - 1

    victorias_l, victorias_v, empates, over_25, under_25 = 0, 0, 0, 0, 0

    for _ in range(simulaciones):
        gl = poisson_val(lambda_local)
        gv = poisson_val(lambda_visitante)

        if gl > gv:
            victorias_l += 1
        elif gv > gl:
            victorias_v += 1
        else:
            empates += 1

        if (gl + gv) > 2.5:
            over_25 += 1
        else:
            under_25 += 1

    p_local = (victorias_l / simulaciones) * 100
    p_visitante = (victorias_v / simulaciones) * 100
    p_empate = (empates / simulaciones) * 100
    p_over = (over_25 / simulaciones) * 100
    p_under = (under_25 / simulaciones) * 100

    # Estimación de cuotas de mercado basadas en la probabilidad real
    cuota_local = round(100 / max(p_local, 1.0), 2)
    cuota_over = round(100 / max(p_over, 1.0), 2)
    cuota_visitante = round(100 / max(p_visitante, 1.0), 2)

    # Aplicación del Criterio de Kelly con un bankroll base de 1,000,000 COP
    bankroll = 1000000.0

    # Evaluamos Kelly para Local
    f_kelly_local = calcular_kelly(p_local, cuota_local)
    monto_kelly_local = bankroll * f_kelly_local

    # Evaluamos Kelly para Más de 2.5 Goles
    f_kelly_over = calcular_kelly(p_over, cuota_over)
    monto_kelly_over = bankroll * f_kelly_over

    return {
        "p_local": p_local,
        "p_empate": p_empate,
        "p_visitante": p_visitante,
        "p_over": p_over,
        "cuota_local": cuota_local,
        "cuota_over": cuota_over,
        "monto_local": monto_kelly_local,
        "monto_over": monto_kelly_over,
        "f_local": f_kelly_local * 100,
        "f_over": f_kelly_over * 100
    }

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bienvenida = (
        "🤖 **Bot Financiero con Monte Carlo y Criterio de Kelly**\n\n"
        "Para analizar un partido y calcular la inversión de tu millón, usa:\n"
        "`/analizar [GolesLocal] [GolesVisitante]`\n\n"
        "Ejemplo:\n"
        "`/analizar 1.7 1.0`"
    )
    await update.message.reply_text(bienvenida, parse_mode="Markdown")

async def analizar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("⚠️ Faltan datos. Usa el formato: `/analizar 1.7 1.0`", parse_mode="Markdown")
        return

    try:
        l_local = float(args[0])
        l_visitante = float(args[1])
    except ValueError:
        await update.message.reply_text("❌ Los goles deben ser números válidos (ejemplo: 1.5).")
        return

    await update.message.reply_text("⏳ Ejecutando 100,000 simulaciones y aplicando Criterio de Kelly...", parse_mode="Markdown")

    res = simular_y_analizar_kelly(l_local, l_visitante)

    # Determinamos la mejor opción para la inversión única del millón y parley
    if res["p_local"] >= res["p_over"]:
        inversion_sugerida = f"🏠 **Victoria Local**\n• Cuota estimada de valor: `{res['cuota_local']}`\n• Porcentaje Kelly: `{res['f_local']:.1f}%`\n• 💰 **Monto sugerido de tu millón:** `${res['monto_local']:,.0f} COP`"
    else:
        inversion_sugerida = f"📈 **Más de 2.5 Goles**\n• Cuota estimada de valor: `{res['cuota_over']}`\n• Porcentaje Kelly: `{res['f_over']:.1f}%`\n• 💰 **Monto sugerido de tu millón:** `${res['monto_over']:,.0f} COP`"

    respuesta = (
        f"📊 **REPORTE DE VALOR & KELLY (100k Simulaciones)**\n\n"
        f"⚽ Goles base: Local ({l_local}) vs Visitante ({l_visitante})\n"
        f"• Prob. Local: `{res['p_local']:.1f}%` (Cuota: `{res['cuota_local']}`)\n"
        f"• Prob. Empate: `{res['p_empate']:.1f}%`\n"
        f"• Prob. Visitante: `{res['p_visitante']:.1f}%`\n"
        f"• Prob. Más de 2.5: `{res['p_over']:.1f}%` (Cuota: `{res['cuota_over']}`)\n\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 **APUESTA DE VALOR PRINCIPAL (Inversión 1M):**\n"
        f"{inversion_sugerida}\n\n"
        f"🔗 **SUGERENCIA PARA PARLEY:**\n"
        f"• Combinar Victoria Local (`{res['cuota_local']}`) con Más de 2.5 Goles (`{res['cuota_over']}`) para buscar cuotas altas (2.80 - 3.50)."
    )

    await update.message.reply_text(respuesta, parse_mode="Markdown")

def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("Error: No se encontró el TELEGRAM_BOT_TOKEN")
        return

    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("analizar", analizar))

    print("¡Bot con Criterio de Kelly y Simulaciones activo!")
    # IMPORTANTE: stop_signals=None se mantiene para evitar el error de hilos en el servidor
    app.run_polling(stop_signals=None)

if __name__ == "__main__":
    main()
