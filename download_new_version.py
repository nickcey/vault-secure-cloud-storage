# ══════════════════════════════════════════════════════════════
# NOUVELLES VERSIONS DES ROUTES /download
# Avec support métadonnées chiffrées + padding
# ══════════════════════════════════════════════════════════════

@app.route('/download/<int:file_id>', methods=['GET', 'POST'])
def download_file(file_id):
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    file_meta = FileMetadata.query.get(file_id)
    if not file_meta or file_meta.user_id != user_id:
        flash('Fichier introuvable', 'error')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        password = request.form.get('password')
        user = User.query.get(user_id)

        _, private_key = login_user(user.email, password)

        if private_key is None:
            return jsonify({'error': 'Mot de passe incorrect'}), 401

        # Sérialiser clé privée
        from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption
        private_key_b64 = base64.b64encode(
            private_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())
        ).decode()

        # Token one-time valide 10 minutes
        dl_token = secrets.token_urlsafe(32)
        dt = DownloadToken(
            token=dl_token,
            file_id=file_id,
            user_id=user_id,
            private_key_pem=private_key_b64,
            expiry=int(time.time()) + 600
        )
        db.session.add(dt)

        # ══════════════════════════════════════════════════════════════
        # LOG : Utiliser UUID si nouveau schéma, sinon filename
        # ══════════════════════════════════════════════════════════════
        log_filename = file_meta.uuid if file_meta.uuid else file_meta.filename
        activity = ActivityLog(user_id=user_id, action='Téléchargement', filename=log_filename)
        db.session.add(activity)
        db.session.commit()

        return jsonify({'token': dl_token})

    # ══════════════════════════════════════════════════════════════
    # GET : Afficher page download (besoin nom pour affichage)
    # ══════════════════════════════════════════════════════════════
    # Déchiffrer métadonnées pour obtenir filename si nouveau schéma
    private_key_pem = session.get('private_key_pem')
    
    if file_meta.encrypted_metadata and private_key_pem:
        # NOUVEAU : Déchiffrer métadonnées
        try:
            from modules.metadata_crypto import decrypt_metadata_from_base64
            from cryptography.hazmat.primitives import serialization, hashes
            from cryptography.hazmat.primitives.asymmetric import padding as rsa_padding
            
            private_key = serialization.load_pem_private_key(
                private_key_pem.encode('utf-8') if isinstance(private_key_pem, str) else private_key_pem,
                password=None
            )
            
            encrypted_metadata_key = base64.b64decode(file_meta.encrypted_metadata_key)
            metadata_key = private_key.decrypt(
                encrypted_metadata_key,
                rsa_padding.OAEP(
                    mgf=rsa_padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            
            metadata = decrypt_metadata_from_base64(
                file_meta.encrypted_metadata,
                file_meta.metadata_iv,
                file_meta.metadata_tag,
                metadata_key
            )
            
            filename = metadata['filename']
            file_size = metadata['plaintext_size']
            
        except Exception as e:
            app.logger.error(f'Failed to decrypt metadata for download page: {e}')
            filename = file_meta.uuid or f'fichier_{file_meta.id}'
            file_size = file_meta.padded_size if file_meta.padded_size else 0
    
    elif file_meta.filename:
        # ANCIEN : Métadonnées en clair
        filename = file_meta.filename
        file_size = file_meta.file_size
    
    else:
        filename = f'fichier_{file_meta.id}'
        file_size = file_meta.file_size or file_meta.padded_size or 0
    
    # Créer objet file_meta modifié pour le template
    file_display = type('obj', (object,), {
        'id': file_meta.id,
        'filename': filename,
        'file_size': file_size
    })()
    
    return render_template('download.html', file=file_display, file_size=format_size(file_size))


@app.route('/download-file/<token>')
@csrf.exempt
def download_with_token(token):
    print(f"[download_with_token] token={token[:8]}... method={request.method}")

    dt = DownloadToken.query.filter_by(token=token).first()
    print(f"[download_with_token] token trouvé: {dt is not None}")

    if not dt:
        print(f"[download_with_token] TOKEN INTROUVABLE")
        return '<h2>Lien invalide ou expiré</h2><p><a href="/dashboard">Retour</a></p>', 403

    print(f"[download_with_token] expiry={dt.expiry}, now={int(time.time())}")

    if int(time.time()) > dt.expiry:
        db.session.delete(dt)
        db.session.commit()
        print(f"[download_with_token] TOKEN EXPIRÉ")
        return '<h2>Lien expiré</h2><p><a href="/dashboard">Retour</a></p>', 403

    file_id = dt.file_id
    user_id = dt.user_id
    private_key_b64 = dt.private_key_pem

    # Marquer token utilisé
    dt.expiry = int(time.time()) + 30
    db.session.commit()
    print(f"[download_with_token] Token marqué utilisé, file_id={file_id}")

    file_meta = FileMetadata.query.get(file_id)
    if not file_meta or file_meta.user_id != user_id:
        return 'Fichier introuvable', 404

    # ══════════════════════════════════════════════════════════════
    # SUPPORT DUAL SCHÉMA (Ancien + Nouveau)
    # ══════════════════════════════════════════════════════════════
    
    from cryptography.hazmat.primitives.serialization import load_pem_private_key
    from modules.crypto_engine import decrypt_file_from_storage, decrypt_file_streaming
    from flask import Response, stream_with_context
    import urllib.parse
    
    private_key = load_pem_private_key(base64.b64decode(private_key_b64), password=None)
    
    if file_meta.uuid:
        # NOUVEAU SCHÉMA
        upload_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{file_meta.uuid}.enc")
        
        # Déchiffrer métadonnées pour obtenir filename et plaintext_size
        try:
            from modules.metadata_crypto import decrypt_metadata_from_base64
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.asymmetric import padding as rsa_padding
            
            encrypted_metadata_key = base64.b64decode(file_meta.encrypted_metadata_key)
            metadata_key = private_key.decrypt(
                encrypted_metadata_key,
                rsa_padding.OAEP(
                    mgf=rsa_padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            
            metadata = decrypt_metadata_from_base64(
                file_meta.encrypted_metadata,
                file_meta.metadata_iv,
                file_meta.metadata_tag,
                metadata_key
            )
            
            filename = metadata['filename']
            plaintext_size = metadata['plaintext_size']
            
        except Exception as e:
            app.logger.error(f'Failed to decrypt metadata for download: {e}')
            filename = file_meta.uuid
            plaintext_size = file_meta.padded_size if file_meta.padded_size else 0
        
        # Lire fichier paddé
        with open(upload_path, 'rb') as f:
            padded_encrypted_data = f.read()
        
        # Supprimer padding (garder seulement plaintext_size bytes après chiffrement)
        # Note: plaintext_size est la taille AVANT chiffrement
        # La taille après chiffrement AES-GCM = plaintext_size + overhead (tag, etc.)
        # On doit lire le tag GCM stocké en DB
        from modules.padding import remove_padding
        
        # Calculer taille chiffrée attendue (plaintext_size + overhead GCM)
        # GCM ajoute 16 bytes de tag
        encrypted_size_expected = plaintext_size + 16
        
        # Supprimer padding
        encrypted_data = remove_padding(padded_encrypted_data, encrypted_size_expected)
        
    else:
        # ANCIEN SCHÉMA
        upload_path = os.path.join(app.config['UPLOAD_FOLDER'], file_meta.encrypted_filename)
        filename = file_meta.filename
        plaintext_size = file_meta.plaintext_size if file_meta.plaintext_size else 0
        
        # Pas de padding à supprimer
        with open(upload_path, 'rb') as f:
            encrypted_data = f.read()
    
    # ══════════════════════════════════════════════════════════════
    # DÉCHIFFREMENT CONTENU (même logique ancien/nouveau)
    # ══════════════════════════════════════════════════════════════
    encrypted_aes_key = bytes.fromhex(file_meta.encrypted_aes_key)
    nonce = bytes.fromhex(file_meta.aes_iv)
    
    encoded_name = urllib.parse.quote(filename)

    # Méthode 1: Streaming (si nonce 16 bytes)
    if len(nonce) == 16:
        # Note: decrypt_file_streaming lit depuis le fichier, pas depuis encrypted_data
        # On doit réécrire le fichier sans padding temporairement OU adapter la fonction
        # Pour simplifier, utilisons la méthode 2 (en mémoire) pour l'instant
        pass
    
    # Méthode 2: En mémoire (toujours utilisée maintenant)
    plaintext = decrypt_file_from_storage(encrypted_data, encrypted_aes_key, nonce, private_key)
    
    return send_file(
        io.BytesIO(plaintext),
        download_name=filename,
        as_attachment=True,
        mimetype='application/octet-stream'
    )
