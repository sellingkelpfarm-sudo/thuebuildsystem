import discord
from discord.ext import commands
import os
import asyncio

# Khởi tạo Intents (Cần thiết để đọc tin nhắn và thành viên)
intents = discord.Intents.default()
intents.message_content = True  # Quan trọng để đọc nội dung tin nhắn bank
intents.members = True          # Để tìm khách hàng trong server

# Khởi tạo Bot
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f'---')
    print(f'Logged in as: {bot.user.name}')
    print(f'ID: {bot.user.id}')
    print(f'---')
    # Set trạng thái cho bot
    await bot.change_presence(activity=discord.Game(name="Building Services"))

async def load_extensions():
    # Load file thuebuildsystem.py (đảm bảo file nằm cùng thư mục)
    try:
        await bot.load_extension("thuebuildsystem")
        print("✅ Đã nạp thành công hệ thống Thuê Build")
    except Exception as e:
        print(f"❌ Lỗi khi nạp hệ thống: {e}")

async def main():
    async with bot:
        await load_extensions()
        # Lấy Token từ biến môi trường (Environment Variable) của Railway
        token = os.getenv("DISCORD_TOKEN")
        if token:
            await bot.start(token)
        else:
            print("❌ Lỗi: Chưa cấu hình DISCORD_TOKEN trong Variables của Railway!")

if __name__ == "__main__":
    asyncio.run(main())
