import asyncio
import hmac
import hashlib
import json
import logging
import uuid
from typing import Dict, Any, List
from fastapi import FastAPI, Request, HTTPException, Depends
from sqlalchemy.orm import Session
import discord
import discord.utils
from database import get_session_local, Delivery
from config import config
from discord_bot import bot

# Configuration du logging
logger = logging.getLogger(__name__)

# Créer l'application FastAPI
app = FastAPI(title="Farcaster Tracker Webhook Handler")

# Queue pour les messages Discord
import queue
import threading
import time

discord_queue = queue.Queue()
worker_thread = None
worker_running = False

def discord_worker():
    """Worker thread pour envoyer les messages Discord de manière synchrone"""
    global worker_running
    
    logger.info("🚀 Worker Discord démarré")
    
    while worker_running:
        try:
            # Récupérer un message de la queue (timeout de 1 seconde)
            try:
                message_data = discord_queue.get(timeout=1)
            except queue.Empty:
                continue
            
            # Extraire les données du message
            channel_id = message_data['channel_id']
            embed_dict = message_data['embed']
            author_username = message_data['author_username']
            cast_hash = message_data['cast_hash']
            guild_id = message_data['guild_id']
            
            logger.info(f"📤 Traitement du message pour {author_username} dans le canal {channel_id}")
            
            # Récupérer le canal
            channel = bot.get_channel(channel_id)
            if not channel:
                logger.error(f"❌ Canal {channel_id} non trouvé")
                continue
            
            # Envoyer le message
            try:
                # Créer l'embed Discord
                embed = discord.Embed(
                    title=embed_dict.get("title", "Nouveau Cast"),
                    description=embed_dict.get("description", ""),
                    color=embed_dict.get("color", 0x8B5CF6),
                    url=embed_dict.get("url", "")
                )
                
                if embed_dict.get("timestamp"):
                    embed.timestamp = discord.utils.utcnow()
                if embed_dict.get("footer"):
                    embed.set_footer(text=embed_dict.get("footer", {}).get("text", ""))
                if embed_dict.get("fields"):
                    for field in embed_dict["fields"]:
                        embed.add_field(
                            name=field.get("name", ""), 
                            value=field.get("value", ""), 
                            inline=field.get("inline", True)
                        )
                if embed_dict.get("thumbnail"):
                    embed.set_thumbnail(url=embed_dict["thumbnail"]["url"])
                if embed_dict.get("author"):
                    author_info = embed_dict["author"]
                    embed.set_author(
                        name=author_info.get("name", ""), 
                        url=author_info.get("url", ""), 
                        icon_url=author_info.get("icon_url", "")
                    )
                
                # Envoyer le message de manière synchrone avec asyncio.run()
                try:
                    async def send_message():
                        await channel.send(embed=embed)
                    
                    # Utiliser asyncio.run() qui gère correctement l'event loop
                    asyncio.run(send_message())
                    
                    # Marquer comme livré dans la base de données
                    try:
                        db = get_session_local()()
                        delivery = Delivery(
                            id=str(uuid.uuid4()),
                            guild_id=guild_id,
                            channel_id=str(channel_id),
                            cast_hash=cast_hash
                        )
                        db.add(delivery)
                        db.commit()
                        logger.info(f"✅ Livraison enregistrée pour {author_username}")
                    except Exception as e:
                        logger.error(f"❌ Erreur lors de l'enregistrement de la livraison: {e}")
                        if db:
                            db.rollback()
                    finally:
                        if db:
                            db.close()
                    
                    logger.info(f"✅ Message envoyé avec succès dans {channel.name}")
                    
                except Exception as e:
                    logger.error(f"❌ Erreur lors de l'envoi du message: {e}")
                
            except Exception as e:
                logger.error(f"❌ Erreur lors de l'envoi du message: {e}")
            
            # Marquer la tâche comme terminée
            discord_queue.task_done()
            
        except Exception as e:
            logger.error(f"❌ Erreur dans le worker Discord: {e}")
            time.sleep(1)  # Pause en cas d'erreur
    
    logger.info("🛑 Worker Discord arrêté")



def start_discord_worker():
    """Démarrer le worker thread Discord"""
    global worker_thread, worker_running
    worker_running = True
    if worker_thread is None or not worker_thread.is_alive():
        worker_thread = threading.Thread(target=discord_worker, daemon=True)
        worker_thread.start()
        logger.info("🚀 Worker Discord démarré")

def stop_discord_worker():
    """Arrêter le worker thread Discord"""
    global worker_running, worker_thread
    worker_running = False
    if worker_thread:
        worker_thread.join(timeout=5)
        logger.info("🛑 Worker Discord arrêté")

# Démarrer le worker au démarrage
@app.on_event("startup")
async def startup_event():
    start_discord_worker()

# Arrêter le worker à l'arrêt
@app.on_event("shutdown")
async def shutdown_event():
    stop_discord_worker()

