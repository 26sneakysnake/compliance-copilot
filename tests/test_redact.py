from ccp.redact import contains_pii, pseudonymise, redact


def test_french_identifiers_are_removed():
    text = ("Assuré : Camille Martin. Joignable au 06 39 98 12 34 ou camille.martin@example.org. "
            "IBAN FR00 1234 5678 9012 3456 7890 123. Adresse : 12 rue des Lilas, Cergy.")
    out = redact(text)
    for leaked in ("Camille", "Martin", "06 39 98", "@example.org", "FR00 1234", "rue des Lilas"):
        assert leaked not in out
    for tag in ("[NAME]", "[PHONE]", "[EMAIL]", "[IBAN]", "[ADDRESS]"):
        assert tag in out


def test_title_names_and_international_phone():
    out = redact("Bonjour, je suis Mme Benali, appelez le +33 1 99 00 45 67.")
    assert "Benali" not in out and "+33" not in out


def test_clinical_text_is_kept():
    text = "Dégât des eaux, plafond taché, pas de blessé."
    assert redact(text) == text and not contains_pii(text)


def test_pseudonymise_is_stable_salted_and_normalised():
    a = pseudonymise("Camille.Martin@example.org", salt="s1")
    assert a == pseudonymise(" camille.martin@example.org ", salt="s1")
    assert a != pseudonymise("camille.martin@example.org", salt="s2")
    assert a.startswith("psd_") and len(a) == 20
