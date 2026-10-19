# 🧪 Tests de la Protection CSRF

## 🎯 Objectif
Vérifier que l'application est protégée contre les attaques CSRF (Cross-Site Request Forgery)

---

## ✅ Test 1 : Vérifier la présence du token CSRF dans la page

### Étapes :
1. Ouvre ton navigateur et va sur **http://127.0.0.1:5000/login**
2. Clique droit > **Inspecter** (ou appuie sur **F12**)
3. Va dans l'onglet **Elements** (ou **Inspecteur**)
4. Dans le `<head>`, cherche une ligne comme celle-ci :
   ```html
   <meta name="csrf-token" content="IjYxN2...très_long_token...">
   ```

### ✅ Résultat attendu :
- La meta tag `csrf-token` doit être présente
- Le `content` doit contenir un long token aléatoire

### ❌ Si la meta tag est absente :
La protection CSRF n'est pas activée sur cette page.

---

## ✅ Test 2 : Vérifier le token dans les formulaires

### Étapes :
1. Toujours sur la page de login, dans l'inspecteur
2. Cherche la balise `<form method="POST">`
3. À l'intérieur du formulaire, tu dois voir :
   ```html
   <input type="hidden" name="csrf_token" value="IjYxN2...token...">
   ```

### ✅ Résultat attendu :
- Un champ caché `csrf_token` est présent dans le formulaire
- La valeur correspond au token de la meta tag

### ❌ Si le champ est absent :
Le formulaire n'est pas protégé.

---

## ✅ Test 3 : Tester une attaque CSRF (simulation)

### Étapes :
1. **Connecte-toi** à Vault normalement
2. Une fois connecté, va sur le **Dashboard**
3. Ouvre la **Console JavaScript** (F12 > Console)
4. Tape cette commande pour simuler une attaque CSRF :
   ```javascript
   fetch('/delete/1', { 
       method: 'POST',
       headers: { 'Content-Type': 'application/json' }
   }).then(r => console.log('Status:', r.status))
   ```
5. Appuie sur **Entrée**

### ✅ Résultat attendu :
```
Status: 400
```
**Message dans l'application :** "Votre session a expiré ou la requête est invalide"

**Explication :** La requête est **BLOQUÉE** car elle ne contient pas le token CSRF ! 🛡️

### ❌ Si Status: 200 ou 302 :
La protection CSRF ne fonctionne PAS. La requête malveillante a réussi ! ⚠️

---

## ✅ Test 4 : Tester avec le token valide

### Étapes :
1. Toujours dans la Console (tu dois être connecté)
2. Tape cette commande pour récupérer le token CSRF :
   ```javascript
   const token = document.querySelector('meta[name="csrf-token"]').content;
   console.log('Token CSRF:', token);
   ```
3. Maintenant, envoie une requête avec le token :
   ```javascript
   const formData = new FormData();
   formData.append('csrf_token', token);
   
   fetch('/delete/999', {
       method: 'POST',
       body: formData
   }).then(r => console.log('Status:', r.status, r.statusText))
   ```

### ✅ Résultat attendu :
```
Status: 302 Found
```
OU
```
Status: 404 Not Found
```
(Selon que le fichier 999 existe ou pas)

**Explication :** La requête est **ACCEPTÉE** car le token CSRF est valide ! ✅

---

## ✅ Test 5 : Tester l'upload avec AJAX

### Étapes :
1. Va sur **http://127.0.0.1:5000/upload**
2. Ouvre la Console (F12)
3. Sélectionne un petit fichier (image, txt)
4. Clique sur **Upload**
5. Regarde dans l'onglet **Network** (Réseau)

### ✅ Résultat attendu :
- La requête POST `/upload` doit avoir un statut **200 OK** ou **302 Found**
- Dans les **Headers** de la requête, tu dois voir :
  ```
  X-CSRFToken: IjYxN2...token...
  ```
  OU dans le **Form Data** :
  ```
  csrf_token: IjYxN2...token...
  ```

**Explication :** Le script `csrf.js` ajoute automatiquement le token ! ✅

---

## ✅ Test 6 : Tester le login

### Étapes :
1. Déconnecte-toi (si connecté)
2. Va sur **http://127.0.0.1:5000/login**
3. Remplis le formulaire avec des identifiants valides
4. Avant de cliquer sur "Connexion", ouvre l'onglet **Network** (F12)
5. Clique sur **Connexion**
6. Regarde la requête POST `/login`

