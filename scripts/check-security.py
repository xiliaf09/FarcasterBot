#!/usr/bin/env python3
"""
Script de vérification de sécurité pour Farcaster Tracker Bot
Vérifie qu'aucun secret n'est exposé dans le code source
"""

import os
import re
import sys
from pathlib import Path

# Patterns à détecter (secrets potentiels)
SECRET_PATTERNS = [
    r'discord\.gg/[a-zA-Z0-9]+',  # Liens d'invitation Discord
    r'[a-zA-Z0-9]{24}\.[a-zA-Z0-9]{6}\.[a-zA-Z0-9]{27}',  # Tokens Discord
    r'sk-[a-zA-Z0-9]{48}',  # Clés API (format générique)
    r'[a-zA-Z0-9]{32,}',  # Hashs longs
    r'postgresql://[^/]+:[^@]+@',  # URLs de base avec credentials
]

# Patterns d'exemple à ignorer (dans README, env.example, etc.)
EXAMPLE_PATTERNS = [
    r'https://your-app-name\.up\.railway\.app',  # URL d'exemple Railway
    r'your_discord_bot_token_here',  # Token d'exemple
    r'your_neynar_api_key_here',  # Clé d'exemple
    r'postgresql://username:password@localhost:5432/farcaster_tracker',  # URL d'exemple
]

# Fichiers à ignorer
IGNORE_FILES = {
    '.git', 'node_modules', '__pycache__', '.pytest_cache',
    'dist', 'build', '.venv', 'venv', 'env'
}

# Extensions de fichiers à vérifier
CHECK_EXTENSIONS = {'.py', '.js', '.ts', '.json', '.yaml', '.yml', '.md', '.txt'}

def check_file(file_path):
    """Vérifier un fichier pour des secrets potentiels"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        issues = []
        for pattern in SECRET_PATTERNS:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                # Vérifier si c'est un exemple
                is_example = False
                for example_pattern in EXAMPLE_PATTERNS:
                    if re.search(example_pattern, content, re.IGNORECASE):
                        is_example = True
                        break
                
                if not is_example:
                    line_num = content[:match.start()].count('\n') + 1
                    issues.append(f"  Ligne {line_num}: {match.group()[:50]}...")
        
        return issues
    except Exception as e:
        return [f"  Erreur de lecture: {e}"]

def scan_directory(directory):
    """Scanner un répertoire pour des secrets potentiels"""
    issues_found = False
    
    for root, dirs, files in os.walk(directory):
        # Ignorer les répertoires à exclure
        dirs[:] = [d for d in dirs if d not in IGNORE_FILES]
        
        for file in files:
            file_path = Path(root) / file
            
            # Vérifier l'extension
            if file_path.suffix not in CHECK_EXTENSIONS:
                continue
                
            # Ignorer les fichiers de configuration d'environnement
            if file_path.name in {'.env', '.env.local', '.env.production'}:
                print(f"⚠️  Fichier d'environnement détecté: {file_path}")
                print("   Assurez-vous qu'il n'est pas commité dans Git !")
                continue
            
            # Vérifier le contenu du fichier
            file_issues = check_file(file_path)
            if file_issues:
                print(f"🚨 Secrets potentiels détectés dans: {file_path}")
                for issue in file_issues:
                    print(issue)
                issues_found = True
    
    return issues_found

def main():
    """Fonction principale"""
    print("🔒 Vérification de sécurité du code source...")
    print("=" * 50)
    
    # Vérifier le répertoire courant
    current_dir = Path.cwd()
    print(f"📁 Scan du répertoire: {current_dir}")
    
    # Vérifier que .env est dans .gitignore
    gitignore_path = current_dir / '.gitignore'
    if gitignore_path.exists():
        with open(gitignore_path, 'r') as f:
            gitignore_content = f.read()
        
        if '.env' in gitignore_content:
            print("✅ .env est bien dans .gitignore")
        else:
            print("❌ .env n'est PAS dans .gitignore !")
            print("   Ajoutez '.env' à votre .gitignore")
    else:
        print("❌ Fichier .gitignore manquant !")
    
    print()
    
    # Scanner le code source
    issues = scan_directory(current_dir)
    
    print("=" * 50)
    if issues:
        print("❌ Des secrets potentiels ont été détectés !")
        print("   Vérifiez ces fichiers avant de commiter.")
        sys.exit(1)
    else:
        print("✅ Aucun secret détecté dans le code source")
        print("   Votre code est prêt pour GitHub !")

if __name__ == "__main__":
    main()
