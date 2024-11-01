import discord
from discord.ext import commands
from discord import ui
import random
import asyncio
import os
from dotenv import load_dotenv
import psycopg2
from psycopg2 import sql

load_dotenv()
token = os.getenv('DISCORD_TOKEN')
database_url = os.getenv('DATABASE_URL')

# Variables globales pour stocker les messages de stock
stock_message_munitions = None
stock_message_pharmacie = None

# Liste des stations de radio disponibles
stations_radio = [87.8, 89.5, 91.3, 91.9, 94.6, 96.6, 99.7, 102.5]

# Connexion à la base de données PostgreSQL
conn = psycopg2.connect(database_url)
cur = conn.cursor()

# Création des tables si elles n'existent pas encore
cur.execute('''
CREATE TABLE IF NOT EXISTS stock_munitions (
    item TEXT PRIMARY KEY,
    quantity INTEGER
)
''')
conn.commit()

cur.execute('''
CREATE TABLE IF NOT EXISTS stock_pharmacie (
    item TEXT PRIMARY KEY,
    quantity INTEGER
)
''')
conn.commit()

cur.execute('''
CREATE TABLE IF NOT EXISTS bot_state (
    key TEXT PRIMARY KEY,
    value TEXT
)
''')
conn.commit()

cur.execute('''
CREATE TABLE IF NOT EXISTS bot_state_pharmacie (
    key TEXT PRIMARY KEY,
    value TEXT
)
''')
conn.commit()

# Liste des types de munitions et médicaments
munitions_list = ["5.56", "5.45", "7.62x39", "308Win", "Cal12C", "Cal12R", "9x39", "7.62x54R"]
pharmacie_list = ["Morphine", "Tétracycline", "Charbon", "Vitamine", "Attelles", "Kit Sanguin", "O+", "O-", "serum phy", "kit intraveineuse", "kit de chirurgie"]

# Ajout des types de munitions et médicaments dans la base de données
for munition in munitions_list:
    cur.execute('SELECT * FROM stock_munitions WHERE item=%s', (munition,))
    if not cur.fetchone():
        cur.execute('INSERT INTO stock_munitions (item, quantity) VALUES (%s, %s)', (munition, 0))
conn.commit()

for medicament in pharmacie_list:
    cur.execute('SELECT * FROM stock_pharmacie WHERE item=%s', (medicament,))
    if not cur.fetchone():
        cur.execute('INSERT INTO stock_pharmacie (item, quantity) VALUES (%s, %s)', (medicament, 0))
conn.commit()

# Initialisation du bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Event when bot is ready
@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    global stock_message_munitions, stock_message_pharmacie

# Fonctions pour mettre à jour les stocks
async def update_stock_message_munitions():
    global stock_message_munitions
    if stock_message_munitions is not None:
        cur.execute('SELECT item, quantity FROM stock_munitions')
        munitions_results = cur.fetchall()
        message = "**Stocks actuels des munitions :**\n\n"
        if munitions_results:
            message += "```\n"
            message += "{:<20} {:<10}\n".format("Munitions", "Quantité")
            message += "-" * 30 + "\n"
            for row in munitions_results:
                message += "{:<20} {:<10}\n".format(row[0], row[1])
            message += "```\n"
        else:
            message += "*Aucune munition en stock.*\n"
        await stock_message_munitions.edit(content=message)

async def update_stock_message_pharmacie():
    global stock_message_pharmacie
    if stock_message_pharmacie is not None:
        cur.execute('SELECT item, quantity FROM stock_pharmacie')
        pharmacie_results = cur.fetchall()
        message = "**Stocks actuels de la pharmacie :**\n\n"
        if pharmacie_results:
            message += "```\n"
            message += "{:<20} {:<10}\n".format("Médicaments", "Quantité")
            message += "-" * 30 + "\n"
            for row in pharmacie_results:
                message += "{:<20} {:<10}\n".format(row[0], row[1])
            message += "```\n"
        else:
            message += "*Aucun médicament en stock.*\n"
        await stock_message_pharmacie.edit(content=message)

# Classes pour les vues des boutons des munitions et médicaments avec callback
class MunitionsView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        for munition in munitions_list:
            button = discord.ui.Button(label=munition, style=discord.ButtonStyle.blurple, custom_id=f"munition_{munition}")
            button.callback = self.on_button_click
            self.add_item(button)

    async def on_button_click(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"Vous avez cliqué sur {interaction.custom_id}", ephemeral=True)

class PharmacieView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        for medicament in pharmacie_list:
            button = discord.ui.Button(label=medicament, style=discord.ButtonStyle.blurple, custom_id=f"pharmacie_{medicament}")
            button.callback = self.on_button_click
            self.add_item(button)

    async def on_button_click(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"Vous avez cliqué sur {interaction.custom_id}", ephemeral=True)

# Nouvelle commande !init globale
@bot.command()
@commands.has_permissions(administrator=True)
async def init(ctx):
    global stock_message_munitions, stock_message_pharmacie
    if not ctx.guild:
        await ctx.send("Cette commande doit être utilisée dans un serveur.")
        return

    # Initialisation du tableau des munitions
    munitions_channel = bot.get_channel(1290283964547989514)
    if munitions_channel:
        await munitions_channel.purge()
        stock_message_munitions = await munitions_channel.send("**Chargement du tableau des stocks...**")
        await update_stock_message_munitions()
        view_munitions = MunitionsView()
        await munitions_channel.send("Gestion des munitions :", view=view_munitions)

    # Initialisation du tableau de la pharmacie
    pharmacie_channel = bot.get_channel(1293868842115797013)
    if pharmacie_channel:
        await pharmacie_channel.purge()
        stock_message_pharmacie = await pharmacie_channel.send("**Chargement du tableau des stocks...**")
        await update_stock_message_pharmacie()
        view_pharmacie = PharmacieView()
        await pharmacie_channel.send("Gestion de la pharmacie :", view=view_pharmacie)

bot.run(token)
