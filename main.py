"""
OVIA PROSPECT AGENT — Backend Python
Déployer sur Replit : colle ce fichier, ajoute ANTHROPIC_API_KEY dans les Secrets, clique Run.
"""

import os
import json
import anthropic
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)  # Permet les appels depuis l'artifact Claude

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

# ── Outils disponibles pour l'agent ─────────────────────────────────────────
AGENT_TOOLS = [{"type": "web_search_20250305", "name": "web_search"}]

# ── System prompt de l'agent ─────────────────────────────────────────────────
def build_system_prompt():
    now = datetime.now()
    three_months_ago = now - timedelta(days=90)
    date_from = three_months_ago.strftime("%d/%m/%Y")
    date_to = now.strftime("%d/%m/%Y")

    return f"""Tu es un expert en prospection B2B pour une agence d'automatisation digitale française appelée Ovia Services.

Ta mission : trouver de VRAIES entreprises avec de VRAIS signaux de besoin d'automatisation.

CONTRAINTE TEMPORELLE : tous les signaux doivent dater du {date_from} au {date_to} uniquement.

SOURCES à utiliser :
1. Indeed.fr : offres d'emploi révélant des tâches manuelles
2. HelloWork.com : offres PME francophones
3. Google : signaux web, forums métier, avis clients
4. LinkedIn public : posts de dirigeants mentionnant des problèmes process
5. Trustpilot / Google Maps : avis clients mentionnant lenteur ou désorganisation

MÉTHODE :
- Lance plusieurs recherches web ciblées
- Analyse les résultats réels
- Identifie des entreprises concrètes avec preuves datées

RÈGLES :
- Retourner UNIQUEMENT du JSON valide, sans texte avant ou après
- Entreprises RÉELLES uniquement, pas fictives
- Pain points prouvés par une source datée réelle
- Score 1-5 basé sur la force du signal

FORMAT JSON exact :
{{
  "prospects": [
    {{
      "company": "Nom réel",
      "city": "Ville réelle",
      "painPoint": "Problème précis avec preuve",
      "signal": "Source exacte + date",
      "signalUrl": "URL si disponible",
      "contact": "Nom Poste si trouvé ou null",
      "score": 4,
      "evidence": "Citation ou extrait exact de la source"
    }}
  ],
  "summary": "Résumé de la recherche avec sources utilisées",
  "searchesPerformed": ["liste des requêtes effectuées"]
}}"""


# ── Route principale ─────────────────────────────────────────────────────────
@app.route("/prospect", methods=["POST"])
def prospect():
    data = request.json
    dept = data.get("dept", "Haute-Garonne (31)")
    sector = data.get("sector", "Cabinet comptable")
    pain = data.get("pain", "Saisie manuelle répétitive")
    sources = data.get("sources", ["indeed", "google"])
    count = data.get("count", 10)

    source_names = {
        "indeed": "Indeed.fr",
        "hellowork": "HelloWork.com",
        "google": "Google",
        "reddit": "Forums/Reddit",
        "maps": "Google Maps/Trustpilot"
    }
    src_list = ", ".join([source_names.get(s, s) for s in sources])

    user_message = f"""Trouve {count} prospects B2B réels dans :
- Département : {dept}
- Secteur : {sector}
- Pain point recherché : {pain}
- Sources à utiliser : {src_list}

Lance des recherches web réelles sur ces sources. Utilise des requêtes comme :
- site:indeed.fr "{sector}" "{pain.split()[0]}" "{dept.split('(')[0].strip()}"
- "{sector}" "{pain}" {dept.split('(')[0].strip()} 2025 2026
- "{sector}" {dept.split('(')[0].strip()} "cherche" OR "recrute" assistant
- site:trustpilot.com "{sector}" {dept.split('(')[0].strip()} "lent" OR "désorganisé"

Analyse les vrais résultats et retourne uniquement le JSON demandé."""

    try:
        # Appel à l'API Claude avec web_search
        response = client.messages.create(
            model="claude-opus-4-6",  # Opus pour meilleure qualité de recherche
            max_tokens=4000,
            system=build_system_prompt(),
            tools=AGENT_TOOLS,
            messages=[{"role": "user", "content": user_message}]
        )

        # Extraire le texte de la réponse
        raw_text = ""
        for block in response.content:
            if hasattr(block, "text"):
                raw_text += block.text

        # Parser le JSON
        result = parse_json(raw_text)
        return jsonify({"success": True, "data": result, "raw": raw_text[:500]})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/email", methods=["POST"])
def generate_email():
    data = request.json
    prospect = data.get("prospect", {})

    prompt = f"""Rédige un cold email B2B en français pour une agence d'automatisation digitale.

Prospect RÉEL :
- Entreprise : {prospect.get('company')} ({prospect.get('city')})
- Problème détecté : {prospect.get('painPoint')}
- Signal source : {prospect.get('signal')}
- Preuve : {prospect.get('evidence', 'signal web')}
- Contact : {prospect.get('contact') or 'Dirigeant'}

Règles : objet < 8 mots, corps 4-5 phrases, commence par le fait observé spécifiquement, termine par une question ouverte simple. Ton direct et humain, pas de "je me permets".

Retourne UNIQUEMENT ce JSON :
{{"subject":"Objet","body":"Corps complet","ps":"PS court ou null"}}"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = response.content[0].text
        result = parse_json(raw)
        return jsonify({"success": True, "data": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "agent": "Ovia Prospect", "version": "1.0"})


# ── JSON parser robuste ───────────────────────────────────────────────────────
def parse_json(raw):
    if not raw:
        raise ValueError("Réponse vide")
    s = raw.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(s)
    except Exception:
        pass
    a = s.find("{")
    b = s.rfind("}")
    if a != -1 and b > a:
        try:
            return json.loads(s[a:b+1])
        except Exception:
            pass
    raise ValueError(f"JSON invalide dans : {raw[:200]}")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
