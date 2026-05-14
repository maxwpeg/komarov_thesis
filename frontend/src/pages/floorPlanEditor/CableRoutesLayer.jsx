import React from 'react';
import { Circle, Group, Line, Rect, Text } from 'react-konva';

import { polylineToKonvaPoints, shouldShowRouteTerminator, SOUE_VISUAL_STYLE } from './helpers';
import {
  placePlanText,
} from './textPlacement';

const BASE_ROUTE_STROKE_WIDTH = 3;
const ZC_LABEL_TEXT = 'ZC';
const ZC_LABEL_FONT_SIZE = 8;
const DETECTOR_SYMBOL_HALF_SIZE = 14;
const ZC_TERMINATOR_HALF_SIZE = 5.4;
const ZC_ROUTE_OFFSET = DETECTOR_SYMBOL_HALF_SIZE + ZC_TERMINATOR_HALF_SIZE;
const ZC_SIDE_VECTORS = {
  east: { x: 1, y: 0 },
  west: { x: -1, y: 0 },
  north: { x: 0, y: -1 },
  south: { x: 0, y: 1 },
};

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

function buildRectObstacle(point, halfWidth, halfHeight) {
  if (!point) {
    return null;
  }
  return {
    x: Number(point[0] || 0) - halfWidth,
    y: Number(point[1] || 0) - halfHeight,
    width: halfWidth * 2,
    height: halfHeight * 2,
  };
}

function buildZcTerminatorObstacle(point) {
  return buildRectObstacle(point, ZC_TERMINATOR_HALF_SIZE, ZC_TERMINATOR_HALF_SIZE);
}

function buildZcTailObstacle(start, end, padding = 3.5) {
  return buildSegmentObstacle(start, end, padding);
}

function getPointSignature(point) {
  if (!point) {
    return null;
  }
  return `${roundDisplayPoint(point[0])}:${roundDisplayPoint(point[1])}`;
}

function getOrderedSidesForVector(dx, dy) {
  if (Math.abs(dx) <= 1e-6 && Math.abs(dy) <= 1e-6) {
    return ['east', 'north', 'south', 'west'];
  }
  return Object.entries(ZC_SIDE_VECTORS)
    .sort((left, right) => {
      const leftScore = -((left[1].x * dx) + (left[1].y * dy));
      const rightScore = -((right[1].x * dx) + (right[1].y * dy));
      if (leftScore !== rightScore) {
        return leftScore - rightScore;
      }
      return left[0].localeCompare(right[0]);
    })
    .map(([side]) => side);
}

function inferUsedSide(centerPoint, polyline) {
  if (!centerPoint || !Array.isArray(polyline) || polyline.length === 0) {
    return null;
  }
  const centerSignature = getPointSignature(centerPoint);
  for (let index = polyline.length - 1; index >= 0; index -= 1) {
    const point = polyline[index];
    if (getPointSignature(point) === centerSignature) {
      continue;
    }
    const dx = Number(point[0] || 0) - Number(centerPoint[0] || 0);
    const dy = Number(point[1] || 0) - Number(centerPoint[1] || 0);
    return getOrderedSidesForVector(dx, dy)[0] || null;
  }
  return null;
}

function getZcTerminatorCandidate(centerPoint, side) {
  const vector = ZC_SIDE_VECTORS[side] || ZC_SIDE_VECTORS.east;
  return [
    roundDisplayPoint(Number(centerPoint?.[0] || 0) + (vector.x * ZC_ROUTE_OFFSET)),
    roundDisplayPoint(Number(centerPoint?.[1] || 0) + (vector.y * ZC_ROUTE_OFFSET)),
  ];
}

function rectMatches(obstacle, candidate) {
  if (!obstacle || !candidate) {
    return false;
  }
  return (
    Math.abs(obstacle.x - candidate.x) <= 1e-6
    && Math.abs(obstacle.y - candidate.y) <= 1e-6
    && Math.abs(obstacle.width - candidate.width) <= 1e-6
    && Math.abs(obstacle.height - candidate.height) <= 1e-6
  );
}

