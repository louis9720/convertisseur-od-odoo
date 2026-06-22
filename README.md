# Convertisseur OD → Odoo | Fabricom

## Déploiement sur Render.com (gratuit)

### Étape 1 — Créer un compte GitHub
1. Va sur **github.com** et crée un compte gratuit
2. Crée un nouveau dépôt (repository) appelé `convertisseur-od-odoo`
3. Upload tous les fichiers de ce dossier dedans

### Étape 2 — Déployer sur Render
1. Va sur **render.com** et crée un compte gratuit
2. Clique sur **"New +"** → **"Web Service"**
3. Connecte ton compte GitHub et sélectionne le dépôt `convertisseur-od-odoo`
4. Render détecte automatiquement la config grâce au fichier `render.yaml`
5. Dans la section **"Environment Variables"**, ajoute :
   - Clé : `ANTHROPIC_API_KEY`
   - Valeur : ta clé API Anthropic (sk-ant-...)
6. Clique sur **"Create Web Service"**

### Étape 3 — Partager l'URL
Une fois déployé, Render te donne une URL comme :
`https://convertisseur-od-odoo.onrender.com`

Partage cette URL avec tes collègues — c'est tout !

### Notes importantes
- La clé API n'est **jamais visible** dans le code, elle est sécurisée dans Render
- Le service gratuit "dort" après 15 min d'inactivité — première ouverture ~30 secondes
- Pour éviter ça, abonnement Render à 7$/mois

## Structure du projet
```
convertisseur_app/
├── app.py                  # Serveur Python Flask
├── requirements.txt        # Dépendances Python
├── render.yaml             # Config déploiement Render
├── toutes_societes.json    # Plans comptables des sociétés
└── static/
    └── index.html          # Interface utilisateur
```
