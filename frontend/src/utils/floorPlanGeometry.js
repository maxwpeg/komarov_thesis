export function pxToMeters(pxValue, scaleFactor) {
  if (pxValue === null || pxValue === undefined) {
    return null;
  }
  const scale = scaleFactor && scaleFactor > 0 ? scaleFactor : 1;
  return (Number(pxValue) * scale) / 1000;
}

export function metersToPx(metersValue, scaleFactor) {
  if (metersValue === null || metersValue === undefined) {
    return null;
  }
  const scale = scaleFactor && scaleFactor > 0 ? scaleFactor : 1;
  return (Number(metersValue) * 1000) / scale;
}

export function pxToMillimeters(pxValue, scaleFactor) {
  if (pxValue === null || pxValue === undefined) {
    return null;
  }
  const scale = scaleFactor && scaleFactor > 0 ? scaleFactor : 1;
  return Number(pxValue) * scale;
}

export function millimetersToPx(mmValue, scaleFactor) {
  if (mmValue === null || mmValue === undefined) {
    return null;
  }
  const scale = scaleFactor && scaleFactor > 0 ? scaleFactor : 1;
  return Number(mmValue) / scale;
}

export function getWallThicknessPx(wall, scaleFactor) {
  const scale = scaleFactor && scaleFactor > 0 ? scaleFactor : 1;
  const thicknessMm = wall?.thickness ?? 200;
  return Math.max(4, thicknessMm / scale);
}

export function normalizeWallAlignment(value) {
  const alignment = String(value || 'center').toLowerCase();
  return ['left', 'right'].includes(alignment) ? alignment : 'center';
}

export function getWallNormalOffsetsPx(wall, scaleFactor) {
  const thicknessPx = getWallThicknessPx(wall, scaleFactor);
  const alignment = normalizeWallAlignment(wall?.alignment);
  return {
    positive: thicknessPx / 2,
    negative: thicknessPx / 2,
    thicknessPx,
    alignment,
  };
}

export function getWallOutlineGeometry(wall, scaleFactor) {
  const axis = getWallAxis(wall);
  const offsets = getWallNormalOffsetsPx(wall, scaleFactor);
  if (!axis) {
    const half = offsets.thicknessPx / 2;
    const x = Number(wall?.x1 || 0);
    const y = Number(wall?.y1 || 0);
    return {
      axis: null,
      thicknessPx: offsets.thicknessPx,
      offsets,
      top: [x - half, y - half, x + half, y - half],
      bottom: [x - half, y + half, x + half, y + half],
      start: [x - half, y - half, x - half, y + half],
      end: [x + half, y - half, x + half, y + half],
      polygon: [
        x - half, y - half,
        x + half, y - half,
        x + half, y + half,
        x - half, y + half,
      ],
      bounds: {
        x: x - half,
        y: y - half,
        width: offsets.thicknessPx,
        height: offsets.thicknessPx,
      },
    };
  }
  const { x1, y1, x2, y2, nx, ny } = axis;
  const topStartX = x1 + (nx * offsets.positive);
  const topStartY = y1 + (ny * offsets.positive);
  const topEndX = x2 + (nx * offsets.positive);
  const topEndY = y2 + (ny * offsets.positive);
  const bottomStartX = x1 - (nx * offsets.negative);
  const bottomStartY = y1 - (ny * offsets.negative);
  const bottomEndX = x2 - (nx * offsets.negative);
  const bottomEndY = y2 - (ny * offsets.negative);
  const polygon = [
    topStartX, topStartY,
    topEndX, topEndY,
    bottomEndX, bottomEndY,
    bottomStartX, bottomStartY,
  ];
  const xs = [topStartX, topEndX, bottomEndX, bottomStartX];
  const ys = [topStartY, topEndY, bottomEndY, bottomStartY];
  return {
    axis,
    thicknessPx: offsets.thicknessPx,
    offsets,
    top: [topStartX, topStartY, topEndX, topEndY],
    bottom: [bottomStartX, bottomStartY, bottomEndX, bottomEndY],
    start: [topStartX, topStartY, bottomStartX, bottomStartY],
    end: [topEndX, topEndY, bottomEndX, bottomEndY],
    polygon,
    bounds: {
      x: Math.min(...xs),
      y: Math.min(...ys),
      width: Math.max(...xs) - Math.min(...xs),
      height: Math.max(...ys) - Math.min(...ys),
    },
  };
}

export function getWallBounds(wall, scaleFactor) {
  return getWallOutlineGeometry(wall, scaleFactor).bounds;
}

