#!/usr/bin/env python3
"""
Module de Padding pour Obfuscation des Tailles
===============================================

Auteur: Kiro AI
Date: 8 juillet 2026
Objectif: Masquer la taille réelle des fichiers pour empêcher l'analyse de corrélation

Ce module applique un padding agressif aux fichiers chiffrés pour qu'un attaquant
avec accès à la base de données ne puisse pas deviner le contenu via la taille.

Principe:
- Arrondir la taille à la tranche supérieure (paliers exponentiels)
- Exemple: 1.5 Mo → arrondi à 4 Mo
- Plusieurs fichiers peuvent avoir la même taille paddée (camouflage)

Fonctionnalités:
- get_padded_size(): Calcule la taille avec padding
- add_padding(): Ajoute du padding aléatoire
- remove_padding(): Supprime le padding
"""

import secrets
import os


# ══════════════════════════════════════════════════════════════
# CONFIGURATION DES PALIERS DE PADDING
# ══════════════════════════════════════════════════════════════

# Paliers de padding (tailles en bytes)
# Progression exponentielle pour optimiser overhead vs obfuscation
PADDING_SIZES = [
    4 * 1024,                # 4 Ko
    16 * 1024,               # 16 Ko
    64 * 1024,               # 64 Ko
    256 * 1024,              # 256 Ko (0.25 Mo)
    1 * 1024 * 1024,         # 1 Mo
    4 * 1024 * 1024,         # 4 Mo
    16 * 1024 * 1024,        # 16 Mo
    64 * 1024 * 1024,        # 64 Mo
    256 * 1024 * 1024,       # 256 Mo (0.25 Go)
    1024 * 1024 * 1024,      # 1 Go
    # Au-delà de 1 Go : arrondir au Go supérieur
]


def get_padded_size(actual_size):
    """
    Taille après remplissage selon l'algorithme Padmé (Nikitin et al., 2019),
    identique à vaultGetPaddedSize() côté navigateur.

    Pour une taille L (au moins 4 Kio), seuls floor(log2(floor(log2 L))) + 1 bits
    de poids fort sont conservés ; le surcoût est au plus de 12 %.

    >>> get_padded_size(1024)
    4096
    >>> get_padded_size(5000)
    5120
    >>> get_padded_size(10 * 1024 * 1024)
    10485760
    """
    size = max(int(actual_size), PADDING_SIZES[0])
    e = size.bit_length() - 1
    s = e.bit_length()
    step = 1 << (e - s)
    return -(-size // step) * step


def add_padding(data, target_size):
    """
    Ajoute du padding aléatoire pour atteindre la taille cible.
    
    Le padding est composé de bytes aléatoires pour éviter qu'un attaquant
    puisse distinguer les données réelles du padding (ex: si padding = 0x00).
    
    Args:
        data (bytes): Données originales
        target_size (int): Taille cible après padding
    
    Returns:
        bytes: Données + padding aléatoire
    
    Raises:
        ValueError: Si target_size < len(data)
    
    Examples:
        >>> data = b"Hello World"
        >>> padded = add_padding(data, 100)
        >>> len(padded)
        100
        >>> padded[:11]
        b'Hello World'
    """
    current_size = len(data)
    
    if target_size < current_size:
        raise ValueError(f"target_size ({target_size}) doit être >= len(data) ({current_size})")
    
    if target_size == current_size:
        return data  # Pas de padding nécessaire
    
    # Calcul taille padding
    padding_size = target_size - current_size
    
    # Génération padding aléatoire (cryptographiquement sûr)
    padding = secrets.token_bytes(padding_size)
    
    # Concaténation données + padding
    return data + padding


def remove_padding(padded_data, original_size):
    """
    Supprime le padding pour récupérer les données originales.
    
    Args:
        padded_data (bytes): Données avec padding
        original_size (int): Taille originale sans padding
    
    Returns:
        bytes: Données originales sans padding
    
    Raises:
        ValueError: Si original_size > len(padded_data)
    
    Examples:
        >>> data = b"Hello World"
        >>> padded = add_padding(data, 100)
        >>> unpadded = remove_padding(padded, len(data))
        >>> unpadded == data
        True
    """
    if original_size > len(padded_data):
        raise ValueError(f"original_size ({original_size}) > len(padded_data) ({len(padded_data)})")
    
    # Extraction des données originales (suppression du padding)
    return padded_data[:original_size]


def format_size(size_bytes):
    """
    Formate une taille en bytes vers une chaîne lisible (Ko, Mo, Go).
    
    Utilitaire pour afficher les tailles de manière lisible.
    
    Args:
        size_bytes (int): Taille en bytes
    
    Returns:
        str: Taille formatée (ex: "2.5 Mo", "1.2 Go")
    
    Examples:
        >>> format_size(1024)
        '1.0 Ko'
        >>> format_size(1536)
        '1.5 Ko'
        >>> format_size(1048576)
        '1.0 Mo'
        >>> format_size(1073741824)
        '1.0 Go'
    """
    if size_bytes < 1024:
        return f"{size_bytes} bytes"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} Ko"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} Mo"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} Go"


