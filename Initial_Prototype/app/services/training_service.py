"""Training session manager for the mock real-time training loop."""

from datetime import datetime
from typing import Dict, List, Optional

from app.services.algorithm_service import MockAlgorithmService


class TrainingSessionManager:
    def __init__(self):
        self.algorithm = MockAlgorithmService()
        self.reset()

    def reset(self) -> None:
        self.is_running = False
        self.expected_action = "Seated Knee Raise"
        self.start_time: Optional[datetime] = None
        self.frame_index = 0
        self.results: List[Dict] = []

    def start(self, expected_action: str) -> None:
        self.reset()
        self.expected_action = expected_action or "Seated Knee Raise"
        self.start_time = datetime.now()
        self.is_running = True

    def process_next_step(self) -> Dict:
        self.frame_index += 1
        result = self.algorithm.analyze_frame(self.expected_action, self.frame_index)
        self.results.append(result)
        return result

    def stop(self) -> Dict:
        end_time = datetime.now()
        duration_seconds = int((end_time - self.start_time).total_seconds()) if self.start_time else 0
        summary = self.algorithm.summarize_session(self.expected_action, self.results)

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
            "completion_rate": summary.get("completion_rate", 0),
            "pain_feedback": 2 if avg_score >= 85 else 3,
            "summary": summary["summary"],
            "doctor_recommendation": summary["doctor_recommendation"],
            "plan_adjustment": summary["plan_adjustment"],
            "scores": scores,
            "errors": list(error_map.values()),
            "compensations": list(compensation_map.values()),
            "feedbacks": feedbacks[-10:],
        }
        self.is_running = False
        return payload
