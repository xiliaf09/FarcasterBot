import discord
from discord.ext import commands
import logging
import uuid
import json
from typing import Optional
from database import get_session_local, Guild, TrackedAccount, Delivery, TrackedFollowing, FollowingState, FollowingDelivery
from neynar_client import get_neynar_client
from webhook_sync import sync_neynar_webhook, add_fids_to_webhook, remove_fids_from_webhook, force_webhook_fixe
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
    
    # FORCER l'utilisation du webhook fixe 01K45KREDQ77B80YD87AAXJ3E8 au démarrage
    try:
        force_webhook_fixe()
        logger.info("🔒 Webhook fixe 01K45KREDQ77B80YD87AAXJ3E8 forcé au démarrage")
    except Exception as e:
        logger.error(f"Erreur lors du forçage du webhook fixe: {e}")
        logger.info("Forçage du webhook fixe échoué - utilisez !test-neynar pour tester")
    
    # DÉMARRER le service de polling des followings
    try:
        from following_polling import start_following_polling
        await start_following_polling(bot)
        logger.info("🔄 Service de polling des followings démarré")
    except Exception as e:
        logger.error(f"Erreur lors du démarrage du polling des followings: {e}")

@bot.event
async def on_guild_join(guild):
    """Événement déclenché quand le bot rejoint un serveur"""
    try:
        logger.info(f'Bot rejoint le serveur: {guild.name} (ID: {guild.id})')
        
        # Créer l'entrée de guild en base
        db = get_session_local()()
        try:
            existing_guild = db.query(Guild).filter_by(id=str(guild.id)).first()
            if not existing_guild:
                new_guild = Guild(id=str(guild.id))
                db.add(new_guild)
                db.commit()
                logger.info(f"Guild {guild.name} ajoutée à la base de données")
        except Exception as e:
            logger.error(f"Erreur lors de l'ajout de la guild {guild.name}: {e}")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Erreur générale dans on_guild_join: {e}")

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
            logger.info("🔧 Tentative de résolution de l'utilisateur...")
            
            client = get_neynar_client()
            logger.info(f"🔧 Client Neynar récupéré: {client}")
            
            if client is None:
                logger.error("❌ Client Neynar est None - vérification de la configuration")
                await ctx.reply("❌ Erreur: Client Neynar non initialisé. Vérifiez la configuration.")
                return
                
            logger.info(f"🔧 Client Neynar valide: {type(client).__name__}")
            logger.info(f"🔧 Méthodes disponibles: {[m for m in dir(client) if not m.startswith('_')]}")
            
            user = client.resolve_user(fid_or_username)
            logger.info(f"🔧 Utilisateur résolu: {user}")
            
            if user is None:
                await ctx.reply(f"❌ Impossible de résoudre l'utilisateur `{fid_or_username}`. Vérifiez que le FID ou le nom d'utilisateur est correct.")
                return
        except Exception as e:
            logger.error(f"❌ Erreur lors de la résolution de l'utilisateur: {e}")
            logger.error(f"❌ Type d'erreur: {type(e).__name__}")
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            await ctx.reply(f"❌ Erreur lors de la résolution de l'utilisateur: {str(e)}")
            return
        
        # Vérifier si le compte est déjà suivi dans ce salon
        db = get_session_local()()
        try:
            existing = db.query(TrackedAccount).filter_by(
                guild_id=str(ctx.guild.id),
                channel_id=str(target_channel.id),
                fid=user['fid']
            ).first()
            
            if existing:
                await ctx.reply(f"❌ Le compte `{user['username']}` (FID: {user['fid']}) est déjà suivi dans ce salon.")
                return
            
            # Ajouter le compte au suivi
            tracked_account = TrackedAccount(
                id=str(uuid.uuid4()),
                guild_id=str(ctx.guild.id),
                channel_id=str(target_channel.id),
                fid=user['fid'],
                username=user['username'],
                added_by_discord_user_id=str(ctx.author.id)
            )
            
            db.add(tracked_account)
            db.commit()
            
            # Ajouter le FID au webhook existant SANS le recréer
            try:
                # Convertir le FID en string pour la compatibilité
                fid_to_add = str(user['fid'])
                success = add_fids_to_webhook([fid_to_add])
                if success:
                    logger.info(f"✅ FID {fid_to_add} ajouté au webhook existant 01K45KREDQ77B80YD87AAXJ3E8")
                else:
                    logger.warning(f"⚠️ Impossible d'ajouter le FID {fid_to_add} au webhook, mais le compte est tracké localement")
            except Exception as e:
                logger.error(f"❌ Erreur lors de l'ajout du FID au webhook: {e}")
                logger.warning("⚠️ Le compte est tracké localement, mais le webhook n'a pas été mis à jour")
            
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
            if get_neynar_client() is None:
                await ctx.reply("❌ Erreur: Client Neynar non initialisé. Vérifiez la configuration.")
                return
                
            user = get_neynar_client().resolve_user(fid_or_username)
            if user is None:
                await ctx.reply(f"❌ Impossible de résoudre l'utilisateur `{fid_or_username}`. Vérifiez que le FID ou le nom d'utilisateur est correct.")
                return
        except Exception as e:
            await ctx.reply(f"❌ Erreur lors de la résolution de l'utilisateur: {str(e)}")
            return
        
        # Supprimer le compte du suivi
        db = get_session_local()()
        try:
            # Supprimer tous les suivis de ce compte dans cette guild
            deleted_count = db.query(TrackedAccount).filter_by(
                guild_id=str(ctx.guild.id),
                fid=user['fid']
            ).delete()
            
            if deleted_count > 0:
                db.commit()
                
                # Retirer le FID du webhook existant SANS le recréer
                try:
                    # Convertir le FID en string pour la compatibilité
                    fid_to_remove = str(user['fid'])
                    success = remove_fids_from_webhook([fid_to_remove])
                    if success:
                        logger.info(f"✅ FID {fid_to_remove} retiré du webhook existant 01K45KREDQ77B80YD87AAXJ3E8")
                    else:
                        logger.warning(f"⚠️ Impossible de retirer le FID {fid_to_remove} du webhook, mais le compte est untracké localement")
                except Exception as e:
                    logger.error(f"❌ Erreur lors du retrait du FID du webhook: {e}")
                    logger.warning("⚠️ Le compte est untracké localement, mais le webhook n'a pas été mis à jour")
                
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
        
        db = get_session_local()()
        try:
            tracked_accounts = db.query(TrackedAccount).filter_by(guild_id=str(ctx.guild.id)).all()
            
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
        
        db = get_session_local()()
        try:
            guild = db.query(Guild).filter_by(id=str(ctx.guild.id)).first()
            if not guild:
                guild = Guild(id=str(ctx.guild.id))
                db.add(guild)
            
            guild.default_channel_id = str(channel.id)
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

