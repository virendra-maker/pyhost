# PyHost Telegram Bot

A professional, production-ready Telegram bot with a user system, credit system, admin panel, and force join functionality.

## Features
- **User System**: Auto-registration, profile management.
- **Credit System**: Limited credits for free users, unlimited for premium.
- **Premium System**: Admin-managed premium status with expiry.
- **Admin Panel**: Stats, broadcast, user management (ban/unban, credits, premium).
- **Force Join**: Ensures users join a specific channel before using the bot.
- **Railway Ready**: Pre-configured for easy deployment on Railway.app.

## Setup Instructions

### 1. Local Setup
1. Clone the repository.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create a `.env` file based on `.env.example` and fill in your credentials.
4. Run the bot:
   ```bash
   python main.py
   ```

### 2. Railway Deployment
1. Connect your GitHub repository to Railway.
2. Add the environment variables from your `.env` file to the Railway project settings.
3. Railway will automatically detect the `railway.json` and `requirements.txt` to build and deploy the bot.

## Environment Variables
- `BOT_TOKEN`: Your Telegram Bot API token.
- `OWNER_ID`: Your Telegram User ID (Main Admin).
- `ADMIN_ID`: Secondary Admin User ID.
- `YOUR_USERNAME`: Your Telegram username for support/sales.
- `UPDATE_CHANNEL`: Link to your Telegram update channel.
- `PORT`: Port for the bot (default: 8080).

## Database
The bot uses **SQLite** by default (`bot_database.db`). The schema is automatically created on the first run.

## License
MIT
