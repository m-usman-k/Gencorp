import discord
from discord.ext import commands
import sqlite3
import json
from config import SUPREME_USER_ID
from datetime import timedelta, datetime

CONFIG_PATH = 'databases/server_config.json'

def get_ticket_category_id():
    with open(CONFIG_PATH, 'r') as f:
        data = json.load(f)
    return data.get('ticket_category')

def set_ticket_category_id(category_id):
    with open(CONFIG_PATH, 'r+') as f:
        data = json.load(f)
        data['ticket_category'] = category_id
        f.seek(0)
        json.dump(data, f, indent=2)
        f.truncate()

class TicketActionView(discord.ui.View):
    def __init__(self, bot, ticket_id, persistent=True):
        super().__init__(timeout=None)
        self.bot = bot
        self.ticket_id = ticket_id

    @discord.ui.button(label='Close Ticket', style=discord.ButtonStyle.danger, custom_id='close_ticket')
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel_id = interaction.channel.id
        conn = sqlite3.connect('databases/gencorp.db')
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM tickets WHERE channel_id=? AND status=?', (channel_id, 'open'))
        result = cursor.fetchone()
        if not result:
            await interaction.response.send_message('This is not an open ticket channel.', ephemeral=True)
            conn.close()
            return
        cursor.execute('UPDATE tickets SET status=? WHERE channel_id=?', ('closed', channel_id))
        conn.commit()
        conn.close()
        await interaction.response.send_message('Ticket closed. This channel will be deleted in 10 seconds.', ephemeral=True)
        await discord.utils.sleep_until(datetime.utcnow() + timedelta(seconds=10))
        await interaction.channel.delete()

    @discord.ui.button(label='Assign Staff', style=discord.ButtonStyle.primary, custom_id='assign_staff')
    async def assign_staff(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message('Use `/assign_ticket @user` to assign a staff member.', ephemeral=True)

    @discord.ui.button(label='Rename Ticket', style=discord.ButtonStyle.secondary, custom_id='rename_ticket')
    async def rename_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message('Use `/rename_ticket <new-name>` to rename this ticket.', ephemeral=True)

    @discord.ui.button(label='Summon Panel', style=discord.ButtonStyle.success, custom_id='summon_panel')
    async def summon_panel(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = Ticket.ticket_embed(interaction.user)
        await interaction.channel.send(embed=embed, view=TicketActionView(self.bot, self.ticket_id))
        await interaction.response.send_message('Panel re-summoned.', ephemeral=True)

class OpenTicketButton(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label='Open Ticket', style=discord.ButtonStyle.green, custom_id='open_ticket_button')
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        conn = sqlite3.connect('databases/gencorp.db')
        cursor = conn.cursor()
        cursor.execute('SELECT channel_id FROM tickets WHERE user_id=? AND status=?', (user_id, 'open'))
        result = cursor.fetchone()
        if result:
            await interaction.response.send_message(f'You already have an open ticket: <#{result[0]}>', ephemeral=True)
            conn.close()
            return
        guild = interaction.guild
        category_id = get_ticket_category_id()
        category = guild.get_channel(category_id) if category_id else None
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        channel = await guild.create_text_channel(f'ticket-{interaction.user.display_name}', category=category, overwrites=overwrites)
        cursor.execute('INSERT INTO tickets (user_id, channel_id, status) VALUES (?, ?, ?)', (user_id, channel.id, 'open'))
        conn.commit()
        ticket_id = cursor.lastrowid
        conn.close()
        embed = Ticket.ticket_embed(interaction.user)
        await channel.send(embed=embed, view=TicketActionView(self.bot, ticket_id))
        await interaction.response.send_message(f'Ticket created: {channel.mention}', ephemeral=True)

class Ticket(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.add_view(OpenTicketButton(bot))
        self.bot.add_view(TicketActionView(bot, ticket_id=None))

    @staticmethod
    def ticket_embed(user):
        embed = discord.Embed(title="🎫 Support Ticket", color=discord.Color.blue())
        embed.description = (
            f"Welcome {user.mention}!\n\n"
            "A team member will assist you soon.\n\n"
            "**Actions:**\n"
            "- Close Ticket\n"
            "- Assign Staff\n"
            "- Rename Ticket\n"
            "- Summon Panel (this message)"
        )
        return embed

    @commands.command(name='tickets')
    async def tickets(self, ctx):
        embed = discord.Embed(title="Support Tickets", description="Click the button below to open a support ticket.", color=discord.Color.green())
        await ctx.send(embed=embed, view=OpenTicketButton(self.bot))

    @commands.command(name='ticketpanel')
    async def ticketpanel(self, ctx):
        embed = discord.Embed(title="Support Tickets", description="Click the button below to open a support ticket.", color=discord.Color.green())
        await ctx.send(embed=embed, view=OpenTicketButton(self.bot))

    @commands.command(name='summon_ticket_panel', aliases=['summonpanel'])
    async def summon_ticket_panel(self, ctx):
        # Only allow in ticket channels
        conn = sqlite3.connect('databases/gencorp.db')
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM tickets WHERE channel_id=? AND status=?', (ctx.channel.id, 'open'))
        result = cursor.fetchone()
        conn.close()
        if not result:
            await ctx.send('This is not an open ticket channel.')
            return
        embed = self.ticket_embed(ctx.author)
        await ctx.send(embed=embed, view=TicketActionView(self.bot, result[0]))

    @commands.command()
    async def set_ticket_category(self, ctx, category: discord.CategoryChannel):
        if ctx.author.id != SUPREME_USER_ID:
            await ctx.send("You do not have permission to use this command.")
            return
        set_ticket_category_id(category.id)
        await ctx.send(f"Ticket category set to {category.name}")

    @commands.command()
    async def assign_ticket(self, ctx, member: discord.Member):
        channel_id = ctx.channel.id
        conn = sqlite3.connect('databases/gencorp.db')
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM tickets WHERE channel_id=? AND status=?', (channel_id, 'open'))
        result = cursor.fetchone()
        if not result:
            await ctx.send('This is not an open ticket channel.')
            conn.close()
            return
        await ctx.channel.set_permissions(member, read_messages=True, send_messages=True)
        await ctx.send(f'{member.mention} has been assigned to this ticket.')
        conn.close()

    @commands.command()
    async def rename_ticket(self, ctx, *, new_name: str):
        channel = ctx.channel
        await channel.edit(name=new_name)
        await ctx.send(f'Ticket channel renamed to {new_name}')

async def setup(bot):
    await bot.add_cog(Ticket(bot)) 