@bot.command(name='test-neynar')
async def test_neynar_command(ctx):
    """Commande pour tester la connexion à l'API Neynar"""
    try:
        if not ctx.guild:
            await ctx.reply("❌ Cette commande ne peut être utilisée que dans un serveur.")
            return
        
        embed = discord.Embed(
            title="🧪 Test de Connexion Neynar",
            description="Test en cours...",
            color=0xFFFF00
        )
        embed.set_footer(text="Farcaster Tracker Bot")
        
        # Envoyer le message initial
        message = await ctx.reply(embed=embed)
        
        # Test 1: Vérifier la configuration
        embed.add_field(
            name="1️⃣ Configuration",
            value="✅ API Key configurée\n✅ Webhook Secret configuré\n✅ Base URL configurée",
            inline=False
        )
        await message.edit(embed=embed)
        
        # Test 2: Test de résolution d'utilisateur
        try:
            user = get_neynar_client().resolve_user("dwr")
            embed.add_field(
                name="2️⃣ Résolution Utilisateur",
                value=f"✅ @{user['username']} (FID: {user['fid']})",
                inline=False
            )
            embed.color = 0x00FF00
        except Exception as e:
            embed.add_field(
                name="2️⃣ Résolution Utilisateur",
                value=f"❌ Erreur: {str(e)}",
                inline=False
            )
            embed.color = 0xFF0000
        
        await message.edit(embed=embed)
        
        # Test 3: Test de création de webhook
        try:
            from webhook_sync import get_webhook_stats
            stats = get_webhook_stats()
            
            if stats.get("status") == "active":
                embed.add_field(
                    name="3️⃣ Webhook Neynar",
                    value=f"✅ Webhook actif (ID: {stats.get('webhook_id', 'N/A')})\n✅ {stats.get('author_fids_count', 0)} FID(s) configuré(s)",
                    inline=False
                )
            else:
                embed.add_field(
                    name="3️⃣ Webhook Neynar",
                    value=f"⚠️ Statut: {stats.get('status', 'N/A')}\n📝 {stats.get('message', 'Aucun message')}",
                    inline=False
                )
        except Exception as e:
            embed.add_field(
                name="3️⃣ Webhook Neynar",
                value=f"❌ Erreur: {str(e)}",
                inline=False
            )
        
        await message.edit(embed=embed)
        
        # Test 4: Test de synchronisation
        try:
            from webhook_sync import sync_neynar_webhook
            sync_neynar_webhook()  # Test de synchronisation
            embed.add_field(
                name="4️⃣ Synchronisation",
                value="✅ Synchronisation testée avec succès",
                inline=False
            )
        except Exception as e:
            embed.add_field(
                name="4️⃣ Synchronisation",
                value=f"❌ Erreur: {str(e)}",
                inline=False
            )
        
        # Mise à jour finale
        embed.description = "Test de connexion Neynar terminé"
        await message.edit(embed=embed)
        
        logger.info(f"Test Neynar effectué dans {ctx.guild.name} par {ctx.author.name}")
        
    except Exception as e:
        logger.error(f"Erreur dans la commande test-neynar: {e}")
        await ctx.reply(f"❌ Une erreur est survenue: {str(e)}")

