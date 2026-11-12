import json
import os
from unittest.mock import MagicMock, patch

import pytest

import config
from apis.growth_database import HistoricalPerformanceDB
from apis.state_store import (
    create_state_backup,
    reconcile_branch_schedule_state,
    restore_from_sqlite,
    restore_state_backup,
    sync_to_sqlite,
)
from agents.adaptive_engine import generate_weekly_adaptive_strategy
from uploader.safety import PublishingState, record_production_state
from uploader.youtube import reconcile_channel_publications


def _mock_yt_service(items):
    svc = MagicMock()
    svc.channels.return_value.list.return_value.execute.return_value = {
        "items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UUtest"}}}]
    }
    svc.playlistItems.return_value.list.return_value.execute.return_value = {
        "items": [{"contentDetails": {"videoId": it["id"]}} for it in items]
    }
    svc.videos.return_value.list.return_value.execute.return_value = {"items": items}
    return svc


def test_reconcile_four_categories_and_no_fabrication(tmp_path):
    out_dir = str(tmp_path)
    # 1. Production DB record (verified_production_record)
    record_production_state(
        str(tmp_path / "v1.mp4"),
        PublishingState.PUBLISHED.value,
        metadata={"youtube_id": "VID_PROD_1", "job_id": "job-1"},
    )
    # 2. Schedule _url slot key only (verified_upload_incomplete_local_history)
    sched_path = tmp_path / "automation_schedule.json"
    sched_path.write_text(
        json.dumps(
            {
                "last_short_pub_2026-11-12_12": "2026-11-12T06:30:00Z",
                "last_short_pub_2026-11-12_12_url": "https://www.youtube.com/watch?v=VID_SCHED_2",
                "history_runs": [],
            }
        ),
        encoding="utf-8",
    )
    # 3. Backup schedule only (verified_upload_incomplete_local_history)
    bkp_dir = tmp_path / "backups" / "snap_1"
    bkp_dir.mkdir(parents=True)
    (bkp_dir / "automation_schedule.json").write_text(
        json.dumps({"history_runs": [{"type": "longform", "url": "https://www.youtube.com/watch?v=VID_BKP_3", "title": "Recovered Longform"}]}),
        encoding="utf-8",
    )

    items = [
        {
            "id": "VID_PROD_1",
            "snippet": {"channelId": config.YOUTUBE_CHANNEL_ID, "title": "Prod Video #Shorts #History", "publishedAt": "2026-11-12T03:30:00Z"},
            "status": {"privacyStatus": "public"},
            "contentDetails": {"duration": "PT55S"},
        },
        {
            "id": "VID_SCHED_2",
            "snippet": {"channelId": config.YOUTUBE_CHANNEL_ID, "title": "Scheduled Slot Video #Shorts #History", "publishedAt": "2026-11-12T06:30:00Z"},
            "status": {"privacyStatus": "public"},
            "contentDetails": {"duration": "PT58S"},
            "statistics": {"viewCount": "12", "likeCount": "1", "commentCount": "0"},
        },
        {
            "id": "VID_BKP_3",
            "snippet": {"channelId": config.YOUTUBE_CHANNEL_ID, "title": "Backup Recovered Video", "publishedAt": "2026-11-11T13:30:00Z"},
            "status": {"privacyStatus": "public"},
            "contentDetails": {"duration": "PT480S"},
        },
        {
            "id": "VID_EXT_4",
            "snippet": {"channelId": config.YOUTUBE_CHANNEL_ID, "title": "Manual Channel Trailer", "publishedAt": "2026-11-10T10:00:00Z"},
            "status": {"privacyStatus": "public"},
            "contentDetails": {"duration": "PT90S"},
        },
        {
            "id": "VID_UNREC_5",
            "snippet": {"channelId": config.YOUTUBE_CHANNEL_ID, "title": "Ancient Mystery: Lost Temple #Shorts #History", "publishedAt": "2026-11-09T06:30:00Z"},
            "status": {"privacyStatus": "public"},
            "contentDetails": {"duration": "PT50S"},
        },
    ]

    report = reconcile_channel_publications(
        output_dir=out_dir,
        youtube_service=_mock_yt_service(items),
        include_git_main_state=False,
    )

    assert report["live_videos_inspected"] == 5
    assert report["category_counts"] == {
        "verified_production_record": 1,
        "verified_upload_incomplete_local_history": 2,
        "external_or_manual_upload": 1,
        "unrecoverable_historical_record": 1,
    }
    assert report["reconciliation_coverage_pct"] == 60.0

    by_id = {v["video_id"]: v for v in report["videos"]}
    assert by_id["VID_PROD_1"]["classification"] == "verified_production_record"
    assert by_id["VID_SCHED_2"]["classification"] == "verified_upload_incomplete_local_history"
    assert by_id["VID_BKP_3"]["classification"] == "verified_upload_incomplete_local_history"
    assert by_id["VID_EXT_4"]["classification"] == "external_or_manual_upload"
    assert by_id["VID_UNREC_5"]["classification"] == "unrecoverable_historical_record"

    # Verify recovered HDB entries preserve IDs and do not fabricate private analytics
    hdb = HistoricalPerformanceDB(db_path=str(tmp_path / "historical_performance_db.json"))
    rec2 = hdb.get_video("VID_SCHED_2")
    assert rec2 is not None
    assert rec2["owner_analytics_available"] is False
    assert rec2["latest_metrics"]["average_percentage_viewed"] is None
    assert rec2["latest_metrics"]["watch_time_minutes"] is None
    assert rec2["latest_metrics"]["impressions"] is None
    assert rec2["latest_metrics"]["ctr"] is None

    # Re-running reconciliation must not duplicate HDB records or snapshots
    report2 = reconcile_channel_publications(
        output_dir=out_dir,
        youtube_service=_mock_yt_service(items),
        include_git_main_state=False,
    )
    assert report2["recovered_historical_count"] == 0
    assert len(hdb.get_video("VID_SCHED_2")["snapshot_history"]) == 1


