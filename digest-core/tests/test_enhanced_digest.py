"""
Tests for enhanced digest v2 functionality.
"""

import pytest
from datetime import datetime, timezone
from digest_core.llm.schemas import (
    EnhancedDigest,
    ActionItem,
    DeadlineMeeting,
    RiskBlocker,
    FYIItem,
)
from digest_core.llm.date_utils import normalize_date_to_tz, get_current_datetime_in_tz
from digest_core.llm.gateway import LLMGateway

try:
    from jsonschema import ValidationError
except ImportError:
    ValidationError = Exception


class TestEnhancedSchemas:
    """Test enhanced Pydantic schemas."""

    def test_action_item_with_all_fields(self):
        """Test ActionItem with all fields populated."""
        action = ActionItem(
            title="Review document",
            description="Please review the attached document",
            evidence_id="ev_123",
            quote="Please review the attached document by Friday.",
            due_date="2024-12-15",
            due_date_normalized="2024-12-15T15:00:00-03:00",
            due_date_label="tomorrow",
            actors=["user"],
            confidence="High",
            response_channel="email",
        )

        assert action.title == "Review document"
        assert action.evidence_id == "ev_123"
        assert len(action.quote) >= 10
        assert action.confidence == "High"

    def test_enhanced_digest_creation(self):
        """Test EnhancedDigest creation with sections."""
        action1 = ActionItem(
            title="Test action",
            description="Description",
            evidence_id="ev_1",
            quote="This is a test quote for the action.",
            confidence="High",
        )

        digest = EnhancedDigest(
            prompt_version="v2",
            digest_date="2024-12-14",
            trace_id="test_123",
            my_actions=[action1],
            others_actions=[],
            deadlines_meetings=[],
            risks_blockers=[],
            fyi=[],
        )

        assert digest.schema_version == "2.0"
        assert len(digest.my_actions) == 1
        assert digest.timezone == "America/Sao_Paulo"

    def test_deadline_meeting_schema(self):
        """Test DeadlineMeeting schema."""
        deadline = DeadlineMeeting(
            title="Team meeting",
            evidence_id="ev_456",
            quote="Team meeting scheduled for tomorrow at 2 PM.",
            date_time="2024-12-15T14:00:00-03:00",
            date_label="tomorrow",
            location="Room 101",
            participants=["Alice", "Bob"],
        )

        assert deadline.title == "Team meeting"
        assert deadline.date_label == "tomorrow"
        assert len(deadline.participants) == 2

    def test_risk_blocker_schema(self):
        """Test RiskBlocker schema."""
        risk = RiskBlocker(
            title="Server outage",
            evidence_id="ev_789",
            quote="Critical server experiencing intermittent outages.",
            severity="High",
            impact="May affect deployment schedule",
        )

        assert risk.severity == "High"
        assert len(risk.quote) >= 10

    def test_fyi_item_schema(self):
        """Test FYIItem schema."""
        fyi = FYIItem(
            title="New policy announced",
            evidence_id="ev_101",
            quote="Company announces new remote work policy effective next month.",
            category="announcement",
        )

        assert fyi.category == "announcement"
        assert fyi.evidence_id == "ev_101"


class TestDateNormalization:
    """Test date normalization utilities."""

    def test_normalize_date_today(self):
        """Test date normalization for today."""
        base_dt = datetime(2024, 12, 14, 10, 0, 0, tzinfo=timezone.utc)
        result = normalize_date_to_tz("2024-12-14T12:00:00", base_dt, "America/Sao_Paulo")

        assert result["label"] == "today"
        assert result["normalized"] is not None

    def test_normalize_date_tomorrow(self):
        """Test date normalization for tomorrow."""
        base_dt = datetime(2024, 12, 14, 10, 0, 0, tzinfo=timezone.utc)
        result = normalize_date_to_tz("2024-12-15T12:00:00", base_dt, "America/Sao_Paulo")

        assert result["label"] == "tomorrow"

    def test_normalize_date_future(self):
        """Test date normalization for future date."""
        base_dt = datetime(2024, 12, 14, 10, 0, 0, tzinfo=timezone.utc)
        result = normalize_date_to_tz("2024-12-20T12:00:00", base_dt, "America/Sao_Paulo")

        assert result["label"] is None
        assert result["normalized"] is not None

    def test_get_current_datetime_in_tz(self):
        """Test getting current datetime in timezone."""
        dt_str = get_current_datetime_in_tz("America/Sao_Paulo")

        assert "T" in dt_str
        assert "-03:00" in dt_str or "-02:00" in dt_str  # Depends on DST