export function getZcTerminatorPoint({
  route,
  polyline,
  deviceLookup = {},
  obstacles = [],
}) {
  const points = Array.isArray(polyline) ? polyline : [];
  const lastDeviceId = Array.isArray(route?.device_ids) && route.device_ids.length > 0
    ? route.device_ids[route.device_ids.length - 1]
    : null;
  const device = lastDeviceId !== null && lastDeviceId !== undefined ? deviceLookup[lastDeviceId] : null;
  const rawEndpoint = points.length ? points[points.length - 1] : null;
  if (!device || !rawEndpoint) {
    return rawEndpoint;
  }

  const centerPoint = [Number(device.x || 0), Number(device.y || 0)];
  const cablePolyline = points.length > 1 ? points.slice(0, -1) : points;
  const blockedSide = inferUsedSide(centerPoint, cablePolyline);
  const preferredSource = cablePolyline.length
    ? cablePolyline[cablePolyline.length - 1]
    : rawEndpoint;
  const preferredDx = Number(centerPoint[0] || 0) - Number(preferredSource?.[0] || 0);
  const preferredDy = Number(centerPoint[1] || 0) - Number(preferredSource?.[1] || 0);
  const orderedSides = getOrderedSidesForVector(preferredDx, preferredDy);
  const candidateSides = blockedSide && orderedSides.includes(blockedSide) && orderedSides.length > 1
    ? [...orderedSides.filter((side) => side !== blockedSide), blockedSide]
    : orderedSides;

  for (const side of candidateSides) {
    const candidate = getZcTerminatorCandidate(centerPoint, side);
    const tailObstacle = buildZcTailObstacle(centerPoint, candidate);
    const terminatorObstacle = buildZcTerminatorObstacle(candidate);
    const collides = (obstacles || []).some((obstacle) => (
      (tailObstacle && rectsIntersect(obstacle, tailObstacle))
      || (terminatorObstacle && rectsIntersect(obstacle, terminatorObstacle))
    ));
    if (!collides) {
      return candidate;
    }
  }

  return rawEndpoint;
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

function buildSpreadOffsets(count, spacingStep = BASE_ROUTE_STROKE_WIDTH) {
  if (count <= 1) {
    return [0];
  }
  const midpoint = (count - 1) / 2;
  return Array.from({ length: count }, (_, index) => (index - midpoint) * spacingStep);
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

export function buildDisplayCableRoutes(routes, spacingStep = BASE_ROUTE_STROKE_WIDTH) {
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
      if (left.routeNumber !== right.routeNumber) {
        return left.routeNumber - right.routeNumber;
      }
      if (left.routeId !== right.routeId) {
        return String(left.routeId || '').localeCompare(String(right.routeId || ''));
      }
      return left.routeIndex - right.routeIndex;
    });
    const offsets = buildSpreadOffsets(ordered.length, spacingStep);
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
  const placement = placePlanText({
    text,
    fontSize: ZC_LABEL_FONT_SIZE,
    strategy: 'anchor',
    anchor: { x: Number(end[0] || 0), y: Number(end[1] || 0) },
    symbolHalfWidth: terminatorSize / 2,
    symbolHalfHeight: terminatorSize / 2,
    preferredVector: getTerminalDirection(points),
    obstacles,
    bounds: stageBounds,
  });
  return placement?.rect || null;
}

