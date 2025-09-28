import asyncio
import json
import logging
import time
import uuid
from datetime import datetime
from typing import List, Dict, Optional
from database import get_session_local, TrackedFollowing, FollowingState, FollowingDelivery
from neynar_client import get_neynar_client
from config import config

logger = logging.getLogger(__name__)

class FollowingPoller:
    """Service de polling pour détecter les nouveaux followings"""
    
    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.running = False
        self.poll_interval = 60  # 1 minute
        
    async def start(self):
        """Démarrer le service de polling"""
        if self.running:
            logger.warning("FollowingPoller déjà en cours d'exécution")
            return
            
        self.running = True
        logger.info("🔄 Démarrage du service de polling des followings...")
        
        # Lancer la boucle de polling dans une tâche asyncio
        asyncio.create_task(self._polling_loop())
        
    async def stop(self):
        """Arrêter le service de polling"""
        self.running = False
        logger.info("🛑 Arrêt du service de polling des followings")
        
    async def _polling_loop(self):
        """Boucle principale de polling"""
        while self.running:
            try:
                await self._check_all_followings()
                await asyncio.sleep(self.poll_interval)
            except Exception as e:
                logger.error(f"❌ Erreur dans la boucle de polling: {e}")
                await asyncio.sleep(30)  # Attendre 30s en cas d'erreur
                
    async def _check_all_followings(self):
        """Vérifier tous les comptes trackés pour de nouveaux followings"""
        try:
            # Récupérer tous les comptes trackés pour les followings
            db = get_session_local()()
            try:
                tracked_followings = db.query(TrackedFollowing).all()
                
                if not tracked_followings:
                    logger.debug("Aucun compte tracké pour les followings")
                    return
                
                logger.info(f"🔍 Vérification de {len(tracked_followings)} compte(s) pour de nouveaux followings...")
                
                # Grouper par target_fid pour éviter les vérifications multiples
                unique_fids = {}
                for tf in tracked_followings:
                    if tf.target_fid not in unique_fids:
                        unique_fids[tf.target_fid] = []
                    unique_fids[tf.target_fid].append(tf)
                
                # Vérifier chaque FID unique
                for target_fid, tracking_entries in unique_fids.items():
                    await self._check_user_followings(target_fid, tracking_entries, db)
                    
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"❌ Erreur lors de la vérification des followings: {e}")
            
    async def _check_user_followings(self, target_fid: int, tracking_entries: List, db):
        """Vérifier les followings d'un utilisateur spécifique"""
        try:
            client = get_neynar_client()
            if client is None:
                logger.error("❌ Client Neynar non initialisé")
                return
            
            # Récupérer la liste actuelle des followings
            current_followings = client.get_user_following(target_fid)
            current_fids = [f['fid'] for f in current_followings]
            current_usernames = {f['fid']: f['username'] for f in current_followings}
            
            logger.debug(f"🔍 FID {target_fid}: {len(current_fids)} followings actuels")
            
            # Récupérer l'état précédent
            following_state = db.query(FollowingState).filter_by(target_fid=target_fid).first()
            
            if not following_state:
                # Premier check - créer l'état
                following_state = FollowingState(
                    id=str(uuid.uuid4()),
                    target_fid=target_fid,
                    last_following_list=json.dumps(current_fids)
                )
                db.add(following_state)
                db.commit()
                logger.info(f"✅ État initial créé pour FID {target_fid}")
                return
            
            # Comparer avec l'état précédent
            previous_fids = json.loads(following_state.last_following_list)
            new_fids = list(set(current_fids) - set(previous_fids))
            
            if new_fids:
                logger.info(f"🆕 Nouveaux followings détectés pour FID {target_fid}: {new_fids}")
                
                # Envoyer les notifications
                await self._send_following_notifications(target_fid, new_fids, current_usernames, tracking_entries, db)
                
                # Mettre à jour l'état
                following_state.last_following_list = json.dumps(current_fids)
                following_state.last_check_at = datetime.utcnow()
                db.commit()
                
            else:
                logger.debug(f"✅ FID {target_fid}: Aucun nouveau following")
                
        except Exception as e:
            logger.error(f"❌ Erreur lors de la vérification des followings pour FID {target_fid}: {e}")
            
    async def _send_following_notifications(self, target_fid: int, new_fids: List[int], current_usernames: Dict, tracking_entries: List, db):
        """Envoyer les notifications de nouveaux followings"""
        try:
            # Récupérer les infos du compte tracké
            target_username = tracking_entries[0].target_username
            
            # Récupérer les infos des nouveaux comptes suivis
            client = get_neynar_client()
            new_users_info = []
            
            for fid in new_fids:
                try:
                    user_info = client.get_user_by_fid(fid)
                    new_users_info.append({
                        'fid': fid,
                        'username': user_info['username'],
                        'display_name': user_info.get('display_name', user_info['username']),
                        'pfp_url': user_info.get('pfp_url', '')
                    })
                except Exception as e:
                    logger.warning(f"⚠️ Impossible de récupérer les infos pour FID {fid}: {e}")
                    # Utiliser les infos de base si disponibles
                    new_users_info.append({
                        'fid': fid,
                        'username': current_usernames.get(fid, f'FID_{fid}'),
                        'display_name': current_usernames.get(fid, f'FID_{fid}'),
                        'pfp_url': ''
                    })
            
            # Envoyer une notification pour chaque salon qui track ce compte
            for tracking_entry in tracking_entries:
                await self._send_channel_notification(
                    target_fid, target_username, new_users_info, 
                    tracking_entry, db
                )
                
        except Exception as e:
            logger.error(f"❌ Erreur lors de l'envoi des notifications: {e}")
            
    async def _send_channel_notification(self, target_fid: int, target_username: str, new_users_info: List[Dict], tracking_entry, db):
        """Envoyer une notification dans un salon Discord spécifique"""
        try:
            # Utiliser le salon configuré, ou essayer de trouver le salon par défaut
            channel = self.bot.get_channel(int(tracking_entry.channel_id))
            
            # Si le salon configuré n'existe plus, utiliser le salon de la variable d'environnement
            if not channel:
                if config.DEFAULT_CHANNEL_ID:
                    channel = self.bot.get_channel(int(config.DEFAULT_CHANNEL_ID))
                    logger.info(f"🔄 Utilisation du salon configuré {config.DEFAULT_CHANNEL_ID} pour les followings")
            
            if not channel:
                logger.warning(f"⚠️ Salon Discord {tracking_entry.channel_id} introuvable et aucun salon configuré dans DEFAULT_CHANNEL_ID")
                return
            
            # Vérifier si on a déjà envoyé cette notification (anti-doublon)
            for new_user in new_users_info:
                existing_delivery = db.query(FollowingDelivery).filter_by(
                    guild_id=tracking_entry.guild_id,
                    channel_id=tracking_entry.channel_id,
                    target_fid=target_fid,
                    new_following_fid=new_user['fid']
                ).first()
                
                if existing_delivery:
                    logger.debug(f"Notification déjà envoyée pour {target_username} → {new_user['username']}")
                    continue
                
                # Créer l'embed de notification
                embed = discord.Embed(
                    title=f"🆕 Nouveau Following",
                    description=f"**@{target_username}** suit maintenant **@{new_user['username']}** !",
                    color=0x00FF00,
                    timestamp=discord.utils.utcnow()
                )
                
                # Ajouter les informations du nouveau compte suivi
                embed.add_field(
                    name="👤 Nouveau compte suivi",
                    value=f"**@{new_user['username']}** ({new_user['display_name']})\nFID: `{new_user['fid']}`",
                    inline=False
                )
                
                # Ajouter le lien vers Warpcast
                warpcast_url = f"https://warpcast.com/{new_user['username']}"
                embed.add_field(
                    name="🔗 Voir sur Warpcast",
                    value=f"[@{new_user['username']}]({warpcast_url})",
                    inline=False
                )
                
                # Ajouter l'image de profil si disponible
                if new_user.get('pfp_url'):
                    embed.set_thumbnail(url=new_user['pfp_url'])
                
                embed.set_footer(text=f"Suivi par @{target_username} • Farcaster Tracker Bot")
                
                # Envoyer la notification
                await channel.send(embed=embed)
                
                # Marquer comme envoyé
                delivery = FollowingDelivery(
                    id=str(uuid.uuid4()),
                    guild_id=tracking_entry.guild_id,
                    channel_id=tracking_entry.channel_id,
                    target_fid=target_fid,
                    new_following_fid=new_user['fid']
                )
                db.add(delivery)
                db.commit()
                
                logger.info(f"✅ Notification envoyée: {target_username} → {new_user['username']} dans {channel.name}")
                
        except Exception as e:
            logger.error(f"❌ Erreur lors de l'envoi de notification dans {tracking_entry.channel_id}: {e}")

# Instance globale du poller
_following_poller = None

def get_following_poller(bot_instance=None):
    """Obtenir l'instance du poller de followings"""
    global _following_poller
    
    if _following_poller is None and bot_instance:
        _following_poller = FollowingPoller(bot_instance)
        logger.info("✅ FollowingPoller initialisé")
    
    return _following_poller

async def start_following_polling(bot_instance):
    """Démarrer le polling des followings"""
    poller = get_following_poller(bot_instance)
    if poller:
        await poller.start()

async def stop_following_polling():
    """Arrêter le polling des followings"""
    global _following_poller
    if _following_poller:
        await _following_poller.stop()
        _following_poller = None
