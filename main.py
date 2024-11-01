import os
import discord
from discord.ext import commands
from discord import ui
import random
import psycopg2
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
DATABASE_URL = os.getenv('DATABASE_URL')

# Configurations des listes
STATIONS_RADIO = [87.8, 89.5, 91.3, 91.9, 94.6, 96.6, 99.7, 102.5]
MUNITIONS_LIST = ["5.56", "5.45", "7.62x39", "308Win", "Cal12C", "Cal12R", "9x39", "7.62x54R"]
PHARMACIE_LIST = ["Morphine", "Tétracycline", "Charbon", "Vitamine", "Attelles", "Kit Sanguin", "O+", "O-", "serum phy", "kit intraveineuse", "kit de chirurgie"]

class InventoryBot:
    def __init__(self):
        # Configuration des intents
        intents = discord.Intents.default()
        intents.message_content = True
        self.bot = commands.Bot(command_prefix='!', intents=intents)

        # Connexion à la base de données
        self.conn = psycopg2.connect(DATABASE_URL)
        self.cur = self.conn.cursor()

        # Initialisation des tables
        self._create_tables()
        self._initialize_inventory()

        # Messages de stock globaux
        self.stock_message_munitions = None
        self.stock_message_pharmacie = None

        # Configuration des événements et commandes
        self._setup_events()
        self._setup_commands()

    def _create_tables(self):
        """Créer les tables nécessaires si elles n'existent pas"""
        tables = [
            '''CREATE TABLE IF NOT EXISTS stock_munitions (
                item TEXT PRIMARY KEY,
                quantity INTEGER
            )''',
            '''CREATE TABLE IF NOT EXISTS stock_pharmacie (
                item TEXT PRIMARY KEY,
                quantity INTEGER
            )'''
        ]
        
        for table in tables:
            self.cur.execute(table)
        self.conn.commit()

    def _initialize_inventory(self):
        """Initialiser l'inventaire avec des items si non existants"""
        def _add_items_to_table(table_name, item_list):
            for item in item_list:
                self.cur.execute(f'SELECT * FROM {table_name} WHERE item=%s', (item,))
                if not self.cur.fetchone():
                    self.cur.execute(f'INSERT INTO {table_name} (item, quantity) VALUES (%s, %s)', (item, 0))
            self.conn.commit()

        _add_items_to_table('stock_munitions', MUNITIONS_LIST)
        _add_items_to_table('stock_pharmacie', PHARMACIE_LIST)

    def _setup_events(self):
        @self.bot.event
        async def on_ready():
            print(f'{self.bot.user} est connecté à Discord!')

    def _setup_commands(self):
        @self.bot.command()
        async def radio(ctx):
            """Sélectionne une station de radio aléatoire"""
            station = random.choice(STATIONS_RADIO)
            await ctx.send(f"🎵 Station de radio sélectionnée : {station} MHz")

        @self.bot.command(name='init')
        @commands.has_permissions(administrator=True)
        async def init_inventory(ctx):
            """Initialise les canaux d'inventaire"""
            if not ctx.guild:
                await ctx.send("Cette commande doit être utilisée dans un serveur.")
                return

            # Canal des munitions
            munitions_channel = self.bot.get_channel(1290283964547989514)
            if munitions_channel:
                await munitions_channel.purge()
                await self._update_stock_message(munitions_channel, 'munitions')

            # Canal de la pharmacie
            pharmacie_channel = self.bot.get_channel(1293868842115797013)
            if pharmacie_channel:
                await pharmacie_channel.purge()
                await self._update_stock_message(pharmacie_channel, 'pharmacie')

        async def _update_stock_message(self, channel, stock_type):
            """Mettre à jour le message de stock"""
            if stock_type == 'munitions':
                self.cur.execute('SELECT item, quantity FROM stock_munitions ORDER BY item')
                title = "**Stocks actuels des munitions :**"
                item_list = MUNITIONS_LIST
            else:
                self.cur.execute('SELECT item, quantity FROM stock_pharmacie ORDER BY item')
                title = "**Stocks actuels de la pharmacie :**"
                item_list = PHARMACIE_LIST

            results = self.cur.fetchall()
            message = f"{title}\n\n"
            
            if results:
                message += "```\n"
                message += "{:<20} {:<10}\n".format("Items", "Quantité")
                message += "-" * 30 + "\n"
                for row in results:
                    message += "{:<20} {:<10}\n".format(row[0], row[1])
                message += "```\n"
            else:
                message += "*Aucun item en stock.*\n"

            view = InventoryView(self, stock_type)
            await channel.send(message, view=view)

        class InventoryView(discord.ui.View):
            def __init__(self, bot_instance, stock_type):
                super().__init__(timeout=None)
                self.bot_instance = bot_instance
                self.stock_type = stock_type
                
                # Ajouter un modal pour chaque item
                for item in (MUNITIONS_LIST if stock_type == 'munitions' else PHARMACIE_LIST):
                    button = discord.ui.Button(
                        label=item, 
                        style=discord.ButtonStyle.blurple, 
                        custom_id=f"{stock_type}_{item}"
                    )
                    button.callback = self.on_button_click
                    self.add_item(button)

            async def on_button_click(self, interaction: discord.Interaction):
                # Créer un modal pour saisir la quantité
                class QuantityModal(ui.Modal, title="Ajuster la quantité"):
                    quantity = ui.TextInput(
                        label="Quantité à ajouter/retirer",
                        style=discord.TextStyle.short,
                        placeholder="Entrez un nombre (positif pour ajouter, négatif pour retirer)",
                        required=True
                    )

                    def __init__(self, bot_instance, stock_type, item):
                        super().__init__()
                        self.bot_instance = bot_instance
                        self.stock_type = stock_type
                        self.item = item

                    async def on_submit(self, interaction: discord.Interaction):
                        try:
                            # Convertir la quantité en entier
                            quantity = int(self.quantity.value)
                            
                            # Déterminer la table en fonction du type de stock
                            table_name = 'stock_munitions' if self.stock_type == 'munitions' else 'stock_pharmacie'
                            
                            # Mettre à jour la quantité dans la base de données
                            with self.bot_instance.conn:
                                with self.bot_instance.conn.cursor() as cur:
                                    # Récupérer la quantité actuelle
                                    cur.execute(f'SELECT quantity FROM {table_name} WHERE item = %s', (self.item,))
                                    current_quantity = cur.fetchone()[0]
                                    
                                    # Calculer la nouvelle quantité (ne pas descendre en dessous de 0)
                                    new_quantity = max(0, current_quantity + quantity)
                                    
                                    # Mettre à jour la quantité
                                    cur.execute(f'UPDATE {table_name} SET quantity = %s WHERE item = %s', 
                                                (new_quantity, self.item))
                            
                            # Réponse à l'utilisateur
                            await interaction.response.send_message(
                                f"✅ {self.item} : Quantité mise à jour. "
                                f"Changement de {quantity} (Nouvelle quantité : {new_quantity})", 
                                ephemeral=True
                            )
                            
                            # Rafraîchir le message dans le canal approprié
                            channel = interaction.channel
                            await channel.purge(limit=2)  # Supprimer le dernier message (stock) et le modal
                            
                            # Recréer le message de stock
                            await self.bot_instance._update_stock_message(channel, self.stock_type)
                            
                        except ValueError:
                            await interaction.response.send_message(
                                "❌ Erreur : Veuillez entrer un nombre valide.", 
                                ephemeral=True
                            )
                        except Exception as e:
                            await interaction.response.send_message(
                                f"❌ Une erreur s'est produite : {str(e)}", 
                                ephemeral=True
                            )

                # Créer et ouvrir le modal
                modal = QuantityModal(self.bot_instance, self.stock_type, interaction.data['custom_id'].split('_')[1])
                await interaction.response.send_modal(modal)

    def run(self):
        """Démarrer le bot"""
        self.bot.run(TOKEN)

def main():
    bot = InventoryBot()
    bot.run()

if __name__ == "__main__":
    main()
