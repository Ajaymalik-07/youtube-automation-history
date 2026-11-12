"""
Phase 21.1 Test Suite: OAuth Reauthorization & Live Analytics Validation
Verifies:
1. OAuth reauthorization channel-identity & scope verification before overwriting valid tokens.
2. Separation of genuine owner Analytics v2 metrics vs public Data API stats, delayed (<48h)
   metrics, and video-level unavailable metrics.
3. Unavailable metrics stored and reported as None / Unavailable (never 0).
4. Duplicate snapshot prevention for the same observation period while preserving history.
5. Unsupported/unavailable metrics blocked from influencing experiment decisions or directives.
6. Test fixture isolation preventing contamination of production output/ and .env.
"""
import os
import json
import pickle
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock
import pytest

import config
from uploader.oauth_manager import (
    reauthorize_channel,
    verify_granted_scopes,
    REQUIRED_SCOPES,
)
from apis.growth_database import HistoricalPerformanceDB, get_performance_db
from apis.youtube_analytics import (
    get_video_analytics,
    sync_owner_channel_analytics,
)
from agents.growth_analyst import (
    analyze_shorts_performance,
    analyze_longform_performance,
    generate_growth_intelligence_dossier,
    get_adaptive_production_brief,
)
from agents.adaptive_engine import generate_weekly_adaptive_strategy
from agents.experiment_tracker import ExperimentTracker


class _PersistCreds:
    def __init__(self, scopes, valid=True, refresh_token="rt_val"):
        self.scopes = list(scopes)
        self.valid = valid
        self.expired = False
        self.refresh_token = refresh_token


def test_reauthorize_rejects_channel_mismatch_without_overwriting_valid_token(tmp_path, monkeypatch):
    tok_file = tmp_path / "youtube_token.pickle"
    original_creds = _PersistCreds(["https://www.googleapis.com/auth/youtube.upload"])
    with open(tok_file, "wb") as f:
        pickle.dump(original_creds, f)

    cs_file = tmp_path / "client_secret.json"
    cs_file.write_text(json.dumps({"installed": {"client_id": "cid", "client_secret": "csec"}}))

    mock_flow_cls = MagicMock()
    mock_flow = mock_flow_cls.from_client_secrets_file.return_value
    mock_flow.authorization_url.return_value = ("http://localhost:8080/auth", "state123")
    mock_flow.run_local_server.return_value = _PersistCreds(REQUIRED_SCOPES)

    mock_build = MagicMock()
    mock_yt = mock_build.return_value
    mock_yt.channels().list.return_value.execute.return_value = {
        "items": [{"id": "UC_WRONG_CHANNEL", "snippet": {"title": "Wrong Channel"}}]
    }

    monkeypatch.setattr("uploader.oauth_manager.InstalledAppFlow", mock_flow_cls)
    monkeypatch.setattr("uploader.oauth_manager.build", mock_build)

    ok, res = reauthorize_channel(
        client_secret_file=str(cs_file),
        token_path=str(tok_file),
        open_browser=False,
        expected_channel_id="UCb1BDNY8WxoD1q_UVyEmvuw",
    )
    assert ok is False
    assert "mismatch" in res["error"].lower()

    # Original valid token must remain untouched
    with open(tok_file, "rb") as f:
        preserved = pickle.load(f)
    assert preserved.scopes == ["https://www.googleapis.com/auth/youtube.upload"]


def test_reauthorize_rejects_missing_scopes_without_overwriting_valid_token(tmp_path, monkeypatch):
    tok_file = tmp_path / "youtube_token.pickle"
    original_creds = _PersistCreds(["https://www.googleapis.com/auth/youtube.upload"])
    with open(tok_file, "wb") as f:
        pickle.dump(original_creds, f)

    cs_file = tmp_path / "client_secret.json"
    cs_file.write_text(json.dumps({"installed": {"client_id": "cid", "client_secret": "csec"}}))

    mock_flow_cls = MagicMock()
    mock_flow = mock_flow_cls.from_client_secrets_file.return_value
    mock_flow.authorization_url.return_value = ("http://localhost:8080/auth", "state123")
    # User unchecked yt-analytics.readonly on consent screen
    mock_flow.run_local_server.return_value = _PersistCreds([
        "https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/youtube.readonly",
    ])

    monkeypatch.setattr("uploader.oauth_manager.InstalledAppFlow", mock_flow_cls)

    ok, res = reauthorize_channel(
        client_secret_file=str(cs_file),
        token_path=str(tok_file),
        open_browser=False,
        expected_channel_id="UCb1BDNY8WxoD1q_UVyEmvuw",
    )
    assert ok is False
    assert "yt-analytics.readonly" in res["error"]

    with open(tok_file, "rb") as f:
        preserved = pickle.load(f)
    assert preserved.scopes == ["https://www.googleapis.com/auth/youtube.upload"]


