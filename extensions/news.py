import discord
from discord.ext import commands, tasks
import json
import asyncio
import requests
from bs4 import BeautifulSoup
import re
import finnhub
import os
from config import FINNHUB_API_KEY

CONFIG_PATH = 'databases/server_config.json'
EMBED_COLOR = 0x56DFCF

NEWS_CHANNEL_NAMES = {
    'market': 'market-news',
    'crypto': 'crypto-news',
    'options': 'options-flow',
}
COINTELEGRAPH_URL = "https://cointelegraph.com/category/latest-news"
COINTELEGRAPH_HEADERS = {
    "Host": "cointelegraph.com",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:139.0) Gecko/20100101 Firefox/139.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Alt-Used": "cointelegraph.com",
    "Connection": "keep-alive",
    "Cookie": "_ga_2FVV5584TH=GS2.1.s1751026681$o1$g0$t1751026681$j60$l0$h0; _ga=GA1.1.2134773886.1751026682; _ga_53R24TEEB1=GS2.1.s1751026682$o1$g0$t1751026682$j60$l0$h240213002; _ga_LKJQ7JZELH=GS2.1.s1751026682$o1$g0$t1751026682$j60$l0$h0; _cb=Cv_F5MBuFIVYIO_Ej; _chartbeat2=.1751026683081.1751026683081.1.FcMYbCWEi5hDspg_tWRnf9CXhk4y.1; _cb_svref=external; _clck=1j8qsh0|2|fx4|0|2004; _clsk=hw9hsc|1751026685927|1|1|z.clarity.ms%2Fcollect",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Priority": "u=0, i",
    "TE": "trailers"
}
POSTED_NEWS_FILE = "databases/posted_news.txt"
POSTED_MARKET_NEWS_FILE = "databases/posted_market_news.txt"

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

def is_supreme_leader(user_id):
    with open(CONFIG_PATH, 'r') as f:
        data = json.load(f)
    return user_id in data.get('supreme_leader_ids', [])

