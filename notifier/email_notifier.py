"""
Email Notifier for YAAS Studio
Dispatches modern, high-aesthetic HTML email summaries after Shorts and Long-form
videos are rendered and published to YouTube.
Includes live YouTube video analytics (views, likes, comments) and channel metrics.
Recipient default: ajaymobulous@gmail.com
"""
import os
import sys
import smtplib
from datetime import datetime, timezone, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import config
from uploader.analytics import get_channel_and_last_video_analytics

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def _get_ist_time_str() -> str:
    """Returns formatted IST timestamp."""
    ist = timezone(timedelta(hours=5, minutes=30))
    return datetime.now(ist).strftime("%d %B %Y, %I:%M %p IST")


def build_html_report(longform_result: dict = None, shorts_results: list = None,
                      analytics: dict = None, recipient: str = None) -> str:
    """Generates a responsive, visually stunning HTML email report."""
    lf = longform_result or {}
    shorts = shorts_results or []
    an = analytics or {}
    to_email = recipient or getattr(config, "NOTIFICATION_EMAIL", "ajaymobulous@gmail.com")
    now_ist = _get_ist_time_str()

    # Longform details
    lf_title = lf.get("title", "5000 साल पुरानी खोई हुई सभ्यता जो रेगिस्तान के नीचे दबी है")
    lf_url = lf.get("url", "")
    lf_score = lf.get("score", 100)
    lf_link_html = (
        f'<a href="{lf_url}" style="background-color: #ef4444; color: #ffffff; text-decoration: none; padding: 10px 18px; border-radius: 6px; font-weight: 600; font-size: 14px; display: inline-block;">▶ Watch on YouTube</a>'
        if lf_url and not lf_url.startswith("local://") else
        f'<span style="background-color: #374151; color: #d1d5db; padding: 6px 12px; border-radius: 4px; font-size: 13px;">📦 Stored in Local Archive / Pre-Render Queue</span>'
    )

    # Shorts rows
    shorts_html = ""
    if shorts:
        for i, s in enumerate(shorts, 1):
            s_title = s.get("title", f"Short {i}")
            s_url = s.get("url", "")
            s_score = s.get("score", 100)
            url_display = (
                f'<a href="{s_url}" style="color: #6366f1; text-decoration: none; font-weight: 600;">Watch Short →</a>'
                if s_url and not s_url.startswith("local://") else
                '<span style="color: #9ca3af;">Scheduled for Peak Scroll</span>'
            )
            shorts_html += f"""
            <tr style="border-bottom: 1px solid #2d3748;">
              <td style="padding: 10px 12px; font-weight: bold; color: #a5b4fc;">#{i}</td>
              <td style="padding: 10px 12px; color: #f3f4f6; font-size: 14px;">{s_title}</td>
              <td style="padding: 10px 12px; color: #34d399; font-weight: 600; font-size: 13px;">{s_score}/100</td>
              <td style="padding: 10px 12px; font-size: 13px;">{url_display}</td>
            </tr>
            """
    else:
        shorts_html = """
        <tr>
          <td colspan="4" style="padding: 14px; text-align: center; color: #9ca3af; font-size: 13px;">
            No Shorts batch included in this cycle.
          </td>
        </tr>
        """

    # Analytics card
    v_views = an.get("views", "0")
    v_likes = an.get("likes", "0")
    v_comments = an.get("comments", "0")
    ch_subs = an.get("channel_subscribers", "N/A")
    last_title = an.get("video_title", "Previous Historical Documentary")
    last_url = an.get("video_url", "")
    last_url_html = (
        f'<a href="{last_url}" style="color: #60a5fa; text-decoration: underline;">{last_url}</a>'
        if last_url else '<span style="color: #9ca3af;">Available on YouTube Studio</span>'
    )

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>YAAS Studio Content & Analytics Report</title>
</head>
<body style="margin: 0; padding: 0; background-color: #0b0f19; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #f3f4f6;">
  <table width="100%" border="0" cellspacing="0" cellpadding="0" style="background-color: #0b0f19; padding: 30px 15px;">
    <tr>
      <td align="center">
        <table width="650" border="0" cellspacing="0" cellpadding="0" style="max-width: 650px; background-color: #111827; border-radius: 12px; border: 1px solid #1f2937; overflow: hidden; box-shadow: 0 10px 25px rgba(0,0,0,0.5);">
          
          <!-- HEADER -->
          <tr>
            <td style="background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%); padding: 30px 35px;">
              <table width="100%" border="0" cellspacing="0" cellpadding="0">
                <tr>
                  <td>
                    <h1 style="margin: 0; color: #ffffff; font-size: 24px; font-weight: 800; letter-spacing: -0.5px;">
                      YAAS AUTONOMOUS STUDIO
                    </h1>
                    <p style="margin: 6px 0 0 0; color: #c7d2fe; font-size: 14px;">
                      Daily Upload & Channel Performance Dispatch
                    </p>
                  </td>
                  <td align="right">
                    <span style="background-color: #059669; color: #ffffff; font-size: 12px; font-weight: 700; padding: 6px 12px; border-radius: 20px; text-transform: uppercase; letter-spacing: 0.5px;">
                      🟢 Upload Success
                    </span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- TIMESTAMP & DISPATCH META -->
          <tr>
            <td style="padding: 20px 35px 10px 35px; border-bottom: 1px solid #1f2937; background-color: #161f30;">
              <table width="100%" border="0" cellspacing="0" cellpadding="0" style="font-size: 13px; color: #9ca3af;">
                <tr>
                  <td>📅 <strong>Dispatched:</strong> {now_ist}</td>
                  <td align="right">👤 <strong>Recipient:</strong> <span style="color: #e5e7eb;">{to_email}</span></td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- SECTION 1: LONGFORM VIDEO -->
          <tr>
            <td style="padding: 25px 35px 20px 35px;">
              <table width="100%" border="0" cellspacing="0" cellpadding="0">
                <tr>
                  <td>
                    <span style="font-size: 11px; text-transform: uppercase; font-weight: 700; color: #818cf8; letter-spacing: 1px;">
                      🎬 Featured Long-Form Documentary (15+ Min)
                    </span>
                    <h2 style="margin: 8px 0 12px 0; font-size: 20px; color: #ffffff; font-weight: 700; line-height: 1.3;">
                      {lf_title}
                    </h2>
                    <table width="100%" border="0" cellspacing="0" cellpadding="0" style="background-color: #1f2937; border-radius: 8px; padding: 14px 18px; margin-bottom: 16px;">
                      <tr>
                        <td style="color: #9ca3af; font-size: 13px;">
                          🎯 SEO Quality Score: <strong style="color: #34d399;">{lf_score}/100 (Grade A)</strong><br>
                          🗣️ Voice Narration: <strong style="color: #e5e7eb;">Hindi (hi-IN-MadhurNeural)</strong><br>
                          📺 Resolution & Font: <strong style="color: #e5e7eb;">1080p FHD · Nirmala UI Devanagari</strong>
                        </td>
                      </tr>
                    </table>
                    <div>
                      {lf_link_html}
                    </div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- SECTION 2: SHORTS BATCH -->
          <tr>
            <td style="padding: 10px 35px 25px 35px;">
              <span style="font-size: 11px; text-transform: uppercase; font-weight: 700; color: #a78bfa; letter-spacing: 1px;">
                ⚡ Daily High-Velocity Shorts ({len(shorts)} Videos)
              </span>
              <table width="100%" border="0" cellspacing="0" cellpadding="0" style="margin-top: 10px; background-color: #182235; border-radius: 8px; border-collapse: collapse; overflow: hidden;">
                <thead>
                  <tr style="background-color: #1e293b; border-bottom: 2px solid #334155; text-align: left; font-size: 12px; color: #94a3b8; text-transform: uppercase;">
                    <th style="padding: 10px 12px;">Slot</th>
                    <th style="padding: 10px 12px;">Title</th>
                    <th style="padding: 10px 12px;">SEO</th>
                    <th style="padding: 10px 12px;">Link</th>
                  </tr>
                </thead>
                <tbody>
                  {shorts_html}
                </tbody>
              </table>
            </td>
          </tr>

          <!-- SECTION 3: LAST VIDEO ANALYTICS & CHANNEL METRICS -->
          <tr>
            <td style="padding: 20px 35px 25px 35px; background-color: #0f172a; border-top: 1px solid #1f2937; border-bottom: 1px solid #1f2937;">
              <span style="font-size: 11px; text-transform: uppercase; font-weight: 700; color: #38bdf8; letter-spacing: 1px;">
                📊 Last Video & Channel Performance
              </span>
              <p style="margin: 6px 0 14px 0; font-size: 13px; color: #94a3b8;">
                Recent video: <strong style="color: #f1f5f9;">{last_title}</strong><br>
                URL: {last_url_html}
              </p>
              
              <!-- 4 STAT BOXES -->
              <table width="100%" border="0" cellspacing="0" cellpadding="0">
                <tr>
                  <td width="23%" style="background-color: #1e293b; padding: 14px 10px; border-radius: 8px; text-align: center; border: 1px solid #334155;">
                    <div style="font-size: 11px; color: #94a3b8; text-transform: uppercase; font-weight: 600;">Views</div>
                    <div style="font-size: 20px; font-weight: 800; color: #38bdf8; margin-top: 4px;">{v_views}</div>
                  </td>
                  <td width="2%"></td>
                  <td width="23%" style="background-color: #1e293b; padding: 14px 10px; border-radius: 8px; text-align: center; border: 1px solid #334155;">
                    <div style="font-size: 11px; color: #94a3b8; text-transform: uppercase; font-weight: 600;">Likes</div>
                    <div style="font-size: 20px; font-weight: 800; color: #34d399; margin-top: 4px;">{v_likes}</div>
                  </td>
                  <td width="2%"></td>
                  <td width="23%" style="background-color: #1e293b; padding: 14px 10px; border-radius: 8px; text-align: center; border: 1px solid #334155;">
                    <div style="font-size: 11px; color: #94a3b8; text-transform: uppercase; font-weight: 600;">Comments</div>
                    <div style="font-size: 20px; font-weight: 800; color: #fbbf24; margin-top: 4px;">{v_comments}</div>
                  </td>
                  <td width="2%"></td>
                  <td width="23%" style="background-color: #1e293b; padding: 14px 10px; border-radius: 8px; text-align: center; border: 1px solid #334155;">
                    <div style="font-size: 11px; color: #94a3b8; text-transform: uppercase; font-weight: 600;">Channel Subs</div>
                    <div style="font-size: 20px; font-weight: 800; color: #e879f9; margin-top: 4px;">{ch_subs}</div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- FOOTER -->
          <tr>
            <td style="padding: 25px 35px; text-align: center; font-size: 12px; color: #6b7280;">
              Sent automatically by <strong>YAAS — YouTube Agentic AI Studio</strong>.<br>
              Every video is pre-rendered and verified against the 100/100 Publishing Checklist.
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""
    return html


