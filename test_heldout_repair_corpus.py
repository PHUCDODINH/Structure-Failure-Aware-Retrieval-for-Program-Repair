from src.datasets.build_heldout_repair_corpus import (
    candidate_project_keys,
    filter_rows,
    normalize_project_name,
)


def test_normalize_project_name_handles_owner_and_case():
    assert normalize_project_name("pandas-dev/pandas") == "pandas"
    assert normalize_project_name("explosion/spaCy") == "spacy"
    assert normalize_project_name("youtube-dl") == "youtubedl"


def test_candidate_project_keys_extracts_bugsinpy_id_and_repository():
    item = {
        "id": "bugsinpy:black:1:black.py",
        "repository": "psf/black",
        "instance_id": "bugsinpy_black_1",
    }

    assert candidate_project_keys(item) == {"black"}


def test_filter_rows_removes_matching_projects_only():
    rows = [
        {"id": "bugsinpy:black:1:black.py", "repository": "psf/black"},
        {"id": "bugsinpy:pandas:1:pandas/core/frame.py", "repository": "pandas-dev/pandas"},
        {"id": "bugsinpy:keras:1:keras/backend.py", "repository": "keras-team/keras"},
    ]

    kept, summary = filter_rows(rows, ["black", "pandas"])

    assert [row["repository"] for row in kept] == ["keras-team/keras"]
    assert summary["input_count"] == 3
    assert summary["kept_count"] == 1
    assert summary["removed_count"] == 2
    assert summary["removed_by_project"] == {"black": 1, "pandas": 1}
