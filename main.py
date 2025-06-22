import discord
from discord.ext import commands
import logging
import os
import sqlite3
import json
from config import BOT_TOKEN
from extensions.ticket import OpenTicketButton, TicketActionView

# Logging setup
if not os.path.exists('logs'):
    os.makedirs('logs')
logging.basicConfig(
    filename='logs/bot.log',
    level=logging.INFO,
    format='%(asctime)s:%(levelname)s:%(name)s: %(message)s'
)

# Database setup
if not os.path.exists('databases'):
    os.makedirs('databases')
conn = sqlite3.connect('databases/gencorp.db')
cursor = conn.cursor()
# Example: create a table for tickets if not exists
cursor.execute('''CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)''')
conn.commit()
conn.close()

# Bot setup
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

views_registered = False  # Flag to ensure views are only registered once

# Custom help command
def get_command_info():
    return [
        ("/help", "Show this help message."),
        ("/tickets", "Show the ticket panel with a button to open a ticket."),
        ("/ticketpanel", "Re-summon the ticket panel in a channel."),
        ("/set_welcome_channel <#channel>", "Set the welcome channel (supreme only)."),
        ("/set_ticket_category <category>", "Set the ticket category (supreme only)."),
        ("/set_news_channel <type> <#channel>", "Set a news channel for market/crypto/options (supreme only)."),
        ("/assign_ticket <@user>", "Assign a staff member to the ticket."),
        ("/rename_ticket <new-name>", "Rename the ticket channel."),
    ]

@bot.command(name="help", help="Show this help message.")
async def help_command(ctx):
    # Remove the default help command if it exists
    if "help" in bot.all_commands and bot.all_commands["help"] != help_command:
        bot.remove_command("help")
    embed = discord.Embed(title="Gencorp Assistant Help", color=discord.Color.green())
    description = "\n".join([f"`{cmd}`: {desc}" for cmd, desc in get_command_info()])
    embed.description = description
    await ctx.send(embed=embed)

# Load cogs/extensions
async def load_extensions():
    for filename in os.listdir('./extensions'):
        if filename.endswith('.py') and filename != '__init__.py':
            await bot.load_extension(f'extensions.{filename[:-3]}')

@bot.event
async def on_ready():
    global views_registered
    if not views_registered:
        bot.add_view(OpenTicketButton(bot))
        # Register persistent ticket action views for all open tickets
        conn = sqlite3.connect('databases/gencorp.db')
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM tickets WHERE status=?', ('open',))
        for (ticket_id,) in cursor.fetchall():
            bot.add_view(TicketActionView(bot, ticket_id))
        conn.close()
        views_registered = True
    await load_extensions()
    logging.info(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')

if __name__ == '__main__':
    bot.run(BOT_TOKEN) 