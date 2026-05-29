"""
Entry point: runs Flask web server + Discord bot concurrently.
Render runs this via: python main.py
"""
import threading
import os
from dotenv import load_dotenv

load_dotenv()

def run_web():
    from web import app
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, use_reloader=False)

def run_bot():
    from bot import bot
    bot.run(os.getenv("BOT_TOKEN"))

if __name__ == "__main__":
    # Start Flask in a background thread
    web_thread = threading.Thread(target=run_web, daemon=True)
    web_thread.start()

    # Run bot in main thread (blocking)
    run_bot()
