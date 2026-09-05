import os
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("¡Hola! Ya estoy conectado y funcionando correctamente.")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto_recibido = update.message.text
    await update.message.reply_text(f"Me dijiste: {texto_recibido}")

def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("Error: No se encontró el TELEGRAM_BOT_TOKEN")
        return

    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), echo))

    print("¡El bot está arrancando y listo para escuchar!")
    app.run_polling()

if __name__ == "__main__":
    main()
