import discord
from discord.ext import commands, tasks
import random
import json
from config import SUPREME_USER_ID

CONFIG_PATH = 'databases/server_config.json'

def get_news_channel_id(news_type):
    with open(CONFIG_PATH, 'r') as f:
        data = json.load(f)
    return data.get('news_channels', {}).get(news_type)

def set_news_channel_id(news_type, channel_id):
    with open(CONFIG_PATH, 'r+') as f:
        data = json.load(f)
        if 'news_channels' not in data:
            data['news_channels'] = {}
        data['news_channels'][news_type] = channel_id
        f.seek(0)
        json.dump(data, f, indent=2)
        f.truncate()

class NewsFeed(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.post_news.start()

    @tasks.loop(minutes=30)
    async def post_news(self):
        news_samples = {
            'market': ["Market News: S&P 500 hits new high!", "Market News: Fed announces rate decision."],
            'crypto': ["Crypto News: Bitcoin surges 5%.", "Crypto News: Ethereum upgrade released."],
            'options': ["Options Flow: Unusual call activity on TSLA.", "Options Flow: Large put sweep on AAPL."]
        }
        for key in ['market', 'crypto', 'options']:
            channel_id = get_news_channel_id(key)
            if channel_id:
                channel = self.bot.get_channel(channel_id)
                if channel:
                    await channel.send(random.choice(news_samples[key]))

    @post_news.before_loop
    async def before_news(self):
        await self.bot.wait_until_ready()

    @commands.command()
    async def set_news_channel(self, ctx, news_type: str, channel: discord.TextChannel):
        if ctx.author.id != SUPREME_USER_ID:
            await ctx.send("You do not have permission to use this command.")
            return
        if news_type not in ['market', 'crypto', 'options']:
            await ctx.send("Invalid news type. Choose from: market, crypto, options.")
            return
        set_news_channel_id(news_type, channel.id)
        await ctx.send(f"{news_type.capitalize()} news channel set to {channel.mention}")

async def setup(bot):
    await bot.add_cog(NewsFeed(bot)) 