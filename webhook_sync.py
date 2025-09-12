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
            all_fids = [int(account[0]) for account in tracked_accounts]  # S'assurer que ce sont des entiers
            
            logger.info(f"FIDs collectés pour le tracking: {len(all_fids)} - {all_fids}")
            
            # Récupérer l'état actuel du webhook
            webhook_state = db.query(WebhookState).filter_by(id="singleton").first()
            
            if not webhook_state:
                # FORCER L'UTILISATION DU WEBHOOK EXISTANT 01K45KREDQ77B80YD87AAXJ3E8
                logger.info("🔒 Aucun état de webhook trouvé, utilisation FORCÉE du webhook existant 01K45KREDQ77B80YD87AAXJ3E8")
                
                # Créer l'état local avec le webhook existant
                webhook_state = WebhookState(
                    id="singleton",
                    webhook_id="01K45KREDQ77B80YD87AAXJ3E8",  # WEBHOOK FIXE
                    active=True,
                    author_fids=json.dumps(all_fids)
                )
                db.add(webhook_state)
                db.commit()
                
                logger.info("✅ État local créé avec le webhook fixe 01K45KREDQ77B80YD87AAXJ3E8")
                
                # Mettre à jour le webhook existant avec les FIDs actuels
                try:
                    updated_webhook = get_neynar_client().update_webhook(
                        "01K45KREDQ77B80YD87AAXJ3E8",  # WEBHOOK FIXE
                        all_fids
                    )
                    logger.info("✅ Webhook existant 01K45KREDQ77B80YD87AAXJ3E8 mis à jour avec les FIDs actuels")
                except Exception as e:
                    logger.warning(f"⚠️ Impossible de mettre à jour le webhook existant: {e}")
                    logger.warning("⚠️ Mais l'état local est créé et le webhook sera utilisé")
                    
            else:
                # Vérifier si la liste des FIDs a changé
                current_fids = json.loads(webhook_state.author_fids)
                current_fids.sort()
                new_fids = sorted(all_fids)
                
                # FORCER L'UTILISATION DU WEBHOOK FIXE 01K45KREDQ77B80YD87AAXJ3E8
                if webhook_state.webhook_id != "01K45KREDQ77B80YD87AAXJ3E8":
                    logger.warning("🔒 Webhook ID différent du webhook fixe, FORCAGE de l'utilisation du webhook 01K45KREDQ77B80YD87AAXJ3E8")
                    webhook_state.webhook_id = "01K45KREDQ77B80YD87AAXJ3E8"
                    db.commit()
                    logger.info("✅ Webhook ID forcé sur 01K45KREDQ77B80YD87AAXJ3E8")
                
                # Vérifier l'état du webhook fixe côté Neynar
                try:
                    webhook_details = get_neynar_client().get_webhook("01K45KREDQ77B80YD87AAXJ3E8")
                    if not webhook_details or not webhook_details.get("active"):
                        logger.warning("⚠️ Webhook fixe 01K45KREDQ77B80YD87AAXJ3E8 inactif côté Neynar, tentative de réactivation...")
                        try:
                            # Réactiver le webhook fixe avec les FIDs actuels
                            reactivated_webhook = get_neynar_client().update_webhook(
                                "01K45KREDQ77B80YD87AAXJ3E8",
                                all_fids
                            )
                            logger.info("✅ Webhook fixe 01K45KREDQ77B80YD87AAXJ3E8 réactivé")
                            # Mettre à jour l'état local
                            webhook_state.author_fids = json.dumps(all_fids)
                            webhook_state.updated_at = time.time()
                            db.commit()
                        except Exception as reactivate_error:
                            logger.error(f"❌ Impossible de réactiver le webhook fixe: {reactivate_error}")
                            logger.warning("⚠️ Mais on continue avec l'état local existant")
                    else:
                        logger.info("✅ Webhook fixe 01K45KREDQ77B80YD87AAXJ3E8 actif et accessible")
                except Exception as check_error:
                    logger.warning(f"⚠️ Impossible de vérifier l'état du webhook fixe: {check_error}")
                    logger.warning("⚠️ Mais on continue avec l'état local existant")
                
                if current_fids != new_fids:
                    logger.info(f"FIDs modifiés, mise à jour du webhook... Anciens: {current_fids}, Nouveaux: {new_fids}")
                    
                    try:
                        # Mettre à jour le webhook fixe 01K45KREDQ77B80YD87AAXJ3E8
                        updated_webhook = get_neynar_client().update_webhook(
                            "01K45KREDQ77B80YD87AAXJ3E8",  # WEBHOOK FIXE
                            all_fids
                        )
                        
                        # Mettre à jour l'état en base
                        webhook_state.author_fids = json.dumps(all_fids)
                        webhook_state.updated_at = time.time()
                        db.commit()
                        
                        logger.info("✅ Webhook fixe 01K45KREDQ77B80YD87AAXJ3E8 mis à jour avec succès")
                        
                    except Exception as e:
                        logger.error(f"Erreur lors de la mise à jour du webhook: {e}")
                        # STRATÉGIE CONSERVATIVE : Ne JAMAIS recréer le webhook
                        # Si erreur, on garde l'ancien état et on log l'erreur
                        error_message = str(e).lower()
                        if "404" in error_message or "not found" in error_message:
                            logger.warning("⚠️ Webhook introuvable côté Neynar, mais on NE LE RECRÉE PAS")
                            logger.warning("⚠️ On garde l'état local pour éviter la perte de connexion")
                            logger.warning("⚠️ Le webhook sera récupéré au prochain redémarrage du bot")
                            # On ne fait RIEN, on garde l'état local
                        else:
                            logger.warning("⚠️ Erreur de mise à jour, mais on garde l'état existant")
                            # On ne fait RIEN, on garde l'état local
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
            # EMPÊCHER LA SUPPRESSION DU WEBHOOK FIXE
            if webhook_state.webhook_id == "01K45KREDQ77B80YD87AAXJ3E8":
                logger.warning("🔒 TENTATIVE DE SUPPRESSION DU WEBHOOK FIXE BLOQUÉE")
                logger.warning("🔒 Le webhook 01K45KREDQ77B80YD87AAXJ3E8 ne peut pas être supprimé")
                return
            
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
        
        # Tester la récupération des détails du webhook fixe
        webhook_details = get_neynar_client().get_webhook("01K45KREDQ77B80YD87AAXJ3E8")  # WEBHOOK FIXE
        
        if webhook_details.get("active"):
            logger.info("✅ Webhook fixe 01K45KREDQ77B80YD87AAXJ3E8 actif et accessible")
            return True
        else:
            logger.warning("⚠️ Webhook fixe 01K45KREDQ77B80YD87AAXJ3E8 inactif")
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
            
            webhook_details = client.get_webhook("01K45KREDQ77B80YD87AAXJ3E8")  # WEBHOOK FIXE
            logger.info(f"🔧 Détails du webhook fixe récupérés: {webhook_details}")
            
            if webhook_details.get("active"):
                return {
                    "status": "active",
                    "webhook_id": "01K45KREDQ77B80YD87AAXJ3E8",  # WEBHOOK FIXE
                    "author_fids_count": len(json.loads(webhook_state.author_fids)),
                    "message": "Webhook fixe actif"
                }
            else:
                return {
                    "status": "inactive",
                    "webhook_id": "01K45KREDQ77B80YD87AAXJ3E8",  # WEBHOOK FIXE
                    "message": "Webhook fixe inactif"
                }
                
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"❌ Erreur lors de la récupération des stats: {e}")
        logger.error(f"❌ Type d'erreur: {type(e).__name__}")
        import traceback
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        return {"status": "error", "message": str(e)}

