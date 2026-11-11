"""
Controlled Growth Experimentation Framework for Stories Malik
Phase 19: Scientific YouTube Publishing & Production Experiments.

Supports controlled, evidence-based experiments:
- Hook variations (intrigue question vs bold contradiction vs dramatic artifact)
- Topic clusters (ancient civilizations vs battles vs architecture)
- Video duration (8-10 min vs 11-13 min; 30s vs 55s Shorts)
- Title approaches (Search-oriented vs Story-oriented vs Curiosity-oriented)
- Thumbnail concepts (Impact vs Cinematic vs Split vs Studio)
- Publishing windows (17:00, 18:00, 19:00, 20:00, 21:00 IST)
- Narrative structures (chronological vs in media res vs forensic investigation)

Enforces sample size thresholds to avoid drawing false conclusions from 1-2 videos.
"""
import os
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import config

EXPERIMENTS_FILE = os.path.join(config.OUTPUT_DIR, "growth_experiments.json")

VALID_EXPERIMENT_CATEGORIES = [
    "hook_variation",
    "topic_cluster",
    "video_duration",
    "title_approach",
    "thumbnail_concept",
    "publishing_window",
    "narrative_structure",
]

MIN_SAMPLE_SIZE_FOR_CONCLUSION = 3


class ExperimentTracker:
    """Manages creation, evaluation, and documentation of YouTube growth experiments."""

    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = storage_path or EXPERIMENTS_FILE
        self.experiments: List[Dict[str, Any]] = []
        self.load()

    def load(self) -> None:
        """Loads experiments from storage."""
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, encoding="utf-8") as f:
                    self.experiments = json.load(f)
            except Exception:
                self.experiments = []
        else:
            self._seed_default_experiments()

    def _seed_default_experiments(self) -> None:
        """Seeds initial controlled production experiments for Stories Malik."""
        now_iso = datetime.now(timezone.utc).isoformat()
        self.experiments = [
            {
                "id": "EXP-001",
                "name": "Shorts Opening Hook Pacing",
                "category": "hook_variation",
                "target_format": "short",
                "hypothesis": "Opening with an archaeological artifact contradiction in the first 2.5s achieves >= 75% APV compared to narrative storytelling introductions.",
                "target_metric": "average_percentage_viewed",
                "control_variant": "Standard narrative intro",
                "test_variant": "High-contrast visual paradox + direct question",
                "min_sample_size": 3,
                "current_samples": 0,
                "status": "in_progress",
                "created_at": now_iso,
                "samples": [],
                "conclusion": None,
                "confidence_level": "insufficient_data",
            },
            {
                "id": "EXP-002",
                "name": "Long-form Title Pacing: Curiosity vs Search",
                "category": "title_approach",
                "target_format": "longform",
                "hypothesis": "Curiosity-oriented titles with historical contradictions generate higher CTR and subscriber conversions than generic search titles.",
                "target_metric": "ctr",
                "control_variant": "Search-oriented title",
                "test_variant": "Curiosity-oriented contradiction title",
                "min_sample_size": 3,
                "current_samples": 0,
                "status": "in_progress",
                "created_at": now_iso,
                "samples": [],
                "conclusion": None,
                "confidence_level": "insufficient_data",
            },
            {
                "id": "EXP-003",
                "name": "Ancient Engineering Retention Lift",
                "category": "topic_cluster",
                "target_format": "longform",
                "hypothesis": "Pillar 5 (Ancient Engineering & Architecture) with technical 3D diagrams yields >= 50% AVD compared to dynastic biography chronicles.",
                "target_metric": "average_percentage_viewed",
                "control_variant": "Dynastic biography narrative",
                "test_variant": "Step-by-step engineering forensics with architectural diagrams",
                "min_sample_size": 3,
                "current_samples": 0,
                "status": "in_progress",
                "created_at": now_iso,
                "samples": [],
                "conclusion": None,
                "confidence_level": "insufficient_data",
            },
        ]
        self.save()

    def record_experiment_sample(
        self,
        experiment_id: str,
        video_id: str,
        variant: str,
        metric_value: float,
        notes: str = "",
    ) -> Dict[str, Any]:
        """Records an observed result for an active experiment."""
        exp = next((e for e in self.experiments if e["id"] == experiment_id), None)
        if not exp:
            raise ValueError(f"Experiment ID '{experiment_id}' not found.")

        exp["samples"].append({
            "video_id": video_id,
            "variant": variant,
            "metric_value": float(metric_value),
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "notes": notes,
        })
        exp["current_samples"] = len(exp["samples"])
        self._evaluate_experiment(exp)
        self.save()
        return exp

    def _evaluate_experiment(self, exp: Dict[str, Any]) -> None:
        """Evaluates experiment status based on recorded sample data."""
        samples = exp["samples"]
        min_samples = exp.get("min_sample_size", MIN_SAMPLE_SIZE_FOR_CONCLUSION)

        if len(samples) < min_samples:
            exp["status"] = "in_progress"
            exp["confidence_level"] = "preliminary (low sample size)"
            exp["conclusion"] = f"Gathered {len(samples)}/{min_samples} required video observations. No statistically defensible conclusion yet."
            return

        control_vals = [s["metric_value"] for s in samples if s["variant"].lower() == "control"]
        test_vals = [s["metric_value"] for s in samples if s["variant"].lower() == "test"]

        if not control_vals or not test_vals:
            exp["status"] = "in_progress"
            exp["confidence_level"] = "insufficient_variants"
            exp["conclusion"] = "Both control and test samples are required to determine a statistical winner."
            return

        avg_ctrl = sum(control_vals) / len(control_vals)
        avg_test = sum(test_vals) / len(test_vals)

        exp["status"] = "completed"
        exp["confidence_level"] = "moderate (sample size >= 3)"
        delta = round(avg_test - avg_ctrl, 2)
        if delta > 0:
            exp["conclusion"] = f"Test variant outperformed control by +{delta} on {exp['target_metric']} (Control Avg: {avg_ctrl:.2f}, Test Avg: {avg_test:.2f}). Hypothesis validated."
        else:
            exp["conclusion"] = f"Test variant did not outperform control ({delta} on {exp['target_metric']}, Control Avg: {avg_ctrl:.2f}, Test Avg: {avg_test:.2f}). Retain control or iterate variant."

    def get_active_experiments(self) -> List[Dict[str, Any]]:
        """Returns list of active experiments."""
        return [e for e in self.experiments if e.get("status") == "in_progress"]

    def get_all_experiments(self) -> List[Dict[str, Any]]:
        """Returns all experiments."""
        return list(self.experiments)

    def save(self) -> None:
        """Persists experiments to disk."""
        os.makedirs(os.path.dirname(os.path.abspath(self.storage_path)), exist_ok=True)
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(self.experiments, f, indent=2, ensure_ascii=False)


# Singleton
_tracker_instance: Optional[ExperimentTracker] = None


def get_experiment_tracker() -> ExperimentTracker:
    """Returns singleton experiment tracker instance."""
    global _tracker_instance
    if _tracker_instance is None:
        _tracker_instance = ExperimentTracker()
    return _tracker_instance
