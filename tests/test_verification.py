from hermes.inference.verification import classify_claim, extract_claims, verify_claims


def test_claims_are_extracted_from_bullets_not_headings():
    claims = extract_claims("# Experience\n\n- Built Python services handling 2M requests per day")
    assert claims == ["Built Python services handling 2M requests per day"]


def test_claims_receive_evidence_references_or_are_marked_unsupported():
    references = verify_claims(
        "- Built Python services handling 2M requests per day\n"
        "- Led an unrelated quantum computing laboratory research team",
        [("b1", "Built Python services handling 2M requests per day")],
    )
    assert references[0].supported is True
    assert references[0].evidence_id == "b1"
    assert references[1].supported is False


def test_metrics_and_dates_require_exact_evidence_values():
    assert classify_claim("Reduced latency by 72% in 2025") == "METRIC"
    references = verify_claims(
        "- Built FastAPI services with 72% lower latency in 2025",
        [("b1", "Built FastAPI services with 42% lower latency in 2024")],
    )
    assert references[0].supported is False
    assert references[0].claim_type == "METRIC"


def test_typed_skill_claim_requires_a_known_candidate_skill():
    references = verify_claims(
        "- Skills: Python and Rust",
        [("b1", "Skills: Python and Rust")],
        known_entities={"SKILL": ["Python"]},
    )
    assert references[0].claim_type == "SKILL"
    assert references[0].supported is True

    unsupported = verify_claims(
        "- Skills: Rust",
        [("b1", "Skills: Rust")],
        known_entities={"SKILL": ["Python"]},
    )
    assert unsupported[0].supported is False