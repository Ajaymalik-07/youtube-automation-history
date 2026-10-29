"""
YouTube One-Time Authorization Tool
Run this once to link your YouTube channel:
    python authorize_youtube.py

Once authorized, 'youtube_token.pickle' is saved and the autonomous daemon
and Web Studio will publish videos automatically without ever asking again!
"""
import os
import sys
import pickle
import webbrowser
import config
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

TOKEN_FILE = "youtube_token.pickle"

def main():
    print("=" * 65)
    print("  ✦ YouTube Channel One-Time Authorization")
    print("=" * 65)

    config.sync_client_secret_file()
    cs_file = getattr(config, "YOUTUBE_CLIENT_SECRET_FILE", "client_secret.json")

    if not os.path.exists(cs_file):
        print(f"\n[ERROR] '{cs_file}' not found.")
        print("Please set YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET in .env first.")
        sys.exit(1)

    with open(cs_file, encoding="utf-8") as f:
        content = f.read()
        if "YOUR_CLIENT_ID" in content:
            print(f"\n[ERROR] '{cs_file}' contains placeholder credentials.")
            print("Please set your real Client ID & Secret in .env or Settings.")
            sys.exit(1)

    print("\n1. Generating Google OAuth link...")
    import secrets
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
    flow = InstalledAppFlow.from_client_secrets_file(cs_file, config.YOUTUBE_SCOPES)
    flow.redirect_uri = "http://localhost:8080/"
    state_token = secrets.token_urlsafe(24)
    auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline", state=state_token)

    print("\n2. Opening Google Sign-in in your default browser...")
    print(f"\nIf the browser did not open automatically, copy & paste this URL into your browser:\n")
    print(f"👉 {auth_url}\n")
    webbrowser.open(auth_url)

    print("=" * 65)
    print("  📋 IMPORTANT GOOGLE PROMPTS GUIDE:")
    print("  1. Select your Google account that owns the YouTube channel.")
    print("  2. If you see 'Google hasn't verified this app':")
    print("     -> Click 'Advanced' (or 'उन्नत') at the bottom.")
    print("     -> Click 'Go to youtube-agentic-studio (unsafe)'.")
    print("  3. Check the box: 'Manage your YouTube videos' -> Click 'Continue'.")
    print("=" * 65)
    print("\nWaiting for authorization callback on http://localhost:8080 ...")

    try:
        creds = flow.run_local_server(bind_addr="0.0.0.0", port=8080, open_browser=False, timeout_seconds=240, state=state_token)
        with open(TOKEN_FILE, "wb") as f:
            pickle.dump(creds, f)
        print(f"\n✓ Successfully saved credentials to '{TOKEN_FILE}'!")

        # Verify by fetching channel title
        yt = build("youtube", "v3", credentials=creds)
        res = yt.channels().list(mine=True, part="snippet").execute()
        title = res["items"][0]["snippet"]["title"] if res.get("items") else "YouTube Channel"
        print(f"✓ Channel Linked: {title}")
        print("\n🎉 AUTOMATION READY! Videos will now be published automatically without prompting.")
    except Exception as e:
        print(f"\n[ERROR] Authorization failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
