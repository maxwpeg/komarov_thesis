"""Exact-ish room coverage solver for smoke detector auto placement."""

from __future__ import annotations

import math
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Iterable

from shapely.geometry import LineString, MultiPolygon, Point, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import orient, polylabel, unary_union


PointM = tuple[float, float]


class CoverageConfig:
    """Configuration for room detector coverage solving."""

    POINT_TOLERANCE_M = 0.05
    COVERAGE_AREA_TOLERANCE_SQM = 1e-4
    MAX_VERIFICATION_ITERATIONS = 6
    DISK_SEGMENTS = 32
    MAX_EXACT_SEARCH_CANDIDATES = 96
    EXACT_SEARCH_TIME_LIMIT_SECONDS = 1.0


@dataclass(frozen=True, slots=True)
class CoverageCandidate:
    point: PointM
    mask: int
    clearance: float


def _safe_scale(scale_factor: float | None) -> float:
    return float(scale_factor) if scale_factor and scale_factor > 0 else 1.0


def _meters_per_pixel(scale_factor: float | None) -> float:
    return _safe_scale(scale_factor) / 1000.0


def _distance(a: PointM, b: PointM) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _point_key(point: PointM, tolerance: float = CoverageConfig.POINT_TOLERANCE_M) -> tuple[int, int]:
    return (
        int(round(point[0] / tolerance)),
        int(round(point[1] / tolerance)),
    )


def _iter_polygons(geometry: BaseGeometry) -> list[Polygon]:
    if geometry.is_empty:
        return []
    if isinstance(geometry, Polygon):
        return [geometry]
    if isinstance(geometry, MultiPolygon):
        return [polygon for polygon in geometry.geoms if not polygon.is_empty]
    polygons = [item for item in getattr(geometry, "geoms", []) if isinstance(item, Polygon) and not item.is_empty]
    return polygons


def _largest_polygon(geometry: BaseGeometry) -> Polygon | None:
    polygons = _iter_polygons(geometry)
    if not polygons:
        return None
    return max(polygons, key=lambda polygon: float(polygon.area))


def _normalize_room_geometry(room: dict[str, Any], scale_factor: float | None) -> BaseGeometry | None:
    points = room.get("boundary_points") or []
    if len(points) < 3:
        return None
    meters_per_pixel = _meters_per_pixel(scale_factor)
    polygon = Polygon(
        [
            (float(point[0]) * meters_per_pixel, float(point[1]) * meters_per_pixel)
            for point in points
        ]
    )
    if polygon.is_empty:
        return None
    if not polygon.is_valid:
        polygon = polygon.buffer(0)
    if polygon.is_empty:
        return None
    if isinstance(polygon, BaseGeometry):
        return polygon
    return None


def _point_within_geometry(point: PointM, geometry: BaseGeometry) -> bool:
    return bool(geometry.covers(Point(point)))


def _clamp_to_geometry(point: PointM, geometry: BaseGeometry) -> PointM | None:
    shapely_point = Point(point)
    if geometry.covers(shapely_point):
        return point
    representative = geometry.representative_point()
    if representative.is_empty:
        return None
    return (float(representative.x), float(representative.y))


def _room_center_point(room: dict[str, Any], geometry: BaseGeometry) -> PointM:
    meters_per_pixel = _meters_per_pixel(room.get("_scale_factor"))
    room_center = (
        float(room.get("center_x") or 0.0) * meters_per_pixel,
        float(room.get("center_y") or 0.0) * meters_per_pixel,
    )
    clamped = _clamp_to_geometry(room_center, geometry)
    if clamped is not None:
        return clamped
    centroid = geometry.centroid
    return (float(centroid.x), float(centroid.y))


def _polylabel_point(geometry: BaseGeometry) -> PointM | None:
    polygon = _largest_polygon(geometry)
    if polygon is None:
        return None
    try:
        point = polylabel(polygon, tolerance=1e-3)
    except Exception:
        point = polygon.representative_point()
    if point.is_empty:
        return None
    return (float(point.x), float(point.y))