def test_reauthorize_succeeds_after_scope_and_channel_match(tmp_path, monkeypatch):
    tok_file = tmp_path / "youtube_token.pickle"
    with open(tok_file, "wb") as f:
        pickle.dump(_PersistCreds(["https://www.googleapis.com/auth/youtube.upload"]), f)

    cs_file = tmp_path / "client_secret.json"
    cs_file.write_text(json.dumps({"installed": {"client_id": "cid", "client_secret": "csec"}}))

    mock_flow_cls = MagicMock()
    mock_flow = mock_flow_cls.from_client_secrets_file.return_value
    mock_flow.authorization_url.return_value = ("http://localhost:8080/auth", "state123")
    mock_flow.run_local_server.return_value = _PersistCreds(REQUIRED_SCOPES)

    mock_build = MagicMock()
    mock_yt = mock_build.return_value
    mock_yt.channels().list.return_value.execute.return_value = {
        "items": [{"id": "UCb1BDNY8WxoD1q_UVyEmvuw", "snippet": {"title": "Stories Malik"}}]
    }

    monkeypatch.setattr("uploader.oauth_manager.InstalledAppFlow", mock_flow_cls)
    monkeypatch.setattr("uploader.oauth_manager.build", mock_build)

    ok, res = reauthorize_channel(
        client_secret_file=str(cs_file),
        token_path=str(tok_file),
        open_browser=False,
        expected_channel_id="UCb1BDNY8WxoD1q_UVyEmvuw",
    )
    assert ok is True
    assert res["channel_id"] == "UCb1BDNY8WxoD1q_UVyEmvuw"
    assert res["channel_title"] == "Stories Malik"
    with open(tok_file, "rb") as f:
        updated = pickle.load(f)
    scopes_ok, _ = verify_granted_scopes(updated)
    assert scopes_ok is True


