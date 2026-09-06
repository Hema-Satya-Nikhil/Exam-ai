"""Regression tests for Phase 1 model-paper extraction into the new exam model.

Only explicit markers create ChoiceGroups - nothing is ever fabricated.
"""
from __future__ import annotations

from app.services.model_paper_extractor import ModelPaperExtractor


SAMPLE_MID = """Question Paper - Operating Systems
PART B (30 Marks, 90 Minutes)

Q1. (5 marks) BTL3 CO1
(a) (5) Explain process scheduling.
OR
(b) (5) Describe round robin.

Q2. (5) BTL4 CO2
(a) (5) Analyze deadlocks.
OR
(b) (5) Evaluate avoidance.

Q3. (5) BTL2 CO3
(a) (5) List memory management types.

Q5. (5) BTL5 CO4
(a) (5) Assess disk scheduling.
"""

SAMPLE_NO_OR = """Q4. (5 marks) BTL3 CO1
(a) (5) Explain paging.
(b) (5) Describe segmentation.
"""


def test_extracts_groups_parts_marks():
    r = ModelPaperExtractor().extract(SAMPLE_MID)
    assert [g.group_number for g in r.groups] == [1, 2, 3, 5]
    g1 = r.groups[0]
    assert [(p.part_label, p.marks) for p in g1.parts] == [("a", 5), ("b", 5)]
    assert r.total_printed_marks == 30


def test_extracts_btl_and_co():
    r = ModelPaperExtractor().extract(SAMPLE_MID)
    assert r.groups[0].btl == ["L3"] and r.groups[0].co == ["1"]
    assert r.groups[1].btl == ["L4"] and r.groups[1].co == ["2"]
    assert r.groups[3].btl == ["L5"] and r.groups[3].co == ["4"]


def test_explicit_or_creates_part_level_choice():
    r = ModelPaperExtractor().extract(SAMPLE_MID)
    ids = {c.choice_id for c in r.choices}
    # Q1 and Q2 had explicit "OR" between their parts
    assert "g1_or" in ids and "g2_or" in ids
    g1 = next(c for c in r.choices if c.choice_id == "g1_or")
    assert g1.member_keys == ["1a", "1b"]
    assert g1.select_count == 1


def test_no_or_means_no_fabricated_choice():
    r = ModelPaperExtractor().extract(SAMPLE_NO_OR)
    # (a)+(b) present but NO explicit OR line -> no choice must be invented
    assert r.choices == []
    assert len(r.groups[0].parts) == 2


def test_group_without_or_has_no_choice():
    r = ModelPaperExtractor().extract(SAMPLE_MID)
    ids = {c.choice_id for c in r.choices}
    # Q3/Q5 had a single part and no OR marker
    assert "g3_or" not in ids and "g5_or" not in ids


def test_extraction_requires_faculty_confirmation():
    r = ModelPaperExtractor().extract(SAMPLE_MID)
    # every group was inferred from text -> faculty must confirm
    assert r.confidence == "inferred"
    assert r.requires_confirmation() is True


def test_to_main_config_materialises_confirmed_choices():
    r = ModelPaperExtractor().extract(SAMPLE_MID)
    cfg = r.to_main_config([1, 2])
    assert len(cfg.groups) == 4
    assert cfg.source_mode == "model"
    keys = {(cg.id, tuple(sorted(m.key for m in cg.members)))
            for cg in cfg.choice_groups}
    assert ("g1_or", ("1a", "1b")) in keys
    assert ("g2_or", ("2a", "2b")) in keys
    # every materialised member carries marks + bloom; unit/topic stay
    # unknown (0/"") because a model paper does not carry syllabus mapping -
    # those are filled by faculty during confirmation.
    for cg in cfg.choice_groups:
        for m in cg.members:
            assert m.marks > 0
            assert m.bloom_level in ("L2", "L3", "L4", "L5", "L6")
            assert m.unit == 0 and m.topic == ""