def _sample_line(line: LineString, step: float) -> list[PointM]:
    if line.is_empty:
        return []
    length = float(line.length)
    if length <= 1e-9:
        return []
    if step <= 1e-9 or step >= length:
        points = [line.interpolate(0.0), line.interpolate(length)]
        return [(float(point.x), float(point.y)) for point in points]

    count = max(1, int(math.ceil(length / step)))
    samples = [
        line.interpolate((length * index) / count)
        for index in range(count + 1)
    ]
    return [(float(point.x), float(point.y)) for point in samples]


def _sample_boundary(geometry: BaseGeometry, step: float) -> list[PointM]:
    points: list[PointM] = []
    for polygon in _iter_polygons(geometry):
        points.extend(_sample_line(LineString(polygon.exterior.coords), step))
        for interior in polygon.interiors:
            points.extend(_sample_line(LineString(interior.coords), step))
    return points


def _polygon_vertices_and_midpoints(geometry: BaseGeometry) -> list[PointM]:
    points: list[PointM] = []
    for polygon in _iter_polygons(geometry):
        coords = list(polygon.exterior.coords[:-1])
        for index, point in enumerate(coords):
            nxt = coords[(index + 1) % len(coords)]
            points.append((float(point[0]), float(point[1])))
            points.append(
                (
                    (float(point[0]) + float(nxt[0])) / 2.0,
                    (float(point[1]) + float(nxt[1])) / 2.0,
                )
            )
    return points


def _hex_grid_points(geometry: BaseGeometry, step: float) -> list[PointM]:
    if step <= 1e-9 or geometry.is_empty:
        return []
    min_x, min_y, max_x, max_y = geometry.bounds
    row_height = step * math.sqrt(3.0) / 2.0
    points: list[PointM] = []
    row_index = 0
    y = min_y
    while y <= max_y + 1e-9:
        x = min_x + ((step / 2.0) if row_index % 2 else 0.0)
        while x <= max_x + 1e-9:
            point = (float(x), float(y))
            if _point_within_geometry(point, geometry):
                points.append(point)
            x += step
        row_index += 1
        y += row_height
    return points


def _minimum_rotated_rectangle_points(geometry: BaseGeometry) -> list[PointM]:
    polygon = _largest_polygon(geometry)
    if polygon is None:
        return []
    rectangle = polygon.minimum_rotated_rectangle
    coords = list(rectangle.exterior.coords)
    if len(coords) < 5:
        return []
    corners = coords[:-1]
    edges = []
    for index in range(len(corners)):
        start = corners[index]
        end = corners[(index + 1) % len(corners)]
        edges.append((start, end, _distance(start, end)))
    longest = max(edges, key=lambda item: item[2])
    shortest = min(edges, key=lambda item: item[2])
    long_start, long_end, long_length = longest
    short_start, short_end, short_length = shortest
    if long_length <= 1e-9 or short_length <= 1e-9:
        return []

    center = geometry.centroid
    center_point = (float(center.x), float(center.y))
    long_direction = (
        (long_end[0] - long_start[0]) / long_length,
        (long_end[1] - long_start[1]) / long_length,
    )
    short_direction = (
        (short_end[0] - short_start[0]) / short_length,
        (short_end[1] - short_start[1]) / short_length,
    )

    points: list[PointM] = [center_point]
    for long_factor in (-0.25, 0.0, 0.25):
        for short_factor in (-0.25, 0.0, 0.25):
            point = (
                center_point[0] + (long_direction[0] * long_length * long_factor) + (short_direction[0] * short_length * short_factor),
                center_point[1] + (long_direction[1] * long_length * long_factor) + (short_direction[1] * short_length * short_factor),
            )
            if _point_within_geometry(point, geometry):
                points.append(point)
    return points