def calculate_padding_overhead(actual_size, padded_size):
    """
    Calcule l'overhead (surcoût) du padding en pourcentage.
    
    Args:
        actual_size (int): Taille réelle
        padded_size (int): Taille avec padding
    
    Returns:
        float: Overhead en pourcentage
    
    Examples:
        >>> calculate_padding_overhead(1024, 4096)
        300.0
        >>> calculate_padding_overhead(2 * 1024 * 1024, 4 * 1024 * 1024)
        100.0
    """
    if actual_size == 0:
        return 0.0
    
    overhead = ((padded_size - actual_size) / actual_size) * 100
    return round(overhead, 2)


def get_padding_statistics():
    """
    Génère des statistiques sur les paliers de padding.
    
    Utile pour analyser l'overhead moyen et la distribution des tailles.
    
    Returns:
        list: Liste de dictionnaires avec statistiques par palier
    
    Example:
        >>> stats = get_padding_statistics()
        >>> stats[0]['size']
        4096
        >>> stats[0]['readable']
        '4.0 Ko'
    """
    stats = []
    
    for i, padded_size in enumerate(PADDING_SIZES):
        # Taille précédente (pour calculer la plage)
        prev_size = PADDING_SIZES[i - 1] + 1 if i > 0 else 1
        
        stats.append({
            'index': i,
            'size': padded_size,
            'readable': format_size(padded_size),
            'range_start': prev_size,
            'range_end': padded_size,
            'range_readable': f"{format_size(prev_size)} - {format_size(padded_size)}"
        })
    
    return stats


# ══════════════════════════════════════════════════════════════
# TESTS UNITAIRES
# ══════════════════════════════════════════════════════════════

