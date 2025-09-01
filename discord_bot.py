import discord
from discord.ext import commands
import logging
import uuid
from typing import Optional
from database import SessionLocal, Guild, TrackedAccount, Delivery
from neynar_client import neynar_client
from webhook_sync import sync_neynar_webhook
from config import config

# Configuration du logging
logging.basicConfig(level=getattr(logging, config.LOG_LEVEL))
logger = logging.getLogger(__name__)

# Configuration du bot Discord
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    """Événement déclenché quand le bot est prêt"""
    logger.info(f'Bot connecté en tant que {bot.user.name}')
    logger.info(f'ID du bot: {bot.user.id}')
    logger.info(f'Serveurs connectés: {len(bot.guilds)}')
    
    # Synchroniser le webhook au démarrage
    try:
        sync_neynar_webhook()
    except Exception as e:
        logger.error(f"Erreur lors de la synchronisation initiale du webhook: {e}")

@bot.event
async def on_guild_join(guild):
    """Événement déclenché quand le bot rejoint un serveur"""
    logger.info(f'Bot rejoint le serveur: {guild.name} (ID: {guild.id})')
    
    # Créer l'entrée de guild en base
    db = SessionLocal()
    try:
        existing_guild = db.query(Guild).filter_by(id=guild.id).first()
        if not existing_guild:
            new_guild = Guild(id=guild.id)
            db.add(new_guild)
            db.commit()
            logger.info(f"Guild {guild.name} ajoutée à la base de données")
    except Exception as e:
        logger.error(f"Erreur lors de l'ajout de la guild {guild.name}: {e}")
    finally:
        db.close()

@bot.command(name='track')
async def track_command(ctx, fid_or_username: str, channel: Optional[discord.TextChannel] = None):
    """Commande pour tracker un compte Farcaster"""
    try:
        # Vérifier que la commande est utilisée dans un serveur
        if not ctx.guild:
            await ctx.reply("❌ Cette commande ne peut être utilisée que dans un serveur.")
            return
        
        # Déterminer le salon cible
        target_channel = channel or ctx.channel
        
        # Résoudre l'utilisateur Farcaster
        try:
            user = neynar_client.resolve_user(fid_or_username)
        except Exception as e:
            await ctx.reply(f"❌ Erreur lors de la résolution de l'utilisateur: {str(e)}")
            return
        
        # Vérifier si le compte est déjà suivi dans ce salon
        db = SessionLocal()
        try:
            existing = db.query(TrackedAccount).filter_by(
                guild_id=ctx.guild.id,
                channel_id=target_channel.id,
                fid=user['fid']
            ).first()
            
            if existing:
                await ctx.reply(f"❌ Le compte `{user['username']}` (FID: {user['fid']}) est déjà suivi dans ce salon.")
                return
            
            # Ajouter le compte au suivi
            tracked_account = TrackedAccount(
                id=str(uuid.uuid4()),
                guild_id=ctx.guild.id,
                channel_id=target_channel.id,
                fid=user['fid'],
                username=user['username'],
                added_by_discord_user_id=ctx.author.id
            )
            
            db.add(tracked_account)
            db.commit()
            
            # Synchroniser le webhook Neynar
            sync_neynar_webhook()
            
            await ctx.reply(f"✅ Compte Farcaster `{user['username']}` (FID: {user['fid']}) ajouté au suivi dans {target_channel.mention} !")
            
            logger.info(f"Compte Farcaster {user['username']} (FID: {user['fid']}) ajouté au tracking par {ctx.author.name} dans {ctx.guild.name}")
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Erreur dans la commande track: {e}")
        await ctx.reply(f"❌ Une erreur est survenue: {str(e)}")

@bot.command(name='untrack')
async def untrack_command(ctx, fid_or_username: str):
    """Commande pour arrêter de tracker un compte Farcaster"""
    try:
        if not ctx.guild:
            await ctx.reply("❌ Cette commande ne peut être utilisée que dans un serveur.")
            return
        
        # Résoudre l'utilisateur Farcaster
        try:
            user = neynar_client.resolve_user(fid_or_username)
        except Exception as e:
            await ctx.reply(f"❌ Erreur lors de la résolution de l'utilisateur: {str(e)}")
            return
        
        # Supprimer le compte du suivi
        db = SessionLocal()
        try:
            # Supprimer tous les suivis de ce compte dans cette guild
            deleted_count = db.query(TrackedAccount).filter_by(
                guild_id=ctx.guild.id,
                fid=user['fid']
            ).delete()
            
            if deleted_count > 0:
                db.commit()
                
                # Synchroniser le webhook Neynar
                sync_neynar_webhook()
                
                await ctx.reply(f"✅ Compte Farcaster `{user['username']}` (FID: {user['fid']}) supprimé du suivi !")
                logger.info(f"Compte Farcaster {user['username']} (FID: {user['fid']}) supprimé du tracking dans {ctx.guild.name}")
            else:
                await ctx.reply(f"❌ Le compte `{user['username']}` (FID: {user['fid']}) n'était pas suivi dans ce serveur.")
                
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Erreur dans la commande untrack: {e}")
        await ctx.reply(f"❌ Une erreur est survenue: {str(e)}")

