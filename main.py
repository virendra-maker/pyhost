import os
import logging
import asyncio
import sqlite3
import aiosqlite
import subprocess
import sys
import psutil
import shutil
from datetime import datetime
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

# Paths
DB_PATH = "bot_database.db"
HOSTED_DIR = "hosted_bots"
LOGS_DIR = "logs"

os.makedirs(HOSTED_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

# Database Setup
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                role TEXT DEFAULT 'member',
                is_banned INTEGER DEFAULT 0
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS hosted_apps (
                app_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                app_name TEXT,
                path TEXT,
                status TEXT DEFAULT 'stopped',
                pid INTEGER
            )
        ''')
        # Add initial admins
        await db.execute("INSERT OR IGNORE INTO users (user_id, role) VALUES (?, 'admin')", (OWNER_ID,))
        await db.execute("INSERT OR IGNORE INTO users (user_id, role) VALUES (?, 'admin')", (ADMIN_ID,))
        await db.commit()

# Middleware/Checks
async def is_team_member(user_id):
    if user_id == OWNER_ID or user_id == ADMIN_ID:
        return True
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT 1 FROM users WHERE user_id = ? AND is_banned = 0", (user_id,)) as cursor:
            return await cursor.fetchone() is not None

# Command Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not await is_team_member(user.id):
        await update.message.reply_text("❌ Access Denied. This bot is for private team use only.")
        return

    await update.message.reply_text(
        f"🚀 Welcome {user.first_name} to PyHost Team Panel!\n\n"
        "Commands:\n"
        "📂 Send any .py file to host it\n"
        "/apps - List your hosted apps\n"
        "/stop <app_id> - Stop an app\n"
        "/start_app <app_id> - Start an app\n"
        "/delete <app_id> - Delete an app\n"
        "/status - System status"
    )

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not await is_team_member(user.id): return

    doc = update.message.document
    if not doc.file_name.endswith('.py'):
        await update.message.reply_text("❌ Please send a .py file.")
        return

    app_name = doc.file_name
    user_dir = os.path.join(HOSTED_DIR, str(user.id))
    os.makedirs(user_dir, exist_ok=True)
    
    file_path = os.path.join(user_dir, app_name)
    new_file = await context.bot.get_file(doc.file_id)
    await new_file.download_to_drive(file_path)

    await update.message.reply_text(f"📥 Received {app_name}. Analyzing dependencies...")

    # Auto-install modules (simple regex check for imports)
    try:
        with open(file_path, 'r') as f:
            content = f.read()
            import_lines = [line for line in content.split('\n') if line.startswith('import ') or line.startswith('from ')]
            modules = []
            for line in import_lines:
                parts = line.split()
                if parts[0] == 'import':
                    modules.append(parts[1].split('.')[0])
                elif parts[0] == 'from':
                    modules.append(parts[1].split('.')[0])
            
            unique_modules = list(set(modules))
            # Filter out standard libraries (simplified)
            std_libs = ['os', 'sys', 'time', 'datetime', 'json', 're', 'math', 'random', 'asyncio', 'logging', 'sqlite3']
            to_install = [m for m in unique_modules if m not in std_libs]

            if to_install:
                await update.message.reply_text(f"📦 Installing: {', '.join(to_install)}")
                subprocess.check_call([sys.executable, "-m", "pip", "install"] + to_install)

    except Exception as e:
        await update.message.reply_text(f"⚠️ Dependency check failed: {e}")

    # Register in DB
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO hosted_apps (user_id, app_name, path, status) VALUES (?, ?, ?, ?)",
            (user.id, app_name, file_path, 'stopped')
        )
        await db.commit()
        async with db.execute("SELECT last_insert_rowid()") as cursor:
            app_id = (await cursor.fetchone())[0]

    await update.message.reply_text(f"✅ App registered with ID: {app_id}. Use /start_app {app_id} to run it.")

async def start_app(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_team_member(update.effective_user.id): return
    if not context.args:
        await update.message.reply_text("Usage: /start_app <app_id>")
        return

    app_id = int(context.args[0])
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = sqlite3.Row
        async with db.execute("SELECT * FROM hosted_apps WHERE app_id = ? AND user_id = ?", (app_id, update.effective_user.id)) as cursor:
            app = await cursor.fetchone()

    if not app:
        await update.message.reply_text("❌ App not found.")
        return

    if app['status'] == 'running':
        await update.message.reply_text("ℹ️ App is already running.")
        return

    # Start process
    log_file = os.path.join(LOGS_DIR, f"app_{app_id}.log")
    with open(log_file, "w") as f:
        process = subprocess.Popen([sys.executable, app['path']], stdout=f, stderr=f)
    
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE hosted_apps SET status = 'running', pid = ? WHERE app_id = ?", (process.pid, app_id))
        await db.commit()

    await update.message.reply_text(f"🚀 App {app['app_name']} started (PID: {process.pid}).")

async def stop_app(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_team_member(update.effective_user.id): return
    if not context.args:
        await update.message.reply_text("Usage: /stop <app_id>")
        return

    app_id = int(context.args[0])
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = sqlite3.Row
        async with db.execute("SELECT * FROM hosted_apps WHERE app_id = ? AND user_id = ?", (app_id, update.effective_user.id)) as cursor:
            app = await cursor.fetchone()

    if not app or app['status'] == 'stopped':
        await update.message.reply_text("❌ App is not running.")
        return

    try:
        parent = psutil.Process(app['pid'])
        for child in parent.children(recursive=True):
            child.terminate()
        parent.terminate()
        await update.message.reply_text(f"🛑 App {app['app_name']} stopped.")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Error stopping app: {e}")

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE hosted_apps SET status = 'stopped', pid = NULL WHERE app_id = ?", (app_id,))
        await db.commit()

async def list_apps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_team_member(update.effective_user.id): return
    
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = sqlite3.Row
        async with db.execute("SELECT * FROM hosted_apps WHERE user_id = ?", (update.effective_user.id,)) as cursor:
            apps = await cursor.fetchall()

    if not apps:
        await update.message.reply_text("📭 No apps hosted yet.")
        return

    msg = "📂 Your Hosted Apps:\n\n"
    for app in apps:
        msg += f"ID: {app['app_id']} | {app['app_name']} | Status: {app['status']}\n"
    
    await update.message.reply_text(msg)

async def delete_app(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_team_member(update.effective_user.id): return
    if not context.args:
        await update.message.reply_text("Usage: /delete <app_id>")
        return

    app_id = int(context.args[0])
    # Stop first if running
    await stop_app(update, context)

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = sqlite3.Row
        async with db.execute("SELECT path FROM hosted_apps WHERE app_id = ?", (app_id,)) as cursor:
            app = await cursor.fetchone()
            if app:
                if os.path.exists(app['path']):
                    os.remove(app['path'])
                await db.execute("DELETE FROM hosted_apps WHERE app_id = ?", (app_id,))
                await db.commit()
                await update.message.reply_text("🗑️ App deleted.")
            else:
                await update.message.reply_text("❌ App not found.")

async def system_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_team_member(update.effective_user.id): return
    
    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory().percent
    disk = psutil.disk_usage('/').percent
    
    await update.message.reply_text(
        f"🖥️ System Status:\n"
        f"CPU: {cpu}%\n"
        f"RAM: {ram}%\n"
        f"Disk: {disk}%"
    )

# Main
async def main():
    await init_db()
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("apps", list_apps))
    application.add_handler(CommandHandler("start_app", start_app))
    application.add_handler(CommandHandler("stop", stop_app))
    application.add_handler(CommandHandler("delete", delete_app))
    application.add_handler(CommandHandler("status", system_status))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    
    logger.info("PyHost Team Bot started...")
    await application.run_polling()

if __name__ == '__main__':
    asyncio.run(main())
