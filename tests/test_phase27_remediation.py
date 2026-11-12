import json
from unittest.mock import MagicMock, patch

from agents.seo_optimizer import (
    optimize_for_100_percent,
    sanitize_title_duplicate_prefix,
    validate_youtube_metadata,
)
from uploader.safety import (
    PublishingState,
    is_eligible_for_upload,
    probe_media_duration,
    record_production_state,
    validate_format_and_duration_contract,
)


def _mock_ffprobe_json(duration=None, returncode=0, streams=None):
    proc = MagicMock()
    proc.returncode = returncode
    proc.stderr = "" if returncode == 0 else "Invalid data found when processing input"
    if returncode != 0:
        proc.stdout = ""
    else:
        payload = {
            "format": {} if duration is None else {"duration": str(duration)},
            "streams": streams if streams is not None else [{"codec_type": "video"}, {"codec_type": "audio"}],
        }
        proc.stdout = json.dumps(payload)
    return proc


def test_workstream1_shorts_duration_boundaries_and_corrupt_media(tmp_path):
    f = tmp_path / "short.mp4"
    f.write_bytes(b"\x00" * 2048)

    # 59.5s Short accepted
    with patch("subprocess.run", return_value=_mock_ffprobe_json(59.5)):
        ok, err, info = validate_format_and_duration_contract(str(f), "short", expected_duration_seconds=59.0)
        assert ok is True
        assert err is None
        assert info["actual_duration_seconds"] == 59.5
        assert info["duration_delta_seconds"] == 0.5

    # 60.0s Short accepted (exact configured boundary)
    with patch("subprocess.run", return_value=_mock_ffprobe_json(60.0)):
        ok, err, _ = validate_format_and_duration_contract(str(f), "short")
        assert ok is True

    # 60.01s Short rejected
    with patch("subprocess.run", return_value=_mock_ffprobe_json(60.01)):
        ok, err, _ = validate_format_and_duration_contract(str(f), "short")
        assert ok is False
        assert "exceeds configured maximum" in err

    # 64.0s Short rejected
    with patch("subprocess.run", return_value=_mock_ffprobe_json(64.0)):
        ok, err, _ = validate_format_and_duration_contract(str(f), "short")
        assert ok is False

    # Missing duration metadata rejected
    with patch("subprocess.run", return_value=_mock_ffprobe_json(duration=None)):
        ok, err, _ = validate_format_and_duration_contract(str(f), "short")
        assert ok is False
        assert "Missing duration metadata" in err

    # Corrupt media rejected
    with patch("subprocess.run", return_value=_mock_ffprobe_json(returncode=1)):
        probe = probe_media_duration(str(f))
        assert probe["ok"] is False
        ok, err, _ = validate_format_and_duration_contract(str(f), "short")
        assert ok is False

    # Blocked Short cannot pass is_eligible_for_upload()
    record_production_state(
        str(f),
        PublishingState.VIDEO_VALIDATED.value,
        metadata={"declared_format": "short", "actual_duration_seconds": 64.0},
    )
    eligible, reason = is_eligible_for_upload(str(f))
    assert eligible is False
    assert "64.00s" in reason


def test_workstream2_format_contract_and_contradictions(tmp_path):
    f = tmp_path / "doc.mp4"
    f.write_bytes(b"\x00" * 2048)

    # Valid Long-Form (520s) accepted
    with patch("subprocess.run", return_value=_mock_ffprobe_json(520.0)):
        ok, err, _ = validate_format_and_duration_contract(str(f), "longform", metadata_format="longform", db_format="longform")
        assert ok is True

    # 71s and 73s declared Long-Form rejected
    for bad_dur in (71.0, 73.0):
        with patch("subprocess.run", return_value=_mock_ffprobe_json(bad_dur)):
            ok, err, _ = validate_format_and_duration_contract(str(f), "longform")
            assert ok is False
            assert "below configured minimum" in err

    # Missing format metadata rejected
    with patch("subprocess.run", return_value=_mock_ffprobe_json(520.0)):
        ok, err, _ = validate_format_and_duration_contract(str(f), None)
        assert ok is False
        assert "Missing or invalid declared_format" in err

    # Contradictory db_format and metadata_format rejected
    with patch("subprocess.run", return_value=_mock_ffprobe_json(520.0)):
        ok, err, _ = validate_format_and_duration_contract(str(f), "longform", db_format="short")
        assert ok is False
        assert "Contradictory format contract" in err


def test_workstream3_duplicate_hook_prefix_remediation():
    cases = [
        (
            "This 1600YearOld Iron: Why Has This 1,600-Year-Old Iron Pillar Never Rusted? #Shorts",
            "Why Has This 1,600-Year-Old Iron Pillar Never Rusted? #Shorts",
        ),
        (
            "Shivajis secret escape: Shivaji's secret escape in a fruit basket!",
            "Shivaji's secret escape in a fruit basket!",
        ),
        (
            "Aurangzeb Jailed Father: Why Aurangzeb Jailed His Own Father?",
            "Why Aurangzeb Jailed His Own Father?",
        ),
        (
            "Indias Chola Navy: How India's Chola Navy Conquered 8 Countries",
            "How India's Chola Navy Conquered 8 Countries",
        ),
        (
            "समरट रहसय: Lost Wealth Secret: सम्राट अशोक का गुप्त खजाना और अरबों की खोज",
            "सम्राट अशोक का गुप्त खजाना और अरबों की खोज",
        ),
    ]
    for raw, expected in cases:
        assert sanitize_title_duplicate_prefix(raw) == expected
        ok, issues = validate_youtube_metadata(raw, "A" * 160, ["History"], is_shorts=True)
        assert ok is False
        assert any("duplicated hook prefix" in iss for iss in issues)

    opt = optimize_for_100_percent(
        title="Aurangzeb Jailed Father: Why Aurangzeb Jailed His Own Father?",
        description="A" * 180,
        tags=["Mughal History"],
        is_shorts=True,
    )
    assert opt["title"] == "Why Aurangzeb Jailed His Own Father?"

