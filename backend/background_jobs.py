"""Shared background job type constants and helpers."""

from __future__ import annotations


TASK_RECOGNITION_PROCESS = "recognition_process"
TASK_PIPELINE_DETECT_WALLS = "pipeline_detect_walls"
TASK_PIPELINE_DETECT_OPENINGS = "pipeline_detect_openings"
TASK_PIPELINE_DETECT_ROOMS = "pipeline_detect_rooms"
TASK_PIPELINE_DETECT_ZKSPC = "pipeline_detect_zkspc"
TASK_FIRE_ALARM_AUTO_LAYOUT = "fire_alarm_auto_layout"
TASK_SOUE_AUTO_LAYOUT = "soue_auto_layout"
TASK_RECOGNITION_TRAINING_RUN = "recognition_training_run"
TASK_PROJECT_PDF_GENERATE = "project_pdf_generate"


def dedupe_key_for_task(task_type: str, *, floor_plan_id: int | None = None, project_id: int | None = None, step: str | None = None) -> str | None:
    if task_type == TASK_PROJECT_PDF_GENERATE and project_id is not None:
        return f"{task_type}:project:{project_id}"
    if task_type == TASK_RECOGNITION_TRAINING_RUN and step:
        return f"{task_type}:step:{step}"
    if floor_plan_id is not None:
        return f"{task_type}:floor-plan:{floor_plan_id}"
    if project_id is not None:
        return f"{task_type}:project:{project_id}"
    return None
