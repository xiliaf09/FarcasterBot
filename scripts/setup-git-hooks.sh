#!/bin/bash
#
# Script pour configurer les hooks Git automatiquement
#

echo "🔧 Configuration des hooks Git pour la sécurité..."

# Rendre le hook pre-commit exécutable
chmod +x .git/hooks/pre-commit

echo "✅ Hook pre-commit configuré avec succès"
echo "   La sécurité sera maintenant vérifiée automatiquement avant chaque commit"
echo ""
echo "💡 Pour désactiver temporairement :"
echo "   git commit --no-verify"
echo ""
echo "💡 Pour réactiver :"
echo "   chmod +x .git/hooks/pre-commit"