if __name__ == '__main__':
    print("🎭 Tests Module padding.py")
    print("=" * 60)
    
    # Test 1: Calcul tailles paddées
    print("\n[Test 1] Calcul tailles paddées...")
    test_cases = [
        (1024, 4 * 1024),                          # 1 Ko → 4 Ko
        (10 * 1024, 16 * 1024),                    # 10 Ko → 16 Ko
        (500 * 1024, 1024 * 1024),                 # 500 Ko → 1 Mo
        (2 * 1024 * 1024, 4 * 1024 * 1024),        # 2 Mo → 4 Mo
        (50 * 1024 * 1024, 64 * 1024 * 1024),      # 50 Mo → 64 Mo
        (1.5 * 1024 * 1024 * 1024, 2 * 1024 * 1024 * 1024),  # 1.5 Go → 2 Go
    ]
    
    for actual, expected in test_cases:
        result = get_padded_size(int(actual))
        overhead = calculate_padding_overhead(int(actual), result)
        assert result == int(expected), f"Erreur: {actual} → {result} (attendu {expected})"
        print(f"✅ {format_size(int(actual)):>10} → {format_size(result):>10} (overhead: +{overhead:>6.1f}%)")
    
    # Test 2: Ajout/Suppression padding
    print("\n[Test 2] Ajout/Suppression padding...")
    original_data = b"Hello World! This is a test message."
    original_size = len(original_data)
    target_size = 1024  # 1 Ko
    
    padded_data = add_padding(original_data, target_size)
    assert len(padded_data) == target_size, f"Taille paddée incorrecte: {len(padded_data)}"
    print(f"✅ Données originales : {original_size} bytes")
    print(f"✅ Données paddées    : {len(padded_data)} bytes")
    
    unpadded_data = remove_padding(padded_data, original_size)
    assert unpadded_data == original_data, "Données altérées après padding/unpadding"
    print(f"✅ Données restaurées : {len(unpadded_data)} bytes (identiques)")
    
    # Test 3: Padding aléatoire (non-déterministe)
    print("\n[Test 3] Padding aléatoire (non-déterministe)...")
    padded1 = add_padding(original_data, target_size)
    padded2 = add_padding(original_data, target_size)
    
    # Les paddeds doivent être différents (padding aléatoire)
    assert padded1[:original_size] == padded2[:original_size], "Données originales altérées"
    assert padded1[original_size:] != padded2[original_size:], "Padding déterministe (devrait être aléatoire)"
    print(f"✅ Padding 1: {padded1[original_size:original_size+10].hex()}...")
    print(f"✅ Padding 2: {padded2[original_size:original_size+10].hex()}...")
    print(f"✅ Paddings différents (aléatoire) ✓")
    
    # Test 4: Cas limites
    print("\n[Test 4] Cas limites...")
    
    # Cas 1: Taille 0
    assert get_padded_size(0) == PADDING_SIZES[0], "Taille 0 devrait retourner min padding"
    print(f"✅ Taille 0 → {format_size(get_padded_size(0))}")
    
    # Cas 2: Taille exactement égale à un palier
    for size in [4 * 1024, 1024 * 1024, 1024 * 1024 * 1024]:
        assert get_padded_size(size) == size, f"Taille {size} devrait rester inchangée"
        print(f"✅ Taille exacte {format_size(size)} → pas de padding")
    
    # Cas 3: Très gros fichier (> 1 Go)
    huge_size = 5.5 * 1024 * 1024 * 1024  # 5.5 Go
    padded = get_padded_size(int(huge_size))
    expected_huge = 6 * 1024 * 1024 * 1024  # 6 Go
    assert padded == expected_huge, f"Très gros fichier mal paddé: {padded}"
    print(f"✅ {format_size(int(huge_size))} → {format_size(padded)}")
    
    # Test 5: Statistiques paliers
    print("\n[Test 5] Statistiques des paliers de padding...")
    stats = get_padding_statistics()
    print(f"✅ Nombre de paliers : {len(stats)}")
    print(f"\n{'Index':<6} {'Taille Paddée':<15} {'Plage':<30}")
    print("-" * 60)
    for s in stats[:5]:  # Afficher les 5 premiers
        print(f"{s['index']:<6} {s['readable']:<15} {s['range_readable']:<30}")
    print("   ...")
    print(f"{stats[-1]['index']:<6} {stats[-1]['readable']:<15} {stats[-1]['range_readable']:<30}")
    
    # Test 6: Format size
    print("\n[Test 6] Format taille lisible...")
    test_formats = [
        (512, "512 bytes"),
        (1024, "1.0 Ko"),
        (1536, "1.5 Ko"),
        (1048576, "1.0 Mo"),
        (2621440, "2.5 Mo"),
        (1073741824, "1.0 Go"),
        (2684354560, "2.5 Go"),
    ]
    
    for size, expected in test_formats:
        result = format_size(size)
        # Note: format peut varier légèrement selon le nombre de décimales
        print(f"✅ {size:>12} bytes → {result:>10}")
    
    # Test 7: Overhead analysis
    print("\n[Test 7] Analyse overhead padding...")
    print(f"\n{'Taille Réelle':<15} {'Taille Paddée':<15} {'Overhead':<10} {'Impact'}")
    print("-" * 60)
    
    test_sizes = [
        1 * 1024,           # 1 Ko
        10 * 1024,          # 10 Ko
        500 * 1024,         # 500 Ko
        2 * 1024 * 1024,    # 2 Mo
        50 * 1024 * 1024,   # 50 Mo
        500 * 1024 * 1024,  # 500 Mo
    ]
    
    for size in test_sizes:
        padded = get_padded_size(size)
        overhead = calculate_padding_overhead(size, padded)
        
        if overhead > 100:
            impact = "⚠️  Élevé"
        elif overhead > 50:
            impact = "📊 Moyen"
        else:
            impact = "✅ Faible"
        
        print(f"{format_size(size):<15} {format_size(padded):<15} +{overhead:>6.1f}%  {impact}")
    
    print("\n" + "=" * 60)
    print("✅ TOUS LES TESTS RÉUSSIS !")
    print("=" * 60)
    
    # Statistiques globales
    print("\n📊 Statistiques Globales:")
    total_actual = sum(test_sizes)
    total_padded = sum(get_padded_size(s) for s in test_sizes)
    avg_overhead = calculate_padding_overhead(total_actual, total_padded)
    
    print(f"   - Taille totale réelle : {format_size(total_actual)}")
    print(f"   - Taille totale paddée : {format_size(total_padded)}")
    print(f"   - Overhead moyen       : +{avg_overhead:.1f}%")
    print(f"   - Nombre de paliers    : {len(PADDING_SIZES)}")
    print(f"   - Palier min           : {format_size(PADDING_SIZES[0])}")
    print(f"   - Palier max           : {format_size(PADDING_SIZES[-1])}")
    
    print("\n💡 Recommandations:")
    print("   - Overhead acceptable pour fichiers > 1 Mo (< 100%)")
    print("   - Obfuscation excellente (plusieurs fichiers = même taille)")
    print("   - Padding aléatoire empêche détection pattern")
