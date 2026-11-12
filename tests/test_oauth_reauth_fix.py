import pickle
from unittest.mock import MagicMock, patch

from uploader import oauth_manager
from uploader.oauth_manager import REQUIRED_SCOPES, reauthorize_channel


class _DummyCreds:
    def __init__(self, scopes, valid=True, token="SECRET_ACCESS_TOKEN_XYZ", refresh_token="SECRET_REFRESH_TOKEN_ABC"):
        self.scopes = list(scopes)
        self.valid = valid
        self.expired = False
        self.token = token
        self.refresh_token = refresh_token


def test_reauthorize_delegates_single_auth_url_and_browser_to_run_local_server(tmp_path, capsys):
    cs_file = tmp_path / "client_secret.json"
    cs_file.write_text('{"installed": {"client_id": "cid", "client_secret": "SECRET_CLIENT_XYZ"}}', encoding="utf-8")
    tok_file = tmp_path / "youtube_token.pickle"
    old_creds = _DummyCreds(["https://www.googleapis.com/auth/youtube.upload"])
    tok_file.write_bytes(pickle.dumps(old_creds))

    new_creds = _DummyCreds(REQUIRED_SCOPES)
    mock_flow = MagicMock()
    mock_flow.run_local_server.return_value = new_creds

    with patch("uploader.oauth_manager.InstalledAppFlow.from_client_secrets_file", return_value=mock_flow), \
         patch("uploader.oauth_manager.verify_channel_identity", return_value=(True, {"channel_id": "UCb1BDNY8WxoD1q_UVyEmvuw", "channel_title": "Stories Malik"})), \
         patch("uploader.oauth_manager.config.sync_client_secret_file"):
        ok, res = reauthorize_channel(
            client_secret_file=str(cs_file),
            token_path=str(tok_file),
            open_browser=True,
            timeout_seconds=120,
            expected_channel_id="UCb1BDNY8WxoD1q_UVyEmvuw",
            sync_env=False,
        )

    assert ok is True
    assert res["channel_id"] == "UCb1BDNY8WxoD1q_UVyEmvuw"
    assert not hasattr(oauth_manager, "webbrowser")
    mock_flow.authorization_url.assert_not_called()
    mock_flow.run_local_server.assert_called_once()
    kwargs = mock_flow.run_local_server.call_args.kwargs
    assert kwargs["host"] == "127.0.0.1"
    assert kwargs["port"] == 8080
    assert kwargs["open_browser"] is True
    assert kwargs["timeout_seconds"] == 120
    assert kwargs["prompt"] == "consent"
    assert kwargs["access_type"] == "offline"
    assert kwargs["include_granted_scopes"] == "false"
    assert isinstance(kwargs["state"], str) and len(kwargs["state"]) > 10
    import os
    assert os.environ.get("OAUTHLIB_RELAX_TOKEN_SCOPE") is None
    assert res["unexpected_extra_scopes"] == []

    # Valid scopes & matching channel atomically replaced token
    saved = pickle.loads(tok_file.read_bytes())
    assert set(saved.scopes) == set(REQUIRED_SCOPES)

    # Secrets must never appear in diagnostic logs
    out = capsys.readouterr().out
    assert "SECRET_ACCESS_TOKEN_XYZ" not in out
    assert "SECRET_REFRESH_TOKEN_ABC" not in out
    assert "SECRET_CLIENT_XYZ" not in out
    assert "Requested OAuth scopes (3)" in out
    assert "Granted OAuth scopes (3)" in out
    assert "Channel identity check: ok=True" in out


