import discord
from discord.ext import commands
import asyncio
import websockets
import json
import dotenv
import os
import motor.motor_asyncio
import logging

from keep_alive import keep_alive

dotenv.load_dotenv()

keep_alive()

TOKEN = os.getenv('BOT_TOKEN')
WS_URL = os.getenv('WS_URL') + '?jstudio-key=' + os.getenv('WS_TOKEN')
MONGO_URI = os.getenv('MONGO_URI')
DB_NAME = os.getenv('DB_NAME')

log_handler = logging.FileHandler(
    filename='discord.log', encoding='utf-8', mode='w')

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

mongo_client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
db = mongo_client[DB_NAME]

# Simpan target channel per guild
target_channels = {}


@bot.event
async def on_ready():
    print(f"Bot login sebagai {bot.user}")
    # Jalankan listener WebSocket di background
    bot.loop.create_task(websocket_listener())


@bot.command()
async def here(ctx):
    guild_id = str(ctx.guild.id)
    channel_id = str(ctx.channel.id)

    await db.guild_settings.update_one(
        {"guild_id": guild_id},
        {"$set": {"target_channel_id": channel_id}},
        upsert=True
    )
    await ctx.send(f"✅ Channel ini diset sebagai target event untuk server **{ctx.guild.name}**.")


async def websocket_listener():
    while True:
        try:
            async with websockets.connect(WS_URL) as ws:
                print(f"Terhubung ke GAG WebSocket")
                async for message in ws:
                    try:
                        data = json.loads(message)
                        msg = generate_discord_message(data)
                    except json.JSONDecodeError:
                        data = message

                    async for setting in db.guild_settings.find({}):
                        channel = bot.get_channel(
                            int(setting["target_channel_id"]))
                        if channel and msg is not None:
                            await channel.send("@here", embed=msg)

        except Exception as e:
            print(f"Koneksi WebSocket error: {e}")
            await asyncio.sleep(5)


def generate_discord_message(data):

    sp_egg = ['Mythical', 'Paradise', 'Bug', 'Rare']
    sp_gear = ['Grandmaster', 'Master', 'Godly']
    sp_seed = ['Elder Strawberry', 'Giant Pinecone',
               'Burning Bud', 'Sugar Apple']

    find_egg = [
        item for item in data.get('egg_stock', [])
        if any(keyword in item.get('display_name', '') for keyword in sp_egg)
    ]

    find_gear = [
        item for item in data.get('gear_stock', [])
        if any(keyword in item.get('display_name', '') for keyword in sp_gear)
    ]

    find_seed = [
        item for item in data.get('seed_stock', [])
        if any(keyword in item.get('display_name', '') for keyword in sp_seed)
    ]

    weather_exists = [
        item for item in data.get('weather', [])
        if item.get('active', False) == True
    ]

    if find_egg or find_gear or find_seed:
        title = "📜 Stock Ingfo\n"

        # Seed Stock
        message = "🌱 **Seed**\n"
        for item in data.get("seed_stock", []):
            message += f"- {item['display_name']} (x{item['quantity']})\n"
        message += f"*Berakhir: <t:{data['seed_stock'][0]['end_date_unix']}:R>*\n\n"

        # Gear Stock
        message += "🛠️ **Gear**\n"
        for item in data.get("gear_stock", []):
            message += f"- {item['display_name']} (x{item['quantity']})\n"
        message += f"*Berakhir: <t:{data['gear_stock'][0]['end_date_unix']}:R>*\n\n"

        # Egg Stock
        message += "🥚 **Egg**\n"
        for item in data.get("egg_stock", []):
            message += f"- {item['display_name']} (x{item['quantity']})\n"
        message += f"*Berakhir: <t:{data['egg_stock'][0]['end_date_unix']}:R>*\n\n"

        # # Cosmetic Stock
        # message += "🎨 **Stok Kosmetik**\n"
        # for item in data.get("cosmetic_stock", []):
        #     message += f"  - {item['display_name']} (x{item['quantity']})\n"
        # message += f"*Berakhir: <t:{data['cosmetic_stock'][0]['end_date_unix']}:R>*\n\n"

        # # Event Shop
        # message += "🛒 **Toko Event**\n"
        # for item in data.get("eventshop_stock", []):
        #     message += f"  - {item['display_name']} (x{item['quantity']})\n"
        # message += f"*Berakhir: <t:{data['eventshop_stock'][0]['end_date_unix']}:R>*\n\n"

        # Traveling Merchant
        # merchant = data.get("travelingmerchant_stock", {})
        # message += f"📦 **{merchant.get('merchantName', 'Traveling Merchant')}**\n"
        # for item in merchant.get("stock", []):
        #     message += f"  - {item['display_name']} (x{item['quantity']})\n"
        # message += f"*Berakhir: <t:{merchant['stock'][0]['end_date_unix']}:R>*\n\n"

        # # Notifications (ambil 3 notifikasi terbaru)
        # notifications = data.get("notification", [])
        # if notifications:
        #     latest_notifications = sorted(notifications, key=lambda x: x['timestamp'], reverse=True)[:3]
        #     message += "\n📢 **Notifikasi Terbaru**\n"
        #     for notif in latest_notifications:
        #         timestamp_iso = datetime.utcfromtimestamp(notif['timestamp']).isoformat()
        #         message += f"  - `{notif['message']}`\n"

        message += "*Waktu ditampilkan dalam zona waktu lokal.*"
        embed = discord.Embed(
            title=title,
            description=message,
            color=discord.Color.green()
        )
        embed.set_thumbnail(
            url="https://assetsio.gnwcdn.com/Grow-a-Garden-Codes.jpg?width=1200&height=1200&fit=crop&quality=100&format=png&enable=upscale&auto=webp")
        embed.set_footer(text="Grow A Garden BOT - aeriS")

        return embed

    if weather_exists:
        title = "☀️ Weather Event\n"
        for weather in weather_exists:
            weather_name = weather.get('weather_name', 'Unknown')
            is_active = weather.get('active', False)
            duration = weather.get('duration', 0)

            # Tambahkan emoji berdasarkan status cuaca
            status_emoji = "✅" if is_active == True else "❌"

            message = f"**{status_emoji} {weather_name}**\n"
            message += f"- Status: {'Aktif' if is_active == True else 'Tidak Aktif'}\n"
            message += f"- Durasi: {duration // 60} menit {duration % 60} detik\n\n"
            message += f"- Berakhir: <t:{weather.get('end_duration_unix', 0)}:R>*\n\n"
            embed = discord.Embed(
                title=title,
                description=message,
                color=discord.Color.green()
            )
            embed.set_thumbnail(
                url="https://static.beebom.com/wp-content/uploads/2025/06/Volcano-event.jpg?w=1024")
            embed.set_footer(text="Grow A Garden BOT - aeriS")
        return embed


bot.run(TOKEN, log_handler=log_handler, log_level=logging.DEBUG)
