import requests
import json
import logging
import time
from typing import Dict, List, Optional, Union
from config import config

logger = logging.getLogger(__name__)

class NeynarClient:
    """Client pour l'API Neynar selon la documentation officielle avec gestion des rate limits"""
    
    def __init__(self):
        logger.info("🔧 Initialisation de la classe NeynarClient...")
        
        self.api_key = config.NEYNAR_API_KEY
        logger.info(f"✅ API Key récupérée: {self.api_key[:10] if self.api_key else 'None'}...")
        
        self.base_url = "https://api.neynar.com"
        logger.info(f"✅ Base URL définie: {self.base_url}")
        
        self.headers = {
            "Accept": "application/json",
            "x-api-key": self.api_key,  # Correction selon la doc officielle
            "Content-Type": "application/json"
        }
        logger.info(f"✅ Headers configurés: {list(self.headers.keys())}")
        
        # Gestion des rate limits selon la documentation
        self.rate_limits = {
            "starter": {"rpm": 300, "rps": 5},
            "growth": {"rpm": 600, "rps": 10},
            "scale": {"rpm": 1200, "rps": 20}
        }
        logger.info(f"✅ Rate limits configurés: {list(self.rate_limits.keys())}")
        
        # Plan par défaut (starter) - à ajuster selon votre plan
        self.current_plan = "starter"
        self.last_request_time = 0
        self.requests_this_minute = 0
        self.minute_start = time.time()
        logger.info(f"✅ Plan par défaut: {self.current_plan}")
        
        logger.info("✅ Classe NeynarClient initialisée avec succès")
    
    def _handle_rate_limits(self):
        """Gérer les rate limits selon la documentation officielle"""
        current_time = time.time()
        
        # Réinitialiser le compteur de minute
        if current_time - self.minute_start >= 60:
            self.requests_this_minute = 0
            self.minute_start = current_time
        
        # Vérifier les limites par minute
        if self.requests_this_minute >= self.rate_limits[self.current_plan]["rpm"]:
            wait_time = 60 - (current_time - self.minute_start)
            logger.warning(f"Rate limit RPM atteint, attente de {wait_time:.2f} secondes")
            time.sleep(wait_time)
            self.requests_this_minute = 0
            self.minute_start = time.time()
        
        # Vérifier les limites par seconde
        if current_time - self.last_request_time < 1.0 / self.rate_limits[self.current_plan]["rps"]:
            wait_time = 1.0 / self.rate_limits[self.current_plan]["rps"] - (current_time - self.last_request_time)
            time.sleep(wait_time)
        
        self.last_request_time = current_time
        self.requests_this_minute += 1
    
    def _make_request(self, endpoint: str, method: str = "GET", data: Optional[Dict] = None, retries: int = 3) -> Dict:
        """Effectuer une requête à l'API Neynar avec gestion des rate limits et retry logic"""
        # Gérer les rate limits
        self._handle_rate_limits()
        
        url = f"{self.base_url}{endpoint}"
        
        for attempt in range(retries):
            try:
                if method == "GET":
                    response = requests.get(url, headers=self.headers, timeout=30)
                elif method == "POST":
                    response = requests.post(url, headers=self.headers, json=data, timeout=30)
                elif method == "PUT":
                    response = requests.put(url, headers=self.headers, json=data, timeout=30)
                elif method == "DELETE":
                    response = requests.delete(url, headers=self.headers, timeout=30)
                else:
                    raise ValueError(f"Méthode HTTP non supportée: {method}")
                
                # Gestion des codes d'erreur selon la documentation
                if response.status_code == 429:  # Rate limit
                    retry_after = int(response.headers.get('Retry-After', 60))
                    logger.warning(f"Rate limit atteint, attente de {retry_after} secondes")
                    time.sleep(retry_after)
                    continue
                
                elif response.status_code == 402:  # Payment required
                    logger.error("Erreur 402: Clé API manquante ou invalide")
                    raise ValueError("Clé API Neynar invalide ou manquante")
                
                elif response.status_code == 403:  # Forbidden
                    logger.error("Erreur 403: Accès refusé - vérifiez votre clé API et permissions")
                    raise ValueError("Accès refusé à l'API Neynar")
                
                response.raise_for_status()
                return response.json()
                
            except requests.exceptions.RequestException as e:
                if attempt < retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.warning(f"Tentative {attempt + 1} échouée, attente de {wait_time}s: {e}")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Erreur API Neynar {method} {endpoint} après {retries} tentatives: {e}")
                    raise
        
        raise Exception(f"Échec de la requête après {retries} tentatives")
    
    def get_user_by_fid(self, fid: int) -> Dict:
        """Récupérer un utilisateur par FID selon la doc officielle"""
        endpoint = f"/v2/farcaster/user/bulk?fids={fid}"
        response = self._make_request(endpoint)
        
        if not response.get("users") or len(response["users"]) == 0:
            raise ValueError(f"Utilisateur FID {fid} non trouvé")
        
        return response["users"][0]
    
    def get_user_by_username(self, username: str) -> Dict:
        """Récupérer un utilisateur par username selon la doc officielle"""
        endpoint = f"/v2/farcaster/user/search?q={username}&viewer_fid=1"
        response = self._make_request(endpoint)
        
        if not response.get("users") or len(response["users"]) == 0:
            raise ValueError(f"Utilisateur {username} non trouvé")
        
        # Chercher une correspondance exacte
        for user in response["users"]:
            if user.get("username", "").lower() == username.lower():
                return user
        
        # Si pas de correspondance exacte, retourner le premier
        logger.warning(f"Pas de correspondance exacte pour {username}, utilisation du premier résultat")
        return response["users"][0]
    
    def resolve_user(self, input_value: Union[str, int]) -> Dict:
        """Résoudre un utilisateur par FID ou username"""
        try:
            if isinstance(input_value, int) or str(input_value).isdigit():
                fid = int(input_value)
                return self.get_user_by_fid(fid)
            else:
                return self.get_user_by_username(str(input_value))
        except Exception as e:
            logger.error(f"Erreur lors de la résolution de l'utilisateur {input_value}: {e}")
            raise
    
    def create_webhook(self, url: str, author_fids: List[int] = None) -> Dict:
        """Créer un webhook Neynar selon la structure officielle"""
        payload = {
            "webhook_url": url,  # Correction selon la doc
            "subscription": {
                "cast.created": {
                    "author_fids": author_fids if author_fids else []
                }
            }
        }
        
        return self._make_request("/v2/farcaster/webhook", method="POST", data=payload)
    
    def update_webhook(self, webhook_id: str, author_fids: List[int]) -> Dict:
        """Mettre à jour un webhook existant selon la structure officielle"""
        payload = {
            "subscription": {
                "cast.created": {
                    "author_fids": author_fids
                }
            }
        }
        
        return self._make_request(f"/v2/farcaster/webhook/{webhook_id}", method="PUT", data=payload)
    
    def delete_webhook(self, webhook_id: str) -> None:
        """Supprimer un webhook"""
        self._make_request(f"/v2/farcaster/webhook/{webhook_id}", method="DELETE")
    
    def get_webhook(self, webhook_id: str) -> Dict:
        """Récupérer les détails d'un webhook"""
        return self._make_request(f"/v2/farcaster/webhook/{webhook_id}")
    
    def get_user_feed(self, fid: int, limit: int = 25) -> Dict:
        """Récupérer le feed d'un utilisateur selon la doc officielle"""
        endpoint = f"/v2/farcaster/feed?fid={fid}&limit={limit}"
        return self._make_request(endpoint)
    
    def search_casts(self, query: str, limit: int = 25) -> Dict:
        """Rechercher des casts selon la doc officielle"""
        endpoint = f"/v2/farcaster/cast/search?q={query}&limit={limit}"
        return self._make_request(endpoint)
    
    def get_cast_reactions(self, cast_hash: str) -> Dict:
        """Récupérer les réactions d'un cast selon la doc officielle"""
        endpoint = f"/v2/farcaster/cast/reactions?hash={cast_hash}"
        return self._make_request(endpoint)
    
    def set_plan(self, plan: str):
        """Définir le plan de rate limits (starter, growth, scale)"""
        if plan in self.rate_limits:
            self.current_plan = plan
            logger.info(f"Plan de rate limits défini sur: {plan}")
        else:
            logger.warning(f"Plan invalide: {plan}. Plans disponibles: {list(self.rate_limits.keys())}")

# Instance globale du client (initialisation différée)
_neynar_client_instance = None

def get_neynar_client():
    """Obtenir l'instance du client Neynar avec initialisation différée"""
    global _neynar_client_instance
    
    if _neynar_client_instance is None:
        try:
            logger.info("🔧 Tentative d'initialisation du client Neynar...")
            
            # Vérifier que la configuration est valide
            if not hasattr(config, 'NEYNAR_API_KEY'):
                logger.error("❌ NEYNAR_API_KEY n'existe pas dans config")
                return None
            
            if not config.NEYNAR_API_KEY:
                logger.error("❌ NEYNAR_API_KEY est vide ou None")
                return None
            
            logger.info(f"✅ NEYNAR_API_KEY trouvée: {config.NEYNAR_API_KEY[:10]}...")
            logger.info(f"✅ Base URL: {config.PUBLIC_BASE_URL}")
            
            _neynar_client_instance = NeynarClient()
            logger.info("✅ Client Neynar initialisé avec succès")
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de l'initialisation du client Neynar: {e}")
            logger.error(f"❌ Type d'erreur: {type(e).__name__}")
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            return None
    
    return _neynar_client_instance

# Alias pour la compatibilité
neynar_client = get_neynar_client()
