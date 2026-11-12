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
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
import config
from agents.statistical_validator import (
    calculate_mean_and_confidence_interval,
    compute_welch_t_test,
)
from uploader.safety import CrossProcessFileLock

EXPERIMENTS_FILE = os.path.join(config.OUTPUT_DIR, "growth_experiments.json")

VALID_EXPERIMENT_CATEGORIES = [
    "hook_variation",
    "topic_cluster",
    "video_duration",
    "title_approach",
    "thumbnail_concept",
    "publishing_window",
    "narrative_structure",
    "publishing_frequency",
]

MIN_SAMPLE_SIZE_FOR_CONCLUSION = 3
MIN_LONGFORM_BASELINE_FOR_FREQUENCY_CHANGE = 10
MIN_SHORTS_BASELINE_FOR_FREQUENCY_CHANGE = 30


def validate_frequency_experiment_proposal(proposal: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validates a proposed publishing frequency experiment against the Phase 21 Adaptive Publishing Policy:
    1. Must have a documented hypothesis.
    2. Must change only ONE major variable at a time (rejects simultaneous variable changes).
    3. Must define measurable success criteria.
    4. Must preserve a baseline comparison (e.g. 1 long-form + 5 Shorts daily in Asia/Kolkata).
    5. Must demonstrate sufficient baseline evidence before recommending any reduction/change.
    """
    issues: List[str] = []
    hypothesis = str(proposal.get("hypothesis", "")).strip()
    if len(hypothesis) < 15:
        issues.append("Frequency experiment must include a documented hypothesis.")

    changed_vars = proposal.get("changed_variables", [])
    if not isinstance(changed_vars, list) or len(changed_vars) != 1:
        issues.append(
            f"Frequency experiment must change exactly 1 major variable at a time (received: {changed_vars})."
        )
    if proposal.get("simultaneous_variable_changes"):
        issues.append("Simultaneous changes to multiple publishing variables are forbidden.")

    success_criteria = proposal.get("success_criteria")
    if not success_criteria or (isinstance(success_criteria, str) and len(success_criteria.strip()) < 10):
        issues.append("Frequency experiment must define measurable success criteria.")

    baseline_comp = proposal.get("baseline_comparison") or proposal.get("control_variant")
    if not baseline_comp:
        issues.append("Frequency experiment must preserve a baseline comparison.")

    baseline_longform_n = int(proposal.get("baseline_longform_samples", 0) or 0)
    baseline_shorts_n = int(proposal.get("baseline_shorts_samples", 0) or 0)
    if (
        baseline_longform_n < MIN_LONGFORM_BASELINE_FOR_FREQUENCY_CHANGE
        or baseline_shorts_n < MIN_SHORTS_BASELINE_FOR_FREQUENCY_CHANGE
    ):
        issues.append(
            f"Insufficient baseline evidence for frequency change "
            f"(observed: {baseline_longform_n} long-form, {baseline_shorts_n} Shorts; "
            f"minimum required: {MIN_LONGFORM_BASELINE_FOR_FREQUENCY_CHANGE} long-form and "
            f"{MIN_SHORTS_BASELINE_FOR_FREQUENCY_CHANGE} Shorts over rolling 30-day baseline)."
        )

    return len(issues) == 0, issues


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
        metric_value: Optional[float],
        notes: str = "",
    ) -> Dict[str, Any]:
        """Records an observed result for an active experiment (rejects unavailable None metrics)."""
        if metric_value is None:
            raise ValueError("Cannot record experiment sample: metric_value is unavailable (None).")
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
        """
        Evaluates experiment status with confidence intervals, Welch's t-test,
        and Bonferroni multiple-comparisons adjustment across active/evaluated experiments.
        """
        exp.setdefault("baseline", exp.get("control_variant", "Standard baseline"))
        exp.setdefault("primary_variable", exp.get("category", "single_variable"))
        exp.setdefault("evaluation_window_days", getattr(config, "EVALUATION_WINDOW_DAYS", 30))

        samples = [s for s in exp["samples"] if s.get("metric_value") is not None]
        min_samples = exp.get("min_sample_size", MIN_SAMPLE_SIZE_FOR_CONCLUSION)
        m_comparisons = max(1, len(self.experiments))
        adj_alpha = round(0.05 / m_comparisons, 4)

        control_vals = [float(s["metric_value"]) for s in samples if s["variant"].lower() == "control"]
        test_vals = [float(s["metric_value"]) for s in samples if s["variant"].lower() == "test"]
        ctrl_ci = calculate_mean_and_confidence_interval(control_vals)
        test_ci = calculate_mean_and_confidence_interval(test_vals)
        t_res = compute_welch_t_test(control_vals, test_vals)
        p_val = float(t_res.get("p_value", 1.0)) if t_res.get("valid_test") else 1.0
        sig_bonferroni = bool(t_res.get("valid_test") and p_val < adj_alpha)

        exp["uncertainty_report"] = {
            "control_ci_95": ctrl_ci,
            "test_ci_95": test_ci,
            "welch_t_test": t_res,
            "multiple_comparisons_count": m_comparisons,
            "multiple_comparison_adjusted_alpha": adj_alpha,
            "bonferroni_significant": sig_bonferroni,
        }

        if len(samples) < min_samples:
            exp["status"] = "in_progress"
            exp["confidence_level"] = "preliminary (low sample size)"
            exp["conclusion"] = f"Gathered {len(samples)}/{min_samples} required video observations. No statistically defensible conclusion yet."
            return

        if not control_vals or not test_vals:
            exp["status"] = "in_progress"
            exp["confidence_level"] = "insufficient_variants"
            exp["conclusion"] = "Both control and test samples are required to determine a statistical winner."
            return

        # Strict significance gate when experiment explicitly requires statistical validation
        if exp.get("require_statistical_significance") and not sig_bonferroni:
            exp["status"] = "in_progress"
            exp["confidence_level"] = f"preliminary (p={p_val:.4f} >= bonferroni_alpha={adj_alpha})"
            exp["conclusion"] = (
                f"Observed {len(control_vals)} control vs {len(test_vals)} test samples "
                f"(p={p_val:.4f}, adjusted threshold={adj_alpha}). Insufficient evidence to declare a winner."
            )
            return

        avg_ctrl = sum(control_vals) / len(control_vals)
        avg_test = sum(test_vals) / len(test_vals)

        exp["status"] = "completed"
        exp["confidence_level"] = (
            f"statistically_sound (p={p_val:.4f} < {adj_alpha})"
            if sig_bonferroni
            else f"moderate (sample size >= {min_samples}, exploratory)"
        )
        delta = round(avg_test - avg_ctrl, 2)
        if delta > 0:
            exp["conclusion"] = f"Test variant outperformed control by +{delta} on {exp['target_metric']} (Control Avg: {avg_ctrl:.2f}, Test Avg: {avg_test:.2f}). Hypothesis validated."
        else:
            exp["conclusion"] = f"Test variant did not outperform control ({delta} on {exp['target_metric']}, Control Avg: {avg_ctrl:.2f}, Test Avg: {avg_test:.2f}). Retain control or iterate variant."

    def register_controlled_experiment(self, proposal: Dict[str, Any]) -> Dict[str, Any]:
        """
        Registers a strictly controlled single-variable experiment enforcing Phase 23 rules:
        hypothesis, baseline, 1 primary variable, success metric, min samples >= 6,
        30-day window, and Bonferroni significance requirement.
        """
        hypothesis = str(proposal.get("hypothesis", "")).strip()
        if len(hypothesis) < 15:
            raise ValueError("Controlled experiment requires a documented hypothesis (>= 15 chars).")
        vars_list = proposal.get("changed_variables") or ([proposal["primary_variable"]] if proposal.get("primary_variable") else [])
        if not isinstance(vars_list, list) or len(vars_list) != 1:
            raise ValueError("Controlled experiment must isolate exactly 1 primary variable.")
        if not proposal.get("baseline") and not proposal.get("control_variant"):
            raise ValueError("Controlled experiment must specify a baseline / control_variant.")
        if not proposal.get("success_metric") and not proposal.get("target_metric"):
            raise ValueError("Controlled experiment must define a measurable success_metric.")

        exp_id = proposal.get("id") or f"EXP-{len(self.experiments) + 1:03d}"
        rec = {
            "id": exp_id,
            "name": proposal.get("name", f"Experiment {exp_id}"),
            "category": proposal.get("category", "hook_variation"),
            "target_format": proposal.get("target_format", "short"),
            "hypothesis": hypothesis,
            "baseline": proposal.get("baseline") or proposal.get("control_variant"),
            "primary_variable": vars_list[0],
            "changed_variables": list(vars_list),
            "target_metric": proposal.get("success_metric") or proposal.get("target_metric"),
            "control_variant": proposal.get("baseline") or proposal.get("control_variant"),
            "test_variant": proposal.get("test_variant", "Variant B"),
            "min_sample_size": max(6, int(proposal.get("min_sample_size", 6))),
            "evaluation_window_days": int(proposal.get("evaluation_window_days", getattr(config, "EVALUATION_WINDOW_DAYS", 30))),
            "require_statistical_significance": True,
            "auto_apply_to_schedule": False,
            "current_samples": 0,
            "status": "in_progress",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "samples": [],
            "conclusion": None,
            "confidence_level": "insufficient_data",
        }
        self.experiments.append(rec)
        self.save()
        return rec

    def get_active_experiments(self) -> List[Dict[str, Any]]:
        """Returns list of active experiments."""
        return [e for e in self.experiments if e.get("status") == "in_progress"]

    def get_all_experiments(self) -> List[Dict[str, Any]]:
        """Returns all experiments."""
        return list(self.experiments)

    def create_frequency_experiment(self, proposal: Dict[str, Any]) -> Dict[str, Any]:
        """
        Registers a controlled publishing-frequency experiment ONLY if it passes
        all Phase 21 Adaptive Publishing Policy rules. Never mutates the active
        production schedule automatically.
        """
        ok, issues = validate_frequency_experiment_proposal(proposal)
        if not ok:
            raise ValueError("Frequency experiment rejected by Adaptive Publishing Policy: " + "; ".join(issues))

        exp_id = proposal.get("id") or f"EXP-FREQ-{len(self.experiments) + 1:03d}"
        exp_record = {
            "id": exp_id,
            "name": proposal.get("name", "Controlled Frequency Experiment"),
            "category": "publishing_frequency",
            "target_format": proposal.get("target_format", "all"),
            "hypothesis": proposal["hypothesis"],
            "changed_variables": list(proposal["changed_variables"]),
            "target_metric": proposal.get("target_metric", "median_views_and_apv"),
            "success_criteria": proposal["success_criteria"],
            "control_variant": proposal.get("baseline_comparison") or proposal.get("control_variant"),
            "test_variant": proposal.get("test_variant", ""),
            "baseline_cadence": {
                "longform_per_day": getattr(config, "LONGFORM_DAILY_COUNT", 1),
                "shorts_per_day": getattr(config, "SHORTS_DAILY_COUNT", 5),
                "timezone": getattr(config, "PUBLISHING_TIMEZONE", "Asia/Kolkata"),
            },
            "auto_apply_to_schedule": False,
            "min_sample_size": max(MIN_SAMPLE_SIZE_FOR_CONCLUSION, int(proposal.get("min_sample_size", 5))),
            "current_samples": 0,
            "status": "in_progress",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "samples": [],
            "conclusion": None,
            "confidence_level": "insufficient_data",
        }
        self.experiments.append(exp_record)
        self.save()
        return exp_record

    def save(self) -> None:
        """Persists experiments atomically under cross-process lock."""
        os.makedirs(os.path.dirname(os.path.abspath(self.storage_path)), exist_ok=True)
        with CrossProcessFileLock(f"{self.storage_path}.lock"):
            tmp_path = f"{self.storage_path}.{uuid.uuid4().hex[:8]}.tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self.experiments, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, self.storage_path)


# Singleton
_tracker_instance: Optional[ExperimentTracker] = None


def get_experiment_tracker() -> ExperimentTracker:
    """Returns singleton experiment tracker instance."""
    global _tracker_instance
    if _tracker_instance is None:
        _tracker_instance = ExperimentTracker()
    return _tracker_instance