def _concave_points(geometry: BaseGeometry, radius: float) -> list[PointM]:
    points: list[PointM] = []
    inset = min(radius * 0.25, 0.5)
    for polygon in _iter_polygons(geometry):
        oriented = orient(polygon, sign=1.0)
        coords = list(oriented.exterior.coords[:-1])
        if len(coords) < 3:
            continue
        for index, current in enumerate(coords):
            previous = coords[index - 1]
            nxt = coords[(index + 1) % len(coords)]
            edge_in = (current[0] - previous[0], current[1] - previous[1])
            edge_out = (nxt[0] - current[0], nxt[1] - current[1])
            cross = (edge_in[0] * edge_out[1]) - (edge_in[1] * edge_out[0])
            if cross >= 0.0:
                continue

            in_length = math.hypot(*edge_in)
            out_length = math.hypot(*edge_out)
            if in_length <= 1e-9 or out_length <= 1e-9:
                continue
            in_dir = (edge_in[0] / in_length, edge_in[1] / in_length)
            out_dir = (edge_out[0] / out_length, edge_out[1] / out_length)
            inward = (
                (-in_dir[1] + -out_dir[1]),
                (in_dir[0] + out_dir[0]),
            )
            inward_length = math.hypot(*inward)
            if inward_length <= 1e-9:
                continue
            bisector = (inward[0] / inward_length, inward[1] / inward_length)
            for factor in (1.0, 0.6, 0.35):
                point = (
                    float(current[0] + bisector[0] * inset * factor),
                    float(current[1] + bisector[1] * inset * factor),
                )
                if _point_within_geometry(point, geometry):
                    points.append(point)
                    break
    return points


def _small_room_pair_points(room: dict[str, Any], geometry: BaseGeometry, radius: float) -> list[PointM]:
    center = _room_center_point(room, geometry)
    min_x, min_y, max_x, max_y = geometry.bounds
    width = max_x - min_x
    height = max_y - min_y
    along_x = width >= height
    shift = min(max(width, height) / 4.0, max(radius * 0.6, CoverageConfig.POINT_TOLERANCE_M * 2.0))
    points: list[PointM] = []
    for factor in (1.0, 0.6, 0.35, 0.2):
        delta = shift * factor
        pair = (
            ((center[0] - delta, center[1]), (center[0] + delta, center[1]))
            if along_x
            else ((center[0], center[1] - delta), (center[0], center[1] + delta))
        )
        if all(_point_within_geometry(point, geometry) for point in pair):
            points.extend(pair)
            return points
    if _point_within_geometry(center, geometry):
        points.append(center)
    representative = geometry.representative_point()
    alt = (float(representative.x), float(representative.y))
    if _point_key(alt) != _point_key(center):
        points.append(alt)
    return points


def _dedupe_points(points: Iterable[PointM], tolerance: float = CoverageConfig.POINT_TOLERANCE_M) -> list[PointM]:
    unique: list[PointM] = []
    seen: set[tuple[int, int]] = set()
    for point in points:
        key = _point_key(point, tolerance)
        if key in seen:
            continue
        seen.add(key)
        unique.append((float(point[0]), float(point[1])))
    return unique


def _room_candidate_points(
    room: dict[str, Any],
    geometry: BaseGeometry,
    radius: float,
    coverage_need: int,
) -> list[PointM]:
    points: list[PointM] = []
    points.extend(_hex_grid_points(geometry, max(radius / 1.75, 0.25)))

    inner = geometry.buffer(-min(radius * 0.2, 0.5))
    if inner.is_empty:
        inner = geometry
    points.extend(_sample_boundary(inner, max(radius / 1.5, 0.25)))

    center = _room_center_point(room, geometry)
    points.append(center)
    polylabel_point = _polylabel_point(geometry)
    if polylabel_point is not None:
        points.append(polylabel_point)
    points.extend(_minimum_rotated_rectangle_points(geometry))
    points.extend(_concave_points(geometry, radius))
    points.extend(_polygon_vertices_and_midpoints(geometry))

    if coverage_need > 1:
        points.extend(_small_room_pair_points(room, geometry, radius))

    filtered = [point for point in points if _point_within_geometry(point, geometry)]
    return _dedupe_points(filtered)