def test_owner_analytics_retrieval_distinguishes_retrieved_delayed_and_unavailable(monkeypatch):
    now = datetime.now(timezone.utc)
    mature_ts = (now - timedelta(days=5)).isoformat()
    fresh_ts = (now - timedelta(hours=6)).isoformat()

    monkeypatch.setattr(config, "YOUTUBE_CHANNEL_ID", "UCb1BDNY8WxoD1q_UVyEmvuw")
    monkeypatch.setattr("apis.youtube_analytics.get_analytics_capabilities_and_limitations", lambda: {
        "oauth_token_exists": True,
        "oauth_valid": True,
        "has_analytics_scope": True,
        "has_youtube_readonly_scope": True,
        "has_public_data_api_fallback": True,
        "missing_scopes": [],
        "owner_analytics_connected": True,
        "limitations": ["impressions/CTR unavailable on standard v2 query"],
    })

    mock_yt = MagicMock()
    mock_yt.channels().list.return_value.execute.return_value = {
        "items": [{"id": "UCb1BDNY8WxoD1q_UVyEmvuw", "contentDetails": {"relatedPlaylists": {"uploads": "UU_TEST"}}}]
    }
    mock_yt.playlistItems().list.return_value.execute.return_value = {
        "items": [
            {"contentDetails": {"videoId": "lf_mature"}},
            {"contentDetails": {"videoId": "sh_fresh"}},
        ]
    }
    mock_yt.videos().list.return_value.execute.return_value = {
        "items": [
            {
                "id": "lf_mature",
                "snippet": {"title": "Dwarka Underwater Ruins", "publishedAt": mature_ts},
                "statistics": {"viewCount": "1200", "likeCount": "80", "commentCount": "14"},
                "contentDetails": {"duration": "PT10M15S"},
            },
            {
                "id": "sh_fresh",
                "snippet": {"title": "Kailash Temple Mystery #Shorts", "publishedAt": fresh_ts},
                "statistics": {"viewCount": "5", "likeCount": "1", "commentCount": "0"},
                "contentDetails": {"duration": "PT45S"},
            },
        ]
    }
    monkeypatch.setattr("uploader.youtube._get_service", lambda: mock_yt)

    def fake_query_analytics(**kwargs):
        if kwargs.get("dimensions") == "insightTrafficSourceType":
            if kwargs.get("filters") == "video==lf_mature":
                return {"ok": True, "rows": [["YT_SEARCH", 700, 2100.0], ["BROWSE_FEATURES", 500, 1500.0]]}
            return {"ok": True, "rows": []}
        if kwargs.get("filters") == "video==lf_mature":
            return {"ok": True, "rows": [[1200, 3600.0, 180.0, 29.3, 80, 14, 15]]}
        # Fresh Short <48h old: empty Analytics v2 row due to latency
        return {"ok": True, "rows": []}

    monkeypatch.setattr("apis.youtube_analytics.query_analytics_report", fake_query_analytics)

    sync_res = sync_owner_channel_analytics(days_back=30)
    assert sync_res["ok"] is True
    assert sync_res["channel_verified"] is True
    assert sync_res["owner_analytics_videos_count"] == 1
    assert "sh_fresh" in sync_res["delayed_videos"]
    assert "estimatedMinutesWatched" in sync_res["metrics_retrieved"]
    assert "impressions" in sync_res["metrics_unavailable_at_video_level"]
    assert "returningViewers" in sync_res["metrics_unavailable_at_video_level"]

    db = get_performance_db()
    lf_rec = db.get_video("lf_mature")
    assert lf_rec["owner_analytics_available"] is True
    assert lf_rec["latest_metrics"]["watch_time_minutes"] == 3600.0
    assert lf_rec["latest_metrics"]["impressions"] is None
    assert lf_rec["latest_metrics"]["ctr"] is None
    assert lf_rec["latest_metrics"]["returning_viewers"] is None

    sh_rec = db.get_video("sh_fresh")
    assert sh_rec["owner_analytics_available"] is False
    assert sh_rec["latest_metrics"]["watch_time_minutes"] is None
    assert sh_rec["latest_metrics"]["average_percentage_viewed"] is None


def test_missing_analytics_scope_never_substitutes_public_stats_as_private_metrics(monkeypatch):
    monkeypatch.setattr("apis.youtube_analytics._get_analytics_service", lambda: (None, {
        "error": "insufficient_scope",
        "message": "Token lacks yt-analytics.readonly",
    }))
    monkeypatch.setattr(config, "YOUTUBE_API_KEY", "")

    res = get_video_analytics("vid_no_scope", is_shorts=True, channel_id="UCb1BDNY8WxoD1q_UVyEmvuw")
    assert res["ok"] is False
    assert res["owner_analytics_available"] is False
    assert res["metrics"]["estimatedMinutesWatched"] is None
    assert res["metrics"]["averageViewDuration"] is None
    assert res["metrics"]["averageViewPercentage"] is None
    assert res["metrics"]["subscribersGained"] is None
    assert "estimatedMinutesWatched" in res["metrics_unavailable"]


