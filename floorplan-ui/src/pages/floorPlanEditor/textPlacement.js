import { getBoundingBox, pointInPolygon, rectsIntersect } from './helpers';

const DEFAULT_FONT_FAMILY = 'GOST A';
const DEFAULT_PADDING_X = 3;
const DEFAULT_HEIGHT_FACTOR = 1.2;
const DEFAULT_BOUNDS_PADDING = 24;
const DEFAULT_LEADER_PADDING = 3;
const DEFAULT_OVERFLOW_OFFSETS = 8;
const DEFAULT_OVERFLOW_STEPS = 12;
const DEFAULT_CANDIDATE_RINGS = 6;

let cachedMeasureContext = null;

function getMeasureContext() {
  if (cachedMeasureContext) {
    return cachedMeasureContext;
  }
  if (typeof navigator !== 'undefined' && /jsdom/i.test(String(navigator.userAgent || ''))) {
    return null;
  }
  if (typeof OffscreenCanvas !== 'undefined') {
    try {
      const canvas = new OffscreenCanvas(1, 1);
      cachedMeasureContext = canvas.getContext('2d') || null;
      if (cachedMeasureContext) {
        return cachedMeasureContext;
      }
    } catch (error) {
      cachedMeasureContext = null;
    }
  }
  if (typeof document !== 'undefined' && typeof document.createElement === 'function') {
    try {
      const canvas = document.createElement('canvas');
      cachedMeasureContext = canvas.getContext('2d') || null;
      if (cachedMeasureContext) {
        return cachedMeasureContext;
      }
    } catch (error) {
      cachedMeasureContext = null;
    }
  }
  return null;
}