def force_webhook_fixe():
    """Forcer l'utilisation du webhook fixe 01K45KREDQ77B80YD87AAXJ3E8"""
    try:
        logger.info("🔒 FORCAGE de l'utilisation du webhook fixe 01K45KREDQ77B80YD87AAXJ3E8")
        
        db = get_session_local()()
        try:
            # Récupérer ou créer l'état du webhook
            webhook_state = db.query(WebhookState).filter_by(id="singleton").first()
            
            if not webhook_state:
                # Créer un nouvel état avec le webhook fixe
                webhook_state = WebhookState(
                    id="singleton",
                    webhook_id="01K45KREDQ77B80YD87AAXJ3E8",  # WEBHOOK FIXE
                    active=True,
                    author_fids=json.dumps([])
                )
                db.add(webhook_state)
                logger.info("✅ Nouvel état créé avec le webhook fixe")
            else:
                # Forcer l'utilisation du webhook fixe
                if webhook_state.webhook_id != "01K45KREDQ77B80YD87AAXJ3E8":
                    logger.warning(f"🔒 Webhook ID changé de {webhook_state.webhook_id} vers 01K45KREDQ77B80YD87AAXJ3E8")
                    webhook_state.webhook_id = "01K45KREDQ77B80YD87AAXJ3E8"
                else:
                    logger.info("✅ Webhook ID déjà correct: 01K45KREDQ77B80YD87AAXJ3E8")
            
            # Récupérer tous les FIDs trackés
            tracked_accounts = db.query(TrackedAccount.fid).distinct().all()
            all_fids = [int(account[0]) for account in tracked_accounts]  # S'assurer que ce sont des entiers
            
            # Mettre à jour l'état local
            webhook_state.author_fids = json.dumps(all_fids)
            webhook_state.updated_at = time.time()
            db.commit()
            
            logger.info(f"✅ État local synchronisé avec {len(all_fids)} FID(s)")
            
            # VÉRIFIER D'ABORD SI LE WEBHOOK EXISTE ENCORE CÔTÉ NEYNAR
            try:
                webhook_details = get_neynar_client().get_webhook("01K45KREDQ77B80YD87AAXJ3E8")
                if webhook_details and webhook_details.get("active"):
                    logger.info("✅ Webhook fixe 01K45KREDQ77B80YD87AAXJ3E8 existe et est actif côté Neynar")
                    
                    # Mettre à jour le webhook côté Neynar
                    try:
                        updated_webhook = get_neynar_client().update_webhook(
                            "01K45KREDQ77B80YD87AAXJ3E8",  # WEBHOOK FIXE
                            all_fids
                        )
                        logger.info("✅ Webhook fixe 01K45KREDQ77B80YD87AAXJ3E8 mis à jour côté Neynar")
                        return True
                    except Exception as e:
                        logger.warning(f"⚠️ Impossible de mettre à jour le webhook côté Neynar: {e}")
                        logger.warning("⚠️ Mais l'état local est synchronisé")
                        return False
                else:
                    logger.warning("⚠️ Webhook fixe 01K45KREDQ77B80YD87AAXJ3E8 n'existe plus ou est inactif côté Neynar")
                    logger.warning("⚠️ Il faut le recréer manuellement sur Neynar ou utiliser un autre webhook")
                    return False
                    
            except Exception as e:
                if "404" in str(e) or "not found" in str(e).lower():
                    logger.error("❌ Webhook fixe 01K45KREDQ77B80YD87AAXJ3E8 N'EXISTE PLUS côté Neynar !")
                    logger.error("❌ Il faut le recréer manuellement sur Neynar ou utiliser un autre webhook")
                    return False
                else:
                    logger.warning(f"⚠️ Impossible de vérifier l'état du webhook côté Neynar: {e}")
                    logger.warning("⚠️ Mais l'état local est synchronisé")
                    return False
                
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"❌ Erreur lors du forçage du webhook fixe: {e}")
        return False

