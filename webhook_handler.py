from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
import hmac
import hashlib
import json
import logging
import uuid
from typing import Dict, Any, List
from database import SessionLocal, TrackedAccount, Delivery
from discord_bot import bot
from config import config

# Configuration du logging
logging.basicConfig(level=getattr(logging, config.LOG_LEVEL))
logger = logging.getLogger(__name__)

# Créer l'application FastAPI
app = FastAPI(title="Farcaster Tracker Webhook", version="1.0.0")

def verify_signature(request: Request, body: bytes) -> bool:
    """Vérifier la signature du webhook Neynar"""
    signature = request.headers.get("X-Neynar-Signature")
    if not signature:
        return False
    
    # Calculer le HMAC-SHA512
    expected_signature = hmac.new(
        config.NEYNAR_WEBHOOK_SECRET.encode('utf-8'),
        body,
        hashlib.sha512
    ).hexdigest()
    
    return hmac.compare_digest(signature, expected_signature)

def get_db():
    """Dependency pour obtenir une session de base de données"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
async def root():
    """Route racine"""
    return {"message": "Farcaster Tracker Webhook Server", "status": "running"}

@app.get("/healthz")
async def health_check():
    """Route de santé"""
    return {"status": "healthy", "service": "farcaster-tracker"}

@app.post("/webhooks/neynar")
async def neynar_webhook(request: Request, db: SessionLocal = Depends(get_db)):
    """Endpoint pour recevoir les webhooks Neynar selon la structure officielle"""
    try:
        # Lire le corps brut de la requête
        body = await request.body()
        
        # Vérifier la signature
        if not verify_signature(request, body):
            logger.warning("Signature de webhook invalide reçue")
            raise HTTPException(status_code=401, detail="Signature invalide")
        
        # Parser le JSON
        try:
            data = json.loads(body)
        except json.JSONDecodeError as e:
            logger.error(f"Erreur de parsing JSON: {e}")
            raise HTTPException(status_code=400, detail="JSON invalide")
        
        # Vérifier que c'est un event cast.created selon la structure officielle
        if data.get("type") != "cast.created":
            logger.info(f"Event ignoré (type: {data.get('type')})")
            return {"status": "ignored", "reason": "not cast.created"}
        
        # Extraire les données du cast selon la structure officielle
        cast_data = data.get("data", {})
        author = cast_data.get("author", {})
        cast_hash = cast_data.get("hash")
        text = cast_data.get("text", "")
        timestamp = cast_data.get("timestamp")
        parent_hash = cast_data.get("parent_hash")
        parent_url = cast_data.get("parent_url")
        thread_hash = cast_data.get("thread_hash")
        embeds = cast_data.get("embeds", [])
        reactions = cast_data.get("reactions", {})
        replies = cast_data.get("replies", {})
        views = cast_data.get("views", {})
        
        if not all([cast_hash, author.get("fid"), author.get("username")]):
            logger.warning("Données de cast incomplètes reçues")
            return {"status": "error", "reason": "incomplete_cast_data"}
        
        logger.info(f"Cast reçu de {author['username']} (FID: {author['fid']}): {text[:50]}...")
        
        # Vérifier si la base de données est disponible
        if db is None:
            logger.warning("Base de données non disponible, webhook ignoré")
            return {"status": "error", "reason": "database_unavailable"}
        
        # Trouver tous les serveurs qui suivent cet auteur
        try:
            tracked_accounts = db.query(TrackedAccount).filter_by(fid=author["fid"]).all()
        except Exception as e:
            logger.error(f"Erreur lors de la requête base de données: {e}")
            return {"status": "error", "reason": "database_error"}
        
        if not tracked_accounts:
            logger.info(f"Aucun serveur ne suit l'auteur {author['username']} (FID: {author['fid']})")
            return {"status": "ignored", "reason": "author_not_tracked"}
        
        # Envoyer les notifications Discord
        sent_count = 0
        for tracked_account in tracked_accounts:
            try:
                # Vérifier si ce cast a déjà été livré dans ce salon
                try:
                    existing_delivery = db.query(Delivery).filter_by(
                        cast_hash=cast_hash,
                        channel_id=tracked_account.channel_id
                    ).first()
                except Exception as e:
                    logger.error(f"Erreur lors de la vérification de livraison: {e}")
                    continue
                
                if existing_delivery:
                    logger.info(f"Cast {cast_hash} déjà livré dans le salon {tracked_account.channel_id}")
                    continue
                
                # Construire l'embed Discord avec tous les champs disponibles
                embed = build_cast_embed(cast_data, author, embeds, reactions, replies, views)
                
                # Envoyer le message
                channel = bot.get_channel(int(tracked_account.channel_id))
                if channel:
                    await channel.send(embed=embed)
                    
                    # Marquer comme livré
                    try:
                        delivery = Delivery(
                            id=str(uuid.uuid4()),
                            guild_id=tracked_account.guild_id,
                            channel_id=tracked_account.channel_id,
                            cast_hash=cast_hash
                        )
                        db.add(delivery)
                        
                        sent_count += 1
                        logger.info(f"Notification envoyée dans {channel.name} pour {author['username']}")
                    except Exception as e:
                        logger.error(f"Erreur lors de l'ajout de la livraison: {e}")
                        # Continuer même si la livraison échoue
                        
                else:
                    logger.warning(f"Canal {tracked_account.channel_id} non trouvé")
                    
            except Exception as e:
                logger.error(f"Erreur lors de l'envoi de la notification pour {author['username']}: {e}")
        
        # Commit des livraisons
        if sent_count > 0:
            try:
                db.commit()
                logger.info(f"{sent_count} notification(s) envoyée(s) pour le cast de {author['username']}")
            except Exception as e:
                logger.error(f"Erreur lors du commit des livraisons: {e}")
        
        return {
            "status": "success",
            "notifications_sent": sent_count,
            "author": author["username"],
            "cast_hash": cast_hash
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors du traitement du webhook: {e}")
        raise HTTPException(status_code=500, detail="Erreur interne du serveur")

def build_cast_embed(cast_data: Dict[str, Any], author: Dict[str, Any], 
                    embeds: List[Dict], reactions: Dict, replies: Dict, views: Dict) -> Dict[str, Any]:
    """Construire l'embed Discord pour un cast selon la structure officielle Neynar"""
    # Construire l'URL Warpcast
    username = author.get("username", "")
    cast_hash = cast_data.get("hash", "")
    short_hash = cast_hash[:8] if len(cast_hash) > 8 else cast_hash
    warpcast_url = f"https://warpcast.com/{username}/{short_hash}"
    
    # Tronquer le texte si nécessaire
    text = cast_data.get("text", "")
    if len(text) > 500:
        text = text[:497] + "..."
    
    # Construire l'embed de base
    embed = {
        "title": f"@{username} a posté",
        "description": text,
        "url": warpcast_url,
        "color": 0x8B5CF6,  # Couleur Farcaster
        "timestamp": cast_data.get("timestamp"),
        "footer": {
            "text": f"FID: {author.get('fid')} • {cast_data.get('timestamp', '')}"
        }
    }
    
    # Ajouter les champs conditionnels selon la structure officielle
    fields = []
    
    # Gestion des replies
    if cast_data.get("parent_hash") or cast_data.get("parent_url"):
        if cast_data.get("parent_url"):
            fields.append({
                "name": "💬 Réponse à",
                "value": cast_data["parent_url"],
                "inline": False
            })
        else:
            fields.append({
                "name": "💬 Réponse",
                "value": "Réponse dans un thread",
                "inline": False
            })
    
    # Gestion des threads
    if cast_data.get("thread_hash"):
        fields.append({
            "name": "🧵 Thread",
            "value": f"Thread: {cast_data['thread_hash'][:8]}...",
            "inline": True
        })
    
    # Gestion des embeds
    if embeds:
        embed_count = len(embeds)
        fields.append({
            "name": "🔗 Liens",
            "value": f"{embed_count} lien(s) attaché(s)",
            "inline": True
        })
    
    # Gestion des réactions
    if reactions:
        total_reactions = sum(reactions.values())
        fields.append({
            "name": "❤️ Réactions",
            "value": f"{total_reactions} réaction(s)",
            "inline": True
        })
    
    # Gestion des vues
    if views:
        view_count = views.get("count", 0)
        if view_count > 0:
            fields.append({
                "name": "👁️ Vues",
                "value": f"{view_count} vue(s)",
                "inline": True
            })
    
    # Gestion des replies
    if replies:
        reply_count = replies.get("count", 0)
        if reply_count > 0:
            fields.append({
                "name": "💬 Réponses",
                "value": f"{reply_count} réponse(s)",
                "inline": True
            })
    
    if fields:
        embed["fields"] = fields
    
    # Ajouter l'avatar si disponible
    if author.get("pfp_url"):  # Correction selon la doc officielle
        embed["thumbnail"] = {"url": author["pfp_url"]}
    
    # Ajouter des informations sur l'auteur
    embed["author"] = {
        "name": author.get("display_name", username),
        "url": f"https://warpcast.com/{username}",
        "icon_url": author.get("pfp_url", "")
    }
    
    return embed

