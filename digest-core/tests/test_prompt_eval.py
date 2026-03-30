"""Tests for digest_core.eval — prompt quality evaluation tooling (COMMON-12)."""

import json
import pytest

from digest_core.eval.prompt_eval import (
    evaluate_digest,
    evaluate_digest_file,
    EvalReport,
    ISSUE_ERROR,
    ISSUE_WARN,
    ISSUE_INFO,
    SECTION_ACTIONS,
    SECTION_URGENT,
    SECTION_FYI,
)
from digest_core.eval.changelog import (
    parse_prompt_changelog,
    get_current_version,
    format_changelog,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

GOOD_DIGEST = {
    "schema_version": "1.0",
    "prompt_version": "extract_actions.v1",
    "digest_date": "2026-03-31",
    "trace_id": "test-trace-123",
    "sections": [
        {
            "title": SECTION_ACTIONS,
            "items": [
                {
                    "title": "Согласовать NDA с партнером Orion",
                    "due": "2026-04-01",
                    "evidence_id": "ev-001",
                    "confidence": 0.92,
                    "source_ref": {"type": "email", "msg_id": "msg-001"},
                }
            ],
        },
        {
            "title": SECTION_FYI,
            "items": [
                {
                    "title": "Перенос stand-up на 11:00",
                    "due": None,
                    "evidence_id": "ev-002",
                    "confidence": 0.76,
                    "source_ref": {"type": "email", "msg_id": "msg-002"},
                }
            ],
        },
    ],
}


# ── EvalReport: perfect digest ────────────────────────────────────────────────

class TestEvaluateDigestGoodPath:
    def test_perfect_digest_score_100(self):
        report = evaluate_digest(GOOD_DIGEST)
        assert report.score == 100

    def test_no_issues_on_perfect_digest(self):
        report = evaluate_digest(GOOD_DIGEST)
        assert report.issues == []

    def test_section_counts(self):
        report = evaluate_digest(GOOD_DIGEST)
        assert report.section_counts[SECTION_ACTIONS] == 1
        assert report.section_counts[SECTION_FYI] == 1

    def test_total_items(self):
        report = evaluate_digest(GOOD_DIGEST)
        assert report.total_items == 2

    def test_prompt_version_parsed(self):
        report = evaluate_digest(GOOD_DIGEST)
        assert report.prompt_version == "extract_actions.v1"

    def test_digest_date_parsed(self):
        report = evaluate_digest(GOOD_DIGEST)
        assert report.digest_date == "2026-03-31"

    def test_grade_A_on_100(self):
        report = evaluate_digest(GOOD_DIGEST)
        assert report._grade() == "A"


# ── Evidence ID validation ────────────────────────────────────────────────────

class TestEvidenceIdValidation:
    def test_valid_evidence_ids_pass(self):
        report = evaluate_digest(GOOD_DIGEST, evidence_ids={"ev-001", "ev-002"})
        assert not any(i.category == "evidence_id" for i in report.issues)

    def test_invalid_evidence_id_raises_error(self):
        report = evaluate_digest(GOOD_DIGEST, evidence_ids={"ev-999"})
        errors = [i for i in report.issues if i.category == "evidence_id"]
        assert len(errors) == 2  # ev-001 and ev-002 both invalid

    def test_invalid_evidence_id_deducts_score(self):
        report = evaluate_digest(GOOD_DIGEST, evidence_ids={"ev-999"})
        assert report.score < 100

    def test_missing_evidence_id_in_item(self):
        digest = {
            **GOOD_DIGEST,
            "sections": [
                {
                    "title": SECTION_ACTIONS,
                    "items": [
                        {
                            "title": "Do something",
                            "due": None,
                            "confidence": 0.9,
                            "source_ref": {"type": "email", "msg_id": "msg-x"},
                            # evidence_id intentionally missing
                        }
                    ],
                }
            ],
        }
        report = evaluate_digest(digest)
        errors = [i for i in report.issues if i.category == "evidence_id"]
        assert len(errors) == 1
        assert errors[0].severity == ISSUE_ERROR

    def test_evidence_ids_checked_flag(self):
        report_no_check = evaluate_digest(GOOD_DIGEST)
        assert not report_no_check.evidence_ids_checked

        report_checked = evaluate_digest(GOOD_DIGEST, evidence_ids={"ev-001", "ev-002"})
        assert report_checked.evidence_ids_checked


# ── Confidence calibration ────────────────────────────────────────────────────

class TestConfidenceCalibration:
    def test_confidence_below_0_5_is_warn(self):
        digest = {
            **GOOD_DIGEST,
            "sections": [
                {
                    "title": SECTION_FYI,
                    "items": [
                        {
                            "title": "Some FYI item",
                            "due": None,
                            "evidence_id": "ev-003",
                            "confidence": 0.40,
                            "source_ref": {"type": "email", "msg_id": "msg-003"},
                        }
                    ],
                }
            ],
        }
        report = evaluate_digest(digest)
        warns = [i for i in report.issues if i.category == "confidence"]
        assert any(i.severity == ISSUE_WARN for i in warns)

    def test_confidence_out_of_range_is_error(self):
        digest = {
            **GOOD_DIGEST,
            "sections": [
                {
                    "title": SECTION_ACTIONS,
                    "items": [
                        {
                            "title": "Bad confidence item",
                            "due": None,
                            "evidence_id": "ev-001",
                            "confidence": 1.5,
                            "source_ref": {"type": "email", "msg_id": "msg-001"},
                        }
                    ],
                }
            ],
        }
        report = evaluate_digest(digest)
        errors = [i for i in report.issues if i.category == "confidence" and i.severity == ISSUE_ERROR]
        assert len(errors) == 1

    def test_actions_below_0_7_is_warn(self):
        """'Мои действия' items with confidence < 0.7 should warn (potential false positive)."""
        digest = {
            **GOOD_DIGEST,
            "sections": [
                {
                    "title": SECTION_ACTIONS,
                    "items": [
                        {
                            "title": "Weak action item",
                            "due": None,
                            "evidence_id": "ev-001",
                            "confidence": 0.55,
                            "source_ref": {"type": "email", "msg_id": "msg-001"},
                        }
                    ],
                }
            ],
        }
        report = evaluate_digest(digest)
        warns = [i for i in report.issues if i.category == "confidence" and i.severity == ISSUE_WARN]
        assert len(warns) == 1
        assert "false positive" in warns[0].message

    def test_missing_confidence_is_error(self):
        digest = {
            **GOOD_DIGEST,
            "sections": [
                {
                    "title": SECTION_FYI,
                    "items": [
                        {
                            "title": "No confidence",
                            "due": None,
                            "evidence_id": "ev-001",
                            "source_ref": {"type": "email", "msg_id": "msg-001"},
                            # confidence missing
                        }
                    ],
                }
            ],
        }
        report = evaluate_digest(digest)
        errors = [i for i in report.issues if i.category == "confidence" and i.severity == ISSUE_ERROR]
        assert len(errors) == 1


# ── source_ref checks ─────────────────────────────────────────────────────────

class TestSourceRef:
    def test_missing_source_ref_is_error(self):
        digest = {
            **GOOD_DIGEST,
            "sections": [
                {
                    "title": SECTION_FYI,
                    "items": [
                        {
                            "title": "Item without source_ref",
                            "due": None,
                            "evidence_id": "ev-001",
                            "confidence": 0.8,
                            # source_ref missing
                        }
                    ],
                }
            ],
        }
        report = evaluate_digest(digest)
        errors = [i for i in report.issues if i.category == "source_ref"]
        assert len(errors) == 1
        assert errors[0].severity == ISSUE_ERROR

    def test_source_ref_missing_type_is_error(self):
        digest = {
            **GOOD_DIGEST,
            "sections": [
                {
                    "title": SECTION_FYI,
                    "items": [
                        {
                            "title": "Item with incomplete source_ref",
                            "due": None,
                            "evidence_id": "ev-001",
                            "confidence": 0.8,
                            "source_ref": {"msg_id": "msg-001"},  # no type
                        }
                    ],
                }
            ],
        }
        report = evaluate_digest(digest)
        errors = [i for i in report.issues if i.category == "source_ref"]
        assert len(errors) == 1
        assert errors[0].severity == ISSUE_ERROR


# ── Section assignment rules ──────────────────────────────────────────────────

class TestSectionAssignment:
    def test_empty_section_is_warn(self):
        digest = {
            **GOOD_DIGEST,
            "sections": [
                {"title": SECTION_ACTIONS, "items": []},
            ],
        }
        report = evaluate_digest(digest)
        warns = [i for i in report.issues if i.category == "section_assignment"]
        assert any("Empty section" in i.message for i in warns)

    def test_unknown_section_is_warn(self):
        digest = {
            **GOOD_DIGEST,
            "sections": [
                {
                    "title": "Неизвестная секция",
                    "items": [
                        {
                            "title": "Some item",
                            "due": None,
                            "evidence_id": "ev-001",
                            "confidence": 0.8,
                            "source_ref": {"type": "email", "msg_id": "msg-001"},
                        }
                    ],
                }
            ],
        }
        report = evaluate_digest(digest)
        warns = [i for i in report.issues if i.category == "section_assignment"]
        assert any("Unknown section title" in i.message for i in warns)

    def test_duplicate_section_is_error(self):
        digest = {
            **GOOD_DIGEST,
            "sections": [
                {
                    "title": SECTION_FYI,
                    "items": [
                        {
                            "title": "Item 1",
                            "due": None,
                            "evidence_id": "ev-001",
                            "confidence": 0.8,
                            "source_ref": {"type": "email", "msg_id": "msg-001"},
                        }
                    ],
                },
                {
                    "title": SECTION_FYI,  # duplicate
                    "items": [
                        {
                            "title": "Item 2",
                            "due": None,
                            "evidence_id": "ev-002",
                            "confidence": 0.8,
                            "source_ref": {"type": "email", "msg_id": "msg-002"},
                        }
                    ],
                },
            ],
        }
        report = evaluate_digest(digest)
        errors = [i for i in report.issues if i.category == "section_assignment" and i.severity == ISSUE_ERROR]
        assert len(errors) == 1


# ── Duplicate items ───────────────────────────────────────────────────────────

class TestDuplicateItems:
    def test_same_title_in_two_sections_is_warn(self):
        digest = {
            **GOOD_DIGEST,
            "sections": [
                {
                    "title": SECTION_ACTIONS,
                    "items": [
                        {
                            "title": "Согласовать NDA",
                            "due": None,
                            "evidence_id": "ev-001",
                            "confidence": 0.9,
                            "source_ref": {"type": "email", "msg_id": "msg-001"},
                        }
                    ],
                },
                {
                    "title": SECTION_URGENT,
                    "items": [
                        {
                            "title": "Согласовать NDA",  # same title
                            "due": "2026-04-01",
                            "evidence_id": "ev-001",
                            "confidence": 0.95,
                            "source_ref": {"type": "email", "msg_id": "msg-001"},
                        }
                    ],
                },
            ],
        }
        report = evaluate_digest(digest)
        warns = [i for i in report.issues if i.category == "duplicate"]
        assert len(warns) == 1


# ── Due date format ───────────────────────────────────────────────────────────

class TestDueDateFormat:
    def test_valid_iso_date(self):
        digest = {
            **GOOD_DIGEST,
            "sections": [
                {
                    "title": SECTION_ACTIONS,
                    "items": [
                        {
                            "title": "Item with ISO date",
                            "due": "2026-04-01",
                            "evidence_id": "ev-001",
                            "confidence": 0.9,
                            "source_ref": {"type": "email", "msg_id": "msg-001"},
                        }
                    ],
                }
            ],
        }
        report = evaluate_digest(digest)
        due_issues = [i for i in report.issues if i.category == "due_date"]
        assert len(due_issues) == 0

    def test_invalid_due_format_is_warn(self):
        digest = {
            **GOOD_DIGEST,
            "sections": [
                {
                    "title": SECTION_ACTIONS,
                    "items": [
                        {
                            "title": "Item with bad date",
                            "due": "31.03.2026",  # wrong format
                            "evidence_id": "ev-001",
                            "confidence": 0.9,
                            "source_ref": {"type": "email", "msg_id": "msg-001"},
                        }
                    ],
                }
            ],
        }
        report = evaluate_digest(digest)
        warns = [i for i in report.issues if i.category == "due_date"]
        assert len(warns) == 1

    def test_today_and_tomorrow_are_valid(self):
        for due_val in ("today", "tomorrow"):
            digest = {
                **GOOD_DIGEST,
                "sections": [
                    {
                        "title": SECTION_ACTIONS,
                        "items": [
                            {
                                "title": f"Item with {due_val}",
                                "due": due_val,
                                "evidence_id": "ev-001",
                                "confidence": 0.9,
                                "source_ref": {"type": "email", "msg_id": "msg-001"},
                            }
                        ],
                    }
                ],
            }
            report = evaluate_digest(digest)
            due_issues = [i for i in report.issues if i.category == "due_date"]
            assert len(due_issues) == 0, f"'{due_val}' should be valid"


# ── Empty digest ──────────────────────────────────────────────────────────────

class TestEmptyDigest:
    def test_empty_sections_is_info(self):
        digest = {
            "schema_version": "1.0",
            "prompt_version": "extract_actions.v1",
            "digest_date": "2026-03-31",
            "trace_id": "test-trace",
            "sections": [],
        }
        report = evaluate_digest(digest)
        infos = [i for i in report.issues if i.severity == ISSUE_INFO]
        assert len(infos) == 1
        assert report.score == 100  # empty is valid

    def test_missing_sections_key_is_error(self):
        digest = {
            "schema_version": "1.0",
            "prompt_version": "extract_actions.v1",
            "digest_date": "2026-03-31",
            "trace_id": "test-trace",
            # sections missing
        }
        report = evaluate_digest(digest)
        errors = [i for i in report.issues if i.severity == ISSUE_ERROR]
        assert len(errors) == 1


# ── Score and grade ───────────────────────────────────────────────────────────

class TestScoreAndGrade:
    def test_score_decreases_with_errors(self):
        digest = {
            **GOOD_DIGEST,
            "sections": [
                {
                    "title": SECTION_ACTIONS,
                    "items": [
                        {
                            "title": "Item",
                            "due": None,
                            # missing evidence_id (error), missing source_ref (error), missing confidence (error)
                        }
                    ],
                }
            ],
        }
        report = evaluate_digest(digest)
        assert report.score <= 70  # 3 errors × 10 = 30 deducted → score == 70

    def test_grade_F_below_60(self):
        report = EvalReport(prompt_version="v1", digest_date="2026-03-31", score=50)
        assert report._grade() == "F"

    def test_grade_C_60_to_74(self):
        report = EvalReport(prompt_version="v1", digest_date="2026-03-31", score=65)
        assert report._grade() == "C"

    def test_grade_B_75_to_89(self):
        report = EvalReport(prompt_version="v1", digest_date="2026-03-31", score=80)
        assert report._grade() == "B"

    def test_grade_A_90_plus(self):
        report = EvalReport(prompt_version="v1", digest_date="2026-03-31", score=95)
        assert report._grade() == "A"


# ── Report output ─────────────────────────────────────────────────────────────

class TestReportOutput:
    def test_summary_contains_date(self):
        report = evaluate_digest(GOOD_DIGEST)
        summary = report.summary()
        assert "2026-03-31" in summary

    def test_summary_contains_score(self):
        report = evaluate_digest(GOOD_DIGEST)
        assert "100/100" in report.summary()

    def test_to_dict_keys(self):
        report = evaluate_digest(GOOD_DIGEST)
        d = report.to_dict()
        assert "score" in d
        assert "grade" in d
        assert "total_items" in d
        assert "section_counts" in d
        assert "issues" in d
        assert "quality_rate" in d


# ── Per-item quality rate ─────────────────────────────────────────────────────

class TestQualityRate:
    def test_perfect_digest_rate_is_1(self):
        report = evaluate_digest(GOOD_DIGEST)
        assert report.quality_rate == 1.0

    def test_empty_digest_rate_is_1(self):
        digest = {**GOOD_DIGEST, "sections": []}
        report = evaluate_digest(digest)
        assert report.quality_rate == 1.0

    def test_one_bad_item_reduces_rate(self):
        digest = {
            **GOOD_DIGEST,
            "sections": [
                {
                    "title": SECTION_ACTIONS,
                    "items": [
                        {
                            "title": "Good item",
                            "due": None,
                            "evidence_id": "ev-001",
                            "confidence": 0.9,
                            "source_ref": {"type": "email", "msg_id": "msg-001"},
                        },
                        {
                            "title": "Bad item",
                            "due": None,
                            # missing evidence_id, source_ref, confidence
                        },
                    ],
                }
            ],
        }
        report = evaluate_digest(digest)
        assert report.quality_rate == 0.5  # 1 of 2 items is clean


# ── File-based evaluation ─────────────────────────────────────────────────────

class TestEvaluateDigestFile:
    def test_eval_from_file(self, tmp_path):
        digest_path = tmp_path / "digest-2026-03-31.json"
        digest_path.write_text(json.dumps(GOOD_DIGEST), encoding="utf-8")
        report = evaluate_digest_file(digest_path)
        assert report.score == 100

    def test_eval_with_ingest_snapshot(self, tmp_path):
        digest_path = tmp_path / "digest-2026-03-31.json"
        digest_path.write_text(json.dumps(GOOD_DIGEST), encoding="utf-8")

        # Create a fake ingest snapshot with matching evidence IDs
        snapshot = {
            "chunks": [
                {"evidence_id": "ev-001", "content": "..."},
                {"evidence_id": "ev-002", "content": "..."},
            ]
        }
        snapshot_path = tmp_path / "ingest.json"
        snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")

        report = evaluate_digest_file(digest_path, ingest_snapshot_path=snapshot_path)
        assert report.evidence_ids_checked
        assert not report.errors


# ── Changelog parser ──────────────────────────────────────────────────────────

class TestChangelogParser:
    PROMPT_WITH_CHANGELOG = """\
# CHANGELOG
# v1.0 2026-03-29 — initial version
# v1.1 2026-03-30 — add few-shot examples
# v1.2 2026-03-31 — tighten confidence bands
# END_CHANGELOG

Actual prompt content here.
"""

    PROMPT_NO_CHANGELOG = "Just a plain prompt with no changelog header.\n"

    def test_parses_all_entries(self, tmp_path):
        p = tmp_path / "prompt.txt"
        p.write_text(self.PROMPT_WITH_CHANGELOG, encoding="utf-8")
        versions = parse_prompt_changelog(p)
        assert len(versions) == 3

    def test_version_fields(self, tmp_path):
        p = tmp_path / "prompt.txt"
        p.write_text(self.PROMPT_WITH_CHANGELOG, encoding="utf-8")
        versions = parse_prompt_changelog(p)
        assert versions[0].version == "v1.0"
        assert versions[0].date == "2026-03-29"
        assert "initial version" in versions[0].note

    def test_no_changelog_returns_empty(self, tmp_path):
        p = tmp_path / "prompt.txt"
        p.write_text(self.PROMPT_NO_CHANGELOG, encoding="utf-8")
        versions = parse_prompt_changelog(p)
        assert versions == []

    def test_get_current_version(self, tmp_path):
        p = tmp_path / "prompt.txt"
        p.write_text(self.PROMPT_WITH_CHANGELOG, encoding="utf-8")
        assert get_current_version(p) == "v1.2"

    def test_get_current_version_no_changelog(self, tmp_path):
        p = tmp_path / "prompt.txt"
        p.write_text(self.PROMPT_NO_CHANGELOG, encoding="utf-8")
        assert get_current_version(p) is None

    def test_format_changelog_output(self, tmp_path):
        p = tmp_path / "prompt.txt"
        p.write_text(self.PROMPT_WITH_CHANGELOG, encoding="utf-8")
        versions = parse_prompt_changelog(p)
        output = format_changelog(versions)
        assert "v1.0" in output
        assert "v1.2" in output

    def test_format_changelog_empty(self):
        output = format_changelog([])
        assert "no changelog" in output.lower()

    def test_companion_file_preferred_over_inline(self, tmp_path):
        """If a .changelog companion file exists, it should be used instead of inline."""
        prompt = tmp_path / "prompt.txt"
        prompt.write_text("Just a prompt, no changelog.", encoding="utf-8")
        companion = tmp_path / "prompt.changelog"
        companion.write_text(self.PROMPT_WITH_CHANGELOG, encoding="utf-8")
        versions = parse_prompt_changelog(prompt)
        assert len(versions) == 3

    def test_actual_prompt_file_has_changelog(self):
        """Smoke test: the real extract_actions.v1.changelog must have parseable entries."""
        from digest_core.config import PROJECT_ROOT
        prompt_path = PROJECT_ROOT / "prompts" / "extract_actions.v1.txt"
        if not prompt_path.exists():
            pytest.skip("Prompt file not found")
        versions = parse_prompt_changelog(prompt_path)
        assert len(versions) >= 1, "extract_actions.v1 must have at least one changelog entry"


# ── CLI integration smoke test ────────────────────────────────────────────────

class TestEvalPromptCLI:
    def test_eval_prompt_cli_exits_0_on_good_digest(self, tmp_path):
        """CLI should exit 0 for a valid digest."""
        from typer.testing import CliRunner
        from digest_core.cli import app

        digest_path = tmp_path / "digest.json"
        digest_path.write_text(json.dumps(GOOD_DIGEST), encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(app, ["eval-prompt", "--digest", str(digest_path)])
        assert result.exit_code == 0, result.output

    def test_eval_prompt_cli_exits_1_on_bad_digest(self, tmp_path):
        """CLI should exit 1 for a digest with errors."""
        from typer.testing import CliRunner
        from digest_core.cli import app

        bad_digest = {
            "schema_version": "1.0",
            "prompt_version": "extract_actions.v1",
            "digest_date": "2026-03-31",
            "trace_id": "test-trace",
            "sections": [
                {
                    "title": SECTION_ACTIONS,
                    "items": [
                        {
                            "title": "Broken item",
                            # missing evidence_id, source_ref, confidence
                        }
                    ],
                }
            ],
        }
        digest_path = tmp_path / "bad_digest.json"
        digest_path.write_text(json.dumps(bad_digest), encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(app, ["eval-prompt", "--digest", str(digest_path)])
        assert result.exit_code == 1, result.output

    def test_eval_prompt_writes_json_report(self, tmp_path):
        """CLI --output-json should create a JSON report file."""
        from typer.testing import CliRunner
        from digest_core.cli import app

        digest_path = tmp_path / "digest.json"
        digest_path.write_text(json.dumps(GOOD_DIGEST), encoding="utf-8")
        json_report = tmp_path / "report.json"

        runner = CliRunner()
        result = runner.invoke(
            app,
            ["eval-prompt", "--digest", str(digest_path), "--output-json", str(json_report)],
        )
        assert result.exit_code == 0, result.output
        assert json_report.exists()
        report_data = json.loads(json_report.read_text())
        assert "score" in report_data
        assert "issues" in report_data
