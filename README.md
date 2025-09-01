# 🤖 Farcaster Tracker Bot

Un bot Discord intelligent qui permet de tracker les comptes Farcaster et de recevoir des notifications instantanées dès qu'ils publient un nouveau cast (post original ou réponse).

## ✨ Fonctionnalités

- **Tracking automatique** : Suivez n'importe quel compte Farcaster par FID ou username
- **Notifications instantanées** : Recevez des embeds Discord dès qu'un cast est publié
- **Multi-serveurs** : Chaque serveur peut configurer ses propres comptes à tracker
- **Déduplication intelligente** : Jamais de doublons grâce au système de livraison
- **Webhooks sécurisés** : Intégration sécurisée avec l'API Neynar
- **Interface simple** : Commandes Discord intuitives avec préfixe `!`

## 🚀 Commandes Disponibles

| Commande | Description | Exemple |
|----------|-------------|---------|
| `!track <fid_ou_username> [salon]` | Suivre un compte Farcaster | `!track 544244` ou `!track alice #notifications` |
| `!untrack <fid_ou_username>` | Arrêter de suivre un compte | `!untrack dwr.eth` |
| `!list` | Lister tous les comptes suivis | `!list` |
| `!setchannel <#salon>` | Définir le salon par défaut | `!setchannel #farcaster` |
| `!test` | Tester les notifications | `!test` |
| `!help` | Afficher l'aide | `!help` |

## 🌐 **Routes d'Administration (Neynar)**

| Route | Description | Utilisation |
|-------|-------------|-------------|
| `/admin/webhook/status` | Statut du webhook Neynar | Monitoring |
| `/admin/webhook/test` | Test de connexion webhook | Diagnostic |
| `/admin/neynar/rate-limits` | Rate limits actuels | Performance |
| `/admin/neynar/set-plan` | Changer le plan (starter/growth/scale) | Configuration |
| `/admin/resync` | Resynchroniser le webhook | Maintenance |

## 🛠️ Prérequis