@bot.command(name='lastcast')
async def lastcast_command(ctx, fid_or_username: str):
    """Commande pour récupérer le dernier cast d'un compte Farcaster"""
    try:
        if not ctx.guild:
            await ctx.reply("❌ Cette commande ne peut être utilisée que dans un serveur.")
            return
        
        # Résoudre l'utilisateur Farcaster
        try:
            client = get_neynar_client()
            if client is None:
                await ctx.reply("❌ Erreur: Client Neynar non initialisé. Vérifiez la configuration.")
                return
                
            user = client.resolve_user(fid_or_username)
            if user is None:
                await ctx.reply(f"❌ Impossible de résoudre l'utilisateur `{fid_or_username}`. Vérifiez que le FID ou le nom d'utilisateur est correct.")
                return
        except Exception as e:
            await ctx.reply(f"❌ Erreur lors de la résolution de l'utilisateur: {str(e)}")
            return
        
        # Récupérer le dernier cast
        try:
            # Utiliser la nouvelle méthode officielle v2 pour récupérer les casts
            logger.info(f"🔧 Récupération des casts avec get_user_feed pour FID {user['fid']}")
            feed_result = client.get_user_feed(user['fid'], limit=10, include_replies=True)
            
            if not feed_result.get("casts") or len(feed_result["casts"]) == 0:
                await ctx.reply(f"📝 Aucun cast trouvé pour `{user['username']}` (FID: {user['fid']})")
                return
            
            # Les casts sont déjà triés chronologiquement par l'API
            casts = feed_result["casts"]
            cast = casts[0]  # Le plus récent (premier de la liste)
            
            logger.info(f"🔧 Cast trouvé: {cast.get('text', 'N/A')} - Hash: {cast.get('hash', 'N/A')}")
            logger.info(f"🔧 Timestamp du cast: {cast.get('timestamp', 'N/A')}")
            logger.info(f"🔧 Nombre total de casts trouvés: {len(casts)}")
            
            # Log des premiers casts pour debug
            for i, c in enumerate(casts[:3]):
                logger.info(f"🔧 Cast {i+1}: {c.get('text', 'N/A')[:50]}... - Hash: {c.get('hash', 'N/A')}")
            
            # Créer un embed avec les détails du cast
            embed = discord.Embed(
                title=f"📝 Dernier Cast de @{user['username']}",
                description=f"**{cast.get('text', 'Aucun texte')}**",
                color=0x6F4CFF,
                timestamp=discord.utils.utcnow()
            )
            
            # Ajouter les informations du cast
            if cast.get("timestamp"):
                embed.add_field(
                    name="🕐 Publié le",
                    value=f"<t:{cast['timestamp']}:F>",
                    inline=False
                )
            
            # Ajouter le lien direct vers le cast
            if cast.get("hash"):
                # Vérifier que le hash est valide (commence par 0x)
                if cast['hash'].startswith('0x'):
                    cast_url = f"https://warpcast.com/{user['username']}/{cast['hash']}"
                    embed.add_field(
                        name="🔗 Voir le Cast",
                        value=f"[Cliquer ici pour voir sur Warpcast]({cast_url})",
                        inline=False
                    )
                else:
                    embed.add_field(
                        name="⚠️ Hash Invalide",
                        value=f"Hash du cast invalide: `{cast['hash']}`",
                        inline=False
                    )
            else:
                embed.add_field(
                    name="⚠️ Hash Manquant",
                    value="Hash du cast non disponible",
                    inline=False
                )
            
            # Ajouter l'image de profil de l'utilisateur
            if user.get("pfp_url"):
                embed.set_thumbnail(url=user["pfp_url"])
            
            embed.set_footer(text=f"FID: {user['fid']} • Farcaster Tracker Bot")
            
            await ctx.reply(embed=embed)
            logger.info(f"Dernier cast récupéré pour {user['username']} (FID: {user['fid']}) par {ctx.author.name}")
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération du cast: {e}")
            await ctx.reply(f"❌ Erreur lors de la récupération du cast: {str(e)}")
            
    except Exception as e:
        logger.error(f"Erreur dans la commande lastcast: {e}")
        await ctx.reply(f"❌ Une erreur est survenue: {str(e)}")

@bot.command(name='debug-cast')
async def debug_cast_command(ctx, fid_or_username: str):
    """Commande de debug pour tester différentes méthodes de récupération de casts"""
    try:
        if not ctx.guild:
            await ctx.reply("❌ Cette commande ne peut être utilisée que dans un serveur.")
            return
        
        # Résoudre l'utilisateur Farcaster
        try:
            client = get_neynar_client()
            if client is None:
                await ctx.reply("❌ Erreur: Client Neynar non initialisé.")
                return
                
            user = client.resolve_user(fid_or_username)
            if user is None:
                await ctx.reply(f"❌ Impossible de résoudre l'utilisateur `{fid_or_username}`.")
                return
        except Exception as e:
            await ctx.reply(f"❌ Erreur lors de la résolution: {str(e)}")
            return
        
        # Créer l'embed de debug
        embed = discord.Embed(
            title=f"🔍 Debug Cast pour @{user['username']}",
            description="Test des différentes méthodes de récupération...",
            color=0xFFFF00,
            timestamp=discord.utils.utcnow()
        )
        
        # Test 1: search_casts avec from:
        try:
            search_query = f"from:{user['username']}"
            search_result = client.search_casts(search_query, limit=5)
            casts_count = len(search_result.get("casts", []))
            embed.add_field(
                name="1️⃣ search_casts (from:username)",
                value=f"✅ {casts_count} cast(s) trouvé(s)\nRequête: `{search_query}`",
                inline=False
            )
            
            if casts_count > 0:
                for i, cast in enumerate(search_result["casts"][:3]):
                    embed.add_field(
                        name=f"Cast {i+1}",
                        value=f"Texte: {cast.get('text', 'N/A')[:50]}...\nHash: {cast.get('hash', 'N/A')}",
                        inline=True
                    )
        except Exception as e:
            embed.add_field(
                name="1️⃣ search_casts (from:username)",
                value=f"❌ Erreur: {str(e)}",
                inline=False
            )
        
        # Test 2: search_casts avec le username seul
        try:
            search_query = user['username']
            search_result = client.search_casts(search_query, limit=5)
            casts_count = len(search_result.get("casts", []))
            embed.add_field(
                name="2️⃣ search_casts (username seul)",
                value=f"✅ {casts_count} cast(s) trouvé(s)\nRequête: `{search_query}`",
                inline=False
            )
        except Exception as e:
            embed.add_field(
                name="2️⃣ search_casts (username seul)",
                value=f"❌ Erreur: {str(e)}",
                inline=False
            )
        
        # Test 3: get_user_feed (nouvelle méthode v2)
        try:
            feed_result = client.get_user_feed(user['fid'], limit=5, include_replies=True)
            casts_count = len(feed_result.get("casts", []))
            embed.add_field(
                name="3️⃣ get_user_feed v2 (FID)",
                value=f"✅ {casts_count} cast(s) trouvé(s)\nFID: {user['fid']}\nMéthode: /v2/farcaster/feed/user/casts/",
                inline=False
            )
            
            if casts_count > 0:
                for i, cast in enumerate(feed_result["casts"][:3]):
                    embed.add_field(
                        name=f"Cast {i+1} (v2)",
                        value=f"Texte: {cast.get('text', 'N/A')[:50]}...\nHash: {cast.get('hash', 'N/A')}",
                        inline=True
                    )
        except Exception as e:
            embed.add_field(
                name="3️⃣ get_user_feed v2 (FID)",
                value=f"❌ Erreur: {str(e)}",
                inline=False
            )
        
        embed.set_footer(text=f"Debug pour {user['username']} (FID: {user['fid']})")
        await ctx.reply(embed=embed)
        
    except Exception as e:
        logger.error(f"Erreur dans la commande debug-cast: {e}")
        await ctx.reply(f"❌ Une erreur est survenue: {str(e)}")

