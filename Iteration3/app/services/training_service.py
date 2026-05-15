"""Training session manager for the mock real-time training loop."""

from datetime import datetime
from typing import Dict, List, Optional

from app.core.rehab_actions import DEFAULT_ACTION_NAME, get_action
from app.services.algorithm_service import MockAlgorithmService


class TrainingSessionManager:
    def __init__(self, algorithm_service=None):
        self.algorithm = algorithm_service or MockAlgorithmService()
        self.reset()

    def reset(self) -> None:
        self.is_running = False
        self.expected_action = DEFAULT_ACTION_NAME
        self.start_time: Optional[datetime] = None
        self.frame_index = 0
        self.results: List[Dict] = []
        self.sets_count = 3
        self.reps_per_set = 10
        self.hold_seconds = 2
        self.rep_count = 0
        self.current_set = 1
        self.last_peak_frame = -100
        self.last_low_frame = -100
        self.hold_counter = 0
        self.last_prompt_frame = -100
        self.prompt_cooldown_frames = 12

    def start(self, expected_action: str, sets_count: int = 3, reps_per_set: int = 10, hold_seconds: int = 2) -> None:
        self.reset()
        self.expected_action = get_action(expected_action or DEFAULT_ACTION_NAME).name
        self.start_time = datetime.now()
        self.sets_count = max(1, int(sets_count or 3))
        self.reps_per_set = max(1, int(reps_per_set or 10))
        self.hold_seconds = max(1, int(hold_seconds or 2))
        self.is_running = True

    def next_frame_context(self) -> Dict:
        self.frame_index += 1
        cycle_progress = (self.frame_index % 12) / 12
        elapsed = int((datetime.now() - self.start_time).total_seconds()) if self.start_time else 0
        return {
            "frame_index": self.frame_index,
            "cycle_progress": cycle_progress,
            "elapsed_seconds": elapsed,
        }

    def _update_rep_counter(self, leg_peak: float, phase: str) -> None:
        if phase == "Peak/Hold":
            self.hold_counter += 1
            if self.hold_counter >= self.hold_seconds and (self.frame_index - self.last_peak_frame) >= 4 and leg_peak >= 55:
                self.rep_count += 1
                self.last_peak_frame = self.frame_index
                self.hold_counter = 0
        elif phase == "Recovery":
            self.hold_counter = 0

    def _current_set_index(self) -> int:
        return min(self.sets_count, (self.rep_count // self.reps_per_set) + 1)

    def _completion_rate(self) -> float:
        total_target = self.sets_count * self.reps_per_set
        if total_target <= 0:
            return 0.0
        return max(0.0, min(1.0, self.rep_count / total_target))

    def _build_throttled_feedback(self, result: Dict) -> List[str]:
        raw = list(result.get("feedbacks", []))
        risks = [comp for comp in result.get("compensations", []) if comp.get("risk_level") in {"high", "medium"}]
        severe_errors = [err for err in result.get("errors", []) if err.get("severity") in {"high", "medium"}]
        should_prompt = False
        if risks or severe_errors:
            if (self.frame_index - self.last_prompt_frame) >= self.prompt_cooldown_frames:
                should_prompt = True
                self.last_prompt_frame = self.frame_index
        if should_prompt:
            return raw
        action = get_action(self.expected_action)
        return [f"Monitoring in progress... {action.first_cue}"]

    def process_next_step(self, frame_rgb=None) -> Dict:
        context = self.next_frame_context()
        try:
            result = self.algorithm.analyze_frame(
                self.expected_action,
                context["frame_index"],
                context["cycle_progress"],
                context["elapsed_seconds"],
                frame_rgb=frame_rgb,
            )
        except TypeError:
            result = self.algorithm.analyze_frame(
                self.expected_action,
                context["frame_index"],
                context["cycle_progress"],
                context["elapsed_seconds"],
            )
        return self.consume_external_result(result, frame_index=context["frame_index"])

    def consume_external_result(self, result: Dict, frame_index: Optional[int] = None) -> Dict:
        if frame_index is not None:
            self.frame_index = max(self.frame_index, int(frame_index))
        result["frame_index"] = int(frame_index or result.get("frame_index", self.frame_index))
        angles = result.get("lower_limb_angles", {})
        peak_leg_angle = max(angles.get("left_leg_angle", 0), angles.get("right_leg_angle", 0))
        self._update_rep_counter(peak_leg_angle, result.get("action_phase", "Execution"))
        self.current_set = self._current_set_index()
        completion_rate = self._completion_rate()

        result["rep_count"] = self.rep_count
        result["set_index"] = self.current_set
        result["set_progress"] = min(1.0, (self.rep_count % self.reps_per_set) / self.reps_per_set)
        result["completion_rate"] = completion_rate
        result["completion_status"] = "Completed" if completion_rate >= 1.0 else "In Progress"
        result["feedbacks"] = self._build_throttled_feedback(result)
        self.results.append(result)
        return result

    def stop(self) -> Dict:
        end_time = datetime.now()
        duration_seconds = int((end_time - self.start_time).total_seconds()) if self.start_time else 0
        completion_rate = self._completion_rate()
        summary = self.algorithm.summarize_session(self.expected_action, self.results, completion_rate)

        scores = []
        error_map = {}
        compensation_map = {}
        feedbacks = []

        for item in self.results:
            scores.append({
                "frame_index": item["frame_index"],
                "action_label": item["action_label"],
                "accuracy_score": item["accuracy_score"],
                "stability_score": item["stability_score"],
                "range_score": item["range_score"],
                "rhythm_score": item["rhythm_score"],
                "symmetry_score": item.get("symmetry_score", 0),
                "total_score": item["total_score"],
            })

            for err in item["errors"]:
                key = err["error_type"]
                if key not in error_map:
                    error_map[key] = err.copy()
                else:
                    error_map[key]["error_count"] += 1

            for comp in item["compensations"]:
                key = comp["compensation_type"]
                if key not in compensation_map:
                    compensation_map[key] = comp.copy()
                else:
                    compensation_map[key]["detected_count"] += 1

            for feedback in item["feedbacks"]:
                feedbacks.append({
                    "feedback_type": "realtime",
                    "feedback_content": feedback,
                    "source": "LLM-mock",
                })

        avg_score = round(sum(s["total_score"] for s in scores) / len(scores), 2) if scores else 0
        payload = {
            "action_name": self.expected_action,
            "session_start": self.start_time.strftime("%Y-%m-%d %H:%M:%S") if self.start_time else end_time.strftime("%Y-%m-%d %H:%M:%S"),
            "session_end": end_time.strftime("%Y-%m-%d %H:%M:%S"),
            "duration_seconds": duration_seconds,
            "avg_score": avg_score,
            "completion_rate": summary.get("completion_rate", completion_rate),
            "pain_feedback": 2 if avg_score >= 85 else 3,
            "summary": summary["summary"],
            "doctor_recommendation": summary["doctor_recommendation"],
            "plan_adjustment": summary["plan_adjustment"],
            "total_reps": self.rep_count,
            "sets_count": self.sets_count,
            "reps_per_set": self.reps_per_set,
            "scores": scores,
            "errors": list(error_map.values()),
            "compensations": list(compensation_map.values()),
            "feedbacks": feedbacks[-10:],
        }
        self.is_running = False
        return payload