def _room_witness_points(room: dict[str, Any], geometry: BaseGeometry, radius: float) -> list[PointM]:
    points: list[PointM] = []
    step = max(radius / 4.0, 0.2)
    points.extend(_sample_boundary(geometry, step))
    points.extend(_hex_grid_points(geometry, max(radius / 3.0, 0.2)))

    center = _room_center_point(room, geometry)
    points.append(center)
    polylabel_point = _polylabel_point(geometry)
    if polylabel_point is not None:
        points.append(polylabel_point)
    points.extend(_minimum_rotated_rectangle_points(geometry))
    points.extend(_concave_points(geometry, radius))

    for polygon in _iter_polygons(geometry):
        coords = list(polygon.exterior.coords[:-1])
        for index, point in enumerate(coords):
            points.append((float(point[0]), float(point[1])))
            nxt = coords[(index + 1) % len(coords)]
            points.append(((float(point[0]) + float(nxt[0])) / 2.0, (float(point[1]) + float(nxt[1])) / 2.0))

    filtered = [point for point in points if _point_within_geometry(point, geometry)]
    return _dedupe_points(filtered)


def _coverage_mask(point: PointM, witnesses: list[PointM], radius: float) -> int:
    mask = 0
    for index, witness in enumerate(witnesses):
        if _distance(point, witness) <= radius + 1e-6:
            mask |= 1 << index
    return mask


def _compress_candidates(
    points: list[PointM],
    witnesses: list[PointM],
    radius: float,
    geometry: BaseGeometry,
    coverage_need: int,
) -> list[CoverageCandidate]:
    grouped: dict[int, list[tuple[float, PointM]]] = defaultdict(list)
    for point in points:
        mask = _coverage_mask(point, witnesses, radius)
        if mask == 0:
            continue
        clearance = float(geometry.boundary.distance(Point(point)))
        grouped[mask].append((clearance, point))

    candidates: list[CoverageCandidate] = []
    for mask, variants in grouped.items():
        variants.sort(key=lambda item: (-item[0], item[1][0], item[1][1]))
        unique_variants: list[tuple[float, PointM]] = []
        seen_keys: set[tuple[int, int]] = set()
        for clearance, point in variants:
            key = _point_key(point)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            unique_variants.append((clearance, point))

        if coverage_need <= 1 or len(unique_variants) <= coverage_need:
            selected_points = unique_variants[:coverage_need]
        else:
            first = unique_variants[0]
            farthest = max(
                unique_variants[1:],
                key=lambda item: (
                    _distance(first[1], item[1]),
                    item[0],
                    -item[1][0],
                    -item[1][1],
                ),
            )
            selected_points = [first, farthest]
        for clearance, point in selected_points:
            candidates.append(CoverageCandidate(point=point, mask=mask, clearance=clearance))

    if coverage_need == 1:
        pruned: list[CoverageCandidate] = []
        for candidate in sorted(candidates, key=lambda item: (-item.mask.bit_count(), -item.clearance, item.point[0], item.point[1])):
            if any((candidate.mask | existing.mask) == existing.mask for existing in pruned):
                continue
            pruned.append(candidate)
        candidates = pruned

    return sorted(candidates, key=lambda item: (-item.mask.bit_count(), -item.clearance, item.point[0], item.point[1]))


def _lower_bound(area: float, span_major: float, radius: float, coverage_need: int) -> int:
    if radius <= 1e-9:
        return 0
    area_bound = math.ceil((coverage_need * area) / (math.pi * radius * radius))
    span_bound = math.ceil(span_major / (2.0 * radius))
    return max(1, area_bound, span_bound)


def _incompatibility_lower_bound(witnesses: list[PointM], radius: float, coverage_need: int) -> int:
    if not witnesses:
        return 0

    threshold = (2.0 * radius) + 1e-6
    neighbor_sets: list[set[int]] = []
    for index, witness in enumerate(witnesses):
        neighbors: set[int] = set()
        for other_index, other_witness in enumerate(witnesses):
            if index == other_index:
                continue
            if _distance(witness, other_witness) > threshold:
                neighbors.add(other_index)
        neighbor_sets.append(neighbors)

    order = sorted(range(len(witnesses)), key=lambda index: len(neighbor_sets[index]), reverse=True)
    best_size = 1
    for start_index in order:
        clique_size = 1
        common = set(neighbor_sets[start_index])
        while common:
            next_index = max(common, key=lambda candidate_index: len(common & neighbor_sets[candidate_index]))
            clique_size += 1
            common &= neighbor_sets[next_index]
        best_size = max(best_size, clique_size)
    return best_size * max(1, coverage_need)


