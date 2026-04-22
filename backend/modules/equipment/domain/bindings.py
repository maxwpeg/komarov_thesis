"""Helpers for binding floor-plan elements to project-linked equipment."""

from __future__ import annotations

from typing import Any, Callable, Iterable

from backend.errors import AppError


def list_project_equipment_items(floor_plan, allowed_categories: Iterable[str] | None = None) -> list[Any]:
    allowed = {str(category) for category in (allowed_categories or [])}
    project = getattr(floor_plan, "project", None)
    links = getattr(project, "equipment_links", None) or []
    items: list[Any] = []
    seen_ids: set[int] = set()
    for link in links:
        equipment = getattr(link, "equipment", None)
        equipment_id = getattr(equipment, "id", None)
        if equipment is None or equipment_id is None:
            continue
        safe_id = int(equipment_id)
        if safe_id in seen_ids:
            continue
        if allowed and str(getattr(equipment, "category", "")) not in allowed:
            continue
        seen_ids.add(safe_id)
        items.append(equipment)
    items.sort(key=lambda item: (str(getattr(item, "name", "") or "").lower(), int(getattr(item, "id", 0) or 0)))
    return items


def resolve_project_equipment_id(
    floor_plan,
    allowed_categories: Iterable[str] | None,
    equipment_id: int | None,
    *,
    entity_label: str,
    require_on_ambiguous: bool = True,
) -> int | None:
    project_items = list_project_equipment_items(floor_plan)
    project_items_by_id = {
        int(getattr(item, "id")): item
        for item in project_items
        if getattr(item, "id", None) is not None
    }
    compatible_items = list_project_equipment_items(floor_plan, allowed_categories)
    compatible_ids = {
        int(getattr(item, "id"))
        for item in compatible_items
        if getattr(item, "id", None) is not None
    }

    if equipment_id is not None:
        safe_id = int(equipment_id)
        selected_item = project_items_by_id.get(safe_id)
        if selected_item is None:
            raise AppError(
                409,
                "equipment_not_linked_to_project",
                "Equipment must be added to the project before it can be used on the plan",
            )
        if compatible_ids and safe_id not in compatible_ids:
            raise AppError(
                409,
                "equipment_category_mismatch",
                f"Selected equipment is incompatible with {entity_label}",
            )
        return safe_id

    if len(compatible_items) == 1:
        return int(getattr(compatible_items[0], "id"))
    if len(compatible_items) > 1 and require_on_ambiguous:
        raise AppError(
            409,
            "equipment_assignment_required",
            f"Select concrete equipment for {entity_label}",
        )
    return None


def ensure_model_equipment_assignments(
    floor_plan,
    models: Iterable[Any],
    *,
    allowed_categories_getter: Callable[[Any], Iterable[str] | None],
    entity_label_getter: Callable[[Any], str],
) -> bool:
    changed = False
    for model in models:
        resolved_id = resolve_project_equipment_id(
            floor_plan,
            allowed_categories_getter(model),
            getattr(model, "equipment_id", None),
            entity_label=entity_label_getter(model),
            require_on_ambiguous=True,
        )
        if resolved_id != getattr(model, "equipment_id", None):
            setattr(model, "equipment_id", resolved_id)
            changed = True
    return changed
