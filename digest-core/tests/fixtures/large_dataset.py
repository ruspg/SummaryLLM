"""
Large dataset generator for testing hierarchical mode.

Generates synthetic 300+ email dataset with known actions/deadlines.
"""

from datetime import datetime, timedelta, timezone
from typing import List
import random

from digest_core.ingest.ews import NormalizedMessage


def generate_large_email_dataset(count: int = 300, seed: int = 42) -> List[NormalizedMessage]:
    """
    Generate synthetic 300+ email dataset with known actions/deadlines.

    Mix of:
    - Large threads (10-20 messages)
    - Medium threads (5-10 messages)
    - Small threads (1-3 messages)
    - Known action signals
    - Known deadlines

    Args:
        count: Number of emails to generate
        seed: Random seed for reproducibility

    Returns:
        List of NormalizedMessage objects
    """
    random.seed(seed)

    messages = []
    base_time = datetime.now(timezone.utc) - timedelta(hours=24)

    # Thread distribution
    large_threads = count // 10  # 10% large threads (10-20 messages each)
    medium_threads = count // 5  # 20% medium threads (5-10 messages each)
    # Rest will be small threads (1-3 messages each)

    thread_id = 0
    msg_count = 0

    # Generate large threads
    for _ in range(large_threads):
        thread_id += 1
        thread_size = random.randint(10, 20)
        thread_messages = _generate_thread(
            thread_id, thread_size, base_time, has_actions=True, has_deadlines=True
        )
        messages.extend(thread_messages)
        msg_count += len(thread_messages)
        if msg_count >= count:
            break

    # Generate medium threads
    for _ in range(medium_threads):
        if msg_count >= count:
            break
        thread_id += 1
        thread_size = random.randint(5, 10)
        has_actions = random.random() > 0.5
        has_deadlines = random.random() > 0.6
        thread_messages = _generate_thread(
            thread_id,
            thread_size,
            base_time,
            has_actions=has_actions,
            has_deadlines=has_deadlines,
        )
        messages.extend(thread_messages)
        msg_count += len(thread_messages)

    # Generate small threads to fill remaining
    while msg_count < count:
        thread_id += 1
        thread_size = random.randint(1, 3)
        has_actions = random.random() > 0.7
        has_deadlines = random.random() > 0.8
        thread_messages = _generate_thread(
            thread_id,
            thread_size,
            base_time,
            has_actions=has_actions,
            has_deadlines=has_deadlines,
        )
        messages.extend(thread_messages)
        msg_count += len(thread_messages)

    # Trim to exact count
    messages = messages[:count]

    # Shuffle to simulate real email order
    random.shuffle(messages)

    return messages


def _generate_thread(
    thread_id: int,
    size: int,
    base_time: datetime,
    has_actions: bool = False,
    has_deadlines: bool = False,
) -> List[NormalizedMessage]:
    """Generate a single thread with specified characteristics."""
    messages = []
    conversation_id = f"thread_{thread_id}"

    subjects = [
        "Project update",
        "Meeting follow-up",
        "Q4 Planning",
        "Code review",
        "Budget approval",
        "Weekly sync",
        "Customer feedback",
        "Technical discussion",
        "Deployment schedule",
        "Team announcement",
    ]
    subject = random.choice(subjects) + f" (Thread {thread_id})"

    for i in range(size):
        msg_time = base_time + timedelta(minutes=i * 30)

        # Generate content
        content_parts = [
            f"This is message {i+1} in thread {thread_id}.",
            "Some general discussion about the topic.",
        ]

        # Add action signals
        if has_actions and i == size - 1:  # Last message has action
            content_parts.append("\nПожалуйста, проверьте и согласуйте документ до конца недели.")
            content_parts.append("Please review and approve the document by end of week.")

        # Add deadline signals
        if has_deadlines and i == size - 2:  # Second to last has deadline
            deadline_date = (msg_time + timedelta(days=2)).strftime("%Y-%m-%d")
            content_parts.append(f"\nДедлайн: {deadline_date} 15:00")
            content_parts.append(f"Deadline: {deadline_date} at 3 PM")

        content = "\n".join(content_parts)

        # Generate message
        msg = NormalizedMessage(
            msg_id=f"msg_{thread_id}_{i}",
            conversation_id=conversation_id,
            datetime_received=msg_time,
            sender_email=f"sender{random.randint(1, 10)}@company.com",
            subject=subject,
            text_body=content,
            to_recipients=["user@company.com"],
            cc_recipients=[],
            importance="High" if has_actions or has_deadlines else "Normal",
            is_flagged=has_actions,
            has_attachments=random.random() > 0.8,
            attachment_types=["pdf"] if random.random() > 0.9 else [],
        )
        messages.append(msg)

    return messages


def get_action_thread_ids(messages: List[NormalizedMessage]) -> set:
    """Get thread IDs that contain action signals."""
    action_threads = set()

    action_keywords = [
        "проверьте",
        "согласуйте",
        "review",
        "approve",
        "пожалуйста",
        "please",
    ]

    for msg in messages:
        for keyword in action_keywords:
            if keyword.lower() in msg.text_body.lower():
                action_threads.add(msg.conversation_id)
                break

    return action_threads


def get_deadline_thread_ids(messages: List[NormalizedMessage]) -> set:
    """Get thread IDs that contain deadline signals."""
    deadline_threads = set()

    deadline_keywords = ["дедлайн", "deadline", "срок", "due"]

    for msg in messages:
        for keyword in deadline_keywords:
            if keyword.lower() in msg.text_body.lower():
                deadline_threads.add(msg.conversation_id)
                break

    return deadline_threads
