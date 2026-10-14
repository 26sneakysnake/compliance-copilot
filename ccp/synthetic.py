"""Seeded generator of FICTIONAL property & casualty insurance claims with gold labels.

Everything is invented: names, e-mails (example.org), phone numbers taken from
the ranges ARCEP reserves for fiction (01 99 00 xx xx, 06 39 98 xx xx), IBANs
that fail the checksum, and the insurer "Assurances du Vexin (fictive)".

Each raw claim contains direct identifiers on purpose, so that the pipeline can
demonstrate anonymisation before the silver layer.
"""
from __future__ import annotations

import json
import random
from datetime import date, timedelta
from pathlib import Path

from .triage import decide

FIRST = ["Camille", "Lucas", "Inès", "Hugo", "Léa", "Nathan", "Chloé", "Yanis", "Manon", "Adam", "Sarah", "Malik"]
LAST = ["Martin", "Bernard", "Moreau", "Laurent", "Garnier", "Fontaine", "Rousseau", "Benali", "Diallo", "Nguyen"]
STREETS = ["rue des Lilas", "avenue de la Gare", "chemin du Moulin", "boulevard de l'Oise", "allée des Tilleuls"]
TOWNS = ["Cergy (fictif)", "Pontoise (fictif)", "Osny (fictif)", "Vauréal (fictif)"]

# category -> (line of business, list of (template, urgency))
TEMPLATES: dict[str, tuple[str, list[tuple[str, str]]]] = {
    "collision": ("auto", [
        ("Accrochage sur le parking du supermarché, pare-choc arrière enfoncé. Pas de blessé.", "normal"),
        ("Collision avec un autre véhicule au rond-point, constat amiable rempli. Aucun blessé.", "normal"),
        ("Accident sur l'A15, le conducteur adverse a été blessé et transporté à l'hôpital.", "high"),
        ("Choc avec un poteau en reculant, rétroviseur et aile avant endommagés.", "low"),
        ("Ma voiture garée a été emboutie par un camion de livraison qui a pris la fuite.", "normal"),
    ]),
    "theft": ("auto", [
        ("Vol du véhicule pendant la nuit devant le domicile, plainte déposée au commissariat.", "normal"),
        ("Vitre brisée et vol d'un ordinateur portable laissé dans la voiture.", "low"),
        ("Au retour de vacances, la porte était forcée et la télévision avait disparu.", "normal"),
        ("Cambriolage du domicile pendant les vacances, bijoux et télévision dérobés, plainte déposée.", "normal"),
    ]),
    "water_damage": ("home", [
        ("Dégât des eaux venant de l'appartement du dessus, plafond de la salle de bain taché.", "low"),
        ("Fuite d'un tuyau sous l'évier, parquet de la cuisine gonflé.", "normal"),
        ("De l'eau coule du plafond du salon depuis ce matin, les murs sont humides.", "normal"),
        ("Inondation du sous-sol après un orage, la chaudière est hors service et le logement est inhabitable.", "high"),
    ]),
    "fire": ("home", [
        ("Départ de feu dans la cuisine, la hotte et les placards ont brûlé, pas de blessé.", "normal"),
        ("Incendie du garage, la maison est inhabitable, la famille est relogée chez des proches.", "high"),
    ]),
    "liability": ("liability", [
        ("Mon fils a cassé la vitre du voisin avec un ballon, le voisin demande réparation.", "low"),
        ("Un client a glissé dans ma boutique et s'est blessé au poignet, il réclame une indemnisation.", "high"),
        ("Notre chien a mordu un passant qui a dû consulter un médecin.", "high"),
        ("Un pot de fleurs tombé de mon balcon a abîmé la voiture garée en bas.", "low"),
    ]),
    "travel": ("travel", [
        ("Annulation du voyage à Lisbonne pour cause de maladie, certificat médical joint.", "normal"),
        ("Bagage perdu par la compagnie aérienne lors du vol retour.", "low"),
        ("Mon vol pour Montréal a été annulé et j'ai dû payer deux nuits d'hôtel.", "low"),
        ("Hospitalisation à l'étranger pendant le séjour, rapatriement demandé en urgence.", "high"),
    ]),
}

CATEGORIES = tuple(TEMPLATES)
URGENCIES = ("low", "normal", "high")
LINES = ("auto", "home", "liability", "travel")
INSURER = "Assurances du Vexin (fictive)"


def _phone(rng: random.Random) -> str:
    if rng.random() < 0.5:
        return f"01 99 00 {rng.randint(10, 99)} {rng.randint(10, 99)}"
    return f"06 39 98 {rng.randint(10, 99)} {rng.randint(10, 99)}"


def _fake_iban(rng: random.Random) -> str:
    # "00" check digits are never valid in ISO 13616, so this cannot be a real account.
    digits = "".join(str(rng.randint(0, 9)) for _ in range(23))
    groups = [digits[i : i + 4] for i in range(0, 23, 4)]
    return "FR00 " + " ".join(groups)


def generate(n: int = 300, seed: int = 7, start: date = date(2026, 1, 1)) -> list[dict]:
    rng = random.Random(seed)
    claims = []
    for i in range(n):
        category = rng.choice(CATEGORIES)
        lob, templates = TEMPLATES[category]
        template, urgency = rng.choice(templates)
        first, last = rng.choice(FIRST), rng.choice(LAST)
        incident = start + timedelta(days=rng.randint(0, 250))
        # most claims are reported within days; a few are late (fraud signal)
        delay = rng.choice([0, 1, 2, 3, 5, 7, 10]) if rng.random() < 0.88 else rng.randint(31, 120)
        policy_age = rng.randint(200, 3000) if rng.random() < 0.9 else rng.randint(1, 25)
        amount = round(rng.lognormvariate(7.2, 1.0), 2)
        if rng.random() < 0.06:
            amount = round(rng.uniform(15000, 60000), 2)
        email = f"{first}.{last}{rng.randint(1, 99)}@example.org".lower()
        phone = _phone(rng)

        style = rng.random()
        if style < 0.35:
            description = f"Assuré : {first} {last}. {template} Joignable au {phone} ou {email}."
        elif style < 0.6:
            description = f"{template} Contact : {phone}. Adresse : {rng.randint(1, 80)} {rng.choice(STREETS)}, {rng.choice(TOWNS)}."
        elif style < 0.8:
            description = f"Bonjour, je suis Mme {last}. {template} Merci de me rappeler."
        else:
            description = template

        claim = {
            "claim_id": f"CLM-2026-{i + 1:06d}",
            "policy_id": f"POL-{rng.randint(100000, 999999)}",
            "insurer": INSURER,
            "customer_name": f"{first} {last}",
            "customer_email": email,
            "customer_phone": phone,
            "iban": _fake_iban(rng),
            "line_of_business": lob,
            "channel": rng.choice(["web", "phone", "agent"]),
            "policy_start_date": (incident - timedelta(days=policy_age)).isoformat(),
            "incident_date": incident.isoformat(),
            "report_date": (incident + timedelta(days=delay)).isoformat(),
            "amount_claimed_eur": amount,
            "description": description,
            "is_synthetic": True,
            "gold_category": category,
            "gold_urgency": urgency,
        }
        claim["gold_route"] = decide(claim, category, urgency).route
        claims.append(claim)
    return claims


def write_jsonl(rows: list[dict], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    return path


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