function normalizePoint(point) {
  if (!point) {
    return null;
  }
  return {
    x: Number(point.x ?? point[0] ?? 0),
    y: Number(point.y ?? point[1] ?? 0),
  };
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function rectContainsPoint(rect, point) {
  if (!rect || !point) {
    return false;
  }
  return point.x >= rect.x
    && point.x <= rect.x + rect.width
    && point.y >= rect.y
    && point.y <= rect.y + rect.height;
}

function normalizeVector(vector) {
  const point = normalizePoint(vector);
  if (!point) {
    return null;
  }
  const length = Math.hypot(point.x, point.y);
  if (length <= 1e-6) {
    return null;
  }
  return {
    x: point.x / length,
    y: point.y / length,
  };
}

function rectCenter(rect) {
  return {
    x: rect.x + (rect.width / 2),
    y: rect.y + (rect.height / 2),
  };
}

export function inflateRect(rect, padding = 0) {
  if (!rect) {
    return null;
  }
  return {
    x: rect.x - padding,
    y: rect.y - padding,
    width: rect.width + (padding * 2),
    height: rect.height + (padding * 2),
  };
}

export function isRectInsideBounds(rect, bounds) {
  if (!rect || !bounds) {
    return true;
  }
  return rect.x >= bounds.x
    && rect.y >= bounds.y
    && rect.x + rect.width <= bounds.x + bounds.width
    && rect.y + rect.height <= bounds.y + bounds.height;
}

export function mergeBounds(boundsList = []) {
  const validBounds = boundsList.filter(Boolean);
  if (!validBounds.length) {
    return null;
  }
  const minX = Math.min(...validBounds.map((item) => item.x));
  const minY = Math.min(...validBounds.map((item) => item.y));
  const maxX = Math.max(...validBounds.map((item) => item.x + item.width));
  const maxY = Math.max(...validBounds.map((item) => item.y + item.height));
  return {
    x: minX,
    y: minY,
    width: Math.max(0, maxX - minX),
    height: Math.max(0, maxY - minY),
  };
}

export function buildPlanDrawingBounds({
  imageWidth = null,
  imageHeight = null,
  geometryBounds = null,
  padding = DEFAULT_BOUNDS_PADDING,
} = {}) {
  const sourceBounds = mergeBounds([
    Number(imageWidth) > 0 && Number(imageHeight) > 0
      ? { x: 0, y: 0, width: Number(imageWidth), height: Number(imageHeight) }
      : null,
    geometryBounds,
  ]);
  return inflateRect(sourceBounds, padding);
}

export function buildLineObstacle(start, end, padding = 4) {
  const left = normalizePoint(start);
  const right = normalizePoint(end);
  if (!left || !right) {
    return null;
  }
  return inflateRect({
    x: Math.min(left.x, right.x),
    y: Math.min(left.y, right.y),
    width: Math.max(1, Math.abs(right.x - left.x)),
    height: Math.max(1, Math.abs(right.y - left.y)),
  }, padding);
}

export function buildPolylineObstacles(points, padding = 4) {
  const list = Array.isArray(points) ? points : [];
  const obstacles = [];
  for (let index = 0; index < list.length - 1; index += 1) {
    const obstacle = buildLineObstacle(list[index], list[index + 1], padding);
    if (obstacle) {
      obstacles.push(obstacle);
    }
  }
  return obstacles;
}

export function buildPointObstacle(point, size = 14, padding = 0) {
  const normalized = normalizePoint(point);
  if (!normalized) {
    return null;
  }
  return inflateRect({
    x: normalized.x - (size / 2),
    y: normalized.y - (size / 2),
    width: size,
    height: size,
  }, padding);
}

export function placementToObstacles(layout, rectPadding = 2, leaderPadding = DEFAULT_LEADER_PADDING) {
  if (!layout?.rect) {
    return [];
  }
  return [
    inflateRect(layout.rect, rectPadding),
    ...buildPolylineObstacles(layout.leaderPolyline || [], leaderPadding),
  ].filter(Boolean);
}

function measureTextWidth(text, fontSize, fontFamily) {
  const context = getMeasureContext();
  if (context) {
    context.font = `${fontSize}px ${fontFamily}`;
    const metrics = context.measureText(String(text || ''));
    if (metrics && Number.isFinite(metrics.width)) {
      return metrics.width;
    }
  }
  return String(text || '').length * fontSize * 0.62;
}

export function measurePlanText(text, fontSize, {
  fontFamily = DEFAULT_FONT_FAMILY,
  paddingX = DEFAULT_PADDING_X,
  heightFactor = DEFAULT_HEIGHT_FACTOR,
  rotation = 0,
} = {}) {
  const content = String(text || '');
  const baseWidth = Math.max(fontSize, measureTextWidth(content, fontSize, fontFamily) + (paddingX * 2));
  const baseHeight = Math.max(fontSize + 2, fontSize * heightFactor);
  const quarterTurns = ((((rotation % 360) + 360) % 360) / 90) % 4;
  if (quarterTurns === 1 || quarterTurns === 3) {
    return { width: baseHeight, height: baseWidth };
  }
  return { width: baseWidth, height: baseHeight };
}

export function measureTextRectAtTopLeft(text, x, y, fontSize, options = {}) {
  const { width, height } = measurePlanText(text, fontSize, options);
  return {
    x: Number(x || 0),
    y: Number(y || 0),
    width,
    height,
  };
}

export function measureTextRectFromCenter(text, centerX, centerY, fontSize, options = {}) {
  const { width, height } = measurePlanText(text, fontSize, options);
  return {
    x: Number(centerX || 0) - (width / 2),
    y: Number(centerY || 0) - (height / 2),
    width,
    height,
  };
}

function normalizeRegionConstraint(regionConstraint) {
  if (!regionConstraint) {
    return null;
  }
  const polygons = (regionConstraint.polygons || [])
    .map((polygon) => (Array.isArray(polygon) ? polygon : []))
    .filter((polygon) => polygon.length >= 3);
  const preferredPoints = (regionConstraint.preferredPoints || [])
    .map((point) => normalizePoint(point))
    .filter(Boolean);
  const bounds = regionConstraint.bounds || mergeBounds(
    polygons.map((polygon) => getBoundingBox(polygon)),
  );
  return {
    polygons,
    preferredPoints,
    bounds,
  };
}

function pointInAnyPolygon(point, polygons) {
  if (!polygons?.length) {
    return true;
  }
  return polygons.some((polygon) => pointInPolygon([point.x, point.y], polygon));
}

function rectMatchesRegion(rect, regionConstraint) {
  if (!regionConstraint) {
    return true;
  }
  const center = rectCenter(rect);
  if (!pointInAnyPolygon(center, regionConstraint.polygons)) {
    return false;
  }
  return isRectInsideBounds(rect, regionConstraint.bounds);
}

function candidateCollides(rect, obstacles = []) {
  return obstacles.some((obstacle) => rectsIntersect(rect, obstacle));
}

function buildDirectionOrder(preferredVector = null) {
  const baseDirections = [
    { key: 'e', x: 1, y: 0 },
    { key: 'ne', x: Math.SQRT1_2, y: -Math.SQRT1_2 },
    { key: 'se', x: Math.SQRT1_2, y: Math.SQRT1_2 },
    { key: 'w', x: -1, y: 0 },
    { key: 'nw', x: -Math.SQRT1_2, y: -Math.SQRT1_2 },
    { key: 'sw', x: -Math.SQRT1_2, y: Math.SQRT1_2 },
    { key: 'n', x: 0, y: -1 },
    { key: 's', x: 0, y: 1 },
  ];
  const preferred = normalizeVector(preferredVector);
  if (!preferred) {
    return baseDirections;
  }
  return [...baseDirections].sort((left, right) => {
    const leftDot = (left.x * preferred.x) + (left.y * preferred.y);
    const rightDot = (right.x * preferred.x) + (right.y * preferred.y);
    if (rightDot !== leftDot) {
      return rightDot - leftDot;
    }
    return 0;
  });
}

function buildAnchorCandidates({
  anchor,
  text,
  fontSize,
  metrics,
  symbolHalfWidth = 0,
  symbolHalfHeight = 0,
  preferredOffset = null,
  preferredVector = null,
  fontFamily = DEFAULT_FONT_FAMILY,
  rotation = 0,
}) {
  const candidates = [];
  if (preferredOffset) {
    candidates.push({
      rect: measureTextRectAtTopLeft(
        text,
        anchor.x + preferredOffset.dx,
        anchor.y + preferredOffset.dy,
        fontSize,
        { fontFamily, rotation },
      ),
      score: -1000,
    });
  }

  const preferredRect = preferredOffset
    ? measureTextRectAtTopLeft(
      text,
      anchor.x + preferredOffset.dx,
      anchor.y + preferredOffset.dy,
      fontSize,
      { fontFamily, rotation },
    )
    : null;
  const preferredDirection = preferredRect
    ? normalizeVector({
      x: rectCenter(preferredRect).x - anchor.x,
      y: rectCenter(preferredRect).y - anchor.y,
    })
    : normalizeVector(preferredVector);
  const directionOrder = buildDirectionOrder(preferredDirection);
  const ringStep = Math.max(10, Math.min(metrics.width, metrics.height));
  directionOrder.forEach((direction, directionIndex) => {
    for (let ring = 0; ring < DEFAULT_CANDIDATE_RINGS; ring += 1) {
      const tangentialOffsets = ring === 0 ? [0] : [0, -ringStep * 0.35, ringStep * 0.35];
      tangentialOffsets.forEach((tangentOffset, tangentIndex) => {
        const normalX = -direction.y;
        const normalY = direction.x;
        const horizontalDistance = symbolHalfWidth + 8 + (metrics.width / 2) + (ring * ringStep);
        const verticalDistance = symbolHalfHeight + 8 + (metrics.height / 2) + (ring * ringStep);
        const centerX = anchor.x + (direction.x * horizontalDistance) + (normalX * tangentOffset);
        const centerY = anchor.y + (direction.y * verticalDistance) + (normalY * tangentOffset);
        candidates.push({
          rect: measureTextRectFromCenter(text, centerX, centerY, fontSize, { fontFamily, rotation }),
          score: (ring * 100) + (directionIndex * 10) + tangentIndex,
        });
      });
    }
  });
  return candidates;
}

function buildSegmentCandidates({
  anchor,
  segment,
  text,
  fontSize,
  metrics,
  preferredOffset = null,
  preferredSide = null,
  fontFamily = DEFAULT_FONT_FAMILY,
  rotation = 0,
}) {
  const candidates = [];
  if (preferredOffset) {
    candidates.push({
      rect: measureTextRectAtTopLeft(
        text,
        anchor.x + preferredOffset.dx,
        anchor.y + preferredOffset.dy,
        fontSize,
        { fontFamily, rotation },
      ),
      score: -1000,
    });
  }
  const start = normalizePoint(segment?.start);
  const end = normalizePoint(segment?.end);
  if (!start || !end) {
    return candidates;
  }
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  const length = Math.hypot(dx, dy) || 1;
  const tangent = { x: dx / length, y: dy / length };
  const normal = { x: -tangent.y, y: tangent.x };
  const midpoint = {
    x: (start.x + end.x) / 2,
    y: (start.y + end.y) / 2,
  };
  const preferredSigns = preferredSide === -1 ? [-1, 1] : preferredSide === 1 ? [1, -1] : [1, -1];
  const tangentStep = Math.max(metrics.width * 0.5, 18);
  const tangentOffsets = [0, -tangentStep, tangentStep, -(tangentStep * 2), tangentStep * 2];
  const normalStep = Math.max(metrics.height * 0.75, 10);

  preferredSigns.forEach((sign, signIndex) => {
    for (let ring = 0; ring < DEFAULT_CANDIDATE_RINGS; ring += 1) {
      tangentOffsets.forEach((tangentOffset, tangentIndex) => {
        const centerX = midpoint.x
          + (normal.x * sign * ((metrics.height / 2) + 8 + (ring * normalStep)))
          + (tangent.x * tangentOffset);
        const centerY = midpoint.y
          + (normal.y * sign * ((metrics.height / 2) + 8 + (ring * normalStep)))
          + (tangent.y * tangentOffset);
        candidates.push({
          rect: measureTextRectFromCenter(text, centerX, centerY, fontSize, { fontFamily, rotation }),
          score: (ring * 100) + (signIndex * 10) + tangentIndex,
        });
      });
    }
  });
  return candidates;
}

function buildRegionCandidates({
  anchor,
  regionConstraint,
  text,
  fontSize,
  metrics,
  preferredOffset = null,
  fontFamily = DEFAULT_FONT_FAMILY,
  rotation = 0,
}) {
  const candidates = [];
  if (preferredOffset) {
    candidates.push({
      rect: measureTextRectAtTopLeft(
        text,
        anchor.x + preferredOffset.dx,
        anchor.y + preferredOffset.dy,
        fontSize,
        { fontFamily, rotation },
      ),
      score: -1000,
    });
  }
  const normalizedRegion = normalizeRegionConstraint(regionConstraint);
  if (!normalizedRegion?.bounds) {
    return candidates;
  }

  const seededCenters = normalizedRegion.preferredPoints.map((point, index) => ({
    point,
    score: index,
  }));
  const scanStepX = Math.max(metrics.width * 0.55, 12);
  const scanStepY = Math.max(metrics.height * 0.8, 12);
  const minX = normalizedRegion.bounds.x + (metrics.width / 2);
  const maxX = normalizedRegion.bounds.x + normalizedRegion.bounds.width - (metrics.width / 2);
  const minY = normalizedRegion.bounds.y + (metrics.height / 2);
  const maxY = normalizedRegion.bounds.y + normalizedRegion.bounds.height - (metrics.height / 2);
  for (let y = minY; y <= maxY + 1e-6; y += scanStepY) {
    for (let x = minX; x <= maxX + 1e-6; x += scanStepX) {
      seededCenters.push({
        point: { x, y },
        score: 1000 + Math.hypot(x - anchor.x, y - anchor.y),
      });
    }
  }

  seededCenters
    .filter(({ point }) => pointInAnyPolygon(point, normalizedRegion.polygons))
    .sort((left, right) => {
      if (left.score !== right.score) {
        return left.score - right.score;
      }
      if (left.point.y !== right.point.y) {
        return left.point.y - right.point.y;
      }
      return left.point.x - right.point.x;
    })
    .forEach(({ point, score }) => {
      candidates.push({
        rect: measureTextRectFromCenter(text, point.x, point.y, fontSize, { fontFamily, rotation }),
        score,
      });
    });

  return candidates;
}

function buildOverflowCandidates(anchor, metrics, bounds) {
  if (!bounds) {
    return [];
  }
  const sideOffsets = [];
  const step = Math.max(metrics.width * 0.55, metrics.height * 1.15, 18);
  for (let index = 0; index <= DEFAULT_OVERFLOW_STEPS; index += 1) {
    if (index === 0) {
      sideOffsets.push(0);
    } else {
      sideOffsets.push(-(index * step), index * step);
    }
  }

  const sideCandidates = [
    {
      side: 'top',
      distance: Math.abs(anchor.y - bounds.y),
      buildRect: (offset) => ({
        x: clamp(anchor.x + offset, bounds.x + (metrics.width / 2) + DEFAULT_OVERFLOW_OFFSETS, bounds.x + bounds.width - (metrics.width / 2) - DEFAULT_OVERFLOW_OFFSETS) - (metrics.width / 2),
        y: bounds.y + DEFAULT_OVERFLOW_OFFSETS,
        width: metrics.width,
        height: metrics.height,
      }),
    },
    {
      side: 'bottom',
      distance: Math.abs((bounds.y + bounds.height) - anchor.y),
      buildRect: (offset) => ({
        x: clamp(anchor.x + offset, bounds.x + (metrics.width / 2) + DEFAULT_OVERFLOW_OFFSETS, bounds.x + bounds.width - (metrics.width / 2) - DEFAULT_OVERFLOW_OFFSETS) - (metrics.width / 2),
        y: bounds.y + bounds.height - DEFAULT_OVERFLOW_OFFSETS - metrics.height,
        width: metrics.width,
        height: metrics.height,
      }),
    },
    {
      side: 'left',
      distance: Math.abs(anchor.x - bounds.x),
      buildRect: (offset) => ({
        x: bounds.x + DEFAULT_OVERFLOW_OFFSETS,
        y: clamp(anchor.y + offset, bounds.y + (metrics.height / 2) + DEFAULT_OVERFLOW_OFFSETS, bounds.y + bounds.height - (metrics.height / 2) - DEFAULT_OVERFLOW_OFFSETS) - (metrics.height / 2),
        width: metrics.width,
        height: metrics.height,
      }),
    },
    {
      side: 'right',
      distance: Math.abs((bounds.x + bounds.width) - anchor.x),
      buildRect: (offset) => ({
        x: bounds.x + bounds.width - DEFAULT_OVERFLOW_OFFSETS - metrics.width,
        y: clamp(anchor.y + offset, bounds.y + (metrics.height / 2) + DEFAULT_OVERFLOW_OFFSETS, bounds.y + bounds.height - (metrics.height / 2) - DEFAULT_OVERFLOW_OFFSETS) - (metrics.height / 2),
        width: metrics.width,
        height: metrics.height,
      }),
    },
  ].sort((left, right) => left.distance - right.distance);

  const candidates = [];
  sideCandidates.forEach(({ buildRect }, sideIndex) => {
    sideOffsets.forEach((offset, offsetIndex) => {
      candidates.push({
        rect: buildRect(offset),
        score: (sideIndex * 1000) + offsetIndex,
      });
    });
  });
  return candidates;
}

function buildRectConnectionPoint(anchor, rect) {
  const center = rectCenter(rect);
  const leftDistance = Math.abs(anchor.x - rect.x);
  const rightDistance = Math.abs(anchor.x - (rect.x + rect.width));
  const topDistance = Math.abs(anchor.y - rect.y);
  const bottomDistance = Math.abs(anchor.y - (rect.y + rect.height));
  const minimum = Math.min(leftDistance, rightDistance, topDistance, bottomDistance);
  if (minimum === leftDistance) {
    return { x: rect.x, y: clamp(anchor.y, rect.y, rect.y + rect.height) };
  }
  if (minimum === rightDistance) {
    return { x: rect.x + rect.width, y: clamp(anchor.y, rect.y, rect.y + rect.height) };
  }
  if (minimum === topDistance) {
    return { x: clamp(anchor.x, rect.x, rect.x + rect.width), y: rect.y };
  }
  if (minimum === bottomDistance) {
    return { x: clamp(anchor.x, rect.x, rect.x + rect.width), y: rect.y + rect.height };
  }
  return center;
}

function buildLeaderPolylineCandidates(anchor, rect) {
  const target = buildRectConnectionPoint(anchor, rect);
  if (Math.abs(anchor.x - target.x) <= 1e-6 || Math.abs(anchor.y - target.y) <= 1e-6) {
    return [[[anchor.x, anchor.y], [target.x, target.y]]];
  }
  return [
    [[anchor.x, anchor.y], [target.x, anchor.y], [target.x, target.y]],
    [[anchor.x, anchor.y], [anchor.x, target.y], [target.x, target.y]],
  ];
}

function leaderPolylineIsClear(polyline, anchor, rect, obstacles) {
  const filteredObstacles = (obstacles || []).filter((obstacle) => !rectContainsPoint(obstacle, anchor));
  const leaderObstacles = buildPolylineObstacles(polyline, DEFAULT_LEADER_PADDING);
  return leaderObstacles.every((leaderObstacle) => (
    !filteredObstacles.some((obstacle) => (
      rectsIntersect(leaderObstacle, obstacle)
      && !rectsIntersect(obstacle, rect)
    ))
  ));
}

function buildPlacementResult(candidateRect, anchor, obstacles, forceLeader = false) {
  if (!forceLeader) {
    return { rect: candidateRect, leaderPolyline: null, overflow: false };
  }
  const leaderCandidate = buildLeaderPolylineCandidates(anchor, candidateRect)
    .find((polyline) => leaderPolylineIsClear(polyline, anchor, candidateRect, obstacles));
  if (!leaderCandidate) {
    return null;
  }
  return { rect: candidateRect, leaderPolyline: leaderCandidate, overflow: true };
}

function normalizePreferredOffset(preferredOffset) {
  if (!preferredOffset || preferredOffset.dx === null || preferredOffset.dx === undefined || preferredOffset.dy === null || preferredOffset.dy === undefined) {
    return null;
  }
  return {
    dx: Number(preferredOffset.dx),
    dy: Number(preferredOffset.dy),
  };
}

export function placePlanText({
  text,
  fontSize,
  fontFamily = DEFAULT_FONT_FAMILY,
  strategy = 'anchor',
  anchor,
  segment = null,
  symbolHalfWidth = 0,
  symbolHalfHeight = 0,
  preferredOffset = null,
  preferredVector = null,
  preferredSide = null,
  obstacles = [],
  bounds = null,
  regionConstraint = null,
  rotation = 0,
  allowOverflow = true,
} = {}) {
  const normalizedAnchor = normalizePoint(anchor)
    || (segment?.start && segment?.end
      ? {
        x: (Number(segment.start.x ?? segment.start[0] ?? 0) + Number(segment.end.x ?? segment.end[0] ?? 0)) / 2,
        y: (Number(segment.start.y ?? segment.start[1] ?? 0) + Number(segment.end.y ?? segment.end[1] ?? 0)) / 2,
      }
      : null);
  if (!normalizedAnchor || !String(text || '').trim()) {
    return null;
  }

  const metrics = measurePlanText(text, fontSize, { fontFamily, rotation });
  const normalizedPreferredOffset = normalizePreferredOffset(preferredOffset);
  const normalizedRegion = normalizeRegionConstraint(regionConstraint);
  const candidateSource = strategy === 'segment'
    ? buildSegmentCandidates({
      anchor: normalizedAnchor,
      segment,
      text,
      fontSize,
      metrics,
      preferredOffset: normalizedPreferredOffset,
      preferredSide,
      fontFamily,
      rotation,
    })
    : strategy === 'region'
      ? buildRegionCandidates({
        anchor: normalizedAnchor,
        regionConstraint: normalizedRegion,
        text,
        fontSize,
        metrics,
        preferredOffset: normalizedPreferredOffset,
        fontFamily,
        rotation,
      })
      : buildAnchorCandidates({
        anchor: normalizedAnchor,
        text,
        fontSize,
        metrics,
        symbolHalfWidth,
        symbolHalfHeight,
        preferredOffset: normalizedPreferredOffset,
        preferredVector,
        fontFamily,
        rotation,
      });

  const normalizedObstacles = (obstacles || []).filter(Boolean);
  for (const candidate of candidateSource.sort((left, right) => left.score - right.score)) {
    if (!isRectInsideBounds(candidate.rect, bounds)) {
      continue;
    }
    if (!rectMatchesRegion(candidate.rect, normalizedRegion)) {
      continue;
    }
    if (candidateCollides(candidate.rect, normalizedObstacles)) {
      continue;
    }
    return { rect: candidate.rect, leaderPolyline: null, overflow: false };
  }

  if (!allowOverflow) {
    return null;
  }

  const overflowCandidate = buildOverflowCandidates(normalizedAnchor, metrics, bounds)
    .sort((left, right) => left.score - right.score)
    .find((candidate) => {
      if (!isRectInsideBounds(candidate.rect, bounds)) {
        return false;
      }
      if (candidateCollides(candidate.rect, normalizedObstacles)) {
        return false;
      }
      return buildLeaderPolylineCandidates(normalizedAnchor, candidate.rect)
        .some((polyline) => leaderPolylineIsClear(polyline, normalizedAnchor, candidate.rect, normalizedObstacles));
    });

  if (overflowCandidate) {
    return buildPlacementResult(overflowCandidate.rect, normalizedAnchor, normalizedObstacles, true);
  }
  return null;
}
