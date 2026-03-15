import discord
from discord.ext import commands
import os
import asyncio

# --- KHỞI TẠO INTENTS ---
intents = discord.Intents.default()
intents.message_content = True 
intents.members = True          

# --- KHỞI TẠO BOT ---
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f'---')
    print(f'Đã đăng nhập thành công: {bot.user.name}')
    print(f'ID Bot: {bot.user.id}')
    print(f'---')
    await bot.change_presence(activity=discord.Game(name="Building Services"))

async def load_extensions():
    """Tải các file hệ thống (Cogs)"""
    extensions = [
        "thuebuildsystem", 
        "thuebuildcard_system", # Đã thêm dấu phẩy ở đây
        "top_system"
    ]
    
    for ext in extensions:
        try:
            await bot.load_extension(ext)
            print(f"✅ Đã nạp thành công hệ thống: {ext}")
        except Exception as e:
            print(f"❌ Lỗi khi nạp hệ thống {ext}: {e}")

async def main():
    async with bot:
        await load_extensions()
        token = os.getenv("DISCORD_TOKEN")
        if token:
            await bot.start(token)
        else:
            print("❌ LỖI: Chưa tìm thấy DISCORD_TOKEN trong cấu hình Railway!")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot đã dừng.")