### ✅ Résultat attendu :
Dans le **Form Data** de la requête, tu dois voir :
```
email: ton@email.com
password: ••••••••
csrf_token: IjYxN2...token...
```

**Explication :** Le formulaire envoie bien le token CSRF ! ✅

---

## ✅ Test 7 : Tester le webhook (doit être exempté)

### Étapes :
1. Dans la Console, simule un webhook Campay :
   ```javascript
   fetch('/payment-webhook', {
       method: 'POST',
       headers: { 'Content-Type': 'application/json' },
       body: JSON.stringify({
           reference: 'TEST123',
           status: 'SUCCESSFUL'
       })
   }).then(r => console.log('Status:', r.status))
   ```

### ✅ Résultat attendu :
```
Status: 200 OK
```

**Explication :** Le webhook est **exempté** de CSRF (car il vient de Campay, pas de notre site) ! ✅

---

## 🎨 Test Visuel Complet

### Ouvre ces pages et vérifie la meta tag CSRF :
- ✅ /login
- ✅ /signup
- ✅ /dashboard
- ✅ /upload
- ✅ /settings
- ✅ /admin/login (si admin)

### Teste ces actions et vérifie qu'elles fonctionnent :
- ✅ Connexion
- ✅ Inscription
- ✅ Upload de fichier
- ✅ Suppression de fichier (dans la corbeille)
- ✅ Renommage de fichier
- ✅ Changement de mot de passe
- ✅ Création de lien de partage

### Si TOUTES ces actions fonctionnent → CSRF est bien implémenté ! 🎉

---

## 🚨 Test de Sécurité Avancé (Optionnel)

### Créer une page d'attaque simulée

1. Crée un fichier HTML local `attack.html` :
```html
<!DOCTYPE html>
<html>
<head><title>Attaque CSRF Simulée</title></head>
<body>
<h1>Page Malveillante (Simulation)</h1>
<p>Si tu cliques sur le bouton, on va tenter de supprimer ton fichier ID 1</p>

<form id="csrf-attack" action="http://127.0.0.1:5000/delete/1" method="POST">
    <button type="submit">Cliquez ici pour gagner 1000€ 🎁</button>
</form>

<script>
// Attaque automatique (ne pas décommenter en vrai !)
// document.getElementById('csrf-attack').submit();
</script>
</body>
</html>
```

2. Ouvre `attack.html` dans ton navigateur
3. **Assure-toi d'être connecté à Vault** dans un autre onglet
4. Clique sur le bouton

### ✅ Résultat attendu :
Tu es redirigé vers Vault avec le message :
```
⚠️ Votre session a expiré ou la requête est invalide. Veuillez réessayer.
```

**Le fichier N'est PAS supprimé** ! 🛡️

### ❌ Si le fichier est supprimé :
La protection CSRF ne fonctionne PAS ! ⚠️

---

## 📊 Checklist Finale

- [ ] Meta tag `csrf-token` présente dans toutes les pages
- [ ] Champs `csrf_token` présents dans tous les formulaires POST
- [ ] Requêtes sans token sont **bloquées** (Status 400)
- [ ] Requêtes avec token sont **acceptées** (Status 200/302)
- [ ] Upload de fichiers fonctionne
- [ ] Connexion/Inscription fonctionnent
- [ ] Actions admin fonctionnent
- [ ] Webhook Campay n'est PAS bloqué
- [ ] Attaque CSRF simulée est **bloquée**

---

## ✅ Si tous les tests passent :

**🎉 FÉLICITATIONS ! Ton application Vault est maintenant 100% protégée contre les attaques CSRF !**

---

## 🆘 Dépannage

### Erreur "The CSRF token is missing"
**Cause :** Le formulaire ne contient pas le token
**Solution :** Vérifie que `{% include 'partials/csrf_token.html' %}` est dans le `<form>`

### Erreur "The CSRF session token is missing"
**Cause :** La session Flask ne fonctionne pas
**Solution :** Vérifie que `SECRET_KEY` est défini dans `config.py`

### Upload ne fonctionne plus
**Cause :** Le token n'est pas envoyé dans la requête AJAX
**Solution :** Vérifie que `/static/js/csrf.js` est chargé

### Webhook Campay est bloqué
**Cause :** L'exemption CSRF n'est pas appliquée
**Solution :** Ajoute `@csrf.exempt` sur la route

---

**Date des tests :** 2026-07-08  
**Application testée :** Vault Secure Cloud Storage  
**Protection CSRF :** ✅ ACTIVE
