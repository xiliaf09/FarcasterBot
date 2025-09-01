import json
import logging
import time
from typing import List
from database import SessionLocal, WebhookState, TrackedAccount
from neynar_client import neynar_client
from config import config

logger = logging.getLogger(__name__)

def sync_neynar_webhook():
    """Synchroniser le webhook Neynar avec les FIDs suivis selon la documentation officielle"""
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
                # Créer un nouveau webhook selon la structure officielle
                logger.info("Aucun état de webhook trouvé, création d'un nouveau webhook...")
                
                try:
                    webhook = neynar_client.create_webhook(
                        f"{config.PUBLIC_BASE_URL}/webhooks/neynar",
                        all_fids
                    )
                    
                    webhook_state = WebhookState(
                        id="singleton",
                        webhook_id=webhook["id"],
                        active=webhook.get("active", True),
                        author_fids=json.dumps(all_fids)
                    )
                    db.add(webhook_state)
                    db.commit()
                    
                    logger.info(f"Nouveau webhook Neynar créé: {webhook['id']}")
                    
                except Exception as e:
                    logger.error(f"Erreur lors de la création du webhook: {e}")
                    raise
                    
            else:
                # Vérifier si la liste des FIDs a changé
                current_fids = json.loads(webhook_state.author_fids)
                current_fids.sort()
                new_fids = sorted(all_fids)
                
                if current_fids != new_fids:
                    logger.info(f"FIDs modifiés, mise à jour du webhook... Anciens: {current_fids}, Nouveaux: {new_fids}")
                    
                    try:
                        # Mettre à jour le webhook existant selon la structure officielle
                        updated_webhook = neynar_client.update_webhook(
                            webhook_state.webhook_id,
                            all_fids
                        )
                        
                        # Mettre à jour l'état en base
                        webhook_state.author_fids = json.dumps(all_fids)
                        webhook_state.updated_at = time.time()
                        db.commit()
                        
                        logger.info(f"Webhook Neynar mis à jour: {webhook_state.webhook_id}")
                        
                    except Exception as e:
                        logger.error(f"Erreur lors de la mise à jour du webhook: {e}")
                        raise
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
    """Nettoyer le webhook Neynar selon la documentation officielle"""
    try:
        webhook_state = get_webhook_state()
        if webhook_state:
            try:
                neynar_client.delete_webhook(webhook_state.webhook_id)
                logger.info(f"Webhook Neynar {webhook_state.webhook_id} supprimé")
                
                db = SessionLocal()
                try:
                    db.delete(webhook_state)
                    db.commit()
                    logger.info("État du webhook supprimé de la base de données")
                finally:
                    db.close()
                    
            except Exception as e:
                logger.error(f"Erreur lors de la suppression du webhook: {e}")
                raise
                
    except Exception as e:
        logger.error(f"Erreur lors du nettoyage du webhook: {e}")

def test_webhook_connection():
    """Tester la connexion au webhook Neynar selon la documentation officielle"""
    try:
        webhook_state = get_webhook_state()
        if not webhook_state:
            logger.info("Aucun webhook configuré")
            return False
        
        # Tester la récupération des détails du webhook
        webhook_details = neynar_client.get_webhook(webhook_state.webhook_id)
        
        if webhook_details.get("active"):
            logger.info("✅ Webhook Neynar actif et accessible")
            return True
        else:
            logger.warning("⚠️ Webhook Neynar inactif")
            return False
            
    except Exception as e:
        logger.error(f"❌ Erreur de connexion au webhook: {e}")
        return False

def get_webhook_stats():
    """Récupérer les statistiques du webhook selon la documentation officielle"""
    try:
        webhook_state = get_webhook_state()
        if not webhook_state:
            return {"status": "no_webhook"}
        
        webhook_details = neynar_client.get_webhook(webhook_state.webhook_id)
        
        return {
            "status": "active" if webhook_details.get("active") else "inactive",
            "webhook_id": webhook_state.webhook_id,
            "author_fids_count": len(json.loads(webhook_state.author_fids)),
            "last_updated": webhook_state.updated_at.isoformat() if webhook_state.updated_at else None,
            "webhook_details": webhook_details
        }
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des stats: {e}")
        return {"status": "error", "message": str(e)}
