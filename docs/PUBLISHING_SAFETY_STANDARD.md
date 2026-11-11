# Publishing Safety & Automated Governance Standard

**Channel:** Stories Malik (`@StoriesMalik`)  
**Scope:** Automated Video Publishing Lifecycle, 18-State Machine, Quality Gate Governance & Upload Security  
**Status:** Canonical & Enforced (Phase 17 Overhaul)  

---

## 1. Core Principles

1. **Autonomous Quality Gate Governance:** Manual human approval is replaced by automated, verifiable quality gates across Research, Script, Video, and Metadata.
2. **Private Default Privacy:** Every new upload defaults to `privacyStatus: "private"`. In scheduled mode, YouTube promotes the video to Public at the future `publishAt` timestamp.
3. **Deterministic 18-Stage Lifecycle:** Assets progress through an immutable state machine from `TOPIC_SELECTED` to `COMPLETED`. Any quality failure halts progression and transitions to `BLOCKED_QUALITY_GATE`.
4. **Idempotency & Duplicate Prevention:** Every production job maintains a persistent database record. Uploads verify that a video has not already been scheduled or published, preventing duplicate public uploads.
5. **Safe Server Protocol:** The review dashboard runs on an isolated daemon server thread using `werkzeug.serving.make_server` and shuts down cleanly, never calling destructive process exit commands (`os.kill`).

---

## 2. Production Lifecycle States (18 States)

| State | Description | Permitted Next States |
|---|---|---|
| `TOPIC_SELECTED` | Topic chosen from 10 content pillars | `RESEARCH_IN_PROGRESS`, `BLOCKED_QUALITY_GATE`, `FAILED` |
| `RESEARCH_IN_PROGRESS` | Multi-tier historical evidence acquisition active | `RESEARCH_VALIDATED`, `BLOCKED_QUALITY_GATE`, `FAILED` |
| `RESEARCH_VALIDATED` | Passed research quality gate | `SCRIPT_GENERATED`, `BLOCKED_QUALITY_GATE`, `FAILED` |
| `SCRIPT_GENERATED` | Narration, sections, and hooks generated | `SCRIPT_VALIDATED`, `BLOCKED_QUALITY_GATE`, `FAILED` |
| `SCRIPT_VALIDATED` | Passed script quality gate | `VIDEO_RENDERING`, `BLOCKED_QUALITY_GATE`, `FAILED` |
| `VIDEO_RENDERING` | Voiceover, video clips, and subtitles assembling | `VIDEO_RENDERED`, `FAILED` |
| `VIDEO_RENDERED` | Physical MP4 rendered on disk | `VIDEO_VALIDATED`, `METADATA_VALIDATED`, `BLOCKED_QUALITY_GATE`, `FAILED` |
| `VIDEO_VALIDATED` | Passed video integrity and duration gate | `METADATA_VALIDATED`, `UPLOAD_QUEUED`, `BLOCKED_QUALITY_GATE`, `FAILED` |
| `METADATA_VALIDATED` | Passed SEO and compliance metadata gate | `UPLOAD_QUEUED`, `UPLOADING`, `BLOCKED_QUALITY_GATE`, `FAILED` |
| `UPLOAD_QUEUED` | Ready for upload execution | `UPLOADING`, `FAILED` |
| `UPLOADING` | Active resumable upload stream to YouTube | `UPLOADED_PRIVATE`, `SCHEDULED`, `PUBLISHED`, `FAILED` |
| `UPLOADED_PRIVATE` | Uploaded in private archive mode | `SCHEDULED`, `PUBLISHED`, `ANALYTICS_PENDING`, `COMPLETED`, `FAILED` |
| `SCHEDULED` | Uploaded as private with future `publishAt` timestamp | `PUBLISHED`, `ANALYTICS_PENDING`, `COMPLETED`, `FAILED` |
| `PUBLISHED` | Publicly live on YouTube | `ANALYTICS_PENDING`, `COMPLETED`, `FAILED` |
| `ANALYTICS_PENDING` | Queued for 24h, 48h, 7d, 28d performance snapshots | `COMPLETED`, `ANALYTICS_PENDING`, `FAILED` |
| `COMPLETED` | Final lifecycle completion | `ANALYTICS_PENDING` |
| `FAILED` | Recoverable technical error (quota, network) | `TOPIC_SELECTED`, `VIDEO_RENDERING`, `UPLOAD_QUEUED` |
| `BLOCKED_QUALITY_GATE` | Non-recoverable quality failure with diagnostic report | `TOPIC_SELECTED`, `SCRIPT_GENERATED`, `FAILED` |

---

## 3. Automated Eligibility & Gate Enforcement

In `uploader/youtube.py`:
```python
# 1. Automated Quality Gate Evaluation
q_report = evaluate_all_quality_gates(
    research=research,
    script=script,
    video_path=video_path,
    thumb_path=thumb_path,
    metadata=metadata_dict,
    is_shorts=is_shorts,
)
if not q_report.get("passed", False):
    # Publication blocked; diagnostic persisted to output/diagnostics/
    return f"local://blocked_quality_gate/{filename}"

# 2. Idempotent Duplicate Prevention
if rec and rec.get("current_state") in (PublishingState.SCHEDULED, PublishingState.PUBLISHED):
    return existing_youtube_url
```

---

## 4. Quota and Retry Handling

- YouTube Data API v3 enforces daily quotas (typically 10,000 units/day).
- Upon encountering `quotaExceeded` or network interruption:
  1. The video state transitions to `FAILED` with error classification.
  2. An upload manifest is written to `output/pending_uploads/`.
  3. Rendered MP4 files and thumbnails remain intact; rendering is never re-run unnecessarily.
  4. Automation checks `production_database.json` to prevent retrying the exact same video file multiple times.
