import discord
from discord.ext import commands
import os
import asyncio

# --- KHỞI TẠO INTENTS ---
# Cần message_content để đọc lệnh và nội dung bank
# Cần members để xác định khách hàng trong ticket
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
    # Trạng thái hiển thị của Bot
    await bot.change_presence(activity=discord.Game(name="Building Services"))

async def load_extensions():
    """Tải các file hệ thống (Cogs)"""
    # Danh sách các file .py hệ thống của bạn
    extensions = [
        "thuebuildsystem", 
        "thuebuildcardsystem"
    ]
    
    for ext in extensions:
        try:
            await bot.load_extension(ext)
            print(f"✅ Đã nạp thành công hệ thống: {ext}")
        except Exception as e:
            print(f"❌ Lỗi khi nạp hệ thống {ext}: {e}")

async def main():
    async with bot:
        # Nạp các file hệ thống trước khi chạy bot
        await load_extensions()
        
        # Lấy Token từ Variables trên Railway
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
