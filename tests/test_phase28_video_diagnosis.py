"""
Regression tests for Phase 28 — Video-Level Performance Diagnosis & Retention Optimization.
Covers video-level queries, format separation, missing analytics/null preservation,
reporting delays, age normalization, API error handling, statistical governance,
no public-stats substitution, recommendation provenance, cadence, and branch integrity.
"""

import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import config
from agents.phase28_video_diagnosis import (
    PHASE28_REPORT_FILES,
    classify_age_cohort,
    classify_video_format,
    collect_individual_video_analytics,
    compute_metric_stats,
    fetch_live_video_inventory,
    generate_phase28_reports,
)


def _mock_youtube_service(videos_spec):
    """Builds a minimal mock YouTube Data API v3 service without requesting public statistics."""
    yt = MagicMock()
    yt.channels.return_value.list.return_value.execute.return_value = {
        "items": [
            {
                "id": "UCb1BDNY8WxoD1q_UVyEmvuw",
                "snippet": {"title": "Stories Malik"},
                "contentDetails": {"relatedPlaylists": {"uploads": "UU_MOCK"}},
            }
        ]
    }
    yt.playlistItems.return_value.list.return_value.execute.return_value = {
        "items": [{"contentDetails": {"videoId": v["id"]}} for v in videos_spec]
    }

    def _videos_list(**kwargs):
        # Ensure public statistics are never requested as a substitute for owner analytics
        assert "statistics" not in kwargs.get("part", "")
        m = MagicMock()
        m.execute.return_value = {
            "items": [
                {
                    "id": v["id"],
                    "snippet": {
                        "title": v["title"],
                        "description": v.get("description", ""),
                        "publishedAt": v["publishedAt"],
                    },
                    "contentDetails": {"duration": v["duration"]},
                    "status": {
                        "privacyStatus": v.get("privacyStatus", "public"),
                        **({"publishAt": v["publishAt"]} if v.get("publishAt") else {}),
                    },
                }
                for v in videos_spec
            ]
        }
        return m

    yt.videos.return_value.list.side_effect = _videos_list
    return yt


def test_format_separation_and_unknown_handling():
    assert classify_video_format(45.0, "Short Title", "") == "short"
    assert classify_video_format(90.0, "Mystery #shorts", "") == "short"
    assert classify_video_format(600.0, "Documentary Title", "") == "longform"
    assert classify_video_format(0.0, "Missing Duration", "") == "unknown"


def test_sample_size_governance_rules():
    s0 = compute_metric_stats([])
    assert s0["sample_size"] == 0 and s0["mean"] is None and s0["variance"] is None

    s1 = compute_metric_stats([42.0])
    assert s1["sample_size"] == 1 and s1["variance"] is None and s1["confidence_interval_95"] is None

    s3 = compute_metric_stats([10.0, 20.0, 30.0])
    assert s3["sample_size"] == 3 and s3["variance"] is not None and s3["confidence_interval_95"] is None

    s5 = compute_metric_stats([10.0, 20.0, 30.0, 40.0, 50.0])
    assert s5["sample_size"] == 5 and s5["confidence_interval_95"] is not None


def test_publication_age_cohorts():
    assert classify_age_cohort(None, is_future_scheduled=True) == "scheduled_future"
    assert classify_age_cohort(10.0) == "lt_24h"
    assert classify_age_cohort(30.0) == "24h_to_48h"
    assert classify_age_cohort(72.0) == "48h_to_7d"
    assert classify_age_cohort(14 * 24.0) == "7d_to_28d"
    assert classify_age_cohort(35 * 24.0) == "gt_28d"