def test_branch_schedule_reconciliation_and_sqlite_backup_parity(tmp_path):
    out_dir = str(tmp_path)
    local_sched = {
        "last_short_pub_2026-11-04_9": "2026-11-04T09:00:00+05:30",
        "last_short_pub_2026-11-04_9_url": "https://www.youtube.com/watch?v=LOCAL_VID",
        "history_runs": [{"type": "short", "url": "https://www.youtube.com/watch?v=LOCAL_VID", "date_ist": "2026-11-04T09:00:00+05:30"}],
    }
    (tmp_path / "automation_schedule.json").write_text(json.dumps(local_sched), encoding="utf-8")

    incoming_main_sched = {
        "last_short_pub_2026-11-12_12": "2026-11-12T12:00:00+05:30",
        "last_short_pub_2026-11-12_12_url": "https://www.youtube.com/watch?v=MAIN_CI_VID",
        "history_runs": [{"type": "short", "url": "https://www.youtube.com/watch?v=MAIN_CI_VID", "date_ist": "2026-11-12T12:00:00+05:30"}],
    }

    res = reconcile_branch_schedule_state(output_dir=out_dir, incoming_schedule=incoming_main_sched)
    assert res["merged"] is True
    assert res["merged_history_runs"] == 2
    assert res["new_url_keys_added"] == 1

    merged = json.loads((tmp_path / "automation_schedule.json").read_text(encoding="utf-8"))
    assert merged["last_short_pub_2026-11-04_9_url"].endswith("LOCAL_VID")
    assert merged["last_short_pub_2026-11-12_12_url"].endswith("MAIN_CI_VID")

    # Backup + SQLite parity check
    bkp = create_state_backup(out_dir, label="phase23_1_test")
    sync_to_sqlite(out_dir)

    # Corrupt/remove schedule and restore from SQLite
    (tmp_path / "automation_schedule.json").unlink()
    restore_from_sqlite(out_dir)
    assert (tmp_path / "automation_schedule.json").exists()

    # Corrupt again and restore from backup
    (tmp_path / "automation_schedule.json").unlink()
    restore_state_backup(bkp["backup_dir"], base_dir=out_dir)
    restored = json.loads((tmp_path / "automation_schedule.json").read_text(encoding="utf-8"))
    assert len(restored["history_runs"]) == 2


def test_adaptive_engine_ignores_unverified_or_mock_apv(tmp_path):
    db = HistoricalPerformanceDB(db_path=str(tmp_path / "historical_performance_db.json"))
    # Record 1: Public-only record where APV is None
    db.record_snapshot(
        video_id="PUB_ONLY_1",
        video_format="short",
        topic="Iron Pillar",
        content_pillar="Ancient India",
        publication_timestamp="2026-11-12T06:30:00Z",
        video_duration=55.0,
        title="Iron Pillar #Shorts",
        views=10,
        average_percentage_viewed=None,
        owner_analytics_available=False,
    )
    # Record 2: Mocked/unverified record that accidentally has numeric APV but owner_analytics_available=False
    db.record_snapshot(
        video_id="UNVERIFIED_2",
        video_format="short",
        topic="Kailash Temple",
        content_pillar="Ancient India",
        publication_timestamp="2026-11-12T03:30:00Z",
        video_duration=58.0,
        title="Kailash Temple #Shorts",
        views=20,
        average_percentage_viewed=95.0,
        owner_analytics_available=False,
    )

    strategy = generate_weekly_adaptive_strategy(db_override=db, evaluation_window_days=30)

    assert strategy["statistical_evaluation"]["shorts_retention"]["available"] is False
    assert strategy["statistical_evaluation"]["shorts_retention"]["observed_apv_mean"] is None
    assert strategy["statistical_evaluation"]["shorts_retention"]["sample_size"] == 0
