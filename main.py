import discord
from discord.ext import commands
import os

TOKEN = os.getenv("TOKEN")
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"🤖 Bot Thuê Build đã sẵn sàng: {bot.user}")
    await bot.load_extension("thuebuildsystem")

if __name__ == "__main__":
    bot.run(TOKEN)