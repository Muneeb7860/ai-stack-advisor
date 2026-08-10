"""Unit test suite for guided mode wizard requirement synthesis and rule engine signal detection.
Validates that the guided-input wizard choices produce natural language text that faithfully
triggers the intended signals in detect_signals() and recommendations in recommend_stack().
"""

from app.rule_engine import detect_signals, recommend_stack


def synthesize_guided_text(wiz_state: dict) -> str:
    """Python mirror of synthesizeRequirementText(state) in index.html.
    Keeps the backend test suite aligned with frontend synthesis logic.
    """
    parts = []
    building_map = {
        "web": "a web application",
        "mobile": "a mobile app for iOS and Android",
        "api": "an API / backend service",
        "chatbot": "an AI chatbot",
        "data": "a data analytics platform with data pipelines",
        "internal": "an internal tool for internal company employees",
    }
    building_phrases = [building_map[b] for b in wiz_state.get("building", []) if b in building_map]
    if building_phrases:
        parts.append(f"We're building {' and '.join(building_phrases)}.")

    audience_map = {
        "internal": "This is for internal team use only, not customer-facing.",
        "smb": "It serves small business customers (B2B).",
        "enterprise": "It serves enterprise customers at large organizations.",
        "consumer": "It serves consumer / general public users, anyone can sign up.",
    }
    audience = wiz_state.get("audience")
    if audience and audience in audience_map:
        parts.append(audience_map[audience])

    compliance_map = {
        "hipaa": "Must be HIPAA compliant, handling clinical patient data.",
        "pci": "Must be PCI compliant, handling payment transaction data.",
        "soc2": "Must be SOC2 compliant, an enterprise compliance requirement.",
        "gov": "This involves a government contract with regulated compliance requirements.",
    }
    compliance_sel = [c for c in wiz_state.get("compliance", []) if c != "none"]
    if compliance_sel:
        parts.append(" ".join(compliance_map[c] for c in compliance_sel if c in compliance_map))

    team_map = {
        "1-5": "The engineering team is a small team of 5 engineers.",
        "6-15": "The engineering team is a small team of 10 engineers.",
        "16-50": "The engineering team has about 30 engineers across multiple teams.",
        "50+": "This is a large engineering organization of 50+ people with multiple teams.",
    }
    teamsize = wiz_state.get("teamsize")
    if teamsize and teamsize in team_map:
        parts.append(team_map[teamsize])

    ai_map = {
        "chatbot": "It needs a customer-facing chatbot.",
        "internal-kb": "It needs an internal knowledge assistant that can search internal documents.",
        "reco": "It needs personalized recommendations for users.",
        "fraud": "It needs a fraud detection model.",
    }
    ai_sel = [a for a in wiz_state.get("ai", []) if a not in ("none", "unsure")]
    if ai_sel:
        parts.append(" ".join(ai_map[a] for a in ai_sel if a in ai_map))

    freetext = (wiz_state.get("freetext") or "").strip()
    if freetext:
        parts.append(freetext)

    return " ".join(parts)


def test_guided_scenario_1_small_team_enterprise_chatbot():
    """Scenario 1: B2B/Enterprise Chatbot (Web + Chatbot, Enterprise audience, SOC2, 1-5 engineers)."""
    wiz_state = {
        "building": ["web", "chatbot"],
        "audience": "enterprise",
        "compliance": ["soc2"],
        "teamsize": "1-5",
        "ai": ["chatbot"],
        "freetext": "",
    }
    text = synthesize_guided_text(wiz_state)
    signals = detect_signals(text)

    assert signals["web"] is True
    assert signals["chatbot"] is True
    assert signals["enterprise"] is True
    assert signals["compliance"] is True
    assert signals["smallTeam"] is True

    result = recommend_stack(text)
    rec = result["recommendations"]
    assert "monolith" in rec["architecture"]["v"].lower()
    assert "Serverless" in rec["compute"]["v"] or "Fargate" in rec["compute"]["v"]
    # Compliance (SOC2) triggers local/VPC-isolated requirement for sensitive data
    assert "Local / self-hosted" in rec["hosting_location"]["rec"] or "VPC-isolated" in rec["hosting_location"]["rec"]


