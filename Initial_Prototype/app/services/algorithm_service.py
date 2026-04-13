"""Mock algorithm service.

This module is only a placeholder for the first development stage. In later stages you
can replace `analyze_frame` with real outputs from YOLO pose/action recognition, and
replace the summary generation with an LLM-based feedback generator.
"""

import random
from datetime import datetime
from typing import Dict, List


ACTIONS = ["Seated Knee Raise", "Half Squat", "Step-Up March", "Straight Leg Raise"]
ERROR_LIBRARY = [
    ("Knee valgus", "Keep the knee aligned with the toes."),
    ("Insufficient range", "Lift slightly higher within a safe and pain-free range."),
    ("Rhythm too fast", "Slow down and keep a steady rhythm."),
]
COMPENSATION_LIBRARY = [
    ("Pelvic tilt compensation", "Engage the core and avoid side-to-side trunk sway."),
    ("Forward trunk lean", "Keep the torso upright and avoid excessive forward lean."),
    ("Overuse of the healthy side", "Make sure the affected side actively participates."),
]


class MockAlgorithmService:
    """Return mock action labels, scores, errors, and feedback for demos."""

    def analyze_frame(self, expected_action: str = "Seated Knee Raise", frame_index: int = 1) -> Dict:
        action = expected_action if random.random() > 0.15 else random.choice(ACTIONS)
        accuracy = random.uniform(72, 96)
        stability = random.uniform(68, 95)
        range_score = random.uniform(65, 94)
        rhythm_score = random.uniform(70, 95)
        total_score = round((accuracy + stability + range_score + rhythm_score) / 4, 2)

        errors: List[Dict] = []
        compensations: List[Dict] = []
        feedbacks: List[str] = []

        if total_score < 80 or random.random() < 0.35:
            error_type, suggestion = random.choice(ERROR_LIBRARY)
            errors.append({
                "error_type": error_type,
                "error_count": 1,
                "severity": random.choice(["low", "medium", "high"]),
                "suggestion": suggestion,
            })
            feedbacks.append(f"Detected {error_type}. {suggestion}")

        if total_score < 78 or random.random() < 0.25:
            compensation_type, suggestion = random.choice(COMPENSATION_LIBRARY)
            compensations.append({
                "compensation_type": compensation_type,
                "detected_count": 1,
                "risk_level": random.choice(["low", "medium", "high"]),
                "suggestion": suggestion,
            })
            feedbacks.append(f"Detected {compensation_type}. {suggestion}")

        if not feedbacks:
            feedbacks.append("Movement quality is stable. Keep the current rhythm.")

        return {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "frame_index": frame_index,
            "action_label": action,
            "accuracy_score": round(accuracy, 2),
            "stability_score": round(stability, 2),
            "range_score": round(range_score, 2),
            "rhythm_score": round(rhythm_score, 2),
            "total_score": total_score,
            "errors": errors,
            "compensations": compensations,
            "feedbacks": feedbacks,
        }

    def summarize_session(self, expected_action: str, results: List[Dict]) -> Dict:
        if not results:
            return {
                "summary": "No valid training data was collected in this session.",
                "doctor_recommendation": "Please restart the session and check the camera or algorithm connection.",
                "plan_adjustment": None,
            }

        avg_score = round(sum(item["total_score"] for item in results) / len(results), 2)
        low_frames = sum(1 for item in results if item["total_score"] < 80)
        completion_rate = round(max(0.6, min(1.0, avg_score / 100 + 0.1)), 2)

        if avg_score >= 88:
            summary = f"Overall quality for this {expected_action} session was excellent, with good stability and rhythm control."
            recommendation = "Consider gradually increasing the difficulty level or the number of repetitions per set."
            adjustment = {
                "reason": "Strong training performance",
                "detail": "Consider increasing repetitions by 10% to 15% and adding a more advanced stability task in the next phase.",
            }
        elif avg_score >= 78:
            summary = f"The {expected_action} session met the target overall, but a few movement errors still need consolidation."
            recommendation = "Keep the current plan and focus on correcting error actions and compensation patterns."
            adjustment = {
                "reason": "Stable but improvable performance",
                "detail": "Keep the current intensity and reinforce knee alignment and trunk stability in the real-time guidance prompts.",
            }
        else:
            summary = f"The {expected_action} session scored relatively low, with obvious movement deviation or compensation patterns."
            recommendation = "Reduce the pace, lower the repetition count, and prioritize basic movement correction."
            adjustment = {
                "reason": "Low training quality",
                "detail": "Lower the difficulty by one level, shorten the session duration, and increase the frequency of real-time text or voice guidance.",
            }

        return {
            "summary": summary + f" A total of {len(results)} time points were analyzed, with {low_frames} low-score segments.",
            "doctor_recommendation": recommendation,
            "completion_rate": completion_rate,
            "plan_adjustment": adjustment,
        }