@app.get("/admin/resync")
async def admin_resync():
    """Route admin pour forcer la resynchronisation du webhook (dev only)"""
    try:
        from webhook_sync import sync_neynar_webhook
        # sync_neynar_webhook()  # Désactivé temporairement
        return {"status": "success", "message": "Webhook resynchronisation désactivée temporairement"}
    except Exception as e:
        logger.error(f"Erreur lors de la resynchronisation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/webhook/status")
async def admin_webhook_status():
    """Route admin pour vérifier le statut du webhook Neynar"""
    try:
        from webhook_sync import get_webhook_stats
        stats = get_webhook_stats()
        return stats
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du statut: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/webhook/test")
async def admin_webhook_test():
    """Route admin pour tester la connexion au webhook Neynar"""
    try:
        from webhook_sync import test_webhook_connection
        success = test_webhook_connection()
        return {
            "status": "success" if success else "error",
            "webhook_connection": "active" if success else "failed"
        }
    except Exception as e:
        logger.error(f"Erreur lors du test de connexion: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/neynar/rate-limits")
async def admin_neynar_rate_limits():
    """Route admin pour vérifier les rate limits Neynar"""
    try:
        from neynar_client import neynar_client
        return {
            "status": "success",
            "current_plan": neynar_client.current_plan,
            "rate_limits": neynar_client.rate_limits[neynar_client.current_plan],
            "requests_this_minute": neynar_client.requests_this_minute,
            "last_request_time": neynar_client.last_request_time
        }
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des rate limits: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/admin/neynar/set-plan")
async def admin_set_plan(plan: str):
    """Route admin pour changer le plan de rate limits"""
    try:
        from neynar_client import neynar_client
        neynar_client.set_plan(plan)
        return {
            "status": "success",
            "message": f"Plan défini sur: {plan}",
            "new_plan": neynar_client.current_plan
        }
    except Exception as e:
        logger.error(f"Erreur lors du changement de plan: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=config.PORT)
