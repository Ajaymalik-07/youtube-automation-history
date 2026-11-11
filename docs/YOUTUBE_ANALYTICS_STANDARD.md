# YouTube Analytics API Integration Standard
**YouTube Agentic AI Studio (YAAS)**  
**Channel:** Stories Malik  
**Canonical Specification Reference:** `docs/YOUTUBE_ANALYTICS_STANDARD.md`  

---

## 1. Overview & Authorized API Scope

Stories Malik utilizes the official YouTube Analytics API (v2) under owner-authorized OAuth 2.0 to collect verified first-party audience retention, watch time, and traffic source insights.

### Required OAuth Scopes
To access private video performance data, the following scope is required:
* `https://www.googleapis.com/auth/yt-analytics.readonly`
* `https://www.googleapis.com/auth/youtube.readonly`

---

## 2. Tracked Performance Metrics

| Metric Dimension | API Dimension / Metric | Long-Form Treatment | Shorts Treatment |
| :--- | :--- | :--- | :--- |
| **Views** | `views` | Total views accumulated | Total views & engaged views |
| **Watch Time** | `estimatedMinutesWatched` | Cumulative minutes watched | Total seconds watched |
| **Average View Duration (AVD)** | `averageViewDuration` | Measured in minutes/seconds | Key velocity signal (seconds) |
| **Average Percentage Viewed (APV)** | `averageViewPercentage` | Critical retention benchmark (>45% ideal) | Completion benchmark (>85% ideal) |
| **Engagement** | `likes`, `comments` | Viewer sentiment indicator | Engagement ratio per 1,000 views |
| **Subscriber Conversion** | `subscribersGained` | Conversion per video release | Subscriber acquisition velocity |
| **Traffic Source** | `insightTrafficSourceType` | Browse, Search, Suggested | Shorts feed vs Search |

> [!IMPORTANT]
> The engine never fabricates metrics. If YouTube Analytics API access is unavailable or delayed by YouTube's 48-hour processing window, the system clearly reports data status and falls back safely to YouTube Data API v3 public stats.

---

## 3. Performance Checkpoints Architecture

Analytics snapshots are recorded at standardized post-publication intervals to monitor growth curves:
* **24 Hours:** Initial audience click-through and hook retention.
* **48 Hours:** Recommended feed velocity and algorithmic distribution.
* **7 Days:** Stabilized evergreen search and browse traction.
* **28 Days:** Mature civilizational documentary benchmark.

All checkpoints are saved in `output/analytics_snapshots.json` for historical comparison.
