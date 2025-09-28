from sqlalchemy import create_engine, Column, String, Integer, DateTime, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.sql import func
from typing import List, Optional
import logging
from config import config

# Configuration du logging
logging.basicConfig(level=getattr(logging, config.LOG_LEVEL))
logger = logging.getLogger(__name__)

# Base pour les modèles
Base = declarative_base()

class Guild(Base):
    """Table des serveurs Discord"""
    __tablename__ = "guilds"
    
    id = Column(String, primary_key=True)
    default_channel_id = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class TrackedAccount(Base):
    """Table des comptes Farcaster suivis"""
    __tablename__ = "tracked_accounts"
    
    id = Column(String, primary_key=True)
    guild_id = Column(String, nullable=False)
    channel_id = Column(String, nullable=False)
    fid = Column(Integer, nullable=False)
    username = Column(String, nullable=False)
    added_by_discord_user_id = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class Delivery(Base):
    """Table des livraisons pour éviter les doublons"""
    __tablename__ = "deliveries"
    
    id = Column(String, primary_key=True)
    guild_id = Column(String, nullable=False)
    channel_id = Column(String, nullable=False)
    cast_hash = Column(String, nullable=False)
    delivered_at = Column(DateTime(timezone=True), server_default=func.now())

class WebhookState(Base):
    """État du webhook Neynar (singleton)"""
    __tablename__ = "webhook_state"
    
    id = Column(String, primary_key=True, default="singleton")
    webhook_id = Column(String, nullable=False)
    active = Column(Boolean, default=True)
    author_fids = Column(Text, nullable=False)  # JSON string des FIDs
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class TrackedFollowing(Base):
    """Table des comptes Farcaster suivis pour leurs nouveaux followings"""
    __tablename__ = "tracked_following"
    
    id = Column(String, primary_key=True)
    guild_id = Column(String, nullable=False)
    channel_id = Column(String, nullable=False)
    target_fid = Column(Integer, nullable=False)  # FID du compte à surveiller
    target_username = Column(String, nullable=False)
    added_by_discord_user_id = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class FollowingState(Base):
    """État des followings pour éviter les doublons et tracker les changements"""
    __tablename__ = "following_state"
    
    id = Column(String, primary_key=True)
    target_fid = Column(Integer, nullable=False, unique=True)  # FID du compte surveillé
    last_following_list = Column(Text, nullable=False)  # JSON des FIDs suivis
    last_check_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class FollowingDelivery(Base):
    """Table des livraisons de notifications de followings pour éviter les doublons"""
    __tablename__ = "following_deliveries"
    
    id = Column(String, primary_key=True)
    guild_id = Column(String, nullable=False)
    channel_id = Column(String, nullable=False)
    target_fid = Column(Integer, nullable=False)  # FID du compte surveillé
    new_following_fid = Column(Integer, nullable=False)  # FID du nouveau compte suivi
    delivered_at = Column(DateTime(timezone=True), server_default=func.now())

# Variables globales pour l'engine et SessionLocal
engine = None
SessionLocal = None

def init_database_connection():
    """Initialiser la connexion à la base de données"""
    global engine, SessionLocal
    
    if engine is None:
        try:
            logger.info("Initialisation de la connexion à la base de données...")
            engine = create_engine(config.DATABASE_URL)
            SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
            logger.info("Connexion à la base de données initialisée avec succès")
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation de la base de données: {e}")
            raise

def get_db() -> Session:
    """Obtenir une session de base de données"""
    if SessionLocal is None:
        init_database_connection()
    
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_session_local():
    """Obtenir SessionLocal avec initialisation automatique"""
    global SessionLocal
    
    if SessionLocal is None:
        init_database_connection()
    
    return SessionLocal

def init_db():
    """Initialiser la base de données"""
    if engine is None:
        init_database_connection()
    
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Base de données initialisée avec succès")
    except Exception as e:
        logger.error(f"Erreur lors de l'initialisation de la base: {e}")
        raise

def check_db_connection() -> bool:
    """Vérifier la connexion à la base de données"""
    if engine is None:
        init_database_connection()
    
    try:
        with engine.connect() as conn:
            # Utiliser text() pour les requêtes SQL brutes
            from sqlalchemy import text
            conn.execute(text("SELECT 1"))
        logger.info("Connexion à la base de données réussie")
        return True
    except Exception as e:
        logger.error(f"Erreur de connexion à la base: {e}")
        return False
