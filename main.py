import discord
from discord.ext import commands
from fastapi import FastAPI
import uvicorn
import asyncio
import threading
import os

# 1. Khởi tạo FastAPI và Bot
app = FastAPI()
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# 2. Hàm để các file khác có thể nạp Cog
async def load_extensions():
    # Nạp file hệ thống của bạn (bỏ đuôi .py)
    await bot.load_extension("thuebuildcard_system")

@bot.event
async def on_ready():
    print(f"✅ Bot {bot.user} đã Online!")

async def run_fastapi():
    config = uvicorn.Config(app, host="0.0.0.0", port=8080)
    server = uvicorn.Server(config)
    await server.serve()

async def main():
    async with bot:
        await load_extensions()
        # Chạy FastAPI trong thread riêng để không chặn Bot
        threading.Thread(target=lambda: asyncio.run(run_fastapi()), daemon=True).start()
        await bot.start(os.getenv("TOKEN"))

if __name__ == "__main__":
    asyncio.run(main())
