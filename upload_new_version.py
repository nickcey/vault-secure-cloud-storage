# ══════════════════════════════════════════════════════════════
# NOUVELLE VERSION DE LA ROUTE /upload
# Avec chiffrement des métadonnées (Phase 1: Serveur)
# ══════════════════════════════════════════════════════════════

@app.route('/upload', methods=['GET', 'POST'])
@limiter.limit("20 per minute")
def upload():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    user = User.query.get(user_id)
    
    # ══════════════════════════════════════════════════════════════
    # CALCUL ESPACE UTILISÉ (avec support ancien/nouveau schéma)
    # ══════════════════════════════════════════════════════════════
    total_used = sum(
        (f.padded_size if f.padded_size else f.file_size)  # Compatibilité
        for f in FileMetadata.query.filter_by(user_id=user.id, is_deleted=False).all()
    )

    if request.method == 'POST':
        files = request.files.getlist('files')
        
        if not files or len(files) == 0 or files[0].filename == '':
            flash('Aucun fichier sélectionné', 'error')
            return redirect(url_for('upload'))
        
        success_count = 0
        error_count = 0
        blocked_files = []
        
        for file in files:
            if file.filename == '':
                continue

            original_filename = file.filename
            
            # ══════════════════════════════════════════════════════════════
            # VÉRIFICATION SÉCURITÉ : Whitelist
            # ══════════════════════════════════════════════════════════════
            is_allowed, reason = is_file_allowed(original_filename)
            if not is_allowed:
                error_count += 1
                blocked_files.append(f"{original_filename} ({reason})")
                continue
            
            # Calculer taille sans charger en RAM
            file.stream.seek(0, 2)
            file_size = file.stream.tell()
            file.stream.seek(0)

            # Vérifier quota (sur taille paddée estimée)
            from modules.padding import get_padded_size
            estimated_padded_size = get_padded_size(file_size)
            
            if total_used + estimated_padded_size > user.quota:
                error_count += 1
                blocked_files.append(f"{original_filename} (Quota dépassé)")
                continue

            # ══════════════════════════════════════════════════════════════
            # ÉTAPE 1 : CHIFFREMENT CONTENU (existant)
            # ══════════════════════════════════════════════════════════════
            from modules.crypto_engine import encrypt_file_streaming
            
            # Générer UUID opaque (remplace encrypted_filename)
            file_uuid = str(uuid.uuid4())
            encrypted_filename = f"{file_uuid}.enc"
            upload_path = os.path.join(app.config['UPLOAD_FOLDER'], encrypted_filename)

            # Chiffrement streaming
            result = encrypt_file_streaming(file.stream, upload_path, user.public_key)

            # ══════════════════════════════════════════════════════════════
            # ÉTAPE 2 : CRÉATION MÉTADONNÉES
            # ══════════════════════════════════════════════════════════════
            metadata = {
                "filename": original_filename,
                "mime_type": file.content_type or 'application/octet-stream',
                "plaintext_size": result['file_size'],
                "original_uploaded_at": datetime.utcnow().isoformat()
            }

            # ══════════════════════════════════════════════════════════════
            # ÉTAPE 3 : CHIFFREMENT MÉTADONNÉES
            # ══════════════════════════════════════════════════════════════
            from modules.metadata_crypto import encrypt_metadata_to_base64, generate_metadata_key
            from cryptography.hazmat.primitives import serialization, hashes
            from cryptography.hazmat.primitives.asymmetric import padding as rsa_padding
            
            try:
                # Générer clé AES pour métadonnées
                metadata_key = generate_metadata_key()
                
                # Chiffrer métadonnées
                encrypted_metadata_b64, metadata_iv_hex, metadata_tag_hex = encrypt_metadata_to_base64(
                    metadata, 
                    metadata_key
                )
                
                # Charger clé publique RSA
                public_key = serialization.load_pem_public_key(
                    user.public_key.encode('utf-8')
                )
                
                # Chiffrer clé métadonnées avec RSA
                encrypted_metadata_key = public_key.encrypt(
                    metadata_key,
                    rsa_padding.OAEP(
                        mgf=rsa_padding.MGF1(algorithm=hashes.SHA256()),
                        algorithm=hashes.SHA256(),
                        label=None
                    )
                )
                encrypted_metadata_key_b64 = base64.b64encode(encrypted_metadata_key).decode('ascii')
                
            except Exception as e:
                # Si chiffrement métadonnées échoue, supprimer fichier uploadé
                if os.path.exists(upload_path):
                    os.remove(upload_path)
                error_count += 1
                blocked_files.append(f"{original_filename} (Erreur chiffrement: {str(e)[:50]})")
                continue

            # ══════════════════════════════════════════════════════════════
            # ÉTAPE 4 : APPLICATION PADDING
            # ══════════════════════════════════════════════════════════════
            from modules.padding import add_padding
            
            try:
                # Lire fichier chiffré
                with open(upload_path, 'rb') as f:
                    encrypted_content = f.read()
                
                # Calculer taille paddée
                actual_padded_size = get_padded_size(len(encrypted_content))
                
                # Appliquer padding
                padded_content = add_padding(encrypted_content, actual_padded_size)
                
                # Réécrire fichier paddé
                with open(upload_path, 'wb') as f:
                    f.write(padded_content)
                    
            except Exception as e:
                # Si padding échoue, supprimer fichier
                if os.path.exists(upload_path):
                    os.remove(upload_path)
                error_count += 1
                blocked_files.append(f"{original_filename} (Erreur padding: {str(e)[:50]})")
                continue

            # ══════════════════════════════════════════════════════════════
            # ÉTAPE 5 : SAUVEGARDE EN DB (Nouveau schéma)
            # ══════════════════════════════════════════════════════════════
            file_meta = FileMetadata(
                # Nouveau schéma (métadonnées chiffrées)
                uuid=file_uuid,
                encrypted_metadata=encrypted_metadata_b64,
                metadata_iv=metadata_iv_hex,
                metadata_tag=metadata_tag_hex,
                encrypted_metadata_key=encrypted_metadata_key_b64,
                padded_size=actual_padded_size,
                
                # Chiffrement contenu (inchangé)
                encrypted_aes_key=result['encrypted_aes_key'].hex(),
                aes_iv=result['nonce'].hex(),
                aes_tag=result['tag'].hex(),
                
                # Ancien schéma (NULL pour rétrocompatibilité)
                filename=None,  # Plus utilisé
                encrypted_filename=None,  # Remplacé par uuid
                file_size=None,  # Remplacé par padded_size
                plaintext_size=None,  # Déplacé dans encrypted_metadata
                mime_type=None,  # Déplacé dans encrypted_metadata
                
                # Système
                user_id=user.id,
                uploaded_at=datetime.utcnow()
            )
            db.session.add(file_meta)

            # Log d'activité (UUID à la place du nom pour privacy)
            activity = ActivityLog(
                user_id=user_id, 
                action='Upload', 
                filename=file_uuid  # UUID opaque au lieu du nom clair
            )
            db.session.add(activity)

            success_count += 1
        
        # Commit en base
        db.session.commit()
        
        # ══════════════════════════════════════════════════════════════
        # MESSAGES UTILISATEUR
        # ══════════════════════════════════════════════════════════════
        if success_count > 0 and error_count == 0:
            message = f'{success_count} fichier(s) uploadé(s) et chiffré(s) avec succès ! 🔐'
            category = 'success'
        elif success_count > 0 and error_count > 0:
            blocked_list = ', '.join(blocked_files[:3])
            if len(blocked_files) > 3:
                blocked_list += f' (+{len(blocked_files) - 3} autres)'
            message = f'{success_count} uploadé(s), {error_count} refusé(s) : {blocked_list}'
            category = 'warning'
        else:
            if blocked_files:
                blocked_list = ', '.join(blocked_files[:3])
                if len(blocked_files) > 3:
                    blocked_list += f' (+{len(blocked_files) - 3} autres)'
                message = f'Aucun fichier uploadé. Fichiers refusés : {blocked_list}'
            else:
                message = 'Échec de l\'upload. Vérifiez les types de fichiers autorisés.'
            category = 'error'

        # Réponse JSON si AJAX
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            flash(message, category)
            return jsonify({'status': category, 'message': message}), 200

        flash(message, category)
        return redirect(url_for('dashboard'))
    
    # GET : Afficher formulaire upload
    return render_template('upload.html', max_space=user.quota, used_space=total_used)
