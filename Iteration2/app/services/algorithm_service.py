"""Mock algorithm service for V2.

The V2 goal is to mimic a YOLO-pose + LLM pipeline while still remaining runnable
without GPU or cloud dependencies. This service now outputs:
1. Lower-limb keypoint-derived angles (simulated)
2. Action phase labels
3. Error/compensation tags
4. Itemized quality scores
"""

import random
from datetime import datetime
from typing import Dict, List, Tuple


ACTIONS = ["Seated Knee Raise", "Half Squat", "Step-Up March", "Straight Leg Raise"]

ACTION_RULES = {
    "Seated Knee Raise": {"target_peak": 78, "rom_min": 55},
    "Half Squat": {"target_peak": 95, "rom_min": 70},
    "Step-Up March": {"target_peak": 84, "rom_min": 60},
    "Straight Leg Raise": {"target_peak": 72, "rom_min": 50},
}


class MockAlgorithmService:
    """Return structured pseudo pose-recognition outputs for demos."""

    def _phase_from_progress(self, progress: float) -> str:
        if progress < 0.2:
            return "Start"
        if progress < 0.65:
            return "Execution"
        if progress < 0.82:
            return "Peak/Hold"
        return "Recovery"

    def _generate_angles(self, expected_action: str, progress: float) -> Tuple[float, float, float, float]:
        rule = ACTION_RULES.get(expected_action, ACTION_RULES["Seated Knee Raise"])
        peak = rule["target_peak"]
        wave = progress if progress <= 0.5 else (1 - progress)
        amplitude = (wave / 0.5) * peak
        affected_leg = max(10.0, min(peak + 5, amplitude + random.uniform(-6, 6)))
        healthy_leg = max(12.0, min(peak + 8, amplitude + random.uniform(-4, 4)))
        trunk_angle = max(3.0, min(35.0, random.uniform(6, 20) + (0 if progress < 0.65 else random.uniform(-1, 5))))
        knee_valgus = max(0.0, min(20.0, random.uniform(2, 12)))
        return round(affected_leg, 2), round(healthy_leg, 2), round(trunk_angle, 2), round(knee_valgus, 2)

    def analyze_frame(
        self,
        expected_action: str = "Seated Knee Raise",
        frame_index: int = 1,
        cycle_progress: float = 0.0,
        elapsed_seconds: int = 0,
    ) -> Dict:
        action = expected_action if random.random() > 0.12 else random.choice(ACTIONS)
        phase = self._phase_from_progress(cycle_progress)
        left_leg_angle, right_leg_angle, trunk_angle, knee_valgus = self._generate_angles(expected_action, cycle_progress)
        target_rule = ACTION_RULES.get(expected_action, ACTION_RULES["Seated Knee Raise"])

        symmetry_delta = abs(left_leg_angle - right_leg_angle)
        range_ok = max(left_leg_angle, right_leg_angle) >= target_rule["rom_min"]
        rhythm_ref = 4.0
        rhythm_variance = abs((elapsed_seconds % 8) - rhythm_ref)

        accuracy = max(55.0, 96 - symmetry_delta * 1.1 - knee_valgus * 0.8 + random.uniform(-3, 2))
        stability = max(50.0, 95 - trunk_angle * 1.2 + random.uniform(-2, 3))
        range_score = max(50.0, 96 - max(0, target_rule["rom_min"] - max(left_leg_angle, right_leg_angle)) * 1.6)
        rhythm_score = max(52.0, 95 - rhythm_variance * 4 + random.uniform(-2, 2))
        symmetry_score = max(50.0, 96 - symmetry_delta * 2.3)
        total_score = round((accuracy + stability + range_score + rhythm_score + symmetry_score) / 5, 2)

        errors: List[Dict] = []
        compensations: List[Dict] = []
        feedbacks: List[str] = []

        if not range_ok:
            errors.append({
                "error_type": "Insufficient leg raise height",
                "error_count": 1,
                "severity": "medium",
                "suggestion": "Raise the affected leg slightly higher in a pain-free range.",
            })
        if knee_valgus > 10:
            errors.append({
                "error_type": "Knee valgus",
                "error_count": 1,
                "severity": "high" if knee_valgus > 13 else "medium",
                "suggestion": "Keep the knee aligned with the second toe.",
            })
        if trunk_angle > 17:
            errors.append({
                "error_type": "Excessive trunk leaning",
                "error_count": 1,
                "severity": "medium",
                "suggestion": "Keep the trunk upright and engage your core.",
            })
        if symmetry_delta > 12:
            errors.append({
                "error_type": "Left-right asymmetry",
                "error_count": 1,
                "severity": "medium",
                "suggestion": "Control both sides evenly and slow down the stronger side.",
            })

        if trunk_angle > 20:
            compensations.append({
                "compensation_type": "Forward trunk compensation",
                "detected_count": 1,
                "risk_level": "high",
                "suggestion": "Reduce range temporarily and re-stabilize trunk posture.",
            })
        if symmetry_delta > 14:
            compensations.append({
                "compensation_type": "Support-side shift",
                "detected_count": 1,
                "risk_level": "medium",
                "suggestion": "Keep pelvis centered and distribute load more symmetrically.",
            })
        if random.random() < 0.1:
            compensations.append({
                "compensation_type": "Swing momentum compensation",
                "detected_count": 1,
                "risk_level": "low",
                "suggestion": "Avoid swinging; drive movement with controlled muscle effort.",
            })

        if errors:
            feedbacks.append(f"Detected {errors[0]['error_type']}. {errors[0]['suggestion']}")
        if compensations:
            feedbacks.append(f"Detected {compensations[0]['compensation_type']}. {compensations[0]['suggestion']}")
        if not feedbacks:
            feedbacks.append("Good control. Keep this rhythm and posture.")

        return {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "frame_index": frame_index,
            "action_label": action,
            "action_phase": phase,
            "lower_limb_angles": {
                "left_leg_angle": left_leg_angle,
                "right_leg_angle": right_leg_angle,
                "trunk_forward_angle": trunk_angle,
                "knee_valgus_angle": knee_valgus,
            },
            "roi_box": {"x": 160, "y": 70, "w": 360, "h": 420},
            "accuracy_score": round(accuracy, 2),
            "stability_score": round(stability, 2),
            "range_score": round(range_score, 2),
            "rhythm_score": round(rhythm_score, 2),
            "symmetry_score": round(symmetry_score, 2),
            "total_score": total_score,
            "errors": errors,
            "compensations": compensations,
            "feedbacks": feedbacks,
        }

    def summarize_session(self, expected_action: str, results: List[Dict], completion_rate: float) -> Dict:
        if not results:
            return {
                "summary": "No valid training data was collected in this session.",
                "doctor_recommendation": "Please restart the session and check the camera or algorithm connection.",
                "plan_adjustment": None,
            }

        avg_score = round(sum(item["total_score"] for item in results) / len(results), 2)
        low_frames = sum(1 for item in results if item["total_score"] < 80)
        high_risk = sum(
            1
            for item in results
            for comp in item["compensations"]
            if comp.get("risk_level") == "high"
        )

        if avg_score >= 88 and completion_rate >= 0.9:
            summary = f"Overall quality for this {expected_action} session was excellent with stable control."
            recommendation = "You can progress with slightly higher difficulty or longer hold time."
            adjustment = {
                "reason": "Strong performance and high completion",
                "detail": "Increase difficulty by one level or increase hold time by 1-2 seconds.",
                "decision": "Increase hold time",
            }
        elif avg_score >= 78 and completion_rate >= 0.75:
            summary = f"The {expected_action} session met most targets but still shows room for correction."
            recommendation = "Keep intensity stable and prioritize knee alignment and trunk control cues."
            adjustment = {
                "reason": "Stable yet improvable quality",
                "detail": "Maintain current set/rep volume and reinforce corrective guidance.",
                "decision": "Keep current plan",
            }
        else:
            summary = f"The {expected_action} session quality was below target with recurrent deviations."
            recommendation = "Lower difficulty, reduce pace, and focus on movement pattern correction."
            adjustment = {
                "reason": "Low quality or insufficient completion",
                "detail": "Decrease volume and add unilateral basic corrective drills.",
                "decision": "Lower difficulty",
            }

        summary += f" {len(results)} frames analyzed, {low_frames} low-score segments, {high_risk} high-risk compensations."
        return {
            "summary": summary,
            "doctor_recommendation": recommendation,
            "completion_rate": completion_rate,
            "plan_adjustment": adjustment,
        }
