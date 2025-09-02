import json
import logging
import time
from typing import List
from database import get_session_local, WebhookState, TrackedAccount
from neynar_client import get_neynar_client
from config import config

logger = logging.getLogger(__name__)

def build_webhook_url(base_url: str, endpoint: str = "webhooks/neynar") -> str:
    """Construire une URL de webhook sans double slash"""
    # Supprimer les slashes en fin de base_url
    base_url = base_url.rstrip('/')
    # Supprimer les slashes en début d'endpoint
    endpoint = endpoint.lstrip('/')
    # Construire l'URL proprement
    return f"{base_url}/{endpoint}"

def sync_neynar_webhook():
    """Synchroniser le webhook Neynar avec les FIDs suivis selon la documentation officielle"""
    try:
        logger.info("Début de la synchronisation du webhook Neynar...")
        
        # Vérifier que le client Neynar est disponible
        if not get_neynar_client() or not hasattr(get_neynar_client(), 'create_webhook'):
            logger.error("Client Neynar non disponible ou invalide")
            return
        
        # Récupérer tous les FIDs suivis (toutes guilds confondues)
        db = get_session_local()()
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
                    logger.info("🔧 Tentative de création du webhook...")
                    webhook = get_neynar_client().create_webhook(
                        build_webhook_url(config.PUBLIC_BASE_URL),
                        all_fids
                    )
                    
                    logger.info(f"🔧 Réponse de création webhook: {webhook}")
                    
                    # Vérifier que la réponse contient un webhook_id
                    if not webhook or "webhook" not in webhook:
                        logger.error(f"❌ Réponse invalide de l'API Neynar: {webhook}")
                        logger.error("❌ La réponse ne contient pas de champ 'webhook'")
                        return
                    
                    webhook_data = webhook["webhook"]
                    if "webhook_id" not in webhook_data:
                        logger.error(f"❌ Réponse webhook invalide: {webhook_data}")
                        logger.error("❌ La réponse webhook ne contient pas de champ 'webhook_id'")
                        return
                    
                    webhook_id = webhook_data["webhook_id"]
                    logger.info(f"✅ Webhook ID extrait: {webhook_id}")
                    
                    webhook_state = WebhookState(
                        id="singleton",
                        webhook_id=webhook_id,
                        active=webhook.get("active", True),
                        author_fids=json.dumps(all_fids)
                    )
                    db.add(webhook_state)
                    db.commit()
                    
                    logger.info(f"✅ Nouveau webhook Neynar créé: {webhook_id}")
                    
                except Exception as e:
                    logger.error(f"❌ Erreur lors de la création du webhook: {e}")
                    logger.error(f"❌ Type d'erreur: {type(e).__name__}")
                    import traceback
                    logger.error(f"❌ Traceback: {traceback.format_exc()}")
                    return
                    
            else:
                # Vérifier si la liste des FIDs a changé
                current_fids = json.loads(webhook_state.author_fids)
                current_fids.sort()
                new_fids = sorted(all_fids)
                
                if current_fids != new_fids:
                    logger.info(f"FIDs modifiés, mise à jour du webhook... Anciens: {current_fids}, Nouveaux: {new_fids}")
                    
                    try:
                        # Mettre à jour le webhook existant selon la structure officielle
                        updated_webhook = get_neynar_client().update_webhook(
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
                        # Si le webhook n'existe plus côté Neynar (404), le recréer proprement
                        error_message = str(e).lower()
                        if "404" in error_message or "not found" in error_message:
                            logger.warning("Webhook introuvable côté Neynar. Suppression de l'état local et recréation...")
                            try:
                                # Supprimer l'état local existant
                                db.delete(webhook_state)
                                db.commit()
                                # Créer un nouveau webhook avec les FIDs actuels
                                new_webhook = get_neynar_client().create_webhook(
                                    build_webhook_url(config.PUBLIC_BASE_URL),
                                    all_fids
                                )
                                if not new_webhook or "webhook" not in new_webhook or "webhook_id" not in new_webhook["webhook"]:
                                    logger.error(f"❌ Réponse invalide lors de la recréation: {new_webhook}")
                                    return
                                new_id = new_webhook["webhook"]["webhook_id"]
                                logger.info(f"✅ Nouveau webhook recréé avec l'ID: {new_id}")
                                # Enregistrer le nouvel état
                                new_state = WebhookState(
                                    id="singleton",
                                    webhook_id=new_id,
                                    active=new_webhook.get("active", True),
                                    author_fids=json.dumps(all_fids)
                                )
                                db.add(new_state)
                                db.commit()
                                logger.info("✅ État du webhook recréé et synchronisé")
                            except Exception as recreate_error:
                                logger.error(f"❌ Échec de la recréation du webhook après 404: {recreate_error}")
                                return
                        else:
                            # Ne pas lever l'exception, juste logger l'erreur
                            return
                else:
                    logger.info("Aucun changement de FIDs détecté, webhook à jour")
            
            logger.info("Synchronisation du webhook Neynar terminée avec succès")
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Échec de la synchronisation du webhook Neynar: {e}")
        # Ne pas lever l'exception, juste logger l'erreur
        return

def get_webhook_state():
    """Récupérer l'état actuel du webhook"""
    db = get_session_local()()
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
                get_neynar_client().delete_webhook(webhook_state.webhook_id)
                logger.info(f"Webhook Neynar {webhook_state.webhook_id} supprimé")
                
                db = get_session_local()()
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
        webhook_details = get_neynar_client().get_webhook(webhook_state.webhook_id)
        
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
    """Récupérer les statistiques du webhook Neynar"""
    try:
        logger.info("🔧 Tentative de récupération des stats du webhook...")
        
        db = get_session_local()()
        try:
            webhook_state = db.query(WebhookState).filter_by(id="singleton").first()
            
            if not webhook_state:
                logger.info("📝 Aucun état de webhook trouvé")
                return {"status": "no_webhook", "message": "Aucun webhook configuré"}
            
            logger.info(f"🔧 État du webhook trouvé: {webhook_state.webhook_id}")
            
            client = get_neynar_client()
            logger.info(f"🔧 Client Neynar récupéré: {client}")
            
            if client is None:
                logger.error("❌ Client Neynar est None - vérification de la configuration")
                return {"status": "error", "message": "Client Neynar non initialisé"}
            
            logger.info(f"🔧 Client Neynar valide: {type(client).__name__}")
            
            webhook_details = client.get_webhook(webhook_state.webhook_id)
            logger.info(f"🔧 Détails du webhook récupérés: {webhook_details}")
            
            if webhook_details.get("active"):
                return {
                    "status": "active",
                    "webhook_id": webhook_state.webhook_id,
                    "author_fids_count": len(json.loads(webhook_state.author_fids)),
                    "message": "Webhook actif"
                }
            else:
                return {
                    "status": "inactive",
                    "webhook_id": webhook_state.webhook_id,
                    "message": "Webhook inactif"
                }
                
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"❌ Erreur lors de la récupération des stats: {e}")
        logger.error(f"❌ Type d'erreur: {type(e).__name__}")
        import traceback
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        return {"status": "error", "message": str(e)}