def verify_signature(request: Request, body: bytes) -> bool:
    """Vérifier la signature HMAC-SHA512 du webhook Neynar"""
    signature = request.headers.get("X-Neynar-Signature")
    if not signature:
        logger.warning("❌ Signature manquante dans les headers")
        return False
    
    logger.info(f"🔐 Signature reçue: {signature}")
    logger.info(f"🔐 Secret utilisé: {config.NEYNAR_WEBHOOK_SECRET[:10]}...")
    logger.info(f"🔐 Body length: {len(body)} bytes")
    
    expected_signature = hmac.new(
        config.NEYNAR_WEBHOOK_SECRET.encode('utf-8'),
        body,
        hashlib.sha512
    ).hexdigest()
    
    logger.info(f"🔐 Signature calculée: {expected_signature}")
    is_valid = hmac.compare_digest(signature, expected_signature)
    logger.info(f"🔐 Signature valide: {is_valid}")
    
    return is_valid

def build_cast_embed(cast_data: Dict[str, Any], author: Dict[str, Any],
                    embeds: List[Dict], reactions: Dict, replies: Dict, views: Dict) -> Dict[str, Any]:
    """Construire l'embed Discord pour le cast"""
    try:
        username = author.get('username', 'Unknown')
        text = cast_data.get('text', '')
        
        # Construire l'URL du cast
        cast_hash = cast_data.get('hash', '')
        cast_url = f"https://warpcast.com/{username}/{cast_hash}" if cast_hash else ""
        
        # Gérer les réactions
        reaction_counts = []
        if reactions:
            for reaction_type, users in reactions.items():
                if isinstance(users, list):
                    count = len(users)
                    if count > 0:
                        emoji_map = {
                            'like': '❤️',
                            'recast': '🔄',
                            'reply': '💬'
                        }
                        emoji = emoji_map.get(reaction_type, '👍')
                        reaction_counts.append(f"{emoji} {count}")
        
        # Construire l'embed
        embed = {
            "title": f"@{username} a posté",
            "description": text[:2000] if len(text) <= 2000 else text[:1997] + "...",
            "color": 0x8B5CF6,
            "url": cast_url,
            "timestamp": discord.utils.utcnow().isoformat(),
            "footer": {"text": "Farcaster Tracker"},
            "author": {
                "name": f"@{username}",
                "url": f"https://warpcast.com/{username}",
                "icon_url": author.get('pfp_url', '')
            }
        }
        
        # Ajouter les réactions si disponibles
        if reaction_counts:
            embed["fields"] = [{
                "name": "Réactions",
                "value": " ".join(reaction_counts),
                "inline": True
            }]
        
        # Ajouter l'image si disponible
        if embeds and len(embeds) > 0:
            first_embed = embeds[0]
            if isinstance(first_embed, dict) and 'url' in first_embed:
                embed["thumbnail"] = {"url": str(first_embed['url'])}
        
        return embed
        
    except Exception as e:
        logger.error(f"❌ Erreur lors de la construction de l'embed: {e}")
        return {
            "title": f"@{username} a posté",
            "description": text[:100] + "..." if len(text) > 100 else text,
            "color": 0xFF0000,
            "footer": {"text": "Erreur lors de la construction de l'embed"}
        }

@app.get("/healthz")
async def health_check():
    """Endpoint de santé pour Railway"""
    return {"status": "healthy", "timestamp": discord.utils.utcnow().isoformat()}

@app.get("/webhooks/neynar")
async def webhook_health():
    """Endpoint de santé pour Neynar"""
    return {"status": "webhook endpoint ready"}

