"""
Email Notifier for YAAS Studio
Dispatches modern, high-aesthetic HTML email summaries for Shorts and Long-form
videos rendered and published to YouTube, consolidated into a 24-hour daily digest.
Includes live YouTube video analytics (views, likes, comments) and channel metrics.
Recipient default: ajaymobulous@gmail.com
"""
import os
import sys
import json
import smtplib
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
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

DEFAULT_DIGEST_INTERVAL_HOURS: float = 24.0


def _get_ist_time_str(dt: Optional[datetime] = None) -> str:
    """Returns formatted IST timestamp."""
    ist = timezone(timedelta(hours=5, minutes=30))
    target = dt.astimezone(ist) if dt else datetime.now(ist)
    return target.strftime("%d %B %Y, %I:%M %p IST")


def _get_digest_interval_hours() -> float:
    """Returns the configured digest interval in hours (default: 24.0)."""
    try:
        val = getattr(config, "EMAIL_DIGEST_INTERVAL_HOURS", 24.0)
        return max(0.1, float(val))
    except Exception:
        return DEFAULT_DIGEST_INTERVAL_HOURS


# ─────────────────────────────────────────────────────────────────────────────
#  24-HOUR DAILY DIGEST BUFFER & RATE LIMITING
# ─────────────────────────────────────────────────────────────────────────────

