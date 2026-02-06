import os
import json
import requests
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
AI_API_KEY = os.getenv("AI_API_KEY")
AI_API_URL = os.getenv("AI_API_URL")
AI_MODEL = os.getenv("AI_MODEL", "llama3-70b-8192")

HOSPITAL_DB_FILE = "hospitals.json"

# Store memory per user
user_memory = {}
user_language_mode = {}

MAX_HISTORY = 14


SYSTEM_PROMPT = """
You are NaijaCare AI, a friendly Nigerian nurse-style healthcare assistant for Nigerians.

You help users understand symptoms, give safe health guidance, and detect emergencies.

RULES:
- You are NOT a doctor.
- You do NOT confirm diagnosis.
- You do NOT prescribe antibiotics or strong drugs.
- You can suggest safe basic first aid advice.
- You must ask follow-up questions like a nurse.
- You must include warning signs and emergency advice.
- Always be calm, friendly, caring, and simple.

MEDICATION RULES:
- You can mention basic safe options like Paracetamol, ORS, hydration, rest.
- Do NOT prescribe antibiotics or injections.
- Do NOT recommend dangerous doses.
- Encourage hospital visit if severe.

EMERGENCY CONDITIONS:
If user mentions chest pain, difficulty breathing, fainting, seizure, stroke symptoms, vomiting blood,
heavy bleeding, pregnancy bleeding, severe abdominal pain, child breathing fast, respond urgently.

RESPONSE FORMAT:
- Empathy line
- Ask 3-6 short follow-up questions (age, duration, severity, fever, vomiting, pregnancy)
- Mention possible causes (not diagnosis)
- Give safe advice
- Give warning signs
- Recommend hospital visit when needed
- Add disclaimer

Always end with:
"This is guidance, not a doctor diagnosis. Please visit a hospital if symptoms persist or worsen."
"""


