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

    cuota_local = round(100 / max(p_local, 1.0), 2)
    cuota_over = round(100 / max(p_over, 1.0), 2)

    bankroll = 1000000.0
    f_kelly_local = calcular_kelly(p_local, cuota_local)
    monto_kelly_local = bankroll * f_kelly_local

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
        "🤖 **Bot Financiero de Apuestas Inteligentes**\n\n"
        "¡Ya estoy conectado y libre de bloqueos!\n"
        "Escríbeme lo que quieras analizar o pásame los goles esperados (ej: `1.8 1.1`)."
    )
    await update.message.reply_text(bienvenida, parse_mode="Markdown")

async def procesar_mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto_usuario = update.message.text
    palabras = texto_usuario.split()
    l_local, l_visitante = 1.6, 1.1 
    
    try:
        if len(palabras) >= 2:
            numeros = [float(p) for p in palabras if p.replace('.', '', 1).isdigit()]
            if len(numeros) >= 2:
                l_local = numeros[0]
                l_visitante = numeros[1]
    except ValueError:
        pass

    await update.message.reply_text(
        f"🧠 Analizando solicitud: *'{texto_usuario}'*...\n"
        f"⏳ Ejecutando 100,000 simulaciones y aplicando Criterio de Kelly...", 
        parse_mode="Markdown"
    )

    res = simular_y_analizar_kelly(l_local, l_visitante)

    if res["p_local"] >= res["p_over"]:
        inversion_sugerida = f"🏠 **Victoria Local**\n• Cuota estimada: `{res['cuota_local']}`\n• Porcentaje Kelly: `{res['f_local']:.1f}%`\n• 💰 **Inversión sugerida de tu millón:** `${res['monto_local']:,.0f} COP`"
    else:
        inversion_sugerida = f"📈 **Más de 2.5 Goles**\n• Cuota estimada: `{res['cuota_over']}`\n• Porcentaje Kelly: `{res['f_over']:.1f}%`\n• 💰 **Inversión sugerida de tu millón:** `${res['monto_over']:,.0f} COP`"

    respuesta = (
        f"📊 **REPORTE FINANCIERO & INTELIGENTE**\n\n"
        f"⚽ Simulación (100k iteraciones):\n"
        f"• Local: `{res['p_local']:.1f}%` (Cuota: `{res['cuota_local']}`)\n"
        f"• Empate: `{res['p_empate']:.1f}%`\n"
        f"• Visitante: `{res['p_visitante']:.1f}%`\n"
        f"• Más de 2.5 Goles: `{res['p_over']:.1f}%` (Cuota: `{res['cuota_over']}`)\n\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 **APUESTA ÚNICA RECOMENDADA (1M COP):**\n"
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
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), procesar_mensaje))

    print("¡Bot inteligente operando con éxito!")
    app.run_polling(stop_signals=None)

if __name__ == "__main__":
    main()
