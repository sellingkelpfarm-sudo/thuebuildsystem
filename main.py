import discord
from discord.ext import commands
import os
import threading
import uvicorn
from thuebuildcard_system import app # Import app FastAPI từ file card system của bạn

TOKEN = os.getenv("TOKEN")
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"🤖 Bot Thuê Build đã sẵn sàng: {bot.user}")
    # Load các extension
    try:
        await bot.load_extension("thuebuildsystem")
        await bot.load_extension("thuebuildcard_system")
    except Exception as e:
        print(f"❌ Lỗi khi load extension: {e}")

# Hàm để chạy bot trong một luồng riêng
def run_bot():
    bot.run(TOKEN)

if __name__ == "__main__":
    # Chạy Bot ở luồng phụ (background)
    threading.Thread(target=run_bot, daemon=True).start()
    
    # Chạy FastAPI (Web Server) ở luồng chính để nhận callback
    # Port 8000 là port mặc định thường dùng cho các dịch vụ web
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