export default function CableRoutesLayer({
  routes,
  selectedElement,
  selectedCableSegment,
  hoveredElement,
  activeCableHandle,
  isRouteBlocked,
  onSelectRoute,
  onSelectSegment,
  onHoverEnter,
  onHoverMove,
  onHoverLeave,
  onHandleDragStart,
  onHandleDragEnd,
  onSegmentDragStart,
  onSegmentDragEnd,
  onZcLabelDragEnd,
  deviceLookup = {},
  labelObstacles = [],
  stageBounds = null,
}) {
  const displayRouteMap = buildDisplayCableRoutes(routes, BASE_ROUTE_STROKE_WIDTH);
  const routeDisplayData = React.useMemo(() => {
    const baseRouteObstacles = (routes || []).flatMap((route) => {
      const displayPolyline = displayRouteMap[route.id] || route.polyline_points || [];
      const basePolyline = shouldShowRouteTerminator(route) && displayPolyline.length > 1
        ? displayPolyline.slice(0, -1)
        : displayPolyline;
      return [
        ...buildPolylineObstacles(basePolyline, 4),
        buildEndpointObstacle(basePolyline[basePolyline.length - 1], 16),
      ].filter(Boolean);
    });

    const placedZcObstacles = [];
    const displayData = {};
    (routes || []).forEach((route) => {
      const displayPolyline = displayRouteMap[route.id] || route.polyline_points || [];
      const shouldShowZc = shouldShowRouteTerminator(route) && displayPolyline.length > 0;
      const basePolyline = shouldShowZc && displayPolyline.length > 1
        ? displayPolyline.slice(0, -1)
        : displayPolyline;
      const zcPoint = shouldShowZc
        ? getZcTerminatorPoint({
          route,
          polyline: displayPolyline,
          deviceLookup,
          obstacles: [...labelObstacles, ...baseRouteObstacles, ...placedZcObstacles],
        })
        : null;
      const finalPolyline = zcPoint ? [...basePolyline, zcPoint] : basePolyline;
      const ownTailObstacles = zcPoint && basePolyline.length
        ? [
          buildZcTailObstacle(basePolyline[basePolyline.length - 1], zcPoint),
          buildZcTerminatorObstacle(zcPoint),
        ].filter(Boolean)
        : [];
      displayData[route.id] = {
        polyline: finalPolyline,
        zcPoint,
        ownTailObstacles,
      };
      placedZcObstacles.push(...ownTailObstacles);
    });

    return {
      displayData,
      routeObstacles: [...baseRouteObstacles, ...placedZcObstacles],
    };
  }, [deviceLookup, displayRouteMap, labelObstacles, routes]);

  return routes.map((route) => {
    const isSelected = selectedElement?.type === 'cable-route' && selectedElement?.id === route.id;
    const isHovered = hoveredElement?.type === 'cable-route' && hoveredElement?.id === route.id;
    const isBlocked = typeof isRouteBlocked === 'function' ? isRouteBlocked(route.id) : false;
    const routeDisplay = routeDisplayData.displayData[route.id] || {};
    const displayPolyline = routeDisplay.polyline || displayRouteMap[route.id] || route.polyline_points || [];
    const shouldShowZc = shouldShowRouteTerminator(route) && displayPolyline.length > 0;
    const zcPoint = shouldShowZc ? (routeDisplay.zcPoint || displayPolyline[displayPolyline.length - 1]) : null;
    const terminatorSize = isSelected || isHovered ? 12.6 : 10.8;
    const savedZcLayout = zcPoint
      && route.zc_label_dx !== null
      && route.zc_label_dx !== undefined
      && route.zc_label_dy !== null
      && route.zc_label_dy !== undefined
      ? { dx: route.zc_label_dx, dy: route.zc_label_dy }
      : null;
    const zcLabelPlacement = shouldShowZc
      ? placePlanText({
        text: ZC_LABEL_TEXT,
        fontSize: ZC_LABEL_FONT_SIZE,
        strategy: 'anchor',
        anchor: { x: Number(zcPoint[0] || 0), y: Number(zcPoint[1] || 0) },
        symbolHalfWidth: terminatorSize / 2,
        symbolHalfHeight: terminatorSize / 2,
        preferredVector: getTerminalDirection(displayPolyline),
        preferredOffset: savedZcLayout,
        obstacles: [
          ...labelObstacles,
          ...routeDisplayData.routeObstacles.filter((obstacle) => !routeDisplay.ownTailObstacles?.some((ownObstacle) => rectMatches(obstacle, ownObstacle))),
        ],
        bounds: stageBounds,
      })
      : null;
    const baseColor = String(route?.subsystem_type || 'sps') === 'soue' ? SOUE_VISUAL_STYLE.base : '#ef4444';
    const hoverColor = String(route?.subsystem_type || 'sps') === 'soue' ? SOUE_VISUAL_STYLE.hover : '#dc2626';
    const selectedColor = String(route?.subsystem_type || 'sps') === 'soue' ? SOUE_VISUAL_STYLE.selected : '#b91c1c';
    const routeStroke = isSelected ? selectedColor : (isHovered ? hoverColor : baseColor);

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
        {zcLabelPlacement?.leaderPolyline && (
          <Line
            points={zcLabelPlacement.leaderPolyline.flat()}
            stroke={routeStroke}
            strokeWidth={1.2}
            dash={[4, 3]}
            lineCap="round"
            lineJoin="round"
            listening={false}
          />
        )}
        {zcLabelPlacement?.rect && (
          <Text
            text={ZC_LABEL_TEXT}
            x={zcLabelPlacement.rect.x}
            y={zcLabelPlacement.rect.y}
            width={zcLabelPlacement.rect.width}
            align="center"
            fontSize={ZC_LABEL_FONT_SIZE}
            fontFamily="GOST A"
            fill={routeStroke}
            wrap="none"
            ellipsis={false}
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
            stroke={hoverColor}
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
          const isSegmentSelected = selectedCableSegment?.routeId === route.id && selectedCableSegment?.segmentIndex === pointIndex;
          return (
            <Rect
              key={`cable-route-segment-${route.id}-${pointIndex}`}
              x={(point[0] + nextPoint[0]) / 2 - 4}
              y={(point[1] + nextPoint[1]) / 2 - 4}
              width={8}
              height={8}
              fill={activeCableHandle?.routeId === route.id && activeCableHandle?.insertIndex === pointIndex + 1
                ? '#dc2626'
                : (isSegmentSelected ? '#fee2e2' : '#ffffff')}
              stroke={hoverColor}
              strokeWidth={isSegmentSelected ? 2.2 : 1.5}
              cornerRadius={2}
              listening={!isBlocked}
              draggable={!isBlocked}
              onClick={!isBlocked ? ((e) => {
                e.cancelBubble = true;
                onSelectSegment?.(route, pointIndex);
              }) : undefined}
              onDragStart={!isBlocked ? (() => {
                onSelectSegment?.(route, pointIndex);
                onSegmentDragStart(route.id, pointIndex + 1);
              }) : undefined}
              onDragEnd={!isBlocked ? ((e) => onSegmentDragEnd(route, pointIndex + 1, e)) : undefined}
            />
          );
        })}
      </React.Fragment>
    );
  });
}
