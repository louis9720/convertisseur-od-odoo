import os
import json
import requests
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')

with open('toutes_societes.json', 'r', encoding='utf-8') as f:
    PLANS_COMPTABLES = json.load(f)

@app.route('/')
def index():
    return send_file('index.html')

@app.route('/api/societes', methods=['GET'])
def get_societes():
    return jsonify({k: len(v) for k, v in PLANS_COMPTABLES.items()})

@app.route('/api/convertir', methods=['POST'])
def convertir():
    if not ANTHROPIC_API_KEY:
        return jsonify({'error': 'Clé API non configurée'}), 500

    data = request.json
    societe = data.get('societe')
    file_b64 = data.get('file_b64')
    file_type = data.get('file_type', 'pdf')
    file_content_text = data.get('file_content_text', '')

    if not societe or societe not in PLANS_COMPTABLES:
        return jsonify({'error': 'Société invalide'}), 400

    plan = PLANS_COMPTABLES[societe]
    plan_str = json.dumps(plan, ensure_ascii=False)

    prompt = f"""Tu es expert-comptable. Ce document PDF peut contenir plusieurs types de pages : bulletins de salaire, récapitulatifs RH, et écritures comptables.

TON TRAVAIL EN 2 ÉTAPES :

ÉTAPE 1 - EXTRACTION : Trouver UNIQUEMENT les pages dont le titre contient "Écritures comptables" ou "ECRITURES COMPTABLES" et extraire toutes les lignes d'écritures de ces pages. Ignore complètement les bulletins de salaire, fiches de paie, récapitulatifs RH.

ÉTAPE 2 - RAPPROCHEMENT : Pour chaque ligne extraite, trouver le compte Odoo exact dans le plan comptable ci-dessous. 
- Si le numéro de compte correspond exactement → utilise-le
- Si le numéro n'existe pas exactement → utilise le LIBELLÉ pour trouver le bon compte (ex: "ADEP" → cherche "ADEP" dans le plan, "AG2R" → cherche "AG2R", "Ircom" → cherche "IRCOM")
- Utilise toujours le numéro de compte Odoo exact (8 chiffres) et non celui du PDF

PLAN COMPTABLE ODOO :
{plan_str}

Retourne UNIQUEMENT un JSON valide sans balises markdown :
{{"ecritures":[{{"compte_odoo":"43734000","compte_nom":"ADEP","libelle":"ADEP SANTE (3840/01/02)","debit":0,"credit":569.76}}]}}

Champs obligatoires : compte_odoo (numéro exact du plan), compte_nom (nom exact du plan), libelle (libellé original du document), debit (nombre), credit (nombre).
Règles : montants en nombres, 0 si absent, ignorer les lignes de totaux."""

    if file_type == 'pdf':
        content = [
            {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": file_b64}},
            {"type": "text", "text": prompt}
        ]
    else:
        content = [{"type": "text", "text": f"Contenu du fichier :\n\n{file_content_text}\n\n{prompt}"}]

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
    except:
        return jsonify({'error': 'Impossible de parser la reponse'}), 500

    ecritures = []
    for e in parsed.get('ecritures', []):
        compte_odoo = str(e.get('compte_odoo', '')).strip()
        compte_nom = e.get('compte_nom', '')
        found = compte_odoo in plan
        ecritures.append({
            'compte_odoo': compte_odoo,
            'compte_nom': compte_nom,
            'libelle': e.get('libelle', ''),
            'debit': e.get('debit', 0),
            'credit': e.get('credit', 0),
            'compte_found': found,
            'compte_approx': False
        })

    return jsonify({'ecritures': ecritures})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
