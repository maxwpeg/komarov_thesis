import React from 'react';
import { Circle, Group, Line, Rect, Text } from 'react-konva';

import { polylineToKonvaPoints } from './helpers';

const DISPLAY_ROUTE_SPACING = 4;
const ZC_LABEL_TEXT = 'ZC';
const ZC_LABEL_FONT_SIZE = 8;
const ZC_LABEL_PADDING_X = 3;
const ZC_LABEL_HEIGHT = 12;

function rectsIntersect(a, b) {
  if (!a || !b) {
    return false;
  }
  return !(
    a.x + a.width <= b.x
    || b.x + b.width <= a.x
    || a.y + a.height <= b.y
    || b.y + b.height <= a.y
  );
}

function inflateRect(rect, padding) {
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

function isRectInsideBounds(rect, bounds) {
  if (!rect || !bounds) {
    return true;
  }
  return rect.x >= bounds.x
    && rect.y >= bounds.y
    && rect.x + rect.width <= bounds.x + bounds.width
    && rect.y + rect.height <= bounds.y + bounds.height;
}

function getLabelWidth(text = ZC_LABEL_TEXT) {
  return (String(text || '').length * ZC_LABEL_FONT_SIZE * 0.62) + (ZC_LABEL_PADDING_X * 2);
}

function makeLabelRect(centerX, centerY, text = ZC_LABEL_TEXT) {
  const width = getLabelWidth(text);
  return {
    x: centerX - (width / 2),
    y: centerY - (ZC_LABEL_HEIGHT / 2),
    width,
    height: ZC_LABEL_HEIGHT,
  };
}

function makeOffsetLabelRect(anchorX, anchorY, dx, dy, text = ZC_LABEL_TEXT) {
  return {
    x: anchorX + dx,
    y: anchorY + dy,
    width: getLabelWidth(text),
    height: ZC_LABEL_HEIGHT,
  };
}

function buildSegmentObstacle(start, end, padding = 4) {
  if (!start || !end) {
    return null;
  }
  const x1 = Number(start[0] || 0);
  const y1 = Number(start[1] || 0);
  const x2 = Number(end[0] || 0);
  const y2 = Number(end[1] || 0);
  return inflateRect({
    x: Math.min(x1, x2),
    y: Math.min(y1, y2),
    width: Math.abs(x2 - x1) || 1,
    height: Math.abs(y2 - y1) || 1,
  }, padding);
}

function buildPolylineObstacles(polyline, padding = 4) {
  const points = Array.isArray(polyline) ? polyline : [];
  const obstacles = [];
  for (let index = 0; index < points.length - 1; index += 1) {
    const obstacle = buildSegmentObstacle(points[index], points[index + 1], padding);
    if (obstacle) {
      obstacles.push(obstacle);
    }
  }
  return obstacles;
}

function buildEndpointObstacle(point, size = 14) {
  if (!point) {
    return null;
  }
  return {
    x: Number(point[0] || 0) - (size / 2),
    y: Number(point[1] || 0) - (size / 2),
    width: size,
    height: size,
  };
}

function ZcTerminator({ x, y, isSelected, isHovered }) {
  const size = isSelected || isHovered ? 12.6 : 10.8;
  const half = size / 2;
  const stroke = isSelected ? '#b91c1c' : (isHovered ? '#dc2626' : '#ef4444');
  return (
    <Group x={x} y={y} listening={false}>
      <Rect
        x={-half}
        y={-half}
        width={size}
        height={size}
        fill="#ffffff"
        stroke={stroke}
        strokeWidth={2}
      />
      <Line
        points={[-size * 0.25, 0, size * 0.25, 0]}
        stroke={stroke}
        strokeWidth={1.6}
        lineCap="round"
      />
    </Group>
  );
}

function roundDisplayPoint(value) {
  return Math.round(Number(value || 0) * 1000) / 1000;
}

function getSegmentOrientation(start, end) {
  if (!start || !end) {
    return null;
  }
  const dx = Number(end[0] || 0) - Number(start[0] || 0);
  const dy = Number(end[1] || 0) - Number(start[1] || 0);
  if (Math.abs(dx) >= Math.abs(dy) && Math.abs(dx) > 1e-6) {
    return 'horizontal';
  }
  if (Math.abs(dy) > 1e-6) {
    return 'vertical';
  }
  return null;
}

function getSegmentKey(start, end) {
  const orientation = getSegmentOrientation(start, end);
  if (!orientation) {
    return null;
  }
  if (orientation === 'horizontal') {
    const y = roundDisplayPoint(start[1]);
    const x1 = roundDisplayPoint(Math.min(start[0], end[0]));
    const x2 = roundDisplayPoint(Math.max(start[0], end[0]));
    return `h:${y}:${x1}:${x2}`;
  }
  const x = roundDisplayPoint(start[0]);
  const y1 = roundDisplayPoint(Math.min(start[1], end[1]));
  const y2 = roundDisplayPoint(Math.max(start[1], end[1]));
  return `v:${x}:${y1}:${y2}`;
}

function buildSpreadOffsets(count) {
  if (count <= 1) {
    return [0];
  }
  const midpoint = (count - 1) / 2;
  return Array.from({ length: count }, (_, index) => (index - midpoint) * DISPLAY_ROUTE_SPACING);
}

function buildSelectedSpreadOffsets(count) {
  if (count <= 1) {
    return [0];
  }
  const offsets = [0];
  let distance = 1;
  while (offsets.length < count) {
    offsets.push(-distance * DISPLAY_ROUTE_SPACING);
    if (offsets.length < count) {
      offsets.push(distance * DISPLAY_ROUTE_SPACING);
    }
    distance += 1;
  }
  return offsets;
}

function offsetSegment(start, end, offset) {
  const orientation = getSegmentOrientation(start, end);
  if (!orientation || Math.abs(offset) <= 1e-6) {
    return {
      orientation,
      start: { x: Number(start?.[0] || 0), y: Number(start?.[1] || 0) },
      end: { x: Number(end?.[0] || 0), y: Number(end?.[1] || 0) },
    };
  }

  if (orientation === 'horizontal') {
    return {
      orientation,
      start: { x: Number(start[0]), y: Number(start[1]) + offset },
      end: { x: Number(end[0]), y: Number(end[1]) + offset },
    };
  }

  return {
    orientation,
    start: { x: Number(start[0]) + offset, y: Number(start[1]) },
    end: { x: Number(end[0]) + offset, y: Number(end[1]) },
  };
}

function resolveSegmentJoint(previousSegment, nextSegment) {
  if (!previousSegment) {
    return nextSegment?.start || { x: 0, y: 0 };
  }
  if (!nextSegment) {
    return previousSegment.end;
  }
  if (previousSegment.orientation === 'horizontal' && nextSegment.orientation === 'vertical') {
    return { x: nextSegment.start.x, y: previousSegment.end.y };
  }
  if (previousSegment.orientation === 'vertical' && nextSegment.orientation === 'horizontal') {
    return { x: previousSegment.end.x, y: nextSegment.start.y };
  }
  return {
    x: (previousSegment.end.x + nextSegment.start.x) / 2,
    y: (previousSegment.end.y + nextSegment.start.y) / 2,
  };
}

function applyOffsetsToPolyline(polyline, routeId, offsetLookup) {
  const points = Array.isArray(polyline) ? polyline : [];
  if (points.length < 2) {
    return points;
  }

  const offsetSegments = [];
  for (let segmentIndex = 0; segmentIndex < points.length - 1; segmentIndex += 1) {
    const start = points[segmentIndex];
    const end = points[segmentIndex + 1];
    const offset = offsetLookup.get(`${routeId}:${segmentIndex}`) || 0;
    offsetSegments.push(offsetSegment(start, end, offset));
  }

  if (!offsetSegments.length) {
    return points;
  }

  const displayPoints = [offsetSegments[0].start];
  for (let segmentIndex = 0; segmentIndex < offsetSegments.length - 1; segmentIndex += 1) {
    displayPoints.push(resolveSegmentJoint(offsetSegments[segmentIndex], offsetSegments[segmentIndex + 1]));
  }
  displayPoints.push(offsetSegments[offsetSegments.length - 1].end);

  return displayPoints.map((point) => [roundDisplayPoint(point.x), roundDisplayPoint(point.y)]);
}

function getTerminalDirection(polyline) {
  const points = Array.isArray(polyline) ? polyline : [];
  if (points.length < 2) {
    return { x: 1, y: 0 };
  }
  const end = points[points.length - 1];
  for (let index = points.length - 2; index >= 0; index -= 1) {
    const start = points[index];
    const dx = Number(end[0] || 0) - Number(start[0] || 0);
    const dy = Number(end[1] || 0) - Number(start[1] || 0);
    const length = Math.hypot(dx, dy);
    if (length > 1e-6) {
      return {
        x: dx / length,
        y: dy / length,
      };
    }
  }
  return { x: 1, y: 0 };
}

export function buildDisplayCableRoutes(routes, selectedRouteId = null) {
  const preparedRoutes = (routes || []).map((route, index) => ({
    route,
    routeId: route?.id,
    routeIndex: index,
    routeNumber: Number(route?.route_number || 0),
  }));
  const groups = new Map();

  preparedRoutes.forEach(({ route, routeId, routeIndex, routeNumber }) => {
    const polyline = route?.polyline_points || [];
    for (let segmentIndex = 0; segmentIndex < polyline.length - 1; segmentIndex += 1) {
      const key = getSegmentKey(polyline[segmentIndex], polyline[segmentIndex + 1]);
      if (!key) {
        continue;
      }
      if (!groups.has(key)) {
        groups.set(key, []);
      }
      groups.get(key).push({ routeId, routeIndex, routeNumber, segmentIndex });
    }
  });

  const offsetLookup = new Map();
  groups.forEach((entries) => {
    if (!entries || entries.length < 2) {
      return;
    }
    const ordered = [...entries].sort((left, right) => {
      const leftSelected = left.routeId === selectedRouteId ? 1 : 0;
      const rightSelected = right.routeId === selectedRouteId ? 1 : 0;
      if (leftSelected !== rightSelected) {
        return rightSelected - leftSelected;
      }
      if (left.routeNumber !== right.routeNumber) {
        return left.routeNumber - right.routeNumber;
      }
      if (left.routeId !== right.routeId) {
        return Number(left.routeId || 0) - Number(right.routeId || 0);
      }
      return left.routeIndex - right.routeIndex;
    });
    const offsets = selectedRouteId !== null && selectedRouteId !== undefined && ordered.some((entry) => entry.routeId === selectedRouteId)
      ? buildSelectedSpreadOffsets(ordered.length)
      : buildSpreadOffsets(ordered.length);
    ordered.forEach((entry, index) => {
      offsetLookup.set(`${entry.routeId}:${entry.segmentIndex}`, offsets[index] || 0);
    });
  });

  return Object.fromEntries(preparedRoutes.map(({ route, routeId }) => [
    routeId,
    applyOffsetsToPolyline(route?.polyline_points || [], routeId, offsetLookup),
  ]));
}

export function getZcLabelLayout({
  polyline,
  terminatorSize = 10.8,
  text = ZC_LABEL_TEXT,
  obstacles = [],
  stageBounds = null,
}) {
  const points = Array.isArray(polyline) ? polyline : [];
  if (!points.length) {
    return null;
  }
  const end = points[points.length - 1];
  const direction = getTerminalDirection(points);
  const normal = { x: -direction.y, y: direction.x };
  const labelRect = makeLabelRect(0, 0, text);
  const forwardDistance = (terminatorSize / 2) + (labelRect.width / 2) + 6;
  const sideDistance = (labelRect.height / 2) + 6;
  const farForwardDistance = forwardDistance + labelRect.width + 4;
  const obstacleRects = (obstacles || []).filter(Boolean);

  const makeCandidateRect = (distance, normalOffset = 0, directionMultiplier = 1) => makeLabelRect(
    Number(end[0] || 0) + (direction.x * distance * directionMultiplier) + (normal.x * normalOffset),
    Number(end[1] || 0) + (direction.y * distance * directionMultiplier) + (normal.y * normalOffset),
    text,
  );

  const candidates = [
    makeCandidateRect(forwardDistance, 0, 1),
    makeCandidateRect(forwardDistance, sideDistance, 1),
    makeCandidateRect(forwardDistance, -sideDistance, 1),
    makeCandidateRect(forwardDistance, 0, -1),
  ];
  const fallback = makeCandidateRect(farForwardDistance, 0, 1);

  const isAvailable = (candidate) => (
    isRectInsideBounds(candidate, stageBounds)
    && !obstacleRects.some((obstacle) => rectsIntersect(candidate, obstacle))
  );

  return candidates.find(isAvailable) || fallback;
}

export default function CableRoutesLayer({
  routes,
  selectedElement,
  hoveredElement,
  activeCableHandle,
  isRouteBlocked,
  onSelectRoute,
  onHoverEnter,
  onHoverMove,
  onHoverLeave,
  onHandleDragStart,
  onHandleDragEnd,
  onSegmentDragStart,
  onSegmentDragEnd,
  onZcLabelDragEnd,
  labelObstacles = [],
  stageBounds = null,
}) {
  const selectedRouteId = selectedElement?.type === 'cable-route' ? selectedElement.id : null;
  const displayRouteMap = buildDisplayCableRoutes(routes, selectedRouteId);
  const routeObstacles = React.useMemo(() => (
    (routes || []).flatMap((route) => {
      const displayPolyline = displayRouteMap[route.id] || route.polyline_points || [];
      return [
        ...buildPolylineObstacles(displayPolyline, 4),
        buildEndpointObstacle(displayPolyline[displayPolyline.length - 1], 16),
      ].filter(Boolean);
    })
  ), [displayRouteMap, routes]);

  return routes.map((route) => {
    const isSelected = selectedElement?.type === 'cable-route' && selectedElement?.id === route.id;
    const isHovered = hoveredElement?.type === 'cable-route' && hoveredElement?.id === route.id;
    const isBlocked = typeof isRouteBlocked === 'function' ? isRouteBlocked(route.id) : false;
    const displayPolyline = displayRouteMap[route.id] || route.polyline_points || [];
    const shouldShowZc = route.system_type === 'non_addressable'
      && ['zone_loop', 'manual_line'].includes(route.route_kind)
      && displayPolyline.length > 0;
    const zcPoint = shouldShowZc ? displayPolyline[displayPolyline.length - 1] : null;
    const terminatorSize = isSelected || isHovered ? 12.6 : 10.8;
    const savedZcLayout = zcPoint
      && route.zc_label_dx !== null
      && route.zc_label_dx !== undefined
      && route.zc_label_dy !== null
      && route.zc_label_dy !== undefined
      ? makeOffsetLabelRect(zcPoint[0], zcPoint[1], route.zc_label_dx, route.zc_label_dy)
      : null;
    const zcLabelLayout = shouldShowZc
      ? savedZcLayout || getZcLabelLayout({
        polyline: displayPolyline,
        terminatorSize,
        obstacles: [
          ...labelObstacles,
          ...routeObstacles.filter((obstacle) => !rectsIntersect(obstacle, buildEndpointObstacle(zcPoint, 18))),
        ],
        stageBounds,
      })
      : null;
    const routeStroke = isSelected ? '#b91c1c' : (isHovered ? '#dc2626' : '#ef4444');

    return (
      <React.Fragment key={`cable-route-${route.id}`}>
        <Line
          points={polylineToKonvaPoints(displayPolyline)}
          stroke={routeStroke}
          strokeWidth={isSelected || isHovered ? 4 : 3}
          lineCap="round"
          lineJoin="round"
          listening={!isBlocked}
          onClick={!isBlocked ? ((e) => {
            e.cancelBubble = true;
            onSelectRoute(route);
          }) : undefined}
          onMouseEnter={!isBlocked ? ((e) => onHoverEnter(route.id, e)) : undefined}
          onMouseMove={!isBlocked ? ((e) => onHoverMove(route.id, e)) : undefined}
          onMouseLeave={!isBlocked ? onHoverLeave : undefined}
        />
        {zcPoint && (
          <ZcTerminator
            x={zcPoint[0]}
            y={zcPoint[1]}
            isSelected={isSelected}
            isHovered={isHovered}
          />
        )}
        {zcLabelLayout && (
          <Text
            text={ZC_LABEL_TEXT}
            x={zcLabelLayout.x}
            y={zcLabelLayout.y}
            width={zcLabelLayout.width}
            align="center"
            fontSize={ZC_LABEL_FONT_SIZE}
            fontFamily="GOST A"
            fill={routeStroke}
            listening={!isBlocked}
            draggable={!isBlocked}
            onClick={(e) => {
              e.cancelBubble = true;
              onSelectRoute(route);
            }}
            onDragEnd={!isBlocked ? ((e) => onZcLabelDragEnd?.(route, displayPolyline, e)) : undefined}
          />
        )}
        {isSelected && (route.polyline_points || []).map((point, pointIndex) => (
          <Circle
            key={`cable-route-handle-${route.id}-${pointIndex}`}
            x={point[0]}
            y={point[1]}
            radius={5}
            fill={activeCableHandle?.routeId === route.id && activeCableHandle?.pointIndex === pointIndex ? '#fee2e2' : '#ffffff'}
            stroke="#dc2626"
            strokeWidth={2}
            listening={!isBlocked}
            draggable={!isBlocked && pointIndex !== 0 && pointIndex !== (route.polyline_points || []).length - 1}
            onDragStart={!isBlocked ? (() => onHandleDragStart(route.id, pointIndex)) : undefined}
            onDragEnd={!isBlocked ? ((e) => onHandleDragEnd(route, pointIndex, e)) : undefined}
          />
        ))}
        {isSelected && (route.polyline_points || []).slice(0, -1).map((point, pointIndex) => {
          const nextPoint = route.polyline_points?.[pointIndex + 1];
          if (!nextPoint) {
            return null;
          }
          return (
            <Rect
              key={`cable-route-segment-${route.id}-${pointIndex}`}
              x={(point[0] + nextPoint[0]) / 2 - 4}
              y={(point[1] + nextPoint[1]) / 2 - 4}
              width={8}
              height={8}
              fill={activeCableHandle?.routeId === route.id && activeCableHandle?.insertIndex === pointIndex + 1 ? '#dc2626' : '#ffffff'}
              stroke="#dc2626"
              strokeWidth={1.5}
              cornerRadius={2}
              listening={!isBlocked}
              draggable={!isBlocked}
              onDragStart={!isBlocked ? (() => onSegmentDragStart(route.id, pointIndex + 1)) : undefined}
              onDragEnd={!isBlocked ? ((e) => onSegmentDragEnd(route, pointIndex + 1, e)) : undefined}
            />
          );
        })}
      </React.Fragment>
    );
  });
}
