from hermes.inference.verification import extract_claims, verify_claims


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