def _room_span_major(geometry: BaseGeometry) -> float:
    polygon = _largest_polygon(geometry)
    if polygon is None:
        return 0.0
    rectangle = polygon.minimum_rotated_rectangle
    coords = list(rectangle.exterior.coords)
    if len(coords) < 5:
        min_x, min_y, max_x, max_y = geometry.bounds
        return max(max_x - min_x, max_y - min_y)
    edges = [
        _distance(coords[index], coords[index + 1])
        for index in range(4)
    ]
    return max(edges)


def _greedy_upper_bound(candidates: list[CoverageCandidate], witness_count: int, coverage_need: int) -> list[int]:
    remaining = [coverage_need for _ in range(witness_count)]
    selected: list[int] = []
    used: set[int] = set()
    while any(need > 0 for need in remaining):
        best_index = None
        best_score = (0, 0.0, 0)
        for index, candidate in enumerate(candidates):
            if index in used:
                continue
            gain = 0
            covered_count = 0
            for witness_index in range(witness_count):
                if ((candidate.mask >> witness_index) & 1) == 0:
                    continue
                covered_count += 1
                gain += max(0, remaining[witness_index])
            score = (gain, candidate.clearance, covered_count)
            if score > best_score:
                best_index = index
                best_score = score
        if best_index is None or best_score[0] <= 0:
            return []
        used.add(best_index)
        selected.append(best_index)
        mask = candidates[best_index].mask
        for witness_index in range(witness_count):
            if ((mask >> witness_index) & 1) and remaining[witness_index] > 0:
                remaining[witness_index] -= 1
    return selected