export function normalizeRectFromPoints(start, end) {
  return {
    x: Math.min(start.x, end.x),
    y: Math.min(start.y, end.y),
    width: Math.abs(end.x - start.x),
    height: Math.abs(end.y - start.y),
  };
}

export function getWallAxis(wall) {
  const dx = (wall.x2 ?? 0) - (wall.x1 ?? 0);
  const dy = (wall.y2 ?? 0) - (wall.y1 ?? 0);
  const length = Math.hypot(dx, dy);
  if (length < 1e-6) {
    return null;
  }
  return {
    x1: wall.x1,
    y1: wall.y1,
    x2: wall.x2,
    y2: wall.y2,
    dx,
    dy,
    length,
    ux: dx / length,
    uy: dy / length,
    nx: -dy / length,
    ny: dx / length,
    rotationDeg: (Math.atan2(dy, dx) * 180) / Math.PI,
  };
}

export function projectPointToWall(point, wall) {
  const axis = getWallAxis(wall);
  if (!axis) {
    return null;
  }
  const relativeX = point.x - axis.x1;
  const relativeY = point.y - axis.y1;
  const along = relativeX * axis.ux + relativeY * axis.uy;
  const normal = relativeX * axis.nx + relativeY * axis.ny;
  return {
    along,
    normal,
    projectedX: axis.x1 + axis.ux * along,
    projectedY: axis.y1 + axis.uy * along,
    axis,
  };
}

export function clampHoverPanelPosition(pointer, containerRect, panelSize, padding = 12) {
  const width = panelSize?.width || 290;
  const height = panelSize?.height || 200;
  const offsetX = 28;
  const relativeX = pointer.x - containerRect.left;
  const relativeY = pointer.y - containerRect.top;
  const canPlaceRight = relativeX + offsetX + width <= containerRect.width - padding;
  const preferredLeft = canPlaceRight
    ? relativeX + offsetX
    : relativeX - width - offsetX;
  const preferredTop = relativeY - height / 2;
  return {
    left: Math.max(
      padding,
      Math.min(preferredLeft, containerRect.width - width - padding),
    ),
    top: Math.max(
      padding,
      Math.min(preferredTop, containerRect.height - height - padding),
    ),
    width,
    height,
  };
}

export function normalizeQuarterTurns(value) {
  const normalized = Math.round(Number(value) || 0) % 4;
  return normalized < 0 ? normalized + 4 : normalized;
}

export function getRotatedImageSize(imageWidth, imageHeight, rotationQuarterTurns = 0) {
  const width = Math.max(1, Number(imageWidth || 0));
  const height = Math.max(1, Number(imageHeight || 0));
  return normalizeQuarterTurns(rotationQuarterTurns) % 2 === 0
    ? { width, height }
    : { width: height, height: width };
}

export function createViewportTransform({
  containerWidth,
  containerHeight,
  imageWidth,
  imageHeight,
  zoom = 1,
  pan = { x: 0, y: 0 },
  rotationQuarterTurns = 0,
  fitPaddingRatio = 1,
}) {
  const safeContainerWidth = Math.max(1, Number(containerWidth || 0));
  const safeContainerHeight = Math.max(1, Number(containerHeight || 0));
  const safeImageWidth = Math.max(1, Number(imageWidth || 0));
  const safeImageHeight = Math.max(1, Number(imageHeight || 0));
  const normalizedTurns = normalizeQuarterTurns(rotationQuarterTurns);
  const rotatedSize = getRotatedImageSize(safeImageWidth, safeImageHeight, normalizedTurns);
  const safePadding = Math.max(0.05, Math.min(1, Number(fitPaddingRatio || 1)));
  const baseScale = Math.min(
    safeContainerWidth / rotatedSize.width,
    safeContainerHeight / rotatedSize.height,
  ) * safePadding;
  const scale = Math.max(1e-6, baseScale * Math.max(0.01, Number(zoom || 1)));
  const scaledWidth = rotatedSize.width * scale;
  const scaledHeight = rotatedSize.height * scale;
  return {
    containerWidth: safeContainerWidth,
    containerHeight: safeContainerHeight,
    imageWidth: safeImageWidth,
    imageHeight: safeImageHeight,
    imageCenterX: safeImageWidth / 2,
    imageCenterY: safeImageHeight / 2,
    rotatedWidth: rotatedSize.width,
    rotatedHeight: rotatedSize.height,
    rotationQuarterTurns: normalizedTurns,
    rotationDeg: normalizedTurns * 90,
    scale,
    baseScale,
    scaledWidth,
    scaledHeight,
    centerX: (safeContainerWidth / 2) + Number(pan?.x || 0),
    centerY: (safeContainerHeight / 2) + Number(pan?.y || 0),
  };
}

