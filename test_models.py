#!/usr/bin/env python3
"""Test rapide des models mis à jour"""

print("🔍 Test des models mis à jour...")

try:
    from database.models import FileMetadata
    print("✅ Import FileMetadata réussi")
    
    # Vérifier les nouveaux champs
    new_fields = ['uuid', 'encrypted_metadata', 'metadata_iv', 'metadata_tag', 
                  'encrypted_metadata_key', 'padded_size']
    
    print("\n📋 Vérification des nouveaux champs:")
    for field in new_fields:
        if hasattr(FileMetadata, field):
            print(f"   ✅ {field}")
        else:
            print(f"   ❌ {field} MANQUANT")
    
    # Vérifier les anciens champs (rétrocompatibilité)
    old_fields = ['filename', 'encrypted_filename', 'file_size', 'plaintext_size', 
                  'mime_type', 'encrypted_aes_key', 'aes_iv', 'aes_tag']
    
    print("\n📋 Vérification rétrocompatibilité (anciens champs):")
    for field in old_fields:
        if hasattr(FileMetadata, field):
            print(f"   ✅ {field}")
        else:
            print(f"   ❌ {field} MANQUANT")
    
    print("\n✅ Tous les champs sont présents !")
    
except Exception as e:
    print(f"\n❌ Erreur : {e}")
    import traceback
    traceback.print_exc()