@bot.command(name='check-webhook')
async def check_webhook_command(ctx):
    """Commande pour vérifier l'état du webhook fixe 01K45KREDQ77B80YD87AAXJ3E8"""
    try:
        if not ctx.guild:
            await ctx.reply("❌ Cette commande ne peut être utilisée que dans un serveur.")
            return
        
        embed = discord.Embed(
            title="🔍 Vérification du Webhook Fixe",
            description="Vérification en cours de l'état du webhook 01K45KREDQ77B80YD87AAXJ3E8...",
            color=0x00BFFF
        )
        embed.set_footer(text="Farcaster Tracker Bot")
        
        message = await ctx.reply(embed=embed)
        
        try:
            from webhook_sync import get_webhook_stats
            stats = get_webhook_stats()
            
            if stats.get("status") == "active":
                embed.description = "✅ **Webhook fixe 01K45KREDQ77B80YD87AAXJ3E8 ACTIF !**"
                embed.color = 0x00FF00
                embed.add_field(
                    name="🔒 Webhook Fixe",
                    value=f"ID: {stats.get('webhook_id', 'N/A')}\nStatut: Actif\nFIDs configurés: {stats.get('author_fids_count', 0)}",
                    inline=False
                )
            elif stats.get("status") == "inactive":
                embed.description = "⚠️ **Webhook fixe 01K45KREDQ77B80YD87AAXJ3E8 INACTIF !**"
                embed.color = 0xFFFF00
                embed.add_field(
                    name="⚠️ Attention",
                    value="Le webhook existe mais est inactif côté Neynar",
                    inline=False
                )
            else:
                embed.description = "❌ **Webhook fixe 01K45KREDQ77B80YD87AAXJ3E8 INTROUVABLE !**"
                embed.color = 0xFF0000
                embed.add_field(
                    name="❌ Problème",
                    value="Le webhook n'existe plus côté Neynar - il faut le recréer",
                    inline=False
                )
                
        except Exception as e:
            embed.description = "❌ **Erreur lors de la vérification**"
            embed.color = 0xFF0000
            embed.add_field(
                name="❌ Erreur",
                value=f"Erreur: {str(e)}",
                inline=False
            )
        
        await message.edit(embed=embed)
        logger.info(f"Vérification du webhook effectuée dans {ctx.guild.name} par {ctx.author.name}")
        
    except Exception as e:
        logger.error(f"Erreur dans la commande check-webhook: {e}")
        await ctx.reply(f"❌ Une erreur est survenue: {str(e)}")

@bot.command(name='force-webhook')
async def force_webhook_command(ctx):
    """Commande pour forcer l'utilisation du webhook fixe 01K45KREDQ77B80YD87AAXJ3E8"""
    try:
        if not ctx.guild:
            await ctx.reply("❌ Cette commande ne peut être utilisée que dans un serveur.")
            return
        
        embed = discord.Embed(
            title="🔒 Forçage du Webhook Fixe",
            description="Forçage en cours de l'utilisation du webhook 01K45KREDQ77B80YD87AAXJ3E8...",
            color=0xFF6B35
        )
        embed.set_footer(text="Farcaster Tracker Bot")
        
        message = await ctx.reply(embed=embed)
        
        try:
            success = force_webhook_fixe()
            if success:
                embed.description = "✅ **Webhook fixe 01K45KREDQ77B80YD87AAXJ3E8 forcé avec succès !**"
                embed.color = 0x00FF00
                embed.add_field(
                    name="🔒 Webhook Fixe",
                    value="Le bot utilise maintenant exclusivement le webhook 01K45KREDQ77B80YD87AAXJ3E8",
                    inline=False
                )
            else:
                embed.description = "⚠️ **Webhook fixe forcé localement, mais erreur côté Neynar**"
                embed.color = 0xFFFF00
                embed.add_field(
                    name="⚠️ Attention",
                    value="L'état local est synchronisé, mais le webhook Neynar n'a pas pu être mis à jour",
                    inline=False
                )
        except Exception as e:
            embed.description = "❌ **Erreur lors du forçage du webhook fixe**"
            embed.color = 0xFF0000
            embed.add_field(
                name="❌ Erreur",
                value=f"Erreur: {str(e)}",
                inline=False
            )
        
        await message.edit(embed=embed)
        logger.info(f"Forçage du webhook fixe effectué dans {ctx.guild.name} par {ctx.author.name}")
        
    except Exception as e:
        logger.error(f"Erreur dans la commande force-webhook: {e}")
        await ctx.reply(f"❌ Une erreur est survenue: {str(e)}")