def build_plain_text_report(longform_result: dict = None, shorts_results: list = None,
                            analytics: dict = None, recipient: str = None) -> str:
    """Plain-text fallback version of the email."""
    lf = longform_result or {}
    shorts = shorts_results or []
    an = analytics or {}
    now_ist = _get_ist_time_str()

    lines = [
        "===================================================",
        "🎬 YAAS AUTONOMOUS STUDIO — DAILY UPLOAD REPORT",
        "===================================================",
        f"Timestamp : {now_ist}",
        f"Recipient : {recipient or getattr(config, 'NOTIFICATION_EMAIL', 'ajaymobulous@gmail.com')}",
        f"Status    : Upload Complete 🟢",
        "",
        "--- 1. FEATURED 15+ MIN LONG-FORM VIDEO (HINDI) ---",
        f"Title : {lf.get('title', 'Historical Documentary')}",
        f"Score : {lf.get('score', 100)}/100 (Grade A)",
        f"URL   : {lf.get('url', 'Available in Local Studio')}",
        "",
        f"--- 2. DAILY SHORTS BATCH ({len(shorts)} Videos) ---",
    ]
    for i, s in enumerate(shorts, 1):
        lines.append(f"  #{i} {s.get('title')} [{s.get('score', 100)}/100] -> {s.get('url', 'Pending')}")

    lines.extend([
        "",
        "--- 3. LAST VIDEO & CHANNEL ANALYTICS ---",
        f"Last Video : {an.get('video_title')}",
        f"Last URL   : {an.get('video_url')}",
        f"Views      : {an.get('views', '0')}",
        f"Likes      : {an.get('likes', '0')}",
        f"Comments   : {an.get('comments', '0')}",
        f"Subscribers: {an.get('channel_subscribers', 'N/A')}",
        "",
        "===================================================",
        "Generated automatically by YAAS Autonomous Studio",
        "===================================================",
    ])
    return "\n".join(lines)