def _load_schedule_state_safe() -> Dict[str, Any]:
    """Helper to load schedule state without circular dependency issues."""
    try:
        from automation import load_schedule_state
        return load_schedule_state()
    except Exception:
        sched_file = os.path.join(getattr(config, "OUTPUT_DIR", "output"), "automation_schedule.json")
        if os.path.exists(sched_file):
            try:
                with open(sched_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
            except Exception:
                pass
    return {}


def _update_schedule_state_safe(updater) -> Dict[str, Any]:
    """Helper to atomically update schedule state under lock without circular dependency or re-entrant lock deadlock issues."""
    try:
        from automation import _get_schedule_file, _SCHEDULE_LOCK, _save_schedule_unlocked, DEFAULT_SLOTS
        from uploader.safety import CrossProcessFileLock
        sched_file = _get_schedule_file()
        with _SCHEDULE_LOCK:
            with CrossProcessFileLock(f"{sched_file}.lock"):
                state = dict(DEFAULT_SLOTS)
                if os.path.exists(sched_file):
                    try:
                        with open(sched_file, "r", encoding="utf-8") as f:
                            loaded = json.load(f)
                            if isinstance(loaded, dict):
                                state.update(loaded)
                    except Exception:
                        pass
                updater(state)
                _save_schedule_unlocked(sched_file, state)
                return state
    except Exception:
        sched_file = os.path.join(getattr(config, "OUTPUT_DIR", "output"), "automation_schedule.json")
        try:
            os.makedirs(os.path.dirname(sched_file) or ".", exist_ok=True)
            st = {}
            if os.path.exists(sched_file):
                try:
                    with open(sched_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, dict):
                            st = data
                except Exception:
                    pass
            updater(st)
            tmp_path = f"{sched_file}.tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(st, f, indent=2)
            os.replace(tmp_path, sched_file)
            return st
        except Exception as e:
            print(f"   ⚠ Could not atomically update schedule state for email digest: {e}")
            return {}


def record_digest_event(
    longform_result: Optional[Dict[str, Any]] = None,
    shorts_results: Optional[List[Dict[str, Any]]] = None,
    errors: Optional[List[Dict[str, Any]]] = None,
    force_flush: bool = False,
) -> Dict[str, Any]:
    """
    Appends execution outcomes (published videos, scheduled items, diagnostics)
    into the persistent 24-hour daily digest buffer in automation_schedule.json.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    captured_buf: Dict[str, Any] = {}

    def _apply_event(state: Dict[str, Any]):
        nonlocal captured_buf
        buf = state.get("email_digest_buffer")
        if not isinstance(buf, dict):
            buf = {"longform": [], "shorts": [], "errors": [], "last_event_at": None}

        buf["last_event_at"] = now_iso

        # 1. Accumulate Longform
        if longform_result and isinstance(longform_result, dict):
            lf_copy = dict(longform_result)
            lf_copy.setdefault("recorded_at", now_iso)
            sig = (lf_copy.get("title"), lf_copy.get("url"))
            existing_sigs = {(x.get("title"), x.get("url")) for x in buf.get("longform", [])}
            if sig not in existing_sigs:
                buf.setdefault("longform", []).append(lf_copy)

        # 2. Accumulate Shorts
        if shorts_results and isinstance(shorts_results, list):
            existing_short_sigs = {(x.get("title"), x.get("url")) for x in buf.get("shorts", [])}
            for s in shorts_results:
                if isinstance(s, dict):
                    s_copy = dict(s)
                    s_copy.setdefault("recorded_at", now_iso)
                    sig = (s_copy.get("title"), s_copy.get("url"))
                    if sig not in existing_short_sigs:
                        existing_short_sigs.add(sig)
                        buf.setdefault("shorts", []).append(s_copy)

        # 3. Accumulate Errors / Notices
        if errors and isinstance(errors, list):
            existing_err_sigs = {(e.get("item"), e.get("title"), str(e.get("error"))[:80]) for e in buf.get("errors", [])}
            for e in errors:
                if isinstance(e, dict):
                    e_copy = dict(e)
                    e_copy.setdefault("recorded_at", now_iso)
                    sig = (e_copy.get("item"), e_copy.get("title"), str(e_copy.get("error"))[:80])
                    if sig not in existing_err_sigs:
                        existing_err_sigs.add(sig)
                        buf.setdefault("errors", []).append(e_copy)

        # Bound buffer size
        buf["longform"] = buf.get("longform", [])[-30:]
        buf["shorts"] = buf.get("shorts", [])[-100:]
        buf["errors"] = buf.get("errors", [])[-50:]

        state["email_digest_buffer"] = buf
        captured_buf = buf

    _update_schedule_state_safe(_apply_event)
    return captured_buf


def should_send_email_digest(force: bool = False) -> Tuple[bool, str]:
    """
    Evaluates whether the 24-hour email digest window has elapsed.
    Returns (should_send: bool, reason: str).
    """
    if force:
        return True, "force_flag_enabled"

    state = _load_schedule_state_safe()
    last_sent_iso = state.get("last_email_digest_sent_at")
    interval_hours = _get_digest_interval_hours()

    if not last_sent_iso:
        # Never sent before — eligible to establish the 24-hour cycle
        return True, f"initial_digest_cycle (interval={interval_hours}h)"

    try:
        last_sent_dt = datetime.fromisoformat(last_sent_iso)
        if last_sent_dt.tzinfo is None:
            last_sent_dt = last_sent_dt.replace(tzinfo=timezone.utc)
    except Exception as e:
        return True, f"invalid_last_sent_timestamp ({e})"

    now_utc = datetime.now(timezone.utc)
    elapsed = now_utc - last_sent_dt
    elapsed_hours = elapsed.total_seconds() / 3600.0

    if elapsed_hours >= interval_hours:
        return True, f"interval_elapsed ({elapsed_hours:.2f}h >= {interval_hours:.1f}h)"

    rem_hours = interval_hours - elapsed_hours
    return False, f"interval_not_elapsed ({elapsed_hours:.2f}h < {interval_hours:.1f}h, {rem_hours:.1f}h remaining)"


def get_consolidated_24h_data() -> Dict[str, Any]:
    """
    Collects complete 24-hour activity records from:
    1. Pending in-memory/state digest buffer.
    2. automation_schedule.json history_runs from the past 24 hours.
    3. Live YouTube channel & last video analytics.
    """
    state = _load_schedule_state_safe()
    buf = state.get("email_digest_buffer") or {}
    interval_hours = _get_digest_interval_hours()
    cutoff_utc = datetime.now(timezone.utc) - timedelta(hours=max(24.0, interval_hours))

    # 1. Harvest past 24h history_runs
    history_runs = state.get("history_runs", []) or []
    recent_history: List[Dict[str, Any]] = []
    for r in history_runs:
        if not isinstance(r, dict):
            continue
        d_str = r.get("date_ist")
        if d_str:
            try:
                dt = datetime.fromisoformat(d_str)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone(timedelta(hours=5, minutes=30)))
                if dt.astimezone(timezone.utc) >= cutoff_utc:
                    recent_history.append(r)
            except Exception:
                pass

    # Merge buffered longform and history longform
    longform_items: List[Dict[str, Any]] = list(buf.get("longform", []))
    shorts_items: List[Dict[str, Any]] = list(buf.get("shorts", []))
    errors_items: List[Dict[str, Any]] = list(buf.get("errors", []))

    # Add from recent_history if not already present
    lf_sigs = {(x.get("title"), x.get("url")) for x in longform_items}
    sh_sigs = {(x.get("title"), x.get("url")) for x in shorts_items}

    for r in recent_history:
        r_type = r.get("type")
        sig = (r.get("title"), r.get("url"))
        if r_type == "longform" and sig not in lf_sigs:
            lf_sigs.add(sig)
            longform_items.append(r)
        elif r_type == "short" and sig not in sh_sigs:
            sh_sigs.add(sig)
            shorts_items.append(r)

    # Primary featured longform (most recent)
    primary_lf = longform_items[-1] if longform_items else None

    return {
        "primary_longform": primary_lf,
        "all_longform": longform_items,
        "all_shorts": shorts_items,
        "all_errors": errors_items,
        "window_hours": interval_hours,
        "total_published_or_scheduled": len(longform_items) + len(shorts_items),
    }


def clear_digest_buffer() -> None:
    """Resets the accumulated digest buffer after successful dispatch."""
    def _apply_clear(state: Dict[str, Any]):
        state["email_digest_buffer"] = {
            "longform": [],
            "shorts": [],
            "errors": [],
            "last_cleared_at": datetime.now(timezone.utc).isoformat(),
        }
        state["last_email_digest_sent_at"] = datetime.now(timezone.utc).isoformat()
    _update_schedule_state_safe(_apply_clear)


# ─────────────────────────────────────────────────────────────────────────────
#  HTML & PLAIN TEXT DIGEST BUILDERS
# ─────────────────────────────────────────────────────────────────────────────

def build_html_report(
    longform_result: dict = None,
    shorts_results: list = None,
    analytics: dict = None,
    recipient: str = None,
    errors: list = None,
    all_longform: list = None,
    window_hours: float = 24.0,
) -> str:
    """Generates a responsive, visually stunning HTML 24-hour daily digest email report."""
    lf = longform_result or {}
    shorts = shorts_results or []
    all_lf = all_longform or ([lf] if lf else [])
    an = analytics or {}
    errs = errors or []
    to_email = recipient or getattr(config, "NOTIFICATION_EMAIL", "ajaymobulous@gmail.com")
    now_ist = _get_ist_time_str()

    # Dynamic status badge
    if errs:
        badge_html = """
        <span style="background-color: #dc2626; color: #ffffff; font-size: 12px; font-weight: 700; padding: 6px 12px; border-radius: 20px; text-transform: uppercase; letter-spacing: 0.5px;">
          ⚠️ 24h Summary (With Notices)
        </span>
        """
    else:
        badge_html = """
        <span style="background-color: #059669; color: #ffffff; font-size: 12px; font-weight: 700; padding: 6px 12px; border-radius: 20px; text-transform: uppercase; letter-spacing: 0.5px;">
          🟢 24h Daily Digest
        </span>
        """

    # Errors section HTML
    errors_html = ""
    if errs:
        err_rows = ""
        for e in errs:
            item_name = e.get("item", "Pipeline Task")
            title = e.get("title", "")
            err_msg = e.get("error", "Unknown error")
            action = e.get("action", "Scheduled for automated retry")
            err_rows += f"""
            <tr style="border-bottom: 1px solid #7f1d1d;">
              <td style="padding: 10px 12px; color: #fca5a5; font-weight: 700; font-size: 13px; width: 25%;">{item_name}</td>
              <td style="padding: 10px 12px; color: #fee2e2; font-size: 13px;">
                <strong>{title}</strong><br>
                <span style="color: #f87171; font-family: monospace; font-size: 12px;">{err_msg}</span><br>
                <span style="color: #a7f3d0; font-size: 12px;">➡ Action: {action}</span>
              </td>
            </tr>
            """
        errors_html = f"""
        <!-- ERROR DIAGNOSTICS SECTION -->
        <tr>
          <td style="padding: 20px 35px 0 35px;">
            <div style="background-color: #450a0a; border: 1px solid #ef4444; border-radius: 8px; padding: 16px 20px;">
              <span style="font-size: 11px; text-transform: uppercase; font-weight: 700; color: #f87171; letter-spacing: 1px;">
                🚨 24-Hour Pipeline Notices & Diagnostic Events ({len(errs)})
              </span>
              <p style="margin: 6px 0 12px 0; color: #fca5a5; font-size: 13px;">
                Events captured across pipeline executions over the past 24 hours:
              </p>
              <table width="100%" border="0" cellspacing="0" cellpadding="0" style="background-color: #2b0c0c; border-radius: 6px; border-collapse: collapse;">
                <tbody>
                  {err_rows}
                </tbody>
              </table>
            </div>
          </td>
        </tr>
        """

    # Longform details
    lf_title = lf.get("title", "Historical Documentary")
    lf_url = lf.get("url", "")
    lf_score = lf.get("score", 100)
    lf_link_html = (
        f'<a href="{lf_url}" style="background-color: #ef4444; color: #ffffff; text-decoration: none; padding: 10px 18px; border-radius: 6px; font-weight: 600; font-size: 14px; display: inline-block;">▶ Watch Featured Documentary</a>'
        if lf_url and not lf_url.startswith("local://") else
        f'<span style="background-color: #374151; color: #d1d5db; padding: 6px 12px; border-radius: 4px; font-size: 13px;">📦 Stored in Local Archive / Pre-Render Queue</span>'
    )

    # Extra longform rows if multiple were processed in 24h
    extra_lf_html = ""
    if len(all_lf) > 1:
        extra_rows = ""
        for idx, doc in enumerate(all_lf, 1):
            d_title = doc.get("title", f"Documentary {idx}")
            d_url = doc.get("url", "")
            d_score = doc.get("score", 100)
            d_link = (
                f'<a href="{d_url}" style="color: #60a5fa; text-decoration: none; font-weight: 600;">Watch →</a>'
                if d_url and not d_url.startswith("local://") else
                '<span style="color: #9ca3af;">Queued</span>'
            )
            extra_rows += f"""
            <tr style="border-bottom: 1px solid #2d3748;">
              <td style="padding: 8px 12px; color: #f3f4f6; font-size: 13px;">#{idx} {d_title}</td>
              <td style="padding: 8px 12px; color: #34d399; font-size: 13px; font-weight: 600;">{d_score}/100</td>
              <td style="padding: 8px 12px; font-size: 13px;">{d_link}</td>
            </tr>
            """
        extra_lf_html = f"""
        <table width="100%" border="0" cellspacing="0" cellpadding="0" style="margin-top: 12px; background-color: #1a2234; border-radius: 6px; border-collapse: collapse;">
          <thead>
            <tr style="background-color: #232d42; color: #94a3b8; font-size: 11px; text-transform: uppercase;">
              <th style="padding: 8px 12px; text-align: left;">All Documentaries in 24h ({len(all_lf)})</th>
              <th style="padding: 8px 12px; text-align: left;">Score</th>
              <th style="padding: 8px 12px; text-align: left;">Link</th>
            </tr>
          </thead>
          <tbody>
            {extra_rows}
          </tbody>
        </table>
        """

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
                '<span style="color: #9ca3af;">Scheduled on YouTube</span>'
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
            No Shorts published during this 24-hour cycle.
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

    total_count = len(all_lf) + len(shorts)

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>YAAS Studio 24-Hour Complete Digest</title>
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
                      24-Hour Complete Daily Digest & Channel Performance
                    </p>
                  </td>
                  <td align="right">
                    {badge_html}
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- TIMESTAMP & DISPATCH META -->
          <tr>
            <td style="padding: 18px 35px; border-bottom: 1px solid #1f2937; background-color: #161f30;">
              <table width="100%" border="0" cellspacing="0" cellpadding="0" style="font-size: 13px; color: #9ca3af;">
                <tr>
                  <td>📅 <strong>Dispatched:</strong> {now_ist}</td>
                  <td align="right">👤 <strong>Recipient:</strong> <span style="color: #e5e7eb;">{to_email}</span></td>
                </tr>
                <tr>
                  <td style="padding-top: 6px;" colspan="2">
                    ⏱️ <strong>Cadence:</strong> 1 Email per 24 Hours · 📊 <strong>Total Videos in 24h:</strong> <span style="color: #38bdf8; font-weight: 700;">{total_count}</span> ({len(all_lf)} Long-form, {len(shorts)} Shorts)
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          {errors_html}

          <!-- SECTION 1: LONGFORM VIDEO -->
          <tr>
            <td style="padding: 25px 35px 20px 35px;">
              <table width="100%" border="0" cellspacing="0" cellpadding="0">
                <tr>
                  <td>
                    <span style="font-size: 11px; text-transform: uppercase; font-weight: 700; color: #818cf8; letter-spacing: 1px;">
                      🎬 Featured Long-Form Documentary ({len(all_lf)} in 24h)
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
                    {extra_lf_html}
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- SECTION 2: SHORTS BATCH -->
          <tr>
            <td style="padding: 10px 35px 25px 35px;">
              <span style="font-size: 11px; text-transform: uppercase; font-weight: 700; color: #a78bfa; letter-spacing: 1px;">
                ⚡ 24-Hour YouTube Shorts Summary ({len(shorts)} Videos)
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
                📊 24-Hour Channel & Video Performance Snapshot
              </span>
              <p style="margin: 6px 0 14px 0; font-size: 13px; color: #94a3b8;">
                Most recent video: <strong style="color: #f1f5f9;">{last_title}</strong><br>
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
              Daily consolidated 24-hour digest policy active: 1 comprehensive email every 24 hours.
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""
    return html


def build_plain_text_report(
    longform_result: dict = None,
    shorts_results: list = None,
    analytics: dict = None,
    recipient: str = None,
    errors: list = None,
    all_longform: list = None,
    window_hours: float = 24.0,
) -> str:
    """Plain-text fallback version of the 24-hour daily digest email."""
    lf = longform_result or {}
    shorts = shorts_results or []
    all_lf = all_longform or ([lf] if lf else [])
    an = analytics or {}
    errs = errors or []
    now_ist = _get_ist_time_str()

    status_str = f"Alert / Attention 🚨 ({len(errs)} notices)" if errs else "24h Digest Complete 🟢"
    lines = [
        "===================================================",
        "🎬 YAAS AUTONOMOUS STUDIO — 24-HOUR DAILY DIGEST",
        "===================================================",
        f"Timestamp : {now_ist}",
        f"Recipient : {recipient or getattr(config, 'NOTIFICATION_EMAIL', 'ajaymobulous@gmail.com')}",
        f"Cadence   : 1 Email per 24 Hours",
        f"Status    : {status_str}",
        f"Activity  : {len(all_lf)} Long-form + {len(shorts)} Shorts in past 24h",
        "",
    ]

    if errs:
        lines.append("--- ⚠️ PIPELINE NOTICES & ERROR DIAGNOSTICS ---")
        for e in errs:
            lines.append(f"  • {e.get('item')}: {e.get('title')}")
            lines.append(f"    Cause  : {e.get('error')}")
            lines.append(f"    Action : {e.get('action')}")
        lines.append("")

    lines.extend([
        f"--- 1. FEATURED DOCUMENTARIES ({len(all_lf)} Videos) ---",
    ])
    for idx, doc in enumerate(all_lf, 1):
        lines.append(f"  #{idx} Title : {doc.get('title', 'Historical Documentary')}")
        lines.append(f"     Score : {doc.get('score', 100)}/100 (Grade A)")
        lines.append(f"     URL   : {doc.get('url', 'Stored in Local Archive')}")

    lines.extend([
        "",
        f"--- 2. 24-HOUR SHORTS BATCH ({len(shorts)} Videos) ---",
    ])
    for i, s in enumerate(shorts, 1):
        lines.append(f"  #{i} {s.get('title')} [{s.get('score', 100)}/100] -> {s.get('url', 'Pending')}")

    lines.extend([
        "",
        "--- 3. CHANNEL & LATEST VIDEO ANALYTICS ---",
        f"Last Video : {an.get('video_title')}",
        f"Last URL   : {an.get('video_url')}",
        f"Views      : {an.get('views', '0')}",
        f"Likes      : {an.get('likes', '0')}",
        f"Comments   : {an.get('comments', '0')}",
        f"Subscribers: {an.get('channel_subscribers', 'N/A')}",
        "",
        "===================================================",
        "Generated automatically by YAAS Autonomous Studio (24h Digest)",
        "===================================================",
    ])
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
#  EMAIL DISPATCH CONTROLLER (ONLY 1 EMAIL IN 24 HOURS)
# ─────────────────────────────────────────────────────────────────────────────

def _dispatch_smtp_email(to_email: str, subject: str, text_content: str, html_content: str) -> bool:
    """Delivers email via configured SMTP server."""
    smtp_user = getattr(config, "SMTP_USER", "").strip()
    smtp_pass = getattr(config, "SMTP_PASSWORD", "").strip()
    smtp_host = getattr(config, "SMTP_HOST", "smtp.gmail.com").strip()
    smtp_port = getattr(config, "SMTP_PORT", 587)

    if not smtp_user or not smtp_pass or smtp_user.startswith("YOUR_"):
        print("   ℹ SMTP credentials not yet provided in .env (SMTP_USER / SMTP_PASSWORD).")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
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


def send_daily_email_digest(recipient: Optional[str] = None, force: bool = False) -> bool:
    """
    Consolidates all 24-hour activity (Shorts, Long-form, Analytics, Notices)
    and dispatches exactly ONE comprehensive daily email report.
    Respects the 24-hour rate limit unless force=True.
    """
    to_email = recipient or getattr(config, "NOTIFICATION_EMAIL", "ajaymobulous@gmail.com")
    should_send, reason = should_send_email_digest(force=force)

    if not should_send:
        print(f"   ℹ Daily 24-hour email digest skipped: {reason}.")
        print("      Activity is buffered and will be dispatched when the 24-hour window arrives.")
        return False

    print(f"\n📧 Assembling 24-hour complete daily email digest for {to_email} ({reason})…")

    # Gather consolidated activity
    digest_data = get_consolidated_24h_data()
    analytics = get_channel_and_last_video_analytics()

    primary_lf = digest_data.get("primary_longform")
    all_lf = digest_data.get("all_longform", [])
    shorts = digest_data.get("all_shorts", [])
    errs = digest_data.get("all_errors", [])
    window = digest_data.get("window_hours", 24.0)

    html_content = build_html_report(
        longform_result=primary_lf,
        shorts_results=shorts,
        analytics=analytics,
        recipient=to_email,
        errors=errs,
        all_longform=all_lf,
        window_hours=window,
    )
    text_content = build_plain_text_report(
        longform_result=primary_lf,
        shorts_results=shorts,
        analytics=analytics,
        recipient=to_email,
        errors=errs,
        all_longform=all_lf,
        window_hours=window,
    )

    # Persist report archive
    reports_dir = os.path.join(getattr(config, "OUTPUT_DIR", "output"), "email_reports")
    os.makedirs(reports_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_file = os.path.join(reports_dir, f"digest_24h_{stamp}.html")
    latest_file = os.path.join(getattr(config, "OUTPUT_DIR", "output"), "latest_email_report.html")

    with open(archive_file, "w", encoding="utf-8") as f:
        f.write(html_content)
    with open(latest_file, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"   💾 24-hour email report saved: {archive_file}")

    if errs:
        subject = f"🚨 YAAS Studio 24-Hour Digest: Daily Performance & Notices ({_get_ist_time_str()})"
    else:
        subject = f"🎬 YAAS Studio 24-Hour Digest: Daily Uploads & YouTube Analytics ({_get_ist_time_str()})"

    delivered = _dispatch_smtp_email(to_email, subject, text_content, html_content)
    if delivered:
        clear_digest_buffer()
        print(f"   ✅ 24-hour email digest delivered. Next digest in {_get_digest_interval_hours():.1f} hours.")
    else:
        # Update last_email_digest_sent_at even if SMTP is unconfigured so local runs do not spam reports
        def _touch_sent(state: Dict[str, Any]):
            state["last_email_digest_sent_at"] = datetime.now(timezone.utc).isoformat()
        _update_schedule_state_safe(_touch_sent)
        print(f"   ℹ Saved digest to disk. Updated 24-hour schedule checkpoint.")

    return delivered


def send_upload_notification_email(
    longform_result: dict = None,
    shorts_results: list = None,
    recipient: str = None,
    errors: list = None,
    force: bool = False,
) -> bool:
    """
    Main entry point invoked by pipeline tasks.
    Enforces ONLY 1 EMAIL IN 24 HOURS:
    1. Records the task's results into the 24-hour digest buffer.
    2. Checks if 24 hours have elapsed since the last digest email.
    3. If 24 hours have passed (or force=True), dispatches the complete 24-hour digest.
    4. Otherwise, silently buffers the details and suppresses per-task emails.
    """
    # 1. Record event into 24-hour persistent buffer
    record_digest_event(
        longform_result=longform_result,
        shorts_results=shorts_results,
        errors=errors,
    )

    # 2. Check 24-hour rate limit & dispatch if due
    return send_daily_email_digest(recipient=recipient, force=force)