@bot.command(name='debug-webhook')
async def debug_webhook_command(ctx):
    """Commande de debug pour tester l'API webhook Neynar"""
    try:
        if not ctx.guild:
            await ctx.reply("❌ Cette commande ne peut être utilisée que dans un serveur.")
            return
        
        embed = discord.Embed(
            title="🔍 Debug Webhook Neynar",
            description="Test de l'API webhook en cours...",
            color=0x00BFFF
        )
        embed.set_footer(text="Farcaster Tracker Bot")
        
        message = await ctx.reply(embed=embed)
        
        # Test 1: Vérifier la configuration
        webhook_id = config.NEYNAR_WEBHOOK_ID
        embed.add_field(
            name="1️⃣ Configuration",
            value=f"✅ Webhook ID: `{webhook_id}`\n✅ API Key: `{config.NEYNAR_API_KEY[:10]}...`\n✅ Base URL: `{config.PUBLIC_BASE_URL}`",
            inline=False
        )
        await message.edit(embed=embed)
        
        # Test 2: Test de récupération du webhook
        try:
            client = get_neynar_client()
            if client is None:
                embed.add_field(
                    name="2️⃣ Client Neynar",
                    value="❌ Client Neynar non initialisé",
                    inline=False
                )
                await message.edit(embed=embed)
                return
            
            webhook_details = client.get_webhook(webhook_id)
            embed.add_field(
                name="2️⃣ Récupération Webhook",
                value=f"✅ Webhook récupéré avec succès\n📊 Statut: `{webhook_details.get('active', 'N/A')}`\n🔗 URL: `{webhook_details.get('url', 'N/A')}`",
                inline=False
            )
        except Exception as e:
            # Extraire le code d'erreur HTTP si disponible
            error_code = "N/A"
            if hasattr(e, 'response') and hasattr(e.response, 'status_code'):
                error_code = e.response.status_code
            elif "404" in str(e):
                error_code = "404"
            elif "403" in str(e):
                error_code = "403"
            elif "400" in str(e):
                error_code = "400"
            
            embed.add_field(
                name="2️⃣ Récupération Webhook",
                value=f"❌ Erreur: {str(e)}\n🔍 Code: {error_code}",
                inline=False
            )
        
        await message.edit(embed=embed)
        
        # Test 3: Test de mise à jour du webhook
        try:
            # Récupérer les FIDs actuels de la base
            db = get_session_local()()
            try:
                tracked_accounts = db.query(TrackedAccount.fid).distinct().all()
                current_fids = [int(account[0]) for account in tracked_accounts]
                
                if current_fids:
                    # Tester la mise à jour avec les FIDs actuels
                    updated_webhook = client.update_webhook(webhook_id, current_fids)
                    embed.add_field(
                        name="3️⃣ Mise à jour Webhook",
                        value=f"✅ Webhook mis à jour avec succès\n📊 FIDs configurés: {len(current_fids)}\n🔢 FIDs: `{current_fids[:5]}{'...' if len(current_fids) > 5 else ''}`",
                        inline=False
                    )
                else:
                    embed.add_field(
                        name="3️⃣ Mise à jour Webhook",
                        value="⚠️ Aucun FID à configurer (base vide)",
                        inline=False
                    )
            finally:
                db.close()
                
        except Exception as e:
            # Extraire le code d'erreur HTTP si disponible
            error_code = "N/A"
            if hasattr(e, 'response') and hasattr(e.response, 'status_code'):
                error_code = e.response.status_code
            elif "404" in str(e):
                error_code = "404"
            elif "403" in str(e):
                error_code = "403"
            elif "400" in str(e):
                error_code = "400"
            
            embed.add_field(
                name="3️⃣ Mise à jour Webhook",
                value=f"❌ Erreur: {str(e)}\n🔍 Code: {error_code}",
                inline=False
            )
        
        # Mise à jour finale
        embed.description = "Test de l'API webhook terminé"
        embed.color = 0x00FF00 if "✅" in str(embed.fields[-1].value) else 0xFF0000
        await message.edit(embed=embed)
        
        logger.info(f"Debug webhook effectué dans {ctx.guild.name} par {ctx.author.name}")
        
    except Exception as e:
        logger.error(f"Erreur dans la commande debug-webhook: {e}")
        await ctx.reply(f"❌ Une erreur est survenue: {str(e)}")

