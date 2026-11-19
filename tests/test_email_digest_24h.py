"""
Tests for 24-Hour Consolidated Email Digest & Rate Limiting Policy.
Validates:
1. Per-task emails are consolidated into a persistent buffer.
2. Only 1 email is dispatched within 24 hours.
3. Subsequent tasks within the 24-hour window accumulate in the buffer without triggering emails.
4. Once 24 hours elapse, the complete digest with all 24-hour details (Shorts, Long-form, Analytics, Notices) is sent.
5. Force flag allows immediate manual override when desired.
"""
import os
import json
from datetime import datetime, timezone, timedelta
import pytest

import config
import automation
import notifier.email_notifier as email_notif


@pytest.fixture(autouse=True)
def isolated_digest_workspace(tmp_path, monkeypatch):
    """Isolate output dir and schedule file for email digest tests."""
    out_dir = tmp_path / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(config, "OUTPUT_DIR", str(out_dir))
    monkeypatch.setattr(automation, "SCHEDULE_FILE", str(out_dir / "automation_schedule.json"))
    monkeypatch.setattr(config, "EMAIL_DIGEST_INTERVAL_HOURS", 24.0)
    monkeypatch.setattr(config, "SMTP_USER", "")  # Do not actually dial SMTP in unit tests
    monkeypatch.setattr(config, "SMTP_PASSWORD", "")
    yield out_dir


def test_24_hour_email_digest_rate_limiting_and_buffering(isolated_digest_workspace, monkeypatch):
    """
    Simulate multiple tasks running throughout the day:
    - Task 1 (Short 1): triggers first digest, records timestamp.
    - Task 2 (Short 2): within 24h, buffers data, returns False (no email dispatched).
    - Task 3 (Long-form): within 24h, buffers data, returns False.
    - Task 4 (Error Notice): within 24h, buffers notice, returns False.
    - Simulate 24.1 hours passing -> triggers complete consolidated 24-hour digest.
    """
    dispatched_emails = []

    def mock_smtp(to_email, subject, text_content, html_content):
        dispatched_emails.append({
            "to": to_email,
            "subject": subject,
            "text": text_content,
            "html": html_content,
        })
        return True

    monkeypatch.setattr(email_notif, "_dispatch_smtp_email", mock_smtp)

    # 1. First task of the day: Short 1
    short1 = {"title": "Short 1: Indus Valley Drainage", "url": "https://youtube.com/shorts/s1", "score": 95}
    sent1 = email_notif.send_upload_notification_email(shorts_results=[short1])
    assert sent1 is True
    assert len(dispatched_emails) == 1
    assert "24-Hour Digest" in dispatched_emails[0]["subject"]
    assert "Short 1: Indus Valley Drainage" in dispatched_emails[0]["html"]

    # 2. Second task 2 hours later: Short 2 (should be buffered, NO email sent)
    short2 = {"title": "Short 2: Kailash Temple Monolith", "url": "https://youtube.com/shorts/s2", "score": 100}
    sent2 = email_notif.send_upload_notification_email(shorts_results=[short2])
    assert sent2 is False, "Second task within 24 hours must NOT send an email"
    assert len(dispatched_emails) == 1, "Email count must remain exactly 1"

    # Verify short2 is safely recorded in the buffer
    st = automation.load_schedule_state()
    buf = st.get("email_digest_buffer", {})
    buf_shorts = [s.get("title") for s in buf.get("shorts", [])]
    assert "Short 2: Kailash Temple Monolith" in buf_shorts

    # 3. Third task: Long-form documentary (should be buffered, NO email sent)
    long1 = {"title": "Long Documentary: The Lost Saraswati River", "url": "https://youtube.com/watch?v=lf1", "score": 98}
    sent3 = email_notif.send_upload_notification_email(longform_result=long1)
    assert sent3 is False, "Long-form within 24 hours must NOT send a separate email"
    assert len(dispatched_emails) == 1

    st = automation.load_schedule_state()
    buf_lf = [l.get("title") for l in st.get("email_digest_buffer", {}).get("longform", [])]
    assert "Long Documentary: The Lost Saraswati River" in buf_lf

    # 4. Fourth task: Pipeline error diagnostic (should be buffered, NO email sent)
    err1 = {"item": "Image Downloader", "title": "Pexels Rate Limit", "error": "HTTP 429", "action": "Switched to Pixabay"}
    sent4 = email_notif.send_upload_notification_email(errors=[err1])
    assert sent4 is False, "Diagnostics within 24 hours must be buffered, not spammed"
    assert len(dispatched_emails) == 1

    # 5. Fast-forward clock by 24.5 hours
    old_time = datetime.now(timezone.utc) - timedelta(hours=24.5)
    st = automation.load_schedule_state()
    st["last_email_digest_sent_at"] = old_time.isoformat()
    automation.save_schedule_state(st)

    should, reason = email_notif.should_send_email_digest()
    assert should is True
    assert "interval_elapsed" in reason

    # 6. Trigger next cycle task (e.g. daily cron heartbeat or next task)
    short3 = {"title": "Short 3: Ashoka Edict", "url": "https://youtube.com/shorts/s3", "score": 92}
    sent5 = email_notif.send_upload_notification_email(shorts_results=[short3])
    assert sent5 is True, "After 24 hours have passed, the complete digest MUST be sent"
    assert len(dispatched_emails) == 2, "Exactly 2 emails total across the two 24h cycles"

    # Verify the second email contains ALL accumulated details from the past 24 hours
    second_email_html = dispatched_emails[1]["html"]
    assert "Short 2: Kailash Temple Monolith" in second_email_html
    assert "The Lost Saraswati River" in second_email_html
    assert "Pexels Rate Limit" in second_email_html
    assert "Short 3: Ashoka Edict" in second_email_html


def test_force_flag_bypasses_24_hour_cooldown(isolated_digest_workspace, monkeypatch):
    """Verify that force=True delivers the email immediately even if 24 hours have not passed."""
    dispatched = []
    monkeypatch.setattr(email_notif, "_dispatch_smtp_email", lambda *a: dispatched.append(a) or True)

    short = {"title": "Short Forced", "url": "https://youtube.com/shorts/sf", "score": 100}
    email_notif.send_upload_notification_email(shorts_results=[short])
    assert len(dispatched) == 1

    # Normal attempt immediately after: blocked
    res_normal = email_notif.send_upload_notification_email(shorts_results=[short])
    assert res_normal is False
    assert len(dispatched) == 1

    # Forced attempt: dispatched immediately
    res_forced = email_notif.send_upload_notification_email(shorts_results=[short], force=True)
    assert res_forced is True
    assert len(dispatched) == 2
