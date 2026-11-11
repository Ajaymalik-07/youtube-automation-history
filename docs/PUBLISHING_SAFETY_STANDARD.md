# Publishing Safety Standard

**Channel:** Stories Malik (`@StoriesMalik`)  
**Scope:** Video Publishing Lifecycle, State Machine, Human Approval Gates & Upload Security  
**Status:** Canonical & Enforced  

---

## 1. Core Principles

1. **Mandatory Human Approval:** No video file may be published or scheduled to YouTube without an explicit, verifiable human approval token recorded in the production database.
2. **Private Default Privacy:** Every new upload defaults to `privacyStatus: "private"` (or `"unlisted"` if explicitly configured for reviewer preview), never `"public"`.
3. **Deterministic State Machine:** Videos transition through explicit, validated lifecycle states. Illegal state transitions are rejected.
4. **Duplicate Prevention:** Before any upload attempt, file paths and content hashes are checked in the production database to prevent duplicate videos and wasted YouTube API quota.
5. **Safe, Cooperative Server Shutdown:** The review dashboard runs on an isolated daemon server thread using `werkzeug.serving.make_server` and shuts down cleanly upon decision receipt, never calling destructive process exit commands (`os.kill`).

---

## 2. Production Lifecycle States

| State | Description | Permitted Next States |
|---|---|---|
| `DRAFT` | Topic initiated or video in early assembly | `RESEARCH_APPROVED`, `REJECTED`, `FAILED` |
| `RESEARCH_APPROVED` | Research dossier verified against historical evidence framework | `SCRIPT_APPROVED`, `REJECTED`, `FAILED` |
| `SCRIPT_APPROVED` | Documentary or Shorts script cleared fact-checking quality gate | `VIDEO_RENDERED`, `REJECTED`, `FAILED` |
| `VIDEO_RENDERED` | Audio, visual frames, Devanagari subtitles rendered to MP4 | `REVIEW_PENDING`, `REJECTED`, `FAILED` |
| `REVIEW_PENDING` | Video queued in review dashboard awaiting human inspection | `APPROVED`, `REJECTED`, `FAILED` |
| `APPROVED` | Human editor inspected video and issued approval token | `SCHEDULED`, `PUBLISHED`, `FAILED` |
| `SCHEDULED` | Video uploaded to YouTube with a future UTC release timestamp | `PUBLISHED`, `FAILED` |
| `PUBLISHED` | Video live or scheduled on YouTube (terminal state) | None |
| `REJECTED` | Human editor or quality gate rejected video for revisions | `DRAFT` |
| `FAILED` | Rendering, quota, or network exception occurred | `DRAFT`, `REVIEW_PENDING` |

---

## 3. Approval Token Architecture

When a human editor clicks **Approve** in the local review dashboard or via CLI/GUI:

```python
approval_token = f"approval_{int(time.time())}_{abs(hash(video_path)) % 1000000:06d}"
```

The approval record stores:
- `approved`: `True`
- `token`: Unique approval token
- `reviewer`: Identifier of editor (e.g., `human_editor`, `channel_lead`)
- `timestamp`: ISO 8601 UTC timestamp
- `notes`: Editorial review comments

### Upload Gate Enforcement

In `uploader/youtube.py`:
```python
if not bypass_approval and not is_approved_for_upload(video_path):
    # Upload is blocked immediately
    # Video is preserved in output/pending_uploads/
    return f"local://pending_approval/{filename}"
```

---

## 4. Quota and Retry Handling

- YouTube Data API v3 enforces a daily quota (typically 10,000 units/day, ~1,600 units per upload).
- Upon encountering `quotaExceeded`:
  1. The video state transitions to `FAILED` with reason `pending_quota_reset`.
  2. A persistent JSON upload manifest is written to `output/pending_uploads/`.
  3. Video files are preserved intact; rendering does not need to rerun.
  4. Automation checks `production_database.json` to prevent retrying the exact same video file multiple times.

---

## 5. Review Server Protocol

- Host: `127.0.0.1`
- Port: `config.REVIEW_PORT` (default: 5000)
- Browser automatically opens to review dashboard.
- The server runs on a background `ServerThread` using `werkzeug.serving.make_server`.
- When `/api/approve` or `/api/reject` is called:
  - Frontend receives confirmation status (HTTP 200).
  - Background timer calls `server.shutdown()` after 800ms.
  - Sockets close cleanly; parent process remains healthy and intact.
