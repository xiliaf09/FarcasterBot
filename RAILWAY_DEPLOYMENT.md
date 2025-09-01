# 🚀 Guide de Déploiement Railway

Ce guide vous accompagne étape par étape pour déployer votre Farcaster Tracker Bot sur Railway.

## 📋 Prérequis

- ✅ Repository GitHub configuré et poussé
- ✅ Compte Railway créé
- ✅ Bot Discord créé avec permissions
- ✅ Clé API Neynar obtenue

## 🔧 Étape 1: Connexion à Railway

1. **Aller sur [Railway](https://railway.app/)**
2. **Se connecter avec GitHub**
3. **Cliquer sur "New Project"**
4. **Sélectionner "Deploy from GitHub repo"**
5. **Choisir votre repository `FarcasterBot`**

## 🗄️ Étape 2: Configuration de la Base de Données

1. **Dans votre projet Railway, cliquer sur "New"**
2. **Sélectionner "Database" → "PostgreSQL"**
3. **Attendre que la base soit créée**
4. **Cliquer sur la base PostgreSQL créée**
5. **Copier l'URL de connexion (DATABASE_URL)**

## ⚙️ Étape 3: Configuration des Variables d'Environnement

1. **Dans votre projet Railway, aller dans l'onglet "Variables"**
2. **Ajouter les variables suivantes :**

```bash
# Discord Bot Configuration
DISCORD_TOKEN=votre_vrai_token_discord
DISCORD_APPLICATION_ID=votre_vrai_application_id

# Neynar API Configuration
NEYNAR_API_KEY=votre_vraie_clé_neynar
NEYNAR_WEBHOOK_SECRET=votre_vrai_secret_webhook

# Base de données (généré automatiquement par Railway)
DATABASE_URL=postgresql://... (copié depuis l'étape 2)

# URL publique (à configurer après l'étape 4)
PUBLIC_BASE_URL=https://votre-app.up.railway.app

# Configuration optionnelle
LOG_LEVEL=INFO
PORT=8000
```

## 🌐 Étape 4: Configuration du Domaine

1. **Dans votre projet Railway, aller dans l'onglet "Settings"**
2. **Section "Domains", noter l'URL générée**
3. **Mettre à jour la variable `PUBLIC_BASE_URL` avec cette URL**

## 🚀 Étape 5: Déploiement

1. **Railway détectera automatiquement le Dockerfile**
2. **Le déploiement commencera automatiquement**
3. **Attendre que le statut passe à "Deployed"**
4. **Vérifier les logs dans l'onglet "Deployments"**

## ✅ Étape 6: Vérification

1. **Tester l'endpoint de santé : `https://votre-app.up.railway.app/healthz`**
2. **Vérifier que le bot Discord est connecté**
3. **Tester une commande dans Discord : `!help`**

## 🔍 Dépannage

### Erreur "Signature invalide"
- Vérifier `NEYNAR_WEBHOOK_SECRET` dans Railway
- Redémarrer le service après modification

### Erreur "Impossible de se connecter à la base"
- Vérifier `DATABASE_URL` dans Railway
- Attendre que la base PostgreSQL soit prête

### Bot ne répond pas
- Vérifier `DISCORD_TOKEN` dans Railway
- Vérifier les permissions du bot Discord

### Webhook non créé
- Vérifier `NEYNAR_API_KEY` dans Railway
- Vérifier `PUBLIC_BASE_URL` (doit être accessible)

## 📊 Monitoring

- **Logs** : Onglet "Deployments" dans Railway
- **Métriques** : Onglet "Metrics" pour les performances
- **Variables** : Onglet "Variables" pour la configuration

## 🔄 Mise à Jour

- **Push sur GitHub** → Déploiement automatique sur Railway
- **Variables** : Modifier dans Railway, redémarrage automatique
- **Code** : Modifier localement, push, déploiement automatique

## 🆘 Support

- **Logs Railway** : Vérifier les erreurs dans l'interface
- **GitHub Issues** : Pour les problèmes de code
- **Documentation** : README.md du projet

---

**Votre bot est maintenant prêt à tracker les comptes Farcaster ! 🎉**
