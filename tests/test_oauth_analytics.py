"""
Unit and Integration Tests for OAuth Scope Management, Video Processing Verification,
and YouTube Analytics API v2
Phase 18.1 Test Suite
"""
import os
import json
import pickle
import pytest
from unittest.mock import MagicMock, patch
from googleapiclient.errors import HttpError
from uploader.oauth_manager import (
    audit_token_scopes,
    reauthorize_channel,
    safe_refresh_credentials,
    REQUIRED_SCOPES,
)
from uploader.youtube import verify_upload_and_processing, upload_to_youtube
from apis.youtube_analytics import (
    get_video_analytics,
    query_analytics_report,
    generate_weekly_format_report,
)
from uploader.safety import record_production_state, get_production_record, PublishingState


@pytest.fixture(autouse=True)
def isolate_analytics_files(tmp_path, monkeypatch):
    """Isolate analytics snapshots, weekly reports, and growth DB from real output/ during tests."""
    import apis.youtube_analytics as ya
    import apis.growth_database as gdb

    monkeypatch.setattr(ya, "SNAPSHOT_FILE", str(tmp_path / "analytics_snapshots.json"))
    monkeypatch.setattr(ya, "WEEKLY_REPORT_FILE", str(tmp_path / "weekly_analytics_report.json"))
    monkeypatch.setattr(gdb, "DB_FILE", str(tmp_path / "historical_performance_db.json"))
    monkeypatch.setattr(gdb, "LEGACY_SNAPSHOT_FILE", str(tmp_path / "legacy_snapshots.json"))
    monkeypatch.setattr(gdb, "_db_instance", gdb.HistoricalPerformanceDB(db_path=str(tmp_path / "historical_performance_db.json")))
    yield


class DummyCreds:
    def __init__(self, scopes=None, valid=True, expired=False, refresh_token="dummy_refresh"):
        self.scopes = scopes or []
        self.valid = valid
        self.expired = expired
        self.refresh_token = refresh_token

    def refresh(self, request):
        self.valid = True
        self.expired = False


# ─────────────────────────────────────────────────────────────
# 1. OAuth Scope Audit & Token Tests
# ─────────────────────────────────────────────────────────────

def test_oauth_missing_scopes_detection(tmp_path):
    token_file = tmp_path / "test_token.pickle"
    creds = DummyCreds(scopes=["https://www.googleapis.com/auth/youtube.upload"])
    with open(token_file, "wb") as f:
        pickle.dump(creds, f)

    audit = audit_token_scopes(str(token_file))
    assert audit["exists"] is True
    assert audit["valid"] is True
    assert audit["is_fully_authorized"] is False
    assert "https://www.googleapis.com/auth/youtube.readonly" in audit["missing_scopes"]
    assert "https://www.googleapis.com/auth/yt-analytics.readonly" in audit["missing_scopes"]
    assert len(audit["missing_descriptions"]) == 2


def test_oauth_all_scopes_granted(tmp_path):
    token_file = tmp_path / "test_full_token.pickle"
    creds = DummyCreds(scopes=REQUIRED_SCOPES)
    with open(token_file, "wb") as f:
        pickle.dump(creds, f)

    audit = audit_token_scopes(str(token_file))
    assert audit["exists"] is True
    assert audit["is_fully_authorized"] is True
    assert len(audit["missing_scopes"]) == 0


def test_oauth_reauthorization_backup_and_recovery(tmp_path, monkeypatch):
    token_file = tmp_path / "youtube_token.pickle"
    creds = DummyCreds(scopes=["https://www.googleapis.com/auth/youtube.upload"])
    with open(token_file, "wb") as f:
        pickle.dump(creds, f)

    secret_file = tmp_path / "client_secret.json"
    secret_file.write_text(json.dumps({"installed": {"client_id": "test", "client_secret": "test"}}))

    # Mock InstalledAppFlow to simulate user cancelling authorization
    mock_flow_cls = MagicMock()
    mock_flow = mock_flow_cls.from_client_secrets_file.return_value
    mock_flow.authorization_url.return_value = ("http://auth_url", "state")
    mock_flow.run_local_server.side_effect = RuntimeError("User closed the browser window.")

    monkeypatch.setattr("uploader.oauth_manager.InstalledAppFlow", mock_flow_cls)
    monkeypatch.setattr("uploader.oauth_manager.BACKUP_TOKEN_FILE", str(tmp_path / "youtube_token.pickle.bak"))

    ok, res = reauthorize_channel(
        client_secret_file=str(secret_file),
        token_path=str(token_file),
        open_browser=False,
    )
    assert ok is False
    assert "User closed the browser window" in res["error"]

    # Verify backup was restored and working upload token is preserved
    assert os.path.exists(token_file)
    with open(token_file, "rb") as f:
        restored_creds = pickle.load(f)
    assert restored_creds.scopes == ["https://www.googleapis.com/auth/youtube.upload"]