class NewsFeed(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.post_cointelegraph_news.start()
        self.post_market_news.start()

    @tasks.loop(minutes=1)
    async def post_cointelegraph_news(self):
        await self.bot.wait_until_ready()
        channel_id = get_news_channel_id('crypto')
        if not channel_id:
            print("No crypto news channel set")
            return
        channel = self.bot.get_channel(channel_id)
        if not channel:
            print("Crypto news channel not found")
            return
        # Load already posted URLs
        try:
            with open(POSTED_NEWS_FILE, "r", encoding="utf-8") as f:
                posted_urls = set(line.strip() for line in f)
        except FileNotFoundError:
            posted_urls = set()
        new_posts = []
        with requests.Session() as session:
            with session.get(COINTELEGRAPH_URL, headers=COINTELEGRAPH_HEADERS) as resp:
                html = resp.text
        soup = BeautifulSoup(html, "html.parser")
        # Find the ldjson-schema script tag
        script_tag = soup.find("script", {"data-hid": "ldjson-schema", "type": "application/ld+json"})
        if not script_tag:
            print("ldjson-schema script tag not found")
            return
        try:
            data = json.loads(script_tag.string)
            items = data.get("itemListElement", [])
        except Exception as e:
            print(f"Failed to parse ldjson-schema JSON: {e}")
            return
        for item in items:
            url = item.get("url")
            title = item.get("name")
            image_url = item.get("image")
            desc = None  # No description in ldjson-schema, can be left blank or fetched if needed
            if url and url not in posted_urls:
                new_posts.append((title, url, desc, image_url))
                posted_urls.add(url)
        # Save updated posted URLs
        with open(POSTED_NEWS_FILE, "w", encoding="utf-8") as f:
            for url in posted_urls:
                f.write(url + "\n")
        # Post new news
        for title, url, desc, image_url in new_posts:
            embed = discord.Embed(title=title, description=desc or "", url=url, color=EMBED_COLOR)
            if image_url:
                embed.set_image(url=image_url)
            await channel.send(embed=embed)
            await asyncio.sleep(2)  # avoid spamming

    @tasks.loop(minutes=1)
    async def post_market_news(self):
        await self.bot.wait_until_ready()
        channel_id = get_news_channel_id('market')
        if not channel_id:
            print("No market news channel set")
            return
        channel = self.bot.get_channel(channel_id)
        if not channel:
            print("Market news channel not found")
            return
        # Load already posted market news IDs
        try:
            with open(POSTED_MARKET_NEWS_FILE, "r", encoding="utf-8") as f:
                posted_ids = set(line.strip() for line in f)
        except FileNotFoundError:
            posted_ids = set()
        f_c = finnhub.Client(api_key=FINNHUB_API_KEY)
        all_news = list(f_c.general_news(category="general", min_id=0))
        new_posts = []
        # Define keywords to filter out crypto and forex news
        filter_keywords = [
            'crypto', 'cryptocurrency', 'bitcoin', 'btc', 'ethereum', 'eth', 'blockchain', 'defi', 'nft', 'altcoin',
            'forex', 'fx', 'currency', 'currencies', 'forex market', 'forex trading', 'forex pair', 'forex broker',
            'binance', 'coinbase', 'kraken', 'stablecoin', 'usdt', 'usdc', 'ripple', 'xrp', 'solana', 'dogecoin',
            'token', 'tokens', 'web3', 'web 3', 'airdrops', 'airdropped', 'airdrops', 'airdropped', 'satoshi',
            'exchange', 'wallet', 'mining', 'hashrate', 'halving', 'ledger', 'metamask', 'bitfinex', 'bitstamp',
            'futures', 'spot trading', 'crypto exchange', 'crypto wallet', 'crypto trading', 'crypto market',
            'forex news', 'forex signal', 'forex trader', 'forex account', 'forex broker', 'forex pair', 'forex trading',
            'pip', 'pips', 'leverage', 'margin', 'forex analysis', 'forex strategy', 'forex signals', 'forex forecast',
            'forex chart', 'forex indicator', 'forex robot', 'forex ea', 'forex expert advisor', 'forex scalping',
            'forex swing', 'forex day trading', 'forex scalper', 'forex swing trader', 'forex day trader', 'coin'
        ]
        def contains_filter_keyword(text):
            if not text:
                return False
            text = text.lower()
            return any(kw in text for kw in filter_keywords)
        for news in all_news:
            headline = news.get("headline", "")
            summary = news.get("summary", "")
            category = news.get("category", "")
            # Filter out if any field contains a filter keyword
            if contains_filter_keyword(headline) or contains_filter_keyword(summary) or contains_filter_keyword(category):
                continue
            if "?" in headline:
                continue  # Skip news with question mark in headline
            news_id = str(news.get("id"))
            if news_id not in posted_ids:
                new_posts.append(news)
                posted_ids.add(news_id)
        # Save updated posted IDs
        with open(POSTED_MARKET_NEWS_FILE, "w", encoding="utf-8") as f:
            for news_id in posted_ids:
                f.write(news_id + "\n")
        # Post new news (only the latest, if multiple, post in order)
        for news in new_posts:
            # Format Discord timestamp if datetime is present
            dt = news.get("datetime")
            if dt:
                try:
                    dt = int(dt)
                    timestamp_str = f"<t:{dt}:f>"
                except Exception:
                    timestamp_str = "-"
            else:
                timestamp_str = "-"
            embed = discord.Embed(
                title=news.get("headline", "No Title"),
                url=news.get("url", None),
                description=(news.get("summary", "")).replace("<p>", "").replace("</p>", ""),
                color=EMBED_COLOR
            )
            # Add fields as requested
            embed.add_field(name="Source", value=news.get("source", "-"), inline=True)
            embed.add_field(name="Time", value=timestamp_str, inline=True)
            embed.add_field(name="Category", value=news.get("category", "-"), inline=True)
            if news.get("image"):
                embed.set_thumbnail(url=news["image"])
            await channel.send(embed=embed)
            await asyncio.sleep(2)  # avoid spamming

    @post_cointelegraph_news.before_loop
    async def before_cointelegraph_news(self):
        await self.bot.wait_until_ready()

    @post_market_news.before_loop
    async def before_market_news(self):
        await self.bot.wait_until_ready()

    @commands.hybrid_command(name='set-news-category', description='Set a category and auto-create news channels in it (supreme only).')
    async def set_news_category(self, ctx, category: discord.CategoryChannel):
        if not is_supreme_leader(ctx.author.id):
            embed = discord.Embed(description="You do not have permission to use this command.", color=EMBED_COLOR)
            await ctx.send(embed=embed, ephemeral=True)
            return
        created_channels = []
        for news_type, channel_name in NEWS_CHANNEL_NAMES.items():
            # Check if channel exists in category
            channel = discord.utils.get(category.channels, name=channel_name)
            if not channel:
                channel = await ctx.guild.create_text_channel(channel_name, category=category)
                created_channels.append(channel.mention)
            set_news_channel_id(news_type, channel.id)
        if created_channels:
            msg = f"Created channels: {', '.join(created_channels)} in {category.mention}."
        else:
            msg = f"All news channels already exist in {category.mention}."
        embed = discord.Embed(description=msg, color=EMBED_COLOR)
        await ctx.send(embed=embed)

    # Optionally, deprecate the old set-news-channel command
    @commands.hybrid_command(name='set-news-channel', description='(Deprecated) Set a news channel for market/crypto/options (supreme only).')
    async def set_news_channel(self, ctx, news_type: str, channel: discord.TextChannel):
        embed = discord.Embed(description="This command is deprecated. Use /set-news-category instead.", color=EMBED_COLOR)
        await ctx.send(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(NewsFeed(bot)) 