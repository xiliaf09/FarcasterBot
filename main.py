import asyncio
import threading
import logging
from config import config
from database import init_db, check_db_connection
from discord_bot import run_bot
from webhook_handler import app
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
    
    # Initialiser la base de données
    try:
        logger.info("🗄️ Initialisation de la base de données...")
        init_db()
        
        # Vérifier la connexion
        if not check_db_connection():
            logger.error("❌ Impossible de se connecter à la base de données")
            return
            
        logger.info("✅ Base de données initialisée avec succès")
        
    except Exception as e:
        logger.error(f"❌ Erreur lors de l'initialisation de la base: {e}")
        return
    
    # Lancer le serveur webhook dans un thread séparé
    logger.info(f"🌐 Lancement du serveur webhook sur le port {config.PORT}...")
    webhook_thread = threading.Thread(target=run_webhook_server, daemon=True)
    webhook_thread.start()
    
    # Attendre un peu que le serveur démarre
    import time
    time.sleep(2)
    
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