def _solve_k_cover(
    candidates: list[CoverageCandidate],
    witness_count: int,
    coverage_need: int,
    initial_lower_bound: int,
) -> list[int]:
    if witness_count == 0:
        return []

    witness_to_candidates: list[list[int]] = [[] for _ in range(witness_count)]
    for candidate_index, candidate in enumerate(candidates):
        for witness_index in range(witness_count):
            if (candidate.mask >> witness_index) & 1:
                witness_to_candidates[witness_index].append(candidate_index)

    if any(len(indices) < coverage_need for indices in witness_to_candidates):
        return []

    greedy = _greedy_upper_bound(candidates, witness_count, coverage_need)
    if not greedy:
        return []

    upper_bound = len(greedy)
    if len(candidates) > CoverageConfig.MAX_EXACT_SEARCH_CANDIDATES:
        return greedy

    full_witness_mask = (1 << witness_count) - 1
    deadline = time.perf_counter() + CoverageConfig.EXACT_SEARCH_TIME_LIMIT_SECONDS

    def dynamic_lower_bound(need_once_mask: int, need_twice_mask: int, used_mask: int) -> int:
        total_need = need_once_mask.bit_count() + need_twice_mask.bit_count()
        if total_need <= 0:
            return 0
        max_gain = 0
        for index in range(len(candidates)):
            if (used_mask >> index) & 1:
                continue
            gain = (candidates[index].mask & need_once_mask).bit_count()
            max_gain = max(max_gain, gain)
        if max_gain <= 0:
            return math.inf
        hardest_witness = 2 if need_twice_mask else (1 if need_once_mask else 0)
        return max(math.ceil(total_need / max_gain), hardest_witness)

    def pick_witness(need_once_mask: int, need_twice_mask: int, used_mask: int) -> int | None:
        best_witness = None
        best_score = None
        pending = need_once_mask
        while pending:
            lowest_bit = pending & -pending
            witness_index = lowest_bit.bit_length() - 1
            pending ^= lowest_bit
            options = [
                candidate_index
                for candidate_index in witness_to_candidates[witness_index]
                if ((used_mask >> candidate_index) & 1) == 0
            ]
            if not options:
                return None
            score = (
                len(options),
                0 if ((need_twice_mask >> witness_index) & 1) else 1,
            )
            if best_score is None or score < best_score:
                best_score = score
                best_witness = witness_index
        return best_witness

    def apply_candidate(need_once_mask: int, need_twice_mask: int, candidate_mask: int) -> tuple[int, int]:
        if coverage_need <= 1:
            return need_once_mask & ~candidate_mask, 0

        fully_satisfied = (need_once_mask & ~need_twice_mask) & candidate_mask
        updated_need_once = need_once_mask & ~fully_satisfied
        updated_need_twice = need_twice_mask & ~candidate_mask
        return updated_need_once, updated_need_twice

    def search(
        target_size: int,
        used_mask: int,
        chosen: list[int],
        need_once_mask: int,
        need_twice_mask: int,
        visited: set[tuple[int, int, int]],
        best_seen: dict[tuple[int, int], int],
    ) -> list[int] | None:
        if time.perf_counter() >= deadline:
            return None
        if need_once_mask == 0:
            return chosen[:]
        if len(chosen) >= target_size:
            return None

        state = (used_mask, need_once_mask, need_twice_mask)
        if state in visited:
            return None
        visited.add(state)

        compact_state = (need_once_mask, need_twice_mask)
        best_length = best_seen.get(compact_state)
        if best_length is not None and len(chosen) > best_length:
            return None
        best_seen[compact_state] = min(best_length, len(chosen)) if best_length is not None else len(chosen)

        additional_lower_bound = dynamic_lower_bound(need_once_mask, need_twice_mask, used_mask)
        if len(chosen) + additional_lower_bound > target_size:
            return None

        witness_index = pick_witness(need_once_mask, need_twice_mask, used_mask)
        if witness_index is None:
            return None

        options = [
            candidate_index
            for candidate_index in witness_to_candidates[witness_index]
            if ((used_mask >> candidate_index) & 1) == 0
        ]
        options.sort(
            key=lambda candidate_index: (
                -((candidates[candidate_index].mask & need_once_mask).bit_count()),
                -((candidates[candidate_index].mask & need_twice_mask).bit_count()),
                -candidates[candidate_index].clearance,
                candidate_index,
            )
        )

        for candidate_index in options:
            mask = candidates[candidate_index].mask
            updated_need_once, updated_need_twice = apply_candidate(need_once_mask, need_twice_mask, mask)
            chosen.append(candidate_index)
            result = search(
                target_size,
                used_mask | (1 << candidate_index),
                chosen,
                updated_need_once,
                updated_need_twice,
                visited,
                best_seen,
            )
            chosen.pop()
            if result is not None:
                return result
        return None

    for target_size in range(max(1, initial_lower_bound), upper_bound + 1):
        if time.perf_counter() >= deadline:
            return greedy
        result = search(
            target_size,
            0,
            [],
            full_witness_mask,
            full_witness_mask if coverage_need > 1 else 0,
            set(),
            {},
        )
        if result is not None:
            return result
        if time.perf_counter() >= deadline:
            return greedy
    return greedy


def _disk_geometry(point: PointM, radius: float, room_geometry: BaseGeometry) -> BaseGeometry:
    return Point(point).buffer(radius, quad_segs=CoverageConfig.DISK_SEGMENTS).intersection(room_geometry)


def _polygonal_components(geometry: BaseGeometry) -> list[Polygon]:
    if geometry.is_empty:
        return []
    if isinstance(geometry, Polygon):
        return [geometry]
    if isinstance(geometry, MultiPolygon):
        return [polygon for polygon in geometry.geoms if polygon.area > CoverageConfig.COVERAGE_AREA_TOLERANCE_SQM]
    polygons: list[Polygon] = []
    for item in getattr(geometry, "geoms", []):
        polygons.extend(_polygonal_components(item))
    return polygons


def _uncovered_regions(
    room_geometry: BaseGeometry,
    detector_points: list[PointM],
    radius: float,
    coverage_need: int,
) -> list[Polygon]:
    if not detector_points:
        return _polygonal_components(room_geometry)

    disks = [_disk_geometry(point, radius, room_geometry) for point in detector_points]
    if coverage_need <= 1:
        covered = unary_union(disks)
    else:
        covered_once: BaseGeometry = Polygon()
        covered_twice: BaseGeometry = Polygon()
        for disk in disks:
            if covered_once.is_empty:
                covered_once = disk
                continue
            overlap = covered_once.intersection(disk)
            if covered_twice.is_empty:
                covered_twice = overlap
            else:
                covered_twice = unary_union([covered_twice, overlap])
            covered_once = unary_union([covered_once, disk])
        covered = covered_twice

    uncovered = room_geometry.difference(covered)
    return [
        polygon
        for polygon in _polygonal_components(uncovered)
        if polygon.area > CoverageConfig.COVERAGE_AREA_TOLERANCE_SQM
    ]


