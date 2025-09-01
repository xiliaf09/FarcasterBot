import json
import logging
from typing import List
from database import SessionLocal, WebhookState, TrackedAccount
from neynar_client import neynar_client
from config import config

logger = logging.getLogger(__name__)

def sync_neynar_webhook():
    """Synchroniser le webhook Neynar avec les FIDs suivis"""
    try:
        logger.info("Début de la synchronisation du webhook Neynar...")
        
        # Récupérer tous les FIDs suivis (toutes guilds confondues)
        db = SessionLocal()
        try:
            tracked_accounts = db.query(TrackedAccount.fid).distinct().all()
            all_fids = [account[0] for account in tracked_accounts]
            
            logger.info(f"FIDs collectés pour le tracking: {len(all_fids)} - {all_fids}")
            
            # Récupérer l'état actuel du webhook
            webhook_state = db.query(WebhookState).filter_by(id="singleton").first()
            
            if not webhook_state:
                # Créer un nouveau webhook
                logger.info("Aucun état de webhook trouvé, création d'un nouveau webhook...")
                webhook = neynar_client.create_webhook(
                    f"{config.PUBLIC_BASE_URL}/webhooks/neynar",
                    all_fids
                )
                
                webhook_state = WebhookState(
                    id="singleton",
                    webhook_id=webhook["id"],
                    active=webhook["active"],
                    author_fids=json.dumps(all_fids)
                )
                db.add(webhook_state)
                db.commit()
                
                logger.info(f"Nouveau webhook Neynar créé: {webhook['id']}")
            else:
                # Vérifier si la liste des FIDs a changé
                current_fids = json.loads(webhook_state.author_fids)
                current_fids.sort()
                new_fids = sorted(all_fids)
                
                if current_fids != new_fids:
                    logger.info(f"FIDs modifiés, mise à jour du webhook... Anciens: {current_fids}, Nouveaux: {new_fids}")
                    
                    # Mettre à jour le webhook existant
                    updated_webhook = neynar_client.update_webhook(
                        webhook_state.webhook_id,
                        all_fids
                    )
                    
                    # Mettre à jour l'état en base
                    webhook_state.author_fids = json.dumps(all_fids)
                    db.commit()
                    
                    logger.info(f"Webhook Neynar mis à jour: {webhook_state.webhook_id}")
                else:
                    logger.info("Aucun changement de FIDs détecté, webhook à jour")
            
            logger.info("Synchronisation du webhook Neynar terminée avec succès")
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Échec de la synchronisation du webhook Neynar: {e}")
        raise

def get_webhook_state():
    """Récupérer l'état actuel du webhook"""
    db = SessionLocal()
    try:
        return db.query(WebhookState).filter_by(id="singleton").first()
    finally:
        db.close()

def cleanup_webhook():
    """Nettoyer le webhook Neynar"""
    try:
        webhook_state = get_webhook_state()
        if webhook_state:
            neynar_client.delete_webhook(webhook_state.webhook_id)
            
            db = SessionLocal()
            try:
                db.delete(webhook_state)
                db.commit()
                logger.info("Webhook Neynar nettoyé")
            finally:
                db.close()
    except Exception as e:
        logger.error(f"Erreur lors du nettoyage du webhook: {e}")
