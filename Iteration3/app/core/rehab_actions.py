"""Canonical rehab action catalog for demo videos, plans, prompts, and scoring."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List, Tuple

from app.core.runtime_config import BASE_DIR


VIDEOS_DIR = os.path.join(BASE_DIR, "videos")
ACTION_IMAGE_DIR = os.path.join(BASE_DIR, "assets", "rehab_actions")
DEFAULT_ACTION_NAME = "Hip and Knee Flexion"


@dataclass(frozen=True)
class RehabAction:
    name: str
    cn_name: str
    video_filename: str
    image_filename: str
    plan_name: str
    difficulty_level: str
    sets_count: int
    reps_count: int
    duration_minutes: int
    rest_seconds: int
    description: str
    target_peak: int
    rom_min: int
    scoring_focus: Tuple[str, ...]
    key_cues: Tuple[str, ...]
    common_errors: Tuple[str, ...]
    compensation_risks: Tuple[str, ...]

    @property
    def video_path(self) -> str:
        return os.path.join(VIDEOS_DIR, self.video_filename)

    @property
    def image_path(self) -> str:
        return os.path.join(ACTION_IMAGE_DIR, self.image_filename)

    @property
    def display_name(self) -> str:
        return f"{self.cn_name} / {self.name}"

    @property
    def first_cue(self) -> str:
        return self.key_cues[0] if self.key_cues else "Move slowly and keep a pain-free range."

    @property
    def focus_text(self) -> str:
        return " | ".join(self.scoring_focus)


DEMO_ACTIONS: Tuple[RehabAction, ...] = (
    RehabAction(
        name="Knee Extension with Toe Lift",
        cn_name="伸膝绷脚尖",
        video_filename="伸膝绷脚尖 Straighten the knee and lift the to.mp4",
        image_filename="knee_extension_toe_lift.jpg",
        plan_name="Knee Extension Activation",
        difficulty_level="Low",
        sets_count=3,
        reps_count=10,
        duration_minutes=15,
        rest_seconds=30,
        description=(
            "Use the standard demo video to practice controlled knee extension with the toes lifted. "
            "The focus is terminal knee control, ankle dorsiflexion, and smooth return."
        ),
        target_peak=70,
        rom_min=46,
        scoring_focus=("terminal knee extension", "toe lift control", "slow return"),
        key_cues=(
            "Straighten the knee, lift the toes, and avoid locking the joint hard.",
            "Hold briefly at the top, then return with the same speed.",
            "Keep the pelvis quiet and do not swing the leg.",
        ),
        common_errors=(
            "Incomplete knee extension",
            "Toe lift not maintained",
            "Swing momentum",
        ),
        compensation_risks=(
            "Pelvis hiking compensation",
            "Backward trunk leaning",
        ),
    ),
    RehabAction(
        name="Lateral Leg Lift",
        cn_name="外侧抬腿",
        video_filename="外侧抬腿 Lateral leg lift.mp4",
        image_filename="lateral_leg_lift.jpg",
        plan_name="Hip Abductor Control",
        difficulty_level="Low",
        sets_count=3,
        reps_count=12,
        duration_minutes=16,
        rest_seconds=35,
        description=(
            "Use the standard demo video to train lateral hip abduction. "
            "The focus is hip-side control, pelvis stability, and avoiding trunk side-lean."
        ),
        target_peak=64,
        rom_min=40,
        scoring_focus=("hip abduction range", "pelvis stability", "no side-lean"),
        key_cues=(
            "Lift the leg to the side without turning the toes outward.",
            "Keep the pelvis level and avoid leaning the trunk.",
            "Move up and down at a steady pace.",
        ),
        common_errors=(
            "Insufficient lateral lift height",
            "Toe external rotation",
            "Fast dropping phase",
        ),
        compensation_risks=(
            "Body side-lean compensation",
            "Pelvis rotation compensation",
        ),
    ),
    RehabAction(
        name="Hip and Knee Flexion",
        cn_name="屈髋屈膝",
        video_filename="屈髋屈膝 Bend the hip and the knee.mp4",
        image_filename="hip_knee_flexion.jpg",
        plan_name="Hip-Knee Flexion Control",
        difficulty_level="Medium",
        sets_count=3,
        reps_count=10,
        duration_minutes=18,
        rest_seconds=35,
        description=(
            "Use the standard demo video to practice coordinated hip and knee flexion. "
            "The focus is synchronized hip-knee movement, stable trunk, and controlled return."
        ),
        target_peak=82,
        rom_min=54,
        scoring_focus=("hip-knee coordination", "movement range", "trunk control"),
        key_cues=(
            "Bend the hip and knee together, then return smoothly.",
            "Keep the trunk stable and avoid pulling with momentum.",
            "Stay within a comfortable, pain-free range.",
        ),
        common_errors=(
            "Insufficient hip-knee flexion",
            "Asynchronous hip and knee movement",
            "Fast return without control",
        ),
        compensation_risks=(
            "Forward trunk compensation",
            "Support-side shift",
        ),
    ),
    RehabAction(
        name="Standing Hamstring Curl",
        cn_name="站立位后勾腿",
        video_filename="站立位后勾腿 Standing position with crossed legs.mp4",
        image_filename="standing_hamstring_curl.jpg",
        plan_name="Standing Hamstring Curl",
        difficulty_level="Medium",
        sets_count=3,
        reps_count=12,
        duration_minutes=18,
        rest_seconds=40,
        description=(
            "Use the standard demo video to practice standing knee flexion behind the body. "
            "The focus is hamstring control, standing balance, and avoiding pelvis movement."
        ),
        target_peak=76,
        rom_min=50,
        scoring_focus=("knee flexion range", "standing balance", "pelvis stability"),
        key_cues=(
            "Bend the knee backward slowly while the thigh stays steady.",
            "Keep the supporting side stable and do not arch the lower back.",
            "Pause briefly, then lower the foot with control.",
        ),
        common_errors=(
            "Insufficient backward knee bend",
            "Thigh swings forward",
            "Foot drops too quickly",
        ),
        compensation_risks=(
            "Lumbar extension compensation",
            "Support-side shift",
        ),
    ),
)


def _normalize_action_name(name: str) -> str:
    return " ".join(str(name or "").strip().lower().replace("_", " ").split())


ACTION_LOOKUP: Dict[str, RehabAction] = {}
for action in DEMO_ACTIONS:
    ACTION_LOOKUP[_normalize_action_name(action.name)] = action
    ACTION_LOOKUP[_normalize_action_name(action.cn_name)] = action
    ACTION_LOOKUP[_normalize_action_name(action.display_name)] = action
    ACTION_LOOKUP[_normalize_action_name(action.plan_name)] = action


def get_action(action_name: str | None = None) -> RehabAction:
    key = _normalize_action_name(action_name or DEFAULT_ACTION_NAME)
    return ACTION_LOOKUP.get(key, ACTION_LOOKUP[_normalize_action_name(DEFAULT_ACTION_NAME)])


def get_action_names() -> List[str]:
    return [action.name for action in DEMO_ACTIONS]


def get_action_rules() -> Dict[str, Dict[str, int]]:
    return {
        action.name: {"target_peak": action.target_peak, "rom_min": action.rom_min}
        for action in DEMO_ACTIONS
    }


def get_action_video_path(action_name: str | None = None) -> str:
    action = get_action(action_name)
    return action.video_path if os.path.exists(action.video_path) else ""


def get_action_image_path(action_name: str | None = None) -> str:
    action = get_action(action_name)
    return action.image_path if os.path.exists(action.image_path) else ""


def build_default_plan_payload(action: RehabAction, is_active: int = 0) -> Dict[str, object]:
    return {
        "plan_name": action.plan_name,
        "target_action": action.name,
        "difficulty_level": action.difficulty_level,
        "sets_count": action.sets_count,
        "reps_count": action.reps_count,
        "duration_minutes": action.duration_minutes,
        "rest_seconds": action.rest_seconds,
        "description": action.description,
        "is_active": is_active,
    }


def build_qwen_action_prompt(expected_action: str) -> str:
    action = get_action(expected_action)
    allowed = ", ".join(get_action_names())
    cues = "; ".join(action.key_cues)
    errors = "; ".join(action.common_errors)
    compensations = "; ".join(action.compensation_risks)
    focus = "; ".join(action.scoring_focus)
    return (
        f"Expected action: {action.name} ({action.cn_name}). "
        f"Allowed action labels: {allowed}. "
        f"Scoring focus: {focus}. Key cues: {cues}. "
        f"Common errors to check only when visible: {errors}. "
        f"Compensation risks to check only when visible: {compensations}. "
        "The input is a standard demo-oriented rehab video. If the visible movement is broadly consistent "
        "with the expected action, keep the assessment moderate-positive, avoid inventing severe findings, "
        "use low or medium risk unless an unsafe compensation is obvious, and keep total_score in the 78-95 "
        "range. Use scores below 70 only when the action is clearly wrong, unsafe, or not visible."
    )
