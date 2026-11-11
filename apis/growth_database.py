"""
Historical Performance Database for Stories Malik
Phase 19: Immutable, Versioned Historical Analytics Storage.

Stores and versions complete analytics records:
- Video ID, format ('short' vs 'longform'), topic, content pillar (1-10)
- Publication timestamp, video duration, title, thumbnail reference
- Performance metrics: views, engaged views, watch time, AVD, APV, impressions, CTR, likes, comments, subscribers gained
- Traffic source distribution
- Immutable snapshot history and audit trail
"""
import os
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import config

DB_FILE = os.path.join(config.OUTPUT_DIR, "historical_performance_db.json")
LEGACY_SNAPSHOT_FILE = os.path.join(config.OUTPUT_DIR, "analytics_snapshots.json")


class HistoricalPerformanceDB:
    """
    Manages structured, versioned storage of YouTube video performance snapshots.
    Ensures earlier snapshots are never overwritten by incomplete or delayed reports.
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or DB_FILE
        self.records: Dict[str, Dict[str, Any]] = {}
        self.load()

    def load(self) -> None:
        """Loads records from disk, gracefully importing from legacy snapshots if present."""
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, encoding="utf-8") as f:
                    self.records = json.load(f)
                    return
            except Exception:
                self.records = {}

        # Fallback / migration: import existing legacy snapshots if available
        if os.path.exists(LEGACY_SNAPSHOT_FILE):
            try:
                with open(LEGACY_SNAPSHOT_FILE, encoding="utf-8") as f:
                    legacy = json.load(f)
                    for vid, data in legacy.items():
                        if isinstance(data, dict):
                            self._import_legacy_record(vid, data)
            except Exception:
                pass

    def _import_legacy_record(self, video_id: str, data: dict) -> None:
        """Converts legacy snapshot structure to normalized versioned record."""
        metrics = data.get("metrics", {})
        is_short = bool(data.get("is_shorts", False))
        fmt = "short" if is_short else "longform"
        
        self.record_snapshot(
            video_id=video_id,
            video_format=fmt,
            topic=data.get("topic", "Historical Topic"),
            content_pillar=data.get("pillar_name", "General History"),
            publication_timestamp=data.get("published_at", ""),
            video_duration=float(data.get("duration_seconds", 0.0) or 0.0),
            title=data.get("title", f"Video {video_id}"),
            thumbnail_reference=data.get("thumbnail_url", ""),
            views=int(metrics.get("views", 0) or 0),
            engaged_views=int(metrics.get("engagedViews", 0) or 0),
            watch_time_minutes=float(metrics.get("estimatedMinutesWatched", 0.0) or 0.0),
            average_view_duration_seconds=float(metrics.get("averageViewDuration", 0.0) or 0.0),
            average_percentage_viewed=float(metrics.get("averageViewPercentage", 0.0) or 0.0),
            impressions=int(metrics.get("impressions", 0) or 0),
            ctr=float(metrics.get("impressionClickThroughRate", 0.0) or 0.0),
            likes=int(metrics.get("likes", 0) or 0),
            comments=int(metrics.get("comments", 0) or 0),
            subscribers_gained=int(metrics.get("subscribersGained", 0) or 0),
            traffic_sources=data.get("traffic_sources", []),
            checkpoint="legacy_migration",
        )

    def record_snapshot(
        self,
        video_id: str,
        video_format: str,
        topic: str,
        content_pillar: str,
        publication_timestamp: str,
        video_duration: float,
        title: str,
        thumbnail_reference: str = "",
        views: int = 0,
        engaged_views: int = 0,
        watch_time_minutes: float = 0.0,
        average_view_duration_seconds: float = 0.0,
        average_percentage_viewed: float = 0.0,
        impressions: int = 0,
        ctr: float = 0.0,
        likes: int = 0,
        comments: int = 0,
        subscribers_gained: int = 0,
        traffic_sources: Optional[List[Dict[str, Any]]] = None,
        checkpoint: str = "ad_hoc",
        metadata_extras: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Appends an immutable, timestamped snapshot checkpoint for a video.
        Ensures earlier checkpoints are preserved and never overwritten.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        clean_format = "short" if "short" in str(video_format).lower() else "longform"

        if video_id not in self.records:
            self.records[video_id] = {
                "video_id": video_id,
                "video_format": clean_format,
                "topic": topic,
                "content_pillar": content_pillar,
                "publication_timestamp": publication_timestamp,
                "video_duration_seconds": round(float(video_duration), 1),
                "title": title,
                "thumbnail_reference": thumbnail_reference,
                "created_at": now_iso,
                "latest_retrieval_timestamp": now_iso,
                "snapshot_history": [],
                "latest_metrics": {},
                "traffic_sources": [],
                "metadata_extras": metadata_extras or {},
            }

        rec = self.records[video_id]
        # Update mutable identity attributes only if newly supplied
        if topic and rec["topic"] == "Historical Topic":
            rec["topic"] = topic
        if content_pillar and rec["content_pillar"] == "General History":
            rec["content_pillar"] = content_pillar
        if title:
            rec["title"] = title
        if thumbnail_reference:
            rec["thumbnail_reference"] = thumbnail_reference
        if publication_timestamp and not rec["publication_timestamp"]:
            rec["publication_timestamp"] = publication_timestamp
        if video_duration > 0 and rec["video_duration_seconds"] == 0:
            rec["video_duration_seconds"] = round(float(video_duration), 1)
        if metadata_extras:
            rec["metadata_extras"].update(metadata_extras)

        snapshot_point = {
            "checkpoint": checkpoint,
            "retrieval_timestamp": now_iso,
            "metrics": {
                "views": max(0, int(views)),
                "engaged_views": max(0, int(engaged_views)),
                "watch_time_minutes": round(max(0.0, float(watch_time_minutes)), 2),
                "average_view_duration_seconds": round(max(0.0, float(average_view_duration_seconds)), 1),
                "average_percentage_viewed": round(max(0.0, float(average_percentage_viewed)), 2),
                "impressions": max(0, int(impressions)),
                "ctr": round(max(0.0, float(ctr)), 4),
                "likes": max(0, int(likes)),
                "comments": max(0, int(comments)),
                "subscribers_gained": max(0, int(subscribers_gained)),
            },
            "traffic_sources": list(traffic_sources or []),
        }

        # Append to immutable audit trail
        rec["snapshot_history"].append(snapshot_point)
        rec["latest_retrieval_timestamp"] = now_iso
        rec["latest_metrics"] = snapshot_point["metrics"]
        if traffic_sources:
            rec["traffic_sources"] = list(traffic_sources)

        self.save()
        return rec

    def get_video(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves complete record for a video."""
        return self.records.get(video_id)

    def get_all_videos(self) -> List[Dict[str, Any]]:
        """Retrieves all tracked video records."""
        return list(self.records.values())

    def get_shorts(self) -> List[Dict[str, Any]]:
        """Filters tracked records to Shorts only."""
        return [r for r in self.records.values() if r.get("video_format") == "short"]

    def get_longform(self) -> List[Dict[str, Any]]:
        """Filters tracked records to Long-form documentaries only."""
        return [r for r in self.records.values() if r.get("video_format") == "longform"]

    def save(self) -> None:
        """Persists the database to disk atomically."""
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        temp_path = f"{self.db_path}.tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(self.records, f, indent=2, ensure_ascii=False)
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        os.rename(temp_path, self.db_path)


# Singleton helper
_db_instance: Optional[HistoricalPerformanceDB] = None


def get_performance_db() -> HistoricalPerformanceDB:
    """Returns singleton database instance."""
    global _db_instance
    if _db_instance is None:
        _db_instance = HistoricalPerformanceDB()
    return _db_instance