def test_duplicate_snapshot_prevention_preserves_history(tmp_path):
    db = HistoricalPerformanceDB(db_path=str(tmp_path / "dedup_db.json"))

    db.record_snapshot(
        video_id="vid_dedup",
        video_format="longform",
        topic="Nalanda",
        content_pillar="History Behind Famous Monuments & Places",
        publication_timestamp="2026-11-01T10:00:00Z",
        video_duration=600.0,
        title="Nalanda University",
        views=100,
        watch_time_minutes=200.0,
        average_percentage_viewed=40.0,
        checkpoint="owner_sync_30d",
        observation_period="2026-10-13..2026-11-12",
        owner_analytics_available=True,
    )
    # Second sync for the exact same observation period must NOT append duplicate
    db.record_snapshot(
        video_id="vid_dedup",
        video_format="longform",
        topic="Nalanda",
        content_pillar="History Behind Famous Monuments & Places",
        publication_timestamp="2026-11-01T10:00:00Z",
        video_duration=600.0,
        title="Nalanda University",
        views=100,
        watch_time_minutes=200.0,
        average_percentage_viewed=40.0,
        checkpoint="owner_sync_30d",
        observation_period="2026-10-13..2026-11-12",
        owner_analytics_available=True,
    )
    rec = db.get_video("vid_dedup")
    assert len(rec["snapshot_history"]) == 1

    # Different observation period appends cleanly while preserving earlier snapshot
    db.record_snapshot(
        video_id="vid_dedup",
        video_format="longform",
        topic="Nalanda",
        content_pillar="History Behind Famous Monuments & Places",
        publication_timestamp="2026-11-01T10:00:00Z",
        video_duration=600.0,
        title="Nalanda University",
        views=150,
        watch_time_minutes=310.0,
        average_percentage_viewed=42.0,
        checkpoint="owner_sync_30d",
        observation_period="2026-10-14..2026-11-13",
        owner_analytics_available=True,
    )
    rec2 = db.get_video("vid_dedup")
    assert len(rec2["snapshot_history"]) == 2
    assert rec2["snapshot_history"][0]["metrics"]["views"] == 100
    assert rec2["snapshot_history"][1]["metrics"]["views"] == 150


def test_unavailable_metrics_marked_unavailable_not_zero_in_reports_and_experiments(tmp_path):
    db = get_performance_db()
    now_iso = datetime.now(timezone.utc).isoformat()
    db.record_snapshot(
        video_id="pub_only_sh",
        video_format="short",
        topic="Chola Navy",
        content_pillar="Indian Kings, Empires & Dynasties",
        publication_timestamp=now_iso,
        video_duration=45.0,
        title="How Chola Navy Conquered? #Shorts",
        views=120,
        watch_time_minutes=None,
        average_view_duration_seconds=None,
        average_percentage_viewed=None,
        impressions=None,
        ctr=None,
        subscribers_gained=None,
        owner_analytics_available=False,
    )
    db.record_snapshot(
        video_id="pub_only_lf",
        video_format="longform",
        topic="Indus Valley",
        content_pillar="Ancient Indian Civilizations",
        publication_timestamp=now_iso,
        video_duration=650.0,
        title="Indus Valley Secrets",
        views=40,
        watch_time_minutes=None,
        average_view_duration_seconds=None,
        average_percentage_viewed=None,
        impressions=None,
        ctr=None,
        subscribers_gained=None,
        owner_analytics_available=False,
    )

    dossier = generate_growth_intelligence_dossier()
    assert dossier["shorts_performance"]["observed_avg_apv"] is None
    assert dossier["shorts_performance"]["total_watch_time_minutes"] is None
    assert dossier["shorts_performance"]["sub_conversion_per_1k"] is None
    assert dossier["longform_performance"]["packaging_diagnostics"]["total_impressions"] is None
    assert dossier["longform_performance"]["packaging_diagnostics"]["ctr_available"] is False
    assert dossier["longform_performance"]["storytelling_diagnostics"]["avg_percentage_viewed"] is None

    md_path = os.path.join(config.OUTPUT_DIR, "weekly_growth_intelligence.md")
    md_text = open(md_path, encoding="utf-8").read()
    assert "Unavailable (pending Analytics OAuth)" in md_text

    strategy = generate_weekly_adaptive_strategy()
    assert strategy["statistical_evaluation"]["shorts_retention"]["available"] is False
    assert strategy["statistical_evaluation"]["shorts_retention"]["observed_apv_mean"] is None

    brief = get_adaptive_production_brief()
    assert "unavailable" in brief["shorts_pacing_directive"].lower()
    assert "unavailable" in brief["longform_pacing_directive"].lower()
    assert brief["ctr_analytics_available"] is False

    # Unavailable metric (None) must NOT be accepted into experiment tracker
    tracker = ExperimentTracker(storage_path=str(tmp_path / "exp_guard.json"))
    with pytest.raises(ValueError, match="unavailable"):
        tracker.record_experiment_sample("EXP-001", "pub_only_sh", "test", None)


def test_test_fixtures_isolated_from_production_output():
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    prod_output = os.path.abspath(os.path.join(repo_root, "output"))
    assert os.path.abspath(config.OUTPUT_DIR) != prod_output