@bot.command(name='list')
async def list_command(ctx):
    """Commande pour lister tous les comptes suivis"""
    try:
        if not ctx.guild:
            await ctx.reply("❌ Cette commande ne peut être utilisée que dans un serveur.")
            return
        
        db = SessionLocal()
        try:
            tracked_accounts = db.query(TrackedAccount).filter_by(guild_id=ctx.guild.id).all()
            
            if not tracked_accounts:
                await ctx.reply("📋 Aucun compte Farcaster n'est suivi dans ce serveur.")
                return
            
            # Grouper par salon
            channels = {}
            for account in tracked_accounts:
                channel_id = account.channel_id
                if channel_id not in channels:
                    channels[channel_id] = []
                channels[channel_id].append(account)
            
            # Construire le message
            message = "📋 **Comptes Farcaster suivis dans ce serveur:**\n\n"
            
            for channel_id, accounts in channels.items():
                channel = bot.get_channel(int(channel_id))
                channel_name = channel.mention if channel else f"<#{channel_id}>"
                
                message += f"**{channel_name}:**\n"
                for account in accounts:
                    message += f"• `{account.username}` (FID: {account.fid})\n"
                message += "\n"
            
            await ctx.reply(message)
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Erreur dans la commande list: {e}")
        await ctx.reply(f"❌ Une erreur est survenue: {str(e)}")

@bot.command(name='setchannel')
async def setchannel_command(ctx, channel: discord.TextChannel):
    """Commande pour définir le salon par défaut"""
    try:
        if not ctx.guild:
            await ctx.reply("❌ Cette commande ne peut être utilisée que dans un serveur.")
            return
        
        db = SessionLocal()
        try:
            guild = db.query(Guild).filter_by(id=ctx.guild.id).first()
            if not guild:
                guild = Guild(id=ctx.guild.id)
                db.add(guild)
            
            guild.default_channel_id = channel.id
            db.commit()
            
            await ctx.reply(f"✅ Salon par défaut défini sur {channel.mention} !")
            logger.info(f"Salon par défaut défini sur {channel.name} dans {ctx.guild.name}")
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Erreur dans la commande setchannel: {e}")
        await ctx.reply(f"❌ Une erreur est survenue: {str(e)}")

@bot.command(name='test')
async def test_command(ctx):
    """Commande pour tester les notifications"""
    try:
        if not ctx.guild:
            await ctx.reply("❌ Cette commande ne peut être utilisée que dans un serveur.")
            return
        
        embed = discord.Embed(
            title="🧪 Test de notification",
            description="Ceci est un test pour vérifier que le bot fonctionne correctement dans ce salon.",
            color=0x00FF00
        )
        embed.set_footer(text="Farcaster Tracker Bot")
        
        await ctx.reply(embed=embed)
        logger.info(f"Test de notification effectué dans {ctx.guild.name} par {ctx.author.name}")
        
    except Exception as e:
        logger.error(f"Erreur dans la commande test: {e}")
        await ctx.reply(f"❌ Une erreur est survenue: {str(e)}")

@bot.command(name='far-help')
async def far_help(ctx):
    """Afficher l'aide pour les commandes Farcaster"""
    embed = discord.Embed(
        title="🤖 Aide Farcaster Tracker",
        description="Commandes disponibles pour tracker les comptes Farcaster",
        color=0x6F4CFF
    )
    
    embed.add_field(
        name="📱 Commandes de Tracking",
        value="""
        `!track <fid_ou_username> [channel]` - Commencer à tracker un compte
        `!untrack <fid_ou_username>` - Arrêter de tracker un compte
        `!list` - Lister tous les comptes trackés
        """,
        inline=False
    )
    
    embed.add_field(
        name="⚙️ Commandes de Configuration",
        value="""
        `!setchannel <#channel>` - Définir le salon par défaut
        `!test` - Envoyer un message de test
        `!far-help` - Afficher cette aide
        """,
        inline=False
    )
    
    embed.add_field(
        name="💡 Exemples",
        value="""
        `!track dwr` - Tracker l'utilisateur @dwr
        `!track 194` - Tracker le FID 194
        `!track dwr #notifications` - Tracker dans un salon spécifique
        `!setchannel #general` - Définir #general comme salon par défaut
        """,
        inline=False
    )
    
    embed.add_field(
        name="🔗 Liens Utiles",
        value="""
        [Warpcast](https://warpcast.com) - Plateforme Farcaster
        [Neynar](https://neynar.com) - API Farcaster
        """,
        inline=False
    )
    
    embed.set_footer(text="Bot Farcaster Tracker - Notifications instantanées des casts")
    
    await ctx.send(embed=embed)

def run_bot():
    """Lancer le bot Discord"""
    if not config.validate():
        logger.error("Configuration invalide, arrêt du bot")
        return
    
    try:
        bot.run(config.DISCORD_TOKEN)
    except Exception as e:
        logger.error(f"Erreur lors du lancement du bot: {e}")
        raise
