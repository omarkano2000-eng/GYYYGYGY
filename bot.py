import json
import logging
import os
from flask import Flask
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# ============ KEEP ALIVE (خدعة لإبقاء Render شغال) ============
web_app = Flask('')

@web_app.route('/')
def home():
    return "Bot is running successfully!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.start()
# ==============================================================

# ============ CONFIG ============
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "5746591255"))

PROOFS_LINK = "@Card_cvvl"
SUPPORT_LINK = "@Card_cvvl"
WELCOME_IMG_URL = "https://i.postimg.cc/W3wqHpRY/C38048D5-D90A-4621-9042-EBF53C2C03CF.png"

WALLETS = {"usdt_bep20": "0x85a8c35aD7c9CfB7812269a6E597bDaAC3d9Bd2E"}
PAY_METHODS = {"usdt_bep20": "USDT (BEP20)"}

PRICES = {
    "visa":    {"10": 5,  "25": 11, "50": 20, "100": 38},
    "master":  {"10": 5,  "25": 11, "50": 20, "100": 38},
    "non_vbv": {"50": 50},
}

# ============ STORAGE ============
DATA_FILE = "data.json"
COUPONS = {}
ORDERS = []

def load_data():
    global COUPONS, ORDERS
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                COUPONS = data.get("coupons", {})
                ORDERS = data.get("orders", [])
        except (json.JSONDecodeError, OSError):
            COUPONS, ORDERS = {}, []

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump({"coupons": COUPONS, "orders": ORDERS}, f, ensure_ascii=False, indent=2)

def validate_coupon(code: str):
    code = code.strip().upper()
    if code not in COUPONS: return False, 0, "❌ الكود غير صحيح."
    c = COUPONS[code]
    if not c["active"]: return False, 0, "❌ الكود موقوف."
    if c["used"] >= c["max_uses"]: return False, 0, "❌ الكود خلصت استخداماته."
    return True, c["percent"], f"✅ تم تطبيق خصم {c['percent']}%"

