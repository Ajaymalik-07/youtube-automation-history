"""
YouTube Channel One-Time Authorization & Scope Refresh Tool
Phase 18.1: Safe Google OAuth Scope Auditing, Reauthorization, and Scope Enforcement.
Guarantees required scopes:
- https://www.googleapis.com/auth/youtube.upload
- https://www.googleapis.com/auth/youtube.readonly
- https://www.googleapis.com/auth/yt-analytics.readonly
"""
import os
import sys
import config
from uploader.oauth_manager import audit_token_scopes, reauthorize_channel, REQUIRED_SCOPES

def main():
    print("=" * 65)
    print("  ✦ YouTube Channel Authorization & OAuth Scope Manager")
    print("=" * 65)

    audit = audit_token_scopes()
    print("\n[Current OAuth Status]")
    print(f"  • Token File Exists  : {audit['exists']}")
    print(f"  • Token Valid        : {audit['valid']}")
    print(f"  • Refresh Token Available: {audit['has_refresh_token']}")
    print(f"  • Granted Scopes ({len(audit['granted_scopes'])}):")
    for s in audit['granted_scopes']:
        print(f"     ✓ {s}")

    if audit['is_fully_authorized']:
        print("\n🎉 ALL REQUIRED SCOPES ARE ALREADY GRANTED!")
        print("   Your system is fully authorized for uploads, video processing checks, and YouTube Analytics v2.")
        return

    print("\n⚠ MISSING REQUIRED SCOPES:")
    for s, desc in audit['missing_descriptions'].items():
        print(f"   ✗ {s}")
        print(f"     → Purpose: {desc}")

    print("\n" + "=" * 65)
    print("  📋 IMPORTANT GOOGLE CONSENT SCREEN GUIDE:")
    print("  1. Select your Google account that owns the 'Stories Malik' channel.")
    print("  2. If you see 'Google hasn't verified this app':")
    print("     -> Click 'Advanced' (or 'उन्नत') at the bottom.")
    print("     -> Click 'Go to youtube-agentic-studio (unsafe)'.")
    print("  3. CRITICAL: Check ALL permission boxes requested on the screen:")
    print("     ☑ Manage your YouTube videos (upload & schedule)")
    print("     ☑ View your YouTube account (inspect processing details)")
    print("     ☑ View YouTube Analytics reports (retention & watch time)")
    print("     -> Click 'Continue'.")
    print("=" * 65)

    print("\nStarting safe OAuth reauthorization flow...")
    print("Existing credentials backed up automatically to 'youtube_token.pickle.bak'.")
    
    ok, res = reauthorize_channel(open_browser=True, timeout_seconds=240)
    if ok:
        print(f"\n✓ Successfully authorized channel: {res.get('channel_title')} (ID: {res.get('channel_id')})")
        print("✓ Updated 'youtube_token.pickle' and synchronized YOUTUBE_TOKEN_BASE64 in .env.")
        print("\n🎉 ALL PERMISSIONS GRANTED! Video publishing and YouTube Analytics are active.")
    else:
        print(f"\n[ERROR] Reauthorization failed: {res.get('error')}")
        print("Previous working credentials have been preserved from backup.")
        sys.exit(1)

if __name__ == "__main__":
    main()

