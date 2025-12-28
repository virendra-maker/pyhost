import os
import logging
import asyncio
import sqlite3
import aiosqlite
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    CallbackQueryHandler,
)

# Load environment variables
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))
ADMIN_ID = int(os.getenv("ADMIN_ID"))
UPDATE_CHANNEL = os.getenv("UPDATE_CHANNEL")
YOUR_USERNAME = os.getenv("YOUR_USERNAME")
PORT = int(os.getenv("PORT", 8080))

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Database Setup
DB_PATH = "bot_database.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                join_date TEXT,
                role TEXT DEFAULT 'free',
                credits INTEGER DEFAULT 3,
                premium_expiry TEXT,
                is_banned INTEGER DEFAULT 0
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS admins (
                user_id INTEGER PRIMARY KEY
            )
        ''')
        # Add initial admins
        await db.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (OWNER_ID,))
        await db.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (ADMIN_ID,))
        await db.commit()

# Helper Functions
async def is_admin(user_id):
    if user_id == OWNER_ID:
        return True
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,)) as cursor:
            return await cursor.fetchone() is not None

async def check_force_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # This is a simplified check. In production, you'd use context.bot.get_chat_member
    # For now, we assume the user needs to join the channel in the .env
    channel_username = UPDATE_CHANNEL.split('/')[-1]
    try:
        member = await context.bot.get_chat_member(chat_id=f"@{channel_username}", user_id=update.effective_user.id)
        if member.status in ['member', 'administrator', 'creator']:
            return True
    except Exception as e:
        logger.error(f"Error checking force join: {e}")
    return False

async def get_user(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = sqlite3.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            return await cursor.fetchone()

async def register_user(user_id, username):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, username, join_date) VALUES (?, ?, ?)",
            (user_id, username, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        await db.commit()

# Command Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await register_user(user.id, user.username)
    
    if not await check_force_join(update, context):
        keyboard = [[InlineKeyboardButton("Join Channel", url=UPDATE_CHANNEL)],
                    [InlineKeyboardButton("I have joined", callback_data="check_join")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"Welcome {user.first_name}! To use this bot, you must join our update channel.",
            reply_markup=reply_markup
        )
        return

    await update.message.reply_text(
        f"Hello {user.first_name}! Welcome to the PyHost Bot.\n"
        "Use /help to see available commands."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "Available Commands:\n"
        "/start - Start the bot\n"
        "/profile - View your profile and credits\n"
        "/buy - Premium information\n"
        "/help - Show this message\n"
    )
    if await is_admin(update.effective_user.id):
        help_text += (
            "\nAdmin Commands:\n"
            "/stats - Bot statistics\n"
            "/broadcast <msg> - Send message to all users\n"
            "/addpremium <id> <days> - Add premium to user\n"
            "/givecredits <id> <amt> - Give credits to user\n"
            "/ban <id> - Ban a user\n"
            "/unban <id> - Unban a user\n"
        )
    await update.message.reply_text(help_text)

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = await get_user(update.effective_user.id)
    if not user_data:
        await update.message.reply_text("Please /start the bot first.")
        return

    status = "Premium 🌟" if user_data['role'] == 'premium' else "Free"
    expiry = user_data['premium_expiry'] if user_data['premium_expiry'] else "N/A"
    
    profile_text = (
        f"👤 Profile: {update.effective_user.first_name}\n"
        f"🆔 ID: {user_data['user_id']}\n"
        f"🎭 Role: {status}\n"
        f"💰 Credits: {user_data['credits']}\n"
        f"📅 Joined: {user_data['join_date']}\n"
        f"⏳ Premium Expiry: {expiry}"
    )
    await update.message.reply_text(profile_text)

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buy_text = (
        "💎 Premium Benefits:\n"
        "- Unlimited Credits\n"
        "- Priority Support\n"
        "- Ad-free experience\n\n"
        "To buy premium, contact: " + YOUR_USERNAME
    )
    await update.message.reply_text(buy_text)

# Admin Handlers
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id): return
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cursor:
            total_users = (await cursor.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM users WHERE role = 'premium'") as cursor:
            premium_users = (await cursor.fetchone())[0]
            
    await update.message.reply_text(f"📊 Bot Stats:\nTotal Users: {total_users}\nPremium Users: {premium_users}")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id): return
    if not context.args:
        await update.message.reply_text("Usage: /broadcast <message>")
        return
    
    msg = " ".join(context.args)
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM users") as cursor:
            users = await cursor.fetchall()
            
    count = 0
    for user in users:
        try:
            await context.bot.send_message(chat_id=user[0], text=f"📢 BROADCAST:\n\n{msg}")
            count += 1
        except Exception:
            pass
    await update.message.reply_text(f"✅ Broadcast sent to {count} users.")

async def add_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id): return
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /addpremium <user_id> <days>")
        return
    
    target_id = int(context.args[0])
    days = int(context.args[1])
    expiry_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET role = 'premium', premium_expiry = ? WHERE user_id = ?",
            (expiry_date, target_id)
        )
        await db.commit()
    
    await update.message.reply_text(f"✅ User {target_id} is now Premium for {days} days.")

async def give_credits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id): return
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /givecredits <user_id> <amount>")
        return
    
    target_id = int(context.args[0])
    amount = int(context.args[1])
    
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET credits = credits + ? WHERE user_id = ?", (amount, target_id))
        await db.commit()
    
    await update.message.reply_text(f"✅ Added {amount} credits to user {target_id}.")

async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id): return
    if not context.args:
        await update.message.reply_text("Usage: /ban <user_id>")
        return
    
    target_id = int(context.args[0])
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (target_id,))
        await db.commit()
    await update.message.reply_text(f"🚫 User {target_id} has been banned.")

async def unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id): return
    if not context.args:
        await update.message.reply_text("Usage: /unban <user_id>")
        return
    
    target_id = int(context.args[0])
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET is_banned = 0 WHERE user_id = ?", (target_id,))
        await db.commit()
    await update.message.reply_text(f"✅ User {target_id} has been unbanned.")

# Callback Query Handler
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "check_join":
        if await check_force_join(update, context):
            await query.edit_message_text("Thank you for joining! You can now use the bot. Type /start to begin.")
        else:
            await query.message.reply_text("You haven't joined yet! Please join the channel first.")

# Main function
async def main():
    await init_db()
    
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("profile", profile))
    application.add_handler(CommandHandler("buy", buy))
    
    # Admin Handlers
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(CommandHandler("addpremium", add_premium))
    application.add_handler(CommandHandler("givecredits", give_credits))
    application.add_handler(CommandHandler("ban", ban_user))
    application.add_handler(CommandHandler("unban", unban_user))
    
    application.add_handler(CallbackQueryHandler(button_callback))
    
    logger.info("Bot started...")
    await application.run_polling()

if __name__ == '__main__':
    asyncio.run(main())