export function clampViewportPan(
  pan,
  {
    containerWidth,
    containerHeight,
    imageWidth,
    imageHeight,
    zoom = 1,
    rotationQuarterTurns = 0,
    fitPaddingRatio = 1,
  },
) {
  const transform = createViewportTransform({
    containerWidth,
    containerHeight,
    imageWidth,
    imageHeight,
    zoom,
    pan: { x: 0, y: 0 },
    rotationQuarterTurns,
    fitPaddingRatio,
  });
  const maxPanX = Math.max(0, (transform.scaledWidth - transform.containerWidth) / 2);
  const maxPanY = Math.max(0, (transform.scaledHeight - transform.containerHeight) / 2);
  const nextPanX = Number(pan?.x || 0);
  const nextPanY = Number(pan?.y || 0);
  return {
    x: maxPanX > 0 ? Math.max(-maxPanX, Math.min(maxPanX, nextPanX)) : 0,
    y: maxPanY > 0 ? Math.max(-maxPanY, Math.min(maxPanY, nextPanY)) : 0,
  };
}

function rotateQuarterTurnPoint(x, y, quarterTurns) {
  switch (normalizeQuarterTurns(quarterTurns)) {
    case 1:
      return { x: -y, y: x };
    case 2:
      return { x: -x, y: -y };
    case 3:
      return { x: y, y: -x };
    default:
      return { x, y };
  }
}

export function planPointToViewport(point, transform) {
  if (!transform) {
    return { x: Number(point?.x || 0), y: Number(point?.y || 0) };
  }
  const centeredX = Number(point?.x || 0) - transform.imageCenterX;
  const centeredY = Number(point?.y || 0) - transform.imageCenterY;
  const rotated = rotateQuarterTurnPoint(centeredX, centeredY, transform.rotationQuarterTurns);
  return {
    x: transform.centerX + rotated.x * transform.scale,
    y: transform.centerY + rotated.y * transform.scale,
  };
}

export function viewportPointToPlan(point, transform) {
  if (!transform) {
    return { x: Number(point?.x || 0), y: Number(point?.y || 0) };
  }
  const localX = (Number(point?.x || 0) - transform.centerX) / transform.scale;
  const localY = (Number(point?.y || 0) - transform.centerY) / transform.scale;
  const rotatedBack = rotateQuarterTurnPoint(localX, localY, -transform.rotationQuarterTurns);
  return {
    x: transform.imageCenterX + rotatedBack.x,
    y: transform.imageCenterY + rotatedBack.y,
  };
}

function openingSpanFromInput(opening, useBoundingRect) {
  const width = Math.abs(Number(opening.width ?? 0));
  const height = Math.abs(Number(opening.height ?? 0));
  return Math.max(4, useBoundingRect ? Math.max(width, height) : width);
}

function openingCenter(opening) {
  return {
    x: Number(opening.x ?? 0) + Number(opening.width ?? 0) / 2,
    y: Number(opening.y ?? 0) + Number(opening.height ?? 0) / 2,
  };
}

export function normalizeOpeningToWall(opening, walls, scaleFactor, options = {}) {
  if (!walls?.length) {
    return null;
  }
  const { preferredWallId = null, useBoundingRect = false } = options;
  const center = openingCenter(opening);
  const projectionMargin = Math.max(1, Number(opening.width ?? 0), Number(opening.height ?? 0));

  const distances = walls
    .map((wall) => {
      const projection = projectPointToWall(center, wall);
      if (!projection) {
        return null;
      }
      const offsets = getWallNormalOffsetsPx(wall, scaleFactor);
      const maxDistance = Math.max(
        offsets.thicknessPx * 0.5,
        Math.max(Number(opening.width ?? 0), Number(opening.height ?? 0), 40),
      );
      const fits =
        projection.along >= -projectionMargin &&
        projection.along <= projection.axis.length + projectionMargin &&
        projection.normal >= (-offsets.negative - maxDistance) &&
        projection.normal <= (offsets.positive + maxDistance);
      let distance = 0;
      if (projection.normal < -offsets.negative) {
        distance = Math.abs(projection.normal + offsets.negative);
      } else if (projection.normal > offsets.positive) {
        distance = Math.abs(projection.normal - offsets.positive);
      }
      return {
        wall,
        projection,
        fits,
        distance,
      };
    })
    .filter(Boolean)
    .sort((a, b) => {
      if (preferredWallId && a.wall.id === preferredWallId) {
        return -1;
      }
      if (preferredWallId && b.wall.id === preferredWallId) {
        return 1;
      }
      return a.distance - b.distance;
    });

  const best = distances.find((item) => item.fits) || null;
  if (!best) {
    return null;
  }

  const axis = best.projection.axis;
  const offsets = getWallNormalOffsetsPx(best.wall, scaleFactor);
  const thicknessPx = offsets.thicknessPx;
  const span = Math.min(openingSpanFromInput(opening, useBoundingRect), axis.length);
  const halfSpan = span / 2;
  const clampedAlong = Math.min(
    Math.max(best.projection.along, halfSpan),
    Math.max(halfSpan, axis.length - halfSpan),
  );
  const centerShift = (offsets.positive - offsets.negative) / 2;
  const centerX = axis.x1 + (axis.ux * clampedAlong) + (axis.nx * centerShift);
  const centerY = axis.y1 + (axis.uy * clampedAlong) + (axis.ny * centerShift);

  return {
    x: centerX - span / 2,
    y: centerY - thicknessPx / 2,
    width: span,
    height: thicknessPx,
    rotation_deg: axis.rotationDeg,
    wall_id: best.wall.id,
    centerX,
    centerY,
    wall: best.wall,
    axis,
  };
}

