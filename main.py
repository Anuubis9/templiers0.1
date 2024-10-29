import discord
from discord.ext import commands
from discord import ui
import random
import asyncio
import os
from dotenv import load_dotenv
from keep_alive import keep_alive
import psycopg2
from psycopg2 import sql

load_dotenv()
token = os.getenv('DISCORD_TOKEN')
database_url = os.getenv('DATABASE_URL')

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

# Liste des types de munitions
munitions_list = ["5.56", "5.45", "7.62x39", "308Win", "Cal12C", "Cal12R", "9x39", "7.62x54R"]

# Liste des médicaments
pharmacie_list = ["Morphine", "Tétracycline", "Charbon", "Vitamine", "Attelles", "Kit Sanguin", "O+", "O-", "serum phy", "kit intraveineuse", "kit de chirurgie"]

# Ajout des types de munitions dans la base de données s'ils n'existent pas encore
for munition in munitions_list:
    cur.execute('SELECT * FROM stock_munitions WHERE item=%s', (munition,))
    if not cur.fetchone():
        cur.execute('INSERT INTO stock_munitions (item, quantity) VALUES (%s, %s)', (munition, 0))
conn.commit()

# Ajout des médicaments dans la base de données s'ils n'existent pas encore
for medicament in pharmacie_list:
    cur.execute('SELECT * FROM stock_pharmacie WHERE item=%s', (medicament,))
    if not cur.fetchone():
        cur.execute('INSERT INTO stock_pharmacie (item, quantity) VALUES (%s, %s)', (medicament, 0))
conn.commit()

# Initialisation du bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Fonction pour mettre à jour les tableaux de stock
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

# Classe pour générer des boutons pour les munitions
class MunitionsView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.create_buttons()

    def create_buttons(self):
        for munition in munitions_list:
            self.add_item(ui.Button(label=f"Modifier {munition}", style=discord.ButtonStyle.primary, custom_id=f"mod_munitions_{munition}"))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        custom_id = interaction.data["custom_id"]
        if custom_id.startswith("mod_munitions_"):
            munition = custom_id[len("mod_munitions_"):]
            await interaction.response.send_message(f"Combien de {munition} voulez-vous ajouter ou retirer ? (Nombre positif pour ajouter, négatif pour retirer)", ephemeral=True)
            def check(message):
                return message.author == interaction.user and message.channel == interaction.channel
            try:
                response = await bot.wait_for('message', check=check, timeout=30)
                try:
                    quantity_change = int(response.content)
                except ValueError:
                    await interaction.followup.send("Veuillez entrer un nombre valide.", ephemeral=True)
                    return False
                await response.delete(delay=10)
                cur.execute('SELECT quantity FROM stock_munitions WHERE item=%s', (munition,))
                result = cur.fetchone()
                if result:
                    current_quantity = result[0]
                    new_quantity = max(0, current_quantity + quantity_change)
                    cur.execute('UPDATE stock_munitions SET quantity=%s WHERE item=%s', (new_quantity, munition))
                    conn.commit()
                    confirmation_message = await interaction.followup.send(f"{abs(quantity_change)} {munition} {'ajoutées' if quantity_change > 0 else 'retirées'}. Nouveau stock : {new_quantity}", ephemeral=True)
                    await asyncio.sleep(10)
                    await confirmation_message.delete()
                    await update_stock_message_munitions()
                else:
                    print("Erreur : munition introuvable dans la base de données.")
            except asyncio.TimeoutError:
                await interaction.followup.send("Temps écoulé, veuillez réessayer.", ephemeral=True)
        return True

