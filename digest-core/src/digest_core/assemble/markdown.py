"""
Markdown output assembler for digest data with Russian localization.
"""

from pathlib import Path
import structlog

from digest_core.llm.schemas import Digest, EnhancedDigest

logger = structlog.get_logger()


class MarkdownAssembler:
    """Assemble digest data into Markdown output with Russian localization."""

    def __init__(self):
        self.max_words = 400
        self.max_items_per_section = 10

    def write_digest(self, digest_data: Digest, output_path: Path) -> None:
        """Write digest data to Markdown file."""
        logger.info("Writing Markdown digest", output_path=str(output_path))

        try:
            # Generate markdown content
            markdown_content = self._generate_markdown(digest_data)

            # Write to file
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(markdown_content)

            word_count = self._count_words(markdown_content)
            logger.info(
                "Markdown digest written successfully",
                output_path=str(output_path),
                word_count=word_count,
            )

        except Exception as e:
            logger.error(
                "Failed to write Markdown digest",
                output_path=str(output_path),
                error=str(e),
            )
            raise

    def _generate_markdown(self, digest_data: Digest) -> str:
        """Generate markdown content from digest data."""
        lines = []

        # Header
        digest_date = (
            digest_data.get("digest_date", "")
            if isinstance(digest_data, dict)
            else getattr(digest_data, "digest_date", "")
        )
        trace_id = (
            digest_data.get("trace_id", "")
            if isinstance(digest_data, dict)
            else getattr(digest_data, "trace_id", "")
        )
        lines.append(f"# Дайджест действий - {digest_date}")
        lines.append("")
        lines.append(f"*Trace ID: {trace_id}*")
        lines.append("")

        # Check if digest is empty
        sections = (
            digest_data.get("sections", [])
            if isinstance(digest_data, dict)
            else digest_data.sections
        )
        total_items = sum(
            len(section.get("items", []) if isinstance(section, dict) else section.items)
            for section in sections
        )
        if total_items == 0:
            lines.append("За период релевантных действий не найдено.")
            return "\n".join(lines)

        # Sections
        for section in sections:
            # Handle both object and dict formats
            items = section.get("items", []) if isinstance(section, dict) else section.items
            title = section.get("title", "") if isinstance(section, dict) else section.title

            if not items:
                continue

            lines.append(f"## {title}")
            lines.append("")

            # Limit items per section
            items_to_show = items[: self.max_items_per_section]

            for i, item in enumerate(items_to_show, 1):
                # Handle both object and dict formats
                if isinstance(item, dict):
                    item_title = item.get("title", "")
                    item_due = item.get("due")
                    item_confidence = item.get("confidence", 0)
                    item_evidence_id = item.get("evidence_id", "")
                    item_source_ref = item.get("source_ref", {})
                    item_email_subject = item.get("email_subject")
                else:
                    item_title = item.title
                    item_due = item.due
                    item_confidence = item.confidence
                    item_evidence_id = item.evidence_id
                    item_source_ref = item.source_ref
                    item_email_subject = getattr(item, "email_subject", None)

                lines.append(f"### {i}. {item_title}")

                # Add due date if present
                if item_due:
                    lines.append(f"**Срок:** {item_due}")

                # Add confidence
                confidence_text = self._format_confidence(item_confidence)
                lines.append(f"**Уверенность:** {confidence_text}")

                # Add evidence reference (required format) with email subject
                source_type = item_source_ref.get("type", "unknown")
                if item_email_subject:
                    lines.append(
                        f'**Источник:** {source_type}, тема "{item_email_subject}", evidence {item_evidence_id}'
                    )
                else:
                    lines.append(f"**Источник:** {source_type}, evidence {item_evidence_id}")

                lines.append("")

            # Add note if items were truncated
            if len(items) > self.max_items_per_section:
                remaining = len(items) - self.max_items_per_section
                lines.append(f"*... и еще {remaining} элементов*")
                lines.append("")

        # Statistics section
        total_processed = (
            digest_data.get("total_emails_processed", 0)
            if isinstance(digest_data, dict)
            else getattr(digest_data, "total_emails_processed", 0)
        )
        emails_with_actions = (
            digest_data.get("emails_with_actions", 0)
            if isinstance(digest_data, dict)
            else getattr(digest_data, "emails_with_actions", 0)
        )

        if total_processed > 0:
            lines.append("## Статистика")
            lines.append("")
            percent = (
                int((emails_with_actions / total_processed) * 100) if total_processed > 0 else 0
            )
            lines.append(
                f"Обработано {total_processed} писем, {emails_with_actions} ({percent}%) содержали действия"
            )
            lines.append("")

        # Evidence section
        lines.append("## Источники")
        lines.append("")

        evidence_ids = set()
        for section in sections:
            items = section.get("items", []) if isinstance(section, dict) else section.items
            for item in items:
                evidence_id = (
                    item.get("evidence_id", "") if isinstance(item, dict) else item.evidence_id
                )
                evidence_ids.add(evidence_id)

        for evidence_id in sorted(evidence_ids):
            lines.append(f"### Evidence {evidence_id}")
            lines.append(f"*ID: {evidence_id}*")
            lines.append("")

        # Check word count and truncate if necessary
        content = "\n".join(lines)
        word_count = self._count_words(content)

        if word_count > self.max_words:
            logger.warning(
                "Markdown content exceeds word limit",
                word_count=word_count,
                max_words=self.max_words,
            )
            content = self._truncate_content(content, self.max_words)

        return content

    def _format_confidence(self, confidence: float) -> str:
        """Format confidence score as Russian text."""
        if confidence >= 0.9:
            return "Очень высокая"
        elif confidence >= 0.7:
            return "Высокая"
        elif confidence >= 0.5:
            return "Средняя"
        elif confidence >= 0.3:
            return "Низкая"
        else:
            return "Очень низкая"

    def _count_words(self, text: str) -> int:
        """Count words in text."""
        # Simple word counting (split by whitespace)
        words = text.split()
        return len(words)

    def _truncate_content(self, content: str, max_words: int) -> str:
        """Truncate content to fit word limit."""
        words = content.split()

        if len(words) <= max_words:
            return content

        # Truncate and add note
        truncated_words = words[: max_words - 10]  # Leave room for truncation note
        truncated_content = " ".join(truncated_words)

        # Add truncation note
        truncated_content += "\n\n*[Содержимое обрезано для соблюдения лимита слов]*"

        return truncated_content

    def generate_summary(self, digest_data) -> str:
        """Generate a brief summary of the digest."""
        sections = (
            digest_data.get("sections", [])
            if isinstance(digest_data, dict)
            else digest_data.sections
        )
        total_items = sum(
            len(section.get("items", []) if isinstance(section, dict) else section.items)
            for section in sections
        )

        if total_items == 0:
            return "За период релевантных действий не найдено."

        summary_parts = [f"Найдено {total_items} действий:"]

        for section in sections:
            items = section.get("items", []) if isinstance(section, dict) else section.items
            title = section.get("title", "") if isinstance(section, dict) else section.title
            if items:
                summary_parts.append(f"- {title}: {len(items)}")

        return " ".join(summary_parts)

    def validate_markdown(self, content: str) -> bool:
        """Validate markdown content structure."""
        try:
            lines = content.split("\n")

            # Check for header
            if not any(line.startswith("# ") for line in lines):
                return False

            # Check for sections
            if not any(line.startswith("## ") for line in lines):
                return False

            # Check for evidence references
            evidence_refs = [line for line in lines if "Источник:" in line and "evidence" in line]
            if not evidence_refs:
                logger.warning("No evidence references found in markdown")
                return False

            return True

        except Exception as e:
            logger.warning("Markdown validation failed", error=str(e))
            return False

    def get_word_count(self, content: str) -> int:
        """Get word count of content."""
        return self._count_words(content)

    def format_evidence_reference(self, source_type: str, evidence_id: str) -> str:
        """Format evidence reference in required format."""
        return f"**Источник:** {source_type}, evidence {evidence_id}"

    def write_enhanced_digest(
        self,
        digest: EnhancedDigest,
        output_path: Path,
        is_partial: bool = False,
        partial_reason: str = None,
    ) -> None:
        """
        Write enhanced digest v2 data to Markdown file.

        Args:
            digest: EnhancedDigest instance
            output_path: Path to output file
            is_partial: Whether this is a partial digest (due to LLM failure)
            partial_reason: Reason for partial digest (e.g., "llm_json_error")
        """
        logger.info(
            "Writing enhanced Markdown digest v2",
            output_path=str(output_path),
            is_partial=is_partial,
        )

        try:
            # Generate markdown content
            markdown_content = self._generate_enhanced_markdown(
                digest, is_partial=is_partial, partial_reason=partial_reason
            )

            # Write to file
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(markdown_content)

            word_count = self._count_words(markdown_content)
            logger.info(
                "Enhanced Markdown digest written successfully",
                output_path=str(output_path),
                word_count=word_count,
                is_partial=is_partial,
            )

        except Exception as e:
            logger.error(
                "Failed to write enhanced Markdown digest",
                output_path=str(output_path),
                error=str(e),
            )
            raise

    def _generate_enhanced_markdown(
        self,
        digest: EnhancedDigest,
        is_partial: bool = False,
        partial_reason: str = None,
    ) -> str:
        """Generate markdown content from enhanced digest v2."""
        lines = []

        # Header
        lines.append(f"# Дайджест действий - {digest.digest_date}")
        lines.append(f"*Trace ID: {digest.trace_id}*")
        lines.append(f"*Timezone: {digest.timezone}*")
        lines.append(f"*Schema version: {digest.schema_version}*")
        lines.append("")

        # Add partial digest banner if applicable
        if is_partial:
            if partial_reason == "llm_json_error":
                lines.append("---")
                lines.append("⚠️ **ЧАСТИЧНЫЙ ОТЧЁТ: LLM дал невалидный JSON**")
                lines.append("")
                lines.append(
                    "Данный дайджест создан в резервном режиме (extractive fallback) из-за ошибки парсинга JSON от LLM."
                )
                lines.append("Информация может быть неполной или менее точной, чем обычно.")
                lines.append("---")
                lines.append("")
            elif partial_reason == "llm_processing_failed":
                lines.append("---")
                lines.append("⚠️ **ЧАСТИЧНЫЙ ОТЧЁТ: Ошибка обработки LLM**")
                lines.append("")
                lines.append(
                    "Данный дайджест создан в резервном режиме (extractive fallback) из-за сбоя LLM."
                )
                lines.append("Информация может быть неполной или менее точной, чем обычно.")
                lines.append("---")
                lines.append("")
            else:
                lines.append("---")
                lines.append("⚠️ **ЧАСТИЧНЫЙ ОТЧЁТ**")
                lines.append("")
                lines.append("Данный дайджест создан в резервном режиме (extractive fallback).")
                lines.append("Информация может быть неполной или менее точной, чем обычно.")
                lines.append("---")
                lines.append("")

        # Check if digest is empty
        total_items = (
            len(digest.my_actions)
            + len(digest.others_actions)
            + len(digest.deadlines_meetings)
            + len(digest.risks_blockers)
            + len(digest.fyi)
        )

        if total_items == 0:
            lines.append("За период релевантных действий не найдено.")
            if digest.markdown_summary:
                lines.append("")
                lines.append("---")
                lines.append(digest.markdown_summary)
            return "\n".join(lines)

        # My actions
        if digest.my_actions:
            lines.append("## Мои действия")
            lines.append("")
            for i, action in enumerate(digest.my_actions, 1):
                lines.append(f"### {i}. {action.title}")
                lines.append(f"**Описание:** {action.description}")
                if action.due_date:
                    due_label = f" ({action.due_date_label})" if action.due_date_label else ""
                    lines.append(f"**Срок:** {action.due_date}{due_label}")
                if action.due_date_normalized:
                    lines.append(f"**Дата (ISO):** {action.due_date_normalized}")
                lines.append(f"**Уверенность:** {action.confidence}")
                # Render actors or owners (V2 vs V3)
                actors_or_owners = getattr(action, "owners", None) or getattr(
                    action, "actors", None
                )
                if actors_or_owners:
                    lines.append(f"**Ответственные:** {', '.join(actors_or_owners)}")
                if action.response_channel:
                    lines.append(f"**Канал ответа:** {action.response_channel}")
                # Add source with email subject
                email_subject = getattr(action, "email_subject", None)
                if email_subject:
                    lines.append(
                        f'**Источник:** тема "{email_subject}", evidence {action.evidence_id}'
                    )
                else:
                    lines.append(f"**Источник:** Evidence {action.evidence_id}")
                lines.append(f'**Цитата:** "{action.quote}"')
                lines.append("")

        # Others' actions
        if digest.others_actions:
            lines.append("## Действия других")
            lines.append("")
            for i, action in enumerate(digest.others_actions, 1):
                lines.append(f"### {i}. {action.title}")
                lines.append(f"**Описание:** {action.description}")
                if action.due_date:
                    due_label = f" ({action.due_date_label})" if action.due_date_label else ""
                    lines.append(f"**Срок:** {action.due_date}{due_label}")
                lines.append(f"**Уверенность:** {action.confidence}")
                # Render actors or owners (V2 vs V3)
                actors_or_owners = getattr(action, "owners", None) or getattr(
                    action, "actors", None
                )
                if actors_or_owners:
                    lines.append(f"**Ответственные:** {', '.join(actors_or_owners)}")
                # Add source with email subject
                email_subject = getattr(action, "email_subject", None)
                if email_subject:
                    lines.append(
                        f'**Источник:** тема "{email_subject}", evidence {action.evidence_id}'
                    )
                else:
                    lines.append(f"**Источник:** Evidence {action.evidence_id}")
                lines.append(f'**Цитата:** "{action.quote}"')
                lines.append("")

        # Deadlines and meetings
        if digest.deadlines_meetings:
            lines.append("## Дедлайны и встречи")
            lines.append("")
            for i, item in enumerate(digest.deadlines_meetings, 1):
                lines.append(f"### {i}. {item.title}")
                date_label = f" ({item.date_label})" if item.date_label else ""
                lines.append(f"**Дата/время:** {item.date_time}{date_label}")
                if item.location:
                    lines.append(f"**Место:** {item.location}")
                if item.participants:
                    lines.append(f"**Участники:** {', '.join(item.participants)}")
                # Add source with email subject (use getattr for V3 compatibility)
                email_subject = getattr(item, "email_subject", None)
                if email_subject:
                    lines.append(
                        f'**Источник:** тема "{email_subject}", evidence {item.evidence_id}'
                    )
                else:
                    lines.append(f"**Источник:** Evidence {item.evidence_id}")
                lines.append(f'**Цитата:** "{item.quote}"')
                lines.append("")

        # Risks and blockers
        if digest.risks_blockers:
            lines.append("## Риски и блокеры")
            lines.append("")
            for i, item in enumerate(digest.risks_blockers, 1):
                lines.append(f"### {i}. {item.title}")
                lines.append(f"**Серьёзность:** {item.severity}")
                lines.append(f"**Влияние:** {item.impact}")
                # Render owners if present (V3)
                owners = getattr(item, "owners", None)
                if owners:
                    lines.append(f"**Ответственные:** {', '.join(owners)}")
                # Add source with email subject
                item_email_subject = getattr(item, "email_subject", None)
                if item_email_subject:
                    lines.append(
                        f'**Источник:** тема "{item_email_subject}", evidence {item.evidence_id}'
                    )
                else:
                    lines.append(f"**Источник:** Evidence {item.evidence_id}")
                lines.append(f'**Цитата:** "{item.quote}"')
                lines.append("")

        # FYI items
        if digest.fyi:
            lines.append("## К сведению (FYI)")
            lines.append("")
            for i, item in enumerate(digest.fyi, 1):
                lines.append(f"### {i}. {item.title}")
                if item.category:
                    lines.append(f"**Категория:** {item.category}")
                # Add source with email subject
                if item.email_subject:
                    lines.append(
                        f'**Источник:** тема "{item.email_subject}", evidence {item.evidence_id}'
                    )
                else:
                    lines.append(f"**Источник:** Evidence {item.evidence_id}")
                lines.append(f'**Цитата:** "{item.quote}"')
                lines.append("")

        # Statistics section - get from model_dump if available
        if hasattr(digest, "model_dump"):
            data_dict = digest.model_dump()
        else:
            data_dict = digest.__dict__ if hasattr(digest, "__dict__") else {}

        total_processed = data_dict.get("total_emails_processed", 0)
        emails_with_actions = data_dict.get("emails_with_actions", 0)

        if total_processed > 0:
            lines.append("## Статистика")
            lines.append("")
            percent = (
                int((emails_with_actions / total_processed) * 100) if total_processed > 0 else 0
            )
            lines.append(
                f"Обработано {total_processed} писем, {emails_with_actions} ({percent}%) содержали действия"
            )
            lines.append("")

        # Add markdown summary if present
        if digest.markdown_summary:
            lines.append("---")
            lines.append(digest.markdown_summary)

        return "\n".join(lines)
