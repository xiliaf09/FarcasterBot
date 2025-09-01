#!/usr/bin/env python3
"""
Script de test local pour Farcaster Tracker Bot
Teste les composants individuels sans connexion complète
"""

import sys
import os
from pathlib import Path

# Ajouter le répertoire parent au path pour les imports
sys.path.append(str(Path(__file__).parent.parent))

def test_imports():
    """Tester que tous les modules peuvent être importés"""
    print("🧪 Test des imports...")
    
    try:
        import config
        print("✅ config.py - OK")
    except Exception as e:
        print(f"❌ config.py - Erreur: {e}")
        return False
    
    try:
        import database
        print("✅ database.py - OK")
    except Exception as e:
        print(f"❌ database.py - Erreur: {e}")
        return False
    
    try:
        import neynar_client
        print("✅ neynar_client.py - OK")
    except Exception as e:
        print(f"❌ neynar_client.py - Erreur: {e}")
        return False
    
    try:
        import webhook_sync
        print("✅ webhook_sync.py - OK")
    except Exception as e:
        print(f"❌ webhook_sync.py - Erreur: {e}")
        return False
    
    try:
        import discord_bot
        print("✅ discord_bot.py - OK")
    except Exception as e:
        print(f"❌ discord_bot.py - Erreur: {e}")
        return False
    
    try:
        import webhook_handler
        print("✅ webhook_handler.py - OK")
    except Exception as e:
        print(f"❌ webhook_handler.py - Erreur: {e}")
        return False
    
    return True

def test_config_structure():
    """Tester la structure de la configuration"""
    print("\n🔧 Test de la structure de configuration...")
    
    try:
        from config import config
        
        # Vérifier que les attributs existent
        required_attrs = [
            'DISCORD_TOKEN', 'DISCORD_APPLICATION_ID',
            'NEYNAR_API_KEY', 'NEYNAR_WEBHOOK_SECRET',
            'DATABASE_URL', 'PUBLIC_BASE_URL', 'LOG_LEVEL', 'PORT'
        ]
        
        for attr in required_attrs:
            if hasattr(config, attr):
                print(f"✅ {attr} - OK")
            else:
                print(f"❌ {attr} - Manquant")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors du test de configuration: {e}")
        return False

def test_database_models():
    """Tester les modèles de base de données"""
    print("\n🗄️ Test des modèles de base de données...")
    
    try:
        from database import Guild, TrackedAccount, Delivery, WebhookState
        
        # Vérifier que les modèles peuvent être instanciés
        guild = Guild(id="test")
        tracked = TrackedAccount(
            id="test", guild_id="test", channel_id="test",
            fid=123, username="test", added_by_discord_user_id="test"
        )
        delivery = Delivery(
            id="test", guild_id="test", channel_id="test", cast_hash="test"
        )
        webhook = WebhookState(
            id="test", webhook_id="test", author_fids="[]"
        )
        
        print("✅ Tous les modèles - OK")
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors du test des modèles: {e}")
        return False

def test_neynar_client():
    """Tester le client Neynar"""
    print("\n🌐 Test du client Neynar...")
    
    try:
        from neynar_client import NeynarClient
        
        # Créer une instance (sans API key)
        client = NeynarClient()
        
        # Vérifier que les méthodes existent
        methods = ['get_user_by_fid', 'get_user_by_username', 'resolve_user']
        for method in methods:
            if hasattr(client, method):
                print(f"✅ {method} - OK")
            else:
                print(f"❌ {method} - Manquant")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors du test du client Neynar: {e}")
        return False

def main():
    """Fonction principale de test"""
    print("🧪 Tests locaux du Farcaster Tracker Bot")
    print("=" * 50)
    
    tests = [
        test_imports,
        test_config_structure,
        test_database_models,
        test_neynar_client
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print("=" * 50)
    print(f"📊 Résultats: {passed}/{total} tests réussis")
    
    if passed == total:
        print("🎉 Tous les tests sont passés !")
        print("   Votre code est prêt pour le déploiement.")
        return True
    else:
        print("❌ Certains tests ont échoué.")
        print("   Vérifiez les erreurs ci-dessus.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
