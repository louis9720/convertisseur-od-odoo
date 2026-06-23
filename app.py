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

    prompt = """Tu es expert-comptable. Ce document PDF peut contenir plusieurs types de pages : bulletins de salaire, récapitulatifs RH, et écritures comptables.

TON TRAVAIL : Trouver UNIQUEMENT les pages dont le titre contient "Écritures comptables" ou "ECRITURES COMPTABLES" et extraire toutes les lignes d'écritures de ces pages seulement.

IGNORE complètement : les bulletins de salaire individuels, les fiches de paie, les récapitulatifs RH, les pages sans numéro de compte comptable.

EXTRAIT UNIQUEMENT les lignes qui ont : un numéro de compte (ex: 6411, 421, 43702...) + un libellé + un montant débit ou crédit.

Retourne UNIQUEMENT un JSON valide sans balises markdown :
{"ecritures":[{"compte":"6411","libelle":"Salaires, appointements","debit":27231.34,"credit":0}]}

Règles : montants en nombres, 0 si absent, ignorer les lignes de totaux, extraire TOUTES les lignes d'écritures comptables trouvées."""

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

    plan = PLANS_COMPTABLES[societe]
    ecritures = []
    for e in parsed.get('ecritures', []):
        r = rapprocher_compte(str(e.get('compte', '')).strip(), plan)
        ecritures.append({
            **e,
            'compte_odoo': r['code'],
            'compte_nom': r['nom'],
            'compte_found': r['found'],
            'compte_approx': r['approx']
        })

    return jsonify({'ecritures': ecritures})

def rapprocher_compte(code, plan):
    c = code.replace(' ', '')
    if c in plan:
        return {'code': c, 'nom': plan[c], 'found': True, 'approx': False}
    padded = c.ljust(8, '0')
    if padded in plan:
        return {'code': padded, 'nom': plan[padded], 'found': True, 'approx': False}
    for k, v in plan.items():
        if k.startswith(c[:4]):
            return {'code': k, 'nom': v, 'found': True, 'approx': True}
    return {'code': padded, 'nom': 'COMPTE INCONNU', 'found': False, 'approx': False}

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