def test_reauthorize_preserves_existing_token_on_partial_scopes_and_channel_mismatch(tmp_path, capsys):
    cs_file = tmp_path / "client_secret.json"
    cs_file.write_text('{"installed": {"client_id": "cid", "client_secret": "SECRET_CLIENT_XYZ"}}', encoding="utf-8")
    tok_file = tmp_path / "youtube_token.pickle"
    old_creds = _DummyCreds(["https://www.googleapis.com/auth/youtube.upload"])
    old_bytes = pickle.dumps(old_creds)
    tok_file.write_bytes(old_bytes)

    # 1. Partial scopes rejected & old token preserved
    partial_creds = _DummyCreds(["https://www.googleapis.com/auth/youtube.upload"])
    mock_flow = MagicMock()
    mock_flow.run_local_server.return_value = partial_creds

    with patch("uploader.oauth_manager.InstalledAppFlow.from_client_secrets_file", return_value=mock_flow), \
         patch("uploader.oauth_manager.config.sync_client_secret_file"):
        ok, res = reauthorize_channel(
            client_secret_file=str(cs_file),
            token_path=str(tok_file),
            open_browser=False,
            expected_channel_id="UCb1BDNY8WxoD1q_UVyEmvuw",
            sync_env=False,
        )

    assert ok is False
    assert "required OAuth scopes were not granted" in res["error"]
    assert tok_file.read_bytes() == old_bytes

    # 2. Channel mismatch rejected & old token preserved
    full_creds = _DummyCreds(REQUIRED_SCOPES)
    mock_flow.run_local_server.return_value = full_creds
    with patch("uploader.oauth_manager.InstalledAppFlow.from_client_secrets_file", return_value=mock_flow), \
         patch("uploader.oauth_manager.verify_channel_identity", return_value=(False, {"error": "Channel identity mismatch", "channel_id": "UCWRONG", "channel_title": "Wrong"})), \
         patch("uploader.oauth_manager.config.sync_client_secret_file"):
        ok2, res2 = reauthorize_channel(
            client_secret_file=str(cs_file),
            token_path=str(tok_file),
            open_browser=False,
            expected_channel_id="UCb1BDNY8WxoD1q_UVyEmvuw",
            sync_env=False,
        )

    assert ok2 is False
    assert "Channel identity mismatch" in res2["error"]
    assert tok_file.read_bytes() == old_bytes
    out = capsys.readouterr().out
    assert "SECRET_ACCESS_TOKEN_XYZ" not in out
    assert "SECRET_REFRESH_TOKEN_ABC" not in out


def test_reauthorize_accepts_verified_superset_with_extra_youtube_scope(tmp_path, capsys):
    import os

    cs_file = tmp_path / "client_secret.json"
    cs_file.write_text('{"installed": {"client_id": "cid", "client_secret": "SECRET_CLIENT_XYZ"}}', encoding="utf-8")
    tok_file = tmp_path / "youtube_token.pickle"
    tok_file.write_bytes(pickle.dumps(_DummyCreds(["https://www.googleapis.com/auth/youtube.upload"])))

    superset_scopes = REQUIRED_SCOPES + ["https://www.googleapis.com/auth/youtube"]
    mock_flow = MagicMock()
    mock_flow.run_local_server.return_value = _DummyCreds(superset_scopes)

    with patch("uploader.oauth_manager.InstalledAppFlow.from_client_secrets_file", return_value=mock_flow), \
         patch("uploader.oauth_manager.verify_channel_identity", return_value=(True, {"channel_id": "UCb1BDNY8WxoD1q_UVyEmvuw", "channel_title": "Stories Malik"})), \
         patch("uploader.oauth_manager.config.sync_client_secret_file"):
        ok, res = reauthorize_channel(
            client_secret_file=str(cs_file),
            token_path=str(tok_file),
            open_browser=False,
            expected_channel_id="UCb1BDNY8WxoD1q_UVyEmvuw",
            sync_env=False,
        )

    assert ok is True
    assert res["unexpected_extra_scopes"] == ["https://www.googleapis.com/auth/youtube"]
    assert os.environ.get("OAUTHLIB_RELAX_TOKEN_SCOPE") is None
    out = capsys.readouterr().out
    assert "Additional OAuth scopes returned by Google (1): https://www.googleapis.com/auth/youtube" in out

