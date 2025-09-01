import os
from typing import Optional

class Config:
    """Configuration du bot Farcaster Tracker"""
    
    # Discord Configuration
    DISCORD_TOKEN: str = os.getenv('DISCORD_TOKEN', '')
    DISCORD_APPLICATION_ID: str = os.getenv('DISCORD_APPLICATION_ID', '')
    
    # Neynar Configuration
    NEYNAR_API_KEY: str = os.getenv('NEYNAR_API_KEY', '')
    NEYNAR_WEBHOOK_SECRET: str = os.getenv('NEYNAR_WEBHOOK_SECRET', '')
    
    # Database Configuration
    DATABASE_URL: str = os.getenv('DATABASE_URL', '')
    
    # Public URL for webhooks
    PUBLIC_BASE_URL: str = os.getenv('PUBLIC_BASE_URL', '')
    
    # Optional Configuration
    LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO')
    PORT: int = int(os.getenv('PORT', '8000'))
    
    @classmethod
    def validate(cls) -> bool:
        """Valider que toutes les variables obligatoires sont présentes"""
        required_vars = [
            'DISCORD_TOKEN',
            'DISCORD_APPLICATION_ID', 
            'NEYNAR_API_KEY',
            'NEYNAR_WEBHOOK_SECRET',
            'DATABASE_URL',
            'PUBLIC_BASE_URL'
        ]
        
        missing_vars = []
        for var in required_vars:
            if not getattr(cls, var):
                missing_vars.append(var)
        
        if missing_vars:
            print(f"❌ Variables d'environnement manquantes: {', '.join(missing_vars)}")
            print("💡 Ces variables doivent être configurées dans Railway (Variables d'environnement)")
            print("📖 Consultez le README.md pour la configuration complète")
            return False
        
        return True

# Instance globale de configuration
config = Config()