def _expand_points_for_regions(
    room_geometry: BaseGeometry,
    regions: list[Polygon],
    radius: float,
    coverage_need: int,
) -> tuple[list[PointM], list[PointM]]:
    candidate_points: list[PointM] = []
    witness_points: list[PointM] = []
    local_step = max(radius / 4.0, 0.15)
    for region in regions:
        expanded = room_geometry.intersection(region.buffer(radius / 2.0))
        if expanded.is_empty:
            expanded = region
        witness_points.append((float(region.centroid.x), float(region.centroid.y)))
        try:
            label = polylabel(region, tolerance=1e-3)
            witness_points.append((float(label.x), float(label.y)))
        except Exception:
            pass

        candidate_points.extend(_hex_grid_points(expanded, local_step))
        candidate_points.extend(_sample_boundary(expanded, local_step))
        candidate_points.append((float(region.centroid.x), float(region.centroid.y)))
        try:
            label = polylabel(region, tolerance=1e-3)
            candidate_points.append((float(label.x), float(label.y)))
        except Exception:
            pass
    if coverage_need > 1:
        candidate_points = _dedupe_points(candidate_points)
    return _dedupe_points(candidate_points), _dedupe_points(witness_points)


def _coverage_score(
    detector_points: list[PointM],
    witnesses: list[PointM],
    room_geometry: BaseGeometry,
    radius: float,
    coverage_need: int,
) -> tuple[float, float]:
    min_margin = float("inf")
    for witness in witnesses:
        margins = sorted((radius - _distance(point, witness) for point in detector_points), reverse=True)
        if len(margins) < coverage_need:
            return (float("-inf"), float("-inf"))
        min_margin = min(min_margin, margins[coverage_need - 1])
    boundary_clearance = min(
        float(room_geometry.boundary.distance(Point(point)))
        for point in detector_points
    ) if detector_points else 0.0
    return (min_margin, boundary_clearance)


def _refine_detector_points(
    room_geometry: BaseGeometry,
    detector_points: list[PointM],
    witnesses: list[PointM],
    radius: float,
    coverage_need: int,
) -> list[PointM]:
    if not detector_points:
        return detector_points
    refined = detector_points[:]
    directions = [
        (-1.0, 0.0),
        (1.0, 0.0),
        (0.0, -1.0),
        (0.0, 1.0),
        (-1.0, -1.0),
        (-1.0, 1.0),
        (1.0, -1.0),
        (1.0, 1.0),
    ]
    step = max(radius / 4.0, CoverageConfig.POINT_TOLERANCE_M)
    min_step = max(radius / 32.0, CoverageConfig.POINT_TOLERANCE_M / 2.0)
    current_score = _coverage_score(refined, witnesses, room_geometry, radius, coverage_need)

    while step >= min_step:
        improved = False
        for index, point in enumerate(refined):
            best_point = point
            best_score = current_score
            for dx, dy in directions:
                candidate = (
                    point[0] + dx * step,
                    point[1] + dy * step,
                )
                if not _point_within_geometry(candidate, room_geometry):
                    continue
                if any(
                    other_index != index and _distance(candidate, other_point) < CoverageConfig.POINT_TOLERANCE_M
                    for other_index, other_point in enumerate(refined)
                ):
                    continue
                trial = refined[:]
                trial[index] = candidate
                if _uncovered_regions(room_geometry, trial, radius, coverage_need):
                    continue
                score = _coverage_score(trial, witnesses, room_geometry, radius, coverage_need)
                if score > best_score:
                    best_point = candidate
                    best_score = score
            if best_point != point:
                refined[index] = best_point
                current_score = best_score
                improved = True
        if not improved:
            step /= 2.0
    return refined


