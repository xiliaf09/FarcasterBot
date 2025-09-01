import requests
import json
import logging
from typing import Dict, List, Optional, Union
from config import config

logger = logging.getLogger(__name__)

class NeynarClient:
    """Client pour l'API Neynar"""
    
    def __init__(self):
        self.api_key = config.NEYNAR_API_KEY
        self.base_url = "https://api.neynar.com/v2"
        self.headers = {
            "Accept": "application/json",
            "api_key": self.api_key
        }
    
    def _make_request(self, endpoint: str, method: str = "GET", data: Optional[Dict] = None) -> Dict:
        """Effectuer une requête à l'API Neynar"""
        url = f"{self.base_url}{endpoint}"
        
        try:
            if method == "GET":
                response = requests.get(url, headers=self.headers)
            elif method == "POST":
                response = requests.post(url, headers=self.headers, json=data)
            elif method == "PUT":
                response = requests.put(url, headers=self.headers, json=data)
            elif method == "DELETE":
                response = requests.delete(url, headers=self.headers)
            else:
                raise ValueError(f"Méthode HTTP non supportée: {method}")
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Erreur API Neynar {method} {endpoint}: {e}")
            raise
    
    def get_user_by_fid(self, fid: int) -> Dict:
        """Récupérer un utilisateur par FID"""
        endpoint = f"/farcaster/user/bulk-by-fid?fids={fid}"
        response = self._make_request(endpoint)
        
        if not response.get("users") or len(response["users"]) == 0:
            raise ValueError(f"Utilisateur FID {fid} non trouvé")
        
        return response["users"][0]
    
    def get_user_by_username(self, username: str) -> Dict:
        """Récupérer un utilisateur par username"""
        endpoint = f"/farcaster/user/search?q={username}&viewer_fid=1"
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
        """Créer un webhook Neynar"""
        payload = {
            "url": url,
            "subscription": {
                "cast.created": {
                    "author_fids": author_fids if author_fids else []
                }
            }
        }
        
        return self._make_request("/farcaster/webhook", method="POST", data=payload)
    
    def update_webhook(self, webhook_id: str, author_fids: List[int]) -> Dict:
        """Mettre à jour un webhook existant"""
        payload = {
            "subscription": {
                "cast.created": {
                    "author_fids": author_fids
                }
            }
        }
        
        return self._make_request(f"/farcaster/webhook/{webhook_id}", method="PUT", data=payload)
    
    def delete_webhook(self, webhook_id: str) -> None:
        """Supprimer un webhook"""
        self._make_request(f"/farcaster/webhook/{webhook_id}", method="DELETE")
    
    def get_webhook(self, webhook_id: str) -> Dict:
        """Récupérer les détails d'un webhook"""
        return self._make_request(f"/farcaster/webhook/{webhook_id}")

# Instance globale du client
neynar_client = NeynarClient()