@bot.command(name='test-api')
async def test_api_command(ctx):
    """Commande pour tester l'API Neynar avec différents endpoints"""
    try:
        if not ctx.guild:
            await ctx.reply("❌ Cette commande ne peut être utilisée que dans un serveur.")
            return
        
        embed = discord.Embed(
            title="🧪 Test API Neynar",
            description="Test des différents endpoints de l'API...",
            color=0x00BFFF
        )
        embed.set_footer(text="Farcaster Tracker Bot")
        
        message = await ctx.reply(embed=embed)
        
        client = get_neynar_client()
        if client is None:
            await ctx.reply("❌ Client Neynar non initialisé")
            return
        
        # Test 1: Test de l'endpoint de base
        try:
            # Tester avec un FID connu (dwr = 194)
            user = client.get_user_by_fid(194)
            embed.add_field(
                name="1️⃣ API Base",
                value=f"✅ Endpoint de base fonctionne\n👤 Test avec FID 194: {user.get('username', 'N/A')}",
                inline=False
            )
        except Exception as e:
            embed.add_field(
                name="1️⃣ API Base",
                value=f"❌ Erreur endpoint de base: {str(e)}",
                inline=False
            )
        
        await message.edit(embed=embed)
        
        # Test 2: Test de l'endpoint webhook avec différents formats
        webhook_id = config.NEYNAR_WEBHOOK_ID
        
        # Test 2a: Endpoint actuel
        try:
            webhook_details = client.get_webhook(webhook_id)
            embed.add_field(
                name="2️⃣ Webhook (format actuel)",
                value=f"✅ Webhook trouvé avec le format actuel\n📊 Statut: {webhook_details.get('active', 'N/A')}",
                inline=False
            )
        except Exception as e:
            embed.add_field(
                name="2️⃣ Webhook (format actuel)",
                value=f"❌ Erreur format actuel: {str(e)}",
                inline=False
            )
        
        await message.edit(embed=embed)
        
        # Test 2b: Test avec un endpoint alternatif
        try:
            # Tester avec l'endpoint v1 au cas où
            import requests
            headers = client.headers
            response = requests.get(
                f"https://api.neynar.com/v1/farcaster/webhook/{webhook_id}",
                headers=headers,
                timeout=10
            )
            if response.status_code == 200:
                embed.add_field(
                    name="3️⃣ Webhook (v1)",
                    value=f"✅ Webhook trouvé avec l'endpoint v1\n📊 Statut: {response.json().get('active', 'N/A')}",
                    inline=False
                )
            else:
                embed.add_field(
                    name="3️⃣ Webhook (v1)",
                    value=f"❌ Erreur v1: {response.status_code} - {response.text}",
                    inline=False
                )
        except Exception as e:
            embed.add_field(
                name="3️⃣ Webhook (v1)",
                value=f"❌ Erreur v1: {str(e)}",
                inline=False
            )
        
        # Mise à jour finale
        embed.description = "Test de l'API terminé"
        embed.color = 0x00FF00 if any("✅" in field.value for field in embed.fields) else 0xFF0000
        await message.edit(embed=embed)
        
        logger.info(f"Test API effectué dans {ctx.guild.name} par {ctx.author.name}")
        
    except Exception as e:
        logger.error(f"Erreur dans la commande test-api: {e}")
        await ctx.reply(f"❌ Une erreur est survenue: {str(e)}")