def test_oauth_reauthorization_success(tmp_path, monkeypatch):
    token_file = tmp_path / "youtube_token.pickle"
    secret_file = tmp_path / "client_secret.json"
    secret_file.write_text(json.dumps({"installed": {"client_id": "test", "client_secret": "test"}}))

    mock_flow_cls = MagicMock()
    mock_flow = mock_flow_cls.from_client_secrets_file.return_value
    mock_flow.authorization_url.return_value = ("http://auth_url", "state")
    new_creds = DummyCreds(scopes=REQUIRED_SCOPES)
    mock_flow.run_local_server.return_value = new_creds

    mock_build = MagicMock()
    mock_yt = mock_build.return_value
    mock_yt.channels().list.return_value.execute.return_value = {
        "items": [{"id": "UC_TEST_CHANNEL", "snippet": {"title": "Stories Malik Official"}}]
    }

    monkeypatch.setattr("uploader.oauth_manager.InstalledAppFlow", mock_flow_cls)
    monkeypatch.setattr("uploader.oauth_manager.build", mock_build)
    monkeypatch.setattr("uploader.oauth_manager.BACKUP_TOKEN_FILE", str(tmp_path / "youtube_token.pickle.bak"))

    ok, res = reauthorize_channel(
        client_secret_file=str(secret_file),
        token_path=str(token_file),
        open_browser=False,
    )
    assert ok is True
    assert res["channel_title"] == "Stories Malik Official"
    assert res["channel_id"] == "UC_TEST_CHANNEL"
    assert os.path.exists(token_file)


def test_oauth_invalid_token_and_refresh(tmp_path):
    creds = DummyCreds(scopes=REQUIRED_SCOPES, valid=False, expired=True, refresh_token="valid_rt")
    token_file = tmp_path / "refresh_test.pickle"
    with open(token_file, "wb") as f:
        pickle.dump(creds, f)

    refreshed = safe_refresh_credentials(creds, str(token_file))
    assert refreshed is True
    assert creds.valid is True

    # No refresh token available
    creds_no_rt = DummyCreds(scopes=REQUIRED_SCOPES, valid=False, expired=True, refresh_token=None)
    assert safe_refresh_credentials(creds_no_rt, str(token_file)) is False


# ─────────────────────────────────────────────────────────────
# 2. Video Processing Verification Tests
# ─────────────────────────────────────────────────────────────

def test_video_processing_status_pending():
    mock_yt = MagicMock()
    mock_yt.videos().list.return_value.execute.return_value = {
        "items": [{
            "snippet": {"channelId": "UC_MATCH"},
            "status": {"uploadStatus": "uploaded", "privacyStatus": "private"},
            "processingDetails": {"processingStatus": "processing"},
        }]
    }

    res = verify_upload_and_processing(mock_yt, "vid_pending", expected_channel_id="UC_MATCH")
    assert res["ok"] is True
    assert res["processing_status"] == "processing"
    assert res["is_processing_complete"] is False
    assert res["is_processing_failed"] is False


def test_video_processing_status_succeeded():
    mock_yt = MagicMock()
    mock_yt.videos().list.return_value.execute.return_value = {
        "items": [{
            "snippet": {"channelId": "UC_MATCH"},
            "status": {"uploadStatus": "processed", "privacyStatus": "private"},
            "processingDetails": {"processingStatus": "succeeded"},
        }]
    }

    res = verify_upload_and_processing(mock_yt, "vid_ok", expected_channel_id="UC_MATCH")
    assert res["ok"] is True
    assert res["processing_status"] == "succeeded"
    assert res["is_processing_complete"] is True
    assert res["is_processing_failed"] is False


def test_video_processing_status_failed():
    mock_yt = MagicMock()
    mock_yt.videos().list.return_value.execute.return_value = {
        "items": [{
            "snippet": {"channelId": "UC_MATCH"},
            "status": {"uploadStatus": "rejected", "rejectionReason": "copyright"},
            "processingDetails": {"processingStatus": "failed", "processingFailureReason": "transcodeFailed"},
        }]
    }

    res = verify_upload_and_processing(mock_yt, "vid_fail", expected_channel_id="UC_MATCH")
    assert res["ok"] is True
    assert res["is_processing_failed"] is True
    assert res["failure_reason"] == "copyright"


def test_video_processing_unauthorized_channel():
    mock_yt = MagicMock()
    # Video belongs to UC_OTHER, not expected channel UC_AUTHORIZED
    mock_yt.videos().list.return_value.execute.return_value = {
        "items": [{
            "snippet": {"channelId": "UC_OTHER"},
            "status": {"uploadStatus": "processed"},
            "processingDetails": {"processingStatus": "succeeded"},
        }]
    }

    res = verify_upload_and_processing(mock_yt, "vid_hijack", expected_channel_id="UC_AUTHORIZED")
    assert res["ok"] is True
    assert res["channel_verified"] is False
    assert res["is_processing_failed"] is True


