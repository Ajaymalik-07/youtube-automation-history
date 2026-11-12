import os
import sys
import pytest

# Make the project root importable (agents/, apis/, video/, config, gui)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("STUDIO_NO_BROWSER", "1")


@pytest.fixture(autouse=True)
def isolate_production_artifacts(tmp_path, monkeypatch):
    """
    Phase 21.1 Integrity Guard:
    Ensures pytest tests can NEVER contaminate production analytics databases,
    reports, schedules, .env, or live OAuth tokens on disk.
    """
    import config
    import automation
    import apis.youtube_analytics as ya
    import apis.growth_database as gdb
    import uploader.safety as safety
    import uploader.quality_gates as qg
    import uploader.oauth_manager as om
    import agents.experiment_tracker as et

    iso_out = tmp_path / "iso_output"
    iso_out.mkdir(parents=True, exist_ok=True)

    real_env = os.path.abspath(config.ENV_PATH)
    orig_save_env = config.save_env

    def _safe_save_env(values: dict, path: str = None):
        target = os.path.abspath(path) if path else os.path.abspath(str(tmp_path / ".env.test"))
        if target == real_env:
            target = os.path.abspath(str(tmp_path / ".env.test"))
        return orig_save_env(values, path=target)

    monkeypatch.setattr(config, "OUTPUT_DIR", str(iso_out))
    monkeypatch.setattr(config, "IMAGES_DIR", str(iso_out / "images"))
    monkeypatch.setattr(config, "ENV_PATH", str(tmp_path / ".env.test"))
    monkeypatch.setattr(config, "sync_client_secret_file", lambda: None)
    monkeypatch.setattr(config, "update_youtube_token_env", lambda _bytes: None)
    monkeypatch.setattr(config, "save_env", _safe_save_env)

    monkeypatch.setattr(automation, "SCHEDULE_FILE", str(iso_out / "automation_schedule.json"))
    monkeypatch.setattr(ya, "SNAPSHOT_FILE", str(iso_out / "analytics_snapshots.json"))
    monkeypatch.setattr(ya, "WEEKLY_REPORT_FILE", str(iso_out / "weekly_analytics_report.json"))
    monkeypatch.setattr(safety, "PRODUCTION_DB_FILE", str(iso_out / "production_database.json"))
    monkeypatch.setattr(qg, "DIAGNOSTICS_DIR", str(iso_out / "diagnostics"))

    db_path = str(iso_out / "historical_performance_db.json")
    monkeypatch.setattr(gdb, "DB_FILE", db_path)
    monkeypatch.setattr(gdb, "LEGACY_SNAPSHOT_FILE", str(iso_out / "legacy_snapshots.json"))
    monkeypatch.setattr(gdb, "_db_instance", gdb.HistoricalPerformanceDB(db_path=db_path))

    exp_path = str(iso_out / "growth_experiments.json")
    monkeypatch.setattr(et, "EXPERIMENTS_FILE", exp_path)
    monkeypatch.setattr(et, "_tracker_instance", et.ExperimentTracker(storage_path=exp_path))

    monkeypatch.setattr(om, "TOKEN_FILE", str(tmp_path / "youtube_token.pickle"))
    monkeypatch.setattr(om, "BACKUP_TOKEN_FILE", str(tmp_path / "youtube_token.pickle.bak"))
    yield
