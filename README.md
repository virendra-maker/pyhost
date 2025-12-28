# PyHost Team Private Hosting Bot

An advanced, private Telegram bot designed for team use. It allows team members to upload Python bot codes, which are then automatically hosted, managed, and run with auto-dependency installation.

## 🚀 Features
- **Private Team Use**: Restricted to specific IDs (Owner & Admin).
- **Auto-Hosting**: Send any `.py` file to the bot, and it will save it.
- **Auto-Dependency Installer**: Automatically detects `import` statements and installs missing modules via `pip`.
- **Process Management**: Start, stop, and delete hosted apps via commands.
- **System Monitoring**: Check CPU, RAM, and Disk usage.
- **Multi-App Support**: Host multiple bots simultaneously.

## 🛠️ Commands
- `/start` - Welcome message and command list.
- `/apps` - List all your hosted applications and their status.
- `/start_app <id>` - Start a specific application.
- `/stop <id>` - Stop a running application.
- `/delete <id>` - Remove an application and its files.
- `/status` - View system resource usage.
- **File Upload**: Simply send a `.py` file to register it for hosting.

## 📦 Setup
1. **Environment Variables**:
   - `BOT_TOKEN`: Your Telegram Bot Token.
   - `OWNER_ID`: Main team leader ID.
   - `ADMIN_ID`: Secondary team admin ID.
   - `UPDATE_CHANNEL`: Your team's update channel.
   - `YOUR_USERNAME`: Support contact.

2. **Deployment**:
   - Deploy on Railway or any VPS.
   - The bot will create a `hosted_bots` folder to store uploaded codes and a `logs` folder for app outputs.

## ⚠️ Security Note
This bot is for **private team use only**. It executes uploaded Python code, so ensure only trusted team members have access.

## License
MIT