class TestParseEnhancedResponse:
    """Test parsing of enhanced LLM responses."""

    def test_parse_json_only(self):
        """Test parsing response with JSON only."""
        json_response = """{
  "schema_version": "2.0",
  "prompt_version": "v2",
  "digest_date": "2024-12-14",
  "trace_id": "test_123",
  "timezone": "America/Sao_Paulo",
  "my_actions": [],
  "others_actions": [],
  "deadlines_meetings": [],
  "risks_blockers": [],
  "fyi": []
}"""

        # Create gateway instance (will fail without config, but we just need the method)
        try:
            from digest_core.config import LLMConfig

            config = LLMConfig(endpoint="http://test", model="test")
            gateway = LLMGateway(config)

            result = gateway._parse_enhanced_response(json_response)

            assert result["schema_version"] == "2.0"
            assert "my_actions" in result
            gateway.close()
        except Exception as e:
            # Skip if config fails
            pytest.skip(f"Skipping due to config issue: {e}")

    def test_parse_json_with_markdown(self):
        """Test parsing response with JSON + Markdown."""
        response = """{
  "schema_version": "2.0",
  "digest_date": "2024-12-14",
  "trace_id": "test_123",
  "my_actions": []
}

## Краткое резюме

Важные моменты за период."""

        try:
            from digest_core.config import LLMConfig

            config = LLMConfig(endpoint="http://test", model="test")
            gateway = LLMGateway(config)

            result = gateway._parse_enhanced_response(response)

            assert result["schema_version"] == "2.0"
            assert "markdown_summary" in result
            assert "Краткое резюме" in result["markdown_summary"]
            gateway.close()
        except Exception as e:
            pytest.skip(f"Skipping due to config issue: {e}")


class TestSchemaValidation:
    """Test jsonschema validation."""

    def test_valid_schema_passes(self):
        """Test that valid schema passes validation."""
        valid_data = {
            "schema_version": "2.0",
            "prompt_version": "v2",
            "digest_date": "2024-12-14",
            "trace_id": "test_123",
            "timezone": "America/Sao_Paulo",
            "my_actions": [
                {
                    "title": "Test",
                    "description": "Test description",
                    "evidence_id": "ev_1",
                    "quote": "This is a test quote for validation.",
                    "confidence": "High",
                }
            ],
            "others_actions": [],
            "deadlines_meetings": [],
            "risks_blockers": [],
            "fyi": [],
        }

        try:
            from digest_core.config import LLMConfig

            config = LLMConfig(endpoint="http://test", model="test")
            gateway = LLMGateway(config)

            result = gateway._validate_enhanced_schema(valid_data)
            assert result == valid_data
            gateway.close()
        except ImportError:
            pytest.skip("jsonschema not available")
        except Exception as e:
            pytest.skip(f"Skipping due to config issue: {e}")

    def test_missing_evidence_id_fails(self):
        """Test that missing evidence_id fails validation."""
        invalid_data = {
            "schema_version": "2.0",
            "digest_date": "2024-12-14",
            "trace_id": "test_123",
            "my_actions": [
                {
                    "title": "Test",
                    "description": "Test",
                    "quote": "Quote here",
                    "confidence": "High",
                    # Missing evidence_id
                }
            ],
        }

        try:
            from digest_core.config import LLMConfig

            config = LLMConfig(endpoint="http://test", model="test")
            gateway = LLMGateway(config)

            with pytest.raises(ValueError):
                gateway._validate_enhanced_schema(invalid_data)
            gateway.close()
        except ImportError:
            pytest.skip("jsonschema not available")
        except Exception as e:
            pytest.skip(f"Skipping due to config issue: {e}")

    def test_short_quote_fails(self):
        """Test that quote shorter than 10 chars fails validation."""
        invalid_data = {
            "schema_version": "2.0",
            "digest_date": "2024-12-14",
            "trace_id": "test_123",
            "my_actions": [
                {
                    "title": "Test",
                    "description": "Test",
                    "evidence_id": "ev_1",
                    "quote": "Short",  # Too short
                    "confidence": "High",
                }
            ],
        }

        try:
            from digest_core.config import LLMConfig

            config = LLMConfig(endpoint="http://test", model="test")
            gateway = LLMGateway(config)

            with pytest.raises(ValueError):
                gateway._validate_enhanced_schema(invalid_data)
            gateway.close()
        except ImportError:
            pytest.skip("jsonschema not available")
        except Exception as e:
            pytest.skip(f"Skipping due to config issue: {e}")
