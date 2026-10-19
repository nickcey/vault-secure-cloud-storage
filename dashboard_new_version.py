# ══════════════════════════════════════════════════════════════
# NOUVELLE VERSION DE LA ROUTE /dashboard
# Avec déchiffrement des métadonnées
# ══════════════════════════════════════════════════════════════

@app.route('/dashboard')
def dashboard():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))
    
    user = User.query.get(user_id)

    # Récupérer tous les fichiers (non supprimés)
    files = FileMetadata.query.filter_by(user_id=user.id, is_deleted=False).order_by(FileMetadata.uploaded_at.desc()).all()
    
    # Récupérer la clé privée depuis la session
    private_key_pem = session.get('private_key_pem')
    
    files_data = []
    total_size = 0
    
    for f in files:
        try:
            # ══════════════════════════════════════════════════════════════
            # SUPPORT DUAL SCHÉMA (Ancien + Nouveau)
            # ══════════════════════════════════════════════════════════════
            
            if f.encrypted_metadata and private_key_pem:
                # NOUVEAU SCHÉMA : Métadonnées chiffrées
                from modules.metadata_crypto import decrypt_metadata_from_base64
                from cryptography.hazmat.primitives import serialization, hashes
                from cryptography.hazmat.primitives.asymmetric import padding as rsa_padding
                
                try:
                    # Charger clé privée RSA
                    private_key = serialization.load_pem_private_key(
                        private_key_pem.encode('utf-8') if isinstance(private_key_pem, str) else private_key_pem,
                        password=None
                    )
                    
                    # Déchiffrer clé métadonnées
                    encrypted_metadata_key = base64.b64decode(f.encrypted_metadata_key)
                    metadata_key = private_key.decrypt(
                        encrypted_metadata_key,
                        rsa_padding.OAEP(
                            mgf=rsa_padding.MGF1(algorithm=hashes.SHA256()),
                            algorithm=hashes.SHA256(),
                            label=None
                        )
                    )
                    
                    # Déchiffrer métadonnées
                    metadata = decrypt_metadata_from_base64(
                        f.encrypted_metadata,
                        f.metadata_iv,
                        f.metadata_tag,
                        metadata_key
                    )
                    
                    filename = metadata['filename']
                    file_size_bytes = f.padded_size if f.padded_size else 0  # Taille paddée
                    plaintext_size_bytes = metadata['plaintext_size']  # Taille réelle
                    mime_type = metadata.get('mime_type', 'application/octet-stream')
                    
                except Exception as e:
                    # Si déchiffrement échoue, afficher UUID
                    app.logger.error(f'Failed to decrypt metadata for file {f.id}: {e}')
                    filename = f.uuid or f'fichier_{f.id}'
                    file_size_bytes = f.padded_size if f.padded_size else 0
                    plaintext_size_bytes = file_size_bytes
                    mime_type = 'application/octet-stream'
            
            elif f.filename:
                # ANCIEN SCHÉMA : Métadonnées en clair (rétrocompatibilité)
                filename = f.filename
                file_size_bytes = f.file_size
                plaintext_size_bytes = f.plaintext_size or f.file_size
                mime_type = f.mime_type or 'application/octet-stream'
            
            else:
                # Fichier corrompu ou incomplet
                app.logger.warning(f'File {f.id} has no metadata (old or new)')
                filename = f'fichier_{f.id}'
                file_size_bytes = f.file_size or f.padded_size or 0
                plaintext_size_bytes = file_size_bytes
                mime_type = 'application/octet-stream'
            
            # Extraire extension
            ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
            icon_data = get_file_icon_data(ext)
            
            files_data.append({
                'id': f.id,
                'name': filename,
                'size': format_size(plaintext_size_bytes),  # Afficher taille réelle, pas paddée
                'size_bytes': plaintext_size_bytes,
                'uploaded_at': f.uploaded_at.strftime('%d/%m/%Y %H:%M'),
                'ext': ext,
                'icon': icon_data
            })
            
            # Pour le calcul total, utiliser taille paddée (quota)
            total_size += (f.padded_size if f.padded_size else f.file_size)
            
        except Exception as e:
            app.logger.error(f'Error processing file {f.id} in dashboard: {e}')
            continue
    
    file_count = len(files_data)
    used_space = format_size(total_size)
    max_space = user.quota
    used_percent = min(round((total_size / max_space) * 100, 1), 100) if max_space > 0 else 0
    
    stats = {
        'file_count': file_count,
        'used_space': used_space,
        'used_percent': used_percent,
        'total_space': format_size(max_space)
    }
    
    # Logs d'activité (les 5 derniers)
    activities = ActivityLog.query.filter_by(user_id=user.id).order_by(ActivityLog.timestamp.desc()).limit(5).all()

    return render_template('dashboard.html', user=user, files=files_data, stats=stats, activities=activities)