def test_end_to_end_pipeline_delays_nulls_and_provenance(tmp_path):
    now = datetime(2026, 11, 12, 10, 0, tzinfo=timezone.utc)
    videos_spec = [
        {
            "id": "VID_SHORT_OLD",
            "title": "Why did Ashoka vanish? #shorts",
            "publishedAt": (now - timedelta(days=10)).isoformat(),
            "duration": "PT42S",
        },
        {
            "id": "VID_LONG_OLD",
            "title": "The Forgotten Dynasty of Magadha",
            "publishedAt": (now - timedelta(days=12)).isoformat(),
            "duration": "PT10M15S",
        },
        {
            "id": "VID_DELAYED",
            "title": "Brand New Short #shorts",
            "publishedAt": (now - timedelta(hours=12)).isoformat(),
            "duration": "PT35S",
        },
        {
            "id": "VID_SCHED",
            "title": "Scheduled Future Video",
            "publishedAt": now.isoformat(),
            "publishAt": (now + timedelta(days=1)).isoformat(),
            "privacyStatus": "private",
            "duration": "PT8M",
        },
    ]
    yt = _mock_youtube_service(videos_spec)

    def fake_analytics(**kwargs):
        dims = kwargs.get("dimensions")
        flt = kwargs.get("filters", "")
        if dims == "day":
            return {"ok": True, "rows": [["2026-11-09", 17]]}
        if dims == "video":
            return {
                "ok": True,
                "rows": [
                    ["VID_SHORT_OLD", 120, 40.0, 28.0, 66.7, 1],
                    ["VID_LONG_OLD", 55, 82.5, 90.0, 14.6, 0],
                ],
            }
        if dims == "insightTrafficSourceType" and "VID_SHORT_OLD" in flt:
            return {"ok": True, "rows": [["SHORTS", 100, 35.0], ["YT_SEARCH", 20, 5.0]]}
        if dims == "insightTrafficSourceType" and "VID_LONG_OLD" in flt:
            return {"ok": True, "rows": [["RELATED_VIDEO", 55, 82.5]]}
        return {"ok": True, "rows": []}

    res = generate_phase28_reports(
        days_back=90,
        output_dir=str(tmp_path),
        youtube_service=yt,
        analytics_query_fn=fake_analytics,
        now_utc=now,
    )
    assert res["ok"] is True
    for fname in PHASE28_REPORT_FILES.values():
        assert (tmp_path / fname).exists()

    indiv = json.loads((tmp_path / PHASE28_REPORT_FILES["individual_analytics"]).read_text(encoding="utf-8"))
    assert indiv["summary"]["with_complete_owner_analytics"] == 2
    assert indiv["summary"]["reporting_delay_pending_count"] == 1
    assert indiv["summary"]["unpublished_scheduled_count"] == 1

    short_rec = indiv["formats"]["short"][0]
    assert short_rec["metrics"]["impressions"] is None
    assert short_rec["metrics"]["ctr"] is None
    assert short_rec["metrics"]["retention_curve"] is None

    delayed_rec = indiv["formats"]["short"][1]
    assert delayed_rec["data_availability"] == "reporting_delay_pending"
    assert delayed_rec["metrics"]["views"] is None

    ret_audit = json.loads((tmp_path / PHASE28_REPORT_FILES["retention_audit"]).read_text(encoding="utf-8"))
    assert ret_audit["measured_retention_curve_available"] is False
    assert ret_audit["audit_classification"] == "creative_content_audit"

    recs = json.loads((tmp_path / PHASE28_REPORT_FILES["recommendations"]).read_text(encoding="utf-8"))
    assert recs["cadence_preserved"]["longform_per_day"] == 1
    assert recs["cadence_preserved"]["shorts_per_day"] == 5
    assert recs["cadence_preserved"]["schedule_modified"] is False
    for r in recs["recommendations"]:
        assert r["supporting_evidence"]
        assert r["expected_benefit"]
        assert r["known_limitations"]
        assert r["requires_quality_gate"] is True


def test_invalid_or_failed_analytics_api_response(tmp_path):
    now = datetime(2026, 11, 12, 10, 0, tzinfo=timezone.utc)
    yt = _mock_youtube_service([
        {
            "id": "VID_1",
            "title": "Test Video",
            "publishedAt": (now - timedelta(days=5)).isoformat(),
            "duration": "PT50S",
        }
    ])
    inv = fetch_live_video_inventory(youtube_service=yt, now_utc=now, output_dir=str(tmp_path))
    indiv = collect_individual_video_analytics(
        inventory_report=inv,
        analytics_query_fn=lambda **kw: {"ok": False, "error_type": "api_http_error", "message": "HTTP 503"},
        now_utc=now,
    )
    assert indiv["summary"]["api_error_count"] == 1
    rec = indiv["formats"]["short"][0]
    assert rec["data_availability"] == "api_error"
    assert rec["metrics"]["views"] is None


def test_cadence_and_branch_integrity():
    assert getattr(config, "SHORTS_DAILY_COUNT", 5) == 5
    assert getattr(config, "LONGFORM_DAILY_COUNT", 1) == 1
    branch = subprocess.check_output(["git", "branch", "--show-current"], text=True).strip()
    assert branch == "feature/youtube-growth-overhaul"

