import discord
from discord.ext import commands
import os
import asyncio
import threading
import uvicorn
from thuebuildcard_system import app # Đảm bảo file card đã có biến app = FastAPI()

# --- CẤU HÌNH ---
TOKEN = os.getenv("TOKEN")
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"🤖 Bot Thuê Build đã sẵn sàng: {bot.user}")

# Hàm async để load các file hệ thống
async def load_extensions():
    # Danh sách các file Cog bạn muốn chạy
    extensions = ["thuebuildsystem", "thuebuildcard_system"]
    
    for ext in extensions:
        try:
            await bot.load_extension(ext)
            print(f"✅ Đã nạp thành công: {ext}")
        except Exception as e:
            print(f"❌ Lỗi khi nạp {ext}: {e}")

# Hàm chạy FastAPI
def run_api():
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

async def main():
    # 1. Nạp các file lệnh trước
    async with bot:
        await load_extensions()
        
        # 2. Chạy API ở luồng phụ (không chặn bot)
        api_thread = threading.Thread(target=run_api, daemon=True)
        api_thread.start()
        
        # 3. Chạy bot ở luồng chính
        await bot.start(TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("🛑 Đã tắt Bot.")
