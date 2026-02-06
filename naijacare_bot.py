import os
import json
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

# Load environment variables
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# Load hospitals or symptoms data
try:
    with open("hospitals.json", "r") as f:
        hospitals_data = json.load(f)
except FileNotFoundError:
    hospitals_data = {}
    print("⚠️ hospitals.json not found. Bot will run but may not reply with data.")

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hello! I am NaijaCare AI 🤖\nSend me your symptoms or location and I will try to help."
    )

# Message handler
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.lower()
    
    # Simple check if symptom matches hospital data
    response = "Sorry, I don't have an answer yet 🤷‍♂️"
    for key, value in hospitals_data.items():
        if key.lower() in user_text:
            response = f"{value}"
            break
    
    await update.message.reply_text(response)

# Main function
def main():
    # Create Telegram bot application
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    # Run bot
    print("✅ NaijaCare AI is running...")
    app.run_polling()

# Correct _name_ check
if _name_ == "_main_":
    main()
