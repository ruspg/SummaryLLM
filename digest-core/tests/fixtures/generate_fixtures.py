"""
Sample email fixtures for testing.
"""

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path


def create_sample_emails():
    """Create sample email fixtures."""
    emails = []

    # Email 1: Urgent action item
    email1 = {
        "msg_id": "msg-001",
        "conversation_id": "conv-001",
        "datetime_received": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
        "sender": {"email_address": "manager@company.com"},
        "subject": "URGENT: Server Maintenance Required",
        "text_body": """
        Hi Team,
        
        Our production server is experiencing issues and needs immediate attention.
        Please review the logs and schedule maintenance for tonight.
        
        Best regards,
        Manager
        """,
    }
    emails.append(email1)

    # Email 2: Meeting request
    email2 = {
        "msg_id": "msg-002",
        "conversation_id": "conv-002",
        "datetime_received": (datetime.now(timezone.utc) - timedelta(hours=4)).isoformat(),
        "sender": {"email_address": "colleague@company.com"},
        "subject": "Meeting: Q4 Review",
        "text_body": """
        Hello,
        
        Let's schedule a meeting to review Q4 performance.
        Please confirm your availability for next week.
        
        Thanks,
        Colleague
        """,
    }
    emails.append(email2)

    # Email 3: Out of Office
    email3 = {
        "msg_id": "msg-003",
        "conversation_id": "conv-003",
        "datetime_received": (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat(),
        "sender": {"email_address": "user@company.com"},
        "subject": "Out of Office",
        "text_body": """
        I will be out of office until next Monday.
        For urgent matters, please contact my assistant.
        
        Best regards,
        User
        """,
    }
    emails.append(email3)

    # Email 4: Long thread
    email4 = {
        "msg_id": "msg-004",
        "conversation_id": "conv-004",
        "datetime_received": (datetime.now(timezone.utc) - timedelta(hours=8)).isoformat(),
        "sender": {"email_address": "team@company.com"},
        "subject": "Project Discussion",
        "text_body": """
        This is a long email with multiple paragraphs.
        
        Paragraph 1: We need to discuss the project timeline.
        
        Paragraph 2: The budget has been approved.
        
        Paragraph 3: Please review the attached documents.
        
        Paragraph 4: Let me know if you have any questions.
        
        Paragraph 5: We should schedule a follow-up meeting.
        
        Best regards,
        Team
        """,
    }
    emails.append(email4)

    # Email 5: DSN (Delivery Status Notification)
    email5 = {
        "msg_id": "msg-005",
        "conversation_id": "conv-005",
        "datetime_received": (datetime.now(timezone.utc) - timedelta(hours=10)).isoformat(),
        "sender": {"email_address": "system@company.com"},
        "subject": "Delivery Status Notification",
        "text_body": """
        Delivery Status Notification
        
        Your message could not be delivered.
        Please check the recipient address.
        
        System Administrator
        """,
    }
    emails.append(email5)

    return emails


def create_email_files():
    """Create actual email files for testing."""
    emails_dir = Path("emails")
    emails_dir.mkdir(exist_ok=True)

    # Create various email types
    email_files = []

    # 1. Plain text actionable email
    email1_content = """From: manager@company.com
To: user@company.com
Subject: URGENT: Review Q4 Report
Date: Mon, 15 Jan 2024 10:30:00 +0000

Hi,

Please review the Q4 report and provide feedback by Friday.
This is urgent and requires your immediate attention.

Best regards,
Manager
"""
    email1_path = emails_dir / "urgent_action.txt"
    with open(email1_path, "w", encoding="utf-8") as f:
        f.write(email1_content)
    email_files.append(str(email1_path))

    # 2. HTML email with actionable content
    email2_content = """From: colleague@company.com
To: user@company.com
Subject: Meeting Request - Project Review
Date: Mon, 15 Jan 2024 14:15:00 +0000
Content-Type: text/html; charset=utf-8

<html>
<body>
<h2>Meeting Request</h2>
<p>Hi there,</p>
<p>We need to schedule a meeting to review the project status. <strong>Please confirm your availability for tomorrow at 2 PM.</strong></p>
<p>Best regards,<br>Colleague</p>
</body>
</html>
"""
    email2_path = emails_dir / "meeting_request.html"
    with open(email2_path, "w", encoding="utf-8") as f:
        f.write(email2_content)
    email_files.append(str(email2_path))

    # 3. Cyrillic email
    email3_content = """From: коллега@компания.рф
To: пользователь@компания.рф
Subject: Срочно: Проверка отчета
Date: Mon, 15 Jan 2024 16:45:00 +0000

Привет,

Пожалуйста, проверьте отчет за четвертый квартал до пятницы.
Это срочно и требует вашего немедленного внимания.

С уважением,
Коллега
"""
    email3_path = emails_dir / "cyrillic_action.txt"
    with open(email3_path, "w", encoding="utf-8") as f:
        f.write(email3_content)
    email_files.append(str(email3_path))

    # 4. Out of Office auto-reply
    email4_content = """From: noreply@company.com
To: user@company.com
Subject: [Автоответ] Out of Office
Date: Mon, 15 Jan 2024 09:00:00 +0000
Auto-Submitted: auto-replied

I am currently out of office and will return on Monday, January 22nd.
For urgent matters, please contact my assistant at assistant@company.com.

Best regards,
User
"""
    email4_path = emails_dir / "out_of_office.txt"
    with open(email4_path, "w", encoding="utf-8") as f:
        f.write(email4_content)
    email_files.append(str(email4_path))

    # 5. Delivery Status Notification
    email5_content = """From: postmaster@company.com
To: user@company.com
Subject: Undeliverable: Your message
Date: Mon, 15 Jan 2024 11:20:00 +0000

Delivery Status Notification

Your message could not be delivered to the following recipient:
recipient@invalid.com

The recipient's mailbox is full.

System Administrator
"""
    email5_path = emails_dir / "dsn.txt"
    with open(email5_path, "w", encoding="utf-8") as f:
        f.write(email5_content)
    email_files.append(str(email5_path))

    # 6. Newsletter (non-actionable)
    email6_content = """From: newsletter@company.com
To: user@company.com
Subject: Weekly Newsletter - January 15, 2024
Date: Mon, 15 Jan 2024 08:00:00 +0000

Weekly Newsletter

This week's highlights:
- Company picnic scheduled for Friday
- New employee onboarding program
- IT maintenance window this weekend

FYI - No action required.

Newsletter Team
"""
    email6_path = emails_dir / "newsletter.txt"
    with open(email6_path, "w", encoding="utf-8") as f:
        f.write(email6_content)
    email_files.append(str(email6_path))

    # 7. Long thread with quotes
    email7_content = """From: team@company.com
To: user@company.com
Subject: Re: Project Discussion
Date: Mon, 15 Jan 2024 17:30:00 +0000

On Mon, 15 Jan 2024 at 16:00, user@company.com wrote:
> Thanks for the update. I'll review the documents.

Great! Please also check the budget allocation.

> On Mon, 15 Jan 2024 at 15:30, team@company.com wrote:
> > We need to discuss the project timeline.
> > Please review the attached documents.

The timeline looks good. Let's schedule a follow-up meeting.

Best regards,
Team
"""
    email7_path = emails_dir / "thread_with_quotes.txt"
    with open(email7_path, "w", encoding="utf-8") as f:
        f.write(email7_content)
    email_files.append(str(email7_path))

    # 8. HTML email with tracking pixels
    email8_content = """From: marketing@company.com
To: user@company.com
Subject: Special Offer - Limited Time
Date: Mon, 15 Jan 2024 12:00:00 +0000
Content-Type: text/html; charset=utf-8

<html>
<body>
<h2>Special Offer</h2>
<p>Don't miss our limited-time offer!</p>
<img src="cid:tracking-pixel" width="1" height="1" style="display:none">
<p>Click here to learn more: <a href="https://company.com/offer">View Offer</a></p>
<p>Best regards,<br>Marketing Team</p>
</body>
</html>
"""
    email8_path = emails_dir / "html_with_tracking.html"
    with open(email8_path, "w", encoding="utf-8") as f:
        f.write(email8_content)
    email_files.append(str(email8_path))

    # 9. Email with deadline
    email9_content = """From: boss@company.com
To: user@company.com
Subject: Deadline: Annual Review Due Tomorrow
Date: Mon, 15 Jan 2024 18:00:00 +0000

Hi,

Your annual review is due tomorrow (Tuesday, January 16th) by 5 PM.
Please submit your self-assessment and goals for next year.

This is a hard deadline - no extensions.

Thanks,
Boss
"""
    email9_path = emails_dir / "deadline.txt"
    with open(email9_path, "w", encoding="utf-8") as f:
        f.write(email9_content)
    email_files.append(str(email9_path))

    # 10. Email with multiple recipients
    email10_content = """From: coordinator@company.com
To: user@company.com, colleague@company.com
CC: manager@company.com
Subject: Team Meeting - Please Confirm Attendance
Date: Mon, 15 Jan 2024 13:45:00 +0000

Hi Team,

We have a team meeting scheduled for Wednesday at 10 AM.
Please confirm your attendance by replying to this email.

Meeting details:
- Date: Wednesday, January 17th
- Time: 10:00 AM
- Location: Conference Room A

Best regards,
Coordinator
"""
    email10_path = emails_dir / "team_meeting.txt"
    with open(email10_path, "w", encoding="utf-8") as f:
        f.write(email10_content)
    email_files.append(str(email10_path))

    return email_files


def create_config_fixtures():
    """Create sample configuration fixtures."""
    configs = {}

    # Calendar day config
    configs["calendar_day"] = {
        "time": {"timezone": "UTC", "window_type": "calendar_day"},
        "ews": {
            "endpoint": "https://mail.company.com/EWS/Exchange.asmx",
            "user_upn": "test@company.com",
            "sync_state_path": "/tmp/test.state",
        },
        "llm": {
            "endpoint": "https://api.openai.com/v1/chat/completions",
            "model": "qwen35-397b-a17b",
            "max_retries": 3,
            "timeout": 30,
        },
    }

    # Rolling 24h config
    configs["rolling_24h"] = {
        "time": {"timezone": "UTC", "window_type": "rolling_24h"},
        "ews": {
            "endpoint": "https://mail.company.com/EWS/Exchange.asmx",
            "user_upn": "test@company.com",
            "sync_state_path": "/tmp/test.state",
        },
        "llm": {
            "endpoint": "https://api.openai.com/v1/chat/completions",
            "model": "qwen35-397b-a17b",
            "max_retries": 3,
            "timeout": 30,
        },
    }

    return configs


if __name__ == "__main__":
    # Generate fixture files
    emails = create_sample_emails()
    configs = create_config_fixtures()

    # Create email files
    email_files = create_email_files()

    # Save email fixtures
    with open("emails.json", "w") as f:
        json.dump(emails, f, indent=2)

    # Save config fixtures
    for name, config in configs.items():
        with open(f"config_{name}.yaml", "w") as f:
            import yaml

            yaml.dump(config, f, default_flow_style=False)

    print("Fixture files generated:")
    print("- emails.json")
    print("- config_calendar_day.yaml")
    print("- config_rolling_24h.yaml")
    print(f"- {len(email_files)} email files in emails/ directory:")
    for file_path in email_files:
        print(f"  - {file_path}")