### Discord Bot
- [Application Discord](https://discord.com/developers/applications) créée
- Bot avec les permissions suivantes :
  - `Send Messages`
  - `Use Slash Commands`
  - `Embed Links`
  - `Read Message History`
- Intents activés : `Message Content`, `Guilds`

### Neynar API
- [Clé API Neynar](https://neynar.com/) pour accéder à l'API Farcaster
- [Webhook secret](https://neynar.com/docs/webhooks) pour sécuriser les notifications

### Base de données
- Base PostgreSQL (Railway fournit un add-on gratuit)

## 📦 Installation Locale (Développement)

### 1. Cloner le dépôt
```bash
git clone https://github.com/votre-username/farcaster-tracker.git
cd farcaster-tracker
```

### 2. Installer les dépendances
```bash
pip install -r requirements.txt
```

### 3. Configuration des variables d'environnement
**⚠️ IMPORTANT : Ne jamais créer de fichier `.env` local avec vos vraies clés !**

Pour le développement local uniquement, vous pouvez créer un fichier `.env` temporaire :
```bash
cp env.example .env
# Éditer .env avec vos vraies clés (NE PAS COMMITER !)
```

**OU** définir les variables directement dans votre terminal :
```bash
export DISCORD_TOKEN="votre_token"
export NEYNAR_API_KEY="votre_clé"
# etc...
```

### 4. Vérification de sécurité (RECOMMANDÉ)
Avant de commiter, vérifiez qu'aucun secret n'est exposé :
```bash
python scripts/check-security.py
```

### 5. Lancer le bot
```bash
python main.py
```

## 🚀 Déploiement sur Railway (PRODUCTION)

### 1. Préparer le projet
- Pousser votre code sur GitHub
- Vérifier que tous les fichiers sont présents (Dockerfile, requirements.txt, etc.)
- **NE JAMAIS COMMITER** de fichier `.env` avec vos vraies clés !

### 2. Déployer sur Railway
1. Aller sur [Railway](https://railway.app/)
2. Se connecter avec GitHub
3. Cliquer sur "New Project" → "Deploy from GitHub repo"
4. Sélectionner votre dépôt `farcaster-tracker`
5. Railway détectera automatiquement le Dockerfile

### 3. Configuration Railway (CRUCIAL)
1. **Variables d'environnement** : Cliquer sur votre projet → "Variables" et ajouter :

```bash
# Discord Bot Configuration
DISCORD_TOKEN=your_real_discord_bot_token
DISCORD_APPLICATION_ID=your_real_discord_application_id

# Neynar API Configuration
NEYNAR_API_KEY=your_real_neynar_api_key
NEYNAR_WEBHOOK_SECRET=your_real_neynar_webhook_secret

# Public URL for webhooks (Railway domain)
PUBLIC_BASE_URL=https://your-app-name.up.railway.app

# Configuration optionnelle
LOG_LEVEL=INFO
PORT=8000
```

2. **Base PostgreSQL** : 
   - Cliquer sur "New" → "Database" → "PostgreSQL"
   - Railway générera automatiquement `DATABASE_URL`
   - **Copier cette valeur** dans vos variables d'environnement

3. **Domaine** : Noter l'URL générée par Railway
4. **Mettre à jour** `PUBLIC_BASE_URL` avec l'URL Railway

### 4. Déploiement
- Railway déploiera automatiquement à chaque push sur GitHub
- Le bot se connectera à Discord et créera le webhook Neynar

## 🔒 Sécurité

- **Variables d'environnement** : Toutes les clés sensibles sont stockées uniquement sur Railway
- **Pas de secrets en dur** : Aucune clé API n'est commitée dans GitHub
- **Vérification HMAC-SHA512** des webhooks Neynar
- **Validation des signatures** avant traitement des données
- **Base de données sécurisée** avec Railway

## 🔧 Utilisation

### 1. Inviter le bot
- Utiliser le lien d'invitation généré par Discord Developer Portal
- Le bot rejoindra votre serveur

### 2. Premier tracking
```bash
!track 544244
# ou
!track alice
# ou avec un salon spécifique
!track dwr.eth #notifications
```

### 3. Vérifier le suivi
```bash
!list
```

### 4. Tester les notifications
```bash
!test
```

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Discord Bot   │    │  Webhook API    │    │   Neynar API    │
│                 │    │   (FastAPI)     │    │                 │
│ • Commands      │◄──►│ • /webhooks/    │◄──►│ • Webhooks      │
│ • Notifications │    │   neynar        │    │ • User lookup   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   PostgreSQL    │    │   Discord API   │    │  Farcaster     │
│                 │    │                 │    │  Network       │
│ • Guilds        │    │ • Send messages │    │ • Casts        │
│ • Tracking      │    │ • Embeds        │    │ • Users        │
│ • Deliveries    │    │ • Permissions   │    │ • Webhooks     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 📊 Base de données

### Tables principales
- **`guilds`** : Serveurs Discord et salons par défaut
- **`tracked_accounts`** : Comptes Farcaster suivis par serveur
- **`deliveries`** : Historique des livraisons (anti-doublons)
- **`webhook_state`** : État du webhook Neynar

## 🐛 Dépannage

### Erreurs courantes

#### "Signature invalide"
- Vérifier que `NEYNAR_WEBHOOK_SECRET` est correct dans Railway
- Redémarrer le bot après modification des variables

#### "Impossible de se connecter à la base"
- Vérifier `DATABASE_URL` dans Railway
- Attendre que la base soit prête (peut prendre quelques minutes)

#### "Bot ne répond pas aux commandes"
- Vérifier les permissions du bot
- S'assurer que les intents sont activés
- Vérifier `DISCORD_TOKEN` dans Railway

#### "Webhook Neynar non créé"
- Vérifier `NEYNAR_API_KEY` dans Railway
- Vérifier `PUBLIC_BASE_URL` dans Railway (doit être accessible publiquement)

### Logs
Les logs sont affichés dans la console Railway. Utilisez `LOG_LEVEL=DEBUG` pour plus de détails.

## 🚨 Sécurité et Bonnes Pratiques

### Ne JAMAIS faire :
- ❌ Commiter un fichier `.env` avec vos vraies clés
- ❌ Partager vos tokens Discord ou clés Neynar
- ❌ Stocker des secrets dans le code source

### Toujours faire :
- ✅ Utiliser les variables d'environnement Railway
- ✅ Garder `env.example` comme modèle (sans vraies clés)
- ✅ Vérifier que `.env` est dans `.gitignore`
- ✅ Régénérer vos tokens si compromis
- ✅ Exécuter `python scripts/check-security.py` avant chaque commit

### Script de vérification de sécurité
Le projet inclut un script automatique pour vérifier la sécurité :
```bash
python scripts/check-security.py
```

Ce script :
- Vérifie qu'aucun secret n'est exposé dans le code
- S'assure que `.env` est dans `.gitignore`
- Scanne tous les fichiers pour des patterns suspects
- Doit passer avant de commiter sur GitHub

## 🤝 Contribution

1. Fork le projet
2. Créer une branche feature (`git checkout -b feature/AmazingFeature`)
3. **IMPORTANT** : Exécuter `python scripts/check-security.py` pour vérifier la sécurité
4. Commit les changements (`git commit -m 'Add some AmazingFeature'`)
5. Push vers la branche (`git push origin feature/AmazingFeature`)
6. Ouvrir une Pull Request

## 📝 Licence

Ce projet est sous licence MIT. Voir le fichier `LICENSE` pour plus de détails.

## 🙏 Remerciements

- [Discord.py](https://discordpy.readthedocs.io/) - API Discord pour Python
- [FastAPI](https://fastapi.tiangolo.com/) - Framework web moderne
- [Neynar](https://neynar.com/) - API Farcaster officielle
- [Railway](https://railway.app/) - Plateforme de déploiement

## 📞 Support

- **Issues GitHub** : Pour les bugs et demandes de fonctionnalités
- **Discord** : Rejoignez notre serveur de support
- **Documentation** : Consultez les commentaires dans le code

---

**Fait avec ❤️ pour la communauté Farcaster**