@bot.command(name='test-webhook-endpoints')
async def test_webhook_endpoints_command(ctx):
    """Commande pour tester différents endpoints webhook v2"""
    try:
        if not ctx.guild:
            await ctx.reply("❌ Cette commande ne peut être utilisée que dans un serveur.")
            return
        
        embed = discord.Embed(
            title="🧪 Test Endpoints Webhook v2",
            description="Test des différents endpoints webhook v2...",
            color=0x00BFFF
        )
        embed.set_footer(text="Farcaster Tracker Bot")
        
        message = await ctx.reply(embed=embed)
        
        webhook_id = config.NEYNAR_WEBHOOK_ID
        client = get_neynar_client()
        
        if client is None:
            await ctx.reply("❌ Client Neynar non initialisé")
            return
        
        # Test 1: Endpoint actuel
        try:
            import requests
            headers = client.headers
            
            # Test 1a: /v2/farcaster/webhook/{id}
            response = requests.get(
                f"https://api.neynar.com/v2/farcaster/webhook/{webhook_id}",
                headers=headers,
                timeout=10
            )
            embed.add_field(
                name="1️⃣ /v2/farcaster/webhook/{id}",
                value=f"Status: {response.status_code}\nResponse: {response.text[:100]}...",
                inline=False
            )
        except Exception as e:
            embed.add_field(
                name="1️⃣ /v2/farcaster/webhook/{id}",
                value=f"Erreur: {str(e)}",
                inline=False
            )
        
        await message.edit(embed=embed)
        
        # Test 2: Endpoint alternatif
        try:
            # Test 2a: /v2/farcaster/webhooks/{id}
            response = requests.get(
                f"https://api.neynar.com/v2/farcaster/webhooks/{webhook_id}",
                headers=headers,
                timeout=10
            )
            embed.add_field(
                name="2️⃣ /v2/farcaster/webhooks/{id}",
                value=f"Status: {response.status_code}\nResponse: {response.text[:100]}...",
                inline=False
            )
        except Exception as e:
            embed.add_field(
                name="2️⃣ /v2/farcaster/webhooks/{id}",
                value=f"Erreur: {str(e)}",
                inline=False
            )
        
        await message.edit(embed=embed)
        
        # Test 3: Endpoint avec query params
        try:
            # Test 3a: /v2/farcaster/webhook?id={id}
            response = requests.get(
                f"https://api.neynar.com/v2/farcaster/webhook?id={webhook_id}",
                headers=headers,
                timeout=10
            )
            embed.add_field(
                name="3️⃣ /v2/farcaster/webhook?id={id}",
                value=f"Status: {response.status_code}\nResponse: {response.text[:100]}...",
                inline=False
            )
        except Exception as e:
            embed.add_field(
                name="3️⃣ /v2/farcaster/webhook?id={id}",
                value=f"Erreur: {str(e)}",
                inline=False
            )
        
        await message.edit(embed=embed)
        
        # Test 4: Lister tous les webhooks
        try:
            # Test 4a: /v2/farcaster/webhooks (liste)
            response = requests.get(
                "https://api.neynar.com/v2/farcaster/webhooks",
                headers=headers,
                timeout=10
            )
            if response.status_code == 200:
                webhooks = response.json()
                webhook_list = []
                if isinstance(webhooks, list):
                    for wh in webhooks[:3]:  # Limiter à 3 pour l'affichage
                        webhook_list.append(f"ID: {wh.get('id', 'N/A')}, Active: {wh.get('active', 'N/A')}")
                elif isinstance(webhooks, dict) and 'webhooks' in webhooks:
                    for wh in webhooks['webhooks'][:3]:
                        webhook_list.append(f"ID: {wh.get('id', 'N/A')}, Active: {wh.get('active', 'N/A')}")
                
                embed.add_field(
                    name="4️⃣ /v2/farcaster/webhooks (liste)",
                    value=f"Status: {response.status_code}\nWebhooks: {', '.join(webhook_list) if webhook_list else 'Aucun'}",
                    inline=False
                )
            else:
                embed.add_field(
                    name="4️⃣ /v2/farcaster/webhooks (liste)",
                    value=f"Status: {response.status_code}\nResponse: {response.text[:100]}...",
                    inline=False
                )
        except Exception as e:
            embed.add_field(
                name="4️⃣ /v2/farcaster/webhooks (liste)",
                value=f"Erreur: {str(e)}",
                inline=False
            )
        
        # Mise à jour finale
        embed.description = "Test des endpoints webhook terminé"
        embed.color = 0x00FF00 if any("200" in field.value for field in embed.fields) else 0xFF0000
        await message.edit(embed=embed)
        
        logger.info(f"Test endpoints webhook effectué dans {ctx.guild.name} par {ctx.author.name}")
        
    except Exception as e:
        logger.error(f"Erreur dans la commande test-webhook-endpoints: {e}")
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
        `!lastcast <fid_ou_username>` - Voir le dernier cast d'un compte
        `!debug-cast <fid_ou_username>` - Debug des méthodes de récupération de casts
        """,
        inline=False
    )
    
    embed.add_field(
        name="🆕 Commandes de Following Tracking",
        value="""
        `!trackfollowing <fid_ou_username>` - Tracker les nouveaux followings d'un compte
        `!untrackfollowing <fid_ou_username>` - Arrêter de tracker les followings
        `!listfollowing` - Lister les comptes suivis pour leurs followings
        *Utilise automatiquement le salon configuré dans DEFAULT_CHANNEL_ID*
        """,
        inline=False
    )
    
    embed.add_field(
        name="⚙️ Commandes de Configuration",
        value="""
        `!setchannel <#channel>` - Définir le salon par défaut
        `!test` - Envoyer un message de test
        `!check-webhook` - Vérifier l'état du webhook fixe
        `!force-webhook` - Forcer l'utilisation du webhook fixe
        `!debug-webhook` - Debug de l'API webhook Neynar
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
        `!trackfollowing dwr` - Tracker les nouveaux followings de @dwr
        `!trackfollowing 194` - Tracker les followings de FID 194
        `!setchannel #general` - Définir #general comme salon par défaut (pour les casts)
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

@bot.command(name='trackfollowing')
async def track_following_command(ctx, fid_or_username: str):
    """Commande pour tracker les nouveaux followings d'un compte Farcaster"""
    try:
        # Vérifier que la commande est utilisée dans un serveur
        if not ctx.guild:
            await ctx.reply("❌ Cette commande ne peut être utilisée que dans un serveur.")
            return
        
        # Utiliser le salon configuré dans les variables d'environnement
        if not config.DEFAULT_CHANNEL_ID:
            await ctx.reply("❌ Aucun salon configuré. Vérifiez la variable d'environnement DEFAULT_CHANNEL_ID.")
            return
            
        target_channel = bot.get_channel(int(config.DEFAULT_CHANNEL_ID))
        if not target_channel:
            await ctx.reply(f"❌ Le salon configuré (ID: {config.DEFAULT_CHANNEL_ID}) n'existe plus ou le bot n'y a pas accès.")
            return
        
        # Résoudre l'utilisateur Farcaster
        try:
            logger.info("🔧 Tentative de résolution de l'utilisateur pour following tracking...")
            
            client = get_neynar_client()
            if client is None:
                await ctx.reply("❌ Erreur: Client Neynar non initialisé. Vérifiez la configuration.")
                return
                
            user = client.resolve_user(fid_or_username)
            if user is None:
                await ctx.reply(f"❌ Impossible de résoudre l'utilisateur `{fid_or_username}`. Vérifiez que le FID ou le nom d'utilisateur est correct.")
                return
        except Exception as e:
            logger.error(f"❌ Erreur lors de la résolution de l'utilisateur: {e}")
            await ctx.reply(f"❌ Erreur lors de la résolution de l'utilisateur: {str(e)}")
            return
        
        # Vérifier si le compte est déjà suivi pour les followings dans ce salon
        db = get_session_local()()
        try:
            existing = db.query(TrackedFollowing).filter_by(
                guild_id=str(ctx.guild.id),
                channel_id=str(target_channel.id),
                target_fid=user['fid']
            ).first()
            
            if existing:
                await ctx.reply(f"❌ Le compte `{user['username']}` (FID: {user['fid']}) est déjà suivi pour ses nouveaux followings dans ce salon.")
                return
            
            # Ajouter le compte au suivi des followings
            tracked_following = TrackedFollowing(
                id=str(uuid.uuid4()),
                guild_id=str(ctx.guild.id),
                channel_id=str(target_channel.id),
                target_fid=user['fid'],
                target_username=user['username'],
                added_by_discord_user_id=str(ctx.author.id)
            )
            
            db.add(tracked_following)
            db.commit()
            
            # Initialiser l'état des followings si nécessaire
            existing_state = db.query(FollowingState).filter_by(target_fid=user['fid']).first()
            if not existing_state:
                # Récupérer la liste actuelle des followings
                try:
                    current_followings = client.get_user_following(user['fid'])
                    following_fids = [f['fid'] for f in current_followings]
                    
                    following_state = FollowingState(
                        id=str(uuid.uuid4()),
                        target_fid=user['fid'],
                        last_following_list=json.dumps(following_fids)
                    )
                    db.add(following_state)
                    db.commit()
                    
                    logger.info(f"✅ État initial des followings créé pour {user['username']} avec {len(following_fids)} followings")
                except Exception as e:
                    logger.warning(f"⚠️ Impossible de récupérer les followings initiaux pour {user['username']}: {e}")
                    # Créer un état vide
                    following_state = FollowingState(
                        id=str(uuid.uuid4()),
                        target_fid=user['fid'],
                        last_following_list=json.dumps([])
                    )
                    db.add(following_state)
                    db.commit()
            
            await ctx.reply(f"✅ Compte Farcaster `{user['username']}` (FID: {user['fid']}) ajouté au suivi des **nouveaux followings** dans {target_channel.mention} !\n🔄 Vérification toutes les minutes...")
            
            logger.info(f"Compte Farcaster {user['username']} (FID: {user['fid']}) ajouté au tracking des followings par {ctx.author.name} dans {ctx.guild.name}")
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Erreur dans la commande track-following: {e}")
        await ctx.reply(f"❌ Une erreur est survenue: {str(e)}")