@app.post("/webhooks/neynar")
async def neynar_webhook(request: Request):
    """Traiter les webhooks Neynar pour les nouveaux casts"""
    try:
        # Lire le body de la requête
        body = await request.body()
        
        # Vérifier la signature
        if not verify_signature(request, body):
            raise HTTPException(status_code=401, detail="Signature invalide")
        
        # Parser le JSON
        try:
            data = json.loads(body)
        except json.JSONDecodeError as e:
            logger.error(f"❌ Erreur de parsing JSON: {e}")
            raise HTTPException(status_code=400, detail="JSON invalide")
        
        # Log complet de la structure des données pour debug
        logger.info(f"🔍 Structure complète du webhook reçue: {json.dumps(data, indent=2)}")
        
        # Extraire les informations du cast selon différentes structures possibles
        cast_data = None
        author = None
        embeds = []
        reactions = {}
        replies = {}
        views = {}
        
        # Essayer différentes structures de webhook Neynar
        if 'cast' in data and 'author' in data:
            # Structure: { "cast": {...}, "author": {...} }
            cast_data = data.get('cast', {})
            author = data.get('author', {})
            embeds = data.get('embeds', [])
            reactions = data.get('reactions', {})
            replies = data.get('replies', {})
            views = data.get('views', {})
            logger.info("✅ Structure détectée: cast + author séparés")
            
        elif 'data' in data and 'type' in data:
            # Structure: { "type": "cast.created", "data": {...} }
            if data.get('type') == 'cast.created':
                cast_data = data.get('data', {})
                author = cast_data.get('author', {})
                embeds = cast_data.get('embeds', [])
                reactions = cast_data.get('reactions', {})
                replies = cast_data.get('replies', {})
                views = cast_data.get('views', {})
                logger.info("✅ Structure détectée: type cast.created")
            else:
                logger.info(f"ℹ️ Type d'event ignoré: {data.get('type')}")
                return {"status": "ok", "message": f"Event type ignoré: {data.get('type')}"}
                
        elif 'cast' in data and 'author' not in data:
            # Structure: { "cast": {...} } avec author dans cast
            cast_data = data.get('cast', {})
            author = cast_data.get('author', {})
            embeds = cast_data.get('embeds', [])
            reactions = cast_data.get('reactions', {})
            replies = cast_data.get('replies', {})
            views = cast_data.get('views', {})
            logger.info("✅ Structure détectée: cast avec author inclus")
            
        else:
            # Structure inconnue, essayer de trouver des données utiles
            logger.warning("⚠️ Structure de webhook inconnue, tentative d'extraction...")
            
            # Chercher des champs qui pourraient contenir des données de cast
            for key, value in data.items():
                if isinstance(value, dict):
                    if 'text' in value or 'hash' in value:
                        cast_data = value
                        logger.info(f"✅ Cast data trouvé dans la clé: {key}")
                    if 'username' in value or 'fid' in value:
                        author = value
                        logger.info(f"✅ Author trouvé dans la clé: {key}")
                        
            # Si pas trouvé, essayer de traiter data comme cast_data
            if not cast_data and 'data' in data:
                cast_data = data.get('data', {})
                logger.info("✅ Utilisation de data comme cast_data")
        
        if not cast_data or not author:
            logger.warning(f"⚠️ Données de cast ou d'auteur manquantes")
            logger.warning(f"🔍 Cast data: {cast_data}")
            logger.warning(f"🔍 Author: {author}")
            return {"status": "ok", "message": "Données insuffisantes"}
        
        # Log du cast reçu
        cast_text = cast_data.get('text', '')[:50]
        logger.info(f"Cast reçu de {author.get('username', 'Unknown')} (FID: {author.get('fid', 'Unknown')}): {cast_text}...")
        
        # Construire l'embed
        embed_dict = build_cast_embed(cast_data, author, embeds, reactions, replies, views)
        logger.info(f"✅ Embed construit avec succès pour {author.get('username', 'Unknown')}")
        
        # Récupérer les comptes trackés pour cet auteur
        from database import TrackedAccount
        
        # Créer une session DB manuellement
        db = get_session_local()()
        try:
            tracked_accounts = db.query(TrackedAccount).filter(
                TrackedAccount.fid == str(author.get('fid'))
            ).all()
            
            if not tracked_accounts:
                logger.info(f"ℹ️ Aucun compte tracké pour {author.get('username', 'Unknown')}")
                return {"status": "ok", "message": "Aucun compte tracké"}
            
            # Vérifier si ce cast a déjà été livré
            cast_hash = cast_data.get('hash', '')
            if cast_hash:
                existing_delivery = db.query(Delivery).filter(
                    Delivery.cast_hash == cast_hash
                ).first()
                
                if existing_delivery:
                    logger.info(f"ℹ️ Cast {cast_hash} déjà livré")
                    return {"status": "ok", "message": "Cast déjà livré"}
        
        finally:
            db.close()
        
        # Envoyer les notifications
        sent_count = 0
        for tracked_account in tracked_accounts:
            try:
                # Convertir le channel_id en int de manière sécurisée
                channel_id = int(tracked_account.channel_id)
                channel = bot.get_channel(channel_id)
                
                if channel and bot.is_ready():
                    try:
                        # Ajouter le message à la queue Discord
                        discord_queue.put({
                            'channel_id': channel_id,
                            'embed': embed_dict,
                            'author_username': author.get('username', 'Unknown'),
                            'cast_hash': cast_hash,
                            'guild_id': tracked_account.guild_id
                        })
                        
                        logger.info(f"✅ Message ajouté à la queue pour {channel.name}")
                        sent_count += 1
                        
                    except Exception as e:
                        logger.error(f"❌ Erreur lors de l'ajout à la queue: {e}")
                else:
                    if not bot.is_ready():
                        logger.warning(f"⚠️ Bot Discord pas encore prêt")
                    else:
                        logger.warning(f"⚠️ Canal {channel_id} non trouvé")
                        
            except ValueError as e:
                logger.error(f"❌ Erreur de conversion du channel_id '{tracked_account.channel_id}': {e}")
            except Exception as e:
                logger.error(f"❌ Erreur lors de l'envoi de la notification pour {author.get('username', 'Unknown')}: {e}")
        
        logger.info(f"✅ {sent_count} notification(s) ajoutée(s) à la queue")
        return {"status": "success", "sent_count": sent_count}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur lors du traitement du webhook: {e}")
        raise HTTPException(status_code=500, detail="Erreur interne")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=config.PORT)
