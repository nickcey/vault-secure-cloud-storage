"""
pre.py — Proxy re-encryption (Umbral) côté serveur.

Le serveur ne fait que deux choses avec Umbral :
  1. vérifier qu'un fragment de clé de re-chiffrement (kfrag) a bien été signé par
     le propriétaire et qu'il relie bien SA clé publique à celle du destinataire ;
  2. transformer la capsule d'un fichier pour le destinataire (re-chiffrement).
Il ne possède aucune clé secrète Umbral : il ne peut déchiffrer ni la capsule,
ni le résultat du re-chiffrement.

Bibliothèque : umbral-pre 0.10.0 (implémentation Rust de référence, liaisons Python).
Elle est isolée dans ce module pour pouvoir être remplacée sans toucher au reste.
"""
import base64

try:
    import umbral_pre as _u
    AVAILABLE = True
    IMPORT_ERROR = None
except Exception as e:          # bibliothèque absente (version de Python non prise en charge)
    _u = None
    AVAILABLE = False
    IMPORT_ERROR = str(e)


class PreError(Exception):
    pass


def _require():
    if not AVAILABLE:
        raise PreError("La bibliothèque umbral-pre n'est pas installée sur le serveur "
                       "(Python 3.7 à 3.11 requis).")


def _pk(hex_value):
    try:
        return _u.PublicKey.from_compressed_bytes(bytes.fromhex(hex_value))
    except Exception:
        raise PreError('Clé publique Umbral invalide')


def check_public_key(hex_value):
    """Vérifie qu'une clé publique compressée est un point valide de la courbe."""
    _require()
    _pk(hex_value)
    return True


def check_capsule(capsule_b64):
    _require()
    try:
        _u.Capsule.from_bytes(base64.b64decode(capsule_b64))
    except Exception:
        raise PreError('Capsule Umbral invalide')
    return True


def verify_kfrag(kfrag_b64, verifying_key_hex, delegating_pk_hex, receiving_pk_hex):
    """Le kfrag doit être signé par le propriétaire et lier ses clés à celles du destinataire."""
    _require()
    try:
        kfrag = _u.KeyFrag.from_bytes(base64.b64decode(kfrag_b64))
        kfrag.verify(_pk(verifying_key_hex), _pk(delegating_pk_hex), _pk(receiving_pk_hex))
    except PreError:
        raise
    except Exception:
        raise PreError('Fragment de re-chiffrement invalide ou non signé par le propriétaire')
    return True


def reencrypt(capsule_b64, kfrag_b64, verifying_key_hex, delegating_pk_hex, receiving_pk_hex):
    """Re-chiffre la capsule pour le destinataire ; renvoie le cfrag (b64)."""
    _require()
    try:
        kfrag = _u.KeyFrag.from_bytes(base64.b64decode(kfrag_b64))
        vkfrag = kfrag.verify(_pk(verifying_key_hex), _pk(delegating_pk_hex), _pk(receiving_pk_hex))
        capsule = _u.Capsule.from_bytes(base64.b64decode(capsule_b64))
        cfrag = _u.reencrypt(capsule, vkfrag)
    except PreError:
        raise
    except Exception:
        raise PreError('Re-chiffrement impossible')
    return base64.b64encode(bytes(cfrag)).decode()