def load_hospitals():
    try:
        with open(HOSPITAL_DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []


def save_user_log(user_id, username, message):
    try:
        log_entry = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "user_id": user_id,
            "username": username,
            "message": message
        }
        with open("user_logs.json", "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry) + "\n")
    except Exception as e:
        print("LOG ERROR:", e)


def detect_language_switch(text: str):
    t = text.lower()

    pidgin_triggers = ["pidgin", "abeg talk pidgin", "talk pidgin", "pidgin mode", "use pidgin"]
    english_triggers = ["english mode", "switch to english", "talk english", "english"]

    for p in pidgin_triggers:
        if p in t:
            return "pidgin"

    for e in english_triggers:
        if e in t:
            return "english"

    return None


def is_emergency(text: str):
    emergency_keywords = [
        "chest pain", "heart pain", "pressure in chest",
        "difficulty breathing", "can't breathe", "cant breathe",
        "vomiting blood", "coughing blood",
        "bleeding heavily", "heavy bleeding",
        "unconscious", "fainting", "fainted",
        "seizure", "convulsion",
        "stroke", "slurred speech", "face drooping",
        "pregnancy bleeding", "pregnant and bleeding",
        "severe abdominal pain", "sharp stomach pain",
        "child breathing fast", "baby breathing fast",
        "not breathing",
        "severe burn", "burns"
    ]

    t = text.lower()
    for word in emergency_keywords:
        if word in t:
            return True
    return False


def emergency_reply(pidgin=False):
    if pidgin:
        return (
            "🚨 EMERGENCY ALERT\n\n"
            "This one fit serious.\n"
            "Abeg no waste time.\n\n"
            "✅ Go nearest hospital NOW\n"
            "✅ Call family/person wey fit help you\n"
            "✅ If you dey struggle breathe, sit upright\n"
            "❌ No take strong drug without doctor\n\n"
            "Abeg no delay."
        )

    return (
        "🚨 EMERGENCY ALERT\n\n"
        "This could be serious.\n"
        "Please do not delay.\n\n"
        "✅ Go to the nearest hospital immediately\n"
        "✅ Call a family member or someone close to help you\n"
        "✅ If you have breathing difficulty, sit upright\n"
        "❌ Avoid taking strong drugs without a doctor\n\n"
        "Please don’t delay."
    )


def hospital_search(state, area):
    hospitals = load_hospitals()
    state = state.lower().strip()
    area = area.lower().strip()

    results = []
    for h in hospitals:
        if h["state"].lower() == state and area in h["area"].lower():
            results.append(h)

    return results


def call_ai(messages):
    if not AI_API_KEY or AI_API_KEY == "PASTE_YOUR_GROQ_KEY_HERE":
        return (
            "⚠️ AI is not yet connected.\n\n"
            "Please add your Groq API key inside the .env file.\n"
            "Then restart the bot.\n\n"
            "Example:\nAI_API_KEY=gsk_xxxxxxxxxxxxx"
        )

    headers = {
        "Authorization": f"Bearer {AI_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": AI_MODEL,
        "messages": messages,
        "temperature": 0.4,
        "max_tokens": 650
    }

    response = requests.post(AI_API_URL, headers=headers, json=payload, timeout=60)
    response.raise_for_status()
    data = response.json()

    return data["choices"][0]["message"]["content"]


def build_menu(pidgin=False):
    if pidgin:
        return (
            "🩺 NaijaCare AI Menu\n\n"
            "1️⃣ Check symptoms\n"
            "2️⃣ Pregnancy support\n"
            "3️⃣ Drug information\n"
            "4️⃣ First aid / Emergency guide\n"
            "5️⃣ Find hospital near you\n"
            "6️⃣ Health tips\n\n"
            "Type any number (1-6) or type your symptoms directly.\n\n"
            "To switch back: type English mode"
        )

    return (
        "🩺 NaijaCare AI Menu\n\n"
        "1️⃣ Check symptoms\n"
        "2️⃣ Pregnancy support\n"
        "3️⃣ Drug information\n"
        "4️⃣ First aid / Emergency guide\n"
        "5️⃣ Find hospital near you\n"
        "6️⃣ Health tips\n\n"
        "Type any number (1-6) or type your symptoms directly.\n\n"
        "To use pidgin: type Abeg talk pidgin"
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username

    user_language_mode[user_id] = "english"
    user_memory[user_id] = []

    save_user_log(user_id, username, "/start")

    msg = (
        "👋 Welcome to NaijaCare AI 🩺🇳🇬\n\n"
        "I can help you check symptoms, give safe health advice, and detect emergencies.\n\n"
        "📌 Example:\n"
        "I have fever and headache for 2 days\n\n"
        "To use pidgin, type:\n"
        "Abeg talk pidgin\n\n"
        "Type /menu to see options.\n\n"
        "⚠️ Note: I am not a doctor."
    )

    await update.message.reply_text(msg, parse_mode="Markdown")


async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = user_language_mode.get(user_id, "english")

    pidgin = (lang == "pidgin")
    await update.message.reply_text(build_menu(pidgin=pidgin), parse_mode="Markdown")


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_memory[user_id] = []
    await update.message.reply_text("✅ Conversation cleared. You can start fresh now.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username
    text = update.message.text.strip()

    save_user_log(user_id, username, text)

    if user_id not in user_language_mode:
        user_language_mode[user_id] = "english"

    if user_id not in user_memory:
        user_memory[user_id] = []

    # language switching
    switch = detect_language_switch(text)
    if switch == "pidgin":
        user_language_mode[user_id] = "pidgin"
        await update.message.reply_text("No wahala 😊 I go dey reply you for pidgin from now on.")
        await update.message.reply_text(build_menu(pidgin=True), parse_mode="Markdown")
        return

    if switch == "english":
        user_language_mode[user_id] = "english"
        await update.message.reply_text("Alright 😊 I will reply in English from now on.")
        await update.message.reply_text(build_menu(pidgin=False), parse_mode="Markdown")
        return

    pidgin_mode = (user_language_mode[user_id] == "pidgin")

    # emergency detection
    if is_emergency(text):
        await update.message.reply_text(emergency_reply(pidgin=pidgin_mode), parse_mode="Markdown")
        return

    # menu shortcuts
    if text in ["1", "2", "3", "4", "5", "6"]:
        if text == "1":
            await update.message.reply_text(
                "🩺 Okay. Please describe your symptoms.\n\nExample: I have fever and headache for 2 days",
                parse_mode="Markdown"
            )
            return

        if text == "2":
            await update.message.reply_text(
                "🤰 Pregnancy support mode.\n\nTell me what you are experiencing (pain, bleeding, vomiting, dizziness, etc).",
                parse_mode="Markdown"
            )
            return

        if text == "3":
            await update.message.reply_text(
                "💊 Drug information mode.\n\nType the name of the drug (example: Paracetamol, Amatem, Flagyl).",
                parse_mode="Markdown"
            )
            return

        if text == "4":
            await update.message.reply_text(
                "🚑 First Aid / Emergency Guide:\n\n"
                "✅ If someone faints: lay them on side\n"
                "✅ If bleeding: apply pressure with clean cloth\n"
                "✅ If burns: cool with running water (not ice)\n"
                "✅ If choking: encourage coughing\n\n"
                "If condition is serious, go to hospital immediately.\n\n"
                "Type your emergency situation and I will guide you.",
                parse_mode="Markdown"
            )
            return

        if text == "5":
            await update.message.reply_text(
                "🏥 Hospital Finder\n\nPlease type like this:\n`State, Area`\n\nExample:\n`Lagos, Ikeja`",
                parse_mode="Markdown"
            )
            return

        if text == "6":
            if pidgin_mode:
                await update.message.reply_text(
                    "💡 Health Tip\n\n"
                    "Drink plenty clean water daily.\n"
                    "No dey take antibiotics anyhow.\n"
                    "Sleep well.\n"
                    "Try check BP and sugar at least once every 2-3 months.\n\n"
                    "Type /menu to continue.",
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text(
                    "💡 Health Tip\n\n"
                    "Drink enough clean water daily.\n"
                    "Avoid self-medication with antibiotics.\n"
                    "Sleep well.\n"
                    "Try to check blood pressure and sugar at least once every 2-3 months.\n\n"
                    "Type /menu to continue.",
                    parse_mode="Markdown"
                )
            return

    # hospital search format
    if "," in text and len(text.split(",")) == 2:
        state = text.split(",")[0].strip()
        area = text.split(",")[1].strip()

        results = hospital_search(state, area)
        if results:
            reply = "🏥 Hospitals found:\n\n"
            for h in results[:5]:
                reply += f"📍 {h['name']}\n{h['address']}\n📞 {h['phone']}\n\n"
            await update.message.reply_text(reply, parse_mode="Markdown")
            return

    # memory
    user_memory[user_id].append({"role": "user", "content": text})
    if len(user_memory[user_id]) > MAX_HISTORY:
        user_memory[user_id] = user_memory[user_id][-MAX_HISTORY:]

    lang_instruction = "Reply in simple Nigerian English."
    if pidgin_mode:
        lang_instruction = "Reply in Nigerian Pidgin English. Keep it respectful and clear."

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": lang_instruction},
    ] + user_memory[user_id]

    try:
        reply = call_ai(messages)

        user_memory[user_id].append({"role": "assistant", "content": reply})
        if len(user_memory[user_id]) > MAX_HISTORY:
            user_memory[user_id] = user_memory[user_id][-MAX_HISTORY:]

        await update.message.reply_text(reply)

    except Exception as e:
        print("AI ERROR:", e)
        await update.message.reply_text(
            "Sorry 😔 NaijaCare AI is having an issue right now. Please try again later."
        )


def main():
    if not TELEGRAM_TOKEN:
        print("ERROR: Telegram token missing. Add it to .env file.")
        return

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CommandHandler("reset", reset))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("✅ NaijaCare AI is running...")
    app.run_polling()


if _name_ == "_main_":

    main()
