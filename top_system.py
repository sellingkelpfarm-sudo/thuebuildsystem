import discord
from discord.ext import commands
import json
import os
from datetime import datetime

# Đường dẫn file lưu trữ (Bạn có thể đổi thành .db nếu muốn dùng SQLite sau này)
DATA_FILE = "top_orders.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except:
                return {}
    return {}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

class TopSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    def update_top(user_id, amount):
        """Hàm dùng chung để cộng dồn tiền từ cả Bank và Card"""
        data = load_data()
        u_id = str(user_id)
        data[u_id] = data.get(u_id, 0) + amount
        save_data(data)

    @commands.command(name="topbuild")
    async def topbuild(self, ctx):
        """Hiển thị bảng xếp hạng đại gia thuê build theo phong cách sang trọng"""
        data = load_data()
        if not data:
            return await ctx.send("🚀 *Hiện chưa có dữ liệu vinh danh, hãy trở thành người đầu tiên!*")

        # Sắp xếp 10 người chi đậm nhất
        sorted_top = sorted(data.items(), key=lambda item: item[1], reverse=True)[:10]

        embed = discord.Embed(
            title="✨ 🏆 BẢNG VÀNG ĐẠI GIA ĐÃ THUÊ BUILD - LOTUSS'S SHOP 🏆 ✨", 
            description=(
                "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n"
                "💎 *Nơi vinh danh những vị khách hàng thân thiết,\n"
                "đã luôn đồng hành và ủng hộ Shop hết mình.*\n"
                "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬"
            ), 
            color=0xf1c40f, # Màu vàng Gold cực sang
            timestamp=datetime.now()
        )

        medals = ["🥇", "🥈", "🥉", "👤", "👤", "👤", "👤", "👤", "👤", "👤"]
        top_list = ""

        for i, (u_id, total) in enumerate(sorted_top):
            user_mention = f"<@{u_id}>"
            money = f"{int(total):,}" # Định dạng 100,000
            
            if i == 0: # QUÁN QUÂN
                top_list += f"⭐ {medals[i]} **QUÁN QUÂN: {user_mention}**\n┗ 💰 Tổng chi: `{money} VND`\n\n"
            elif i < 3: # TOP 2, 3
                top_list += f"{medals[i]} **Top {i+1}: {user_mention}**\n┗ 💸 Tổng chi: `{money} VND`\n\n"
            else: # TOP 4-10
                top_list += f"🔹 `Top {i+1:02d}` | {user_mention} | `{money} VND`\n"

        embed.add_field(name="✨ DANH SÁCH VINH DANH ✨", value=top_list, inline=False)
        
        # Footer kèm ảnh avatar bot
        embed.set_footer(
            text=f"🕒 Cập nhật lúc: {datetime.now().strftime('%H:%M - %d/%m/%Y')}",
            icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None
        )
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(TopSystem(bot))