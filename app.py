import os
import json
import base64
import requests
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder='static')
CORS(app)

# Clé API lue depuis les variables d'environnement (jamais dans le code)
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')

# Charger les plans comptables
with open('toutes_societes.json', 'r', encoding='utf-8') as f:
    PLANS_COMPTABLES = json.load(f)

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/api/societes', methods=['GET'])
def get_societes():
    """Retourne la liste des sociétés et le nombre de comptes."""
    result = {}
    for key, comptes in PLANS_COMPTABLES.items():
        result[key] = len(comptes)
    return jsonify(result)

@app.route('/api/convertir', methods=['POST'])
def convertir():
    """Reçoit un PDF en base64, appelle Claude, retourne les écritures."""
    if not ANTHROPIC_API_KEY:
        return jsonify({'error': 'Clé API non configurée sur le serveur'}), 500

    data = request.json
    societe = data.get('societe')
    file_b64 = data.get('file_b64')
    file_type = data.get('file_type', 'pdf')
    file_content_text = data.get('file_content_text', '')

    if not societe or societe not in PLANS_COMPTABLES:
        return jsonify({'error': 'Société invalide'}), 400

    # Construire le message pour Claude
    if file_type == 'pdf':
        content = [
            {
                "type": "document",
                "source": {"type": "base64", "media_type": "application/pdf", "data": file_b64}
            },
            {
                "type": "text",
                "text": "Tu es expert-comptable. Extrais TOUTES les lignes d'écritures comptables de ce document. Retourne UNIQUEMENT un JSON valide sans balises markdown : {\"ecritures\":[{\"compte\":\"6411\",\"libelle\":\"Salaires\",\"debit\":1500,\"credit\":0}]}. Règles : montants en nombres, 0 si absent, ignorer les lignes de totaux, extraire TOUTES les lignes."
            }
        ]
    else:
        content = [{
            "type": "text",
            "text": f"Voici le contenu du fichier :\n\n{file_content_text}\n\nTu es expert-comptable. Extrais TOUTES les lignes d'écritures comptables. Retourne UNIQUEMENT un JSON valide sans balises markdown : {{\"ecritures\":[{{\"compte\":\"6411\",\"libelle\":\"Salaires\",\"debit\":1500,\"credit\":0}}]}}. Montants en nombres, 0 si absent, ignorer les totaux."
        }]

    # Appel à l'API Claude
    response = requests.post(
        'https://api.anthropic.com/v1/messages',
        headers={
            'Content-Type': 'application/json',
            'x-api-key': ANTHROPIC_API_KEY,
            'anthropic-version': '2023-06-01'
        },
        json={
            'model': 'claude-sonnet-4-6',
            'max_tokens': 4000,
            'messages': [{'role': 'user', 'content': content}]
        },
        timeout=60
    )

    if not response.ok:
        return jsonify({'error': f'Erreur API Claude: {response.status_code}'}), 500

    result = response.json()
    text = ''.join(item.get('text', '') for item in result.get('content', []))
    clean = text.replace('```json', '').replace('```', '').strip()

    try:
        parsed = json.loads(clean)
    except json.JSONDecodeError:
        return jsonify({'error': 'Impossible de parser la réponse de Claude'}), 500

    # Rapprocher les comptes
    plan = PLANS_COMPTABLES[societe]
    ecritures = []
    for e in parsed.get('ecritures', []):
        compte_pdf = str(e.get('compte', '')).strip()
        rapproche = rapprocher_compte(compte_pdf, plan)
        ecritures.append({
            **e,
            'compte_odoo': rapproche['code'],
            'compte_nom': rapproche['nom'],
            'compte_found': rapproche['found'],
            'compte_approx': rapproche['approx']
        })

    return jsonify({'ecritures': ecritures})

def rapprocher_compte(code, plan):
    c = code.replace(' ', '')
    if c in plan:
        return {'code': c, 'nom': plan[c], 'found': True, 'approx': False}
    padded = c.ljust(8, '0')
    if padded in plan:
        return {'code': padded, 'nom': plan[padded], 'found': True, 'approx': False}
    prefix = c[:4]
    for k, v in plan.items():
        if k.startswith(prefix):
            return {'code': k, 'nom': v, 'found': True, 'approx': True}
    return {'code': padded, 'nom': 'COMPTE INCONNU', 'found': False, 'approx': False}

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