def add_fids_to_webhook(new_fids: List[str]):
    """Ajouter des FIDs au webhook existant SANS le recréer"""
    try:
        logger.info(f"🔧 Tentative d'ajout de FIDs au webhook existant: {new_fids}")
        
        db = get_session_local()()
        try:
            webhook_state = db.query(WebhookState).filter_by(id="singleton").first()
            
            if not webhook_state:
                logger.warning("⚠️ Aucun webhook existant, impossible d'ajouter des FIDs")
                return False
            
            # Récupérer les FIDs actuels
            current_fids = json.loads(webhook_state.author_fids)
            # S'assurer que tous les FIDs sont des strings pour la cohérence
            current_fids = [str(fid) for fid in current_fids]
            logger.info(f"🔧 FIDs actuels: {current_fids}")
            
            # Ajouter les nouveaux FIDs (sans doublons) - s'assurer qu'ils sont des strings
            new_fids_str = [str(fid) for fid in new_fids]
            updated_fids = list(set(current_fids + new_fids_str))
            logger.info(f"🔧 FIDs mis à jour: {updated_fids}")
            
            if updated_fids == current_fids:
                logger.info("✅ Aucun nouveau FID à ajouter")
                return True
            
            # VÉRIFIER D'ABORD SI LE WEBHOOK EXISTE ENCORE CÔTÉ NEYNAR
            try:
                webhook_details = get_neynar_client().get_webhook("01K45KREDQ77B80YD87AAXJ3E8")
                if webhook_details and webhook_details.get("active"):
                    logger.info("✅ Webhook fixe 01K45KREDQ77B80YD87AAXJ3E8 existe et est actif côté Neynar")
                    
                    # Mettre à jour le webhook fixe 01K45KREDQ77B80YD87AAXJ3E8
                    try:
                        # Convertir les FIDs en entiers pour l'API Neynar
                        updated_fids_int = [int(fid) for fid in updated_fids]
                        updated_webhook = get_neynar_client().update_webhook(
                            "01K45KREDQ77B80YD87AAXJ3E8",  # WEBHOOK FIXE
                            updated_fids_int
                        )
                        
                        # Mettre à jour l'état local
                        webhook_state.author_fids = json.dumps(updated_fids)
                        webhook_state.updated_at = time.time()
                        db.commit()
                        
                        logger.info("✅ FIDs ajoutés au webhook fixe 01K45KREDQ77B80YD87AAXJ3E8")
                        return True
                        
                    except Exception as update_error:
                        logger.error(f"❌ Erreur lors de la mise à jour du webhook: {update_error}")
                        logger.warning("⚠️ On garde l'état local existant pour éviter la perte de connexion")
                        return False
                        
                else:
                    logger.warning("⚠️ Webhook fixe 01K45KREDQ77B80YD87AAXJ3E8 n'existe plus ou est inactif côté Neynar")
                    logger.warning("⚠️ Il faut le recréer manuellement sur Neynar ou utiliser un autre webhook")
                    return False
                    
            except Exception as e:
                if "404" in str(e) or "not found" in str(e).lower():
                    logger.error("❌ Webhook fixe 01K45KREDQ77B80YD87AAXJ3E8 N'EXISTE PLUS côté Neynar !")
                    logger.error("❌ Il faut le recréer manuellement sur Neynar ou utiliser un autre webhook")
                    return False
                else:
                    logger.warning(f"⚠️ Impossible de vérifier l'état du webhook côté Neynar: {e}")
                    logger.warning("⚠️ Mais l'état local est synchronisé")
                    return False
                
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"❌ Erreur lors de l'ajout des FIDs: {e}")
        return False