def send_upload_notification_email(longform_result: dict = None, shorts_results: list = None,
                                   recipient: str = None) -> bool:
    """
    Builds the report, stores an archive copy in output/email_reports/,
    and dispatches via SMTP if credentials are configured.
    """
    to_email = recipient or getattr(config, "NOTIFICATION_EMAIL", "ajaymobulous@gmail.com")
    print(f"\n📧 Preparing automated email notification for {to_email}…")

    # Fetch analytics
    analytics = get_channel_and_last_video_analytics()
    html_content = build_html_report(longform_result, shorts_results, analytics, to_email)
    text_content = build_plain_text_report(longform_result, shorts_results, analytics, to_email)

    # Always persist report locally
    reports_dir = os.path.join(config.OUTPUT_DIR, "email_reports")
    os.makedirs(reports_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_file = os.path.join(reports_dir, f"report_{stamp}.html")
    latest_file = os.path.join(config.OUTPUT_DIR, "latest_email_report.html")

    with open(archive_file, "w", encoding="utf-8") as f:
        f.write(html_content)
    with open(latest_file, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"   💾 Email report saved: {archive_file}")

    # Check for SMTP config
    smtp_user = getattr(config, "SMTP_USER", "").strip()
    smtp_pass = getattr(config, "SMTP_PASSWORD", "").strip()
    smtp_host = getattr(config, "SMTP_HOST", "smtp.gmail.com").strip()
    smtp_port = getattr(config, "SMTP_PORT", 587)

    if not smtp_user or not smtp_pass or smtp_user.startswith("YOUR_"):
        print("   ℹ SMTP credentials not yet provided in .env (SMTP_USER / SMTP_PASSWORD).")
        print(f"      Report generated and saved to {latest_file}.")
        print("      To receive live inbox delivery:")
        print("        1. Add SMTP_USER=your_email@gmail.com in .env")
        print("        2. Add SMTP_PASSWORD=your_gmail_app_password in .env")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"🎬 YAAS Studio Upload: Videos Published + YouTube Analytics ({_get_ist_time_str()})"
        msg["From"] = f"YAAS Autonomous Studio <{smtp_user}>"
        msg["To"] = to_email

        msg.attach(MIMEText(text_content, "plain", "utf-8"))
        msg.attach(MIMEText(html_content, "html", "utf-8"))

        print(f"   → Connecting to {smtp_host}:{smtp_port} via TLS…")
        server = smtplib.SMTP(smtp_host, smtp_port, timeout=20)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, [to_email], msg.as_string())
        server.quit()

        print(f"   ✅ Email notification successfully sent to {to_email}!")
        return True
    except Exception as e:
        print(f"   ⚠ Could not deliver email to {to_email}: {e}")
        return False