# ─────────────────────────────────────────────────────────────
# 3. YouTube Analytics API v2 Tests
# ─────────────────────────────────────────────────────────────

def test_analytics_response_parsing_valid(monkeypatch):
    mock_service = MagicMock()
    mock_service.reports().query.return_value.execute.return_value = {
        "columnHeaders": [{"name": "views"}, {"name": "estimatedMinutesWatched"}],
        "rows": [[1420, 2840.5, 120.0, 58.2, 85, 12, 18]],
    }
    monkeypatch.setattr("apis.youtube_analytics._get_analytics_service", lambda: (mock_service, None))

    res = get_video_analytics("vid_777", is_shorts=False, channel_id="UC_STORIES_MALIK")
    assert res["ok"] is True
    assert res["metrics"]["views"] == 1420
    assert res["metrics"]["estimatedMinutesWatched"] == 2840.5
    assert res["metrics"]["averageViewDuration"] == 120.0
    assert res["metrics"]["averageViewPercentage"] == 58.2
    assert res["metrics"]["likes"] == 85
    assert res["metrics"]["subscribersGained"] == 18
    assert res["channel_id"] == "UC_STORIES_MALIK"
    assert res["is_live_analytics"] is True


def test_analytics_empty_response_handling(monkeypatch):
    mock_service = MagicMock()
    mock_service.reports().query.return_value.execute.return_value = {
        "columnHeaders": [{"name": "views"}],
        "rows": [],  # Empty rows (no views yet)
    }
    monkeypatch.setattr("apis.youtube_analytics._get_analytics_service", lambda: (mock_service, None))

    res = get_video_analytics("vid_new", is_shorts=True, channel_id="UC_STORIES_MALIK")
    assert res["ok"] is True
    assert res["metrics"]["views"] == 0
    assert res["metrics"]["estimatedMinutesWatched"] == 0.0
    assert res["metrics"]["averageViewPercentage"] == 0.0


def test_analytics_quota_error_handling(monkeypatch):
    mock_service = MagicMock()
    resp_mock = MagicMock()
    resp_mock.status = 403
    http_err = HttpError(resp=resp_mock, content=b'{"error": {"errors": [{"reason": "quotaExceeded"}]}}')
    mock_service.reports().query.return_value.execute.side_effect = http_err

    monkeypatch.setattr("apis.youtube_analytics._get_analytics_service", lambda: (mock_service, None))

    res = query_analytics_report()
    assert res["ok"] is False
    assert res["error_type"] == "quota_error"


def test_weekly_format_separated_report():
    sample_snapshots = {
        "lf_01": {
            "title": "Dholavira Hydraulic Engineering",
            "topic": "Indus Valley Engineering",
            "is_shorts": False,
            "metrics": {
                "views": 5000,
                "estimatedMinutesWatched": 15000.0,
                "averageViewPercentage": 62.5,
                "subscribersGained": 45,
            }
        },
        "lf_02": {
            "title": "Porus & Alexander Battle",
            "topic": "Ancient Warfare",
            "is_shorts": False,
            "metrics": {
                "views": 2000,
                "estimatedMinutesWatched": 3200.0,
                "averageViewPercentage": 38.0,  # Below 45% benchmark
                "subscribersGained": 8,
            }
        },
        "sh_01": {
            "title": "Why Chandragupta Maurya Gave Up His Empire",
            "topic": "Maurya Renunciation",
            "is_shorts": True,
            "metrics": {
                "views": 25000,
                "estimatedMinutesWatched": 18000.0,
                "averageViewPercentage": 82.0,  # Above 70% benchmark
                "subscribersGained": 120,
            }
        },
        "sh_02": {
            "title": "Lost City of Dwarka Underwater",
            "topic": "Marine Archaeology",
            "is_shorts": True,
            "metrics": {
                "views": 12000,
                "estimatedMinutesWatched": 7000.0,
                "averageViewPercentage": 64.0,  # Below 70% benchmark
                "subscribersGained": 35,
            }
        },
    }

    report = generate_weekly_format_report(snapshots=sample_snapshots, days_back=7)
    lf = report["longform_analytics"]
    sh = report["shorts_analytics"]

    # Longform evaluation
    assert lf["video_count"] == 2
    assert lf["total_views"] == 7000
    assert lf["best_performer"]["video_id"] == "lf_01"
    assert any("Ancient Warfare" in w for w in lf["retention_weaknesses"])

    # Shorts evaluation
    assert sh["video_count"] == 2
    assert sh["total_views"] == 37000
    assert sh["best_performer"]["video_id"] == "sh_01"
    assert any("Marine Archaeology" in w for w in sh["retention_weaknesses"])

    # Recommendations generated
    assert len(report["recommended_future_experiments"]) >= 1
