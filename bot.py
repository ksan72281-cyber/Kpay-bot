import os
import re
import json
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATA_FILE = "transactions.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def extract_kpay_amount(text):
    patterns = [
        r'(?:လွှဲငွေ|ငွေပမာဏ|Amount|Transferred|Total)[:\s]+([0-9,]+)\s*(?:Ks|MMK|ကျပ်|K)',
        r'([0-9,]+)\s*(?:Ks|MMK|ကျပ်)(?!\d)',
    ]
    txn_patterns = [
        r'(?:Transaction\s*ID|Txn\s*ID|Ref\.?\s*No|ကိုးကားနံပါတ်)[:\s]*([A-Za-z0-9\-]+)',
        r'(?:TXN|REF|KPay)[A-Za-z0-9]{6,}',
    ]
    amount = None
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            amount_str = match.group(1).replace(",", "")
            try:
                amount = int(amount_str)
                break
            except ValueError:
                continue
    txn_id = None
    for pattern in txn_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            txn_id = match.group(0)
            txn_id = re.sub(r'(?:Transaction\s*ID|Txn\s*ID|Ref\.?\s*No|ကိုးကားနံပါတ်)[:\s]*', '', txn_id, flags=re.IGNORECASE).strip()
            break
    if not txn_id and amount:
        import hashlib
        txn_id = "MSG_" + hashlib.md5(text.encode()).hexdigest()[:10].upper()
    return amount, txn_id

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "👋 မင်္ဂလာပါ! KPay ပြေစာ ခြေရာခံ Bot ထဲကြိုဆိုပါတယ်။\n\n"
        "📋 အသုံးပြုနည်း:\n"
        "• KPay ပြေစာ SMS ကို ဒီ chat ထဲ paste လုပ်ပါ\n"
        "• Bot က ငွေပမာဏ ထုတ်ယူပြီး ပေါင်းပေးမည်\n"
        "• ထပ်တူပြေစာများ အလိုအလျောက် ဖယ်ရှားမည်\n\n"
        "⚙️ Commands:\n"
        "/total - စုစုပေါင်း ကြည့်ရှုရန်\n"
        "/list - ပြေစာများ စာရင်းကြည့်ရန်\n"
        "/reset - စာရင်းပယ်ဖျက်ရန်"
    )
    await update.message.reply_text(msg)

async def show_total(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    data = load_data()
    chat_data = data.get(chat_id, {"transactions": [], "total": 0})
    total = chat_data.get("total", 0)
    count = len(chat_data.get("transactions", []))
    msg = (
        f"💰 စုစုပေါင်း: {total:,} Ks\n"
        f"📝 ပြေစာ အရေအတွက်: {count} ခု"
    )
    await update.message.reply_text(msg)

async def show_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    data = load_data()
    chat_data = data.get(chat_id, {"transactions": [], "total": 0})
    transactions = chat_data.get("transactions", [])
    if not transactions:
        await update.message.reply_text("📭 ပြေစာ မရှိသေးပါ။")
        return
    lines = ["📋 ပြေစာ စာရင်း:\n"]
    for i, txn in enumerate(transactions[-20:], 1):
        lines.append(f"{i}. {txn['amount']:,} Ks  [{txn['id'][:12]}...]")
    if len(transactions) > 20:
        lines.append(f"\n... နှင့် နောက်ထပ် {len(transactions)-20} ခု")
    lines.append(f"\n💰 စုစုပေါင်း: {chat_data['total']:,} Ks")
    await update.message.reply_text("\n".join(lines))

async def reset_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    data = load_data()
    data[chat_id] = {"transactions": [], "total": 0}
    save_data(data)
    await update.message.reply_text("🗑️ စာရင်း ရှင်းလင်းပြီးပါပြီ။")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    text = update.message.text
    chat_id = str(update.effective_chat.id)
    amount, txn_id = extract_kpay_amount(text)
    if not amount:
        return
    data = load_data()
    if chat_id not in data:
        data[chat_id] = {"transactions": [], "total": 0}
    chat_data = data[chat_id]
    existing_ids = [t["id"] for t in chat_data["transactions"]]
    if txn_id in existing_ids:
        await update.message.reply_text(
            f"⚠️ ဤပြေစာ မှတ်တမ်းတင်ပြီးသားဖြစ်သည်!\n"
            f"💰 လက်ရှိ စုစုပေါင်း: {chat_data['total']:,} Ks"
        )
        return
    chat_data["transactions"].append({"id": txn_id, "amount": amount})
    chat_data["total"] = chat_data.get("total", 0) + amount
    save_data(data)
    await update.message.reply_text(
        f"✅ ထည့်သွင်းပြီးပါပြီ!\n"
        f"💵 ဤပြေစာ: +{amount:,} Ks\n"
        f"💰 စုစုပေါင်း: {chat_data['total']:,} Ks\n"
        f"📝 ပြေစာ အရေအတွက်: {len(chat_data['transactions'])} ခု"
    )

def main():
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise ValueError("BOT_TOKEN environment variable မသတ်မှတ်ထားပါ!")
    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("total", show_total))
    app.add_handler(CommandHandler("list", show_list))
    app.add_handler(CommandHandler("reset", reset_data))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Bot စတင်လည်ပတ်နေပါသည်...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
