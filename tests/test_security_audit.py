"""
Security & Credential Audit Tests for YAAS Overhaul.
Verifies secrets prevention, OAuth file protection, safe process termination,
and sanitized review endpoints.
"""
import os
import re
import pytest
from review.app import app


def test_no_hardcoded_google_api_keys_in_code():
    """Ensure no real Google/Gemini API keys (AIzaSy...) are hardcoded in python files."""
    key_pattern = re.compile(r"AIzaSy[A-Za-z0-9_-]{33}")
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    for dirpath, _, filenames in os.walk(root_dir):
        if any(skip in dirpath for skip in [".git", ".venv", "venv", "__pycache__", "output"]):
            continue
        for fname in filenames:
            if fname.endswith(".py"):
                fpath = os.path.join(dirpath, fname)
                with open(fpath, encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    matches = key_pattern.findall(content)
                    assert len(matches) == 0, f"Potential raw API key found in {fpath}: {matches}"


def test_gitignore_protects_credentials():
    """Ensure .gitignore explicitly mentions sensitive OAuth and environment files."""
    gitignore_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".gitignore")
    assert os.path.exists(gitignore_path)
    with open(gitignore_path, encoding="utf-8") as f:
        content = f.read()

    assert ".env" in content
    assert "client_secret.json" in content
    assert "youtube_token.pickle" in content


def test_no_hard_process_kill_in_review_app():
    """Ensure review/app.py uses cooperative shutdown instead of os.kill(os.getpid(), 9)."""
    review_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "review", "app.py")
    with open(review_path, encoding="utf-8") as f:
        content = f.read()

    assert "os.kill(os.getpid(), 9)" not in content
    assert "make_server" in content
    assert "shutdown" in content


def test_review_data_endpoint_sanitizes_video_path():
    """Ensure /api/data never leaks internal video filesystem path."""
    with app.test_client() as client:
        import review.app as review_app
        review_app._state["review_data"] = {
            "video_path": "d:/secret/internal/path/video.mp4",
            "script": {"title": "Test Title"},
            "research": {"topic": "Indus Valley"},
        }
        res = client.get("/api/data")
        assert res.status_code == 200
        data = res.get_json()
        assert "video_path" not in data
        assert data["script"]["title"] == "Test Title"