CARD_TYPE, AMOUNT, COUPON, PAYMENT = range(4)

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    welcome_text = ("👋 <b>أهلاً بك في Card.cvvl</b>\n\nالحل الأول والأسرع لبطاقات الدفع الرقمية والاشتراكات 🌍\n\n✅ <b>تسليم فوري</b>\n✅ <b>ضمان استبدال</b>\n✅ <b>دعم فني 24/7</b>\n\nاختر من القائمة أدناه للبدء:")
    kb = [
        [InlineKeyboardButton("🛒 شراء بطاقة الآن", callback_data="buy")],
        [InlineKeyboardButton("💰 عرض الأسعار", callback_data="prices")],
        [InlineKeyboardButton("✅ الإثباتات (Vouches)", callback_data="proofs")],
        [InlineKeyboardButton("📞 تواصل مع الدعم", callback_data="support")],
    ]
    try:
        await update.message.reply_photo(photo=WELCOME_IMG_URL, caption=welcome_text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
        return
    except Exception as e: logging.error(f"Error sending image: {e}")
    await update.message.reply_text(welcome_text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

async def prices(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = "💳 <b>قائمة الأسعار:</b>\n\n"
    for ctype, tiers in PRICES.items():
        name = ctype.replace("_", " ").upper()
        text += f"<b>{name}</b>\n"
        for amt, price in tiers.items(): text += f"  • {amt}$ → {price}$\n"
        text += "\n"
    text += "💵 <b>الدفع:</b> USDT (BEP20)\n🎟️ عندك كوبون خصم؟ استخدمه وقت الشراء."
    await update.callback_query.message.reply_text(text, parse_mode="HTML")

async def proofs(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.message.reply_text(f"✅ <b>شاهد إثباتات زبائننا:</b>\n{PROOFS_LINK}\n\nكل بطاقة يتم فحصها قبل التسليم، مع ضمان استبدال فوري في حال وجود أي خلل.", parse_mode="HTML")

async def support(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.message.reply_text(f"📞 <b>تحتاج مساعدة؟</b>\nتواصل معنا مباشرة: {SUPPORT_LINK}\n\nفريقنا جاهز للرد على استفساراتك في أي وقت.", parse_mode="HTML")

async def buy_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    try: await q.answer()
    except: pass
    kb = [
        [InlineKeyboardButton("💳 Visa", callback_data="visa"), InlineKeyboardButton("💳 MasterCard", callback_data="master")],
        [InlineKeyboardButton("🔥 Non VBV", callback_data="non_vbv")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back_to_start")]
    ]
    await q.message.reply_text("💳 <b>اختر نوع البطاقة التي تحتاجها:</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    return CARD_TYPE

async def card_type(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    try: await q.answer()
    except: pass
    if q.data == "back_to_start":
        class FakeMessage:
            def __init__(self, msg): self.message = msg
        await start(FakeMessage(q.message), ctx)
        return ConversationHandler.END
    ctx.user_data["type"] = q.data
    tiers = PRICES[q.data]
    kb = [[InlineKeyboardButton(f"{amt}$ — {price}$", callback_data=amt)] for amt, price in tiers.items()]
    kb.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_to_start")])
    await q.message.reply_text("💰 <b>اختر المبلغ:</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    return AMOUNT

async def amount(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    try: await q.answer()
    except: pass
    if q.data == "back_to_start":
        class FakeMessage:
            def __init__(self, msg): self.message = msg
        await start(FakeMessage(q.message), ctx)
        return ConversationHandler.END
    ctx.user_data["amount"] = q.data
    ctx.user_data["base_price"] = PRICES[ctx.user_data["type"]][q.data]
    ctx.user_data["coupon"] = None
    ctx.user_data["percent"] = 0
    await q.message.reply_text("🎟️ <b>هل لديك كود خصم؟</b>\nاكتب الكود هنا، أو اضغط /skip للمتابعة بدون كوبون.", parse_mode="HTML")
    return COUPON

async def coupon_input(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    code = update.message.text
    ok, percent, msg = validate_coupon(code)
    if not ok:
        await update.message.reply_text(f"{msg}\nجرّب كود آخر، أو اضغط /skip.")
        return COUPON
    ctx.user_data["coupon"] = code.strip().upper()
    ctx.user_data["percent"] = percent
    await update.message.reply_text(msg)
    return await ask_payment(update, ctx)

async def coupon_skip(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("تمام، سنكمل بدون كوبون.")
    return await ask_payment(update, ctx)

async def ask_payment(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    kb = [[InlineKeyboardButton(f"💵 {label}", callback_data=key)] for key, label in PAY_METHODS.items()]
    target = update.message if update.message else update.callback_query.message
    await target.reply_text("💳 <b>اختر طريقة الدفع:</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    return PAYMENT

async def payment(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    try: await q.answer()
    except Exception: pass
    if "base_price" not in ctx.user_data or "type" not in ctx.user_data:
        await q.message.reply_text("⚠️ انتهت صلاحية الجلسة. يرجى إرسال /start والمحاولة مرة أخرى.")
        return ConversationHandler.END
    ctx.user_data["pay"] = q.data
    d = ctx.user_data
    user_id = q.from_user.id
    username = q.from_user.username or "no_username"
    base = d["base_price"]
    percent = d["percent"]
    final = round(base * (1 - percent / 100), 2)
    order = {"id": len(ORDERS) + 1, "user_id": user_id, "username": username, "type": d["type"], "amount": d["amount"], "base": base, "coupon": d["coupon"], "percent": percent, "final": final, "pay": d["pay"], "status": "pending"}
    ORDERS.append(order)
    if d["coupon"]: COUPONS[d["coupon"]]["used"] += 1
    save_data()
    wallet_address = WALLETS.get(d["pay"], "⚠️ No wallet available")
    pay_name = PAY_METHODS[d["pay"]]
    coupon_line = f"🎟️ كوبون: {d['coupon']} (-{percent}%)\n" if d["coupon"] else ""
    card_name = d["type"].replace("_", " ").upper()
    admin_msg = (f"🆕 طلب #{order['id']}\n\n👤 @{username} ({user_id})\n💳 {card_name} — {d['amount']}$\n💵 الأصلي: {base}$\n{coupon_line}✅ المطلوب: {final}$\n💳 الدفع: {pay_name}\n")
    try: await ctx.bot.send_message(ADMIN_ID, admin_msg)
    except Exception as e: logging.error(f"Failed to send admin message: {e}")
    user_msg = (f"✅ <b>تم استلام طلبك #{order['id']} بنجاح!</b>\n\n💵 <b>المبلغ المطلوب:</b> {final}$\n\n💳 <b>تفاصيل الدفع:</b>\nأرسل مبلغ {final}$ من نوع {pay_name} إلى العنوان التالي:\n<code>{wallet_address}</code>\n\n⚠️ <b>تنبيه:</b> تأكد أنك ترسل عبر شبكة <b>BEP20 (BSC)</b> فقط.\n\n🔹 <b>بعد إتمام التحويل، أرسل لنا صورة التحويل أو رقم العملية (TXID) هنا.</b>")
    try: await q.message.reply_text(user_msg, parse_mode="HTML")
    except Exception as e:
        logging.error(f"Failed to send user message: {e}")
        await q.message.reply_text(f"عنوان المحفظة:\n{wallet_address}")
    return ConversationHandler.END

async def cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("تم إلغاء العملية. أرسل /start للبدء من جديد.")
    return ConversationHandler.END

def admin_only(func):
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_ID: return
        return await func(update, ctx)
    return wrapper

@admin_only
async def addcoupon(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try: code, percent, max_uses = ctx.args; percent, max_uses = int(percent), int(max_uses)
    except (ValueError, IndexError):
        await update.message.reply_text("استخدام: /addcoupon CODE PERCENT MAX_USES\nمثال: /addcoupon SALE15 15 50"); return
    code = code.upper(); COUPONS[code] = {"percent": percent, "max_uses": max_uses, "used": 0, "active": True}
    save_data(); await update.message.reply_text(f"✅ أضفت {code} — خصم {percent}% × {max_uses}.")

@admin_only
async def listcoupons(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not COUPONS: await update.message.reply_text("ما في كوبونات."); return
    text = "🎟️ الكوبونات:\n\n"
    for code, c in COUPONS.items(): text += f"{'🟢' if c['active'] else '🔴'} {code} — {c['percent']}% — {c['used']}/{c['max_uses']}\n"
    await update.message.reply_text(text)

@admin_only
async def delcoupon(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args: await update.message.reply_text("استخدام: /delcoupon CODE"); return
    code = ctx.args[0].upper()
    if code in COUPONS: del COUPONS[code]; save_data(); await update.message.reply_text(f"🗑️ حذفت {code}.")
    else: await update.message.reply_text("الكود غير موجود.")

@admin_only
async def orders(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ORDERS: await update.message.reply_text("ما في طلبات."); return
    text = "آخر 10 طلبات:\n\n"
    for o in ORDERS[-10:]: text += f"#{o['id']} — @{o['username']} — {o['type'].replace('_', ' ').upper()} {o['amount']}$ — {o['final']}$ — {o['status']}\n"
    await update.message.reply_text(text)

@admin_only
async def markdone(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args: await update.message.reply_text("استخدام: /done ORDER_ID"); return
    try: oid = int(ctx.args[0])
    except ValueError: await update.message.reply_text("آي دي غير صالح."); return
    for o in ORDERS:
        if o["id"] == oid: o["status"] = "delivered"; save_data(); await update.message.reply_text(f"✅ الطلب #{oid} صار delivered."); return
    await update.message.reply_text("الطلب غير موجود.")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logging.error(msg="Exception while handling an update:", exc_info=context.error)

def main():
    keep_alive() # تشغيل خدعة إبقاء Render مستيقظاً
    load_data()
    app = Application.builder().token(TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(buy_start, pattern="^buy$")],
        states={CARD_TYPE: [CallbackQueryHandler(card_type)], AMOUNT: [CallbackQueryHandler(amount)], COUPON: [MessageHandler(filters.TEXT & ~filters.COMMAND, coupon_input), CommandHandler("skip", coupon_skip)], PAYMENT: [CallbackQueryHandler(payment)]},
        fallbacks=[CommandHandler("cancel", cancel)], per_message=False 
    )
    app.add_handler(CommandHandler("start", start)); app.add_handler(CommandHandler("addcoupon", addcoupon))
    app.add_handler(CommandHandler("listcoupons", listcoupons)); app.add_handler(CommandHandler("delcoupon", delcoupon))
    app.add_handler(CommandHandler("orders", orders)); app.add_handler(CommandHandler("done", markdone))
    app.add_handler(CallbackQueryHandler(prices, pattern="^prices$")); app.add_handler(CallbackQueryHandler(proofs, pattern="^proofs$"))
    app.add_handler(CallbackQueryHandler(support, pattern="^support$")); app.add_handler(conv)
    app.add_error_handler(error_handler)
    print("bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
