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

from app.core.rehab_actions import DEFAULT_ACTION_NAME, get_action, get_action_names, get_action_rules


ACTIONS = get_action_names()
ACTION_RULES = get_action_rules()


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
        rule = ACTION_RULES.get(get_action(expected_action).name, ACTION_RULES[DEFAULT_ACTION_NAME])
        peak = rule["target_peak"]
        wave = progress if progress <= 0.5 else (1 - progress)
        amplitude = (wave / 0.5) * peak
        affected_leg = max(12.0, min(peak + 5, amplitude + random.uniform(-4, 5)))
        healthy_leg = max(12.0, min(peak + 6, amplitude + random.uniform(-3, 4)))
        trunk_angle = max(3.0, min(24.0, random.uniform(4, 14) + (0 if progress < 0.65 else random.uniform(-1, 3))))
        knee_valgus = max(0.0, min(14.0, random.uniform(1, 7)))
        return round(affected_leg, 2), round(healthy_leg, 2), round(trunk_angle, 2), round(knee_valgus, 2)

    def analyze_frame(
        self,
        expected_action: str = DEFAULT_ACTION_NAME,
        frame_index: int = 1,
        cycle_progress: float = 0.0,
        elapsed_seconds: int = 0,
    ) -> Dict:
        action_profile = get_action(expected_action)
        action = action_profile.name
        phase = self._phase_from_progress(cycle_progress)
        left_leg_angle, right_leg_angle, trunk_angle, knee_valgus = self._generate_angles(expected_action, cycle_progress)
        target_rule = ACTION_RULES.get(action_profile.name, ACTION_RULES[DEFAULT_ACTION_NAME])

        symmetry_delta = abs(left_leg_angle - right_leg_angle)
        range_ok = max(left_leg_angle, right_leg_angle) >= target_rule["rom_min"]
        rhythm_ref = 4.0
        rhythm_variance = abs((elapsed_seconds % 8) - rhythm_ref)

        accuracy = max(68.0, 96 - symmetry_delta * 0.9 - knee_valgus * 0.55 + random.uniform(-2, 2))
        stability = max(66.0, 95 - trunk_angle * 0.85 + random.uniform(-2, 2.5))
        range_score = max(66.0, 96 - max(0, target_rule["rom_min"] - max(left_leg_angle, right_leg_angle)) * 1.1)
        rhythm_score = max(68.0, 95 - rhythm_variance * 3 + random.uniform(-1.5, 2))
        symmetry_score = max(66.0, 96 - symmetry_delta * 1.7)
        total_score = round((accuracy + stability + range_score + rhythm_score + symmetry_score) / 5, 2)

        errors: List[Dict] = []
        compensations: List[Dict] = []
        feedbacks: List[str] = []

        if not range_ok:
            errors.append({
                "error_type": action_profile.common_errors[0],
                "error_count": 1,
                "severity": "low" if total_score >= 78 else "medium",
                "suggestion": action_profile.first_cue,
            })
        if knee_valgus > 11:
            errors.append({
                "error_type": "Knee valgus",
                "error_count": 1,
                "severity": "medium",
                "suggestion": "Keep the knee aligned with the second toe.",
            })
        if trunk_angle > 18:
            errors.append({
                "error_type": "Excessive trunk leaning",
                "error_count": 1,
                "severity": "medium",
                "suggestion": "Keep the trunk upright and engage your core.",
            })
        if symmetry_delta > 16:
            errors.append({
                "error_type": "Left-right asymmetry",
                "error_count": 1,
                "severity": "medium",
                "suggestion": "Control both sides evenly and slow down the stronger side.",
            })

        if trunk_angle > 21:
            compensations.append({
                "compensation_type": action_profile.compensation_risks[0],
                "detected_count": 1,
                "risk_level": "medium",
                "suggestion": "Reduce range temporarily and re-stabilize trunk posture.",
            })
        if symmetry_delta > 18:
            compensations.append({
                "compensation_type": "Support-side shift",
                "detected_count": 1,
                "risk_level": "medium",
                "suggestion": "Keep pelvis centered and distribute load more symmetrically.",
            })
        if random.random() < 0.04 and total_score < 86:
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
            feedbacks.append(f"Good control. {action_profile.first_cue}")

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
        action_profile = get_action(expected_action)
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
            summary = f"Overall quality for this {action_profile.name} session was excellent with stable control."
            recommendation = "You can progress with slightly higher difficulty or longer hold time."
            adjustment = {
                "reason": "Strong performance and high completion",
                "detail": "Increase difficulty by one level or increase hold time by 1-2 seconds.",
                "decision": "Increase hold time",
            }
        elif avg_score >= 78 and completion_rate >= 0.75:
            summary = f"The {action_profile.name} session met most targets and matched the standard demo pattern."
            recommendation = f"Keep intensity stable and prioritize: {action_profile.focus_text}."
            adjustment = {
                "reason": "Stable yet improvable quality",
                "detail": "Maintain current set/rep volume and reinforce corrective guidance.",
                "decision": "Keep current plan",
            }
        else:
            summary = f"The {action_profile.name} session quality was below target with recurrent deviations."
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
