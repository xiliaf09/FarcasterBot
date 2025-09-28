import asyncio
import threading
import logging
import time
from config import config
from database import init_db, check_db_connection
from discord_bot import run_bot
from webhook_handler import app
from following_polling import start_following_polling, stop_following_polling
import uvicorn

# Configuration du logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def run_webhook_server():
    """Lancer le serveur webhook FastAPI dans un thread séparé"""
    try:
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=config.PORT,
            log_level=config.LOG_LEVEL.lower()
        )
    except Exception as e:
        logger.error(f"Erreur lors du lancement du serveur webhook: {e}")

def main():
    """Fonction principale"""
    logger.info("🚀 Démarrage du Farcaster Tracker Bot...")
    
    # Valider la configuration
    if not config.validate():
        logger.error("❌ Configuration invalide, arrêt du bot")
        return
    
    # Vérifier que les variables essentielles sont présentes
    logger.info("🔧 Vérification de la configuration...")
    logger.info(f"Discord Token: {'✅ Configuré' if config.DISCORD_TOKEN else '❌ Manquant'}")
    logger.info(f"Neynar API Key: {'✅ Configuré' if config.NEYNAR_API_KEY else '❌ Manquant'}")
    logger.info(f"Database URL: {'✅ Configuré' if config.DATABASE_URL else '❌ Manquant'}")
    logger.info(f"Public Base URL: {'✅ Configuré' if config.PUBLIC_BASE_URL else '❌ Manquant'}")
    
    # Initialiser la base de données seulement si DATABASE_URL est configuré
    if config.DATABASE_URL:
        try:
            logger.info("🗄️ Initialisation de la base de données...")
            init_db()
            
            # Vérifier la connexion
            if not check_db_connection():
                logger.error("❌ Impossible de se connecter à la base de données")
                logger.warning("⚠️ Le bot continuera sans base de données (mode dégradé)")
            else:
                logger.info("✅ Base de données initialisée avec succès")
                
        except Exception as e:
            logger.error(f"❌ Erreur lors de l'initialisation de la base: {e}")
            logger.warning("⚠️ Le bot continuera sans base de données (mode dégradé)")
    else:
        logger.warning("⚠️ DATABASE_URL non configuré, le bot fonctionnera en mode dégradé")
    
    # Lancer le serveur webhook dans un thread séparé
    logger.info(f"🌐 Lancement du serveur webhook sur le port {config.PORT}...")
    webhook_thread = threading.Thread(target=run_webhook_server, daemon=True)
    webhook_thread.start()
    
    # Attendre un peu que le serveur démarre
    logger.info("⏳ Attente du démarrage du serveur webhook...")
    time.sleep(3)
    
    # Lancer le bot Discord
    logger.info("🤖 Lancement du bot Discord...")
    try:
        run_bot()
    except KeyboardInterrupt:
        logger.info("🛑 Arrêt demandé par l'utilisateur")
    except Exception as e:
        logger.error(f"❌ Erreur lors de l'exécution du bot: {e}")
    finally:
        logger.info("👋 Arrêt du Farcaster Tracker Bot")

if __name__ == "__main__":
    main()
