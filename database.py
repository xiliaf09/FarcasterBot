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

# Créer l'engine de base de données
engine = create_engine(config.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

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

def get_db() -> Session:
    """Obtenir une session de base de données"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Initialiser la base de données"""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Base de données initialisée avec succès")
    except Exception as e:
        logger.error(f"Erreur lors de l'initialisation de la base: {e}")
        raise

def check_db_connection() -> bool:
    """Vérifier la connexion à la base de données"""
    try:
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        logger.info("Connexion à la base de données réussie")
        return True
    except Exception as e:
        logger.error(f"Erreur de connexion à la base: {e}")
        return False