const WALL_GEOMETRY_EPSILON = 1e-6;
const WALL_EDGE_PARALLEL_THRESHOLD = Math.cos((Math.PI / 180) * 6);

function flatPolygonToPoints(polygon) {
  if (!polygon?.length) {
    return [];
  }
  const points = [];
  for (let index = 0; index < polygon.length; index += 2) {
    points.push({ x: polygon[index], y: polygon[index + 1] });
  }
  return points;
}

function segmentFromFlat(flatSegment) {
  return {
    start: { x: flatSegment[0], y: flatSegment[1] },
    end: { x: flatSegment[2], y: flatSegment[3] },
  };
}

function dot(ax, ay, bx, by) {
  return (ax * bx) + (ay * by);
}

function cross(ax, ay, bx, by) {
  return (ax * by) - (ay * bx);
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function almostEqual(left, right, tolerance = WALL_GEOMETRY_EPSILON) {
  return Math.abs(left - right) <= tolerance;
}

function getSegmentDirection(segment) {
  const dx = segment.end.x - segment.start.x;
  const dy = segment.end.y - segment.start.y;
  const length = Math.hypot(dx, dy);
  if (length < WALL_GEOMETRY_EPSILON) {
    return null;
  }
  return {
    dx,
    dy,
    length,
    ux: dx / length,
    uy: dy / length,
  };
}

function midpointOfSegment(segment) {
  return {
    x: (segment.start.x + segment.end.x) / 2,
    y: (segment.start.y + segment.end.y) / 2,
  };
}

function pointToSegmentDistance(point, segment) {
  const direction = getSegmentDirection(segment);
  if (!direction) {
    return Math.hypot(point.x - segment.start.x, point.y - segment.start.y);
  }
  const relativeX = point.x - segment.start.x;
  const relativeY = point.y - segment.start.y;
  const projection = clamp(
    dot(relativeX, relativeY, direction.ux, direction.uy),
    0,
    direction.length,
  );
  const closestX = segment.start.x + (direction.ux * projection);
  const closestY = segment.start.y + (direction.uy * projection);
  return Math.hypot(point.x - closestX, point.y - closestY);
}

function isPointOnSegment(point, segment, tolerance = 1e-4) {
  const direction = getSegmentDirection(segment);
  if (!direction) {
    return Math.hypot(point.x - segment.start.x, point.y - segment.start.y) <= tolerance;
  }
  const relativeX = point.x - segment.start.x;
  const relativeY = point.y - segment.start.y;
  const lineDistance = Math.abs(cross(relativeX, relativeY, direction.ux, direction.uy));
  if (lineDistance > tolerance) {
    return false;
  }
  const along = dot(relativeX, relativeY, direction.ux, direction.uy);
  return along >= -tolerance && along <= direction.length + tolerance;
}

function pointInPolygonInclusive(point, polygon) {
  if (!polygon?.length) {
    return false;
  }
  let inside = false;
  let previous = polygon[polygon.length - 1];
  for (const current of polygon) {
    const edge = { start: previous, end: current };
    if (isPointOnSegment(point, edge)) {
      return true;
    }
    const intersects = ((current.y > point.y) !== (previous.y > point.y))
      && (point.x < (((previous.x - current.x) * (point.y - current.y)) / ((previous.y - current.y) || 1e-9)) + current.x);
    if (intersects) {
      inside = !inside;
    }
    previous = current;
  }
  return inside;
}

function segmentIntersectionParameters(segment, otherSegment) {
  const direction = getSegmentDirection(segment);
  const otherDirection = getSegmentDirection(otherSegment);
  if (!direction || !otherDirection) {
    return [];
  }
  const rx = direction.dx;
  const ry = direction.dy;
  const sx = otherDirection.dx;
  const sy = otherDirection.dy;
  const qpx = otherSegment.start.x - segment.start.x;
  const qpy = otherSegment.start.y - segment.start.y;
  const rxs = cross(rx, ry, sx, sy);
  const qpxr = cross(qpx, qpy, rx, ry);
  if (almostEqual(rxs, 0) && almostEqual(qpxr, 0)) {
    const rDotR = dot(rx, ry, rx, ry) || 1;
    const t0 = dot(qpx, qpy, rx, ry) / rDotR;
    const t1 = t0 + (dot(sx, sy, rx, ry) / rDotR);
    const overlapStart = clamp(Math.min(t0, t1), 0, 1);
    const overlapEnd = clamp(Math.max(t0, t1), 0, 1);
    if (overlapEnd - overlapStart <= WALL_GEOMETRY_EPSILON) {
      return [];
    }
    return [overlapStart, overlapEnd];
  }
  if (almostEqual(rxs, 0)) {
    return [];
  }
  const t = cross(qpx, qpy, sx, sy) / rxs;
  const u = cross(qpx, qpy, rx, ry) / rxs;
  if (
    t >= -WALL_GEOMETRY_EPSILON
    && t <= 1 + WALL_GEOMETRY_EPSILON
    && u >= -WALL_GEOMETRY_EPSILON
    && u <= 1 + WALL_GEOMETRY_EPSILON
  ) {
    return [clamp(t, 0, 1)];
  }
  return [];
}

function lineIntersection(pointA, directionA, pointB, directionB) {
  const denominator = cross(directionA.x, directionA.y, directionB.x, directionB.y);
  if (Math.abs(denominator) <= WALL_GEOMETRY_EPSILON) {
    return null;
  }
  const deltaX = pointB.x - pointA.x;
  const deltaY = pointB.y - pointA.y;
  const t = cross(deltaX, deltaY, directionB.x, directionB.y) / denominator;
  return {
    x: pointA.x + (directionA.x * t),
    y: pointA.y + (directionA.y * t),
    t,
  };
}

function getWallEdgeDescriptors(wall, scaleFactor) {
  const geometry = getWallOutlineGeometry({ ...wall, alignment: 'center' }, scaleFactor);
  return {
    geometry,
    polygon: flatPolygonToPoints(geometry.polygon),
    longEdges: [
      {
        kind: 'long',
        side: 'positive',
        segment: segmentFromFlat(geometry.top),
      },
      {
        kind: 'long',
        side: 'negative',
        segment: segmentFromFlat(geometry.bottom),
      },
    ],
    shortEdges: [
      {
        kind: 'short',
        side: 'start',
        segment: segmentFromFlat(geometry.start),
      },
      {
        kind: 'short',
        side: 'end',
        segment: segmentFromFlat(geometry.end),
      },
    ],
  };
}

function shouldKeepFarOverlapBoundary(entry, edge, segment, otherEntry) {
  if (edge.kind !== 'short' || !entry?.geometry?.axis) {
    return false;
  }
  const midpoint = midpointOfSegment(segment);
  const overlapsOtherLongEdge = otherEntry.longEdges.some((otherEdge) => (
    isPointOnSegment(midpoint, otherEdge.segment, 1e-3)
  ));
  if (!overlapsOtherLongEdge) {
    return false;
  }
  const inwardDirection = edge.side === 'start'
    ? { x: entry.geometry.axis.ux, y: entry.geometry.axis.uy }
    : { x: -entry.geometry.axis.ux, y: -entry.geometry.axis.uy };
  const probeDistance = Math.max(
    0.1,
    Math.min(entry.geometry.thicknessPx, otherEntry.geometry.thicknessPx) * 0.1,
  );
  const probePoint = {
    x: midpoint.x + (inwardDirection.x * probeDistance),
    y: midpoint.y + (inwardDirection.y * probeDistance),
  };
  return pointInPolygonInclusive(probePoint, otherEntry.polygon);
}

function findEndpointAdjustmentCandidate(
  wall,
  movingPoint,
  walls,
  scaleFactor,
  options = {},
) {
  if (!wall || !movingPoint || !walls?.length) {
    return null;
  }
  const {
    movingEndpoint = 'end',
    excludeWallId = null,
    thresholdPx = null,
    requirePenetration = false,
  } = options;
  const anchor = movingEndpoint === 'start'
    ? { x: Number(wall.x2 ?? 0), y: Number(wall.y2 ?? 0) }
    : { x: Number(wall.x1 ?? 0), y: Number(wall.y1 ?? 0) };
  const candidateWall = {
    ...wall,
    x1: anchor.x,
    y1: anchor.y,
    x2: Number(movingPoint.x ?? 0),
    y2: Number(movingPoint.y ?? 0),
    alignment: 'center',
  };
  const candidateEdges = getWallEdgeDescriptors(candidateWall, scaleFactor);
  const candidateAxis = candidateEdges.geometry.axis;
  if (!candidateAxis) {
    return null;
  }
  const candidateShortEdge = candidateEdges.shortEdges.find((edge) => edge.side === 'end')?.segment;
  if (!candidateShortEdge) {
    return null;
  }
  const shortDirection = getSegmentDirection(candidateShortEdge);
  if (!shortDirection) {
    return null;
  }
  if (
    requirePenetration
    && !(
      pointInPolygonInclusive(midpointOfSegment(candidateShortEdge), candidateEdges.polygon)
      || pointInPolygonInclusive(candidateShortEdge.start, candidateEdges.polygon)
      || pointInPolygonInclusive(candidateShortEdge.end, candidateEdges.polygon)
    )
  ) {
    return null;
  }

  let bestCandidate = null;
  walls.forEach((otherWall) => {
    if (!otherWall || (excludeWallId !== null && otherWall.id === excludeWallId)) {
      return;
    }
    const otherEdges = getWallEdgeDescriptors(otherWall, scaleFactor);
    const penetratesOther = !requirePenetration
      || pointInPolygonInclusive(midpointOfSegment(candidateShortEdge), otherEdges.polygon)
      || pointInPolygonInclusive(candidateShortEdge.start, otherEdges.polygon)
      || pointInPolygonInclusive(candidateShortEdge.end, otherEdges.polygon);
    if (!penetratesOther) {
      return;
    }
    otherEdges.longEdges.forEach((edge) => {
      const edgeDirection = getSegmentDirection(edge.segment);
      if (!edgeDirection) {
        return;
      }
      if (Math.abs(dot(shortDirection.ux, shortDirection.uy, edgeDirection.ux, edgeDirection.uy)) < WALL_EDGE_PARALLEL_THRESHOLD) {
        return;
      }
      const distance = pointToSegmentDistance(movingPoint, edge.segment);
      if (thresholdPx !== null && distance >= thresholdPx) {
        return;
      }
      const intersection = lineIntersection(
        anchor,
        { x: candidateAxis.ux, y: candidateAxis.uy },
        edge.segment.start,
        { x: edgeDirection.ux, y: edgeDirection.uy },
      );
      if (!intersection) {
        return;
      }
      const alongCandidate = dot(
        intersection.x - anchor.x,
        intersection.y - anchor.y,
        candidateAxis.ux,
        candidateAxis.uy,
      );
      if (alongCandidate <= WALL_GEOMETRY_EPSILON) {
        return;
      }
      const alongEdge = dot(
        intersection.x - edge.segment.start.x,
        intersection.y - edge.segment.start.y,
        edgeDirection.ux,
        edgeDirection.uy,
      );
      if (
        alongEdge < -1e-4
        || alongEdge > edgeDirection.length + 1e-4
      ) {
        return;
      }
      const displacement = Math.abs(candidateAxis.length - alongCandidate);
      if (
        !bestCandidate
        || displacement < bestCandidate.displacement - WALL_GEOMETRY_EPSILON
        || (
          almostEqual(displacement, bestCandidate.displacement)
          && distance < bestCandidate.distance
        )
      ) {
        bestCandidate = {
          point: { x: intersection.x, y: intersection.y },
          displacement,
          distance,
        };
      }
    });
  });
  return bestCandidate;
}

function withUpdatedWallEndpoint(wall, movingEndpoint, point, scaleFactor) {
  const nextWall = movingEndpoint === 'start'
    ? { ...wall, x1: point.x, y1: point.y, alignment: 'center' }
    : { ...wall, x2: point.x, y2: point.y, alignment: 'center' };
  const axis = getWallAxis(nextWall);
  if (!axis || axis.length <= WALL_GEOMETRY_EPSILON) {
    return wall;
  }
  return {
    ...nextWall,
    length_m: pxToMeters(axis.length, scaleFactor),
    length_source: 'derived',
  };
}

export function resolveWallEndpointSnap(wall, movingPoint, walls, scaleFactor, options = {}) {
  if (!wall || !movingPoint || !walls?.length) {
    return movingPoint;
  }
  const thresholdPx = options.thresholdPx ?? getWallThicknessPx(wall, scaleFactor);
  const candidate = findEndpointAdjustmentCandidate(
    wall,
    movingPoint,
    walls,
    scaleFactor,
    {
      ...options,
      thresholdPx,
      requirePenetration: false,
    },
  );
  return candidate?.point || movingPoint;
}

export function resolveWallEndpointOverlap(wall, movingPoint, walls, scaleFactor, options = {}) {
  return resolveWallEndpointSnap(wall, movingPoint, walls, scaleFactor, options);
}

export function normalizeWallIntersections(walls, scaleFactor, options = {}) {
  if (!walls?.length) {
    return [];
  }
  const {
    maxIterations = 8,
  } = options;
  const nextWalls = walls.map((wall) => ({
    ...wall,
    alignment: 'center',
  }));

  for (let iteration = 0; iteration < maxIterations; iteration += 1) {
    let changed = false;
    for (let index = 0; index < nextWalls.length; index += 1) {
      let currentWall = nextWalls[index];
      ['start', 'end'].forEach((movingEndpoint) => {
        const currentPoint = movingEndpoint === 'start'
          ? { x: currentWall.x1, y: currentWall.y1 }
          : { x: currentWall.x2, y: currentWall.y2 };
        const candidate = findEndpointAdjustmentCandidate(
          currentWall,
          currentPoint,
          nextWalls,
          scaleFactor,
          {
            movingEndpoint,
            excludeWallId: currentWall.id,
            requirePenetration: true,
          },
        );
        if (!candidate) {
          return;
        }
        const nextPoint = candidate.point;
        if (
          Math.hypot(nextPoint.x - currentPoint.x, nextPoint.y - currentPoint.y)
          <= WALL_GEOMETRY_EPSILON
        ) {
          return;
        }
        const updatedWall = withUpdatedWallEndpoint(
          currentWall,
          movingEndpoint,
          nextPoint,
          scaleFactor,
        );
        if (
          updatedWall.x1 !== currentWall.x1
          || updatedWall.y1 !== currentWall.y1
          || updatedWall.x2 !== currentWall.x2
          || updatedWall.y2 !== currentWall.y2
        ) {
          currentWall = updatedWall;
          changed = true;
        }
      });
      nextWalls[index] = currentWall;
    }
    if (!changed) {
      break;
    }
  }
  return nextWalls;
}

export function getVisibleWallBoundarySegments(walls, scaleFactor) {
  if (!walls?.length) {
    return [];
  }
  const wallEntries = walls.map((wall) => ({
    wall,
    ...getWallEdgeDescriptors(wall, scaleFactor),
  }));
  const visibleSegments = [];
  wallEntries.forEach((entry, entryIndex) => {
    [...entry.longEdges, ...entry.shortEdges].forEach((edge) => {
      const splitParameters = [0, 1];
      wallEntries.forEach((otherEntry, otherIndex) => {
        if (otherIndex === entryIndex) {
          return;
        }
        [...otherEntry.longEdges, ...otherEntry.shortEdges].forEach((otherEdge) => {
          splitParameters.push(...segmentIntersectionParameters(edge.segment, otherEdge.segment));
        });
      });
      const normalizedParameters = [...new Set(
        splitParameters
          .map((value) => clamp(value, 0, 1))
          .sort((left, right) => left - right)
          .map((value) => Number(value.toFixed(6))),
      )];
      for (let index = 0; index < normalizedParameters.length - 1; index += 1) {
        const startT = normalizedParameters[index];
        const endT = normalizedParameters[index + 1];
        if (endT - startT <= WALL_GEOMETRY_EPSILON) {
          continue;
        }
        const segment = {
          start: {
            x: edge.segment.start.x + ((edge.segment.end.x - edge.segment.start.x) * startT),
            y: edge.segment.start.y + ((edge.segment.end.y - edge.segment.start.y) * startT),
          },
          end: {
            x: edge.segment.start.x + ((edge.segment.end.x - edge.segment.start.x) * endT),
            y: edge.segment.start.y + ((edge.segment.end.y - edge.segment.start.y) * endT),
          },
        };
        const midpoint = midpointOfSegment(segment);
        const hidden = wallEntries.some((otherEntry, otherIndex) => (
          otherIndex !== entryIndex
          && pointInPolygonInclusive(midpoint, otherEntry.polygon)
          && !shouldKeepFarOverlapBoundary(entry, edge, segment, otherEntry)
        ));
        if (!hidden) {
          visibleSegments.push({
            wallId: entry.wall.id,
            kind: edge.kind,
            side: edge.side,
            points: [
              segment.start.x,
              segment.start.y,
              segment.end.x,
              segment.end.y,
            ],
          });
        }
      }
    });
  });
  return visibleSegments;
}

export function snapWallPoint(point, walls, options = {}) {
  const {
    excludeWallId = null,
    endpointThreshold = 14,
    axisThreshold = 12,
  } = options;
  let bestCandidate = null;
  const registerCandidate = (candidate) => {
    if (!candidate) {
      return;
    }
    if (candidate.distance > candidate.threshold) {
      return;
    }
    if (
      !bestCandidate
      || candidate.priority < bestCandidate.priority
      || (candidate.priority === bestCandidate.priority && candidate.distance < bestCandidate.distance)
    ) {
      bestCandidate = candidate;
    }
  };

  walls.forEach((wall) => {
    if (!wall || (excludeWallId !== null && wall.id === excludeWallId)) {
      return;
    }
    const axis = getWallAxis(wall);
    if (!axis) {
      return;
    }

    [
      { x: axis.x1, y: axis.y1 },
      { x: axis.x2, y: axis.y2 },
    ].forEach((endpoint) => {
      const distance = Math.hypot(point.x - endpoint.x, point.y - endpoint.y);
      registerCandidate({
        point: endpoint,
        distance,
        threshold: endpointThreshold,
        priority: 0,
      });
    });

    const projection = projectPointToWall(point, wall);
    if (!projection) {
      return;
    }
    if (projection.along < -endpointThreshold || projection.along > axis.length + endpointThreshold) {
      return;
    }
    const clampedAlong = Math.max(0, Math.min(axis.length, projection.along));
    registerCandidate({
      point: {
        x: axis.x1 + (axis.ux * clampedAlong),
        y: axis.y1 + (axis.uy * clampedAlong),
      },
      distance: Math.abs(projection.normal),
      threshold: axisThreshold,
      priority: 1,
    });
  });

  return bestCandidate ? bestCandidate.point : point;
}

export function getRotatedRectCorners(rect) {
  const width = Number(rect.width ?? 0);
  const height = Number(rect.height ?? 0);
  const angle = ((Number(rect.rotation_deg ?? 0) || 0) * Math.PI) / 180;
  const cx = Number(rect.x ?? 0) + width / 2;
  const cy = Number(rect.y ?? 0) + height / 2;
  const cos = Math.cos(angle);
  const sin = Math.sin(angle);
  const points = [
    [-width / 2, -height / 2],
    [width / 2, -height / 2],
    [width / 2, height / 2],
    [-width / 2, height / 2],
  ];
  return points.map(([px, py]) => ({
    x: cx + px * cos - py * sin,
    y: cy + px * sin + py * cos,
  }));
}

export function getOpeningEdgeHandles(opening) {
  const axis = getWallAxis({
    x1: opening.x,
    y1: opening.y + (opening.height ?? 0) / 2,
    x2: opening.x + (opening.width ?? 0),
    y2: opening.y + (opening.height ?? 0) / 2,
  });
  if (!axis) {
    return null;
  }
  const angle = ((Number(opening.rotation_deg ?? 0) || 0) * Math.PI) / 180;
  const cos = Math.cos(angle);
  const sin = Math.sin(angle);
  const cx = Number(opening.x ?? 0) + Number(opening.width ?? 0) / 2;
  const cy = Number(opening.y ?? 0) + Number(opening.height ?? 0) / 2;
  const halfSpan = Number(opening.width ?? 0) / 2;
  return {
    start: { x: cx - cos * halfSpan, y: cy - sin * halfSpan },
    end: { x: cx + cos * halfSpan, y: cy + sin * halfSpan },
  };
}

export function getStairGuideLines(stair) {
  const axis = stair.step_axis || (stair.width >= stair.height ? 'horizontal' : 'vertical');
  const span = axis === 'horizontal' ? Number(stair.width ?? 0) : Number(stair.height ?? 0);
  const count = Math.max(2, Math.min(14, Math.round(span / 28)));
  const lines = [];
  if (axis === 'horizontal') {
    const gap = stair.width / (count + 1);
    for (let index = 1; index <= count; index += 1) {
      const x = stair.x + gap * index;
      lines.push([x, stair.y, x, stair.y + stair.height]);
    }
  } else {
    const gap = stair.height / (count + 1);
    for (let index = 1; index <= count; index += 1) {
      const y = stair.y + gap * index;
      lines.push([stair.x, y, stair.x + stair.width, y]);
    }
  }
  return lines;
}
