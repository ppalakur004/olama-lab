from promptlab.corpus import load_cases, validate_corpus


def test_fixed_corpus_has_twelve_paired_cases_per_task() -> None:
    assert validate_corpus() == {
        "triage": 12,
        "summarization": 12,
        "extraction": 12,
    }

    all_ids: list[str] = []
    for task in ("triage", "summarization", "extraction"):
        pairs = load_cases(task)
        assert len(pairs) == 12
        assert all(case.id == gold.id for case, gold in pairs)
        assert all(case.task == task and gold.task == task for case, gold in pairs)
        all_ids.extend(case.id for case, _gold in pairs)

    assert len(all_ids) == len(set(all_ids))


def test_extraction_version_groups_supply_rule_inputs() -> None:
    grouped = [
        gold
        for _case, gold in load_cases("extraction")
        if gold.version_group is not None
    ]

    assert grouped
    assert all(gold.as_of is not None for gold in grouped)
    assert any(gold.expected_current_case_id is not None for gold in grouped)