def remove_fids_from_webhook(fids_to_remove: List[str]):
    """Retirer des FIDs du webhook existant SANS le recréer"""
    try:
        logger.info(f"🔧 Tentative de retrait de FIDs du webhook existant: {fids_to_remove}")
        
        db = get_session_local()()
        try:
            webhook_state = db.query(WebhookState).filter_by(id="singleton").first()
            
            if not webhook_state:
                logger.warning("⚠️ Aucun webhook existant, impossible de retirer des FIDs")
                return False
            
            # Récupérer les FIDs actuels
            current_fids = json.loads(webhook_state.author_fids)
            # S'assurer que tous les FIDs sont des strings pour la cohérence
            current_fids = [str(fid) for fid in current_fids]
            logger.info(f"🔧 FIDs actuels: {current_fids}")
            
            # Retirer les FIDs spécifiés - s'assurer qu'ils sont des strings
            fids_to_remove_str = [str(fid) for fid in fids_to_remove]
            updated_fids = [fid for fid in current_fids if fid not in fids_to_remove_str]
            logger.info(f"🔧 FIDs mis à jour: {updated_fids}")
            
            if updated_fids == current_fids:
                logger.info("✅ Aucun FID à retirer")
                return True
            
            # VÉRIFIER D'ABORD SI LE WEBHOOK EXISTE ENCORE CÔTÉ NEYNAR
            try:
                webhook_details = get_neynar_client().get_webhook("01K45KREDQ77B80YD87AAXJ3E8")
                if webhook_details and webhook_details.get("active"):
                    logger.info("✅ Webhook fixe 01K45KREDQ77B80YD87AAXJ3E8 existe et est actif côté Neynar")
                    
                    # Mettre à jour le webhook fixe 01K45KREDQ77B80YD87AAXJ3E8
                    try:
                        # Convertir les FIDs en entiers pour l'API Neynar
                        updated_fids_int = [int(fid) for fid in updated_fids]
                        updated_webhook = get_neynar_client().update_webhook(
                            "01K45KREDQ77B80YD87AAXJ3E8",  # WEBHOOK FIXE
                            updated_fids_int
                        )
                        
                        # Mettre à jour l'état local
                        webhook_state.author_fids = json.dumps(updated_fids)
                        webhook_state.updated_at = time.time()
                        db.commit()
                        
                        logger.info("✅ FIDs retirés du webhook fixe 01K45KREDQ77B80YD87AAXJ3E8")
                        return True
                        
                    except Exception as update_error:
                        logger.error(f"❌ Erreur lors de la mise à jour du webhook: {update_error}")
                        logger.warning("⚠️ On garde l'état local existant pour éviter la perte de connexion")
                        return False
                        
                else:
                    logger.warning("⚠️ Webhook fixe 01K45KREDQ77B80YD87AAXJ3E8 n'existe plus ou est inactif côté Neynar")
                    logger.warning("⚠️ Il faut le recréer manuellement sur Neynar ou utiliser un autre webhook")
                    return False
                    
            except Exception as e:
                if "404" in str(e) or "not found" in str(e).lower():
                    logger.error("❌ Webhook fixe 01K45KREDQ77B80YD87AAXJ3E8 N'EXISTE PLUS côté Neynar !")
                    logger.error("❌ Il faut le recréer manuellement sur Neynar ou utiliser un autre webhook")
                    return False
                else:
                    logger.warning(f"⚠️ Impossible de vérifier l'état du webhook côté Neynar: {e}")
                    logger.warning("⚠️ Mais l'état local est synchronisé")
                    return False
                
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"❌ Erreur lors du retrait des FIDs: {e}")
        return False