@bot.command(name='untrackfollowing')
async def untrack_following_command(ctx, fid_or_username: str):
    """Commande pour arrêter de tracker les followings d'un compte Farcaster"""
    try:
        if not ctx.guild:
            await ctx.reply("❌ Cette commande ne peut être utilisée que dans un serveur.")
            return
        
        # Résoudre l'utilisateur Farcaster
        try:
            if get_neynar_client() is None:
                await ctx.reply("❌ Erreur: Client Neynar non initialisé. Vérifiez la configuration.")
                return
                
            user = get_neynar_client().resolve_user(fid_or_username)
            if user is None:
                await ctx.reply(f"❌ Impossible de résoudre l'utilisateur `{fid_or_username}`. Vérifiez que le FID ou le nom d'utilisateur est correct.")
                return
        except Exception as e:
            await ctx.reply(f"❌ Erreur lors de la résolution de l'utilisateur: {str(e)}")
            return
        
        # Supprimer le compte du suivi des followings
        db = get_session_local()()
        try:
            # Supprimer tous les suivis de followings de ce compte dans cette guild
            deleted_count = db.query(TrackedFollowing).filter_by(
                guild_id=str(ctx.guild.id),
                target_fid=user['fid']
            ).delete()
            
            if deleted_count > 0:
                db.commit()
                
                # Vérifier si d'autres guilds suivent encore ce compte
                remaining_tracking = db.query(TrackedFollowing).filter_by(target_fid=user['fid']).count()
                
                # Si plus personne ne suit ce compte, supprimer l'état
                if remaining_tracking == 0:
                    db.query(FollowingState).filter_by(target_fid=user['fid']).delete()
                    db.commit()
                    logger.info(f"État des followings supprimé pour {user['username']} (plus de tracking)")
                
                await ctx.reply(f"✅ Compte Farcaster `{user['username']}` (FID: {user['fid']}) supprimé du suivi des **nouveaux followings** !")
                logger.info(f"Compte Farcaster {user['username']} (FID: {user['fid']}) supprimé du tracking des followings dans {ctx.guild.name}")
            else:
                await ctx.reply(f"❌ Le compte `{user['username']}` (FID: {user['fid']}) n'était pas suivi pour ses followings dans ce serveur.")
                
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Erreur dans la commande untrack-following: {e}")
        await ctx.reply(f"❌ Une erreur est survenue: {str(e)}")

@bot.command(name='listfollowing')
async def list_following_command(ctx):
    """Commande pour lister tous les comptes suivis pour leurs followings"""
    try:
        if not ctx.guild:
            await ctx.reply("❌ Cette commande ne peut être utilisée que dans un serveur.")
            return
        
        db = get_session_local()()
        try:
            tracked_followings = db.query(TrackedFollowing).filter_by(guild_id=str(ctx.guild.id)).all()
            
            if not tracked_followings:
                await ctx.reply("📋 Aucun compte Farcaster n'est suivi pour ses **nouveaux followings** dans ce serveur.")
                return
            
            # Grouper par salon
            channels = {}
            for following in tracked_followings:
                channel_id = following.channel_id
                if channel_id not in channels:
                    channels[channel_id] = []
                channels[channel_id].append(following)
            
            # Construire le message
            message = "📋 **Comptes Farcaster suivis pour leurs nouveaux followings:**\n\n"
            
            for channel_id, followings in channels.items():
                channel = bot.get_channel(int(channel_id))
                channel_name = channel.mention if channel else f"<#{channel_id}>"
                
                message += f"**{channel_name}:**\n"
                for following in followings:
                    message += f"• `{following.target_username}` (FID: {following.target_fid})\n"
                message += "\n"
            
            await ctx.reply(message)
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Erreur dans la commande list-following: {e}")
        await ctx.reply(f"❌ Une erreur est survenue: {str(e)}")

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
