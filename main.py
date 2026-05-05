import os
import json
from datetime import datetime, timedelta

import anthropic
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)


def get_client():
    return anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))


def get_date_range():
    now = datetime.now()
    from_date = now - timedelta(days=90)
    return {
        "from": from_date.strftime("%d/%m/%Y"),
        "to": now.strftime("%d/%m/%Y")
    }


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
    raise ValueError("JSON invalide: " + raw[:200])


def build_system_prompt():
    dates = get_date_range()
    return f"""Tu es un expert en prospection B2B pour Ovia Services, une agence d'automatisation digitale française.

Ta mission : trouver de VRAIES entreprises avec de VRAIS signaux de besoin d'automatisation.

CONTRAINTE TEMPORELLE STRICTE : tous les signaux doivent dater du {dates['from']} au {dates['to']} uniquement.

SOURCES à utiliser :
- Indeed.fr : offres d'emploi révélant des tâches manuelles
- HelloWork.com : offres PME francophones
- Google : forums métier, actualités, avis clients
- LinkedIn public : posts de dirigeants
- Trustpilot / Google Maps : avis clients

RÈGLES ABSOLUES :
- Retourner UNIQUEMENT du JSON valide, sans texte avant ou après
- Entreprises RÉELLES uniquement
- Pain points prouvés par une source datée réelle
- Score 1 à 5 selon la force du signal

FORMAT JSON exact à retourner :
{{
  "prospects": [
    {{
      "company": "Nom réel",
      "city": "Ville réelle",
      "painPoint": "Problème précis avec preuve",
      "signal": "Source exacte + date",
      "signalUrl": "URL si disponible sinon null",
      "contact": "Prénom Nom, Poste ou null",
      "score": 4,
      "evidence": "Citation ou extrait exact de la source"
    }}
  ],
  "summary": "Résumé en 1 phrase avec sources utilisées"
}}"""


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "agent": "Ovia Prospect", "version": "1.0"})


@app.route("/prospect", methods=["POST"])
def prospect():
    data = request.json or {}
    dept = data.get("dept", "Haute-Garonne (31)")
    sector = data.get("sector", "Cabinet comptable")
    pain = data.get("pain", "Saisie manuelle répétitive")
    sources = data.get("sources", ["indeed", "google"])
    count = data.get("count", 10)

    source_map = {
        "indeed": "Indeed.fr",
        "hellowork": "HelloWork.com",
        "google": "Google",
        "reddit": "Forums/Reddit",
        "maps": "Google Maps/Trustpilot"
    }
    src_list = ", ".join([source_map.get(s, s) for s in sources])
    dates = get_date_range()
    dept_name = dept.split("(")[0].strip()

    user_message = f"""Trouve {count} prospects B2B réels :
- Département : {dept}
- Secteur : {sector}
- Pain point : {pain}
- Sources : {src_list}

Utilise ces requêtes web :
- site:indeed.fr "{sector}" "{dept_name}"
- "{sector}" "{pain}" {dept_name} 2026
- "{sector}" {dept_name} "recrute" OR "cherche" assistant
- site:trustpilot.com "{sector}" {dept_name}

Signaux datés entre {dates['from']} et {dates['to']} uniquement.
Retourne uniquement le JSON demandé."""

    try:
        response = get_client().messages.create(
            model="claude-opus-4-6",
            max_tokens=4000,
            system=build_system_prompt(),
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": user_message}]
        )

        raw_text = ""
        for block in response.content:
            if hasattr(block, "text"):
                raw_text += block.text

        result = parse_json(raw_text)
        return jsonify({"success": True, "data": result})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/email", methods=["POST"])
def generate_email():
    data = request.json or {}
    p = data.get("prospect", {})

    prompt = f"""Rédige un cold email B2B en français pour une agence d'automatisation digitale.

Prospect :
- Entreprise : {p.get('company')} ({p.get('city')})
- Problème : {p.get('painPoint')}
- Signal : {p.get('signal')}
- Preuve : {p.get('evidence', 'signal web')}
- Contact : {p.get('contact') or 'Dirigeant'}

Règles : objet moins de 8 mots, corps 4 à 5 phrases, commence par le problème observé, termine par une question simple. Ton direct et humain.

Retourne UNIQUEMENT ce JSON :
{{"subject": "Objet", "body": "Corps complet", "ps": "PS court ou null"}}"""

    try:
        response = get_client().messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = response.content[0].text
        result = parse_json(raw)
        return jsonify({"success": True, "data": result})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
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
