"""
Module de paiement Campay - Secure Cloud Storage
Gère les paiements Orange Money et MTN Money Cameroun
"""

import requests
from config import Config

# Dernière erreur renvoyée par CamPay (affichée à l'utilisateur si le paiement ne démarre pas)
last_error = None


def get_campay_token():
    """Obtient un token d'accès Campay"""
    global last_error
    try:
        response = requests.post(
            f"{Config.CAMPAY_BASE_URL}/token/",
            json={
                "username": Config.CAMPAY_APP_USERNAME,
                "password": Config.CAMPAY_APP_PASSWORD
            },
            timeout=10
        )
        data = response.json()
        if not data.get('token'):
            last_error = "identifiants CamPay refusés (vérifiez le fichier .env)"
        return data.get('token')
    except Exception as e:
        last_error = f"CamPay injoignable ({e.__class__.__name__})"
        return None


def initiate_payment(amount, phone_number, description, external_reference):
    """
    Initie un paiement via Campay
    
    Args:
        amount: montant en FCFA
        phone_number: numéro de téléphone (format 6XXXXXXXX)
        description: description du paiement
        external_reference: référence unique externe
    
    Returns:
        str: référence Campay ou None
    """
    global last_error
    last_error = None
    token = get_campay_token()
    if not token:
        return None
    
    try:
        response = requests.post(
            f"{Config.CAMPAY_BASE_URL}/collect/",
            json={
                "amount": str(amount),
                "currency": "XAF",
                "from": phone_number,
                "description": description,
                "external_reference": external_reference
            },
            headers={"Authorization": f"Token {token}"},
            timeout=10
        )
        data = response.json()
        if not data.get('reference'):
            last_error = data.get('message') or data.get('detail') or str(data)[:200]
        return data.get('reference')
    except Exception as e:
        last_error = f"CamPay injoignable ({e.__class__.__name__})"
        return None


def check_payment_status(reference):
    """
    Vérifie le statut d'un paiement Campay
    
    Args:
        reference: référence Campay
    
    Returns:
        str: 'SUCCESSFUL', 'FAILED', 'PENDING' ou None
    """
    token = get_campay_token()
    if not token:
        return None
    
    try:
        response = requests.get(
            f"{Config.CAMPAY_BASE_URL}/transaction/{reference}/",
            headers={"Authorization": f"Token {token}"},
            timeout=10
        )
        data = response.json()
        return data.get('status')
    except Exception:
        return None