def solve_room_detector_positions(
    room: dict[str, Any],
    *,
    smoke_detector_radius_mm: float,
    scale_factor: float | None,
    coverage_need: int,
) -> tuple[list[PointM], list[str]]:
    """Return detector positions in pixel coordinates for a room."""

    if room.get("room_type") == "необслуживаемое":
        return [], []

    if room.get("room_type") == "РЅРµРѕР±СЃР»СѓР¶РёРІР°РµРјРѕРµ":
        return [], []

    warnings: list[str] = []
    normalized_room = {**room, "_scale_factor": scale_factor}
    room_geometry = _normalize_room_geometry(normalized_room, scale_factor)
    if room_geometry is None or room_geometry.is_empty:
        return [], [f"Помещение {room.get('id') or room.get('name') or 'без имени'} пропущено: некорректный контур."]

    radius_m = float(smoke_detector_radius_mm) / 1000.0
    span_major = _room_span_major(room_geometry)
    lower_bound = _lower_bound(float(room_geometry.area), span_major, radius_m, coverage_need)
    lower_bound = max(lower_bound, _incompatibility_lower_bound(_polygon_vertices_and_midpoints(room_geometry), radius_m, coverage_need))

    candidate_points = _room_candidate_points(normalized_room, room_geometry, radius_m, coverage_need)
    witness_points = _room_witness_points(normalized_room, room_geometry, radius_m)
    if coverage_need > 1:
        candidate_points.extend(_small_room_pair_points(normalized_room, room_geometry, radius_m))
    candidate_points = _dedupe_points(point for point in candidate_points if _point_within_geometry(point, room_geometry))

    solution_points_m: list[PointM] = []
    for _iteration in range(CoverageConfig.MAX_VERIFICATION_ITERATIONS):
        compressed_candidates = _compress_candidates(
            candidate_points,
            witness_points,
            radius_m,
            room_geometry,
            coverage_need,
        )
        selected_indices = _solve_k_cover(
            compressed_candidates,
            len(witness_points),
            coverage_need,
            lower_bound,
        )
        if not selected_indices:
            warnings.append(
                f"Не удалось построить полное покрытие для помещения {room.get('id') or room.get('name') or 'без имени'}."
            )
            return [], warnings

        solution_points_m = [compressed_candidates[index].point for index in selected_indices]
        uncovered = _uncovered_regions(room_geometry, solution_points_m, radius_m, coverage_need)
        if not uncovered:
            break
        extra_candidates, extra_witnesses = _expand_points_for_regions(room_geometry, uncovered, radius_m, coverage_need)
        if not extra_candidates and not extra_witnesses:
            break
        candidate_points.extend(extra_candidates)
        witness_points.extend(extra_witnesses)
        candidate_points = _dedupe_points(point for point in candidate_points if _point_within_geometry(point, room_geometry))
        witness_points = _dedupe_points(point for point in witness_points if _point_within_geometry(point, room_geometry))

    if not solution_points_m:
        return [], warnings

    uncovered = _uncovered_regions(room_geometry, solution_points_m, radius_m, coverage_need)
    if uncovered:
        warnings.append(
            f"Не удалось гарантировать полное покрытие помещения {room.get('id') or room.get('name') or 'без имени'}."
        )
        return [], warnings

    refined_points_m = _refine_detector_points(
        room_geometry,
        solution_points_m,
        witness_points,
        radius_m,
        coverage_need,
    )
    if _uncovered_regions(room_geometry, refined_points_m, radius_m, coverage_need):
        refined_points_m = solution_points_m

    meters_per_pixel = _meters_per_pixel(scale_factor)
    detector_points_px = [
        (point[0] / meters_per_pixel, point[1] / meters_per_pixel)
        for point in refined_points_m
    ]
    detector_points_px = _dedupe_points(detector_points_px, tolerance=max(CoverageConfig.POINT_TOLERANCE_M / max(meters_per_pixel, 1e-9), 0.01))
    if coverage_need > 1 and len(detector_points_px) < 2:
        warnings.append(
            f"Для помещения {room.get('id') or room.get('name') or 'без имени'} не удалось получить две разные позиции датчиков."
        )
        return [], warnings
    return detector_points_px, warnings