# Classe pour générer des boutons pour la pharmacie
class PharmacieView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.create_buttons()

    def create_buttons(self):
        for medicament in pharmacie_list:
            self.add_item(ui.Button(label=f"Modifier {medicament}", style=discord.ButtonStyle.primary, custom_id=f"mod_pharmacie_{medicament}"))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        custom_id = interaction.data["custom_id"]
        if custom_id.startswith("mod_pharmacie_"):
            medicament = custom_id[len("mod_pharmacie_"):]
            await interaction.response.send_message(f"Combien de {medicament} voulez-vous ajouter ou retirer ? (Nombre positif pour ajouter, négatif pour retirer)", ephemeral=True)
            def check(message):
                return message.author == interaction.user and message.channel == interaction.channel
            try:
                response = await bot.wait_for('message', check=check, timeout=30)
                try:
                    quantity_change = int(response.content)
                except ValueError:
                    await interaction.followup.send("Veuillez entrer un nombre valide.", ephemeral=True)
                    return False
                await response.delete(delay=10)
                cur.execute('SELECT quantity FROM stock_pharmacie WHERE item=%s', (medicament,))
                result = cur.fetchone()
                if result:
                    current_quantity = result[0]
                    new_quantity = max(0, current_quantity + quantity_change)
                    cur.execute('UPDATE stock_pharmacie SET quantity=%s WHERE item=%s', (new_quantity, medicament))
                    conn.commit()
                    confirmation_message = await interaction.followup.send(f"{abs(quantity_change)} {medicament} {'ajoutés' if quantity_change > 0 else 'retirés'}. Nouveau stock : {new_quantity}", ephemeral=True)
                    await asyncio.sleep(10)
                    await confirmation_message.delete()
                    await update_stock_message_pharmacie()
                else:
                    print("Erreur : médicament introuvable dans la base de données.")
            except asyncio.TimeoutError:
                await interaction.followup.send("Temps écoulé, veuillez réessayer.", ephemeral=True)
        return True

# Commande pour initialiser les boutons des munitions dans le canal spécifique
@bot.command()
async def init_munitions(ctx):
    global stock_message_munitions
    if ctx.channel.id == 1290283964547989514:  # ID du canal de munitions
        view = MunitionsView()
        if stock_message_munitions is None:
            stock_message_munitions = await ctx.send("**Chargement du tableau des stocks...**")
            await update_stock_message_munitions()
            await ctx.send("Gestion des munitions :", view=view)
            cur.execute('INSERT INTO bot_state (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = %s',
                        ("stock_message_id_munitions", str(stock_message_munitions.id), str(stock_message_munitions.id)))
            conn.commit()
        await ctx.message.delete(delay=10)

# Commande pour initialiser les boutons des médicaments dans le canal spécifique
@bot.command()
async def init_pharmacie(ctx):
    global stock_message_pharmacie
    if ctx.channel.id == 1293868842115797013:  # ID du canal de pharmacie
        view = PharmacieView()
        if stock_message_pharmacie is None:
            stock_message_pharmacie = await ctx.send("**Chargement du tableau des stocks...**")
            await update_stock_message_pharmacie()
            await ctx.send("Gestion de la pharmacie :", view=view)
            cur.execute('INSERT INTO bot_state_pharmacie (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = %s',
                        ("stock_message_id_pharmacie", str(stock_message_pharmacie.id), str(stock_message_pharmacie.id)))
            conn.commit()
        await ctx.message.delete(delay=10)

# Classe pour définir le bouton de sélection de la radio
class RadioButton(ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # Timeout désactivé pour garder le bouton actif

    @ui.button(label="Choisir une station de radio", style=discord.ButtonStyle.primary)
    async def select_radio(self, interaction: discord.Interaction, button: ui.Button):
        # Vérification que l'interaction se déroule dans le bon canal
        if interaction.channel.name == "radio":
            # Sélection aléatoire d'une station de radio
            selected_station = random.choice(stations_radio)
            await interaction.response.send_message(f"Station de radio sélectionnée : **{selected_station}**")
        else:
            await interaction.response.send_message("Cette commande ne peut être utilisée que dans le canal **radio**.")

# Commande pour initialiser le bouton de sélection de station de radio dans le canal radio
@bot.command()
async def init_radio(ctx):
    if ctx.channel.id == 1291085634538176572:  # ID du canal de Radio
        view = RadioButton()
        await ctx.send("Appuyez sur le bouton pour sélectionner une station de radio aléatoire :", view=view)
    else:
        await ctx.send("Cette commande ne peut être utilisée que dans le canal **radio**.")

keep_alive()

# Lancement du bot
bot.run(token=token)