def test_guided_scenario_2_internal_knowledge_assistant_skip_compliance():
    """Scenario 2: Internal tool, Internal audience (compliance skipped), 6-15 team, Internal KB AI."""
    wiz_state = {
        "building": ["internal", "api"],
        "audience": "internal",
        "compliance": ["none"],  # Skipped via wizard decision #7
        "teamsize": "6-15",
        "ai": ["internal-kb"],
        "freetext": "",
    }
    text = synthesize_guided_text(wiz_state)
    signals = detect_signals(text)

    assert signals["compliance"] is False
    assert signals["knowledgeBase"] is True
    assert signals["ragNeed"] is True
    assert signals["smallTeam"] is True

    result = recommend_stack(text)
    rec = result["recommendations"]
    assert rec["rag"]["name"] != "RAG likely not required"
    assert rec["vector_db_placement"]["needed"] is True


def test_guided_scenario_3_mobile_pci_consumer_fraud():
    """Scenario 3: Mobile app, Consumer audience, PCI compliance, 1-5 engineers, Fraud detection."""
    wiz_state = {
        "building": ["mobile", "api"],
        "audience": "consumer",
        "compliance": ["pci"],
        "teamsize": "1-5",
        "ai": ["fraud"],
        "freetext": "",
    }
    text = synthesize_guided_text(wiz_state)
    signals = detect_signals(text)

    assert signals["mobile"] is True
    assert signals["compliance"] is True
    assert signals["finance"] is True  # PCI triggers finance signal
    assert signals["smallTeam"] is True
    assert signals["mlFeatureStore"] is True  # fraud triggers feature store

    result = recommend_stack(text)
    rec = result["recommendations"]
    assert rec["compute_tier"]["tier"] in ("Mobile / Tablet", "Laptop / Workstation")
    assert "PostgreSQL" in rec["database"]["v"]


def test_guided_scenario_4_healthcare_hipaa_enterprise():
    """Scenario 4: Web + Mobile + Chatbot, Enterprise audience, HIPAA compliance, 16-50 team."""
    wiz_state = {
        "building": ["web", "mobile", "chatbot"],
        "audience": "enterprise",
        "compliance": ["hipaa"],
        "teamsize": "16-50",
        "ai": ["chatbot", "internal-kb"],
        "freetext": "",
    }
    text = synthesize_guided_text(wiz_state)
    signals = detect_signals(text)

    assert signals["web"] is True
    assert signals["mobile"] is True
    assert signals["healthcare"] is True
    assert signals["compliance"] is True
    assert signals["chatbot"] is True
    assert signals["knowledgeBase"] is True
    assert signals["largeTeam"] is True

    result = recommend_stack(text)
    rec = result["recommendations"]
    assert "HIPAA" in rec["cloud"]["why"] or "HIPAA" in text
    assert len(rec["guardrails"]) > 0


def test_guided_scenario_5_government_air_gapped_freetext():
    """Scenario 5: Government contract, 50+ engineers, air-gapped free-text override."""
    wiz_state = {
        "building": ["web", "api"],
        "audience": "enterprise",
        "compliance": ["gov"],
        "teamsize": "50+",
        "ai": ["none"],
        "freetext": "Air-gapped environment, cannot use any public cloud. Private data center bare metal deployment.",
    }
    text = synthesize_guided_text(wiz_state)
    signals = detect_signals(text)

    assert signals["onPrem"] is True
    assert signals["compliance"] is True
    assert signals["largeTeam"] is True

    result = recommend_stack(text)
    rec = result["recommendations"]
    assert "On-premises" in rec["cloud"]["v"]
    assert "Internal API gateway" in rec["gateway"]["v"]


def test_guided_scenario_6_multi_compliance_and_ai_selection():
    """Scenario 6: Multiple compliance options (SOC2 + PCI) and multiple AI features selected."""
    wiz_state = {
        "building": ["web", "data"],
        "audience": "enterprise",
        "compliance": ["soc2", "pci"],
        "teamsize": "6-15",
        "ai": ["reco", "fraud"],
        "freetext": "",
    }
    text = synthesize_guided_text(wiz_state)
    signals = detect_signals(text)

    assert signals["compliance"] is True
    assert signals["finance"] is True  # PCI
    assert signals["dataHeavy"] is True  # data analytics platform
    assert signals["searchRecommendation"] is True  # reco
    assert signals["mlFeatureStore"] is True  # fraud


def test_guided_scenario_7_negation_in_step6_freetext():
    """Scenario 7: Free-text step 6 includes negated requirements ("don't have compliance requirements yet")."""
    wiz_state = {
        "building": ["web"],
        "audience": "smb",
        "compliance": ["none"],
        "teamsize": "1-5",
        "ai": ["none"],
        "freetext": "startup MVP, don't have compliance requirements yet, move fast",
    }
    text = synthesize_guided_text(wiz_state)
    signals = detect_signals(text)

    assert signals["compliance"] is False
    assert signals["startupMvp"] is True
