import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Stage, Layer, Line, Rect, Circle, Text, Arc, Group } from 'react-konva';
import { elementsApi, floorPlansApi, pipelineApi, recognitionApi } from '../api/client';
import {
  clampViewportPan,
  clampHoverPanelPosition,
  createViewportTransform,
  getVisibleWallBoundarySegments,
  getOpeningEdgeHandles,
  getRotatedRectCorners,
  getStairGuideLines,
  getWallAxis as getWallAxisData,
  getWallBounds,
  getWallOutlineGeometry,
  millimetersToPx,
  normalizeWallIntersections,
  normalizeOpeningToWall,
  normalizeQuarterTurns,
  normalizeRectFromPoints,
  normalizeWallAlignment,
  projectPointToWall,
  resolveWallEndpointSnap,
  viewportPointToPlan,
} from '../utils/floorPlanGeometry';
import {
  BackgroundImage as BackgroundImagePrimitive,
  DeleteButton as DeleteButtonPrimitive,
  FireAlarmSymbol as FireAlarmSymbolPrimitive,
  SignalInstrumentSymbol as SignalInstrumentSymbolPrimitive,
} from './floorPlanEditor/CanvasPrimitives';
import CableRoutesLayer from './floorPlanEditor/CableRoutesLayer';
import DevicesCablesSidebarSection from './floorPlanEditor/DevicesCablesSidebarSection';
import SignalSystemSidebarSection from './floorPlanEditor/SignalSystemSidebarSection';
import ZkspcSidebarSection from './floorPlanEditor/ZkspcSidebarSection';
import {
  SIGNAL_INSTRUMENT_OPTIONS,
  SIGNAL_SYSTEM_OPTIONS,
  buildZkspcStyleMap,
  buildRoomZoneMap,
  formatCableMeters,
  getBranchCableRoutes,
  getBranchFireAlarms,
  getBranchSignalInstruments,
  getSignalBranchSummary,
  getSignalInstrumentDefinition,
  getSignalSystemLabel,
  getZkspcStyle,
  groupFireAlarmsByZone,
  normalizeSignalSystemType,
  polylineToKonvaPoints,
} from './floorPlanEditor/helpers';
import { useSignalBranchState } from './floorPlanEditor/useSignalBranchState';

// Delete Button Component for Canvas
function DeleteButton({ x, y, onClick }) {
  return <DeleteButtonPrimitive x={x} y={y} onClick={onClick} />;
}

// Background Image Component
function BackgroundImage({ src, grayscale = true, onImageLoad }) {
  return <BackgroundImagePrimitive src={src} grayscale={grayscale} onImageLoad={onImageLoad} />;
}

function getWallThicknessPx(wall, scaleFactor) {
  const scale = scaleFactor && scaleFactor > 0 ? scaleFactor : 1;
  const thicknessMm = wall?.thickness ?? 200;
  return Math.max(4, thicknessMm / scale);
}

function getWallBoundarySegments(x1, y1, x2, y2, thicknessPx) {
  const dx = x2 - x1;
  const dy = y2 - y1;
  const length = Math.sqrt(dx * dx + dy * dy);
  if (length < 1e-6) {
    return {
      top: [x1, y1, x2, y2],
      bottom: [x1, y1, x2, y2],
    };
  }
  const nx = -dy / length;
  const ny = dx / length;
  const offset = thicknessPx / 2;
  return {
    top: [x1 + nx * offset, y1 + ny * offset, x2 + nx * offset, y2 + ny * offset],
    bottom: [x1 - nx * offset, y1 - ny * offset, x2 - nx * offset, y2 - ny * offset],
  };
}

function formatDimensionMeters(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return '—';
  }
  return `${Number(value).toFixed(2)} м`;
}

function getWallPixelLength(wall) {
  if (!wall) {
    return 0;
  }
  const dx = (wall.x2 ?? 0) - (wall.x1 ?? 0);
  const dy = (wall.y2 ?? 0) - (wall.y1 ?? 0);
  return Math.sqrt(dx * dx + dy * dy);
}

function pxToMeters(pxValue, scaleFactor) {
  if (pxValue === null || pxValue === undefined) {
    return null;
  }
  const scale = scaleFactor && scaleFactor > 0 ? scaleFactor : 1;
  return (Number(pxValue) * scale) / 1000;
}

function metersToPx(metersValue, scaleFactor) {
  if (metersValue === null || metersValue === undefined) {
    return null;
  }
  const scale = scaleFactor && scaleFactor > 0 ? scaleFactor : 1;
  return (Number(metersValue) * 1000) / scale;
}

function buildDisplayNumberMap(items) {
  return Object.fromEntries(items.map((item, index) => [item.id, index + 1]));
}

function getDerivedWallLengthMeters(wall, scaleFactor) {
  return pxToMeters(getWallPixelLength(wall), scaleFactor);
}

function getAutoStairStepCount(stair) {
  const axis = stair?.step_axis || ((stair?.width || 0) >= (stair?.height || 0) ? 'horizontal' : 'vertical');
  const span = axis === 'horizontal' ? Number(stair?.width || 0) : Number(stair?.height || 0);
  return Math.max(2, Math.min(14, Math.round(span / 28)));
}

function createEmptyBatchPayload() {
  return {
    deleted: [],
    create_walls: [],
    create_stairs: [],
    create_doors: [],
    create_windows: [],
    create_fire_alarms: [],
    update_walls: [],
    update_stairs: [],
    update_doors: [],
    update_windows: [],
    update_rooms: [],
    update_fire_alarms: [],
  };
}

function parseModifiedElementKey(key) {
  const separator = key.lastIndexOf('-');
  return {
    type: key.slice(0, separator),
    id: parseInt(key.slice(separator + 1), 10),
  };
}

function formatMetersValue(value, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return '—';
  }
  return `${Number(value).toFixed(digits)} м`;
}

function normalizeAngle360(angle) {
  const normalized = angle % 360;
  return normalized < 0 ? normalized + 360 : normalized;
}

function getBoundingBox(points) {
  if (!points || points.length === 0) {
    return null;
  }
  let minX = Number.POSITIVE_INFINITY;
  let minY = Number.POSITIVE_INFINITY;
  let maxX = Number.NEGATIVE_INFINITY;
  let maxY = Number.NEGATIVE_INFINITY;
  points.forEach((point) => {
    const x = point[0];
    const y = point[1];
    minX = Math.min(minX, x);
    minY = Math.min(minY, y);
    maxX = Math.max(maxX, x);
    maxY = Math.max(maxY, y);
  });
  return { x: minX, y: minY, width: maxX - minX, height: maxY - minY };
}

function normalizeRect(rect) {
  if (!rect) {
    return null;
  }
  const x = Math.min(rect.x, rect.x + rect.width);
  const y = Math.min(rect.y, rect.y + rect.height);
  const width = Math.abs(rect.width);
  const height = Math.abs(rect.height);
  return { x, y, width, height };
}

function rectsIntersect(a, b) {
  if (!a || !b) {
    return false;
  }
  return !(
    a.x + a.width < b.x ||
    b.x + b.width < a.x ||
    a.y + a.height < b.y ||
    b.y + b.height < a.y
  );
}

function areViewportStatesEqual(left, right) {
  return left?.zoom === right?.zoom
    && left?.rotationQuarterTurns === right?.rotationQuarterTurns
    && left?.pan?.x === right?.pan?.x
    && left?.pan?.y === right?.pan?.y;
}

function estimateTextRect(text, x, y, fontSize = 10) {
  const content = String(text || '');
  const width = Math.max(fontSize, content.length * fontSize * 0.62);
  const height = Math.max(fontSize + 2, fontSize * 1.2);
  return {
    x,
    y,
    width,
    height,
  };
}

const CANVAS_FONT_FAMILY = 'GOST A';

function getInstrumentLabelText(instrument) {
  if (!instrument) {
    return null;
  }
  const explicitName = String(instrument.name || '').trim();
  if (explicitName) {
    return explicitName;
  }
  return instrument.instrument_type === 'control_panel' ? 'ARK' : null;
}

function getSignalInstrumentBounds(instrument) {
  if (!instrument) {
    return null;
  }
  const isControlPanel = instrument.instrument_type === 'control_panel';
  const width = isControlPanel ? 48 : 36;
  const height = isControlPanel ? 28 : 36;
  return {
    x: instrument.x - (width / 2),
    y: instrument.y - (height / 2),
    width,
    height,
  };
}

function getFireAlarmBounds(alarm) {
  if (!alarm) {
    return null;
  }
  return {
    x: alarm.x - 14,
    y: alarm.y - 14,
    width: 28,
    height: 28,
  };
}

function getDoorSymbolSegmentsForOpening(opening) {
  if (!opening) {
    return null;
  }
  const halfWidth = Number(opening.width || 0) / 2;
  const halfHeight = Number(opening.height || 0) / 2;
  const centerHalfHeight = halfHeight + (Number(opening.height || 0) * 0.75);
  return {
    start: [-halfWidth, -halfHeight, -halfWidth, halfHeight],
    center: [0, -centerHalfHeight, 0, centerHalfHeight],
    end: [halfWidth, -halfHeight, halfWidth, halfHeight],
  };
}

function getSymbolLabelCandidates(anchorX, anchorY, text, fontSize, symbolHalfWidth, symbolHalfHeight) {
  const horizontalGap = symbolHalfWidth + 8;
  const verticalGap = symbolHalfHeight + 8;
  const sideGap = symbolHalfHeight + 6;
  return [
    estimateTextRect(text, anchorX + horizontalGap, anchorY - 8, fontSize),
    estimateTextRect(text, anchorX + horizontalGap, anchorY - verticalGap, fontSize),
    estimateTextRect(text, anchorX + horizontalGap, anchorY + verticalGap, fontSize),
    estimateTextRect(text, anchorX - horizontalGap, anchorY - 8, fontSize),
    estimateTextRect(text, anchorX - horizontalGap, anchorY - verticalGap, fontSize),
    estimateTextRect(text, anchorX - horizontalGap, anchorY + verticalGap, fontSize),
    estimateTextRect(text, anchorX - (symbolHalfWidth / 2), anchorY - sideGap, fontSize),
    estimateTextRect(text, anchorX - (symbolHalfWidth / 2), anchorY + sideGap, fontSize),
  ];
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

function chooseSymbolLabelRect({
  anchorX,
  anchorY,
  text,
  fontSize,
  symbolHalfWidth,
  symbolHalfHeight,
  obstacles = [],
  bounds = null,
}) {
  const candidates = getSymbolLabelCandidates(
    anchorX,
    anchorY,
    text,
    fontSize,
    symbolHalfWidth,
    symbolHalfHeight,
  );
  return candidates.find((candidate) => (
    isRectInsideBounds(candidate, bounds)
    && !obstacles.some((obstacle) => rectsIntersect(candidate, obstacle))
  )) || candidates[0];
}

function padRect(rect, padding = 0) {
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

function clampRectToBounds(rect, bounds) {
  if (!rect || !bounds) {
    return rect;
  }
  return {
    ...rect,
    x: Math.max(bounds.x, Math.min(rect.x, bounds.x + bounds.width - rect.width)),
    y: Math.max(bounds.y, Math.min(rect.y, bounds.y + bounds.height - rect.height)),
  };
}

function rectCenter(rect) {
  return {
    x: rect.x + (rect.width / 2),
    y: rect.y + (rect.height / 2),
  };
}

function translateRect(rect, dx, dy) {
  return {
    ...rect,
    x: rect.x + dx,
    y: rect.y + dy,
  };
}

function resolveRectObstacleOffset(rect, obstacle, threshold = 6) {
  if (!rect || !obstacle) {
    return { dx: 0, dy: 0 };
  }
  const expandedObstacle = padRect(obstacle, threshold);
  if (!rectsIntersect(rect, expandedObstacle)) {
    return { dx: 0, dy: 0 };
  }
  const moveLeft = expandedObstacle.x - (rect.x + rect.width);
  const moveRight = (expandedObstacle.x + expandedObstacle.width) - rect.x;
  const moveUp = expandedObstacle.y - (rect.y + rect.height);
  const moveDown = (expandedObstacle.y + expandedObstacle.height) - rect.y;
  const candidates = [
    { dx: moveLeft, dy: 0, distance: Math.abs(moveLeft) },
    { dx: moveRight, dy: 0, distance: Math.abs(moveRight) },
    { dx: 0, dy: moveUp, distance: Math.abs(moveUp) },
    { dx: 0, dy: moveDown, distance: Math.abs(moveDown) },
  ].sort((left, right) => left.distance - right.distance);
  return candidates[0] || { dx: 0, dy: 0 };
}

function resolveRectAgainstObstacles(rect, obstacles = [], bounds = null, threshold = 6) {
  let nextRect = rect ? { ...rect } : rect;
  if (!nextRect) {
    return null;
  }
  for (let iteration = 0; iteration < 12; iteration += 1) {
    let moved = false;
    obstacles.filter(Boolean).forEach((obstacle) => {
      const { dx, dy } = resolveRectObstacleOffset(nextRect, obstacle, threshold);
      if (dx !== 0 || dy !== 0) {
        nextRect = translateRect(nextRect, dx, dy);
        nextRect = clampRectToBounds(nextRect, bounds);
        moved = true;
      }
    });
    if (!moved) {
      break;
    }
  }
  return clampRectToBounds(nextRect, bounds);
}

function getOpeningBounds(opening) {
  if (!opening) {
    return null;
  }
  const corners = getRotatedRectCorners(opening);
  return getBoundingBox(corners.map(({ x, y }) => [x, y]));
}

function getLabelRectFromOffset(anchorX, anchorY, text, fontSize, dx, dy) {
  if (dx === null || dx === undefined || dy === null || dy === undefined) {
    return null;
  }
  return estimateTextRect(text, anchorX + dx, anchorY + dy, fontSize);
}

function getSegmentOrientation(start, end) {
  if (!start || !end) {
    return null;
  }
  if (Math.abs(Number(end[0] || 0) - Number(start[0] || 0)) >= Math.abs(Number(end[1] || 0) - Number(start[1] || 0))) {
    return 'horizontal';
  }
  return 'vertical';
}

function normalizeOrthogonalPolyline(polyline) {
  const source = Array.isArray(polyline) ? polyline : [];
  if (!source.length) {
    return [];
  }
  const nextPoints = [[Number(source[0][0] || 0), Number(source[0][1] || 0)]];
  for (let index = 1; index < source.length; index += 1) {
    const target = [Number(source[index][0] || 0), Number(source[index][1] || 0)];
    const previous = nextPoints[nextPoints.length - 1];
    if (previous[0] !== target[0] && previous[1] !== target[1]) {
      const beforePrevious = nextPoints[nextPoints.length - 2];
      const preferredOrientation = beforePrevious ? getSegmentOrientation(beforePrevious, previous) : 'horizontal';
      const corner = preferredOrientation === 'vertical'
        ? [previous[0], target[1]]
        : [target[0], previous[1]];
      if (corner[0] !== previous[0] || corner[1] !== previous[1]) {
        nextPoints.push(corner);
      }
    }
    if (target[0] !== nextPoints[nextPoints.length - 1][0] || target[1] !== nextPoints[nextPoints.length - 1][1]) {
      nextPoints.push(target);
    }
  }
  return nextPoints.filter((point, index) => (
    index === 0
    || point[0] !== nextPoints[index - 1][0]
    || point[1] !== nextPoints[index - 1][1]
  ));
}

function updateOrthogonalHandlePoint(polyline, pointIndex, targetPoint) {
  const points = normalizeOrthogonalPolyline(polyline).map((point) => [Number(point[0] || 0), Number(point[1] || 0)]);
  if (pointIndex <= 0 || pointIndex >= points.length - 1) {
    return points;
  }
  const previous = points[pointIndex - 1];
  const current = [...points[pointIndex]];
  const next = points[pointIndex + 1];
  const prevOrientation = getSegmentOrientation(previous, current);
  const nextOrientation = getSegmentOrientation(current, next);
  const targetX = Number(targetPoint?.x ?? current[0]);
  const targetY = Number(targetPoint?.y ?? current[1]);

  if (prevOrientation === 'horizontal' && nextOrientation === 'vertical') {
    current[0] = targetX;
    current[1] = targetY;
  } else if (prevOrientation === 'vertical' && nextOrientation === 'horizontal') {
    current[0] = targetX;
    current[1] = targetY;
  } else if (prevOrientation === 'horizontal' && nextOrientation === 'horizontal') {
    previous[1] = targetY;
    current[1] = targetY;
    next[1] = targetY;
  } else if (prevOrientation === 'vertical' && nextOrientation === 'vertical') {
    previous[0] = targetX;
    current[0] = targetX;
    next[0] = targetX;
  } else {
    current[0] = targetX;
    current[1] = targetY;
  }

  points[pointIndex] = current;
  points[pointIndex - 1] = previous;
  points[pointIndex + 1] = next;
  return normalizeOrthogonalPolyline(points);
}

function insertOrthogonalDogleg(polyline, insertIndex, targetPoint) {
  const points = normalizeOrthogonalPolyline(polyline).map((point) => [Number(point[0] || 0), Number(point[1] || 0)]);
  if (insertIndex <= 0 || insertIndex >= points.length) {
    return points;
  }
  const start = points[insertIndex - 1];
  const end = points[insertIndex];
  const orientation = getSegmentOrientation(start, end);
  const targetX = Number(targetPoint?.x ?? ((start[0] + end[0]) / 2));
  const targetY = Number(targetPoint?.y ?? ((start[1] + end[1]) / 2));
  const dogleg = orientation === 'vertical'
    ? [
      [start[0], targetY],
      [targetX, targetY],
      [targetX, end[1]],
    ]
    : [
      [targetX, start[1]],
      [targetX, targetY],
      [end[0], targetY],
    ];
  points.splice(insertIndex, 0, ...dogleg);
  return normalizeOrthogonalPolyline(points);
}

function translateInstrumentRouteStart(polyline, fromPoint, toPoint) {
  const points = normalizeOrthogonalPolyline(polyline).map((point) => [Number(point[0] || 0), Number(point[1] || 0)]);
  if (!points.length) {
    return points;
  }
  const nextPoints = points.map((point) => [...point]);
  nextPoints[0] = [Number(toPoint?.x || 0), Number(toPoint?.y || 0)];
  if (nextPoints.length === 1) {
    return nextPoints;
  }
  const nextPoint = [...nextPoints[1]];
  const orientation = getSegmentOrientation(points[0], points[1]) || getSegmentOrientation(fromPoint, toPoint) || 'horizontal';
  if (orientation === 'horizontal') {
    nextPoint[1] = Number(toPoint?.y || 0);
  } else {
    nextPoint[0] = Number(toPoint?.x || 0);
  }
  nextPoints[1] = nextPoint;
  return normalizeOrthogonalPolyline(nextPoints);
}

function getRotatedBounds(rect) {
  if (!rect) {
    return null;
  }
  const corners = getRotatedRectCorners(rect);
  return getBoundingBox(corners.map(({ x, y }) => [x, y]));
}

function pointInPolygon(point, polygon) {
  if (!polygon || polygon.length < 3) {
    return false;
  }
  const [x, y] = point;
  let inside = false;
  let previous = polygon[polygon.length - 1];
  for (const current of polygon) {
    const [x1, y1] = previous;
    const [x2, y2] = current;
    const onSegment = Math.abs((x - x1) * (y2 - y1) - (y - y1) * (x2 - x1)) < 1e-4
      && ((x - x1) * (x - x2) + (y - y1) * (y - y2)) <= 1e-4;
    if (onSegment) {
      return true;
    }
    const intersects = ((y1 > y) !== (y2 > y))
      && (x < (((x2 - x1) * (y - y1)) / ((y2 - y1) || 1e-9)) + x1);
    if (intersects) {
      inside = !inside;
    }
    previous = current;
  }
  return inside;
}

function getRoomMetadataForPoint(point, rooms, scaleFactor) {
  const room = rooms.find((item) => item.boundary_points?.length && pointInPolygon([point.x, point.y], item.boundary_points)) || null;
  if (!room?.boundary_points?.length) {
    return { room: null, roomId: null, offsetLeftM: null, offsetTopM: null };
  }
  const bounds = getBoundingBox(room.boundary_points);
  return {
    room,
    roomId: room.id,
    offsetLeftM: pxToMeters(point.x - bounds.x, scaleFactor),
    offsetTopM: pxToMeters(point.y - bounds.y, scaleFactor),
  };
}

function createFireAlarmDraftId() {
  return `temp_fire_alarm_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

function getFireAlarmDisplayLabel(deviceType) {
  return deviceType === 'manual_call_point' ? 'Ручной извещатель' : 'Дымовой датчик';
}

function getFireAlarmShortTypeLabel(deviceType) {
  return deviceType === 'manual_call_point' ? 'Ручной' : 'Дымовой';
}

function getFireAlarmCodePrefix(deviceType) {
  return deviceType === 'manual_call_point' ? 'BTM' : 'BTH';
}

function getFireAlarmDisplayCode(alarm, floorNumber, fallbackNumber = 1, overrides = {}) {
  const planFloor = floorNumber !== null && floorNumber !== undefined ? String(floorNumber) : '1';
  const loop = String(overrides.zone ?? alarm?.zone ?? '1').trim() || '1';
  const address = String(overrides.address ?? alarm?.address ?? fallbackNumber).trim() || String(fallbackNumber);
  return `${planFloor}${getFireAlarmCodePrefix(alarm?.device_type)}${loop}.${address}`;
}

function getFireAlarmRoomCoordinates(alarm, rooms, scaleFactor) {
  if (!alarm?.room_id) {
    return { x: null, y: null };
  }
  const room = rooms.find((item) => item.id === alarm.room_id);
  if (!room?.boundary_points?.length) {
    return { x: alarm.offset_left_m ?? null, y: null };
  }
  const bounds = getBoundingBox(room.boundary_points);
  const roomHeightM = pxToMeters(bounds.height, scaleFactor);
  const offsetLeft = alarm.offset_left_m ?? null;
  const offsetTop = alarm.offset_top_m ?? null;
  return {
    x: offsetLeft,
    y: roomHeightM !== null && roomHeightM !== undefined && offsetTop !== null && offsetTop !== undefined
      ? Math.max(0, roomHeightM - offsetTop)
      : null,
  };
}

function roomContainsStair(room, stairs) {
  if (!room?.boundary_points?.length || !stairs?.length) {
    return false;
  }
  return stairs.some((stair) => {
    const centerX = stair.x + (stair.width || 0) / 2;
    const centerY = stair.y + (stair.height || 0) / 2;
    return pointInPolygon([centerX, centerY], room.boundary_points);
  });
}

function FireAlarmSymbol({ x, y, deviceType, isSelected, isHovered, onClick, ...rest }) {
  return (
    <FireAlarmSymbolPrimitive
      x={x}
      y={y}
      deviceType={deviceType}
      isSelected={isSelected}
      isHovered={isHovered}
      onClick={onClick}
      {...rest}
    />
  );
}

function SignalInstrumentSymbol({ x, y, instrumentType, isSelected, isHovered, onClick, ...rest }) {
  return (
    <SignalInstrumentSymbolPrimitive
      x={x}
      y={y}
      instrumentType={instrumentType}
      isSelected={isSelected}
      isHovered={isHovered}
      onClick={onClick}
      {...rest}
    />
  );
}

function getPolygonBounds(flatPoints) {
  if (!flatPoints?.length) {
    return null;
  }
  let minX = Number.POSITIVE_INFINITY;
  let minY = Number.POSITIVE_INFINITY;
  let maxX = Number.NEGATIVE_INFINITY;
  let maxY = Number.NEGATIVE_INFINITY;
  for (let index = 0; index < flatPoints.length; index += 2) {
    const x = flatPoints[index];
    const y = flatPoints[index + 1];
    minX = Math.min(minX, x);
    minY = Math.min(minY, y);
    maxX = Math.max(maxX, x);
    maxY = Math.max(maxY, y);
  }
  return {
    x: minX,
    y: minY,
    width: maxX - minX,
    height: maxY - minY,
  };
}

function buildZkspcHatchLines(bounds, spacing) {
  if (!bounds || bounds.width <= 0 || bounds.height <= 0) {
    return [];
  }
  const safeSpacing = Math.max(10, Number(spacing || 20));
  const lines = [];
  const startOffset = -bounds.height;
  const endOffset = bounds.width + bounds.height;
  for (let offset = startOffset; offset <= endOffset; offset += safeSpacing) {
    lines.push([
      bounds.x + offset,
      bounds.y,
      bounds.x + offset + bounds.height,
      bounds.y + bounds.height,
    ]);
  }
  return lines;
}

function getRoomDisplayCenter(room) {
  if (room?.center_x !== null && room?.center_x !== undefined && room?.center_y !== null && room?.center_y !== undefined) {
    return { x: room.center_x, y: room.center_y };
  }
  const bounds = getBoundingBox(room?.boundary_points || []);
  if (!bounds) {
    return null;
  }
  return {
    x: bounds.x + (bounds.width / 2),
    y: bounds.y + (bounds.height / 2),
  };
}

const HOVER_PANEL_SIZE = { width: 360, height: 280 };
const HOVER_PANEL_SECTION_STYLE = { display: 'flex', flexDirection: 'column', gap: '10px' };
const HOVER_PANEL_FIELD_ROW_STYLE = { display: 'flex', alignItems: 'center', gap: '10px' };
const HOVER_PANEL_LABEL_STYLE = {
  flex: '0 0 118px',
  fontSize: '12px',
  fontWeight: 600,
  color: '#4f4131',
};
const HOVER_PANEL_INPUT_STYLE = {
  flex: '1 1 auto',
  minWidth: 0,
  height: '32px',
  padding: '0 10px',
  borderRadius: '10px',
  border: '1px solid #d9d2c8',
  backgroundColor: '#fffdfa',
  color: '#1f2933',
  fontSize: '13px',
  boxSizing: 'border-box',
};
const HOVER_PANEL_INFO_ROW_STYLE = {
  display: 'flex',
  justifyContent: 'space-between',
  gap: '10px',
  fontSize: '12px',
  color: '#6c5f52',
};
const INTERACTIVE_TYPES_BY_STEP = {
  original: [],
  walls: ['wall', 'new-wall', 'stair', 'new-stair'],
  openings: ['door', 'window', 'new-door', 'new-window'],
  rooms: ['room'],
  zkspc: ['room'],
  fire_alarms: ['fire-alarm', 'new-fire-alarm'],
  devices_cables: ['signal-instrument', 'cable-route', 'fire-alarm', 'new-fire-alarm'],
};
const DEFAULT_WALL_THICKNESS_MM = 200;
const DEFAULT_WALL_THICKNESS_M = '0.20';
const WALL_PRESET_THICKNESS_DEFAULTS = {
  outer: 300,
  inner: 160,
  manual: 200,
};
const WALL_ALIGNMENT_OPTIONS = [
  { value: 'center', label: 'По центру' },
  { value: 'left', label: 'Слева от оси' },
  { value: 'right', label: 'Справа от оси' },
];

function FloorPlanEditor() {
  const { floorPlanId } = useParams();
  const navigate = useNavigate();
  const WALL_COLOR = '#39FF14';
  const stageRef = useRef(null);
  const stageContainerRef = useRef(null);
  const dragStartRef = useRef({});
  const [floorPlan, setFloorPlan] = useState(null);
  const [walls, setWalls] = useState([]);
  const [stairs, setStairs] = useState([]);
  const [doors, setDoors] = useState([]);
  const [windows, setWindows] = useState([]);
  const [rooms, setRooms] = useState([]);
  const [dimensions, setDimensions] = useState([]);
  const [fireAlarms, setFireAlarms] = useState([]);
  const [zkspcZones, setZkspcZones] = useState([]);
  const [zkspcDraftZones, setZkspcDraftZones] = useState([]);
  const [signalInstruments, setSignalInstruments] = useState([]);
  const [cableRoutes, setCableRoutes] = useState([]);
  const [activeSignalSystemType, setActiveSignalSystemType] = useState('non_addressable');
  const [newFireAlarmsBySystem, setNewFireAlarmsBySystem] = useState({
    non_addressable: [],
    addressable: [],
  });
  const [fireAlarmWarningsBySystem, setFireAlarmWarningsBySystem] = useState({
    non_addressable: [],
    addressable: [],
  });
  const [fireAlarmActionLoading, setFireAlarmActionLoading] = useState(false);
  const [signalBranchActionLoading, setSignalBranchActionLoading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [selectedTool, setSelectedTool] = useState('select');
  const [selectedElement, setSelectedElement] = useState(null);
  const [hoveredElement, setHoveredElement] = useState(null);
  const [, setHasUnsavedChanges] = useState(false);
  const [deletedElements, setDeletedElements] = useState([]);
  const [newWalls, setNewWalls] = useState([]);
  const [newStairs, setNewStairs] = useState([]);
  const [newDoors, setNewDoors] = useState([]);
  const [newWindows, setNewWindows] = useState([]);
  const [modifiedWalls, setModifiedWalls] = useState({});
  const [modifiedElements, setModifiedElements] = useState({});
  const [drawingWall, setDrawingWall] = useState(null);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const [editingWall, setEditingWall] = useState(null);
  const [shiftPressed, setShiftPressed] = useState(false);
  const [undoHistory, setUndoHistory] = useState([]);
  const [recognition, setRecognition] = useState(null);
  const [recognitionMeta, setRecognitionMeta] = useState(null);
  // eslint-disable-next-line no-unused-vars
  const [recognizing, setRecognizing] = useState(false);
  const [recognitionFeedbackSubmitting, setRecognitionFeedbackSubmitting] = useState(false);
  const [recognitionFeedbackStatus, setRecognitionFeedbackStatus] = useState('idle');
  const [recognitionFeedbackError, setRecognitionFeedbackError] = useState('');
  const [debugImages, setDebugImages] = useState([]);
  const [selectedDebugImagePath, setSelectedDebugImagePath] = useState(null);
  const [showDebugPanel, setShowDebugPanel] = useState(false);
  const [stageContainerNode, setStageContainerNode] = useState(null);
  const [containerSize, setContainerSize] = useState({ width: 0, height: 0 });
  const [viewport, setViewport] = useState({
    zoom: 1,
    pan: { x: 0, y: 0 },
    rotationQuarterTurns: 0,
  });
  const [renderedImageSize, setRenderedImageSize] = useState(null);
  const [isStagePanning, setIsStagePanning] = useState(false);
  const stagePanStartRef = useRef(null);
  const stagePanMovedRef = useRef(false);
  const [roomNameDraft, setRoomNameDraft] = useState('');
  const [roomNameSaving, setRoomNameSaving] = useState(false);
  const [pipelineState, setPipelineState] = useState(null);
  const [pipelineLoading, setPipelineLoading] = useState(false);
  const [pipelineActionLoading, setPipelineActionLoading] = useState(false);
  const [missingWallIds, setMissingWallIds] = useState([]);
  const [showWallValidationAlert, setShowWallValidationAlert] = useState(false);
  const [hoverPanel, setHoverPanel] = useState(null);
  const hoverLeaveTimeoutRef = useRef(null);
  const hoverPanelMouseInsideRef = useRef(false);
  const [hoverPanelMouseInside, setHoverPanelMouseInside] = useState(false);
  const [wallLengthDraft, setWallLengthDraft] = useState('');
  const [wallThicknessDraft, setWallThicknessDraft] = useState('');
  const [wallAlignmentDraft, setWallAlignmentDraft] = useState('center');
  const [wallDraftPreset, setWallDraftPreset] = useState('manual');
  const [newWallAlignment, setNewWallAlignment] = useState('center');
  const [newWallThicknessDraft, setNewWallThicknessDraft] = useState(DEFAULT_WALL_THICKNESS_M);
  const [wallAutoSnapEnabled, setWallAutoSnapEnabled] = useState(true);
  const [openingSizeDraft, setOpeningSizeDraft] = useState({ width: '', height: '', wallId: '' });
  const [stairDraft, setStairDraft] = useState({ width: '', height: '' });
  const [roomDraft, setRoomDraft] = useState({ name: '', type: 'базовое', length: '', width: '' });
  const [fireAlarmDraft, setFireAlarmDraft] = useState({ zone: '', address: '' });
  const [signalInstrumentDraft, setSignalInstrumentDraft] = useState({ name: '', instrumentType: 'control_panel' });
  const [mergeInstrumentId, setMergeInstrumentId] = useState(null);
  const [viewStep, setViewStep] = useState(null);
  const [planMetaDraft, setPlanMetaDraft] = useState({ name: '', floor_number: '', ceiling_height_m: '' });
  const [savingPlanMeta, setSavingPlanMeta] = useState(false);
  const [selectedElements, setSelectedElements] = useState([]);
  const [selectedZkspcRooms, setSelectedZkspcRooms] = useState([]);
  const [selectionRect, setSelectionRect] = useState(null);
  const [isSelecting, setIsSelecting] = useState(false);
  const [isRoomZoneDrawing, setIsRoomZoneDrawing] = useState(false);
  const [roomZoneRect, setRoomZoneRect] = useState(null);
  const [placementDraft, setPlacementDraft] = useState(null);
  const [activeDrag, setActiveDrag] = useState(null);
  const [activeCableHandle, setActiveCableHandle] = useState(null);
  const [calibrationDraft, setCalibrationDraft] = useState({ start: null, end: null, distance_m: '' });
  const setStageContainerNodeRef = useCallback((node) => {
    stageContainerRef.current = node;
    setStageContainerNode((prev) => (prev === node ? prev : node));
  }, []);

  const newFireAlarms = useMemo(
    () => newFireAlarmsBySystem[normalizeSignalSystemType(activeSignalSystemType)] || [],
    [newFireAlarmsBySystem, activeSignalSystemType],
  );
  const setNewFireAlarms = useCallback((updater) => {
    const systemType = normalizeSignalSystemType(activeSignalSystemType);
    setNewFireAlarmsBySystem((prev) => ({
      ...prev,
      [systemType]: typeof updater === 'function' ? updater(prev[systemType] || []) : updater,
    }));
  }, [activeSignalSystemType]);
  const fireAlarmWarnings = useMemo(
    () => fireAlarmWarningsBySystem[normalizeSignalSystemType(activeSignalSystemType)] || [],
    [fireAlarmWarningsBySystem, activeSignalSystemType],
  );
  const setFireAlarmWarnings = useCallback((updater) => {
    const systemType = normalizeSignalSystemType(activeSignalSystemType);
    setFireAlarmWarningsBySystem((prev) => ({
      ...prev,
      [systemType]: typeof updater === 'function' ? updater(prev[systemType] || []) : updater,
    }));
  }, [activeSignalSystemType]);
  const currentSignalSystem = normalizeSignalSystemType(activeSignalSystemType || floorPlan?.active_signal_system_type);
  const currentWallDraftThicknessMm = useMemo(() => {
    const parsedValue = Number(newWallThicknessDraft);
    return parsedValue > 0 ? parsedValue * 1000 : DEFAULT_WALL_THICKNESS_MM;
  }, [newWallThicknessDraft]);
  const flipWallAlignment = useCallback(() => 'center', []);
  const currentZkspcZones = zkspcDraftZones.length ? zkspcDraftZones : zkspcZones;
  const roomZoneMap = useMemo(() => buildRoomZoneMap(currentZkspcZones), [currentZkspcZones]);
  const branchFireAlarms = useMemo(
    () => getBranchFireAlarms(fireAlarms, currentSignalSystem),
    [fireAlarms, currentSignalSystem],
  );
  const updateLocalSignalBranchState = useSignalBranchState(setPipelineState);

  // Zoom constants
  const MIN_ZOOM = 0.1;
  const MAX_ZOOM = 5.0;
  const ZOOM_STEP = 0.1;
  const userZoom = viewport.zoom;
  const stagePanOffset = viewport.pan;
  const imageUrl = floorPlan?.original_image_path 
    ? `http://localhost:8000/${floorPlan.original_image_path.replace(/\\/g, '/')}`
    : null;
  const selectedDebugImage = debugImages.find((debugImg) => debugImg.path === selectedDebugImagePath) || null;
  const displayedImageUrl = selectedDebugImage
    ? `http://localhost:8000/${selectedDebugImage.path.replace(/\\/g, '/')}`
    : imageUrl;
  const effectiveImageWidth = Math.max(
    1,
    Number(
      (renderedImageSize?.url === displayedImageUrl ? renderedImageSize?.width : null)
      || floorPlan?.image_width
      || 800,
    ),
  );
  const effectiveImageHeight = Math.max(
    1,
    Number(
      (renderedImageSize?.url === displayedImageUrl ? renderedImageSize?.height : null)
      || floorPlan?.image_height
      || 600,
    ),
  );
  const clampViewportState = useCallback((nextState) => {
    const normalizedZoom = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, Number(nextState?.zoom ?? 1) || 1));
    const normalizedRotationQuarterTurns = normalizeQuarterTurns(nextState?.rotationQuarterTurns || 0);
    const normalizedPan = clampViewportPan(nextState?.pan || { x: 0, y: 0 }, {
      containerWidth: containerSize.width,
      containerHeight: containerSize.height,
      imageWidth: effectiveImageWidth,
      imageHeight: effectiveImageHeight,
      zoom: normalizedZoom,
      rotationQuarterTurns: normalizedRotationQuarterTurns,
    });
    return {
      zoom: normalizedZoom,
      pan: normalizedPan,
      rotationQuarterTurns: normalizedRotationQuarterTurns,
    };
  }, [
    containerSize.width,
    containerSize.height,
    effectiveImageWidth,
    effectiveImageHeight,
    MAX_ZOOM,
    MIN_ZOOM,
  ]);
  const updateViewport = useCallback((updater) => {
    setViewport((prev) => {
      const candidate = typeof updater === 'function'
        ? updater(prev)
        : { ...prev, ...updater };
      const next = clampViewportState({
        zoom: candidate?.zoom ?? prev.zoom,
        pan: candidate?.pan ?? prev.pan,
        rotationQuarterTurns: candidate?.rotationQuarterTurns ?? prev.rotationQuarterTurns,
      });
      return areViewportStatesEqual(prev, next) ? prev : next;
    });
  }, [clampViewportState]);
  const viewTransform = useMemo(() => createViewportTransform({
    containerWidth: containerSize.width,
    containerHeight: containerSize.height,
    imageWidth: effectiveImageWidth,
    imageHeight: effectiveImageHeight,
    zoom: viewport.zoom,
    pan: viewport.pan,
    rotationQuarterTurns: viewport.rotationQuarterTurns,
  }), [
    containerSize.width,
    containerSize.height,
    effectiveImageWidth,
    effectiveImageHeight,
    viewport.zoom,
    viewport.pan.x,
    viewport.pan.y,
    viewport.rotationQuarterTurns,
  ]);
  // Zoom functions
  const handleZoomIn = useCallback(() => {
    updateViewport((prev) => ({
      ...prev,
      zoom: Math.min(prev.zoom + ZOOM_STEP, MAX_ZOOM),
    }));
  }, [MAX_ZOOM, ZOOM_STEP, updateViewport]);

  const handleZoomOut = useCallback(() => {
    updateViewport((prev) => ({
      ...prev,
      zoom: Math.max(prev.zoom - ZOOM_STEP, MIN_ZOOM),
    }));
  }, [MIN_ZOOM, ZOOM_STEP, updateViewport]);

  const handleZoomReset = useCallback(() => {
    updateViewport((prev) => ({
      ...prev,
      zoom: 1,
      pan: { x: 0, y: 0 },
    }));
  }, [updateViewport]);

  const handleRotateViewport = useCallback(() => {
    updateViewport((prev) => ({
      ...prev,
      rotationQuarterTurns: normalizeQuarterTurns(prev.rotationQuarterTurns + 1),
    }));
  }, [updateViewport]);

  // Функция скачивания изображения
  const downloadImage = async (imageUrl, filename) => {
    try {
      const response = await fetch(imageUrl);
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Error downloading image:', error);
    }
  };

  const applyFloorPlanData = useCallback((data) => {
    setFloorPlan(data);
    setWalls(data.walls || []);
    setStairs(data.stairs || []);
    setDoors(data.doors || []);
    setWindows(data.windows || []);
    setRooms(data.rooms || []);
    setDimensions(data.dimensions || []);
    setFireAlarms(data.fire_alarms || []);
    setZkspcZones(data.zkspc_zones || []);
    setZkspcDraftZones(data.zkspc_zones || []);
    setSignalInstruments(data.signal_instruments || []);
    setCableRoutes(data.cable_routes || []);
    setActiveSignalSystemType(normalizeSignalSystemType(data.active_signal_system_type));
  }, []);

  const fetchPipelineState = useCallback(async () => {
    try {
      setPipelineLoading(true);
      const state = await pipelineApi.getState(floorPlanId);
      setPipelineState(state);
    } catch (error) {
      console.error('Error fetching pipeline state:', error);
    } finally {
      setPipelineLoading(false);
    }
  }, [floorPlanId]);

  const fetchFloorPlan = useCallback(async () => {
    try {
      const data = await floorPlansApi.get(floorPlanId, true);
      applyFloorPlanData(data);
      const state = await pipelineApi.getState(floorPlanId);
      setPipelineState(state);
      try {
        const recognitionData = await recognitionApi.get(floorPlanId);
        setRecognitionMeta(recognitionData);
        setRecognition(recognitionData?.recognition_result || null);
      } catch (recognitionError) {
        console.error('Error fetching recognition state:', recognitionError);
        setRecognitionMeta(null);
        setRecognition(null);
      }
      setLoading(false);
    } catch (error) {
      console.error('Error fetching floor plan:', error);
      setLoading(false);
    }
  }, [applyFloorPlanData, floorPlanId]);

  useEffect(() => {
    fetchFloorPlan();
  }, [fetchFloorPlan]);

  useEffect(() => {
    if (!floorPlan) {
      return;
    }
    setPlanMetaDraft({
      name: floorPlan.name || '',
      floor_number: floorPlan.floor_number !== null && floorPlan.floor_number !== undefined
        ? String(floorPlan.floor_number)
        : '',
      ceiling_height_m: floorPlan.ceiling_height_mm !== null && floorPlan.ceiling_height_mm !== undefined
        ? String((Number(floorPlan.ceiling_height_mm) / 1000).toFixed(2))
        : '',
    });
  }, [floorPlan]);

  useEffect(() => {
    if (viewStep || !pipelineState) {
      return;
    }
    if (pipelineState?.steps?.zkspc?.status === 'validated') {
      const normalizedSystem = normalizeSignalSystemType(
        pipelineState.active_signal_system_type || activeSignalSystemType || floorPlan?.active_signal_system_type,
      );
      setViewStep(pipelineState?.branches?.[normalizedSystem]?.active_step || 'fire_alarms');
    } else if (pipelineState?.steps?.rooms?.status === 'validated') {
      setViewStep('zkspc');
    } else if (pipelineState?.active_step) {
      setViewStep(pipelineState.active_step);
    } else {
      setViewStep('original');
    }
  }, [pipelineState, viewStep, activeSignalSystemType, floorPlan?.active_signal_system_type]);

  useEffect(() => {
    if (selectedElement?.type === 'room' && selectedElement?.data) {
      setRoomNameDraft(selectedElement.data.name || '');
    } else {
      setRoomNameDraft('');
    }
  }, [selectedElement]);

  useEffect(() => {
    setPlacementDraft(null);
  }, [selectedTool, viewStep]);

  const buildEditableWall = useCallback((wall) => {
    if (!wall) {
      return null;
    }
    const fallbackLength = getDerivedWallLengthMeters(wall, floorPlan?.scale_factor);
    return {
      ...wall,
      thickness: wall.thickness ?? DEFAULT_WALL_THICKNESS_MM,
      alignment: 'center',
      length_m: wall.length_m ?? fallbackLength,
      length_source: wall.length_source || 'derived',
    };
  }, [floorPlan?.scale_factor]);

  const activeWallGeometries = useMemo(() => (
    walls
      .filter((wall) => !deletedElements.some((del) => del.type === 'walls' && del.id === wall.id))
      .map((wall) => {
        const modifications = modifiedWalls[wall.id] || {};
        return buildEditableWall({
          ...wall,
          x1: modifications.x1 !== undefined ? modifications.x1 : wall.x1,
          y1: modifications.y1 !== undefined ? modifications.y1 : wall.y1,
          x2: modifications.x2 !== undefined ? modifications.x2 : wall.x2,
          y2: modifications.y2 !== undefined ? modifications.y2 : wall.y2,
          thickness: modifications.thickness !== undefined ? modifications.thickness : wall.thickness,
          length_m: modifications.length_m !== undefined ? modifications.length_m : wall.length_m,
          length_source: modifications.length_source !== undefined ? modifications.length_source : wall.length_source,
        });
      })
      .filter(Boolean)
  ), [walls, deletedElements, modifiedWalls, buildEditableWall]);

  const getOpeningCurrentGeometry = useCallback((kind, entityId, fallbackEntity = null) => {
    const collection = kind === 'doors'
      ? doors
      : kind === 'windows'
        ? windows
        : kind === 'new-doors'
          ? newDoors
          : newWindows;
    const entity = fallbackEntity || collection.find((item) => item.id === entityId);
    if (!entity) {
      return null;
    }
    const modifications = kind === 'doors' || kind === 'windows'
      ? (modifiedElements[`${kind}-${entity.id}`] || {})
      : {};
    return {
      ...entity,
      x: modifications.x !== undefined ? modifications.x : entity.x,
      y: modifications.y !== undefined ? modifications.y : entity.y,
      width: modifications.width !== undefined ? modifications.width : entity.width,
      height: modifications.height !== undefined ? modifications.height : entity.height,
      rotation_deg: modifications.rotation_deg !== undefined ? modifications.rotation_deg : entity.rotation_deg,
      wall_id: modifications.wall_id !== undefined ? modifications.wall_id : entity.wall_id,
    };
  }, [doors, windows, newDoors, newWindows, modifiedElements]);

  const getStairCurrentGeometry = useCallback((stairId, fallbackEntity = null) => {
    const entity = fallbackEntity || stairs.find((item) => item.id === stairId);
    if (!entity) {
      return null;
    }
    const modifications = modifiedElements[`stairs-${entity.id}`] || {};
    return {
      ...entity,
      x: modifications.x !== undefined ? modifications.x : entity.x,
      y: modifications.y !== undefined ? modifications.y : entity.y,
      width: modifications.width !== undefined ? modifications.width : entity.width,
      height: modifications.height !== undefined ? modifications.height : entity.height,
      rotation_deg: modifications.rotation_deg !== undefined ? modifications.rotation_deg : entity.rotation_deg,
      step_count: modifications.step_count !== undefined ? modifications.step_count : entity.step_count,
      step_axis: modifications.step_axis !== undefined ? modifications.step_axis : entity.step_axis,
    };
  }, [stairs, modifiedElements]);

  const getFireAlarmCurrentGeometry = useCallback((kind, alarmId, fallbackEntity = null) => {
    const collection = kind === 'fire-alarms' ? fireAlarms : newFireAlarms;
    const entity = fallbackEntity || collection.find((item) => item.id === alarmId);
    if (!entity) {
      return null;
    }
    const modifications = kind === 'fire-alarms'
      ? (modifiedElements[`fire-alarms-${entity.id}`] || {})
      : {};
    const x = modifications.x !== undefined ? modifications.x : entity.x;
    const y = modifications.y !== undefined ? modifications.y : entity.y;
    const metadata = getRoomMetadataForPoint({ x, y }, rooms, floorPlan?.scale_factor);
    return {
      ...entity,
      ...modifications,
      x: placement.x,
      y: placement.y,
      label_dx: modifications.label_dx !== undefined ? modifications.label_dx : entity.label_dx,
      label_dy: modifications.label_dy !== undefined ? modifications.label_dy : entity.label_dy,
      room_id: metadata.roomId ?? entity.room_id ?? null,
      offset_left_m: metadata.offsetLeftM ?? entity.offset_left_m ?? null,
      offset_top_m: metadata.offsetTopM ?? entity.offset_top_m ?? null,
      room_name: metadata.room?.name || null,
    };
  }, [fireAlarms, newFireAlarms, modifiedElements, rooms, floorPlan?.scale_factor]);

  const placementBounds = useMemo(() => ({
    x: 0,
    y: 0,
    width: effectiveImageWidth,
    height: effectiveImageHeight,
  }), [effectiveImageHeight, effectiveImageWidth]);

  const collectDevicePlacementObstacles = useCallback((exclude = {}) => {
    const {
      excludeFireAlarmId = null,
      excludeInstrumentId = null,
    } = exclude;
    const obstacles = [];
    activeWallGeometries.forEach((wall) => {
      const bounds = getWallBounds(wall, floorPlan?.scale_factor);
      if (bounds) {
        obstacles.push(bounds);
      }
    });
    [...doors, ...newDoors].forEach((door) => {
      const current = getOpeningCurrentGeometry(door.id?.toString?.().startsWith('temp_') ? 'new-doors' : 'doors', door.id, door);
      const bounds = getOpeningBounds(current || door);
      if (bounds) {
        obstacles.push(bounds);
      }
    });
    [...windows, ...newWindows].forEach((windowItem) => {
      const current = getOpeningCurrentGeometry(windowItem.id?.toString?.().startsWith('temp_') ? 'new-windows' : 'windows', windowItem.id, windowItem);
      const bounds = getOpeningBounds(current || windowItem);
      if (bounds) {
        obstacles.push(bounds);
      }
    });
    branchFireAlarms.forEach((alarm) => {
      if (alarm.id === excludeFireAlarmId) {
        return;
      }
      const current = getFireAlarmCurrentGeometry('fire-alarms', alarm.id, alarm);
      const bounds = getFireAlarmBounds(current);
      if (bounds) {
        obstacles.push(bounds);
      }
    });
    newFireAlarms.forEach((alarm) => {
      if (alarm.id === excludeFireAlarmId) {
        return;
      }
      const current = getFireAlarmCurrentGeometry('new-fire-alarms', alarm.id, alarm);
      const bounds = getFireAlarmBounds(current);
      if (bounds) {
        obstacles.push(bounds);
      }
    });
    signalInstruments
      .filter((instrument) => normalizeSignalSystemType(instrument.system_type) === currentSignalSystem)
      .forEach((instrument) => {
        if (instrument.id === excludeInstrumentId) {
          return;
        }
        const bounds = getSignalInstrumentBounds(instrument);
        if (bounds) {
          obstacles.push(bounds);
        }
      });
    return obstacles;
  }, [
    activeWallGeometries,
    branchFireAlarms,
    currentSignalSystem,
    doors,
    floorPlan?.scale_factor,
    getFireAlarmCurrentGeometry,
    getOpeningCurrentGeometry,
    newDoors,
    newFireAlarms,
    newWindows,
    signalInstruments,
    windows,
  ]);

  const resolveDevicePlacementPoint = useCallback((point, getBoundsForCenter, exclude = {}) => {
    const bounds = getBoundsForCenter(point);
    const nextBounds = resolveRectAgainstObstacles(
      bounds,
      collectDevicePlacementObstacles(exclude),
      placementBounds,
      8,
    );
    return rectCenter(nextBounds || bounds);
  }, [collectDevicePlacementObstacles, placementBounds]);

  const resolveManualCallPointPlacement = useCallback((point) => {
    const candidateDoors = [...doors, ...newDoors]
      .map((door) => (
        door.id?.toString?.().startsWith('temp_')
          ? getOpeningCurrentGeometry('new-doors', door.id, door)
          : getOpeningCurrentGeometry('doors', door.id, door)
      ))
      .filter(Boolean)
      .filter((door) => door.wall_id);
    if (!candidateDoors.length) {
      return point;
    }
    const nearestDoor = [...candidateDoors].sort((left, right) => {
      const leftCenterX = left.x + (left.width / 2);
      const leftCenterY = left.y + (left.height / 2);
      const rightCenterX = right.x + (right.width / 2);
      const rightCenterY = right.y + (right.height / 2);
      return Math.hypot(point.x - leftCenterX, point.y - leftCenterY) - Math.hypot(point.x - rightCenterX, point.y - rightCenterY);
    })[0];
    const wall = activeWallGeometries.find((item) => item.id === nearestDoor.wall_id);
    const axis = wall ? getWallAxisData(wall) : null;
    if (!wall || !axis) {
      return point;
    }
    const center = {
      x: nearestDoor.x + (nearestDoor.width / 2),
      y: nearestDoor.y + (nearestDoor.height / 2),
    };
    const centerProjection = projectPointToWall(center, wall);
    if (!centerProjection) {
      return point;
    }
    const scale = floorPlan?.scale_factor && floorPlan.scale_factor > 0 ? floorPlan.scale_factor : 1;
    const placementOffsetPx = Math.max(4, 300 / scale);
    const tangentClearancePx = Math.max(8, 180 / scale);
    const halfSpan = Math.max(6, Number(nearestDoor.width || 0) / 2);
    const doorStart = Math.max(0, centerProjection.along - halfSpan);
    const doorEnd = Math.min(axis.length, centerProjection.along + halfSpan);
    let leftLimit = 0;
    let rightLimit = axis.length;
    candidateDoors
      .filter((door) => door.wall_id === nearestDoor.wall_id && door.id !== nearestDoor.id)
      .forEach((door) => {
        const doorCenter = {
          x: door.x + (door.width / 2),
          y: door.y + (door.height / 2),
        };
        const projection = projectPointToWall(doorCenter, wall);
        if (!projection) {
          return;
        }
        const otherHalfSpan = Math.max(6, Number(door.width || 0) / 2);
        const otherStart = Math.max(0, projection.along - otherHalfSpan);
        const otherEnd = Math.min(axis.length, projection.along + otherHalfSpan);
        if (otherEnd <= doorStart && otherEnd > leftLimit) {
          leftLimit = otherEnd;
        }
        if (otherStart >= doorEnd && otherStart < rightLimit) {
          rightLimit = otherStart;
        }
      });
    const availableLeft = Math.max(0, doorStart - leftLimit);
    const availableRight = Math.max(0, rightLimit - doorEnd);
    const alongSign = availableRight >= availableLeft ? 1 : -1;
    const availableSpan = alongSign > 0 ? availableRight : availableLeft;
    const shiftAlongWall = halfSpan + Math.min(
      Math.max(0, availableSpan - 2),
      Math.max(tangentClearancePx, halfSpan + (tangentClearancePx * 0.35)),
    );
    const projected = Math.max(0, Math.min(axis.length, centerProjection.along + (alongSign * shiftAlongWall)));
    const sideDot = ((point.x - center.x) * axis.nx) + ((point.y - center.y) * axis.ny);
    const normalSign = sideDot >= 0 ? 1 : -1;
    return {
      x: axis.x1 + (axis.ux * projected) + (axis.nx * placementOffsetPx * normalSign),
      y: axis.y1 + (axis.uy * projected) + (axis.ny * placementOffsetPx * normalSign),
    };
  }, [activeWallGeometries, doors, floorPlan?.scale_factor, getOpeningCurrentGeometry, newDoors]);

  const resolveFireAlarmPlacement = useCallback((deviceType, point, exclude = {}) => {
    const basePoint = deviceType === 'manual_call_point'
      ? resolveManualCallPointPlacement(point)
      : point;
    return resolveDevicePlacementPoint(
      basePoint,
      (center) => getFireAlarmBounds({ x: center.x, y: center.y }),
      exclude,
    );
  }, [resolveDevicePlacementPoint, resolveManualCallPointPlacement]);

  const resolveInstrumentPlacement = useCallback((point, exclude = {}) => (
    resolveDevicePlacementPoint(
      point,
      (center) => getSignalInstrumentBounds({ ...exclude.instrument, x: center.x, y: center.y }),
      exclude,
    )
  ), [resolveDevicePlacementPoint]);

  const currentStairGeometries = useMemo(() => (
    [
      ...stairs
        .filter((stair) => !deletedElements.some((del) => del.type === 'stairs' && del.id === stair.id))
        .map((stair) => getStairCurrentGeometry(stair.id, stair)),
      ...newStairs,
    ].filter(Boolean)
  ), [stairs, deletedElements, getStairCurrentGeometry, newStairs]);

  const unserviceableRoomIds = useMemo(() => (
    new Set(
      rooms
        .filter((room) => !deletedElements.some((del) => del.type === 'rooms' && del.id === room.id))
        .filter((room) => roomContainsStair(room, currentStairGeometries))
        .map((room) => room.id)
    )
  ), [rooms, deletedElements, currentStairGeometries]);

  const getWallCurrentGeometry = useCallback((wallId) => {
    const wall = walls.find((item) => item.id === wallId);
    if (!wall) {
      return null;
    }
    const modifications = modifiedWalls[wallId] || {};
    return buildEditableWall({
      ...wall,
      x1: modifications.x1 !== undefined ? modifications.x1 : wall.x1,
      y1: modifications.y1 !== undefined ? modifications.y1 : wall.y1,
      x2: modifications.x2 !== undefined ? modifications.x2 : wall.x2,
      y2: modifications.y2 !== undefined ? modifications.y2 : wall.y2,
      thickness: modifications.thickness !== undefined ? modifications.thickness : wall.thickness,
      length_m: modifications.length_m !== undefined ? modifications.length_m : wall.length_m,
      length_source: modifications.length_source !== undefined ? modifications.length_source : wall.length_source,
    });
  }, [walls, modifiedWalls, buildEditableWall]);
  const draftingWalls = useMemo(() => (
    [
      ...activeWallGeometries,
      ...newWalls,
    ].map((wall) => buildEditableWall(wall)).filter(Boolean)
  ), [activeWallGeometries, newWalls, buildEditableWall]);
  const draftingWallMap = useMemo(() => (
    new Map(draftingWalls.map((wall) => [wall.id, wall]))
  ), [draftingWalls]);
  const visibleWallBoundarySegments = useMemo(() => (
    getVisibleWallBoundarySegments(draftingWalls, floorPlan?.scale_factor)
  ), [draftingWalls, floorPlan?.scale_factor]);
  const getWallOutline = useCallback((wallGeometry) => (
    getWallOutlineGeometry(buildEditableWall(wallGeometry), floorPlan?.scale_factor)
  ), [buildEditableWall, floorPlan?.scale_factor]);
  const getWorkingWallsSnapshot = useCallback(() => draftingWalls.map((wall) => buildEditableWall(wall)), [draftingWalls, buildEditableWall]);
  const persistWallWorkingSet = useCallback((workingWalls, options = {}) => {
    const {
      markUnsaved = true,
    } = options;
    const persistedMap = new Map(walls.map((wall) => [wall.id, wall]));
    const existingNewWallMap = new Map(newWalls.map((wall) => [wall.id, wall]));
    const nextModifiedWalls = {};
    const nextNewWalls = [];

    workingWalls.forEach((wall) => {
      const normalizedWall = buildEditableWall(wall);
      if (!normalizedWall) {
        return;
      }
      if (persistedMap.has(normalizedWall.id)) {
        const baseWall = persistedMap.get(normalizedWall.id);
        const nextPatch = {};
        const nextData = {
          x1: normalizedWall.x1,
          y1: normalizedWall.y1,
          x2: normalizedWall.x2,
          y2: normalizedWall.y2,
          thickness: normalizedWall.thickness,
          alignment: 'center',
          length_m: normalizedWall.length_m,
          length_source: normalizedWall.length_source,
        };
        Object.entries(nextData).forEach(([key, value]) => {
          const baseValue = key === 'alignment'
            ? (baseWall.alignment || 'center')
            : baseWall[key];
          if (baseValue !== value) {
            nextPatch[key] = value;
          }
        });
        if (Object.keys(nextPatch).length > 0) {
          nextModifiedWalls[normalizedWall.id] = nextPatch;
        }
        return;
      }
      nextNewWalls.push({
        ...(existingNewWallMap.get(normalizedWall.id) || {}),
        ...normalizedWall,
        alignment: 'center',
      });
    });

    setModifiedWalls(nextModifiedWalls);
    setNewWalls(nextNewWalls);
    if (markUnsaved) {
      setHasUnsavedChanges(true);
    }
    setHoverPanel((prev) => {
      if (!prev || !['wall', 'new-wall'].includes(prev.type)) {
        return prev;
      }
      const nextWall = workingWalls.find((wall) => wall.id === prev.id) || null;
      return nextWall ? { ...prev, data: nextWall } : prev;
    });
    setSelectedElement((prev) => {
      if (!prev || !['wall', 'new-wall'].includes(prev.type)) {
        return prev;
      }
      const nextWall = workingWalls.find((wall) => wall.id === prev.id) || null;
      return nextWall ? { ...prev, data: nextWall } : prev;
    });
  }, [walls, newWalls, buildEditableWall]);
  const finalizeWallWorkingSet = useCallback((workingWalls, options = {}) => {
    const {
      autoNormalize = wallAutoSnapEnabled,
      markUnsaved = true,
    } = options;
    const normalizedInput = workingWalls.map((wall) => buildEditableWall(wall)).filter(Boolean);
    const nextWalls = autoNormalize
      ? normalizeWallIntersections(normalizedInput, floorPlan?.scale_factor)
      : normalizedInput;
    persistWallWorkingSet(nextWalls, { markUnsaved });
    return nextWalls;
  }, [buildEditableWall, floorPlan?.scale_factor, persistWallWorkingSet, wallAutoSnapEnabled]);
  const replaceWallInWorkingSet = useCallback((wallId, transformWall, options = {}) => {
    const workingWalls = getWorkingWallsSnapshot();
    if (!workingWalls.some((wall) => wall.id === wallId)) {
      return [];
    }
    return finalizeWallWorkingSet(
      workingWalls.map((wall) => (
        wall.id === wallId ? buildEditableWall(transformWall(buildEditableWall(wall))) : wall
      )),
      options,
    );
  }, [buildEditableWall, finalizeWallWorkingSet, getWorkingWallsSnapshot]);
  const resolveWallDraftEndpoint = useCallback((wallGeometry, movingPoint, movingEndpoint = 'end', options = {}) => (
    wallAutoSnapEnabled
      ? resolveWallEndpointSnap(
        buildEditableWall(wallGeometry),
        movingPoint,
        draftingWalls,
        floorPlan?.scale_factor,
        {
          movingEndpoint,
          ...options,
        },
      )
      : movingPoint
  ), [wallAutoSnapEnabled, buildEditableWall, draftingWalls, floorPlan?.scale_factor]);
  const getDraggedWallThicknessMm = useCallback((geometry, pointer) => {
    const dx = geometry.x2 - geometry.x1;
    const dy = geometry.y2 - geometry.y1;
    const length = Math.sqrt(dx * dx + dy * dy);
    if (length < 1e-6) {
      return geometry.thickness || 20;
    }
    const nx = -dy / length;
    const ny = dx / length;
    const midX = (geometry.x1 + geometry.x2) / 2;
    const midY = (geometry.y1 + geometry.y2) / 2;
    const signedDistance = (pointer.x - midX) * nx + (pointer.y - midY) * ny;
    const thicknessPx = Math.max(2, Math.abs(signedDistance) * 2);
    const scale = floorPlan?.scale_factor && floorPlan.scale_factor > 0 ? floorPlan.scale_factor : 1;
    return Math.max(20, thicknessPx * scale);
  }, [floorPlan?.scale_factor]);

  const clearCanvasSelection = useCallback(() => {
    setSelectedElement(null);
    setSelectedElements([]);
  }, []);

  const isElementSelected = useCallback((type, id) => (
    (selectedElement?.type === type && selectedElement?.id === id)
      || selectedElements.some((item) => item.type === type && item.id === id)
  ), [selectedElement, selectedElements]);

  const selectionLockActive = Boolean(selectedElement || selectedElements.length > 0);
  const interactionViewStep = viewStep
    || (pipelineState?.steps?.zkspc?.status === 'validated'
      ? (pipelineState?.branches?.[currentSignalSystem]?.active_step || 'fire_alarms')
      : (pipelineState?.steps?.rooms?.status === 'validated'
        ? 'zkspc'
        : (pipelineState?.active_step || 'original')));
  const drawingToolActive = !['select', 'multi-select', 'room-zone'].includes(selectedTool);
  const mergeModeActive = interactionViewStep === 'devices_cables' && mergeInstrumentId !== null;

  const isElementInteractionBlocked = useCallback((type, id) => (
    ((INTERACTIVE_TYPES_BY_STEP[interactionViewStep] || []).length > 0
      && !(INTERACTIVE_TYPES_BY_STEP[interactionViewStep] || []).includes(type))
    || (!mergeModeActive && drawingToolActive)
    || (!mergeModeActive && selectionLockActive && !isElementSelected(type, id))
  ), [interactionViewStep, drawingToolActive, mergeModeActive, selectionLockActive, isElementSelected]);

  const applyOpeningGeometryUpdate = useCallback((kind, entityId, nextGeometry) => {
    if (kind === 'doors' || kind === 'windows') {
      const key = `${kind}-${entityId}`;
      setModifiedElements((prev) => ({
        ...prev,
        [key]: {
          ...(prev[key] || {}),
          ...nextGeometry,
        },
      }));
    } else if (kind === 'new-doors') {
      setNewDoors((prev) => prev.map((item) => (
        item.id === entityId ? { ...item, ...nextGeometry } : item
      )));
    } else if (kind === 'new-windows') {
      setNewWindows((prev) => prev.map((item) => (
        item.id === entityId ? { ...item, ...nextGeometry } : item
      )));
    }
    setHasUnsavedChanges(true);
  }, []);

  const clearHoverCloseTimeout = useCallback(() => {
    if (hoverLeaveTimeoutRef.current) {
      clearTimeout(hoverLeaveTimeoutRef.current);
      hoverLeaveTimeoutRef.current = null;
    }
  }, []);

  const closeHoverPanel = useCallback(() => {
    clearHoverCloseTimeout();
    setHoverPanelMouseInside(false);
    setHoveredElement(null);
    setHoverPanel(null);
  }, [clearHoverCloseTimeout]);

  const scheduleHoverPanelClose = useCallback(() => {
    clearHoverCloseTimeout();
    hoverLeaveTimeoutRef.current = setTimeout(() => {
      if (!hoverPanelMouseInsideRef.current) {
        setHoveredElement(null);
        setHoverPanel(null);
      }
    }, 140);
  }, [clearHoverCloseTimeout]);

  useEffect(() => {
    hoverPanelMouseInsideRef.current = hoverPanelMouseInside;
  }, [hoverPanelMouseInside]);

  useEffect(() => () => clearHoverCloseTimeout(), [clearHoverCloseTimeout]);

  useEffect(() => {
    if (!hoveredElement || !hoveredElement.type || hoveredElement.id === undefined || hoveredElement.id === null) {
      if (!hoverPanelMouseInsideRef.current) {
        setHoverPanel(null);
      }
      return;
    }
    if (!['wall', 'new-wall', 'door', 'window', 'new-door', 'new-window', 'stair', 'new-stair', 'room', 'fire-alarm', 'new-fire-alarm', 'signal-instrument', 'cable-route'].includes(hoveredElement.type)) {
      if (!hoverPanelMouseInsideRef.current) {
        setHoverPanel(null);
      }
      return;
    }

    let data = null;
    if (hoveredElement.type === 'wall' || hoveredElement.type === 'new-wall') {
      const source = hoveredElement.type === 'wall'
        ? walls.find(item => item.id === hoveredElement.id)
        : newWalls.find(item => item.id === hoveredElement.id);
      data = hoveredElement.type === 'wall'
        ? (source ? { ...source, ...(modifiedWalls[source.id] || {}) } : null)
        : source || null;
      if (data) {
        const derivedLength = getDerivedWallLengthMeters(data, floorPlan?.scale_factor);
        setWallLengthDraft(derivedLength ? String(derivedLength.toFixed(2)) : (data.length_m !== null && data.length_m !== undefined ? String(Number(data.length_m).toFixed(2)) : ''));
        setWallThicknessDraft(
          data.thickness !== null && data.thickness !== undefined
            ? String((Number(data.thickness) / 1000).toFixed(2))
            : '',
        );
      }
    } else if (
      hoveredElement.type === 'door'
      || hoveredElement.type === 'window'
      || hoveredElement.type === 'new-door'
      || hoveredElement.type === 'new-window'
    ) {
      const kind = hoveredElement.type === 'door'
        ? 'doors'
        : hoveredElement.type === 'window'
          ? 'windows'
          : hoveredElement.type === 'new-door'
            ? 'new-doors'
            : 'new-windows';
      const source = kind === 'doors'
        ? doors.find(item => item.id === hoveredElement.id)
        : kind === 'windows'
          ? windows.find(item => item.id === hoveredElement.id)
          : kind === 'new-doors'
            ? newDoors.find(item => item.id === hoveredElement.id)
            : newWindows.find(item => item.id === hoveredElement.id);
      data = source ? getOpeningCurrentGeometry(kind, source.id, source) : null;
      if (data) {
        setOpeningSizeDraft({
          width: data.width !== null && data.width !== undefined
            ? String((pxToMeters(data.width, floorPlan?.scale_factor) ?? 0).toFixed(2))
            : '',
          height: data.height !== null && data.height !== undefined
            ? String((pxToMeters(data.height, floorPlan?.scale_factor) ?? 0).toFixed(2))
            : '',
          wallId: data.wall_id !== null && data.wall_id !== undefined ? String(data.wall_id) : '',
        });
      }
    } else if (hoveredElement.type === 'stair' || hoveredElement.type === 'new-stair') {
      const source = hoveredElement.type === 'stair'
        ? stairs.find(item => item.id === hoveredElement.id)
        : newStairs.find(item => item.id === hoveredElement.id);
      data = source ? getStairCurrentGeometry(source.id, source) : null;
      if (data) {
        setStairDraft({
          width: data.width !== null && data.width !== undefined
            ? String((pxToMeters(data.width, floorPlan?.scale_factor) ?? 0).toFixed(2))
            : '',
          height: data.height !== null && data.height !== undefined
            ? String((pxToMeters(data.height, floorPlan?.scale_factor) ?? 0).toFixed(2))
            : '',
        });
      }
    } else if (hoveredElement.type === 'room') {
      data = rooms.find(item => item.id === hoveredElement.id);
      if (data) {
        setRoomDraft({
          name: data.name || '',
          type: unserviceableRoomIds.has(data.id) ? 'необслуживаемое' : (data.room_type || 'базовое'),
          length: data.length_m !== null && data.length_m !== undefined ? String(data.length_m) : '',
          width: data.width_m !== null && data.width_m !== undefined ? String(data.width_m) : '',
        });
      }
    } else if (hoveredElement.type === 'fire-alarm' || hoveredElement.type === 'new-fire-alarm') {
      const kind = hoveredElement.type === 'fire-alarm' ? 'fire-alarms' : 'new-fire-alarms';
      data = getFireAlarmCurrentGeometry(kind, hoveredElement.id);
      if (data) {
        setFireAlarmDraft({
          zone: data.zone !== null && data.zone !== undefined ? String(data.zone) : '1',
          address: data.address !== null && data.address !== undefined ? String(data.address) : '',
        });
      }
    } else if (hoveredElement.type === 'signal-instrument') {
      data = signalInstruments.find((item) => (
        normalizeSignalSystemType(item.system_type) === currentSignalSystem && item.id === hoveredElement.id
      )) || null;
      if (data) {
        setSignalInstrumentDraft({
          name: data.name || '',
          instrumentType: data.instrument_type || 'control_panel',
        });
      }
    } else if (hoveredElement.type === 'cable-route') {
      data = cableRoutes.find((item) => (
        normalizeSignalSystemType(item.system_type) === currentSignalSystem && item.id === hoveredElement.id
      )) || null;
    }

    setHoverPanel({
      ...hoveredElement,
      data,
      x: hoveredElement.x || 0,
      y: hoveredElement.y || 0,
    });
  }, [hoveredElement, walls, doors, windows, newWalls, newDoors, newWindows, stairs, newStairs, rooms, floorPlan?.scale_factor, modifiedWalls, modifiedElements, getOpeningCurrentGeometry, getStairCurrentGeometry, getFireAlarmCurrentGeometry, unserviceableRoomIds, signalInstruments, cableRoutes, currentSignalSystem]);

  useEffect(() => {
    if (!hoverPanel?.id) {
      return;
    }

    if (hoverPanel.type === 'wall' || hoverPanel.type === 'new-wall') {
      const source = hoverPanel.type === 'wall'
        ? walls.find((item) => item.id === hoverPanel.id)
        : newWalls.find((item) => item.id === hoverPanel.id);
      const current = hoverPanel.type === 'wall'
        ? (source ? { ...source, ...(modifiedWalls[source.id] || {}) } : null)
        : source || null;
      if (!current) {
        return;
      }
      const derivedLength = getDerivedWallLengthMeters(current, floorPlan?.scale_factor);
      setWallLengthDraft(derivedLength ? String(derivedLength.toFixed(2)) : '');
      setWallThicknessDraft(
        current.thickness !== null && current.thickness !== undefined
          ? String((Number(current.thickness) / 1000).toFixed(2))
          : '',
      );
      setHoverPanel((prev) => (prev && prev.id === hoverPanel.id ? { ...prev, data: current } : prev));
      setSelectedElement((prev) => (
        prev && prev.id === hoverPanel.id && prev.type === hoverPanel.type
          ? { ...prev, data: current }
          : prev
      ));
      return;
    }

    if (['door', 'window', 'new-door', 'new-window'].includes(hoverPanel.type)) {
      const kind = hoverPanel.type === 'door'
        ? 'doors'
        : hoverPanel.type === 'window'
          ? 'windows'
          : hoverPanel.type === 'new-door'
            ? 'new-doors'
            : 'new-windows';
      const source = kind === 'doors'
        ? doors.find((item) => item.id === hoverPanel.id)
        : kind === 'windows'
          ? windows.find((item) => item.id === hoverPanel.id)
          : kind === 'new-doors'
            ? newDoors.find((item) => item.id === hoverPanel.id)
            : newWindows.find((item) => item.id === hoverPanel.id);
      const current = source ? getOpeningCurrentGeometry(kind, source.id, source) : null;
      if (!current) {
        return;
      }
      setOpeningSizeDraft({
        width: current.width !== null && current.width !== undefined
          ? String((pxToMeters(current.width, floorPlan?.scale_factor) ?? 0).toFixed(2))
          : '',
        height: current.height !== null && current.height !== undefined
          ? String((pxToMeters(current.height, floorPlan?.scale_factor) ?? 0).toFixed(2))
          : '',
        wallId: current.wall_id !== null && current.wall_id !== undefined ? String(current.wall_id) : '',
      });
      setHoverPanel((prev) => (prev && prev.id === hoverPanel.id ? { ...prev, data: current } : prev));
      setSelectedElement((prev) => (
        prev && prev.id === hoverPanel.id && prev.type === hoverPanel.type
          ? { ...prev, data: current }
          : prev
      ));
      return;
    }

    if (hoverPanel.type === 'stair' || hoverPanel.type === 'new-stair') {
      const source = hoverPanel.type === 'stair'
        ? stairs.find((item) => item.id === hoverPanel.id)
        : newStairs.find((item) => item.id === hoverPanel.id);
      const current = source ? getStairCurrentGeometry(source.id, source) : null;
      if (!current) {
        return;
      }
      setStairDraft({
        width: current.width !== null && current.width !== undefined
          ? String((pxToMeters(current.width, floorPlan?.scale_factor) ?? 0).toFixed(2))
          : '',
        height: current.height !== null && current.height !== undefined
          ? String((pxToMeters(current.height, floorPlan?.scale_factor) ?? 0).toFixed(2))
          : '',
      });
      setHoverPanel((prev) => (prev && prev.id === hoverPanel.id ? { ...prev, data: current } : prev));
      setSelectedElement((prev) => (
        prev && prev.id === hoverPanel.id && prev.type === hoverPanel.type
          ? { ...prev, data: current }
          : prev
      ));
    }
  }, [hoverPanel?.id, hoverPanel?.type, floorPlan?.scale_factor, walls, newWalls, modifiedWalls, doors, windows, newDoors, newWindows, stairs, newStairs, getOpeningCurrentGeometry, getStairCurrentGeometry]);

  // Track the real editor viewport size so fit is recalculated when the stage area changes.
  useEffect(() => {
    const container = stageContainerNode;
    if (!container) {
      return undefined;
    }

    let frameId = null;
    const scheduleMeasure = () => {
      if (typeof window.requestAnimationFrame === 'function') {
        if (frameId !== null) {
          window.cancelAnimationFrame(frameId);
        }
        frameId = window.requestAnimationFrame(updateSize);
        return;
      }
      updateSize();
    };
    const updateSize = () => {
      const rect = container.getBoundingClientRect();
      setContainerSize((prev) => (
        prev.width === rect.width && prev.height === rect.height
          ? prev
          : { width: rect.width, height: rect.height }
      ));
    };

    updateSize();
    scheduleMeasure();

    if (typeof ResizeObserver !== 'undefined') {
      const observer = new ResizeObserver(() => scheduleMeasure());
      observer.observe(container);
      return () => {
        observer.disconnect();
        if (frameId !== null && typeof window.cancelAnimationFrame === 'function') {
          window.cancelAnimationFrame(frameId);
        }
      };
    }

    window.addEventListener('resize', updateSize);
    return () => {
      window.removeEventListener('resize', updateSize);
      if (frameId !== null && typeof window.cancelAnimationFrame === 'function') {
        window.cancelAnimationFrame(frameId);
      }
    };
  }, [stageContainerNode]);

  useEffect(() => {
    setViewport((prev) => {
      const next = clampViewportState(prev);
      return areViewportStatesEqual(prev, next) ? prev : next;
    });
  }, [clampViewportState]);

  // Handle mouse wheel zoom
  useEffect(() => {
    const handleWheel = (e) => {
      if (e.ctrlKey) {
        e.preventDefault();
        const delta = e.deltaY > 0 ? -ZOOM_STEP : ZOOM_STEP;
        updateViewport((prev) => ({
          ...prev,
          zoom: Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, prev.zoom + delta)),
        }));
      }
    };

    const container = stageContainerRef.current;
    if (container) {
      container.addEventListener('wheel', handleWheel, { passive: false });
      return () => container.removeEventListener('wheel', handleWheel);
    }
    return undefined;
  }, [MAX_ZOOM, MIN_ZOOM, ZOOM_STEP, updateViewport]);

  const saveToHistory = useCallback(() => {
    setUndoHistory(prev => [...prev, {
      deletedElements: [...deletedElements],
      newWalls: [...newWalls],
      newStairs: [...newStairs],
      newDoors: [...newDoors],
      newWindows: [...newWindows],
      newFireAlarms: [...newFireAlarms],
      modifiedWalls: { ...modifiedWalls },
      modifiedElements: { ...modifiedElements }
    }]);
  }, [deletedElements, newWalls, newStairs, newDoors, newWindows, newFireAlarms, modifiedWalls, modifiedElements]);

  const handleDeleteElement = useCallback((type, id) => {
    // Сохраняем состояние в историю
    setUndoHistory(prev => [...prev, {
      deletedElements: [...deletedElements],
      newWalls: [...newWalls],
      newStairs: [...newStairs],
      newDoors: [...newDoors],
      newWindows: [...newWindows],
      newFireAlarms: [...newFireAlarms],
      modifiedWalls: { ...modifiedWalls },
      modifiedElements: { ...modifiedElements }
    }]);
    
    // Добавляем элемент в список удаленных
    setDeletedElements(prev => [...prev, { type, id }]);
    if (type === 'walls') {
      setModifiedWalls((prev) => {
        if (prev[id] === undefined) {
          return prev;
        }
        const next = { ...prev };
        delete next[id];
        return next;
      });
    }
    setModifiedElements((prev) => {
      const key = `${type}-${id}`;
      if (!(key in prev)) {
        return prev;
      }
      const next = { ...prev };
      delete next[key];
      return next;
    });
    setSelectedElement(null);
    setSelectedElements(prev => prev.filter(item => item.id !== id));
    setHasUnsavedChanges(true);
  }, [deletedElements, newWalls, newStairs, newDoors, newWindows, newFireAlarms, modifiedWalls, modifiedElements]);

  // Обработка клавиатурных событий
  useEffect(() => {
    const handleKeyDown = (e) => {
      // Shift для углов кратных 45°
      if (e.key === 'Shift') {
        setShiftPressed(true);
      }

      if (e.key === 'Escape') {
        if (drawingWall) {
          e.preventDefault();
          setDrawingWall(null);
        }
        if (placementDraft) {
          e.preventDefault();
          setPlacementDraft(null);
        }
        if (calibrationDraft.start && !calibrationDraft.end) {
          e.preventDefault();
          setCalibrationDraft((prev) => ({ ...prev, start: null, end: null }));
        }
        if (selectedTool !== 'select') {
          e.preventDefault();
          setSelectedTool('select');
        }
        return;
      }
      
      // Delete для удаления выделенных элементов
      if (e.key === 'Delete' && selectedElements.length > 0) {
        e.preventDefault();
        saveToHistory();
        const removedNewWalls = selectedElements.filter((element) => element.type === 'new-wall').length;
        const removedNewStairs = selectedElements.filter((element) => element.type === 'new-stair').length;
        const removedNewDoors = selectedElements.filter((element) => element.type === 'new-door').length;
        const removedNewWindows = selectedElements.filter((element) => element.type === 'new-window').length;
        const removedNewFireAlarms = selectedElements.filter((element) => element.type === 'new-fire-alarm').length;
        const removedPersistedElements = selectedElements.some((element) => !['new-wall', 'new-stair', 'new-door', 'new-window', 'new-fire-alarm'].includes(element.type));
        selectedElements.forEach((element) => {
          if (element.type === 'new-wall') {
            setNewWalls((prev) => prev.filter((item) => item.id !== element.id));
          }
          if (element.type === 'wall') handleDeleteElement('walls', element.id);
          if (element.type === 'stair') handleDeleteElement('stairs', element.id);
          if (element.type === 'new-stair') {
            setNewStairs((prev) => prev.filter((item) => item.id !== element.id));
          }
          if (element.type === 'new-door') {
            setNewDoors((prev) => prev.filter((item) => item.id !== element.id));
          }
          if (element.type === 'new-window') {
            setNewWindows((prev) => prev.filter((item) => item.id !== element.id));
          }
          if (element.type === 'door') handleDeleteElement('doors', element.id);
          if (element.type === 'window') handleDeleteElement('windows', element.id);
          if (element.type === 'room') handleDeleteElement('rooms', element.id);
          if (element.type === 'fire-alarm') handleDeleteElement('fire-alarms', element.id);
          if (element.type === 'new-fire-alarm') {
            setNewFireAlarms((prev) => prev.filter((item) => item.id !== element.id));
          }
        });
        setSelectedElement(null);
        setSelectedElements([]);
        setHasUnsavedChanges(
          removedPersistedElements ||
          (newWalls.length - removedNewWalls) > 0 ||
          (newStairs.length - removedNewStairs) > 0 ||
          (newDoors.length - removedNewDoors) > 0 ||
          (newWindows.length - removedNewWindows) > 0 ||
          (newFireAlarms.length - removedNewFireAlarms) > 0 ||
          deletedElements.length > 0 ||
          Object.keys(modifiedWalls).length > 0 ||
          Object.keys(modifiedElements).length > 0,
        );
      } else if (e.key === 'Delete' && selectedElement) {
        e.preventDefault();
        const type = selectedElement.type === 'new-wall' ? 'new-walls' : 
                     selectedElement.type === 'new-door' ? 'new-doors' :
                     selectedElement.type === 'new-window' ? 'new-windows' :
                     selectedElement.type === 'new-stair' ? 'new-stairs' :
                     selectedElement.type === 'new-fire-alarm' ? 'new-fire-alarms' :
                     selectedElement.type === 'fire-alarm' ? 'fire-alarms' : 
                     selectedElement.type + 's';
        if (type === 'new-walls') {
          setNewWalls((prev) => prev.filter((item) => item.id !== selectedElement.id));
          setSelectedElement(null);
          setSelectedElements([]);
          setHasUnsavedChanges(newWalls.length > 1 || newStairs.length > 0 || newDoors.length > 0 || newWindows.length > 0 || deletedElements.length > 0 || Object.keys(modifiedWalls).length > 0 || Object.keys(modifiedElements).length > 0);
        } else if (type === 'new-doors') {
          setNewDoors((prev) => prev.filter((item) => item.id !== selectedElement.id));
          setSelectedElement(null);
          setSelectedElements([]);
          setHasUnsavedChanges(newWalls.length > 0 || newStairs.length > 0 || newDoors.length > 1 || newWindows.length > 0 || deletedElements.length > 0 || Object.keys(modifiedWalls).length > 0 || Object.keys(modifiedElements).length > 0);
        } else if (type === 'new-windows') {
          setNewWindows((prev) => prev.filter((item) => item.id !== selectedElement.id));
          setSelectedElement(null);
          setSelectedElements([]);
          setHasUnsavedChanges(newWalls.length > 0 || newStairs.length > 0 || newDoors.length > 0 || newWindows.length > 1 || deletedElements.length > 0 || Object.keys(modifiedWalls).length > 0 || Object.keys(modifiedElements).length > 0);
        } else if (type === 'new-stairs') {
          setNewStairs((prev) => prev.filter((item) => item.id !== selectedElement.id));
          setSelectedElement(null);
          setSelectedElements([]);
          setHasUnsavedChanges(newWalls.length > 0 || newStairs.length > 1 || newDoors.length > 0 || newWindows.length > 0 || deletedElements.length > 0 || Object.keys(modifiedWalls).length > 0 || Object.keys(modifiedElements).length > 0);
        } else if (type === 'new-fire-alarms') {
          setNewFireAlarms((prev) => prev.filter((item) => item.id !== selectedElement.id));
          setSelectedElement(null);
          setSelectedElements([]);
          setHasUnsavedChanges(newWalls.length > 0 || newStairs.length > 0 || newDoors.length > 0 || newWindows.length > 0 || newFireAlarms.length > 1 || deletedElements.length > 0 || Object.keys(modifiedWalls).length > 0 || Object.keys(modifiedElements).length > 0);
        } else {
          handleDeleteElement(type, selectedElement.id);
        }
      }
      
      // Ctrl+Z для отмены последнего действия (работает в любой раскладке)
      if (e.ctrlKey && e.code === 'KeyZ') {
        e.preventDefault();
        if (undoHistory.length > 0) {
          const previousState = undoHistory[undoHistory.length - 1];
          setDeletedElements(previousState.deletedElements);
          setNewWalls(previousState.newWalls);
          setNewStairs(previousState.newStairs || []);
          setNewDoors(previousState.newDoors || []);
          setNewWindows(previousState.newWindows || []);
          setNewFireAlarms(previousState.newFireAlarms || []);
          setModifiedWalls(previousState.modifiedWalls);
          setModifiedElements(previousState.modifiedElements);
          setUndoHistory(prev => prev.slice(0, -1));
          
          // Проверяем, остались ли изменения после отмены
          const hasChanges = previousState.deletedElements.length > 0 ||
                           previousState.newWalls.length > 0 ||
                           (previousState.newStairs?.length || 0) > 0 ||
                           (previousState.newDoors?.length || 0) > 0 ||
                           (previousState.newWindows?.length || 0) > 0 ||
                           (previousState.newFireAlarms?.length || 0) > 0 ||
                           Object.keys(previousState.modifiedWalls).length > 0 ||
                           Object.keys(previousState.modifiedElements).length > 0;
          setHasUnsavedChanges(hasChanges);
        }
      }
      
      // Ctrl+S для сохранения изменений (работает в любой раскладке)
    };

    const handleKeyUp = (e) => {
      if (e.key === 'Shift') {
        setShiftPressed(false);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);

    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
    };
  }, [
    selectedElement,
    selectedElements,
    undoHistory,
    deletedElements,
    newWalls,
    newStairs,
    newDoors,
    newWindows,
    newFireAlarms,
    modifiedWalls,
    modifiedElements,
    saveToHistory,
    handleDeleteElement,
    setNewFireAlarms,
    drawingWall,
    placementDraft,
    calibrationDraft,
    selectedTool,
  ]);

  // eslint-disable-next-line no-unused-vars
  const handleWallUpdate = async (wallId, updates) => {
    try {
      await elementsApi.updateWall(wallId, updates);
      fetchFloorPlan();
    } catch (error) {
      console.error('Error updating wall:', error);
    }
  };

  // eslint-disable-next-line no-unused-vars
  const handleRoomUpdate = async (roomId, updates) => {
    try {
      await elementsApi.updateRoom(roomId, { ...updates, floor_plan_id: parseInt(floorPlanId, 10) });
      fetchFloorPlan();
    } catch (error) {
      console.error('Error updating room:', error);
    }
  };

  const handleSaveRoomName = async () => {
    if (selectedElement?.type !== 'room' || !selectedElement?.id) {
      return;
    }

    try {
      setRoomNameSaving(true);
      const updatedRoom = await elementsApi.updateRoom(selectedElement.id, {
        floor_plan_id: parseInt(floorPlanId, 10),
        name: roomNameDraft.trim() || null,
      });

      setRooms(prev => prev.map(room => (
        room.id === updatedRoom.id ? updatedRoom : room
      )));
      setSelectedElement(prev => (
        prev && prev.type === 'room' && prev.id === updatedRoom.id
          ? { ...prev, data: updatedRoom }
          : prev
      ));
    } catch (error) {
      console.error('Error saving room name:', error);
    } finally {
      setRoomNameSaving(false);
    }
  };

  // Функция автоматического распознавания плана этажа
  const buildWallsPayload = useCallback(() => {
    const payload = createEmptyBatchPayload();
    const deletedWallIds = new Set();
    const deletedStairIds = new Set();
    payload.deleted = deletedElements
      .filter((element) => element.type === 'walls' || element.type === 'stairs')
      .map((element) => {
        if (element.type === 'walls') {
          deletedWallIds.add(element.id);
        } else if (element.type === 'stairs') {
          deletedStairIds.add(element.id);
        }
        return { element_type: element.type, id: element.id };
      });
    payload.create_walls = newWalls.map((wall) => ({
      x1: wall.x1,
      y1: wall.y1,
      x2: wall.x2,
      y2: wall.y2,
      floor_plan_id: parseInt(floorPlanId, 10),
      thickness: wall.thickness || 200,
      alignment: 'center',
      is_load_bearing: wall.is_load_bearing || false,
      material: wall.material || null,
      length_m: wall.length_m || null,
      length_source: wall.length_source || null,
    }));
    payload.create_stairs = newStairs.map((stair) => ({
      floor_plan_id: parseInt(floorPlanId, 10),
      x: stair.x,
      y: stair.y,
      width: stair.width,
      height: stair.height,
      rotation_deg: stair.rotation_deg || 0,
      step_count: stair.step_count || 5,
      step_axis: stair.step_axis || (stair.width >= stair.height ? 'horizontal' : 'vertical'),
    }));
    payload.update_walls = Object.entries(modifiedWalls)
      .filter(([wallId]) => !deletedWallIds.has(parseInt(wallId, 10)))
      .map(([wallId, modifications]) => {
        const wall = walls.find((item) => item.id === parseInt(wallId, 10));
        if (!wall) {
          return null;
        }
        return {
          id: parseInt(wallId, 10),
          data: {
            floor_plan_id: wall.floor_plan_id,
            x1: modifications.x1 !== undefined ? modifications.x1 : wall.x1,
            y1: modifications.y1 !== undefined ? modifications.y1 : wall.y1,
            x2: modifications.x2 !== undefined ? modifications.x2 : wall.x2,
            y2: modifications.y2 !== undefined ? modifications.y2 : wall.y2,
            thickness: modifications.thickness !== undefined ? modifications.thickness : wall.thickness,
            alignment: 'center',
            is_load_bearing: wall.is_load_bearing,
            material: wall.material,
            length_m: modifications.length_m !== undefined ? modifications.length_m : wall.length_m,
            length_source: modifications.length_source !== undefined ? modifications.length_source : wall.length_source,
          },
        };
      })
      .filter(Boolean);
    payload.update_stairs = Object.entries(modifiedElements)
      .filter(([key]) => key.startsWith('stairs-'))
      .map(([key, data]) => {
        const { id } = parseModifiedElementKey(key);
        return deletedStairIds.has(id) ? null : { id, data };
      })
      .filter(Boolean);
    return payload;
  }, [deletedElements, newWalls, newStairs, floorPlanId, modifiedWalls, walls, modifiedElements]);

  const buildOpeningsPayload = useCallback(() => {
    const payload = createEmptyBatchPayload();
    const deletedDoorIds = new Set();
    const deletedWindowIds = new Set();
    payload.deleted = deletedElements
      .filter((element) => element.type === 'doors' || element.type === 'windows')
      .map((element) => {
        if (element.type === 'doors') {
          deletedDoorIds.add(element.id);
        } else if (element.type === 'windows') {
          deletedWindowIds.add(element.id);
        }
        return { element_type: element.type, id: element.id };
      });
    payload.create_doors = newDoors.map((door) => ({
      floor_plan_id: parseInt(floorPlanId, 10),
      x: door.x,
      y: door.y,
      width: door.width,
      height: door.height,
      rotation_deg: door.rotation_deg || 0,
      wall_id: door.wall_id,
    }));
    payload.create_windows = newWindows.map((windowItem) => ({
      floor_plan_id: parseInt(floorPlanId, 10),
      x: windowItem.x,
      y: windowItem.y,
      width: windowItem.width,
      height: windowItem.height,
      rotation_deg: windowItem.rotation_deg || 0,
      wall_id: windowItem.wall_id,
    }));
    Object.entries(modifiedElements).forEach(([key, data]) => {
      const { type, id } = parseModifiedElementKey(key);
      if (type === 'doors' && !deletedDoorIds.has(id)) {
        payload.update_doors.push({ id, data });
      } else if (type === 'windows' && !deletedWindowIds.has(id)) {
        payload.update_windows.push({ id, data });
      }
    });
    return payload;
  }, [deletedElements, newDoors, newWindows, floorPlanId, modifiedElements]);

  const buildRoomsPayload = useCallback(() => {
    const payload = createEmptyBatchPayload();
    payload.deleted = deletedElements
      .filter((element) => element.type === 'rooms')
      .map((element) => ({ element_type: element.type, id: element.id }));
    return payload;
  }, [deletedElements]);

  const buildZkspcPayload = useCallback(() => ({
    zones: currentZkspcZones.map((zone, index) => ({
      id: zone.id ?? null,
      zone_number: zone.zone_number ?? (index + 1),
      name: zone.name || `ЗКСПС ${zone.zone_number ?? index + 1}`,
      room_ids: zone.room_ids || [],
      is_manual: zone.is_manual ?? true,
      is_locked: zone.is_locked ?? false,
    })),
  }), [currentZkspcZones]);

  const buildFireAlarmsPayload = useCallback(() => {
    const payload = createEmptyBatchPayload();
    const activeBranchIds = new Set(branchFireAlarms.map((alarm) => alarm.id));
    const deletedAlarmIds = new Set();
    payload.deleted = deletedElements
      .filter((element) => element.type === 'fire-alarms' && activeBranchIds.has(element.id))
      .map((element) => {
        deletedAlarmIds.add(element.id);
        return { element_type: element.type, id: element.id };
      });
    payload.create_fire_alarms = newFireAlarms.map((alarm) => {
      const current = getFireAlarmCurrentGeometry('new-fire-alarms', alarm.id, alarm) || alarm;
      return {
        floor_plan_id: parseInt(floorPlanId, 10),
        x: current.x,
        y: current.y,
        device_type: current.device_type,
        device_model: current.device_model || null,
        coverage_radius: current.coverage_radius ?? null,
        mounting_height: current.mounting_height ?? null,
        system_type: currentSignalSystem,
        zkspc_zone_id: current.zkspc_zone_id ?? roomZoneMap[current.room_id]?.id ?? null,
        loop_kind: current.loop_kind ?? null,
        loop_number: current.loop_number ?? null,
        device_number: current.device_number ?? null,
        zone: current.zone ?? null,
        address: current.address ?? null,
        room_id: current.room_id ?? null,
        offset_left_m: current.offset_left_m ?? null,
        offset_top_m: current.offset_top_m ?? null,
        label_dx: current.label_dx ?? null,
        label_dy: current.label_dy ?? null,
      };
    });
    payload.update_fire_alarms = Object.entries(modifiedElements)
      .filter(([key]) => {
        if (!key.startsWith('fire-alarms-')) {
          return false;
        }
        const { id } = parseModifiedElementKey(key);
        return activeBranchIds.has(id) && !deletedAlarmIds.has(id);
      })
      .map(([key, data]) => {
        const { id } = parseModifiedElementKey(key);
        return {
          id,
          data: {
            ...data,
            system_type: currentSignalSystem,
          },
        };
      });
    return payload;
  }, [branchFireAlarms, deletedElements, newFireAlarms, floorPlanId, modifiedElements, getFireAlarmCurrentGeometry, currentSignalSystem, roomZoneMap]);

  const draftStateByStep = useMemo(() => ({
    walls:
      deletedElements.some((item) => item.type === 'walls' || item.type === 'stairs')
      || newWalls.length > 0
      || newStairs.length > 0
      || Object.keys(modifiedWalls).length > 0
      || Object.keys(modifiedElements).some((key) => key.startsWith('stairs-')),
    openings:
      deletedElements.some((item) => item.type === 'doors' || item.type === 'windows')
      || newDoors.length > 0
      || newWindows.length > 0
      || Object.keys(modifiedElements).some((key) => key.startsWith('doors-') || key.startsWith('windows-')),
    rooms:
      deletedElements.some((item) => item.type === 'rooms'),
    zkspc:
      JSON.stringify(zkspcDraftZones) !== JSON.stringify(zkspcZones),
    fire_alarms:
      deletedElements.some((item) => item.type === 'fire-alarms' && branchFireAlarms.some((alarm) => alarm.id === item.id))
      || newFireAlarms.length > 0
      || Object.keys(modifiedElements).some((key) => {
        if (!key.startsWith('fire-alarms-')) {
          return false;
        }
        const { id } = parseModifiedElementKey(key);
        return branchFireAlarms.some((alarm) => alarm.id === id);
      }),
  }), [deletedElements, newWalls.length, newStairs.length, newDoors.length, newWindows.length, newFireAlarms.length, modifiedWalls, modifiedElements, zkspcDraftZones, zkspcZones, branchFireAlarms]);

  const hasLocalDraftChanges = useMemo(
    () => Object.values(draftStateByStep).some(Boolean),
    [draftStateByStep],
  );

  const hasBlockingDraftChangesForStep = useCallback((step) => {
    const dependencyMap = {
      walls: ['walls'],
      openings: ['walls', 'openings'],
      rooms: ['walls', 'openings', 'rooms'],
      zkspc: ['walls', 'openings', 'rooms'],
      fire_alarms: ['fire_alarms'],
      devices_cables: ['fire_alarms'],
    };
    return (dependencyMap[step] || []).some((stepKey) => draftStateByStep[stepKey]);
  }, [draftStateByStep]);

  useEffect(() => {
    setHasUnsavedChanges(hasLocalDraftChanges);
  }, [hasLocalDraftChanges]);

  const clearDraftsForStep = useCallback((step) => {
    if (step === 'walls') {
      setDeletedElements((prev) => prev.filter((item) => item.type !== 'walls' && item.type !== 'stairs'));
      setNewWalls([]);
      setNewStairs([]);
      setModifiedWalls({});
      setModifiedElements((prev) => Object.fromEntries(
        Object.entries(prev).filter(([key]) => !key.startsWith('stairs-'))
      ));
    } else if (step === 'openings') {
      setDeletedElements((prev) => prev.filter((item) => item.type !== 'doors' && item.type !== 'windows'));
      setNewDoors([]);
      setNewWindows([]);
      setModifiedElements((prev) => Object.fromEntries(
        Object.entries(prev).filter(([key]) => !key.startsWith('doors-') && !key.startsWith('windows-'))
      ));
    } else if (step === 'rooms') {
      setDeletedElements((prev) => prev.filter((item) => item.type !== 'rooms'));
    } else if (step === 'zkspc') {
      setZkspcDraftZones(zkspcZones);
      setSelectedZkspcRooms([]);
    } else if (step === 'fire_alarms') {
      setDeletedElements((prev) => prev.filter((item) => item.type !== 'fire-alarms'));
      setNewFireAlarms([]);
      setFireAlarmWarnings([]);
      setModifiedElements((prev) => Object.fromEntries(
        Object.entries(prev).filter(([key]) => !key.startsWith('fire-alarms-'))
      ));
    }
    setSelectedElements([]);
    setSelectedElement(null);
  }, [setFireAlarmWarnings, setNewFireAlarms, zkspcZones]);

  const clearLocalDraftChanges = useCallback(() => {
    setDeletedElements([]);
    setNewWalls([]);
    setNewStairs([]);
    setNewDoors([]);
    setNewWindows([]);
    setNewFireAlarmsBySystem({ non_addressable: [], addressable: [] });
    setFireAlarmWarningsBySystem({ non_addressable: [], addressable: [] });
    setModifiedWalls({});
    setModifiedElements({});
    setZkspcDraftZones(zkspcZones);
    setSelectedZkspcRooms([]);
    setSelectedElements([]);
    setSelectedElement(null);
    setHasUnsavedChanges(false);
    setUndoHistory([]);
  }, [zkspcZones]);

  const applyPipelineResponse = useCallback((response, stepToClear = null) => {
    if (response?.floor_plan) {
      applyFloorPlanData(response.floor_plan);
    }
    if (response?.pipeline_state) {
      setPipelineState(response.pipeline_state);
    }
    if (stepToClear) {
      clearDraftsForStep(stepToClear);
    } else {
      clearLocalDraftChanges();
    }
    setMissingWallIds([]);
    setShowWallValidationAlert(false);
  }, [applyFloorPlanData, clearLocalDraftChanges, clearDraftsForStep]);

  const collectWallLengthUpdates = useCallback(() => {
    const updates = [];
    walls
      .filter(wall => !deletedElements.some(del => del.type === 'walls' && del.id === wall.id))
      .forEach((wall) => {
        const modifications = modifiedWalls[wall.id] || {};
        const lengthValue = modifications.length_m ?? wall.length_m;
        if (lengthValue !== null && lengthValue !== undefined && Number(lengthValue) > 0) {
          updates.push({
            wall_id: wall.id,
            length_m: Number(lengthValue),
            length_source: modifications.length_source || wall.length_source || 'manual',
          });
        }
      });
    return updates;
  }, [walls, deletedElements, modifiedWalls]);

  const handleDetectStep = useCallback(async (step) => {
    if (hasBlockingDraftChangesForStep(step)) {
      alert('Сначала сохраните или отмените локальные изменения, затем запускайте распознавание.');
      return;
    }
    try {
      setPipelineActionLoading(true);
      let response = null;
      if (step === 'walls') {
        response = await pipelineApi.detectWalls(floorPlanId);
      } else if (step === 'openings') {
        response = await pipelineApi.detectOpenings(floorPlanId);
      } else if (step === 'rooms') {
        response = await pipelineApi.detectRooms(floorPlanId);
      } else if (step === 'zkspc') {
        response = await pipelineApi.detectZkspc(floorPlanId);
      }
      if (response) {
        applyPipelineResponse(response);
      }
    } catch (error) {
      console.error(`Error detecting ${step}:`, error);
      alert(`Не удалось выполнить распознавание шага "${step}".`);
      return false;
    } finally {
      setPipelineActionLoading(false);
    }
  }, [applyPipelineResponse, floorPlanId, hasBlockingDraftChangesForStep]);

  const handleCommitStep = useCallback(async (step) => {
    try {
      setPipelineActionLoading(true);
      let changes = createEmptyBatchPayload();
      let response = null;
      const prospectiveScaleFactor = Number(buildPlanMetaPayload()?.scale_factor ?? floorPlan?.scale_factor ?? 0);
      if (step === 'walls' && !(prospectiveScaleFactor > 1.000001)) {
        alert('РџРµСЂРµРґ РїРѕРґС‚РІРµСЂР¶РґРµРЅРёРµРј СЃС‚РµРЅ Р·Р°РґР°Р№С‚Рµ РјР°СЃС€С‚Р°Р± РЅР° С€Р°РіРµ 1.');
        setPipelineActionLoading(false);
        return false;
      }
      if (floorPlan) {
        await persistPlanMetaDraft();
      }
      if (step === 'walls') {
        if (false && floorPlan) { /*
          let nextScaleFactor;
          if (calibrationDraft.start && calibrationDraft.end && Number(calibrationDraft.distance_m) > 0) {
            const pixelDistance = Math.hypot(
              calibrationDraft.end.x - calibrationDraft.start.x,
              calibrationDraft.end.y - calibrationDraft.start.y,
            );
            if (pixelDistance > 1e-6) {
              nextScaleFactor = (Number(calibrationDraft.distance_m) * 1000) / pixelDistance;
            }
          }
          const committedScaleFactor = Number(floorPlan.scale_factor || 0);
          if (!(nextScaleFactor > 0) && !(committedScaleFactor > 1.000001)) {
            alert('Перед подтверждением стен задайте масштаб на шаге 1.');
            setPipelineActionLoading(false);
            return false;
          }
          const planPayload = {
            name: planMetaDraft.name || null,
            floor_number: planMetaDraft.floor_number !== '' ? Number(planMetaDraft.floor_number) : undefined,
            ceiling_height_mm: planMetaDraft.ceiling_height_m !== '' ? Number(planMetaDraft.ceiling_height_m) * 1000 : undefined,
            scale_factor: nextScaleFactor,
          };
          Object.keys(planPayload).forEach((key) => planPayload[key] === undefined && delete planPayload[key]);
          if (Object.keys(planPayload).length > 0) {
            const updatedFloorPlan = await floorPlansApi.update(floorPlan.id, planPayload);
            applyFloorPlanData(updatedFloorPlan);
            setPlanMetaDraft({
              name: updatedFloorPlan.name || '',
              floor_number: updatedFloorPlan.floor_number !== null && updatedFloorPlan.floor_number !== undefined
                ? String(updatedFloorPlan.floor_number)
                : '',
              ceiling_height_m: updatedFloorPlan.ceiling_height_mm !== null && updatedFloorPlan.ceiling_height_mm !== undefined
                ? String((Number(updatedFloorPlan.ceiling_height_mm) / 1000).toFixed(2))
                : '',
            });
            if (calibrationDraft.start || calibrationDraft.end || calibrationDraft.distance_m) {
              setCalibrationDraft({ start: null, end: null, distance_m: '' });
            }
          }
        }
        */ }
        changes = buildWallsPayload();
        response = await pipelineApi.commitWalls(floorPlanId, {
          changes,
          wall_lengths: collectWallLengthUpdates(),
        });
      } else if (step === 'openings') {
        changes = buildOpeningsPayload();
        response = await pipelineApi.commitOpenings(floorPlanId, { changes });
      } else if (step === 'rooms') {
        changes = buildRoomsPayload();
        const roomDisplayNumbers = buildDisplayNumberMap(
          rooms.filter(room => !deletedElements.some(del => del.type === 'rooms' && del.id === room.id))
        );
        response = await pipelineApi.commitRooms(floorPlanId, {
          changes,
          room_updates: rooms
            .filter(room => !deletedElements.some(del => del.type === 'rooms' && del.id === room.id))
            .map(room => ({
            room_id: room.id,
            name: room.name || null,
            room_number: String(roomDisplayNumbers[room.id] ?? ''),
            room_type: unserviceableRoomIds.has(room.id) ? 'необслуживаемое' : (room.room_type || 'базовое'),
            length_m: room.length_m ?? null,
            width_m: room.width_m ?? null,
          })),
        });
      } else if (step === 'zkspc') {
        response = await pipelineApi.commitZkspc(floorPlanId, buildZkspcPayload());
      }

      if (response) {
        applyPipelineResponse(response, step);
        if (step === 'rooms') {
          setViewStep('zkspc');
        } else if (step === 'zkspc') {
          setViewStep('fire_alarms');
        }
      }
    } catch (error) {
      if (error?.status === 409 && error?.payload?.code === 'stale_editor_state') {
        try {
          const [data, state] = await Promise.all([
            floorPlansApi.get(floorPlanId, true),
            pipelineApi.getState(floorPlanId),
          ]);
          applyFloorPlanData(data);
          setPipelineState(state);
          clearLocalDraftChanges();
          closeHoverPanel();
          alert('Изменения конфликтуют с текущим состоянием сервера. План перезагружен.');
        } catch (reloadError) {
          console.error('Error reloading floor plan after stale commit:', reloadError);
        }
        return false;
      }
      const details = error?.payload?.detail;
      if (step === 'walls' && details && typeof details === 'object' && Array.isArray(details.missing_wall_ids)) {
        setMissingWallIds(details.missing_wall_ids);
        setShowWallValidationAlert(true);
      } else if (step === 'openings' && (error?.payload?.code === 'opening_outside_wall' || error?.message?.includes('Opening must be located on'))) {
        alert('Не удалось подтвердить проемы: один или несколько элементов находятся вне стен. Переместите их на стену и повторите.');
      } else {
        const detailText = typeof details === 'string'
          ? details
          : (error?.payload?.code || error?.message || '');
        alert(`Не удалось подтвердить шаг "${step}". ${detailText}`.trim());
      }
      console.error(`Error committing ${step}:`, error);
    } finally {
      setPipelineActionLoading(false);
    }
  }, [applyPipelineResponse, buildWallsPayload, buildOpeningsPayload, buildRoomsPayload, buildZkspcPayload, collectWallLengthUpdates, floorPlanId, rooms, deletedElements, applyFloorPlanData, clearLocalDraftChanges, closeHoverPanel, unserviceableRoomIds, floorPlan, calibrationDraft, planMetaDraft]);

  const handleSaveFireAlarmsStep = useCallback(async () => {
    if (!draftStateByStep.fire_alarms) {
      return true;
    }
    try {
      setFireAlarmActionLoading(true);
      const result = await floorPlansApi.batchSave(floorPlanId, buildFireAlarmsPayload());
      applyFloorPlanData(result.floor_plan);
      await fetchPipelineState();
      const branchAlarms = (result?.floor_plan?.fire_alarms || []).filter(
        (alarm) => normalizeSignalSystemType(alarm.system_type) === currentSignalSystem,
      );
      /*
        } catch (routingError) {
          console.error('Error auto-recalculating cable routes after fire alarm save:', routingError);
          alert('Извещатели сохранены, но трассировку кабеля не удалось пересчитать автоматически.');
        }
      }
      updateLocalSignalBranchState(currentSignalSystem, {
        fireAlarmsStatus: 'validated',
        devicesCablesStatus,
        activeStep: 'devices_cables',
      });
      */
      updateLocalSignalBranchState(currentSignalSystem, {
        fireAlarmsStatus: 'validated',
        devicesCablesStatus: branchAlarms.length ? 'draft' : 'validated',
        activeStep: 'devices_cables',
      });
      clearDraftsForStep('fire_alarms');
      setUndoHistory([]);
      return true;
    } catch (error) {
      if (error?.status === 409 && error?.payload?.code === 'stale_editor_state') {
        try {
          const [data, state] = await Promise.all([
            floorPlansApi.get(floorPlanId, true),
            pipelineApi.getState(floorPlanId),
          ]);
          applyFloorPlanData(data);
          setPipelineState(state);
          clearLocalDraftChanges();
          closeHoverPanel();
        } catch (reloadError) {
          console.error('Error reloading floor plan after stale fire alarm save:', reloadError);
        }
        return false;
      }
      console.error('Error saving fire alarm step:', error);
      // Keep the alert visible for the user before exiting the save handler.
      alert('Не удалось сохранить изменения шага извещателей.');
    } finally {
      setFireAlarmActionLoading(false);
    }
  }, [draftStateByStep.fire_alarms, floorPlanId, buildFireAlarmsPayload, applyFloorPlanData, clearDraftsForStep, clearLocalDraftChanges, closeHoverPanel, updateLocalSignalBranchState, currentSignalSystem, fetchPipelineState]);

  const handleSwitchSignalSystem = useCallback(async (systemType) => {
    const normalized = normalizeSignalSystemType(systemType);
    if (normalized === currentSignalSystem) {
      return;
    }
    setActiveSignalSystemType(normalized);
    setFloorPlan((prev) => (prev ? { ...prev, active_signal_system_type: normalized } : prev));
    updateLocalSignalBranchState(normalized);
    if (pipelineState?.steps?.zkspc?.status === 'validated') {
      setViewStep(pipelineState?.branches?.[normalized]?.active_step || 'fire_alarms');
    }
    try {
      await floorPlansApi.update(floorPlanId, { active_signal_system_type: normalized });
    } catch (error) {
      console.error('Error switching signal system type:', error);
    }
  }, [currentSignalSystem, floorPlanId, pipelineState, updateLocalSignalBranchState]);

  const handleToggleZkspcRoom = useCallback((roomId) => {
    setSelectedZkspcRooms((prev) => (
      prev.includes(roomId) ? prev.filter((item) => item !== roomId) : [...prev, roomId]
    ));
  }, []);

  const handleMergeSelectedZkspcRooms = useCallback(() => {
    if (selectedZkspcRooms.length < 2) {
      return;
    }
    const selectedSet = new Set(selectedZkspcRooms);
    const remainingZones = currentZkspcZones.filter((zone) => !(zone.room_ids || []).some((roomId) => selectedSet.has(roomId)));
    const selectedRooms = rooms
      .filter((room) => !deletedElements.some((del) => del.type === 'rooms' && del.id === room.id))
      .filter((room) => selectedSet.has(room.id));
    const nextZoneNumber = Math.max(0, ...remainingZones.map((zone) => Number(zone.zone_number || 0))) + 1;
    const mergedZone = {
      id: null,
      zone_number: nextZoneNumber,
      name: `ЗКСПС ${nextZoneNumber}`,
      room_ids: [...selectedSet],
      area_sqm: selectedRooms.reduce((sum, room) => sum + Number(room.area_sqm || 0), 0),
      room_count: selectedSet.size,
      is_manual: true,
      is_locked: false,
      compliance_warnings: [],
    };
    setZkspcDraftZones([...remainingZones, mergedZone]);
  }, [selectedZkspcRooms, currentZkspcZones, rooms, deletedElements]);

  const handleSplitZkspcZone = useCallback((zoneId) => {
    const targetZone = currentZkspcZones.find((zone) => (zone.id ?? zone.zone_number) === zoneId);
    if (!targetZone) {
      return;
    }
    const remainingZones = currentZkspcZones.filter((zone) => (zone.id ?? zone.zone_number) !== zoneId);
    const nextZones = (targetZone.room_ids || []).map((roomId, index) => {
      const room = rooms.find((item) => item.id === roomId);
      const nextZoneNumber = Math.max(0, ...remainingZones.map((zone) => Number(zone.zone_number || 0))) + index + 1;
      return {
        id: null,
        zone_number: nextZoneNumber,
        name: `ЗКСПС ${nextZoneNumber}`,
        room_ids: [roomId],
        area_sqm: Number(room?.area_sqm || 0),
        room_count: 1,
        is_manual: true,
        is_locked: false,
        compliance_warnings: [],
      };
    });
    setZkspcDraftZones([...remainingZones, ...nextZones]);
  }, [currentZkspcZones, rooms]);

  const handleToggleZkspcLock = useCallback((zoneId) => {
    setZkspcDraftZones((prev) => prev.map((zone) => (
      (zone.id ?? zone.zone_number) === zoneId ? { ...zone, is_locked: !zone.is_locked } : zone
    )));
  }, []);

  const handleMoveSelectedRoomsToZone = useCallback((zoneId) => {
    if (!selectedZkspcRooms.length) {
      return;
    }
    const selectedSet = new Set(selectedZkspcRooms);
    setZkspcDraftZones((prev) => prev
      .map((zone) => {
        const zoneKey = zone.id ?? zone.zone_number;
        if (zoneKey === zoneId) {
          const roomIds = Array.from(new Set([...(zone.room_ids || []), ...selectedZkspcRooms])).sort((a, b) => a - b);
          const movedRooms = rooms.filter((room) => roomIds.includes(room.id));
          return {
            ...zone,
            room_ids: roomIds,
            room_count: roomIds.length,
            area_sqm: movedRooms.reduce((sum, room) => sum + Number(room.area_sqm || 0), 0),
            is_manual: true,
          };
        }
        const roomIds = (zone.room_ids || []).filter((roomId) => !selectedSet.has(roomId));
        const remainingRooms = rooms.filter((room) => roomIds.includes(room.id));
        return {
          ...zone,
          room_ids: roomIds,
          room_count: roomIds.length,
          area_sqm: remainingRooms.reduce((sum, room) => sum + Number(room.area_sqm || 0), 0),
          is_manual: true,
        };
      })
      .filter((zone) => (zone.room_ids || []).length > 0));
    setSelectedZkspcRooms([]);
  }, [selectedZkspcRooms, rooms]);

  const refreshCableRoutes = useCallback(async (systemType) => {
    const normalizedSystem = normalizeSignalSystemType(systemType);
    await elementsApi.recalculateCableRoutes(floorPlanId, {
      system_type: normalizedSystem,
      use_shared_trunk: false,
    });
    const data = await floorPlansApi.get(floorPlanId, true);
    applyFloorPlanData(data);
    updateLocalSignalBranchState(normalizedSystem, {
      devicesCablesStatus: 'validated',
      activeStep: 'devices_cables',
    });
    return (data.cable_routes || []).filter((route) => normalizeSignalSystemType(route.system_type) === normalizedSystem);
  }, [applyFloorPlanData, floorPlanId, updateLocalSignalBranchState]);

  const handleCreateSignalInstrumentAt = useCallback(async (instrumentType, x, y) => {
    try {
      setSignalBranchActionLoading(true);
      const definition = getSignalInstrumentDefinition(instrumentType);
      const placement = resolveInstrumentPlacement({ x, y });
      const instrument = await elementsApi.createSignalInstrument({
        floor_plan_id: parseInt(floorPlanId, 10),
        system_type: currentSignalSystem,
        instrument_type: instrumentType,
        x: placement.x,
        y: placement.y,
        name: definition.label,
        supports_cable_merge: definition.supportsMerge,
      });
      setSignalInstruments((prev) => [...prev, instrument]);
      updateLocalSignalBranchState(currentSignalSystem, {
        devicesCablesStatus: 'draft',
        activeStep: 'devices_cables',
      });
      setSelectedElement({ type: 'signal-instrument', id: instrument.id, data: instrument });
      setSelectedElements([{ type: 'signal-instrument', id: instrument.id }]);
    } catch (error) {
      console.error('Error creating signal instrument:', error);
      alert('Не удалось добавить прибор.');
    } finally {
      setSignalBranchActionLoading(false);
    }
  }, [currentSignalSystem, floorPlanId, resolveInstrumentPlacement, updateLocalSignalBranchState]);

  const handleInstrumentDragMove = useCallback((instrument, event) => {
    const placement = resolveInstrumentPlacement(
      { x: event.target.x(), y: event.target.y() },
      { excludeInstrumentId: instrument.id, instrument },
    );
    event.target.position(placement);
  }, [resolveInstrumentPlacement]);

  const handleInstrumentDragEnd = useCallback(async (instrumentId, event) => {
    const instrument = signalInstruments.find((item) => item.id === instrumentId) || null;
    const position = resolveInstrumentPlacement(
      event.target.position(),
      { excludeInstrumentId: instrumentId, instrument },
    );
    event.target.position(position);
    try {
      const updated = await elementsApi.updateSignalInstrument(instrumentId, { x: position.x, y: position.y });
      setSignalInstruments((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      const relatedRoutes = cableRoutes.filter((route) => route.instrument_id === instrumentId);
      if (instrument && relatedRoutes.length) {
        const updatedRoutes = await Promise.all(relatedRoutes.map((route) => elementsApi.updateCableRoute(route.id, {
          polyline_points: translateInstrumentRouteStart(
            route.polyline_points || [],
            { x: instrument.x, y: instrument.y },
            position,
          ),
          is_manual: route.is_manual ?? true,
          zc_label_dx: route.zc_label_dx ?? null,
          zc_label_dy: route.zc_label_dy ?? null,
        })));
        setCableRoutes((prev) => prev.map((route) => updatedRoutes.find((item) => item.id === route.id) || route));
      }
      updateLocalSignalBranchState(updated.system_type, {
        devicesCablesStatus: 'validated',
        activeStep: 'devices_cables',
      });
    } catch (error) {
      console.error('Error moving instrument:', error);
      alert('Не удалось переместить прибор.');
    }
  }, [cableRoutes, resolveInstrumentPlacement, signalInstruments, updateLocalSignalBranchState]);

  const handleStartMergeCableRoutes = useCallback((instrument) => {
    if (!instrument?.id) {
      return;
    }
    setMergeInstrumentId(instrument.id);
    setSelectedTool('multi-select');
    setSelectedElement({ type: 'signal-instrument', id: instrument.id, data: instrument });
    setSelectedElements([]);
    return;
    /*
    try {
      setSignalBranchActionLoading(true);
      await refreshCableRoutes(instrument.system_type, true);
    } catch (error) {
      console.error('Error merging cable routes:', error);
      alert('Не удалось свести кабели.');
    } finally {
      setSignalBranchActionLoading(false);
    }
  }, [refreshCableRoutes]);

    */
  }, []);

  const handleCancelMergeCableRoutes = useCallback(() => {
    setMergeInstrumentId(null);
    setSelectedTool('select');
    clearCanvasSelection();
  }, [clearCanvasSelection]);

  const handleMergeCableRoutes = useCallback(async () => {
    if (!mergeInstrumentId) {
      return;
    }
    const deviceIds = selectedElements
      .filter((item) => item.type === 'fire-alarm' || item.type === 'new-fire-alarm')
      .map((item) => Number(item.id))
      .filter((id) => Number.isInteger(id) && id > 0);
    if (!deviceIds.length) {
      alert('Выберите хотя бы один сохранённый датчик для сведения.');
      return;
    }
    try {
      setSignalBranchActionLoading(true);
      await elementsApi.mergeRoutesForInstrument(mergeInstrumentId, { device_ids: deviceIds });
      await fetchFloorPlan();
      setMergeInstrumentId(null);
      setSelectedTool('select');
      setSelectedElements([]);
    } catch (error) {
      console.error('Error merging cable routes:', error);
      alert('РќРµ СѓРґР°Р»РѕСЃСЊ СЃРІРµСЃС‚Рё РєР°Р±РµР»Рё.');
    } finally {
      setSignalBranchActionLoading(false);
    }
  }, [fetchFloorPlan, mergeInstrumentId, selectedElements]);

  const handleSaveSignalInstrumentMeta = useCallback(async () => {
    if (!hoverPanel || hoverPanel.type !== 'signal-instrument' || !hoverPanel.id) {
      return;
    }
    try {
      setSignalBranchActionLoading(true);
      const definition = getSignalInstrumentDefinition(signalInstrumentDraft.instrumentType);
      const updated = await elementsApi.updateSignalInstrument(hoverPanel.id, {
        name: signalInstrumentDraft.name || definition.label,
        instrument_type: signalInstrumentDraft.instrumentType,
        supports_cable_merge: definition.supportsMerge,
      });
      setSignalInstruments((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      setHoverPanel((prev) => (prev ? { ...prev, data: updated } : prev));
      updateLocalSignalBranchState(updated.system_type, {
        devicesCablesStatus: 'draft',
        activeStep: 'devices_cables',
      });
    } catch (error) {
      console.error('Error saving instrument meta:', error);
      alert('Не удалось сохранить параметры прибора.');
    } finally {
      setSignalBranchActionLoading(false);
    }
  }, [hoverPanel, signalInstrumentDraft, updateLocalSignalBranchState]);

  const handleDeleteSignalInstrument = useCallback(async (instrumentId, systemType) => {
    try {
      setSignalBranchActionLoading(true);
      await elementsApi.deleteSignalInstrument(instrumentId);
      await fetchFloorPlan();
      setMergeInstrumentId((prev) => (prev === instrumentId ? null : prev));
      updateLocalSignalBranchState(systemType, {
        devicesCablesStatus: 'draft',
        activeStep: 'devices_cables',
      });
      closeHoverPanel();
      clearCanvasSelection();
    } catch (error) {
      console.error('Error deleting signal instrument:', error);
      alert('Не удалось удалить прибор.');
    } finally {
      setSignalBranchActionLoading(false);
    }
  }, [clearCanvasSelection, closeHoverPanel, fetchFloorPlan, updateLocalSignalBranchState]);

  const handleCableRouteSegmentDragEnd = useCallback(async (route, insertIndex, event) => {
    const nextPoints = insertOrthogonalDogleg(route.polyline_points || [], insertIndex, {
      x: event.target.x(),
      y: event.target.y(),
    });
    try {
      const updated = await elementsApi.updateCableRoute(route.id, {
        polyline_points: normalizeOrthogonalPolyline(nextPoints),
        is_manual: true,
        zc_label_dx: route.zc_label_dx ?? null,
        zc_label_dy: route.zc_label_dy ?? null,
      });
      setCableRoutes((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      updateLocalSignalBranchState(route.system_type, {
        devicesCablesStatus: 'validated',
        activeStep: 'devices_cables',
      });
      setActiveCableHandle(null);
    } catch (error) {
      console.error('Error inserting cable route point:', error);
      alert('Не удалось изменить сегмент кабеля.');
    }
  }, [updateLocalSignalBranchState]);

  const handleCableRouteHandleDragEnd = useCallback(async (route, pointIndex, event) => {
    const nextPoints = updateOrthogonalHandlePoint(route.polyline_points || [], pointIndex, {
      x: event.target.x(),
      y: event.target.y(),
    });
    try {
      const updated = await elementsApi.updateCableRoute(route.id, {
        polyline_points: normalizeOrthogonalPolyline(nextPoints),
        is_manual: true,
        zc_label_dx: route.zc_label_dx ?? null,
        zc_label_dy: route.zc_label_dy ?? null,
      });
      setCableRoutes((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      updateLocalSignalBranchState(route.system_type, {
        devicesCablesStatus: 'validated',
        activeStep: 'devices_cables',
      });
      setActiveCableHandle(null);
    } catch (error) {
      console.error('Error updating cable route:', error);
      alert('Не удалось изменить кабель.');
    }
  }, [updateLocalSignalBranchState]);

  const applyWallLengthDraft = useCallback((wallGeometry) => {
    if (!wallGeometry || wallLengthDraft === '' || Number.isNaN(Number(wallLengthDraft))) {
      return wallGeometry;
    }
    const targetLengthPx = metersToPx(Number(wallLengthDraft), floorPlan?.scale_factor);
    const axis = getWallAxisData(wallGeometry);
    if (!axis || !(targetLengthPx > 0)) {
      return wallGeometry;
    }
    return {
      ...wallGeometry,
      x2: wallGeometry.x1 + (axis.ux * targetLengthPx),
      y2: wallGeometry.y1 + (axis.uy * targetLengthPx),
    };
  }, [wallLengthDraft, floorPlan?.scale_factor]);

  const handleSaveWallMeta = useCallback(async () => {
    if (!hoverPanel || !['wall', 'new-wall'].includes(hoverPanel.type) || !hoverPanel.id) {
      return;
    }
    const workingWalls = getWorkingWallsSnapshot();
    const existingGeometry = workingWalls.find((wall) => wall.id === hoverPanel.id);
    if (!existingGeometry) {
      return;
    }
    let nextGeometry = {
      ...existingGeometry,
      alignment: 'center',
      thickness: wallThicknessDraft !== '' && !Number.isNaN(Number(wallThicknessDraft))
        ? Math.max(10, Number(wallThicknessDraft) * 1000)
        : existingGeometry.thickness,
    };
    if (wallLengthDraft !== '' && !Number.isNaN(Number(wallLengthDraft))) {
      const axis = getWallAxisData(existingGeometry);
      const targetLengthPx = metersToPx(Number(wallLengthDraft), floorPlan?.scale_factor);
      if (axis && targetLengthPx > 0) {
        nextGeometry = {
          ...nextGeometry,
          x2: existingGeometry.x1 + (axis.ux * targetLengthPx),
          y2: existingGeometry.y1 + (axis.uy * targetLengthPx),
          length_m: Number(wallLengthDraft),
          length_source: 'manual',
        };
      }
    }
    const nextWalls = replaceWallInWorkingSet(hoverPanel.id, () => nextGeometry);
    const persistedWall = nextWalls.find((wall) => wall.id === hoverPanel.id) || nextGeometry;
    setSelectedElement((prev) => (
      prev && ['wall', 'new-wall'].includes(prev.type) && prev.id === hoverPanel.id
        ? { ...prev, data: persistedWall }
        : prev
    ));
    return;
    try {
      if (hoverPanel.type === 'new-wall') {
        const sourceWall = newWalls.find((wall) => wall.id === hoverPanel.id);
        const nextGeometry = applyWallLengthDraft(sourceWall);
        setNewWalls((prev) => prev.map((wall) => (
          wall.id === hoverPanel.id
            ? {
              ...wall,
              ...(nextGeometry ? {
                x1: nextGeometry.x1,
                y1: nextGeometry.y1,
                x2: nextGeometry.x2,
                y2: nextGeometry.y2,
              } : {}),
              thickness: wallThicknessDraft !== '' ? Number(wallThicknessDraft) * 1000 : wall.thickness,
              alignment: normalizeWallAlignment(wallAlignmentDraft),
              ...(wallLengthDraft !== '' && !Number.isNaN(Number(wallLengthDraft))
                ? {
                  length_m: Number(wallLengthDraft),
                  length_source: 'manual',
                }
                : {}),
            }
            : wall
        )));
        setHoverPanel((prev) => (prev ? {
          ...prev,
          data: {
            ...(prev.data || {}),
            ...(nextGeometry ? {
              x1: nextGeometry.x1,
              y1: nextGeometry.y1,
              x2: nextGeometry.x2,
              y2: nextGeometry.y2,
            } : {}),
            thickness: wallThicknessDraft !== '' ? Number(wallThicknessDraft) * 1000 : prev.data?.thickness,
            alignment: normalizeWallAlignment(wallAlignmentDraft),
            ...(wallLengthDraft !== '' && !Number.isNaN(Number(wallLengthDraft))
              ? {
                length_m: Number(wallLengthDraft),
                length_source: 'manual',
              }
              : {}),
          },
        } : prev));
        setSelectedElement((prev) => (prev && prev.type === 'new-wall' && prev.id === hoverPanel.id
          ? {
            ...prev,
            data: {
              ...(prev.data || {}),
              ...(nextGeometry ? {
                x1: nextGeometry.x1,
                y1: nextGeometry.y1,
                x2: nextGeometry.x2,
                y2: nextGeometry.y2,
              } : {}),
              thickness: wallThicknessDraft !== '' ? Number(wallThicknessDraft) * 1000 : prev.data?.thickness,
              alignment: normalizeWallAlignment(wallAlignmentDraft),
              ...(wallLengthDraft !== '' && !Number.isNaN(Number(wallLengthDraft))
                ? {
                  length_m: Number(wallLengthDraft),
                  length_source: 'manual',
                }
                : {}),
            },
          }
          : prev));
        return;
      }

      const currentGeometry = applyWallLengthDraft(getWallCurrentGeometry(hoverPanel.id));
      const payload = {
        floor_plan_id: parseInt(floorPlanId, 10),
        x1: currentGeometry?.x1,
        y1: currentGeometry?.y1,
        x2: currentGeometry?.x2,
        y2: currentGeometry?.y2,
        thickness: wallThicknessDraft !== '' ? Number(wallThicknessDraft) * 1000 : undefined,
        alignment: normalizeWallAlignment(wallAlignmentDraft),
        length_m: wallLengthDraft !== '' ? Number(wallLengthDraft) : undefined,
        length_source: wallLengthDraft !== '' ? 'manual' : undefined,
      };

      Object.keys(payload).forEach((key) => payload[key] === undefined && delete payload[key]);
      const updated = await elementsApi.updateWall(hoverPanel.id, payload);
      setWalls(prev => prev.map(item => (item.id === updated.id ? updated : item)));
      setHoverPanel(prev => (prev ? { ...prev, data: updated } : prev));
      setModifiedWalls(prev => {
        const next = { ...prev };
        delete next[hoverPanel.id];
        return next;
      });
      await fetchPipelineState();
      setMissingWallIds(prev => prev.filter(id => id !== updated.id));
    } catch (error) {
      console.error('Error saving wall metadata:', error);
      alert('Не удалось сохранить параметры стены.');
    }
  }, [fetchPipelineState, floorPlan?.scale_factor, floorPlanId, getWallCurrentGeometry, getWorkingWallsSnapshot, hoverPanel, newWalls, replaceWallInWorkingSet, wallAlignmentDraft, wallLengthDraft, wallThicknessDraft]);

  const handleSaveOpeningMeta = useCallback(() => {
    if (!hoverPanel || !['door', 'window', 'new-door', 'new-window'].includes(hoverPanel.type) || !hoverPanel.id) {
      return;
    }
    const kind = hoverPanel.type === 'door'
      ? 'doors'
      : hoverPanel.type === 'window'
        ? 'windows'
        : hoverPanel.type === 'new-door'
          ? 'new-doors'
          : 'new-windows';
    const source = kind === 'doors'
      ? doors.find((item) => item.id === hoverPanel.id)
      : kind === 'windows'
        ? windows.find((item) => item.id === hoverPanel.id)
        : kind === 'new-doors'
          ? newDoors.find((item) => item.id === hoverPanel.id)
          : newWindows.find((item) => item.id === hoverPanel.id);
    const current = source ? getOpeningCurrentGeometry(kind, source.id, source) : null;
    if (!current) {
      return;
    }
    const widthPx = openingSizeDraft.width !== '' ? metersToPx(Number(openingSizeDraft.width), floorPlan?.scale_factor) : current.width;
    const heightPx = openingSizeDraft.height !== '' ? metersToPx(Number(openingSizeDraft.height), floorPlan?.scale_factor) : current.height;
    const normalized = normalizeOpeningToWall(
      {
        ...current,
        width: widthPx,
        height: heightPx,
        wall_id: openingSizeDraft.wallId !== '' ? Number(openingSizeDraft.wallId) : current.wall_id,
      },
      activeWallGeometries,
      floorPlan?.scale_factor,
      { preferredWallId: openingSizeDraft.wallId !== '' ? Number(openingSizeDraft.wallId) : current.wall_id },
    );
    if (!normalized) {
      alert('Не удалось применить параметры проема: элемент должен быть расположен на стене.');
      return;
    }
    applyOpeningGeometryUpdate(kind, hoverPanel.id, normalized);
    setHoverPanel((prev) => (prev ? { ...prev, data: normalized } : prev));
    setSelectedElement((prev) => (
      prev && prev.id === hoverPanel.id ? { ...prev, data: normalized } : prev
    ));
    setHasUnsavedChanges(true);
    /*

    try {
      const widthPx = openingSizeDraft.width !== '' ? metersToPx(Number(openingSizeDraft.width), floorPlan?.scale_factor) : undefined;
      const heightPx = openingSizeDraft.height !== '' ? metersToPx(Number(openingSizeDraft.height), floorPlan?.scale_factor) : undefined;
      const payload = {
        floor_plan_id: parseInt(floorPlanId, 10),
        width: widthPx !== undefined ? Number(widthPx) : undefined,
        height: heightPx !== undefined ? Number(heightPx) : undefined,
        wall_id: openingSizeDraft.wallId !== '' ? Number(openingSizeDraft.wallId) : undefined,
      };
      Object.keys(payload).forEach((key) => payload[key] === undefined && delete payload[key]);

      if (hoverPanel.type === 'door') {
        const updated = await elementsApi.updateDoor(hoverPanel.id, payload);
        setDoors(prev => prev.map(item => (item.id === updated.id ? updated : item)));
        setHoverPanel(prev => (prev ? { ...prev, data: updated } : prev));
        setModifiedElements(prev => {
          const next = { ...prev };
          delete next[`doors-${hoverPanel.id}`];
          return next;
        });
      } else {
        const updated = await elementsApi.updateWindow(hoverPanel.id, payload);
        setWindows(prev => prev.map(item => (item.id === updated.id ? updated : item)));
        setHoverPanel(prev => (prev ? { ...prev, data: updated } : prev));
        setModifiedElements(prev => {
          const next = { ...prev };
          delete next[`windows-${hoverPanel.id}`];
          return next;
        });
      }
      await fetchPipelineState();
    } catch (error) {
      console.error('Error saving opening metadata:', error);
      alert('Не удалось сохранить параметры проема.');
    } */
  }, [hoverPanel, doors, windows, newDoors, newWindows, getOpeningCurrentGeometry, openingSizeDraft, floorPlan?.scale_factor, activeWallGeometries, applyOpeningGeometryUpdate]);

  const handleSaveStairMeta = useCallback(async () => {
    if (!hoverPanel || (hoverPanel.type !== 'stair' && hoverPanel.type !== 'new-stair') || !hoverPanel.id) {
      return;
    }
    if (hoverPanel.type === 'new-stair') {
      const nextGeometry = {
        width: stairDraft.width !== '' ? Math.max(12, metersToPx(Number(stairDraft.width), floorPlan?.scale_factor)) : hoverPanel.data?.width,
        height: stairDraft.height !== '' ? Math.max(12, metersToPx(Number(stairDraft.height), floorPlan?.scale_factor)) : hoverPanel.data?.height,
      };
      nextGeometry.step_axis = nextGeometry.width >= nextGeometry.height ? 'horizontal' : 'vertical';
      nextGeometry.step_count = getAutoStairStepCount(nextGeometry);
      setNewStairs((prev) => prev.map((item) => (
        item.id === hoverPanel.id ? { ...item, ...nextGeometry } : item
      )));
      setHoverPanel((prev) => (prev ? { ...prev, data: { ...(prev.data || {}), ...nextGeometry } } : prev));
      setSelectedElement((prev) => (
        prev && prev.type === 'new-stair' && prev.id === hoverPanel.id
          ? { ...prev, data: { ...(prev.data || {}), ...nextGeometry } }
          : prev
      ));
      setHasUnsavedChanges(true);
      return;
    }
    try {
      const payload = {
        floor_plan_id: parseInt(floorPlanId, 10),
        width: stairDraft.width !== '' ? metersToPx(Number(stairDraft.width), floorPlan?.scale_factor) : undefined,
        height: stairDraft.height !== '' ? metersToPx(Number(stairDraft.height), floorPlan?.scale_factor) : undefined,
      };
      Object.keys(payload).forEach((key) => payload[key] === undefined && delete payload[key]);
      const updated = await elementsApi.updateStair(hoverPanel.id, payload);
      setStairs((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      setHoverPanel((prev) => (prev ? { ...prev, data: updated } : prev));
      setModifiedElements((prev) => {
        const next = { ...prev };
        delete next[`stairs-${hoverPanel.id}`];
        return next;
      });
    } catch (error) {
      console.error('Error saving stair metadata:', error);
      alert('Не удалось сохранить параметры лестницы.');
    }
  }, [hoverPanel, floorPlanId, stairDraft, floorPlan?.scale_factor]);

  const handleSaveRoomMeta = useCallback(async () => {
    if (!hoverPanel || hoverPanel.type !== 'room' || !hoverPanel.id) {
      return;
    }

    try {
      const payload = {
        floor_plan_id: parseInt(floorPlanId, 10),
        name: roomDraft.name || null,
        room_type: unserviceableRoomIds.has(hoverPanel.id) ? 'необслуживаемое' : (roomDraft.type || 'базовое'),
      };
      Object.keys(payload).forEach((key) => payload[key] === undefined && delete payload[key]);
      const updated = await elementsApi.updateRoom(hoverPanel.id, payload);
      setRooms(prev => prev.map(item => (item.id === updated.id ? updated : item)));
      setHoverPanel(prev => (prev ? { ...prev, data: updated } : prev));
      await fetchPipelineState();
    } catch (error) {
      console.error('Error saving room metadata:', error);
      alert('Не удалось сохранить параметры помещения.');
    }
  }, [hoverPanel, floorPlanId, roomDraft, fetchPipelineState, unserviceableRoomIds]);

  const handleSaveFireAlarmMeta = useCallback(() => {
    if (!hoverPanel || !['fire-alarm', 'new-fire-alarm'].includes(hoverPanel.type) || !hoverPanel.id) {
      return;
    }
    const nextPatch = {
      zone: fireAlarmDraft.zone.trim() || '1',
      address: fireAlarmDraft.address.trim() || String(hoverPanel.data?.address || '1'),
    };
    if (hoverPanel.type === 'new-fire-alarm') {
      setNewFireAlarms((prev) => prev.map((item) => (
        item.id === hoverPanel.id ? { ...item, ...nextPatch } : item
      )));
    } else {
      setModifiedElements((prev) => ({
        ...prev,
        [`fire-alarms-${hoverPanel.id}`]: {
          ...(prev[`fire-alarms-${hoverPanel.id}`] || {}),
          ...nextPatch,
        },
      }));
    }
    setHoverPanel((prev) => (prev ? {
      ...prev,
      data: {
        ...(prev.data || {}),
        ...nextPatch,
      },
    } : prev));
    setSelectedElement((prev) => (
      prev && prev.id === hoverPanel.id && (prev.type === 'fire-alarm' || prev.type === 'new-fire-alarm')
        ? { ...prev, data: { ...(prev.data || {}), ...nextPatch } }
        : prev
    ));
    setHasUnsavedChanges(true);
  }, [hoverPanel, fireAlarmDraft, setNewFireAlarms]);

  const handleFireAlarmLabelDragEnd = useCallback((kind, alarmId, alarm, event) => {
    const current = getFireAlarmCurrentGeometry(kind, alarmId, alarm);
    if (!current) {
      return;
    }
    const patch = {
      label_dx: event.target.x() - current.x,
      label_dy: event.target.y() - current.y,
    };
    if (kind === 'new-fire-alarms') {
      setNewFireAlarms((prev) => prev.map((item) => (
        item.id === alarmId ? { ...item, ...patch } : item
      )));
    } else {
      setModifiedElements((prev) => ({
        ...prev,
        [`fire-alarms-${alarmId}`]: {
          ...(prev[`fire-alarms-${alarmId}`] || {}),
          ...patch,
        },
      }));
    }
    setHasUnsavedChanges(true);
  }, [getFireAlarmCurrentGeometry, setNewFireAlarms]);

  const handleSignalInstrumentLabelDragEnd = useCallback(async (instrument, event) => {
    if (!instrument?.id) {
      return;
    }
    try {
      const updated = await elementsApi.updateSignalInstrument(instrument.id, {
        label_dx: event.target.x() - instrument.x,
        label_dy: event.target.y() - instrument.y,
      });
      setSignalInstruments((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      setHoverPanel((prev) => (
        prev?.type === 'signal-instrument' && prev.id === updated.id
          ? { ...prev, data: updated }
          : prev
      ));
    } catch (error) {
      console.error('Error moving instrument label:', error);
      alert('Не удалось переместить подпись прибора.');
    }
  }, []);

  const handleZcLabelDragEnd = useCallback(async (route, displayPolyline, event) => {
    const anchorPoint = Array.isArray(displayPolyline) ? displayPolyline[displayPolyline.length - 1] : null;
    if (!route?.id || !anchorPoint) {
      return;
    }
    try {
      const updated = await elementsApi.updateCableRoute(route.id, {
        polyline_points: normalizeOrthogonalPolyline(route.polyline_points || []),
        is_manual: route.is_manual ?? true,
        zc_label_dx: event.target.x() - anchorPoint[0],
        zc_label_dy: event.target.y() - anchorPoint[1],
      });
      setCableRoutes((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      updateLocalSignalBranchState(route.system_type, {
        devicesCablesStatus: 'validated',
        activeStep: 'devices_cables',
      });
    } catch (error) {
      console.error('Error moving ZC label:', error);
      alert('Не удалось переместить подпись ZC.');
    }
  }, [updateLocalSignalBranchState]);

  const buildPlanMetaPayload = useCallback(() => {
    if (!floorPlan) {
      return null;
    }
    let nextScaleFactor;
    if (calibrationDraft.start && calibrationDraft.end && Number(calibrationDraft.distance_m) > 0) {
      const pixelDistance = Math.hypot(
        calibrationDraft.end.x - calibrationDraft.start.x,
        calibrationDraft.end.y - calibrationDraft.start.y,
      );
      if (pixelDistance > 1e-6) {
        nextScaleFactor = (Number(calibrationDraft.distance_m) * 1000) / pixelDistance;
      }
    }
    const payload = {
      name: planMetaDraft.name || null,
      floor_number: planMetaDraft.floor_number !== '' ? Number(planMetaDraft.floor_number) : undefined,
      ceiling_height_mm: planMetaDraft.ceiling_height_m !== '' ? Number(planMetaDraft.ceiling_height_m) * 1000 : undefined,
      scale_factor: nextScaleFactor,
    };
    Object.keys(payload).forEach((key) => payload[key] === undefined && delete payload[key]);
    return payload;
  }, [floorPlan, planMetaDraft, calibrationDraft]);

  const persistPlanMetaDraft = useCallback(async () => {
    if (!floorPlan) {
      return floorPlan;
    }
    const payload = buildPlanMetaPayload();
    if (!payload || Object.keys(payload).length === 0) {
      return floorPlan;
    }
    const updated = await floorPlansApi.update(floorPlan.id, payload);
    applyFloorPlanData(updated);
    setPlanMetaDraft({
      name: updated.name || '',
      floor_number: updated.floor_number !== null && updated.floor_number !== undefined
        ? String(updated.floor_number)
        : '',
      ceiling_height_m: updated.ceiling_height_mm !== null && updated.ceiling_height_mm !== undefined
        ? String((Number(updated.ceiling_height_mm) / 1000).toFixed(2))
        : '',
    });
    if (calibrationDraft.start || calibrationDraft.end || calibrationDraft.distance_m) {
      setCalibrationDraft({ start: null, end: null, distance_m: '' });
    }
    return updated;
  }, [floorPlan, buildPlanMetaPayload, applyFloorPlanData, calibrationDraft.start, calibrationDraft.end, calibrationDraft.distance_m]);

  const handleSavePlanMeta = useCallback(async () => {
    if (!floorPlan) {
      return;
    }
    try {
      setSavingPlanMeta(true);
      await persistPlanMetaDraft();
    } catch (error) {
      console.error('Error saving floor plan metadata:', error);
      alert('Не удалось сохранить название/этаж плана.');
    } finally {
      setSavingPlanMeta(false);
    }
  }, [floorPlan, persistPlanMetaDraft]);

  const rotateOpeningBy90 = useCallback((kind, entity) => {
    const key = `${kind}-${entity.id}`;
    const previous = modifiedElements[key] || {};
    const width = previous.width ?? entity.width;
    const height = previous.height ?? entity.height;
    const x = previous.x ?? entity.x;
    const y = previous.y ?? entity.y;
    const centerX = x + width / 2;
    const centerY = y + height / 2;
    const nextWidth = height;
    const nextHeight = width;
    const nextRotation = normalizeAngle360((previous.rotation_deg ?? entity.rotation_deg ?? 0) + 90);

    setModifiedElements((prev) => ({
      ...prev,
      [key]: {
        ...(prev[key] || {}),
        x: centerX - nextWidth / 2,
        y: centerY - nextHeight / 2,
        width: nextWidth,
        height: nextHeight,
        rotation_deg: nextRotation,
      },
    }));
    setHasUnsavedChanges(true);
  }, [modifiedElements]);

  const handleCreateDoor = useCallback((geometry) => {
    saveToHistory();
    const created = {
      id: `temp_door_${Date.now()}`,
      floor_plan_id: parseInt(floorPlanId, 10),
      x: geometry.x,
      y: geometry.y,
      width: geometry.width,
      height: geometry.height,
      rotation_deg: geometry.rotation_deg || 0,
      wall_id: geometry.wall_id,
    };
    setNewDoors((prev) => [...prev, created]);
    setSelectedElement({ type: 'new-door', id: created.id, data: created });
    setSelectedElements([{ type: 'new-door', id: created.id }]);
    setHasUnsavedChanges(true);
  }, [floorPlanId, saveToHistory]);

  const handleCreateWindow = useCallback((geometry) => {
    saveToHistory();
    const created = {
      id: `temp_window_${Date.now()}`,
      floor_plan_id: parseInt(floorPlanId, 10),
      x: geometry.x,
      y: geometry.y,
      width: geometry.width,
      height: geometry.height,
      rotation_deg: geometry.rotation_deg || 0,
      wall_id: geometry.wall_id,
    };
    setNewWindows((prev) => [...prev, created]);
    setSelectedElement({ type: 'new-window', id: created.id, data: created });
    setSelectedElements([{ type: 'new-window', id: created.id }]);
    setHasUnsavedChanges(true);
  }, [floorPlanId, saveToHistory]);

  const handleCreateStair = useCallback((geometry) => {
    saveToHistory();
    const created = {
      id: `temp_stair_${Date.now()}`,
      floor_plan_id: parseInt(floorPlanId, 10),
      x: geometry.x,
      y: geometry.y,
      width: geometry.width,
      height: geometry.height,
      rotation_deg: geometry.rotation_deg || 0,
      step_axis: geometry.step_axis || (geometry.width >= geometry.height ? 'horizontal' : 'vertical'),
    };
    created.step_count = getAutoStairStepCount(created);
    setNewStairs((prev) => [...prev, created]);
    setSelectedElement({ type: 'new-stair', id: created.id, data: created });
    setSelectedElements([{ type: 'new-stair', id: created.id }]);
    setHasUnsavedChanges(true);
  }, [floorPlanId, saveToHistory]);

  const handleCreateDraftFireAlarm = useCallback((deviceType, x, y, overrides = {}) => {
    const placement = resolveFireAlarmPlacement(deviceType, { x, y });
    const metadata = getRoomMetadataForPoint(placement, rooms, floorPlan?.scale_factor);
    if (metadata.roomId && unserviceableRoomIds.has(metadata.roomId)) {
      alert('В необслуживаемом помещении нельзя размещать элементы сигнализации.');
      return;
    }
    saveToHistory();
    const visibleAlarmCount = branchFireAlarms.filter((alarm) => !deletedElements.some((del) => del.type === 'fire-alarms' && del.id === alarm.id)).length;
    const nextAddress = String(visibleAlarmCount + newFireAlarms.length + 1);
    const created = {
      id: createFireAlarmDraftId(),
      floor_plan_id: parseInt(floorPlanId, 10),
      x,
      y,
      device_type: deviceType,
      system_type: currentSignalSystem,
      zkspc_zone_id: roomZoneMap[metadata.roomId]?.id ?? null,
      loop_kind: null,
      loop_number: Number(roomZoneMap[metadata.roomId]?.zone_number || 1),
      device_number: visibleAlarmCount + newFireAlarms.length + 1,
      zone: String(roomZoneMap[metadata.roomId]?.zone_number || 1),
      address: nextAddress,
      coverage_radius: deviceType === 'manual_call_point' ? null : 4500,
      mounting_height: deviceType === 'manual_call_point' ? 1400 : (floorPlan?.ceiling_height_mm || 3000),
      room_id: metadata.roomId,
      offset_left_m: metadata.offsetLeftM,
      offset_top_m: metadata.offsetTopM,
      ...overrides,
    };
    setNewFireAlarms((prev) => [...prev, created]);
    setSelectedElement({ type: 'new-fire-alarm', id: created.id, data: created });
    setSelectedElements([{ type: 'new-fire-alarm', id: created.id }]);
    setHasUnsavedChanges(true);
  }, [floorPlanId, saveToHistory, rooms, floorPlan?.scale_factor, floorPlan?.ceiling_height_mm, branchFireAlarms, deletedElements, newFireAlarms.length, currentSignalSystem, roomZoneMap, setNewFireAlarms, unserviceableRoomIds, resolveFireAlarmPlacement]);

  const handleAutoLayoutFireAlarms = useCallback(async () => {
    const visiblePersisted = branchFireAlarms.filter((alarm) => !deletedElements.some((del) => del.type === 'fire-alarms' && del.id === alarm.id));
    if ((visiblePersisted.length || newFireAlarms.length) && !window.confirm('Текущая расстановка извещателей будет заменена. Продолжить?')) {
      return;
    }

    try {
      setFireAlarmActionLoading(true);
      const preview = await floorPlansApi.autoLayoutFireAlarms(floorPlanId, currentSignalSystem);
      if ((preview.warnings || []).length > 0) {
        setFireAlarmWarnings(preview.warnings || []);
        setViewStep('zkspc');
        return;
      }
      saveToHistory();
      setDeletedElements((prev) => {
        const retained = prev.filter((item) => item.type !== 'fire-alarms' || !branchFireAlarms.some((alarm) => alarm.id === item.id));
        return [
          ...retained,
          ...visiblePersisted.map((alarm) => ({ type: 'fire-alarms', id: alarm.id })),
        ];
      });
      setModifiedElements((prev) => Object.fromEntries(
        Object.entries(prev).filter(([key]) => !key.startsWith('fire-alarms-'))
      ));
      setNewFireAlarms((preview.devices || []).map((device) => ({
        ...device,
        id: createFireAlarmDraftId(),
        floor_plan_id: parseInt(floorPlanId, 10),
        system_type: currentSignalSystem,
      })));
      setFireAlarmWarnings(preview.warnings || []);
      setSelectedElement(null);
      setSelectedElements([]);
      setHasUnsavedChanges(Boolean(visiblePersisted.length || (preview.devices || []).length));
    } catch (error) {
      console.error('Error auto-placing fire alarms:', error);
      alert('Не удалось автоматически расставить извещатели.');
    } finally {
      setFireAlarmActionLoading(false);
    }
  }, [branchFireAlarms, deletedElements, newFireAlarms.length, floorPlanId, saveToHistory, currentSignalSystem, setNewFireAlarms, setFireAlarmWarnings]);

  // eslint-disable-next-line no-unused-vars
  const handleRecognize = async (debug = false) => {
    try {
      setRecognizing(true);
      setRecognitionFeedbackStatus('idle');
      setRecognitionFeedbackError('');
      setDebugImages([]);
      setSelectedDebugImagePath(null);
      await recognitionApi.process(floorPlanId, debug);
      const recognitionData = await recognitionApi.get(floorPlanId, debug);
      setRecognitionMeta(recognitionData);
      setRecognition(recognitionData.recognition_result);

      if (debug && recognitionData.debug_images) {
        setDebugImages(recognitionData.debug_images);
        setShowDebugPanel(true);
      }

      await fetchFloorPlan();

    } catch (error) {
      console.error('Recognition failed:', error);
      alert('Не удалось распознать план этажа. Проверьте, что изображение загружено.');
    } finally {
      setRecognizing(false);
    }
  };

  // Функция для расчета координат с учетом углов кратных 45°
  const snapTo45Degrees = (x1, y1, x2, y2) => {
    const dx = x2 - x1;
    const dy = y2 - y1;
    const angle = Math.atan2(dy, dx);
    const distance = Math.sqrt(dx * dx + dy * dy);
    
    // Приводим угол к ближайшему кратному 45° (π/4)
    const snappedAngle = Math.round(angle / (Math.PI / 4)) * (Math.PI / 4);
    
    return {
      x: x1 + distance * Math.cos(snappedAngle),
      y: y1 + distance * Math.sin(snappedAngle)
    };
  };

  const getScaledPointer = useCallback((e) => {
    const stage = e.target.getStage();
    const point = stage.getPointerPosition();
    return viewportPointToPlan(point, viewTransform);
  }, [viewTransform]);

  const handleStageClick = (e) => {
    if (stagePanMovedRef.current) {
      stagePanMovedRef.current = false;
      return;
    }
    const scaledPoint = getScaledPointer(e);
    const activeEditorStep = viewStep || activePipelineStep || 'original';
    const isBackground = e.target === e.target.getStage()
      || e.target === e.target.getLayer()
      || e.target?.attrs?.id === 'editor-layer'
      || e.target?.className === 'Image';
    if (selectionLockActive && isBackground) {
      clearCanvasSelection();
      closeHoverPanel();
      return;
    }
    if (selectedTool === 'wall' && activeEditorStep === 'walls') {

      if (!drawingWall) {
        // Начало рисования стены
        setDrawingWall({ x1: scaledPoint.x, y1: scaledPoint.y });
      } else {
        // Завершение рисования стены - добавляем локально
        saveToHistory();
        
        let x2 = scaledPoint.x;
        let y2 = scaledPoint.y;
        
        // Если зажат Shift, привязываем к углам кратным 45°
        if (shiftPressed) {
          const snapped = snapTo45Degrees(drawingWall.x1, drawingWall.y1, x2, y2);
          x2 = snapped.x;
          y2 = snapped.y;
        }
        
        const resolvedEnd = resolveWallDraftEndpoint(
          {
            x1: drawingWall.x1,
            y1: drawingWall.y1,
            x2,
            y2,
            thickness: currentWallDraftThicknessMm,
            alignment: 'center',
          },
          { x: x2, y: y2 },
          'end',
        );
        x2 = resolvedEnd.x;
        y2 = resolvedEnd.y;

        const newWall = {
          id: `temp_${Date.now()}`, // Временный ID
          x1: drawingWall.x1,
          y1: drawingWall.y1,
          x2: x2,
          y2: y2,
          thickness: currentWallDraftThicknessMm,
          alignment: 'center',
          length_m: getDerivedWallLengthMeters({
            x1: drawingWall.x1,
            y1: drawingWall.y1,
            x2,
            y2,
          }, floorPlan?.scale_factor),
          length_source: 'derived',
        };

        const nextWalls = finalizeWallWorkingSet([...getWorkingWallsSnapshot(), newWall]);
        const persistedWall = nextWalls.find((wall) => wall.id === newWall.id) || newWall;
        setSelectedElement({ type: 'new-wall', id: newWall.id, data: persistedWall });
        setSelectedElements([{ type: 'new-wall', id: newWall.id }]);
        setDrawingWall(null);
        setSelectedTool('select');
      }
    } else if ((selectedTool === 'door' || selectedTool === 'window') && activeEditorStep === 'openings') {
      if (!placementDraft || placementDraft.type !== selectedTool) {
        setPlacementDraft({ type: selectedTool, start: scaledPoint });
      } else {
        const preview = getOpeningPreviewGeometry(selectedTool, placementDraft.start, scaledPoint);
        if (!preview) {
          return;
        }
        if (selectedTool === 'door') {
          handleCreateDoor(preview);
        } else {
          handleCreateWindow(preview);
        }
        setPlacementDraft(null);
      }
    } else if (selectedTool === 'stairs' && activeEditorStep === 'walls') {
      if (!placementDraft || placementDraft.type !== 'stairs') {
        setPlacementDraft({ type: 'stairs', start: scaledPoint });
      } else {
        handleCreateStair(getStairPreviewGeometry(placementDraft.start, scaledPoint));
        setPlacementDraft(null);
      }
    } else if (selectedTool === 'calibration' && activeEditorStep !== 'original') {
      if (!calibrationDraft.start || calibrationDraft.end) {
        setCalibrationDraft((prev) => ({ ...prev, start: scaledPoint, end: null }));
      } else {
        setCalibrationDraft((prev) => ({ ...prev, end: scaledPoint }));
      }
    } else if (selectedTool === 'smoke-detector' && activeEditorStep === 'fire_alarms') {
      handleCreateDraftFireAlarm('smoke_detector', scaledPoint.x, scaledPoint.y);
    } else if (selectedTool === 'manual-call-point' && activeEditorStep === 'fire_alarms') {
      handleCreateDraftFireAlarm('manual_call_point', scaledPoint.x, scaledPoint.y);
    } else if (SIGNAL_INSTRUMENT_OPTIONS.some((option) => option.key === selectedTool) && activeEditorStep === 'devices_cables') {
      handleCreateSignalInstrumentAt(selectedTool, scaledPoint.x, scaledPoint.y);
    } else if (selectedTool === 'select' && isBackground) {
      // Сброс выбора при клике на пустую область в режиме выбора
      clearCanvasSelection();
    }
  };

  const handleSubmitRecognitionFeedback = useCallback(async () => {
    try {
      setRecognitionFeedbackSubmitting(true);
      setRecognitionFeedbackStatus('idle');
      setRecognitionFeedbackError('');
      await recognitionApi.submitFeedback(floorPlanId);
      setRecognitionFeedbackStatus('success');
    } catch (error) {
      console.error('Recognition feedback submission failed:', error);
      setRecognitionFeedbackStatus('error');
      setRecognitionFeedbackError('Не удалось отправить исправленный результат для обучения.');
    } finally {
      setRecognitionFeedbackSubmitting(false);
    }
  }, [floorPlanId]);

  const handleElementDragStart = useCallback((type, id, e) => {
    closeHoverPanel();
    dragStartRef.current[`${type}-${id}`] = { x: e.target.x(), y: e.target.y() };
    setActiveDrag({ type, id, x: e.target.x(), y: e.target.y() });
  }, [closeHoverPanel]);

  const handleElementDragMove = useCallback((type, id, entity, e) => {
    if (type === 'fire-alarms' || type === 'new-fire-alarms') {
      const current = getFireAlarmCurrentGeometry(type, id, entity);
      const placement = resolveFireAlarmPlacement(
        current?.device_type || entity?.device_type || 'smoke_detector',
        { x: e.target.x(), y: e.target.y() },
        { excludeFireAlarmId: id },
      );
      e.target.position(placement);
      setActiveDrag({ type, id, x: placement.x, y: placement.y });
      return;
    }
    if (!['doors', 'windows', 'new-doors', 'new-windows'].includes(type)) {
      return;
    }
    const current = getOpeningCurrentGeometry(type, id, entity);
    if (!current) {
      return;
    }
    const normalized = normalizeOpeningToWall(
      {
        ...current,
        x: e.target.x() - current.width / 2,
        y: e.target.y() - current.height / 2,
      },
      activeWallGeometries,
      floorPlan?.scale_factor,
      { preferredWallId: current.wall_id },
    );
    if (normalized) {
      e.target.position({ x: normalized.x + normalized.width / 2, y: normalized.y + normalized.height / 2 });
    }
  }, [activeWallGeometries, floorPlan?.scale_factor, getFireAlarmCurrentGeometry, getOpeningCurrentGeometry, resolveFireAlarmPlacement]);

  const handleElementDragEnd = (type, id, e) => {
    saveToHistory();
    
    const node = e.target;
    const key = `${type}-${id}`;
    const dragStart = dragStartRef.current[key];
    const newPos = {
      x: node.x(),
      y: node.y(),
    };
    if (shiftPressed && dragStart && !['doors', 'windows', 'new-doors', 'new-windows'].includes(type)) {
      const dx = newPos.x - dragStart.x;
      const dy = newPos.y - dragStart.y;
      const snapped = snapTo45Degrees(0, 0, dx, dy);
      newPos.x = dragStart.x + snapped.x;
      newPos.y = dragStart.y + snapped.y;
      node.position({ x: newPos.x, y: newPos.y });
    }
    delete dragStartRef.current[key];
    setActiveDrag(null);

    if (['doors', 'windows', 'new-doors', 'new-windows'].includes(type)) {
      const current = getOpeningCurrentGeometry(type, id);
      newPos.x -= (current?.width || 0) / 2;
      newPos.y -= (current?.height || 0) / 2;
      const normalized = current ? normalizeOpeningToWall(
        {
          ...current,
          x: newPos.x,
          y: newPos.y,
        },
        activeWallGeometries,
        floorPlan?.scale_factor,
        { preferredWallId: current.wall_id },
      ) : null;
      if (normalized) {
        newPos.x = normalized.x;
        newPos.y = normalized.y;
        newPos.width = normalized.width;
        newPos.height = normalized.height;
        newPos.rotation_deg = normalized.rotation_deg;
        newPos.wall_id = normalized.wall_id;
      }
    } else if (type === 'fire-alarms' || type === 'new-fire-alarms') {
      const current = getFireAlarmCurrentGeometry(type, id);
      const placement = resolveFireAlarmPlacement(
        current?.device_type || 'smoke_detector',
        newPos,
        { excludeFireAlarmId: id },
      );
      newPos.x = placement.x;
      newPos.y = placement.y;
      node.position(placement);
    }

    // Сохраняем изменения локально
    if (['doors', 'windows', 'new-doors', 'new-windows'].includes(type)) {
      applyOpeningGeometryUpdate(type, id, newPos);
    } else if (type === 'new-fire-alarms') {
      setNewFireAlarms((prev) => prev.map((item) => (
        item.id === id ? { ...item, ...newPos } : item
      )));
      setHasUnsavedChanges(true);
    } else {
      setModifiedElements(prev => ({
        ...prev,
        [`${type}-${id}`]: newPos
      }));
      setHasUnsavedChanges(true);
    }
  };

  const handleWallDrag = (wallId, e) => {
    closeHoverPanel();
    const node = e.target;
    let dx = node.x();
    let dy = node.y();
    if (shiftPressed) {
      const snapped = snapTo45Degrees(0, 0, dx, dy);
      dx = snapped.x;
      dy = snapped.y;
    }
    
    setEditingWall({ id: wallId, isDragging: true, dx, dy });
  };

  const handleWallDragEnd = (wallId, originalWall, e) => {
    if (!editingWall || !editingWall.isDragging) return;
    
    saveToHistory();
    
    const node = e.target;
    const dx = node.x();
    const dy = node.y();
    replaceWallInWorkingSet(wallId, (wall) => ({
      ...wall,
      x1: wall.x1 + dx,
      y1: wall.y1 + dy,
      x2: wall.x2 + dx,
      y2: wall.y2 + dy,
    }));
    node.position({ x: 0, y: 0 });
    setEditingWall(null);
    return;

    // Вычисляем текущие координаты с учетом уже сохраненных изменений
    let currentX1 = originalWall.x1;
    let currentY1 = originalWall.y1;
    let currentX2 = originalWall.x2;
    let currentY2 = originalWall.y2;
    
    if (modifiedWalls[wallId]) {
      if (modifiedWalls[wallId].x1 !== undefined) currentX1 = modifiedWalls[wallId].x1;
      if (modifiedWalls[wallId].y1 !== undefined) currentY1 = modifiedWalls[wallId].y1;
      if (modifiedWalls[wallId].x2 !== undefined) currentX2 = modifiedWalls[wallId].x2;
      if (modifiedWalls[wallId].y2 !== undefined) currentY2 = modifiedWalls[wallId].y2;
    }

    // Сохраняем смещение обеих точек стены
    setModifiedWalls(prev => ({
      ...prev,
      [wallId]: {
        x1: currentX1 + dx,
        y1: currentY1 + dy,
        x2: currentX2 + dx,
        y2: currentY2 + dy,
      }
    }));
    
    // Сбрасываем позицию элемента обратно к (0,0)
    node.position({ x: 0, y: 0 });
    
    setHasUnsavedChanges(true);
    setEditingWall(null);
  };

  const handleNewWallDrag = useCallback((wallId, e) => {
    closeHoverPanel();
    const node = e.target;
    let dx = node.x();
    let dy = node.y();
    if (shiftPressed) {
      const snapped = snapTo45Degrees(0, 0, dx, dy);
      dx = snapped.x;
      dy = snapped.y;
    }

    setEditingWall({ id: wallId, isDragging: true, dx, dy });
  }, [closeHoverPanel, shiftPressed]);

  const handleNewWallDragEnd = useCallback((wallId, originalWall, e) => {
    if (!editingWall || !editingWall.isDragging) {
      return;
    }

    saveToHistory();

    const node = e.target;
    const dx = node.x();
    const dy = node.y();
    replaceWallInWorkingSet(wallId, (wall) => ({
      ...wall,
      x1: wall.x1 + dx,
      y1: wall.y1 + dy,
      x2: wall.x2 + dx,
      y2: wall.y2 + dy,
    }));
    node.position({ x: 0, y: 0 });
    setEditingWall(null);
    return;
    const nextWall = {
      ...originalWall,
      x1: originalWall.x1 + dx,
      y1: originalWall.y1 + dy,
      x2: originalWall.x2 + dx,
      y2: originalWall.y2 + dy,
    };

    setNewWalls((prev) => prev.map((wall) => (
      wall.id === wallId ? { ...wall, ...nextWall } : wall
    )));
    node.position({ x: 0, y: 0 });
    setHasUnsavedChanges(true);
    setEditingWall(null);
  }, [editingWall, replaceWallInWorkingSet, saveToHistory]);

  const handleWallPointDrag = (wallId, point, e) => {
    closeHoverPanel();
    const scaledPos = getScaledPointer(e);
    let previewPoint = scaledPos;
    
    // Если зажат Shift, привязываем к углам кратных 45°
    if (shiftPressed) {
      const wall = walls.find((item) => item.id === wallId);
      if (wall) {
        const modifications = modifiedWalls[wallId] || {};
        const x1 = point === 'start' ? scaledPos.x : (modifications.x1 !== undefined ? modifications.x1 : wall.x1);
        const y1 = point === 'start' ? scaledPos.y : (modifications.y1 !== undefined ? modifications.y1 : wall.y1);
        const x2 = point === 'end' ? scaledPos.x : (modifications.x2 !== undefined ? modifications.x2 : wall.x2);
        const y2 = point === 'end' ? scaledPos.y : (modifications.y2 !== undefined ? modifications.y2 : wall.y2);
        
        if (point === 'start') {
          previewPoint = snapTo45Degrees(x2, y2, x1, y1);
        } else {
          previewPoint = snapTo45Degrees(x1, y1, x2, y2);
        }
      }
    }
    e.target.position(previewPoint);
    setEditingWall({ id: wallId, point, x: previewPoint.x, y: previewPoint.y });
  };

  const handleWallPointDragEnd = async (wallId, point, e) => {
    saveToHistory();

    let pos = getScaledPointer(e);
    const scaledPos = pos;
    
    // Если зажат Shift, привязываем к углам кратных 45°
    if (shiftPressed) {
      const wall = walls.find(w => w.id === wallId);
      if (wall) {
        const modifications = modifiedWalls[wallId] || {};
        const x1 = point === 'start' ? scaledPos.x : (modifications.x1 !== undefined ? modifications.x1 : wall.x1);
        const y1 = point === 'start' ? scaledPos.y : (modifications.y1 !== undefined ? modifications.y1 : wall.y1);
        const x2 = point === 'end' ? scaledPos.x : (modifications.x2 !== undefined ? modifications.x2 : wall.x2);
        const y2 = point === 'end' ? scaledPos.y : (modifications.y2 !== undefined ? modifications.y2 : wall.y2);
        
        if (point === 'start') {
          const snapped = snapTo45Degrees(x2, y2, x1, y1);
          pos = { x: snapped.x, y: snapped.y };
        } else {
          const snapped = snapTo45Degrees(x1, y1, x2, y2);
          pos = { x: snapped.x, y: snapped.y };
        }
      }
    } else {
      pos = scaledPos;
    }
    const wall = walls.find((item) => item.id === wallId);
    if (wall) {
      const modifications = modifiedWalls[wallId] || {};
      pos = resolveWallDraftEndpoint(
        {
          ...wall,
          x1: modifications.x1 !== undefined ? modifications.x1 : wall.x1,
          y1: modifications.y1 !== undefined ? modifications.y1 : wall.y1,
          x2: modifications.x2 !== undefined ? modifications.x2 : wall.x2,
          y2: modifications.y2 !== undefined ? modifications.y2 : wall.y2,
          thickness: modifications.thickness !== undefined ? modifications.thickness : wall.thickness,
          alignment: modifications.alignment !== undefined ? modifications.alignment : (wall.alignment || 'center'),
        },
        pos,
        point,
        { excludeWallId: wallId },
      );
    }
    replaceWallInWorkingSet(wallId, (currentWall) => {
      const nextWall = point === 'start'
        ? { ...currentWall, x1: pos.x, y1: pos.y }
        : { ...currentWall, x2: pos.x, y2: pos.y };
      return {
        ...nextWall,
        length_m: getDerivedWallLengthMeters(nextWall, floorPlan?.scale_factor),
        length_source: 'derived',
      };
    });
    setEditingWall(null);
    return;
    
    const updates = point === 'start' 
      ? { x1: pos.x, y1: pos.y }
      : { x2: pos.x, y2: pos.y };

    // Сохраняем изменения локально
    setModifiedWalls(prev => ({
      ...prev,
      [wallId]: {
        ...prev[wallId],
        ...updates
      }
    }));
    
    setEditingWall(null);
    setHasUnsavedChanges(true);
  };

  const handleNewWallPointDrag = useCallback((wallId, point, e) => {
    closeHoverPanel();
    const scaledPos = getScaledPointer(e);
    const wall = newWalls.find((item) => item.id === wallId);
    if (!wall) {
      return;
    }
    let nextPoint = scaledPos;
    if (shiftPressed) {
      const anchor = point === 'start'
        ? { x: wall.x2, y: wall.y2 }
        : { x: wall.x1, y: wall.y1 };
      const snapped = snapTo45Degrees(anchor.x, anchor.y, scaledPos.x, scaledPos.y);
      nextPoint = { x: snapped.x, y: snapped.y };
    }
    setNewWalls((prev) => prev.map((item) => (
      item.id === wallId
        ? {
          ...item,
          ...(point === 'start'
            ? { x1: nextPoint.x, y1: nextPoint.y }
            : { x2: nextPoint.x, y2: nextPoint.y }),
          length_m: getDerivedWallLengthMeters({
            ...(point === 'start'
              ? { x1: nextPoint.x, y1: nextPoint.y, x2: item.x2, y2: item.y2 }
              : { x1: item.x1, y1: item.y1, x2: nextPoint.x, y2: nextPoint.y }),
          }, floorPlan?.scale_factor),
          length_source: item.length_source === 'manual' ? 'manual' : 'derived',
        }
        : item
    )));
    setHasUnsavedChanges(true);
  }, [closeHoverPanel, floorPlan?.scale_factor, getScaledPointer, newWalls, shiftPressed]);

  const handleNewWallPointDragEnd = useCallback((wallId, point, e) => {
    const scaledPos = getScaledPointer(e);
    const wall = newWalls.find((item) => item.id === wallId);
    if (!wall) {
      return;
    }
    let nextPoint = scaledPos;
    if (shiftPressed) {
      const anchor = point === 'start'
        ? { x: wall.x2, y: wall.y2 }
        : { x: wall.x1, y: wall.y1 };
      const snapped = snapTo45Degrees(anchor.x, anchor.y, scaledPos.x, scaledPos.y);
      nextPoint = { x: snapped.x, y: snapped.y };
    }
    nextPoint = resolveWallDraftEndpoint(wall, nextPoint, point, { excludeWallId: wallId });
    replaceWallInWorkingSet(wallId, (currentWall) => {
      const nextWall = point === 'start'
        ? { ...currentWall, x1: nextPoint.x, y1: nextPoint.y }
        : { ...currentWall, x2: nextPoint.x, y2: nextPoint.y };
      return {
        ...nextWall,
        length_m: getDerivedWallLengthMeters(nextWall, floorPlan?.scale_factor),
        length_source: 'derived',
      };
    });
    return;
    setNewWalls((prev) => prev.map((item) => (
      item.id === wallId
        ? {
          ...item,
          ...(point === 'start'
            ? { x1: nextPoint.x, y1: nextPoint.y }
            : { x2: nextPoint.x, y2: nextPoint.y }),
          length_m: getDerivedWallLengthMeters({
            ...(point === 'start'
              ? { x1: nextPoint.x, y1: nextPoint.y, x2: item.x2, y2: item.y2 }
              : { x1: item.x1, y1: item.y1, x2: nextPoint.x, y2: nextPoint.y }),
          }, floorPlan?.scale_factor),
          length_source: item.length_source === 'manual' ? 'manual' : 'derived',
        }
        : item
    )));
    setHasUnsavedChanges(true);
  }, [floorPlan?.scale_factor, getScaledPointer, newWalls, replaceWallInWorkingSet, resolveWallDraftEndpoint, shiftPressed]);

  const handleNewWallThicknessDrag = useCallback((wallId, e) => {
    closeHoverPanel();
    const wall = newWalls.find((item) => item.id === wallId);
    if (!wall) {
      return;
    }
    const pointer = getScaledPointer(e);
    const thicknessMm = getDraggedWallThicknessMm(wall, pointer);

    setEditingWall((prev) => ({ ...(prev || {}), id: wallId, adjustingThickness: true }));
    setNewWalls((prev) => prev.map((item) => (
      item.id === wallId ? { ...item, thickness: thicknessMm } : item
    )));
  }, [closeHoverPanel, getDraggedWallThicknessMm, getScaledPointer, newWalls]);

  const handleNewWallThicknessDragEnd = useCallback((wallId, e) => {
    saveToHistory();
    const pointer = getScaledPointer(e);
    replaceWallInWorkingSet(wallId, (wall) => ({
      ...wall,
      thickness: getDraggedWallThicknessMm(wall, pointer),
    }));
    setEditingWall(null);
  }, [getDraggedWallThicknessMm, getScaledPointer, replaceWallInWorkingSet, saveToHistory]);

  useEffect(() => {
    if (!activeWallGeometries.length) {
      return;
    }
    setModifiedElements((prev) => {
      let changed = false;
      const next = { ...prev };

      doors
        .filter((door) => !deletedElements.some((del) => del.type === 'doors' && del.id === door.id))
        .forEach((door) => {
          const current = {
            ...door,
            ...(next[`doors-${door.id}`] || {}),
          };
          const normalized = normalizeOpeningToWall(current, activeWallGeometries, floorPlan?.scale_factor, {
            preferredWallId: current.wall_id,
          });
          if (!normalized) {
            return;
          }
          const key = `doors-${door.id}`;
          const previous = next[key] || {};
          const shouldUpdate =
            current.x !== normalized.x ||
            current.y !== normalized.y ||
            current.width !== normalized.width ||
            current.height !== normalized.height ||
            current.rotation_deg !== normalized.rotation_deg ||
            current.wall_id !== normalized.wall_id;
          if (shouldUpdate) {
            next[key] = { ...previous, ...normalized };
            changed = true;
          }
        });

      windows
        .filter((windowItem) => !deletedElements.some((del) => del.type === 'windows' && del.id === windowItem.id))
        .forEach((windowItem) => {
          const current = {
            ...windowItem,
            ...(next[`windows-${windowItem.id}`] || {}),
          };
          const normalized = normalizeOpeningToWall(current, activeWallGeometries, floorPlan?.scale_factor, {
            preferredWallId: current.wall_id,
          });
          if (!normalized) {
            return;
          }
          const key = `windows-${windowItem.id}`;
          const previous = next[key] || {};
          const shouldUpdate =
            current.x !== normalized.x ||
            current.y !== normalized.y ||
            current.width !== normalized.width ||
            current.height !== normalized.height ||
            current.rotation_deg !== normalized.rotation_deg ||
            current.wall_id !== normalized.wall_id;
          if (shouldUpdate) {
            next[key] = { ...previous, ...normalized };
            changed = true;
          }
        });

      return changed ? next : prev;
    });
  }, [activeWallGeometries, doors, windows, deletedElements, floorPlan?.scale_factor]);

  useEffect(() => {
    if (!activeWallGeometries.length) {
      return;
    }
    setNewDoors((prev) => prev.map((door) => {
      const normalized = normalizeOpeningToWall(door, activeWallGeometries, floorPlan?.scale_factor, {
        preferredWallId: door.wall_id,
      });
      return normalized ? { ...door, ...normalized } : door;
    }));
    setNewWindows((prev) => prev.map((windowItem) => {
      const normalized = normalizeOpeningToWall(windowItem, activeWallGeometries, floorPlan?.scale_factor, {
        preferredWallId: windowItem.wall_id,
      });
      return normalized ? { ...windowItem, ...normalized } : windowItem;
    }));
  }, [activeWallGeometries, floorPlan?.scale_factor]);

  const getPlacementEndPoint = useCallback((start, end) => {
    if (!shiftPressed) {
      return end;
    }
    return snapTo45Degrees(start.x, start.y, end.x, end.y);
  }, [shiftPressed]);

  const getOpeningPreviewGeometry = useCallback((type, start, end) => {
    const adjustedEnd = getPlacementEndPoint(start, end);
    const rect = normalizeRectFromPoints(start, adjustedEnd);
    return normalizeOpeningToWall(
      {
        x: rect.x,
        y: rect.y,
        width: Math.max(rect.width, 4),
        height: Math.max(rect.height, 4),
        rotation_deg: 0,
      },
      activeWallGeometries,
      floorPlan?.scale_factor,
      { useBoundingRect: true },
    );
  }, [activeWallGeometries, floorPlan?.scale_factor, getPlacementEndPoint]);

  const getStairPreviewGeometry = useCallback((start, end) => {
    const adjustedEnd = getPlacementEndPoint(start, end);
    const rect = normalizeRectFromPoints(start, adjustedEnd);
    const width = Math.max(12, rect.width);
    const height = Math.max(12, rect.height);
    return {
      x: rect.x,
      y: rect.y,
      width,
      height,
      rotation_deg: 0,
      step_axis: width >= height ? 'horizontal' : 'vertical',
    };
  }, [getPlacementEndPoint]);

  const handleOpeningResize = useCallback((kind, entity, edge, e) => {
    closeHoverPanel();
    const current = getOpeningCurrentGeometry(kind, entity.id, entity);
    if (!current) {
      return;
    }
    const wall = activeWallGeometries.find((item) => item.id === current.wall_id);
    if (!wall) {
      return;
    }
    const wallAxis = getWallAxisData(wall);
    if (!wallAxis) {
      return;
    }
    const scaledPointer = getScaledPointer(e);
    const centerProjection = projectPointToWall({
      x: current.x + current.width / 2,
      y: current.y + current.height / 2,
    }, wall);
    const pointerProjection = projectPointToWall(scaledPointer, wall);
    if (!centerProjection || !pointerProjection) {
      return;
    }

    const currentHalfSpan = current.width / 2;
    const fixedAlong = edge === 'start'
      ? centerProjection.along + currentHalfSpan
      : centerProjection.along - currentHalfSpan;
    const minSpan = 4;
    let startAlong = edge === 'start'
      ? Math.min(pointerProjection.along, fixedAlong - minSpan)
      : Math.max(0, fixedAlong);
    let endAlong = edge === 'start'
      ? Math.min(wallAxis.length, fixedAlong)
      : Math.max(pointerProjection.along, fixedAlong + minSpan);
    startAlong = Math.max(0, startAlong);
    endAlong = Math.min(wallAxis.length, endAlong);
    if (endAlong - startAlong < minSpan) {
      if (edge === 'start') {
        startAlong = Math.max(0, endAlong - minSpan);
      } else {
        endAlong = Math.min(wallAxis.length, startAlong + minSpan);
      }
    }

    const span = Math.max(minSpan, endAlong - startAlong);
    const centerAlong = startAlong + span / 2;
    const centerX = wallAxis.x1 + wallAxis.ux * centerAlong;
    const centerY = wallAxis.y1 + wallAxis.uy * centerAlong;
    const nextGeometry = {
      x: centerX - span / 2,
      y: centerY - getWallThicknessPx(wall, floorPlan?.scale_factor) / 2,
      width: span,
      height: getWallThicknessPx(wall, floorPlan?.scale_factor),
      rotation_deg: wallAxis.rotationDeg,
      wall_id: wall.id,
    };

    applyOpeningGeometryUpdate(kind, entity.id, nextGeometry);
  }, [closeHoverPanel, activeWallGeometries, floorPlan?.scale_factor, getOpeningCurrentGeometry, getScaledPointer, applyOpeningGeometryUpdate]);

  const handleWallThicknessDrag = useCallback((wallId, e) => {
    closeHoverPanel();
    const geometry = getWallCurrentGeometry(wallId);
    if (!geometry) {
      return;
    }
    const pointer = getScaledPointer(e);
    const thicknessMm = getDraggedWallThicknessMm(geometry, pointer);

    setEditingWall((prev) => ({ ...(prev || {}), id: wallId, adjustingThickness: true }));
    setModifiedWalls((prev) => ({
      ...prev,
      [wallId]: {
        ...(prev[wallId] || {}),
        thickness: thicknessMm,
      },
    }));
  }, [closeHoverPanel, getDraggedWallThicknessMm, getScaledPointer, getWallCurrentGeometry]);

  const handleWallThicknessDragEnd = useCallback((wallId, e) => {
    saveToHistory();
    const pointer = getScaledPointer(e);
    replaceWallInWorkingSet(wallId, (wall) => ({
      ...wall,
      thickness: getDraggedWallThicknessMm(wall, pointer),
    }));
    setEditingWall(null);
  }, [getDraggedWallThicknessMm, getScaledPointer, replaceWallInWorkingSet, saveToHistory]);

  const updateRoomBoundary = useCallback(async (roomId, boundaryPoints) => {
    try {
      const updated = await elementsApi.updateRoom(roomId, {
        floor_plan_id: parseInt(floorPlanId, 10),
        boundary_points: boundaryPoints,
      });
      setRooms((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      if (selectedElement?.type === 'room' && selectedElement.id === updated.id) {
        setSelectedElement({ type: 'room', id: updated.id, data: updated });
      }
    } catch (error) {
      console.error('Error updating room boundary:', error);
      alert('Не удалось изменить границы помещения.');
    }
  }, [floorPlanId, selectedElement]);

  const handleCanvasElementEnter = useCallback((type, id, e, cursor = 'pointer') => {
    clearHoverCloseTimeout();
    if (e?.target?.getStage) {
      e.target.getStage().container().style.cursor = cursor;
    }
    setHoveredElement({ type, id, x: e.evt.clientX, y: e.evt.clientY });
  }, [clearHoverCloseTimeout]);

  const handleCanvasElementMove = useCallback((type, id, e) => {
    setHoveredElement((prev) => {
      if (!prev || prev.type !== type || prev.id !== id) {
        return { type, id, x: e.evt.clientX, y: e.evt.clientY };
      }
      return {
        ...prev,
        x: e.evt.clientX,
        y: e.evt.clientY,
      };
    });
  }, []);

  const handleCanvasElementLeave = useCallback((e) => {
    if (e?.target?.getStage) {
      e.target.getStage().container().style.cursor = 'default';
    }
    scheduleHoverPanelClose();
  }, [scheduleHoverPanelClose]);

  const getCurrentElementBounds = useCallback((element) => {
    if (!element) {
      return null;
    }
    if (element.type === 'new-wall') {
      const wall = newWalls.find((item) => item.id === element.id);
      if (!wall) {
        return null;
      }
      return getWallBounds(wall, floorPlan?.scale_factor);
    }
    if (element.type === 'wall') {
      const wall = walls.find((item) => item.id === element.id);
      if (!wall) {
        return null;
      }
      const modifications = modifiedWalls[wall.id] || {};
      const x1 = modifications.x1 !== undefined ? modifications.x1 : wall.x1;
      const y1 = modifications.y1 !== undefined ? modifications.y1 : wall.y1;
      const x2 = modifications.x2 !== undefined ? modifications.x2 : wall.x2;
      const y2 = modifications.y2 !== undefined ? modifications.y2 : wall.y2;
      const thicknessMm = modifications.thickness !== undefined ? modifications.thickness : wall.thickness;
      return getWallBounds({
        x1,
        y1,
        x2,
        y2,
        thickness: thicknessMm,
        alignment: modifications.alignment !== undefined ? modifications.alignment : (wall.alignment || 'center'),
      }, floorPlan?.scale_factor);
    }
    if (element.type === 'door') {
      const door = doors.find((item) => item.id === element.id);
      if (!door) {
        return null;
      }
      const current = getOpeningCurrentGeometry('doors', door.id, door);
      const corners = getRotatedRectCorners(current);
      return getBoundingBox(corners.map(({ x, y }) => [x, y]));
    }
    if (element.type === 'new-door') {
      const door = newDoors.find((item) => item.id === element.id);
      if (!door) {
        return null;
      }
      const current = getOpeningCurrentGeometry('new-doors', door.id, door);
      const corners = getRotatedRectCorners(current);
      return getBoundingBox(corners.map(({ x, y }) => [x, y]));
    }
    if (element.type === 'window') {
      const windowItem = windows.find((item) => item.id === element.id);
      if (!windowItem) {
        return null;
      }
      const current = getOpeningCurrentGeometry('windows', windowItem.id, windowItem);
      const corners = getRotatedRectCorners(current);
      return getBoundingBox(corners.map(({ x, y }) => [x, y]));
    }
    if (element.type === 'new-window') {
      const windowItem = newWindows.find((item) => item.id === element.id);
      if (!windowItem) {
        return null;
      }
      const current = getOpeningCurrentGeometry('new-windows', windowItem.id, windowItem);
      const corners = getRotatedRectCorners(current);
      return getBoundingBox(corners.map(({ x, y }) => [x, y]));
    }
    if (element.type === 'stair') {
      const stair = stairs.find((item) => item.id === element.id);
      if (!stair) {
        return null;
      }
      const current = getStairCurrentGeometry(stair.id, stair);
      return { x: current.x, y: current.y, width: current.width, height: current.height };
    }
    if (element.type === 'new-stair') {
      const stair = newStairs.find((item) => item.id === element.id);
      if (!stair) {
        return null;
      }
      return { x: stair.x, y: stair.y, width: stair.width, height: stair.height };
    }
    if (element.type === 'fire-alarm') {
      const alarm = getFireAlarmCurrentGeometry('fire-alarms', element.id);
      if (!alarm) {
        return null;
      }
      return { x: alarm.x - 12, y: alarm.y - 12, width: 24, height: 24 };
    }
    if (element.type === 'new-fire-alarm') {
      const alarm = getFireAlarmCurrentGeometry('new-fire-alarms', element.id);
      if (!alarm) {
        return null;
      }
      return { x: alarm.x - 12, y: alarm.y - 12, width: 24, height: 24 };
    }
    if (element.type === 'signal-instrument') {
      const instrument = visibleSignalInstruments.find((item) => item.id === element.id);
      return getSignalInstrumentBounds(instrument);
    }
    if (element.type === 'room') {
      const room = rooms.find((item) => item.id === element.id);
      if (!room?.boundary_points?.length) {
        return null;
      }
      return getBoundingBox(room.boundary_points);
    }
    return null;
  }, [newWalls, walls, modifiedWalls, floorPlan?.scale_factor, doors, windows, newDoors, newWindows, stairs, newStairs, rooms, getOpeningCurrentGeometry, getStairCurrentGeometry, getFireAlarmCurrentGeometry, visibleSignalInstruments]);

  const selectionViewStep = interactionViewStep;

  const allSelectableElements = useMemo(() => ([
    ...(selectionViewStep === 'walls'
      ? newWalls.map((wall) => ({ type: 'new-wall', id: wall.id }))
      : []),
    ...(selectionViewStep !== 'openings'
      ? walls
        .filter((wall) => !deletedElements.some((del) => del.type === 'walls' && del.id === wall.id))
        .map((wall) => ({ type: 'wall', id: wall.id }))
      : []),
    ...(selectionViewStep === 'walls'
      ? newStairs.map((stair) => ({ type: 'new-stair', id: stair.id }))
      : []),
    ...(selectionViewStep === 'walls'
      ? stairs
        .filter((stair) => !deletedElements.some((del) => del.type === 'stairs' && del.id === stair.id))
        .map((stair) => ({ type: 'stair', id: stair.id }))
      : []),
    ...((selectionViewStep === 'openings' || selectionViewStep === 'rooms')
      ? newDoors.map((door) => ({ type: 'new-door', id: door.id }))
      : []),
    ...((selectionViewStep === 'openings' || selectionViewStep === 'rooms')
      ? doors
        .filter((door) => !deletedElements.some((del) => del.type === 'doors' && del.id === door.id))
        .map((door) => ({ type: 'door', id: door.id }))
      : []),
    ...((selectionViewStep === 'openings' || selectionViewStep === 'rooms')
      ? newWindows.map((windowItem) => ({ type: 'new-window', id: windowItem.id }))
      : []),
    ...((selectionViewStep === 'openings' || selectionViewStep === 'rooms')
      ? windows
        .filter((windowItem) => !deletedElements.some((del) => del.type === 'windows' && del.id === windowItem.id))
        .map((windowItem) => ({ type: 'window', id: windowItem.id }))
      : []),
    ...(selectionViewStep === 'rooms'
      ? rooms
        .filter((room) => !deletedElements.some((del) => del.type === 'rooms' && del.id === room.id))
        .map((room) => ({ type: 'room', id: room.id }))
      : []),
    ...((selectionViewStep === 'fire_alarms' || selectionViewStep === 'devices_cables')
      ? fireAlarms
        .filter((alarm) => !deletedElements.some((del) => del.type === 'fire-alarms' && del.id === alarm.id))
        .map((alarm) => ({ type: 'fire-alarm', id: alarm.id }))
      : []),
    ...((selectionViewStep === 'fire_alarms' || selectionViewStep === 'devices_cables')
      ? newFireAlarms.map((alarm) => ({ type: 'new-fire-alarm', id: alarm.id }))
      : []),
    ...(selectionViewStep === 'devices_cables'
      ? visibleSignalInstruments.map((instrument) => ({ type: 'signal-instrument', id: instrument.id }))
      : []),
  ]), [selectionViewStep, newWalls, walls, newStairs, stairs, newDoors, doors, newWindows, windows, rooms, fireAlarms, newFireAlarms, deletedElements, visibleSignalInstruments]);

  const selectedGroupBounds = useMemo(() => {
    if (!selectedElements.length) {
      return null;
    }
    const boxes = selectedElements.map((element) => getCurrentElementBounds(element)).filter(Boolean);
    if (!boxes.length) {
      return null;
    }
    const minX = Math.min(...boxes.map((box) => box.x));
    const minY = Math.min(...boxes.map((box) => box.y));
    const maxX = Math.max(...boxes.map((box) => box.x + box.width));
    const maxY = Math.max(...boxes.map((box) => box.y + box.height));
    return { x: minX, y: minY, width: maxX - minX, height: maxY - minY };
  }, [selectedElements, getCurrentElementBounds]);

  const applyTransformToSelected = useCallback((transform) => {
    const { dx = 0, dy = 0, scale = 1, centerX = 0, centerY = 0 } = transform;
    const nextModifiedWalls = { ...modifiedWalls };
    const nextModifiedElements = { ...modifiedElements };
    let roomsToUpdate = [];

    selectedElements.forEach((element) => {
      if (element.type === 'new-wall') {
        setNewWalls((prev) => prev.map((wall) => (
          wall.id === element.id
            ? {
              ...wall,
              x1: centerX + (wall.x1 - centerX) * scale + dx,
              y1: centerY + (wall.y1 - centerY) * scale + dy,
              x2: centerX + (wall.x2 - centerX) * scale + dx,
              y2: centerY + (wall.y2 - centerY) * scale + dy,
            }
            : wall
        )));
        return;
      }
      if (element.type === 'wall') {
        const wall = walls.find((item) => item.id === element.id);
        if (!wall) {
          return;
        }
        const mod = nextModifiedWalls[wall.id] || {};
        const x1 = mod.x1 ?? wall.x1;
        const y1 = mod.y1 ?? wall.y1;
        const x2 = mod.x2 ?? wall.x2;
        const y2 = mod.y2 ?? wall.y2;
        nextModifiedWalls[wall.id] = {
          ...mod,
          x1: centerX + (x1 - centerX) * scale + dx,
          y1: centerY + (y1 - centerY) * scale + dy,
          x2: centerX + (x2 - centerX) * scale + dx,
          y2: centerY + (y2 - centerY) * scale + dy,
          thickness: (mod.thickness ?? wall.thickness) * scale,
        };
        return;
      }
      if (element.type === 'new-stair') {
        setNewStairs((prev) => prev.map((stair) => {
          if (stair.id !== element.id) {
            return stair;
          }
          const nextWidth = Math.max(4, (stair.width ?? 0) * scale);
          const nextHeight = Math.max(4, (stair.height ?? 0) * scale);
          return {
            ...stair,
            x: centerX + ((stair.x ?? 0) - centerX) * scale + dx,
            y: centerY + ((stair.y ?? 0) - centerY) * scale + dy,
            width: nextWidth,
            height: nextHeight,
            step_axis: nextWidth >= nextHeight ? 'horizontal' : 'vertical',
          };
        }));
        return;
      }
      if (element.type === 'new-door' || element.type === 'new-window') {
        const kind = element.type === 'new-door' ? 'new-doors' : 'new-windows';
        const current = getOpeningCurrentGeometry(kind, element.id);
        if (!current) {
          return;
        }
        const transformed = {
          ...current,
          x: centerX + (current.x - centerX) * scale + dx,
          y: centerY + (current.y - centerY) * scale + dy,
          width: Math.max(4, (current.width ?? 0) * scale),
          height: Math.max(4, (current.height ?? 0) * scale),
        };
        const normalized = normalizeOpeningToWall(
          transformed,
          activeWallGeometries,
          floorPlan?.scale_factor,
          { preferredWallId: current.wall_id },
        );
        if (normalized) {
          applyOpeningGeometryUpdate(kind, element.id, normalized);
        }
        return;
      }
      if (element.type === 'new-fire-alarm') {
        const current = getFireAlarmCurrentGeometry('new-fire-alarms', element.id);
        if (!current) {
          return;
        }
        setNewFireAlarms((prev) => prev.map((item) => (
          item.id === element.id
            ? {
              ...item,
              x: centerX + (current.x - centerX) * scale + dx,
              y: centerY + (current.y - centerY) * scale + dy,
            }
            : item
        )));
        return;
      }
      if (element.type === 'door' || element.type === 'window' || element.type === 'fire-alarm' || element.type === 'stair') {
        const collection = element.type === 'door'
          ? doors
          : (element.type === 'window'
            ? windows
            : (element.type === 'stair' ? stairs : fireAlarms));
        const keyPrefix = element.type === 'door'
          ? 'doors'
          : (element.type === 'window'
            ? 'windows'
            : (element.type === 'stair' ? 'stairs' : 'fire-alarms'));
        const entity = collection.find((item) => item.id === element.id);
        if (!entity) {
          return;
        }
        const key = `${keyPrefix}-${entity.id}`;
        const mod = nextModifiedElements[key] || {};
        const x = mod.x ?? entity.x;
        const y = mod.y ?? entity.y;
        const width = mod.width ?? entity.width ?? 0;
        const height = mod.height ?? entity.height ?? 0;
        nextModifiedElements[key] = {
          ...mod,
          x: centerX + (x - centerX) * scale + dx,
          y: centerY + (y - centerY) * scale + dy,
          ...(entity.width !== undefined ? { width: Math.max(4, width * scale) } : {}),
          ...(entity.height !== undefined ? { height: Math.max(4, height * scale) } : {}),
          ...(entity.step_count !== undefined ? { step_axis: width >= height ? 'horizontal' : 'vertical' } : {}),
        };
        return;
      }
      if (element.type === 'room') {
        const room = rooms.find((item) => item.id === element.id);
        if (!room?.boundary_points?.length) {
          return;
        }
        const transformed = room.boundary_points.map(([x, y]) => ([
          centerX + (x - centerX) * scale + dx,
          centerY + (y - centerY) * scale + dy,
        ]));
        roomsToUpdate.push({ id: room.id, boundary_points: transformed });
      }
    });

    setModifiedWalls(nextModifiedWalls);
    setModifiedElements(nextModifiedElements);
    setHasUnsavedChanges(true);
    if (roomsToUpdate.length) {
      roomsToUpdate.forEach((update) => {
        updateRoomBoundary(update.id, update.boundary_points);
      });
    }
  }, [selectedElements, modifiedWalls, modifiedElements, walls, doors, windows, stairs, fireAlarms, rooms, updateRoomBoundary, getOpeningCurrentGeometry, getFireAlarmCurrentGeometry, activeWallGeometries, floorPlan?.scale_factor, applyOpeningGeometryUpdate, setNewFireAlarms]);

  const handleDeleteSelectedElements = useCallback(() => {
    if (!selectedElements.length) {
      return;
    }
    saveToHistory();
    const removedNewWalls = selectedElements.filter((element) => element.type === 'new-wall').length;
    const removedNewStairs = selectedElements.filter((element) => element.type === 'new-stair').length;
    const removedNewDoors = selectedElements.filter((element) => element.type === 'new-door').length;
    const removedNewWindows = selectedElements.filter((element) => element.type === 'new-window').length;
    const removedNewFireAlarms = selectedElements.filter((element) => element.type === 'new-fire-alarm').length;
    const removedPersistedElements = selectedElements.some((element) => !['new-wall', 'new-stair', 'new-door', 'new-window', 'new-fire-alarm'].includes(element.type));
    selectedElements.forEach((element) => {
      if (element.type === 'new-wall') setNewWalls((prev) => prev.filter((item) => item.id !== element.id));
      if (element.type === 'wall') handleDeleteElement('walls', element.id);
      if (element.type === 'stair') handleDeleteElement('stairs', element.id);
      if (element.type === 'new-stair') setNewStairs((prev) => prev.filter((item) => item.id !== element.id));
      if (element.type === 'new-door') setNewDoors((prev) => prev.filter((item) => item.id !== element.id));
      if (element.type === 'new-window') setNewWindows((prev) => prev.filter((item) => item.id !== element.id));
      if (element.type === 'new-fire-alarm') setNewFireAlarms((prev) => prev.filter((item) => item.id !== element.id));
      if (element.type === 'door') handleDeleteElement('doors', element.id);
      if (element.type === 'window') handleDeleteElement('windows', element.id);
      if (element.type === 'room') handleDeleteElement('rooms', element.id);
      if (element.type === 'fire-alarm') handleDeleteElement('fire-alarms', element.id);
    });
    setSelectedElement(null);
    setSelectedElements([]);
    setHasUnsavedChanges(
      removedPersistedElements ||
      (newWalls.length - removedNewWalls) > 0 ||
      (newStairs.length - removedNewStairs) > 0 ||
      (newDoors.length - removedNewDoors) > 0 ||
      (newWindows.length - removedNewWindows) > 0 ||
      (newFireAlarms.length - removedNewFireAlarms) > 0 ||
      deletedElements.length > 0 ||
      Object.keys(modifiedWalls).length > 0 ||
      Object.keys(modifiedElements).length > 0,
    );
  }, [selectedElements, saveToHistory, handleDeleteElement, newWalls.length, newStairs.length, newDoors.length, newWindows.length, newFireAlarms.length, deletedElements.length, modifiedWalls, modifiedElements, setNewFireAlarms]);

  const handleGroupDragEnd = useCallback((e) => {
    if (!selectedGroupBounds) {
      return;
    }
    const dx = e.target.x() - selectedGroupBounds.x;
    const dy = e.target.y() - selectedGroupBounds.y;
    e.target.position({ x: selectedGroupBounds.x, y: selectedGroupBounds.y });
    applyTransformToSelected({ dx, dy, scale: 1, centerX: selectedGroupBounds.x, centerY: selectedGroupBounds.y });
  }, [selectedGroupBounds, applyTransformToSelected]);

  const handleGroupScaleHandleDragEnd = useCallback((e) => {
    if (!selectedGroupBounds) {
      return;
    }
    const pointer = getScaledPointer(e);
    const centerX = selectedGroupBounds.x + selectedGroupBounds.width / 2;
    const centerY = selectedGroupBounds.y + selectedGroupBounds.height / 2;
    const baseDx = selectedGroupBounds.width / 2;
    const baseDy = selectedGroupBounds.height / 2;
    const baseDistance = Math.sqrt(baseDx * baseDx + baseDy * baseDy);
    const nextDistance = Math.sqrt((pointer.x - centerX) ** 2 + (pointer.y - centerY) ** 2);
    const scale = Math.max(0.1, Math.min(5, nextDistance / Math.max(1, baseDistance)));
    e.target.position({
      x: selectedGroupBounds.x + selectedGroupBounds.width,
      y: selectedGroupBounds.y + selectedGroupBounds.height,
    });
    applyTransformToSelected({ dx: 0, dy: 0, scale, centerX, centerY });
  }, [selectedGroupBounds, getScaledPointer, applyTransformToSelected]);

  const endStagePan = useCallback(() => {
    stagePanStartRef.current = null;
    setIsStagePanning(false);
  }, []);

  useEffect(() => {
    if (!isStagePanning) {
      return undefined;
    }
    const handlePointerRelease = () => {
      endStagePan();
    };
    window.addEventListener('mouseup', handlePointerRelease);
    window.addEventListener('pointerup', handlePointerRelease);
    window.addEventListener('blur', handlePointerRelease);
    return () => {
      window.removeEventListener('mouseup', handlePointerRelease);
      window.removeEventListener('pointerup', handlePointerRelease);
      window.removeEventListener('blur', handlePointerRelease);
    };
  }, [endStagePan, isStagePanning]);

  const handleStageMouseDown = useCallback((e) => {
    const isBackground = e.target === e.target.getStage()
      || e.target === e.target.getLayer()
      || e.target?.attrs?.id === 'editor-layer'
      || e.target?.className === 'Image';
    if (!isBackground) {
      return;
    }
    if (selectionLockActive && !(mergeModeActive && selectedTool === 'multi-select')) {
      clearCanvasSelection();
      closeHoverPanel();
      return;
    }
    const point = getScaledPointer(e);
    const pointer = e.target.getStage().getPointerPosition();
    if (!pointer) {
      return;
    }
    if (selectedTool === 'select' && userZoom > 1) {
      setIsStagePanning(true);
      stagePanStartRef.current = {
        pointerX: pointer.x,
        pointerY: pointer.y,
        startX: stagePanOffset.x,
        startY: stagePanOffset.y,
      };
      stagePanMovedRef.current = false;
      return;
    }
    if (selectedTool === 'multi-select') {
      setIsSelecting(true);
      setSelectionRect({ x: point.x, y: point.y, width: 0, height: 0 });
    }
    if (selectedTool === 'room-zone' && viewStep === 'rooms' && selectedElement?.type === 'room') {
      setIsRoomZoneDrawing(true);
      setRoomZoneRect({ x: point.x, y: point.y, width: 0, height: 0 });
    }
  }, [getScaledPointer, selectedTool, selectedElement, viewStep, selectionLockActive, mergeModeActive, clearCanvasSelection, closeHoverPanel, userZoom, stagePanOffset.x, stagePanOffset.y]);

  const handleStageMouseUp = useCallback(async () => {
    if (isStagePanning) {
      endStagePan();
      return;
    }
    if (isSelecting && selectionRect) {
      const normalized = normalizeRect(selectionRect);
      const selectionSource = mergeModeActive
        ? allSelectableElements.filter((element) => element.type === 'fire-alarm' || element.type === 'new-fire-alarm')
        : allSelectableElements;
      const selected = selectionSource
        .filter((element) => rectsIntersect(normalized, getCurrentElementBounds(element)))
        .map((element) => ({ type: element.type, id: element.id }));
      const nextSelected = mergeModeActive && shiftPressed
        ? [
          ...selectedElements.filter((existing) => !selected.some((item) => item.type === existing.type && item.id === existing.id)),
          ...selectedElements.filter((existing) => selected.some((item) => item.type === existing.type && item.id === existing.id)),
          ...selected.filter((item) => !selectedElements.some((existing) => existing.type === item.type && existing.id === item.id)),
        ]
        : selected;
      setSelectedElements(nextSelected);
      if (!mergeModeActive && nextSelected.length === 1) {
        const only = nextSelected[0];
        const source = only.type === 'new-wall' ? newWalls
          : only.type === 'wall' ? walls
          : only.type === 'new-door' ? newDoors
          : only.type === 'door' ? doors
          : only.type === 'new-window' ? newWindows
          : only.type === 'window' ? windows
          : only.type === 'new-stair' ? newStairs
          : only.type === 'stair' ? stairs
          : only.type === 'room' ? rooms
          : only.type === 'new-fire-alarm' ? newFireAlarms
          : fireAlarms;
        const data = source.find((item) => item.id === only.id);
        setSelectedElement({ type: only.type, id: only.id, data: data || null });
      } else {
        setSelectedElement(mergeModeActive && mergeInstrumentId
          ? visibleSignalInstruments.find((item) => item.id === mergeInstrumentId)
            ? {
              type: 'signal-instrument',
              id: mergeInstrumentId,
              data: visibleSignalInstruments.find((item) => item.id === mergeInstrumentId) || null,
            }
            : null
          : null);
      }
      setSelectionRect(null);
      setIsSelecting(false);
    }

    if (isRoomZoneDrawing && roomZoneRect && selectedElement?.type === 'room') {
      const normalized = normalizeRect(roomZoneRect);
      if (normalized && normalized.width > 2 && normalized.height > 2) {
        const room = rooms.find((item) => item.id === selectedElement.id);
        const roomBox = room?.boundary_points?.length ? getBoundingBox(room.boundary_points) : null;
        if (room && roomBox) {
          const union = {
            x: Math.min(roomBox.x, normalized.x),
            y: Math.min(roomBox.y, normalized.y),
            width: Math.max(roomBox.x + roomBox.width, normalized.x + normalized.width) - Math.min(roomBox.x, normalized.x),
            height: Math.max(roomBox.y + roomBox.height, normalized.y + normalized.height) - Math.min(roomBox.y, normalized.y),
          };
          await updateRoomBoundary(room.id, [
            [union.x, union.y],
            [union.x + union.width, union.y],
            [union.x + union.width, union.y + union.height],
            [union.x, union.y + union.height],
          ]);
        }
      }
      setRoomZoneRect(null);
      setIsRoomZoneDrawing(false);
    }
  }, [
    isStagePanning,
    isSelecting,
    selectionRect,
    allSelectableElements,
    getCurrentElementBounds,
    mergeInstrumentId,
    mergeModeActive,
    newWalls,
    walls,
    newDoors,
    doors,
    newWindows,
    windows,
    newStairs,
    stairs,
    rooms,
    fireAlarms,
    newFireAlarms,
    selectedElements,
    shiftPressed,
    visibleSignalInstruments,
    isRoomZoneDrawing,
    roomZoneRect,
    selectedElement,
    updateRoomBoundary,
    endStagePan,
  ]);

  const handleRenderedImageLoad = useCallback((nextImageSize) => {
    const nextWidth = Number(nextImageSize?.width || 0);
    const nextHeight = Number(nextImageSize?.height || 0);
    if (!nextWidth || !nextHeight) {
      return;
    }
    setRenderedImageSize((prev) => (
      prev?.url === displayedImageUrl && prev?.width === nextWidth && prev?.height === nextHeight
        ? prev
        : { url: displayedImageUrl, width: nextWidth, height: nextHeight }
    ));
  }, [displayedImageUrl]);
  const visibleDimensions = dimensions.filter(dim => !deletedElements.some(del => del.type === 'dimensions' && del.id === dim.id));
  const roomDimensionsMap = visibleDimensions.reduce((acc, dim) => {
    if (dim.room_id === null || dim.room_id === undefined) {
      return acc;
    }
    if (!acc[dim.room_id]) {
      acc[dim.room_id] = [];
    }
    acc[dim.room_id].push(dim);
    return acc;
  }, {});
  const pipelineSteps = [
    { key: 'original', title: '0. Оригинал' },
    { key: 'walls', title: '1. Стены' },
    { key: 'openings', title: '2. Проемы' },
    { key: 'rooms', title: '3. Помещения' },
    { key: 'zkspc', title: '4. ЗКСПС' },
  ];
  const getStepStatus = (stepKey) => pipelineState?.steps?.[stepKey]?.status || 'draft';
  const wallsValidated = getStepStatus('walls') === 'validated';
  const openingsValidated = getStepStatus('openings') === 'validated';
  const roomsValidated = getStepStatus('rooms') === 'validated';
  const zkspcValidated = getStepStatus('zkspc') === 'validated';
  const canSubmitRecognitionFeedback = Boolean(recognitionMeta?.id) && recognitionMeta?.status === 'completed';
  const currentBranchState = pipelineState?.branches?.[currentSignalSystem] || { active_step: 'fire_alarms', steps: {} };
  const fireAlarmStepUnlocked = zkspcValidated;
  const devicesCablesStepUnlocked = zkspcValidated;
  const editorSteps = [
    ...pipelineSteps,
    { key: 'fire_alarms', title: '5. Пожарные извещатели', editorOnly: true },
    { key: 'devices_cables', title: '6. Приборы и кабели', editorOnly: true },
  ];
  const activePipelineStep = zkspcValidated
    ? (currentBranchState?.active_step || 'fire_alarms')
    : roomsValidated
      ? 'zkspc'
      : (pipelineState?.active_step || 'walls');
  const currentViewStep = viewStep || activePipelineStep || 'original';
  useEffect(() => {
    if (currentViewStep !== 'devices_cables' && mergeInstrumentId !== null) {
      setMergeInstrumentId(null);
      setSelectedElements([]);
    }
  }, [currentViewStep, mergeInstrumentId]);
  const useArchitectBlack = ['rooms', 'zkspc', 'fire_alarms', 'devices_cables'].includes(currentViewStep);
  const isPostZkspcView = currentViewStep === 'fire_alarms' || currentViewStep === 'devices_cables';
  const showBackgroundImage = ['original', 'walls', 'openings', 'rooms'].includes(currentViewStep);
  const showWallsOnCanvas = currentViewStep !== 'original' && (currentViewStep === 'walls' || wallsValidated);
  const wallsInteractive = currentViewStep === 'walls';
  const showStairsOnCanvas = currentViewStep === 'walls' || currentViewStep === 'fire_alarms' || currentViewStep === 'devices_cables';
  const showOpeningsOnCanvas = (currentViewStep === 'openings' || currentViewStep === 'rooms' || currentViewStep === 'zkspc' || currentViewStep === 'fire_alarms' || currentViewStep === 'devices_cables')
    && (currentViewStep === 'openings' || openingsValidated);
  const showRoomsOnCanvas = currentViewStep === 'rooms' || currentViewStep === 'zkspc';
  const showZkspcOverlayOnCanvas = currentViewStep === 'zkspc';
  const showDimensionsOnCanvas = currentViewStep === 'walls';
  const showFireAlarmsOnCanvas = currentViewStep === 'fire_alarms' || currentViewStep === 'devices_cables';
  const showCableRoutesOnCanvas = currentViewStep === 'devices_cables';
  const showSignalInstrumentsOnCanvas = currentViewStep === 'devices_cables';
  const showRoomsSidebar = currentViewStep === 'rooms';
  const showZkspcSidebar = currentViewStep === 'zkspc';
  const showFireAlarmSidebar = currentViewStep === 'fire_alarms';
  const showDevicesCablesSidebar = currentViewStep === 'devices_cables';
  const visibleWalls = walls.filter((wall) => !deletedElements.some((del) => del.type === 'walls' && del.id === wall.id));
  const visibleStairs = stairs.filter((stair) => !deletedElements.some((del) => del.type === 'stairs' && del.id === stair.id));
  const visibleDoors = doors.filter((door) => !deletedElements.some((del) => del.type === 'doors' && del.id === door.id));
  const visibleWindows = windows.filter((windowItem) => !deletedElements.some((del) => del.type === 'windows' && del.id === windowItem.id));
  const visibleRooms = rooms.filter((room) => !deletedElements.some((del) => del.type === 'rooms' && del.id === room.id));
  const zkspcStyleMap = useMemo(
    () => buildZkspcStyleMap(currentZkspcZones, visibleRooms, floorPlan?.id),
    [currentZkspcZones, visibleRooms, floorPlan?.id],
  );
  const zoneLabelAnchors = useMemo(() => (
    currentZkspcZones.reduce((acc, zone) => {
      const zoneRooms = visibleRooms.filter((room) => (zone.room_ids || []).includes(room.id));
      if (!zoneRooms.length) {
        return acc;
      }
      const centers = zoneRooms
        .map((room) => getRoomDisplayCenter(room))
        .filter(Boolean);
      if (!centers.length) {
        return acc;
      }
      acc[zone.id || zone.zone_number] = {
        x: centers.reduce((sum, point) => sum + point.x, 0) / centers.length,
        y: centers.reduce((sum, point) => sum + point.y, 0) / centers.length,
      };
      return acc;
    }, {})
  ), [currentZkspcZones, visibleRooms]);
  const wallDisplayNumberMap = buildDisplayNumberMap([...visibleWalls, ...newWalls]);
  const stairDisplayNumberMap = buildDisplayNumberMap([...visibleStairs, ...newStairs]);
  const doorDisplayNumberMap = buildDisplayNumberMap([...visibleDoors, ...newDoors]);
  const windowDisplayNumberMap = buildDisplayNumberMap([...visibleWindows, ...newWindows]);
  const roomDisplayNumberMap = buildDisplayNumberMap(visibleRooms);
  const visiblePersistedFireAlarms = useMemo(() => (
    branchFireAlarms
      .filter((alarm) => !deletedElements.some((del) => del.type === 'fire-alarms' && del.id === alarm.id))
      .map((alarm) => ({ kind: 'fire-alarms', alarm: getFireAlarmCurrentGeometry('fire-alarms', alarm.id, alarm) }))
      .filter((entry) => entry.alarm)
  ), [branchFireAlarms, deletedElements, getFireAlarmCurrentGeometry]);
  const visibleNewFireAlarms = useMemo(() => (
    newFireAlarms
      .map((alarm) => ({ kind: 'new-fire-alarms', alarm: getFireAlarmCurrentGeometry('new-fire-alarms', alarm.id, alarm) }))
      .filter((entry) => entry.alarm)
  ), [newFireAlarms, getFireAlarmCurrentGeometry]);
  const visibleFireAlarmItems = useMemo(
    () => [...visiblePersistedFireAlarms, ...visibleNewFireAlarms],
    [visiblePersistedFireAlarms, visibleNewFireAlarms],
  );
  const fireAlarmNumberMap = buildDisplayNumberMap(visibleFireAlarmItems.map((entry) => entry.alarm));
  const getFireAlarmCode = useCallback((alarm, overrides = {}) => (
    getFireAlarmDisplayCode(alarm, floorPlan?.floor_number, fireAlarmNumberMap[alarm.id] ?? 1, overrides)
  ), [fireAlarmNumberMap, floorPlan?.floor_number]);
  const visibleSignalInstruments = useMemo(
    () => getBranchSignalInstruments(signalInstruments, currentSignalSystem),
    [signalInstruments, currentSignalSystem],
  );
  const visibleCableRoutes = useMemo(
    () => getBranchCableRoutes(cableRoutes, currentSignalSystem),
    [cableRoutes, currentSignalSystem],
  );
  useEffect(() => {
    if (mergeInstrumentId && !visibleSignalInstruments.some((instrument) => instrument.id === mergeInstrumentId)) {
      setMergeInstrumentId(null);
      setSelectedElements([]);
    }
  }, [mergeInstrumentId, visibleSignalInstruments]);
  const signalBranchSummary = useMemo(
    () => getSignalBranchSummary({
      fireAlarms: visibleFireAlarmItems.map((entry) => entry.alarm),
      cableRoutes: visibleCableRoutes,
      systemType: currentSignalSystem,
    }),
    [visibleFireAlarmItems, visibleCableRoutes, currentSignalSystem],
  );
  const doorNumberMap = Object.fromEntries(
    doors
      .filter((door) => !deletedElements.some((del) => del.type === 'doors' && del.id === door.id))
      .sort((a, b) => a.id - b.id)
      .map((door, idx) => [door.id, idx + 1])
  );
  const windowNumberMap = Object.fromEntries(
    windows
      .filter((windowItem) => !deletedElements.some((del) => del.type === 'windows' && del.id === windowItem.id))
      .sort((a, b) => a.id - b.id)
      .map((windowItem, idx) => [windowItem.id, idx + 1])
  );

  const calibrationPixelDistance = calibrationDraft.start && calibrationDraft.end
    ? Math.hypot(
      calibrationDraft.end.x - calibrationDraft.start.x,
      calibrationDraft.end.y - calibrationDraft.start.y,
    )
    : null;
  const calibrationScalePreview = calibrationPixelDistance && Number(calibrationDraft.distance_m) > 0
    ? (Number(calibrationDraft.distance_m) * 1000) / calibrationPixelDistance
    : null;
  const visibleFireAlarmGroups = useMemo(() => {
    const grouped = groupFireAlarmsByZone(visibleFireAlarmItems.map((entry) => entry.alarm), currentZkspcZones);
    return Object.entries(grouped)
      .map(([key, value]) => ({
        key,
        zone: value.zone,
        items: value.items.map((alarm) => ({
          kind: visibleNewFireAlarms.some((entry) => entry.alarm.id === alarm.id) ? 'new-fire-alarms' : 'fire-alarms',
          alarm,
        })),
      }))
      .sort((left, right) => Number(left.zone?.zone_number || 9999) - Number(right.zone?.zone_number || 9999));
  }, [visibleFireAlarmItems, visibleNewFireAlarms, currentZkspcZones]);

  const suppressedWallIds = useMemo(() => {
    const activeWalls = walls
      .filter((wall) => !deletedElements.some((del) => del.type === 'walls' && del.id === wall.id))
      .map((wall) => {
        const mod = modifiedWalls[wall.id] || {};
        const x1 = mod.x1 ?? wall.x1;
        const y1 = mod.y1 ?? wall.y1;
        const x2 = mod.x2 ?? wall.x2;
        const y2 = mod.y2 ?? wall.y2;
        const length = Math.hypot(x2 - x1, y2 - y1);
        return { id: wall.id, x1, y1, x2, y2, length };
      })
      .filter((wall) => wall.length > 1e-6);

    const toSuppress = new Set();
    const distancePointToLine = (px, py, x1, y1, x2, y2) => {
      const dx = x2 - x1;
      const dy = y2 - y1;
      const denom = Math.sqrt(dx * dx + dy * dy) || 1;
      return Math.abs((px - x1) * dy - (py - y1) * dx) / denom;
    };

    for (let i = 0; i < activeWalls.length; i += 1) {
      for (let j = i + 1; j < activeWalls.length; j += 1) {
        const a = activeWalls[i];
        const b = activeWalls[j];
        const angleA = Math.atan2(a.y2 - a.y1, a.x2 - a.x1);
        const angleB = Math.atan2(b.y2 - b.y1, b.x2 - b.x1);
        let angleDiff = Math.abs(angleA - angleB);
        angleDiff = Math.min(angleDiff, Math.abs(Math.PI - angleDiff));
        if (angleDiff > (Math.PI / 180) * 3) {
          continue;
        }
        const da = distancePointToLine(a.x1, a.y1, b.x1, b.y1, b.x2, b.y2);
        const db = distancePointToLine(a.x2, a.y2, b.x1, b.y1, b.x2, b.y2);
        if (Math.max(da, db) > 2) {
          continue;
        }
        if (a.length <= b.length) {
          toSuppress.add(a.id);
        } else {
          toSuppress.add(b.id);
        }
      }
    }
    return toSuppress;
  }, [walls, deletedElements, modifiedWalls]);

  const getStepColor = (status) => {
    if (status === 'validated') return '#0f8f7c';
    if (status === 'stale') return '#f08b32';
    if (status === 'locked') return '#8e877d';
    return '#8e877d';
  };
  const stageRect = stageContainerRef.current?.getBoundingClientRect();
  const stagePlanBounds = useMemo(() => {
    if (!containerSize.width || !containerSize.height) {
      return null;
    }
    const corners = [
      viewportPointToPlan({ x: 0, y: 0 }, viewTransform),
      viewportPointToPlan({ x: containerSize.width, y: 0 }, viewTransform),
      viewportPointToPlan({ x: containerSize.width, y: containerSize.height }, viewTransform),
      viewportPointToPlan({ x: 0, y: containerSize.height }, viewTransform),
    ];
    return getBoundingBox(corners.map(({ x, y }) => [x, y]));
  }, [containerSize.height, containerSize.width, viewTransform]);
  const drawingLabelBaseObstacles = useMemo(() => {
    if (!showFireAlarmsOnCanvas && !showCableRoutesOnCanvas && !showSignalInstrumentsOnCanvas) {
      return [];
    }
    const obstacles = [];
    [...visibleWalls, ...newWalls].forEach((wall) => {
      const current = wall.id && !String(wall.id).startsWith('temp_')
        ? getWallCurrentGeometry(wall.id)
        : wall;
      if (!current) {
        return;
      }
      const thicknessPx = getWallThicknessPx(current, floorPlan?.scale_factor);
      obstacles.push(padRect({
        x: Math.min(current.x1, current.x2),
        y: Math.min(current.y1, current.y2),
        width: Math.abs(current.x2 - current.x1) || 1,
        height: Math.abs(current.y2 - current.y1) || 1,
      }, Math.max(4, thicknessPx / 2)));
    });
    [...visibleDoors, ...newDoors].forEach((door) => {
      const current = getOpeningCurrentGeometry(
        String(door.id).startsWith('temp_') ? 'new-doors' : 'doors',
        door.id,
        door,
      );
      const bounds = getRotatedBounds(current);
      if (bounds) {
        obstacles.push(padRect(bounds, 4));
      }
    });
    [...visibleWindows, ...newWindows].forEach((windowItem) => {
      const current = getOpeningCurrentGeometry(
        String(windowItem.id).startsWith('temp_') ? 'new-windows' : 'windows',
        windowItem.id,
        windowItem,
      );
      const bounds = getRotatedBounds(current);
      if (bounds) {
        obstacles.push(padRect(bounds, 4));
      }
    });
    currentStairGeometries.forEach((stair) => {
      const bounds = getRotatedBounds(stair);
      if (bounds) {
        obstacles.push(padRect(bounds, 6));
      }
    });
    visibleSignalInstruments.forEach((instrument) => {
      const bounds = getSignalInstrumentBounds(instrument);
      if (bounds) {
        obstacles.push(bounds);
      }
    });
    visibleFireAlarmItems.forEach(({ kind, alarm }) => {
      const current = getFireAlarmCurrentGeometry(kind, alarm.id, alarm);
      if (!current) {
        return;
      }
      obstacles.push(getFireAlarmBounds(current));
    });
    return obstacles.filter(Boolean);
  }, [
    currentStairGeometries,
    floorPlan?.scale_factor,
    getFireAlarmCurrentGeometry,
    getOpeningCurrentGeometry,
    getWallCurrentGeometry,
    newDoors,
    newWalls,
    newWindows,
    showCableRoutesOnCanvas,
    showFireAlarmsOnCanvas,
    showSignalInstrumentsOnCanvas,
    visibleDoors,
    visibleFireAlarmItems,
    visibleSignalInstruments,
    visibleWalls,
    visibleWindows,
  ]);
  const fireAlarmLabelLayouts = useMemo(() => {
    const layouts = {};
    const placed = [];
    visibleFireAlarmItems.forEach(({ kind, alarm }) => {
      const current = getFireAlarmCurrentGeometry(kind, alarm.id, alarm);
      if (!current) {
        return;
      }
      const label = getFireAlarmCode(current);
      const savedRect = getLabelRectFromOffset(current.x, current.y, label, 10, current.label_dx, current.label_dy);
      const rect = savedRect || chooseSymbolLabelRect({
        anchorX: current.x,
        anchorY: current.y,
        text: label,
        fontSize: 10,
        symbolHalfWidth: 14,
        symbolHalfHeight: 14,
        obstacles: [...drawingLabelBaseObstacles, ...placed],
        bounds: stagePlanBounds,
      });
      layouts[current.id] = rect;
      placed.push(rect);
    });
    return layouts;
  }, [
    drawingLabelBaseObstacles,
    getFireAlarmCode,
    getFireAlarmCurrentGeometry,
    stagePlanBounds,
    visibleFireAlarmItems,
  ]);
  const signalInstrumentLabelLayouts = useMemo(() => {
    const layouts = {};
    const placed = [];
    visibleSignalInstruments.forEach((instrument) => {
      const label = getInstrumentLabelText(instrument);
      if (!label) {
        return;
      }
      const bounds = getSignalInstrumentBounds(instrument);
      const savedRect = getLabelRectFromOffset(
        instrument.x,
        instrument.y,
        label,
        11,
        instrument.label_dx,
        instrument.label_dy,
      );
      const rect = savedRect || chooseSymbolLabelRect({
        anchorX: instrument.x,
        anchorY: instrument.y,
        text: label,
        fontSize: 11,
        symbolHalfWidth: bounds.width / 2,
        symbolHalfHeight: bounds.height / 2,
        obstacles: [...drawingLabelBaseObstacles, ...Object.values(fireAlarmLabelLayouts), ...placed],
        bounds: stagePlanBounds,
      });
      layouts[instrument.id] = rect;
      placed.push(rect);
    });
    return layouts;
  }, [drawingLabelBaseObstacles, fireAlarmLabelLayouts, stagePlanBounds, visibleSignalInstruments]);
  const cableLabelObstacles = useMemo(() => {
    if (!showCableRoutesOnCanvas) {
      return [];
    }
    return [
      ...drawingLabelBaseObstacles,
      ...Object.values(fireAlarmLabelLayouts),
      ...Object.values(signalInstrumentLabelLayouts),
    ];
  }, [
    drawingLabelBaseObstacles,
    fireAlarmLabelLayouts,
    showCableRoutesOnCanvas,
    signalInstrumentLabelLayouts,
  ]);
  const hoverPanelStyle = (() => {
    if (!hoverPanel || !stageRect) {
      return null;
    }
    const panelBounds = clampHoverPanelPosition(
      { x: hoverPanel.x, y: hoverPanel.y },
      stageRect,
      HOVER_PANEL_SIZE,
      12,
    );
    return {
      position: 'absolute',
      left: `${panelBounds.left}px`,
      top: `${panelBounds.top}px`,
      width: `${panelBounds.width}px`,
      height: `${panelBounds.height}px`,
      zIndex: 15,
      backgroundColor: 'rgba(255,253,249,0.98)',
      border: '1px solid #d9d2c8',
      borderRadius: '14px',
      boxShadow: '0 18px 32px rgba(84,69,45,0.16)',
      padding: '14px',
      fontSize: '12px',
      pointerEvents: 'auto',
      overflow: 'hidden',
    };
  })();
  const hoverFireAlarmTitle = (hoverPanel?.type === 'fire-alarm' || hoverPanel?.type === 'new-fire-alarm') && hoverPanel?.data
    ? getFireAlarmCode(hoverPanel.data, {
      zone: fireAlarmDraft.zone || hoverPanel.data.zone,
      address: fireAlarmDraft.address || hoverPanel.data.address,
    })
    : null;
  const hoverFireAlarmRoomCoordinates = (hoverPanel?.type === 'fire-alarm' || hoverPanel?.type === 'new-fire-alarm') && hoverPanel?.data
    ? getFireAlarmRoomCoordinates(hoverPanel.data, rooms, floorPlan?.scale_factor)
    : { x: null, y: null };

  if (loading) {
    return <div className="loading">Загрузка плана этажа...</div>;
  }

  if (!floorPlan) {
    return <div>План этажа не найден</div>;
  }

  return (
    <div className="editor-container">
      <div className="editor-sidebar">
        <div className="sidebar-section">
          <button className="tool-button" style={{ width: '100%', marginBottom: '8px' }} onClick={() => navigate(`/projects/${floorPlan.project_id}`)}>
            ← Назад к проекту
          </button>
          <h3>Пошаговый пайплайн</h3>
          {editorSteps.map((step) => {
            const status = step.key === 'original'
              ? 'validated'
              : step.key === 'fire_alarms'
                ? (currentBranchState?.steps?.fire_alarms?.status || (fireAlarmStepUnlocked ? 'draft' : 'locked'))
                : step.key === 'devices_cables'
                  ? (currentBranchState?.steps?.devices_cables?.status || (devicesCablesStepUnlocked ? 'draft' : 'locked'))
                : getStepStatus(step.key);
            const canDetect = step.key === 'walls'
              || (step.key === 'openings' && wallsValidated)
              || (step.key === 'rooms' && wallsValidated && openingsValidated)
              || (step.key === 'zkspc' && roomsValidated);
            const canCommit = canDetect;
            const canOpen = step.key === 'fire_alarms'
              ? fireAlarmStepUnlocked
              : step.key === 'devices_cables'
                ? devicesCablesStepUnlocked
                : step.key === 'zkspc'
                  ? roomsValidated
                  : true;

            return (
              <div
                key={step.key}
                style={{
                  border: step.key === currentViewStep ? '1px solid #0f8f7c' : '1px solid #d9d2c8',
                  borderRadius: '16px',
                  padding: '8px',
                  marginBottom: '8px',
                  background: step.key === currentViewStep ? 'rgba(15, 143, 124, 0.08)' : 'rgba(255, 253, 249, 0.96)',
                  cursor: canOpen ? 'pointer' : 'not-allowed',
                  opacity: canOpen ? 1 : 0.55,
                }}
                onClick={() => {
                  if (canOpen) {
                    setViewStep(step.key);
                  }
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: step.key === 'original' ? 0 : '6px' }}>
                  <strong style={{ fontSize: '13px' }}>{step.title}</strong>
                  <span style={{
                    fontSize: '11px',
                    color: 'white',
                    background: getStepColor(status),
                    borderRadius: '10px',
                    padding: '2px 8px',
                  }}>
                    {status}
                  </span>
                </div>
                {!step.editorOnly && step.key !== 'original' && (
                  <div style={{ display: 'flex', gap: '6px' }} onClick={(e) => e.stopPropagation()}>
                    <button
                      className="tool-button"
                      style={{ fontSize: '12px', padding: '4px 8px' }}
                      disabled={!canDetect || pipelineActionLoading}
                      onClick={() => handleDetectStep(step.key)}
                    >
                      Распознать
                    </button>
                    <button
                      className="tool-button"
                      style={{ fontSize: '12px', padding: '4px 8px' }}
                      disabled={!canCommit || pipelineActionLoading}
                      onClick={() => handleCommitStep(step.key)}
                    >
                      Подтвердить и перейти
                    </button>
                  </div>
                )}
                {step.key === 'fire_alarms' && canOpen && (
                  <div style={{ display: 'flex', gap: '6px' }} onClick={(e) => e.stopPropagation()}>
                    <button
                      className="tool-button"
                      style={{ fontSize: '12px', padding: '4px 8px' }}
                      disabled={!fireAlarmStepUnlocked || fireAlarmActionLoading}
                      onClick={handleAutoLayoutFireAlarms}
                    >
                      {fireAlarmActionLoading ? 'Расстановка...' : 'Расставить'}
                    </button>
                    <button
                      className="tool-button"
                      style={{ fontSize: '12px', padding: '4px 8px' }}
                      disabled={!draftStateByStep.fire_alarms || fireAlarmActionLoading}
                      onClick={handleSaveFireAlarmsStep}
                    >
                      Сохранить
                    </button>
                  </div>
                )}
                {false && step.key === 'devices_cables' && canOpen && (
                  <div style={{ display: 'flex', gap: '6px' }} onClick={(e) => e.stopPropagation()}>
                    <button
                      className="tool-button"
                      style={{ fontSize: '12px', padding: '4px 8px' }}
                      disabled={!visibleSignalInstruments.length || signalBranchActionLoading}
                      onClick={() => refreshCableRoutes(currentSignalSystem, false)}
                    >
                      {signalBranchActionLoading ? 'Пересчет...' : 'Пересчитать'}
                    </button>
                  </div>
                )}
              </div>
            );
          })}
          {(pipelineLoading || pipelineActionLoading) && (
            <p style={{ fontSize: '12px', color: '#6c757d', margin: 0 }}>
              Выполняется операция пайплайна...
            </p>
          )}
        </div>

        {recognition && (
          <div className="sidebar-section">
            <h3>Распознавание</h3>
            <p><strong>Стен:</strong> {recognition.walls?.length || 0}</p>
            <p><strong>Проемов:</strong> {recognition.openings?.length || 0}</p>
            <p><strong>Помещений:</strong> {recognition.rooms?.length || 0}</p>
            <p><strong>OCR размеров:</strong> {recognition.dimensions?.length || 0}</p>
            {selectedDebugImage && (
              <p><strong>Debug шаг:</strong> {selectedDebugImage.step}</p>
            )}
            {canSubmitRecognitionFeedback && (
              <div style={{ display: 'grid', gap: '8px', marginTop: '10px' }}>
                <button
                  className="tool-button"
                  onClick={handleSubmitRecognitionFeedback}
                  disabled={!wallsValidated || !openingsValidated || !roomsValidated || recognitionFeedbackSubmitting}
                >
                  {recognitionFeedbackSubmitting ? 'Отправка...' : 'Отправить исправленный результат для обучения'}
                </button>
                {recognitionFeedbackStatus === 'success' && (
                  <div style={{ fontSize: '12px', color: '#0f766e' }}>
                    Исправленный результат добавлен в обучающую выборку.
                  </div>
                )}
                {recognitionFeedbackStatus === 'error' && (
                  <div style={{ fontSize: '12px', color: '#b42318' }}>
                    {recognitionFeedbackError}
                  </div>
                )}
                {(!wallsValidated || !openingsValidated || !roomsValidated) && (
                  <div style={{ fontSize: '12px', color: '#6c757d' }}>
                    Для отправки примера подтвердите шаги стен, проемов и помещений.
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {(showFireAlarmSidebar || showDevicesCablesSidebar) && (
          <SignalSystemSidebarSection
            currentSignalSystem={currentSignalSystem}
            signalBranchSummary={signalBranchSummary}
            onSwitchSignalSystem={handleSwitchSignalSystem}
          />
        )}

        {/* Legacy sidebar branch selector kept out of render.
          <div className="sidebar-section">
            <h3>Тип сигнализации</h3>
            <div style={{ display: 'grid', gap: '8px' }}>
              {SIGNAL_SYSTEM_OPTIONS.map((option) => (
                <button
                  key={option.key}
                  className={`tool-button ${currentSignalSystem === option.key ? 'active' : ''}`}
                  style={{ textAlign: 'left' }}
                  onClick={() => handleSwitchSignalSystem(option.key)}
                >
                  <div>{option.label}</div>
                  <div style={{ fontSize: '11px', color: '#6c757d', fontWeight: 400 }}>{option.hint}</div>
                </button>
              ))}
            </div>
            <div style={{ marginTop: '10px', padding: '8px', background: '#f8f9fa', borderRadius: '6px', fontSize: '12px' }}>
              <div><strong>{getSignalSystemLabel(currentSignalSystem)}</strong></div>
              <div>Извещателей: {signalBranchSummary.detectorCount}</div>
              <div>Кабеля: {formatCableMeters(signalBranchSummary.cableLengthM)}</div>
            </div>
          </div>
        */}

        {showZkspcSidebar && (
          <ZkspcSidebarSection
            currentZkspcZones={currentZkspcZones}
            visibleRooms={visibleRooms}
            roomDisplayNumberMap={roomDisplayNumberMap}
            selectedZkspcRooms={selectedZkspcRooms}
            pipelineActionLoading={pipelineActionLoading}
            roomsValidated={roomsValidated}
            onDetect={() => handleDetectStep('zkspc')}
            onCommit={() => handleCommitStep('zkspc')}
            onMergeSelected={handleMergeSelectedZkspcRooms}
            onToggleRoom={handleToggleZkspcRoom}
            onMoveSelectedRoomsToZone={handleMoveSelectedRoomsToZone}
            onToggleLock={handleToggleZkspcLock}
            onSplit={handleSplitZkspcZone}
          />
        )}

        {/* Legacy ZKSPC sidebar kept out of render.
          <div className="sidebar-section">
            <h3>ЗКСПС ({currentZkspcZones.length})</h3>
            <div style={{ display: 'flex', gap: '6px', marginBottom: '8px', flexWrap: 'wrap' }}>
              <button className="tool-button" onClick={() => handleDetectStep('zkspc')} disabled={pipelineActionLoading || !roomsValidated}>
                Распознать
              </button>
              <button className="tool-button" onClick={() => handleCommitStep('zkspc')} disabled={pipelineActionLoading || !currentZkspcZones.length}>
                Подтвердить
              </button>
              <button className="tool-button" onClick={handleMergeSelectedZkspcRooms} disabled={selectedZkspcRooms.length < 2}>
                Объединить
              </button>
            </div>
            <ul className="element-list">
              {currentZkspcZones.map((zone) => (
                <li key={`zkspc-${zone.id ?? zone.zone_number}`} className="element-item" style={{ alignItems: 'flex-start' }}>
                  <div style={{ width: '100%' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span style={{ width: '12px', height: '12px', borderRadius: '50%', background: zkspcStyleMap[Number(zone.zone_number || 1)]?.color || getZkspcStyle(zone, floorPlan?.id).color, display: 'inline-block' }} />
                      <strong>{zone.name || `ЗКСПС ${zone.zone_number}`}</strong>
                    </div>
                    <div style={{ fontSize: '11px', color: '#6c757d' }}>
                      Площадь: {Number(zone.area_sqm || 0).toFixed(2)} м² • Помещений: {zone.room_ids?.length || 0}
                    </div>
                    <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginTop: '6px' }}>
                      {(zone.room_ids || []).map((roomId) => {
                        const room = visibleRooms.find((item) => item.id === roomId);
                        return (
                          <button
                            key={`zkspc-room-${zone.id ?? zone.zone_number}-${roomId}`}
                            className={`tool-button ${selectedZkspcRooms.includes(roomId) ? 'active' : ''}`}
                            style={{ fontSize: '11px', padding: '3px 6px' }}
                            onClick={() => handleToggleZkspcRoom(roomId)}
                          >
                            {room?.name || `Помещение ${roomDisplayNumberMap[roomId] ?? roomId}`}
                          </button>
                        );
                      })}
                    </div>
                    {(zone.compliance_warnings || []).map((warning, index) => (
                      <div key={`zkspc-warning-${zone.id ?? zone.zone_number}-${index}`} style={{ fontSize: '11px', color: '#b45309', marginTop: '4px' }}>
                        {warning}
                      </div>
                    ))}
                  </div>
                  <div style={{ display: 'flex', gap: '4px', marginLeft: '8px' }}>
                    <button
                      className="tool-button"
                      style={{ fontSize: '11px', padding: '3px 6px' }}
                      onClick={() => handleMoveSelectedRoomsToZone(zone.id ?? zone.zone_number)}
                      disabled={!selectedZkspcRooms.length}
                    >
                      Move here
                    </button>
                    <button className="tool-button" style={{ fontSize: '11px', padding: '3px 6px' }} onClick={() => handleToggleZkspcLock(zone.id ?? zone.zone_number)}>
                      {zone.is_locked ? 'Unlock' : 'Lock'}
                    </button>
                    <button className="tool-button" style={{ fontSize: '11px', padding: '3px 6px' }} onClick={() => handleSplitZkspcZone(zone.id ?? zone.zone_number)}>
                      Split
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        */}

        {showRoomsSidebar && (
          <div className="sidebar-section">
            <h3>Помещения ({visibleRooms.length})</h3>
            <ul className="element-list">
              {visibleRooms.map((room) => (
                <li
                  key={room.id}
                  className={`element-item ${selectedElement?.type === 'room' && selectedElement?.id === room.id ? 'selected' : ''}`}
                  onClick={() => {
                    setSelectedElement({ type: 'room', id: room.id, data: room });
                    setSelectedElements([{ type: 'room', id: room.id }]);
                  }}
                >
                  <div>
                    <div>
                      №{roomDisplayNumberMap[room.id] ?? '—'} {room.name || `Помещение ${roomDisplayNumberMap[room.id] ?? ''}`.trim()}
                    </div>
                    <small>{room.area_sqm ? `${room.area_sqm.toFixed(2)} м²` : 'Площадь не рассчитана'}</small>
                    {roomDimensionsMap[room.id] && roomDimensionsMap[room.id].length > 0 && (
                      <div style={{ fontSize: '11px', color: '#555' }}>
                        Размеры: {roomDimensionsMap[room.id].map(dim => formatDimensionMeters(dim.value)).join(', ')}
                      </div>
                    )}
                  </div>
                  <button
                    className="element-delete"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteElement('rooms', room.id);
                    }}
                  >
                    ×
                  </button>}
                </li>
              ))}
            </ul>
            {selectedElement?.type === 'room' && (
              <>
                <h3 style={{ marginTop: '1rem' }}>Название помещения</h3>
                <input
                  type="text"
                  value={roomNameDraft}
                  onChange={(e) => setRoomNameDraft(e.target.value)}
                  placeholder="Введите название"
                  style={{
                    width: '100%',
                    marginBottom: '8px',
                    padding: '6px 8px',
                    border: '1px solid #ced4da',
                    borderRadius: '4px',
                    boxSizing: 'border-box',
                  }}
                />
                <button
                  className="tool-button"
                  onClick={handleSaveRoomName}
                  disabled={roomNameSaving}
                  style={{ width: '100%' }}
                >
                  {roomNameSaving ? 'Сохранение...' : 'Сохранить название'}
                </button>
              </>
            )}
          </div>
        )}

        {showFireAlarmSidebar && (
        <div className="sidebar-section">
          <h3>Пожарные извещатели ({visibleFireAlarmItems.length})</h3>
          {/* Legacy fire alarm action list kept out of render.
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginBottom: '10px' }}>
              <button className="tool-button" onClick={handleAutoLayoutFireAlarms} disabled={!fireAlarmStepUnlocked || fireAlarmActionLoading}>
                {fireAlarmActionLoading ? 'Расстановка...' : 'Расставить'}
              </button>
              <button className="tool-button" onClick={() => setSelectedTool('smoke-detector')}>
                Добавить дымовой датчик
              </button>
              <button className="tool-button" onClick={() => setSelectedTool('manual-call-point')}>
                Добавить ручной извещатель
              </button>
            </div>
          */}
          {fireAlarmWarnings.length > 0 && (
            <div style={{ marginBottom: '10px', padding: '8px', borderRadius: '6px', background: '#fff3cd', color: '#664d03', fontSize: '12px' }}>
              {fireAlarmWarnings.map((warning, index) => (
                <div key={`fire-warning-sidebar-${index}`}>{warning}</div>
              ))}
            </div>
          )}
          {visibleFireAlarmGroups.map((group) => (
            <div key={`fire-group-${group.key}`} style={{ marginBottom: '0.75rem' }}>
              <div style={{ fontSize: '12px', fontWeight: 600, color: '#495057', marginBottom: '6px' }}>
                {group.zone
                  ? `${group.zone.name || `ЗКСПС ${group.zone.zone_number}`}`
                  : 'Без ЗКСПС'}
              </div>
              <ul className="element-list">
                {group.items.map(({ kind, alarm }) => (
                  <li
                    key={alarm.id}
                    className={`element-item ${selectedElement?.type === (kind === 'new-fire-alarms' ? 'new-fire-alarm' : 'fire-alarm') && selectedElement?.id === alarm.id ? 'selected' : ''}`}
                    onClick={() => {
                      const type = kind === 'new-fire-alarms' ? 'new-fire-alarm' : 'fire-alarm';
                      setSelectedElement({ type, id: alarm.id, data: alarm });
                      setSelectedElements([{ type, id: alarm.id }]);
                    }}
                  >
                    <div>
                      <div>{getFireAlarmCode(alarm)}</div>
                    </div>
                    <button
                      className="element-delete"
                      onClick={(e) => {
                        e.stopPropagation();
                        if (kind === 'new-fire-alarms') {
                          setNewFireAlarms((prev) => prev.filter((item) => item.id !== alarm.id));
                          setHasUnsavedChanges(true);
                        } else {
                          handleDeleteElement('fire-alarms', alarm.id);
                        }
                      }}
                    >
                      ×
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        )}
      </div>

      {showDevicesCablesSidebar && (
        <DevicesCablesSidebarSection
          selectedTool={selectedTool}
          visibleSignalInstruments={visibleSignalInstruments}
          visibleCableRoutes={visibleCableRoutes}
          selectedElement={selectedElement}
          mergeInstrumentId={mergeInstrumentId}
          mergeSelectionCount={selectedElements.filter((item) => item.type === 'fire-alarm' || item.type === 'new-fire-alarm').length}
          onSelectTool={setSelectedTool}
          onSelectInstrument={(instrument) => {
            setSelectedElement({ type: 'signal-instrument', id: instrument.id, data: instrument });
            setSelectedElements([{ type: 'signal-instrument', id: instrument.id }]);
          }}
          onStartMerge={handleStartMergeCableRoutes}
          onApplyMerge={handleMergeCableRoutes}
          onCancelMerge={handleCancelMergeCableRoutes}
          onDeleteSignalInstrument={handleDeleteSignalInstrument}
        />
      )}

      {/* Legacy devices/cables sidebar kept out of render.
        <div className="editor-sidebar" style={{ borderLeft: '1px solid #dee2e6' }}>
          <div className="sidebar-section">
            <h3>Приборы и кабели</h3>
            <div style={{ display: 'grid', gap: '6px', marginBottom: '10px' }}>
              {SIGNAL_INSTRUMENT_OPTIONS.map((option) => (
                <button
                  key={option.key}
                  className={`tool-button ${selectedTool === option.key ? 'active' : ''}`}
                  onClick={() => setSelectedTool(option.key)}
                >
                  {option.label}
                </button>
              ))}
            </div>
            <ul className="element-list">
              {visibleSignalInstruments.map((instrument) => (
                <li
                  key={`instrument-${instrument.id}`}
                  className={`element-item ${selectedElement?.type === 'signal-instrument' && selectedElement?.id === instrument.id ? 'selected' : ''}`}
                  onClick={() => {
                    setSelectedElement({ type: 'signal-instrument', id: instrument.id, data: instrument });
                    setSelectedElements([{ type: 'signal-instrument', id: instrument.id }]);
                  }}
                >
                  <div>
                    <div>{instrument.name || getSignalInstrumentDefinition(instrument.instrument_type).label}</div>
                    <small>{getSignalInstrumentDefinition(instrument.instrument_type).label}</small>
                  </div>
                  {instrument.supports_cable_merge && (
                    <button
                      className="tool-button"
                      style={{ fontSize: '11px', padding: '3px 6px' }}
                      onClick={(e) => {
                        e.stopPropagation();
                        handleMergeCableRoutes(instrument);
                      }}
                    >
                      Свести
                    </button>
                  )}
                  {getSignalInstrumentDefinition(signalInstrumentDraft.instrumentType || hoverPanel.data?.instrument_type).supportsMerge && (
                    mergeInstrumentId === hoverPanel.id ? (
                      <>
                        <button className="tool-button" onClick={handleMergeCableRoutes}>
                          РџСЂРёРјРµРЅРёС‚СЊ СЃРІРµРґРµРЅРёРµ
                        </button>
                        <button className="tool-button" onClick={handleCancelMergeCableRoutes}>
                          РћС‚РјРµРЅР°
                        </button>
                      </>
                    ) : (
                      <button className="tool-button" onClick={() => handleStartMergeCableRoutes(hoverPanel.data)}>
                        РЎРІРµСЃС‚Рё РґР°С‚С‡РёРєРё
                      </button>
                    )
                  )}
                  <button
                    className="element-delete"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteSignalInstrument(instrument.id, instrument.system_type);
                    }}
                  >
                  ×
                  </button>
                </li>
              ))}
            </ul>
            <div style={{ marginTop: '10px', fontSize: '12px', color: '#495057' }}>
              {visibleCableRoutes.map((route) => (
                <div key={`route-${route.id}`} style={{ marginBottom: '6px' }}>
                  {route.route_kind} #{route.route_number}: {formatCableMeters(route.length_m)}
                </div>
              ))}
            </div>
          </div>
        </div>
      */}
      <div className="editor-canvas">
        <div className="editor-toolbar">
          <button
            className={`tool-button ${selectedTool === 'select' ? 'active' : ''}`}
            onClick={() => setSelectedTool('select')}
          >
            Выбрать
          </button>
          <button
            className={`tool-button ${selectedTool === 'multi-select' ? 'active' : ''}`}
            onClick={() => setSelectedTool('multi-select')}
          >
            Выделить область
          </button>
          {currentViewStep === 'walls' && (
            <button
              className={`tool-button ${selectedTool === 'wall' ? 'active' : ''}`}
              onClick={() => setSelectedTool('wall')}
            >
              Нарисовать стену
            </button>
          )}
          {currentViewStep === 'walls' && (
            <button
              className={`tool-button ${selectedTool === 'stairs' ? 'active' : ''}`}
              onClick={() => setSelectedTool('stairs')}
            >
              Добавить лестницу
            </button>
          )}
          {currentViewStep === 'walls' && (
            <>
              <select
                value={wallDraftPreset}
                onChange={(e) => setWallDraftPreset(e.target.value)}
                style={{ display: 'none' }}
                aria-hidden="true"
              >
                <option value="outer">Наружная стена</option>
                <option value="inner">Внутренняя стена</option>
                <option value="manual">Ручная толщина</option>
              </select>
              <select
                value={newWallAlignment}
                onChange={(e) => setNewWallAlignment(normalizeWallAlignment(e.target.value))}
                style={{ display: 'none' }}
                aria-hidden="true"
              >
                {WALL_ALIGNMENT_OPTIONS.map((option) => (
                  <option key={`new-wall-align-${option.value}`} value={option.value}>{option.label}</option>
                ))}
              </select>
              <button
                className="tool-button"
                type="button"
                onClick={() => setNewWallAlignment((prev) => flipWallAlignment(prev))}
                style={{ display: 'none' }}
                aria-hidden="true"
              >
                Flip стены
              </button>
              <label style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#4f4131' }}>
                <span style={{ fontSize: '12px', fontWeight: 600 }}>Толщина, м</span>
                <input
                  type="number"
                  min="0.01"
                  step="0.01"
                  value={newWallThicknessDraft}
                  onChange={(e) => setNewWallThicknessDraft(e.target.value)}
                  style={{ width: '92px' }}
                  aria-label="Толщина новой стены, м"
                />
              </label>
              <div style={{ display: 'flex', gap: '6px' }}>
                <button
                  className={`tool-button ${!wallAutoSnapEnabled ? 'active' : ''}`}
                  type="button"
                  onClick={() => setWallAutoSnapEnabled(false)}
                >
                  Свободно
                </button>
                <button
                  className={`tool-button ${wallAutoSnapEnabled ? 'active' : ''}`}
                  type="button"
                  onClick={() => setWallAutoSnapEnabled(true)}
                >
                  Прилипание
                </button>
              </div>
              <button
                className="tool-button"
                type="button"
                onClick={() => {
                  saveToHistory();
                  finalizeWallWorkingSet(getWorkingWallsSnapshot(), { autoNormalize: true });
                }}
              >
                Приклеить все стены
              </button>
            </>
          )}
          {currentViewStep === 'openings' && (
            <>
              <button
                className={`tool-button ${selectedTool === 'door' ? 'active' : ''}`}
                onClick={() => setSelectedTool('door')}
              >
                Добавить дверь
              </button>
              <button
                className={`tool-button ${selectedTool === 'window' ? 'active' : ''}`}
                onClick={() => setSelectedTool('window')}
              >
                Добавить окно
              </button>
            </>
          )}
          {currentViewStep === 'rooms' && (
            <button
              className={`tool-button ${selectedTool === 'room-zone' ? 'active' : ''}`}
              onClick={() => setSelectedTool('room-zone')}
            >
              Добавить зону
            </button>
          )}
          {currentViewStep === 'fire_alarms' && (
            <>
              <button
                className={`tool-button ${selectedTool === 'smoke-detector' ? 'active' : ''}`}
                onClick={() => setSelectedTool('smoke-detector')}
              >
                {getFireAlarmDisplayLabel('smoke_detector')}
              </button>
              <button
                className={`tool-button ${selectedTool === 'manual-call-point' ? 'active' : ''}`}
                onClick={() => setSelectedTool('manual-call-point')}
              >
                {getFireAlarmDisplayLabel('manual_call_point')}
              </button>
            </>
          )}
          {currentViewStep === 'devices_cables' && (
            <>
              {SIGNAL_INSTRUMENT_OPTIONS.map((option) => (
                <button
                  key={`toolbar-${option.key}`}
                  className={`tool-button ${selectedTool === option.key ? 'active' : ''}`}
                  onClick={() => setSelectedTool(option.key)}
                >
                  {option.label}
                </button>
              ))}
            </>
          )}
          {currentViewStep !== 'original' && (
            <button
              className={`tool-button ${selectedTool === 'calibration' ? 'active' : ''}`}
              onClick={() => setSelectedTool('calibration')}
            >
              Калибровка
            </button>
          )}
          {currentViewStep !== 'devices_cables' && selectedElements.length > 1 && selectedGroupBounds && (
            <>
              <button className="tool-button" onClick={handleDeleteSelectedElements}>Удалить группу</button>
              <button
                className="tool-button"
                onClick={() => applyTransformToSelected({
                  scale: 1.1,
                  centerX: selectedGroupBounds.x + selectedGroupBounds.width / 2,
                  centerY: selectedGroupBounds.y + selectedGroupBounds.height / 2,
                })}
              >
                Масштаб +
              </button>
              <button
                className="tool-button"
                onClick={() => applyTransformToSelected({
                  scale: 0.9,
                  centerX: selectedGroupBounds.x + selectedGroupBounds.width / 2,
                  centerY: selectedGroupBounds.y + selectedGroupBounds.height / 2,
                })}
              >
                Масштаб -
              </button>
            </>
          )}
          {selectedDebugImage && (
            <button
              className="tool-button"
              onClick={() => setSelectedDebugImagePath(null)}
              style={{ backgroundColor: '#6c757d', color: 'white' }}
            >
              Показать распознавание
            </button>
          )}
          
          {/* Zoom controls */}
          <div style={{ display: 'flex', gap: '0.25rem', marginLeft: '1rem', alignItems: 'center' }}>
            <button
              className="tool-button"
              onClick={handleZoomOut}
              disabled={userZoom <= MIN_ZOOM}
              title="Уменьшить (Ctrl+колесо мыши вниз)"
            >
              −
            </button>
            <span style={{ fontSize: '12px', minWidth: '40px', textAlign: 'center' }}>
              {Math.round(userZoom * 100)}%
            </span>
            <input
              type="range"
              min={Math.round(MIN_ZOOM * 100)}
              max={Math.round(MAX_ZOOM * 100)}
              step={Math.round(ZOOM_STEP * 100)}
              value={Math.round(userZoom * 100)}
              aria-label="Масштаб отображения"
              onChange={(e) => {
                const nextZoom = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, Number(e.target.value) / 100));
                updateViewport((prev) => ({ ...prev, zoom: nextZoom }));
              }}
              style={{ width: '140px' }}
            />
            <button
              className="tool-button"
              onClick={handleZoomIn}
              disabled={userZoom >= MAX_ZOOM}
              title="Увеличить (Ctrl+колесо мыши вверх)"
            >
              +
            </button>
            <button
              className="tool-button"
              onClick={handleZoomReset}
              title="Сбросить зум"
            >
              100%
            </button>
            <button
              className="tool-button"
              onClick={handleRotateViewport}
              title="Повернуть изображение и план на 90°"
            >
              ↻ 90°
            </button>
          </div>
        </div>

        <div className="editor-stage" id="editor-stage-container" ref={setStageContainerNodeRef}>
          {selectedDebugImage && (
            <div style={{
              position: 'absolute',
              top: '10px',
              left: '10px',
              zIndex: 5,
              padding: '6px 10px',
              backgroundColor: 'rgba(23, 162, 184, 0.9)',
              color: 'white',
              borderRadius: '4px',
              fontSize: '12px'
            }}>
              Debug шаг: {selectedDebugImage.step}
            </div>
          )}
          {showWallValidationAlert && (
            <div
              style={{
                position: 'absolute',
                inset: 0,
                backgroundColor: 'rgba(0, 0, 0, 0.35)',
                zIndex: 20,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
              onClick={() => setShowWallValidationAlert(false)}
            >
              <div
                style={{
                  width: '420px',
                  maxWidth: '90%',
                  background: 'white',
                  borderRadius: '8px',
                  border: '1px solid #dc3545',
                  padding: '16px',
                }}
                onClick={(e) => e.stopPropagation()}
              >
                <h3 style={{ margin: '0 0 8px 0', color: '#dc3545' }}>Нельзя перейти к следующему шагу</h3>
                <p style={{ margin: '0 0 12px 0', fontSize: '14px' }}>
                  Назначьте длину всем стенам и сохраните изменения в popup на стене.
                </p>
                <p style={{ margin: 0, fontSize: '13px' }}>
                  Без размеров: {missingWallIds.join(', ')}
                </p>
                <div style={{ marginTop: '12px', textAlign: 'right' }}>
                  <button className="tool-button" onClick={() => setShowWallValidationAlert(false)}>
                    Понятно
                  </button>
                </div>
              </div>
            </div>
          )}
          {hoverPanel && hoverPanelStyle && !selectedDebugImage && (
            <div
              style={hoverPanelStyle}
              onMouseEnter={() => {
                clearHoverCloseTimeout();
                setHoverPanelMouseInside(true);
              }}
              onMouseLeave={() => {
                setHoverPanelMouseInside(false);
                scheduleHoverPanelClose();
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <strong style={{ fontSize: '13px' }}>
                  {['wall', 'new-wall'].includes(hoverPanel.type) && `Стена №${wallDisplayNumberMap[hoverPanel.id] ?? '—'}`}
                  {(['door', 'window', 'new-door', 'new-window'].includes(hoverPanel.type)) && `${hoverPanel.type.includes('door') ? 'Дверь' : 'Окно'} №${(hoverPanel.type.includes('door') ? doorDisplayNumberMap : windowDisplayNumberMap)[hoverPanel.id] ?? '—'}`}
                  {(hoverPanel.type === 'stair' || hoverPanel.type === 'new-stair') && `Лестница №${stairDisplayNumberMap[hoverPanel.id] ?? '—'}`}
                  {hoverPanel.type === 'room' && `Помещение №${roomDisplayNumberMap[hoverPanel.id] ?? '—'}`}
                  {(hoverPanel.type === 'fire-alarm' || hoverPanel.type === 'new-fire-alarm') && hoverFireAlarmTitle}
                  {hoverPanel.type === 'signal-instrument' && (hoverPanel.data?.name || 'Прибор')}
                  {hoverPanel.type === 'cable-route' && `Кабель ${hoverPanel.data?.route_kind || ''} #${hoverPanel.data?.route_number || '—'}`}
                </strong>
                <button
                  type="button"
                  className="tool-button"
                  style={{ fontSize: '11px', padding: '2px 6px' }}
                  onClick={closeHoverPanel}
                >
                  ×
                </button>
              </div>

              {['wall', 'new-wall'].includes(hoverPanel.type) && (
                <div style={HOVER_PANEL_SECTION_STYLE}>
                  <label style={HOVER_PANEL_FIELD_ROW_STYLE}>
                    <span style={HOVER_PANEL_LABEL_STYLE}>Длина, м</span>
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      value={wallLengthDraft}
                      onChange={(e) => {
                        setWallLengthDraft(e.target.value);
                      }}
                      style={HOVER_PANEL_INPUT_STYLE}
                    />
                  </label>
                  <label style={HOVER_PANEL_FIELD_ROW_STYLE}>
                    <span style={HOVER_PANEL_LABEL_STYLE}>Толщина, м</span>
                    <input
                      type="number"
                      step="0.01"
                      min="0.01"
                      value={wallThicknessDraft}
                      onChange={(e) => {
                        setWallThicknessDraft(e.target.value);
                      }}
                      style={HOVER_PANEL_INPUT_STYLE}
                    />
                  </label>
                  <label style={{ ...HOVER_PANEL_FIELD_ROW_STYLE, display: 'none' }} aria-hidden="true">
                    <span style={HOVER_PANEL_LABEL_STYLE}>Смещение</span>
                    <select
                      value={wallAlignmentDraft}
                      onChange={(e) => setWallAlignmentDraft(normalizeWallAlignment(e.target.value))}
                      style={HOVER_PANEL_INPUT_STYLE}
                    >
                      {WALL_ALIGNMENT_OPTIONS.map((option) => (
                        <option key={`wall-alignment-${option.value}`} value={option.value}>{option.label}</option>
                      ))}
                    </select>
                  </label>
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <button
                      className="tool-button"
                      type="button"
                      style={{ flex: '1 1 auto', display: 'none' }}
                      onClick={() => setWallAlignmentDraft((prev) => flipWallAlignment(prev))}
                      aria-hidden="true"
                    >
                      Flip
                    </button>
                    <button className="tool-button" style={{ flex: '1 1 auto' }} onClick={handleSaveWallMeta}>Сохранить</button>
                  </div>
                </div>
              )}

              {(['door', 'window', 'new-door', 'new-window'].includes(hoverPanel.type)) && (
                <div style={HOVER_PANEL_SECTION_STYLE}>
                  <label style={HOVER_PANEL_FIELD_ROW_STYLE}>
                    <span style={HOVER_PANEL_LABEL_STYLE}>Ширина, м</span>
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      value={openingSizeDraft.width}
                      onChange={(e) => {
                        const nextDraft = { ...openingSizeDraft, width: e.target.value };
                        setOpeningSizeDraft(nextDraft);
                      }}
                      style={HOVER_PANEL_INPUT_STYLE}
                    />
                  </label>
                  <label style={HOVER_PANEL_FIELD_ROW_STYLE}>
                    <span style={HOVER_PANEL_LABEL_STYLE}>Толщина, м</span>
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      value={openingSizeDraft.height}
                      onChange={(e) => {
                        const nextDraft = { ...openingSizeDraft, height: e.target.value };
                        setOpeningSizeDraft(nextDraft);
                      }}
                      style={HOVER_PANEL_INPUT_STYLE}
                    />
                  </label>
                  <button className="tool-button" onClick={handleSaveOpeningMeta}>Сохранить</button>
                </div>
              )}

              {(hoverPanel.type === 'stair' || hoverPanel.type === 'new-stair') && (
                <div style={HOVER_PANEL_SECTION_STYLE}>
                  <label style={HOVER_PANEL_FIELD_ROW_STYLE}>
                    <span style={HOVER_PANEL_LABEL_STYLE}>Ширина, м</span>
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      value={stairDraft.width}
                      onChange={(e) => {
                        const nextDraft = { ...stairDraft, width: e.target.value };
                        setStairDraft(nextDraft);
                      }}
                      style={HOVER_PANEL_INPUT_STYLE}
                    />
                  </label>
                  <label style={HOVER_PANEL_FIELD_ROW_STYLE}>
                    <span style={HOVER_PANEL_LABEL_STYLE}>Высота, м</span>
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      value={stairDraft.height}
                      onChange={(e) => {
                        const nextDraft = { ...stairDraft, height: e.target.value };
                        setStairDraft(nextDraft);
                      }}
                      style={HOVER_PANEL_INPUT_STYLE}
                    />
                  </label>
                  <div style={{ fontSize: '12px', color: '#6c757d' }}>
                    Количество линий определяется автоматически по размеру лестницы.
                  </div>
                  <button className="tool-button" onClick={handleSaveStairMeta}>Сохранить</button>
                </div>
              )}

              {hoverPanel.type === 'room' && (
                <div style={HOVER_PANEL_SECTION_STYLE}>
                  <label style={HOVER_PANEL_FIELD_ROW_STYLE}>
                    <span style={HOVER_PANEL_LABEL_STYLE}>Имя</span>
                    <input
                      type="text"
                      value={roomDraft.name}
                      onChange={(e) => setRoomDraft(prev => ({ ...prev, name: e.target.value }))}
                      style={HOVER_PANEL_INPUT_STYLE}
                    />
                  </label>
                  <label style={HOVER_PANEL_FIELD_ROW_STYLE}>
                    <span style={HOVER_PANEL_LABEL_STYLE}>Тип</span>
                    <select
                      value={roomDraft.type}
                      onChange={(e) => setRoomDraft(prev => ({ ...prev, type: e.target.value }))}
                      style={HOVER_PANEL_INPUT_STYLE}
                    >
                      <option value="базовое">базовое</option>
                      <option value="необслуживаемое">необслуживаемое</option>
                    </select>
                  </label>
                  <div style={HOVER_PANEL_INFO_ROW_STYLE}>
                    <span>Длина</span>
                    <strong>{formatMetersValue(hoverPanel.data?.length_m, 2)}</strong>
                  </div>
                  <div style={HOVER_PANEL_INFO_ROW_STYLE}>
                    <span>Ширина</span>
                    <strong>{formatMetersValue(hoverPanel.data?.width_m, 2)}</strong>
                  </div>
                  <div style={HOVER_PANEL_INFO_ROW_STYLE}>
                    <span>Площадь</span>
                    <strong>
                      {hoverPanel.data?.area_sqm !== null && hoverPanel.data?.area_sqm !== undefined
                        ? `${Number(hoverPanel.data.area_sqm).toFixed(2)} м²`
                        : '—'}
                    </strong>
                  </div>
                  <button className="tool-button" onClick={handleSaveRoomMeta}>Сохранить</button>
                </div>
              )}

              {(hoverPanel.type === 'fire-alarm' || hoverPanel.type === 'new-fire-alarm') && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <div>Тип: {getFireAlarmShortTypeLabel(hoverPanel.data?.device_type)}</div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px' }}>
                    <label style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
                      <span>Шлейф</span>
                      <input
                        type="text"
                        value={fireAlarmDraft.zone}
                        onChange={(e) => setFireAlarmDraft((prev) => ({ ...prev, zone: e.target.value }))}
                      />
                    </label>
                    <label style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
                      <span>Номер</span>
                      <input
                        type="text"
                        value={fireAlarmDraft.address}
                        onChange={(e) => setFireAlarmDraft((prev) => ({ ...prev, address: e.target.value }))}
                      />
                    </label>
                  </div>
                  <div>
                    x:{' '}
                    {hoverFireAlarmRoomCoordinates.x !== null && hoverFireAlarmRoomCoordinates.x !== undefined
                      ? `${hoverFireAlarmRoomCoordinates.x.toFixed(2)} м`
                      : '—'}
                    {' / '}
                    y:{' '}
                    {hoverFireAlarmRoomCoordinates.y !== null && hoverFireAlarmRoomCoordinates.y !== undefined
                      ? `${hoverFireAlarmRoomCoordinates.y.toFixed(2)} м`
                      : '—'}
                  </div>
                  <div>
                    Радиус покрытия:{' '}
                    {hoverPanel.data?.coverage_radius
                      ? `${(hoverPanel.data.coverage_radius / 1000).toFixed(2)} м`
                      : '—'}
                  </div>
                  <button className="tool-button" onClick={handleSaveFireAlarmMeta}>Сохранить</button>
                  <button
                    className="tool-button"
                    onClick={() => {
                      if (hoverPanel.type === 'new-fire-alarm') {
                        setNewFireAlarms((prev) => prev.filter((item) => item.id !== hoverPanel.id));
                        setHasUnsavedChanges(true);
                        closeHoverPanel();
                        clearCanvasSelection();
                      } else {
                        handleDeleteElement('fire-alarms', hoverPanel.id);
                        closeHoverPanel();
                      }
                    }}
                  >
                    Удалить
                  </button>
                </div>
              )}

              {hoverPanel.type === 'signal-instrument' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <label style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
                    <span>Название</span>
                    <input
                      type="text"
                      value={signalInstrumentDraft.name}
                      onChange={(e) => setSignalInstrumentDraft((prev) => ({ ...prev, name: e.target.value }))}
                    />
                  </label>
                  <label style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
                    <span>Тип</span>
                    <select
                      value={signalInstrumentDraft.instrumentType}
                      onChange={(e) => setSignalInstrumentDraft((prev) => ({ ...prev, instrumentType: e.target.value }))}
                    >
                      {SIGNAL_INSTRUMENT_OPTIONS.map((option) => (
                        <option key={`instrument-option-${option.key}`} value={option.key}>{option.label}</option>
                      ))}
                    </select>
                  </label>
                  <div>x: {Number(hoverPanel.data?.x || 0).toFixed(1)} px</div>
                  <div>y: {Number(hoverPanel.data?.y || 0).toFixed(1)} px</div>
                  <button className="tool-button" onClick={handleSaveSignalInstrumentMeta}>Сохранить</button>
                  {false && getSignalInstrumentDefinition(signalInstrumentDraft.instrumentType || hoverPanel.data?.instrument_type).supportsMerge && (
                    <button className="tool-button" onClick={() => handleMergeCableRoutes(hoverPanel.data)}>
                      Свести кабели
                    </button>
                  )}
                  <button
                    className="tool-button"
                    onClick={() => handleDeleteSignalInstrument(hoverPanel.id, hoverPanel.data?.system_type || currentSignalSystem)}
                  >
                    Удалить
                  </button>
                </div>
              )}

              {hoverPanel.type === 'cable-route' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <div>Тип: {hoverPanel.data?.route_kind || '—'}</div>
                  <div>Длина: {formatCableMeters(hoverPanel.data?.length_m)}</div>
                  <div>Устройств: {(hoverPanel.data?.device_ids || []).length}</div>
                  <div>Режим: {hoverPanel.data?.is_manual ? 'ручной' : 'авто'}</div>
                  {false && <button className="tool-button" onClick={() => refreshCableRoutes(currentSignalSystem, false)}>
                    Пересчитать
                  </button>
                </div>
              )}
            </div>
          )}
          {containerSize.width > 0 && containerSize.height > 0 && (
          <Stage
            width={containerSize.width}
            height={containerSize.height}
            ref={stageRef}
            onClick={handleStageClick}
            onMouseDown={handleStageMouseDown}
            onMouseUp={handleStageMouseUp}
            onMouseLeave={() => {
              if (isStagePanning) {
                endStagePan();
              }
            }}
            onMouseMove={(e) => {
              const stage = e.target.getStage();
              const point = stage.getPointerPosition();
              if (!point) {
                return;
              }
              const panStart = stagePanStartRef.current;
              if (isStagePanning && panStart) {
                const {
                  pointerX,
                  pointerY,
                  startX,
                  startY,
                } = panStart;
                const dx = point.x - pointerX;
                const dy = point.y - pointerY;
                if (Math.abs(dx) > 2 || Math.abs(dy) > 2) {
                  stagePanMovedRef.current = true;
                }
                updateViewport((prev) => ({
                  ...prev,
                  pan: {
                    x: startX + dx,
                    y: startY + dy,
                  },
                }));
                return;
              }
              const scaledPoint = viewportPointToPlan(point, viewTransform);
              setMousePos(scaledPoint);
              if (isSelecting && selectionRect) {
                setSelectionRect((prev) => (prev ? { ...prev, width: scaledPoint.x - prev.x, height: scaledPoint.y - prev.y } : prev));
              }
              if (isRoomZoneDrawing && roomZoneRect) {
                setRoomZoneRect((prev) => (prev ? { ...prev, width: scaledPoint.x - prev.x, height: scaledPoint.y - prev.y } : prev));
              }
            }}
          >
            <Layer id="editor-layer" onClick={handleStageClick}>
              <Group
                x={viewTransform.centerX}
                y={viewTransform.centerY}
                scaleX={viewTransform.scale}
                scaleY={viewTransform.scale}
                rotation={viewTransform.rotationDeg}
                offsetX={viewTransform.imageCenterX}
                offsetY={viewTransform.imageCenterY}
              >
              {/* Background Image */}
              {showBackgroundImage && displayedImageUrl && (
                <BackgroundImage
                  src={displayedImageUrl}
                  grayscale={!selectedDebugImage}
                  onImageLoad={handleRenderedImageLoad}
                />
              )}

              {/* Drawing Wall Preview */}
              {!selectedDebugImage && showWallsOnCanvas && drawingWall && (() => {
                let x2 = mousePos.x;
                let y2 = mousePos.y;
                
                // Если зажат Shift, привязываем к углам кратным 45°
                if (shiftPressed) {
                  const snapped = snapTo45Degrees(drawingWall.x1, drawingWall.y1, x2, y2);
                  x2 = snapped.x;
                  y2 = snapped.y;
                }
                const previewSegments = getWallOutline({
                  x1: drawingWall.x1,
                  y1: drawingWall.y1,
                  x2,
                  y2,
                  thickness: currentWallDraftThicknessMm,
                  alignment: 'center',
                });

                return (
                  <>
                    <Line
                      points={[
                        previewSegments.top[0],
                        previewSegments.top[1],
                        previewSegments.top[2],
                        previewSegments.top[3],
                        previewSegments.bottom[2],
                        previewSegments.bottom[3],
                        previewSegments.bottom[0],
                        previewSegments.bottom[1],
                      ]}
                      closed
                      fill="rgba(57,255,20,0.18)"
                      stroke="rgba(57,255,20,0.35)"
                      strokeWidth={1}
                    />
                    <Line
                      points={previewSegments.top}
                      stroke={WALL_COLOR}
                      strokeWidth={2}
                      dash={[10, 5]}
                    />
                    <Line
                      points={previewSegments.bottom}
                      stroke={WALL_COLOR}
                      strokeWidth={2}
                      dash={[10, 5]}
                    />
                    <Line
                      points={[
                        previewSegments.top[0],
                        previewSegments.top[1],
                        previewSegments.bottom[0],
                        previewSegments.bottom[1],
                      ]}
                      stroke={WALL_COLOR}
                      strokeWidth={2}
                      dash={[10, 5]}
                    />
                    <Line
                      points={[
                        previewSegments.top[2],
                        previewSegments.top[3],
                        previewSegments.bottom[2],
                        previewSegments.bottom[3],
                      ]}
                      stroke={WALL_COLOR}
                      strokeWidth={2}
                      dash={[10, 5]}
                    />
                  </>
                );
              })()}

              {!selectedDebugImage && placementDraft?.type === 'stairs' && currentViewStep === 'walls' && (() => {
                const preview = getStairPreviewGeometry(placementDraft.start, mousePos);
                return (
                  <Rect
                    x={preview.x}
                    y={preview.y}
                    width={preview.width}
                    height={preview.height}
                    stroke="#8b5cf6"
                    strokeWidth={2}
                    dash={[8, 4]}
                    fill="rgba(139,92,246,0.08)"
                    listening={false}
                  />
                );
              })()}

              {!selectedDebugImage && placementDraft && (placementDraft.type === 'door' || placementDraft.type === 'window') && currentViewStep === 'openings' && (() => {
                const preview = getOpeningPreviewGeometry(placementDraft.type, placementDraft.start, mousePos);
                const baseRect = normalizeRectFromPoints(placementDraft.start, getPlacementEndPoint(placementDraft.start, mousePos));
                if (!preview) {
                  return (
                    <Rect
                      x={baseRect.x}
                      y={baseRect.y}
                      width={Math.max(4, baseRect.width)}
                      height={Math.max(4, baseRect.height)}
                      stroke="#dc3545"
                      strokeWidth={2}
                      dash={[6, 4]}
                      fill="rgba(220,53,69,0.08)"
                      listening={false}
                    />
                  );
                }
                const previewColor = placementDraft.type === 'door' ? '#ff6b6b' : '#0057D9';
                return (
                  <Group
                    x={preview.x + preview.width / 2}
                    y={preview.y + preview.height / 2}
                    rotation={preview.rotation_deg || 0}
                    opacity={0.5}
                    listening={false}
                  >
                    <Rect
                      x={-preview.width / 2}
                      y={-preview.height / 2}
                      width={preview.width}
                      height={preview.height}
                      stroke={previewColor}
                      strokeWidth={2}
                    />
                  </Group>
                );
              })()}

              {!selectedDebugImage && selectedTool === 'calibration' && calibrationDraft.start && (
                <Line
                  points={[
                    calibrationDraft.start.x,
                    calibrationDraft.start.y,
                    (calibrationDraft.end || mousePos).x,
                    (calibrationDraft.end || mousePos).y,
                  ]}
                  stroke="#0d6efd"
                  strokeWidth={2}
                  dash={[6, 4]}
                  listening={false}
                />
              )}

              {!selectedDebugImage && showWallsOnCanvas && visibleWallBoundarySegments.map((segment, index) => {
                const wall = draftingWallMap.get(segment.wallId);
                if (!wall || suppressedWallIds.has(segment.wallId)) {
                  return null;
                }
                const isSelected = (selectedElement?.id === segment.wallId && ['wall', 'new-wall'].includes(selectedElement?.type))
                  || selectedElements.some((item) => ['wall', 'new-wall'].includes(item.type) && item.id === segment.wallId);
                const isHovered = hoveredElement?.id === segment.wallId && ['wall', 'new-wall'].includes(hoveredElement?.type);
                const isMissingDimension = missingWallIds.includes(segment.wallId);
                const stroke = useArchitectBlack
                  ? '#111111'
                  : (isMissingDimension ? '#dc3545' : (isSelected ? 'blue' : (isHovered ? 'orange' : WALL_COLOR)));
                const thicknessPx = getWallThicknessPx(wall, floorPlan?.scale_factor);
                return (
                  <Line
                    key={`wall-boundary-${segment.wallId}-${segment.kind}-${segment.side}-${index}`}
                    points={segment.points}
                    stroke={stroke}
                    strokeWidth={Math.max(1.5, Math.min(3, thicknessPx * 0.16))}
                    lineCap="round"
                    opacity={editingWall?.id === segment.wallId ? 0.45 : 1}
                    listening={false}
                  />
                );
              })}

              {/* Render Walls */}
              {!selectedDebugImage && showWallsOnCanvas && walls
                .filter(wall => !deletedElements.some(del => del.type === 'walls' && del.id === wall.id))
                .filter(wall => !suppressedWallIds.has(wall.id))
                .map((wall) => {
                const isSelected = (selectedElement?.type === 'wall' && selectedElement?.id === wall.id)
                  || selectedElements.some((item) => item.type === 'wall' && item.id === wall.id);
                const isBlocked = isElementInteractionBlocked('wall', wall.id);
                const isHovered = hoveredElement?.type === 'wall' && hoveredElement?.id === wall.id;
                
                // Применяем локальные изменения если есть
                const modifications = modifiedWalls[wall.id] || {};
                let x1 = modifications.x1 !== undefined ? modifications.x1 : wall.x1;
                let y1 = modifications.y1 !== undefined ? modifications.y1 : wall.y1;
                let x2 = modifications.x2 !== undefined ? modifications.x2 : wall.x2;
                let y2 = modifications.y2 !== undefined ? modifications.y2 : wall.y2;
                
                // Для отображения кругов во время перетаскивания всей стены
                let circleX1 = x1, circleY1 = y1, circleX2 = x2, circleY2 = y2;
                
                // Если стена редактируется точками, используем временные координаты
                if (editingWall?.id === wall.id && editingWall.point) {
                  if (editingWall.point === 'start') {
                    circleX1 = editingWall.x;
                    circleY1 = editingWall.y;
                    x1 = editingWall.x;
                    y1 = editingWall.y;
                  } else if (editingWall.point === 'end') {
                    circleX2 = editingWall.x;
                    circleY2 = editingWall.y;
                    x2 = editingWall.x;
                    y2 = editingWall.y;
                  }
                } else if (editingWall?.id === wall.id && editingWall.isDragging) {
                  // При перетаскивании всей стены смещаем круги
                  circleX1 += editingWall.dx;
                  circleY1 += editingWall.dy;
                  circleX2 += editingWall.dx;
                  circleY2 += editingWall.dy;
                }

                const thicknessPx = getWallThicknessPx(
                  { thickness: modifications.thickness !== undefined ? modifications.thickness : wall.thickness },
                  floorPlan?.scale_factor,
                );
                const wallGeometry = {
                  x1,
                  y1,
                  x2,
                  y2,
                  thickness: modifications.thickness !== undefined ? modifications.thickness : wall.thickness,
                  alignment: modifications.alignment !== undefined ? modifications.alignment : (wall.alignment || 'center'),
                };
                const isMissingDimension = missingWallIds.includes(wall.id);
                const wallStrokeColor = useArchitectBlack
                  ? '#111111'
                  : (isMissingDimension
                    ? '#dc3545'
                    : (isSelected ? 'blue' : (isHovered ? 'orange' : WALL_COLOR)));
                const wallPreviewOpacity = editingWall?.id === wall.id ? 0.45 : 1;
                const wallSegments = getWallOutline(wallGeometry);
                const wallOutlineStrokeWidth = 0;
                const topMid = {
                  x: (wallSegments.top[0] + wallSegments.top[2]) / 2,
                  y: (wallSegments.top[1] + wallSegments.top[3]) / 2,
                };
                const bottomMid = {
                  x: (wallSegments.bottom[0] + wallSegments.bottom[2]) / 2,
                  y: (wallSegments.bottom[1] + wallSegments.bottom[3]) / 2,
                };
                return (
                  <React.Fragment key={`wall-${wall.id}`}>
                    <Line
                      points={wallSegments.top}
                      stroke={wallStrokeColor}
                      strokeWidth={wallOutlineStrokeWidth}
                      lineCap="round"
                      opacity={wallPreviewOpacity}
                      listening={false}
                    />
                    <Line
                      points={wallSegments.bottom}
                      stroke={wallStrokeColor}
                      strokeWidth={wallOutlineStrokeWidth}
                      lineCap="round"
                      opacity={wallPreviewOpacity}
                      listening={false}
                    />
                    <Line
                      points={[
                        wallSegments.top[0],
                        wallSegments.top[1],
                        wallSegments.bottom[0],
                        wallSegments.bottom[1],
                      ]}
                      stroke={wallStrokeColor}
                      strokeWidth={wallOutlineStrokeWidth}
                      lineCap="round"
                      opacity={wallPreviewOpacity}
                      listening={false}
                    />
                    <Line
                      points={[
                        wallSegments.top[2],
                        wallSegments.top[3],
                        wallSegments.bottom[2],
                        wallSegments.bottom[3],
                      ]}
                      stroke={wallStrokeColor}
                      strokeWidth={wallOutlineStrokeWidth}
                      lineCap="butt"
                      opacity={wallPreviewOpacity}
                      listening={false}
                    />
                    <Line
                      points={[x1, y1, x2, y2]}
                      stroke={wallStrokeColor}
                      strokeWidth={Math.max(8, thicknessPx + 6)}
                      opacity={0.01}
                      listening={wallsInteractive && !isBlocked}
                      draggable={wallsInteractive && !isBlocked && isSelected && selectedTool === 'select'}
                      onDragMove={wallsInteractive && !isBlocked ? ((e) => handleWallDrag(wall.id, e)) : undefined}
                      onDragEnd={wallsInteractive && !isBlocked ? ((e) => handleWallDragEnd(wall.id, wall, e)) : undefined}
                      onClick={wallsInteractive && !isBlocked ? ((e) => {
                        e.cancelBubble = true;
                        setSelectedElement({ type: 'wall', id: wall.id, data: wall });
                        setSelectedElements([{ type: 'wall', id: wall.id }]);
                      }) : undefined}
                      onMouseEnter={wallsInteractive && !isBlocked ? ((e) => {
                        handleCanvasElementEnter('wall', wall.id, e, isSelected ? 'move' : 'pointer');
                      }) : undefined}
                      onMouseMove={wallsInteractive && !isBlocked ? ((e) => {
                        handleCanvasElementMove('wall', wall.id, e);
                      }) : undefined}
                      onMouseLeave={wallsInteractive && !isBlocked ? handleCanvasElementLeave : undefined}
                    />
                    {isSelected && wallsInteractive && (
                      <>
                        {/* Точка начала стены */}
                        <Circle
                          x={circleX1}
                          y={circleY1}
                          radius={6}
                          fill="white"
                          stroke="blue"
                          strokeWidth={2}
                          draggable
                          opacity={wallPreviewOpacity}
                          onDragStart={() => saveToHistory()}
                          onDragMove={(e) => handleWallPointDrag(wall.id, 'start', e)}
                          onDragEnd={(e) => handleWallPointDragEnd(wall.id, 'start', e)}
                          onMouseEnter={(e) => {
                            e.target.getStage().container().style.cursor = 'move';
                          }}
                          onMouseLeave={(e) => {
                            e.target.getStage().container().style.cursor = 'default';
                          }}
                        />
                        {/* Точка конца стены */}
                        <Circle
                          x={circleX2}
                          y={circleY2}
                          radius={6}
                          fill="white"
                          stroke="blue"
                          strokeWidth={2}
                          draggable
                          opacity={wallPreviewOpacity}
                          onDragStart={() => saveToHistory()}
                          onDragMove={(e) => handleWallPointDrag(wall.id, 'end', e)}
                          onDragEnd={(e) => handleWallPointDragEnd(wall.id, 'end', e)}
                          onMouseEnter={(e) => {
                            e.target.getStage().container().style.cursor = 'move';
                          }}
                          onMouseLeave={(e) => {
                            e.target.getStage().container().style.cursor = 'default';
                          }}
                        />
                        <Circle
                          x={topMid.x}
                          y={topMid.y}
                          radius={5}
                          fill="white"
                          stroke="#0d6efd"
                          strokeWidth={1.5}
                          draggable
                          opacity={wallPreviewOpacity}
                          onDragStart={() => saveToHistory()}
                          onDragMove={(e) => handleWallThicknessDrag(wall.id, e)}
                          onDragEnd={(e) => handleWallThicknessDragEnd(wall.id, e)}
                        />
                        <Circle
                          x={bottomMid.x}
                          y={bottomMid.y}
                          radius={5}
                          fill="white"
                          stroke="#0d6efd"
                          strokeWidth={1.5}
                          draggable
                          opacity={wallPreviewOpacity}
                          onDragStart={() => saveToHistory()}
                          onDragMove={(e) => handleWallThicknessDrag(wall.id, e)}
                          onDragEnd={(e) => handleWallThicknessDragEnd(wall.id, e)}
                        />
                        <DeleteButton
                          x={circleX2 + 10}
                          y={circleY2 - 10}
                          onClick={(e) => {
                            e.cancelBubble = true;
                            handleDeleteElement('walls', wall.id);
                          }}
                        />
                      </>
                    )}
                  </React.Fragment>
                );
              })}

              {/* Render New Walls (not yet saved) */}
              {!selectedDebugImage && showWallsOnCanvas && newWalls.map((wall) => {
                const isSelected = (selectedElement?.type === 'new-wall' && selectedElement?.id === wall.id)
                  || selectedElements.some((item) => item.type === 'new-wall' && item.id === wall.id);
                const isBlocked = isElementInteractionBlocked('new-wall', wall.id);
                const isHovered = hoveredElement?.type === 'new-wall' && hoveredElement?.id === wall.id;
                const thicknessPx = getWallThicknessPx(wall, floorPlan?.scale_factor);
                const wallStrokeColor = useArchitectBlack
                  ? '#111111'
                  : (isSelected ? 'blue' : (isHovered ? 'orange' : WALL_COLOR));
                const wallSegments = getWallOutline(wall);
                const wallOutlineStrokeWidth = 0;
                const topMid = {
                  x: (wallSegments.top[0] + wallSegments.top[2]) / 2,
                  y: (wallSegments.top[1] + wallSegments.top[3]) / 2,
                };
                const bottomMid = {
                  x: (wallSegments.bottom[0] + wallSegments.bottom[2]) / 2,
                  y: (wallSegments.bottom[1] + wallSegments.bottom[3]) / 2,
                };
                return (
                  <React.Fragment key={`new-wall-${wall.id}`}>
                    <Line
                      points={wallSegments.top}
                      stroke={wallStrokeColor}
                      strokeWidth={wallOutlineStrokeWidth}
                      lineCap="round"
                      listening={false}
                    />
                    <Line
                      points={wallSegments.bottom}
                      stroke={wallStrokeColor}
                      strokeWidth={wallOutlineStrokeWidth}
                      lineCap="round"
                      listening={false}
                    />
                    <Line
                      points={[
                        wallSegments.top[0],
                        wallSegments.top[1],
                        wallSegments.bottom[0],
                        wallSegments.bottom[1],
                      ]}
                      stroke={wallStrokeColor}
                      strokeWidth={wallOutlineStrokeWidth}
                      lineCap="round"
                      listening={false}
                    />
                    <Line
                      points={[
                        wallSegments.top[2],
                        wallSegments.top[3],
                        wallSegments.bottom[2],
                        wallSegments.bottom[3],
                      ]}
                      stroke={wallStrokeColor}
                      strokeWidth={wallOutlineStrokeWidth}
                      lineCap="round"
                      listening={false}
                    />
                    <Line
                      points={[wall.x1, wall.y1, wall.x2, wall.y2]}
                      stroke={wallStrokeColor}
                      strokeWidth={Math.max(8, thicknessPx + 6)}
                      opacity={0.01}
                      listening={!isBlocked}
                      draggable={!isBlocked && isSelected && selectedTool === 'select'}
                      onDragMove={!isBlocked ? ((e) => handleNewWallDrag(wall.id, e)) : undefined}
                      onDragEnd={!isBlocked ? ((e) => handleNewWallDragEnd(wall.id, wall, e)) : undefined}
                      onClick={!isBlocked ? ((e) => {
                        e.cancelBubble = true;
                        setSelectedElement({ type: 'new-wall', id: wall.id, data: wall });
                        setSelectedElements([{ type: 'new-wall', id: wall.id }]);
                      }) : undefined}
                      onMouseEnter={!isBlocked ? ((e) => {
                        handleCanvasElementEnter('new-wall', wall.id, e);
                      }) : undefined}
                      onMouseMove={!isBlocked ? ((e) => {
                        handleCanvasElementMove('new-wall', wall.id, e);
                      }) : undefined}
                      onMouseLeave={!isBlocked ? handleCanvasElementLeave : undefined}
                    />
                    {isSelected && (
                      <>
                        <Circle
                          x={wall.x1}
                          y={wall.y1}
                          radius={6}
                          fill="white"
                          stroke="blue"
                          strokeWidth={2}
                          draggable
                          onDragStart={() => saveToHistory()}
                          onDragMove={(e) => handleNewWallPointDrag(wall.id, 'start', e)}
                          onDragEnd={(e) => handleNewWallPointDragEnd(wall.id, 'start', e)}
                        />
                        <Circle
                          x={wall.x2}
                          y={wall.y2}
                          radius={6}
                          fill="white"
                          stroke="blue"
                          strokeWidth={2}
                          draggable
                          onDragStart={() => saveToHistory()}
                          onDragMove={(e) => handleNewWallPointDrag(wall.id, 'end', e)}
                          onDragEnd={(e) => handleNewWallPointDragEnd(wall.id, 'end', e)}
                        />
                        <Circle
                          x={topMid.x}
                          y={topMid.y}
                          radius={5}
                          fill="white"
                          stroke="#0d6efd"
                          strokeWidth={1.5}
                          draggable
                          onDragStart={() => saveToHistory()}
                          onDragMove={(e) => handleNewWallThicknessDrag(wall.id, e)}
                          onDragEnd={(e) => handleNewWallThicknessDragEnd(wall.id, e)}
                        />
                        <Circle
                          x={bottomMid.x}
                          y={bottomMid.y}
                          radius={5}
                          fill="white"
                          stroke="#0d6efd"
                          strokeWidth={1.5}
                          draggable
                          onDragStart={() => saveToHistory()}
                          onDragMove={(e) => handleNewWallThicknessDrag(wall.id, e)}
                          onDragEnd={(e) => handleNewWallThicknessDragEnd(wall.id, e)}
                        />
                        <DeleteButton
                          x={wall.x2 + 10}
                          y={wall.y2 - 10}
                          onClick={(e) => {
                            e.cancelBubble = true;
                            setNewWalls(prev => prev.filter(w => w.id !== wall.id));
                            setSelectedElement(null);
                            if (newWalls.length === 1 && deletedElements.length === 0) {
                              setHasUnsavedChanges(false);
                            }
                          }}
                        />
                      </>
                    )}
                  </React.Fragment>
                );
              })}

              {/* Render Stairs */}
              {!selectedDebugImage && showStairsOnCanvas && newStairs.map((stair) => {
                const isSelected = (selectedElement?.type === 'new-stair' && selectedElement?.id === stair.id)
                  || selectedElements.some((item) => item.type === 'new-stair' && item.id === stair.id);
                const isBlocked = isElementInteractionBlocked('new-stair', stair.id);
                const isHovered = hoveredElement?.type === 'new-stair' && hoveredElement?.id === stair.id;
                const isDragging = activeDrag?.type === 'new-stairs' && activeDrag?.id === stair.id;
                const stairColor = isPostZkspcView
                  ? '#111111'
                  : (isSelected ? '#5b21b6' : (isHovered ? '#7c3aed' : '#8b5cf6'));
                return (
                  <React.Fragment key={`new-stair-${stair.id}`}>
                    <Group
                      x={stair.x}
                      y={stair.y}
                      opacity={isDragging ? 0.45 : 1}
                      listening={!isBlocked}
                      draggable={!isBlocked && selectedTool === 'select'}
                      onDragStart={!isBlocked ? ((e) => {
                        saveToHistory();
                        setActiveDrag({ type: 'new-stairs', id: stair.id });
                        dragStartRef.current[`new-stairs-${stair.id}`] = { x: e.target.x(), y: e.target.y() };
                      }) : undefined}
                      onDragMove={!isBlocked ? ((e) => {
                        const nextPosition = { x: e.target.x(), y: e.target.y() };
                        if (shiftPressed) {
                          const dragStart = dragStartRef.current[`new-stairs-${stair.id}`];
                          if (dragStart) {
                            const snapped = snapTo45Degrees(dragStart.x, dragStart.y, nextPosition.x, nextPosition.y);
                            nextPosition.x = snapped.x;
                            nextPosition.y = snapped.y;
                            e.target.position(nextPosition);
                          }
                        }
                        setNewStairs((prev) => prev.map((item) => (
                          item.id === stair.id ? { ...item, x: nextPosition.x, y: nextPosition.y } : item
                        )));
                        setHasUnsavedChanges(true);
                      }) : undefined}
                      onDragEnd={!isBlocked ? ((e) => {
                        delete dragStartRef.current[`new-stairs-${stair.id}`];
                        setActiveDrag(null);
                        setNewStairs((prev) => prev.map((item) => (
                          item.id === stair.id ? { ...item, x: e.target.x(), y: e.target.y() } : item
                        )));
                        setHasUnsavedChanges(true);
                      }) : undefined}
                      onMouseEnter={!isBlocked ? ((e) => handleCanvasElementEnter('new-stair', stair.id, e)) : undefined}
                      onMouseMove={!isBlocked ? ((e) => handleCanvasElementMove('new-stair', stair.id, e)) : undefined}
                      onMouseLeave={!isBlocked ? handleCanvasElementLeave : undefined}
                    >
                      <Rect
                        x={0}
                        y={0}
                        width={stair.width}
                        height={stair.height}
                        stroke={stairColor}
                        strokeWidth={2}
                        dash={[8, 4]}
                        fill={isPostZkspcView ? 'rgba(0,0,0,0)' : 'rgba(139,92,246,0.06)'}
                        onClick={(e) => {
                          e.cancelBubble = true;
                          setSelectedElement({ type: 'new-stair', id: stair.id, data: stair });
                          setSelectedElements([{ type: 'new-stair', id: stair.id }]);
                        }}
                      />
                      {getStairGuideLines(stair).map((points, index) => (
                        <Line
                          key={`new-stair-${stair.id}-line-${index}`}
                          points={[points[0] - stair.x, points[1] - stair.y, points[2] - stair.x, points[3] - stair.y]}
                          stroke={stairColor}
                          strokeWidth={1.4}
                          listening={false}
                        />
                      ))}
                    </Group>
                    {isSelected && (
                      <DeleteButton
                        x={stair.x + stair.width + 10}
                        y={stair.y - 10}
                        onClick={(e) => {
                          e.cancelBubble = true;
                          setNewStairs((prev) => prev.filter((item) => item.id !== stair.id));
                          setSelectedElement(null);
                          setSelectedElements([]);
                          if (newWalls.length === 0 && newStairs.length === 1 && deletedElements.length === 0 && Object.keys(modifiedWalls).length === 0 && Object.keys(modifiedElements).length === 0) {
                            setHasUnsavedChanges(false);
                          }
                        }}
                      />
                    )}
                  </React.Fragment>
                );
              })}
              {!selectedDebugImage && showStairsOnCanvas && stairs
                .filter((stair) => !deletedElements.some((del) => del.type === 'stairs' && del.id === stair.id))
                .map((stair) => {
                  const current = getStairCurrentGeometry(stair.id, stair);
                  const isSelected = (selectedElement?.type === 'stair' && selectedElement?.id === stair.id)
                    || selectedElements.some((item) => item.type === 'stair' && item.id === stair.id);
                  const isBlocked = isElementInteractionBlocked('stair', stair.id);
                  const isHovered = hoveredElement?.type === 'stair' && hoveredElement?.id === stair.id;
                  const isDragging = activeDrag?.type === 'stairs' && activeDrag?.id === stair.id;
                  const stairColor = isPostZkspcView
                    ? '#111111'
                    : (isSelected ? '#5b21b6' : (isHovered ? '#7c3aed' : '#8b5cf6'));
                  return (
                    <React.Fragment key={`stair-${stair.id}`}>
                      <Group
                        x={current.x}
                        y={current.y}
                        opacity={isDragging ? 0.45 : 1}
                        listening={!isBlocked}
                        draggable={!isBlocked && selectedTool === 'select'}
                        onDragStart={!isBlocked ? ((e) => handleElementDragStart('stairs', stair.id, e)) : undefined}
                        onDragEnd={!isBlocked ? ((e) => handleElementDragEnd('stairs', stair.id, e)) : undefined}
                        onClick={!isBlocked ? ((e) => {
                          e.cancelBubble = true;
                          setSelectedElement({ type: 'stair', id: stair.id, data: stair });
                          setSelectedElements([{ type: 'stair', id: stair.id }]);
                        }) : undefined}
                        onMouseEnter={!isBlocked ? ((e) => handleCanvasElementEnter('stair', stair.id, e)) : undefined}
                        onMouseMove={!isBlocked ? ((e) => handleCanvasElementMove('stair', stair.id, e)) : undefined}
                        onMouseLeave={!isBlocked ? handleCanvasElementLeave : undefined}
                      >
                        <Rect
                          x={0}
                          y={0}
                          width={current.width}
                          height={current.height}
                          stroke={stairColor}
                          strokeWidth={2}
                          fill={isPostZkspcView
                            ? 'rgba(0,0,0,0)'
                            : (isSelected ? 'rgba(139,92,246,0.14)' : 'rgba(139,92,246,0.06)')}
                        />
                        {getStairGuideLines(current).map((points, index) => (
                          <Line
                            key={`stair-${stair.id}-line-${index}`}
                            points={[points[0] - current.x, points[1] - current.y, points[2] - current.x, points[3] - current.y]}
                            stroke={stairColor}
                            strokeWidth={1.4}
                            listening={false}
                          />
                        ))}
                      </Group>
                      {isSelected && (
                        <DeleteButton
                          x={current.x + current.width + 10}
                          y={current.y - 10}
                          onClick={(e) => {
                            e.cancelBubble = true;
                            handleDeleteElement('stairs', stair.id);
                          }}
                        />
                      )}
                    </React.Fragment>
                  );
                })}

              {!selectedDebugImage && showOpeningsOnCanvas && newDoors.map((door) => {
                const current = getOpeningCurrentGeometry('new-doors', door.id, door);
                const isSelected = (selectedElement?.type === 'new-door' && selectedElement?.id === door.id)
                  || selectedElements.some((item) => item.type === 'new-door' && item.id === door.id);
                const isBlocked = isElementInteractionBlocked('new-door', door.id);
                const isHovered = hoveredElement?.type === 'new-door' && hoveredElement?.id === door.id;
                const isDragging = activeDrag?.type === 'new-doors' && activeDrag?.id === door.id;
                const doorColor = useArchitectBlack
                  ? '#111111'
                  : (isSelected ? '#D92D20' : (isHovered ? '#F04438' : '#FF0000'));
                const halfWidth = current.width / 2;
                const halfHeight = current.height / 2;
                const doorSegments = getDoorSymbolSegmentsForOpening(current);
                const edgeHandles = getOpeningEdgeHandles(current);
                return (
                  <React.Fragment key={`new-door-modern-${door.id}`}>
                    <Group
                      x={current.x + current.width / 2}
                      y={current.y + current.height / 2}
                      rotation={current.rotation_deg || 0}
                      opacity={isDragging ? 0.45 : 1}
                      listening={!isBlocked}
                      draggable={!isBlocked && selectedTool === 'select'}
                      onDragStart={!isBlocked ? ((e) => handleElementDragStart('new-doors', door.id, e)) : undefined}
                      onDragMove={!isBlocked ? ((e) => handleElementDragMove('new-doors', door.id, door, e)) : undefined}
                      onDragEnd={!isBlocked ? ((e) => handleElementDragEnd('new-doors', door.id, e)) : undefined}
                      onClick={!isBlocked ? ((e) => {
                        e.cancelBubble = true;
                        setSelectedElement({ type: 'new-door', id: door.id, data: door });
                        setSelectedElements([{ type: 'new-door', id: door.id }]);
                      }) : undefined}
                      onMouseEnter={!isBlocked ? ((e) => handleCanvasElementEnter('new-door', door.id, e)) : undefined}
                      onMouseMove={!isBlocked ? ((e) => handleCanvasElementMove('new-door', door.id, e)) : undefined}
                      onMouseLeave={!isBlocked ? handleCanvasElementLeave : undefined}
                    >
                      <Line points={doorSegments.start} stroke={doorColor} strokeWidth={2} listening={false} />
                      <Line points={doorSegments.center} stroke={doorColor} strokeWidth={2} listening={false} />
                      <Line points={doorSegments.end} stroke={doorColor} strokeWidth={2} listening={false} />
                      <Rect
                        x={-halfWidth}
                        y={-halfHeight}
                        width={current.width}
                        height={current.height}
                        opacity={0.01}
                      />
                    </Group>
                    {isSelected && edgeHandles && (
                      <>
                        <Circle
                          x={edgeHandles.start.x}
                          y={edgeHandles.start.y}
                          radius={5}
                          fill="white"
                          stroke={doorColor}
                          strokeWidth={2}
                          draggable
                          onDragStart={() => saveToHistory()}
                          onDragMove={(e) => handleOpeningResize('new-doors', door, 'start', e)}
                          onDragEnd={(e) => handleOpeningResize('new-doors', door, 'start', e)}
                        />
                        <Circle
                          x={edgeHandles.end.x}
                          y={edgeHandles.end.y}
                          radius={5}
                          fill="white"
                          stroke={doorColor}
                          strokeWidth={2}
                          draggable
                          onDragStart={() => saveToHistory()}
                          onDragMove={(e) => handleOpeningResize('new-doors', door, 'end', e)}
                          onDragEnd={(e) => handleOpeningResize('new-doors', door, 'end', e)}
                        />
                        <DeleteButton
                          x={current.x + current.width + 10}
                          y={current.y - 10}
                          onClick={(e) => {
                            e.cancelBubble = true;
                            setNewDoors((prev) => prev.filter((item) => item.id !== door.id));
                            clearCanvasSelection();
                            setHasUnsavedChanges(
                              newWalls.length > 0 ||
                              newStairs.length > 0 ||
                              newWindows.length > 0 ||
                              newDoors.length > 1 ||
                              deletedElements.length > 0 ||
                              Object.keys(modifiedWalls).length > 0 ||
                              Object.keys(modifiedElements).length > 0,
                            );
                          }}
                        />
                      </>
                    )}
                  </React.Fragment>
                );
              })}

              {/* Render Doors */}
              {!selectedDebugImage && showOpeningsOnCanvas && doors
                .filter((door) => !deletedElements.some((del) => del.type === 'doors' && del.id === door.id))
                .map((door) => {
                  const current = getOpeningCurrentGeometry('doors', door.id, door);
                  const isSelected = (selectedElement?.type === 'door' && selectedElement?.id === door.id)
                    || selectedElements.some((item) => item.type === 'door' && item.id === door.id);
                  const isBlocked = isElementInteractionBlocked('door', door.id);
                  const isHovered = hoveredElement?.type === 'door' && hoveredElement?.id === door.id;
                  const isDragging = activeDrag?.type === 'doors' && activeDrag?.id === door.id;
                  const doorColor = useArchitectBlack
                    ? '#111111'
                    : (isSelected ? '#D92D20' : (isHovered ? '#F04438' : '#FF0000'));
                  const halfWidth = current.width / 2;
                  const halfHeight = current.height / 2;
                  const doorSegments = getDoorSymbolSegmentsForOpening(current);
                  const edgeHandles = getOpeningEdgeHandles(current);
                  return (
                    <React.Fragment key={`door-modern-${door.id}`}>
                      <Group
                        x={current.x + current.width / 2}
                        y={current.y + current.height / 2}
                        rotation={current.rotation_deg || 0}
                        opacity={isDragging ? 0.45 : 1}
                        listening={!isBlocked}
                        draggable={!isBlocked && selectedTool === 'select'}
                        onDragStart={!isBlocked ? ((e) => handleElementDragStart('doors', door.id, e)) : undefined}
                        onDragMove={!isBlocked ? ((e) => handleElementDragMove('doors', door.id, door, e)) : undefined}
                        onDragEnd={!isBlocked ? ((e) => handleElementDragEnd('doors', door.id, e)) : undefined}
                        onClick={!isBlocked ? ((e) => {
                          e.cancelBubble = true;
                          setSelectedElement({ type: 'door', id: door.id, data: door });
                          setSelectedElements([{ type: 'door', id: door.id }]);
                        }) : undefined}
                        onMouseEnter={!isBlocked ? ((e) => handleCanvasElementEnter('door', door.id, e)) : undefined}
                        onMouseMove={!isBlocked ? ((e) => handleCanvasElementMove('door', door.id, e)) : undefined}
                        onMouseLeave={!isBlocked ? handleCanvasElementLeave : undefined}
                      >
                        <Line points={doorSegments.start} stroke={doorColor} strokeWidth={2} listening={false} />
                        <Line points={doorSegments.center} stroke={doorColor} strokeWidth={2} listening={false} />
                        <Line points={doorSegments.end} stroke={doorColor} strokeWidth={2} listening={false} />
                        <Rect
                          x={-halfWidth}
                          y={-halfHeight}
                          width={current.width}
                          height={current.height}
                          opacity={0.01}
                        />
                      </Group>
                      {isSelected && edgeHandles && (
                        <>
                          <Circle
                            x={edgeHandles.start.x}
                            y={edgeHandles.start.y}
                            radius={5}
                            fill="white"
                            stroke={doorColor}
                            strokeWidth={2}
                            draggable
                            onDragStart={() => saveToHistory()}
                            onDragMove={(e) => handleOpeningResize('doors', door, 'start', e)}
                            onDragEnd={(e) => handleOpeningResize('doors', door, 'start', e)}
                          />
                          <Circle
                            x={edgeHandles.end.x}
                            y={edgeHandles.end.y}
                            radius={5}
                            fill="white"
                            stroke={doorColor}
                            strokeWidth={2}
                            draggable
                            onDragStart={() => saveToHistory()}
                            onDragMove={(e) => handleOpeningResize('doors', door, 'end', e)}
                            onDragEnd={(e) => handleOpeningResize('doors', door, 'end', e)}
                          />
                          <DeleteButton
                            x={current.x + current.width + 10}
                            y={current.y - 10}
                            onClick={(e) => {
                              e.cancelBubble = true;
                              handleDeleteElement('doors', door.id);
                            }}
                          />
                        </>
                      )}
                    </React.Fragment>
                  );
                })}
              {false && !selectedDebugImage && showOpeningsOnCanvas && doors.filter(door => !deletedElements.some(del => del.type === 'doors' && del.id === door.id)).map((door) => {
                const isSelected = selectedElement?.type === 'door' && selectedElement?.id === door.id;
                const isHovered = hoveredElement?.type === 'door' && hoveredElement?.id === door.id;
                
                // Применяем сохраненные изменения позиции
                const doorMod = modifiedElements[`doors-${door.id}`] || {};
                const x = doorMod.x ?? door.x;
                const y = doorMod.y ?? door.y;
                const width = doorMod.width ?? door.width;
                const height = doorMod.height ?? door.height;
                const isHorizontal = width >= height;
                const doorColor = isPostZkspcView
                  ? '#111111'
                  : (isSelected ? '#ff1e1e' : (isHovered ? '#ff3b30' : '#ff0000'));
                const hingeX = isHorizontal ? x : x + width / 2;
                const hingeY = isHorizontal ? y + height / 2 : y;
                const leafX = isHorizontal ? x + width : x + width / 2;
                const leafY = isHorizontal ? y + height / 2 : y + height;
                const arcRadius = isHorizontal ? Math.max(8, width) : Math.max(8, height);
                
                return (
                  <React.Fragment key={`door-${door.id}`}>
                    <Line
                      points={[x, y, x + width, y + height]}
                      stroke={doorColor}
                      strokeWidth={2}
                      listening={false}
                    />
                    <Line
                      points={[hingeX, hingeY, leafX, leafY]}
                      stroke={doorColor}
                      strokeWidth={2}
                      listening={false}
                    />
                    <Arc
                      x={hingeX}
                      y={hingeY}
                      innerRadius={0}
                      outerRadius={arcRadius}
                      angle={90}
                      rotation={isHorizontal ? -90 : 0}
                      stroke={doorColor}
                      strokeWidth={2}
                      fillEnabled={false}
                      listening={false}
                    />
                    <Rect
                      x={x}
                      y={y}
                      width={width}
                      height={height}
                      opacity={0.01}
                      draggable={selectedTool === 'select'}
                      onDragStart={(e) => handleElementDragStart('doors', door.id, e)}
                      onClick={(e) => {
                        e.cancelBubble = true;
                        setSelectedElement({ type: 'door', id: door.id, data: door });
                        setSelectedElements([{ type: 'door', id: door.id }]);
                      }}
                      onDragEnd={(e) => handleElementDragEnd('doors', door.id, e)}
                      onMouseEnter={(e) => {
                        handleCanvasElementEnter('door', door.id, e);
                      }}
                      onMouseMove={(e) => {
                        handleCanvasElementMove('door', door.id, e);
                      }}
                      onMouseLeave={handleCanvasElementLeave}
                    />
                    <Text
                      x={x + 2}
                      y={y - 12}
                      text={`Д${doorNumberMap[door.id] ?? door.id}`}
                      fontSize={10}
                      fill={doorColor}
                    />
                    {isSelected && (
                      <>
                        <DeleteButton
                          x={x + width + 10}
                          y={y - 10}
                          onClick={(e) => {
                            e.cancelBubble = true;
                            handleDeleteElement('doors', door.id);
                          }}
                        />
                        <Group
                          x={x + width + 10}
                          y={y + 16}
                          onClick={(e) => {
                            e.cancelBubble = true;
                            rotateOpeningBy90('doors', door);
                          }}
                        >
                          <Circle radius={10} fill="#fff4f4" stroke={doorColor} strokeWidth={1.5} />
                          <Text text="↻" x={-5} y={-8} fill={doorColor} fontSize={14} />
                        </Group>
                      </>
                    )}
                  </React.Fragment>
                );
              })}

              {!selectedDebugImage && showOpeningsOnCanvas && newWindows.map((windowItem) => {
                const current = getOpeningCurrentGeometry('new-windows', windowItem.id, windowItem);
                const isSelected = (selectedElement?.type === 'new-window' && selectedElement?.id === windowItem.id)
                  || selectedElements.some((item) => item.type === 'new-window' && item.id === windowItem.id);
                const isBlocked = isElementInteractionBlocked('new-window', windowItem.id);
                const isHovered = hoveredElement?.type === 'new-window' && hoveredElement?.id === windowItem.id;
                const isDragging = activeDrag?.type === 'new-windows' && activeDrag?.id === windowItem.id;
                const windowColor = useArchitectBlack
                  ? '#111111'
                  : (isSelected ? '#003FB3' : (isHovered ? '#2F74FF' : '#0057D9'));
                const halfWidth = current.width / 2;
                const halfHeight = current.height / 2;
                const lineOffset = Math.max(2, current.height * 0.18);
                const edgeHandles = getOpeningEdgeHandles(current);
                return (
                  <React.Fragment key={`new-window-modern-${windowItem.id}`}>
                    <Group
                      x={current.x + current.width / 2}
                      y={current.y + current.height / 2}
                      rotation={current.rotation_deg || 0}
                      opacity={isDragging ? 0.45 : 1}
                      listening={!isBlocked}
                      draggable={!isBlocked && selectedTool === 'select'}
                      onDragStart={!isBlocked ? ((e) => handleElementDragStart('new-windows', windowItem.id, e)) : undefined}
                      onDragMove={!isBlocked ? ((e) => handleElementDragMove('new-windows', windowItem.id, windowItem, e)) : undefined}
                      onDragEnd={!isBlocked ? ((e) => handleElementDragEnd('new-windows', windowItem.id, e)) : undefined}
                      onClick={!isBlocked ? ((e) => {
                        e.cancelBubble = true;
                        setSelectedElement({ type: 'new-window', id: windowItem.id, data: windowItem });
                        setSelectedElements([{ type: 'new-window', id: windowItem.id }]);
                      }) : undefined}
                      onMouseEnter={!isBlocked ? ((e) => handleCanvasElementEnter('new-window', windowItem.id, e)) : undefined}
                      onMouseMove={!isBlocked ? ((e) => handleCanvasElementMove('new-window', windowItem.id, e)) : undefined}
                      onMouseLeave={!isBlocked ? handleCanvasElementLeave : undefined}
                    >
                      <Rect
                        x={-halfWidth}
                        y={-halfHeight}
                        width={current.width}
                        height={current.height}
                        stroke={windowColor}
                        strokeWidth={2}
                        listening={false}
                      />
                      <Line
                        points={[-halfWidth + 2, -lineOffset, halfWidth - 2, -lineOffset]}
                        stroke={windowColor}
                        strokeWidth={2}
                        listening={false}
                      />
                      <Line
                        points={[-halfWidth + 2, lineOffset, halfWidth - 2, lineOffset]}
                        stroke={windowColor}
                        strokeWidth={2}
                        listening={false}
                      />
                      <Rect
                        x={-halfWidth}
                        y={-halfHeight}
                        width={current.width}
                        height={current.height}
                        opacity={0.01}
                      />
                    </Group>
                    {isSelected && edgeHandles && (
                      <>
                        <Circle
                          x={edgeHandles.start.x}
                          y={edgeHandles.start.y}
                          radius={5}
                          fill="white"
                          stroke={windowColor}
                          strokeWidth={2}
                          draggable
                          onDragStart={() => saveToHistory()}
                          onDragMove={(e) => handleOpeningResize('new-windows', windowItem, 'start', e)}
                          onDragEnd={(e) => handleOpeningResize('new-windows', windowItem, 'start', e)}
                        />
                        <Circle
                          x={edgeHandles.end.x}
                          y={edgeHandles.end.y}
                          radius={5}
                          fill="white"
                          stroke={windowColor}
                          strokeWidth={2}
                          draggable
                          onDragStart={() => saveToHistory()}
                          onDragMove={(e) => handleOpeningResize('new-windows', windowItem, 'end', e)}
                          onDragEnd={(e) => handleOpeningResize('new-windows', windowItem, 'end', e)}
                        />
                        <DeleteButton
                          x={current.x + current.width + 10}
                          y={current.y - 10}
                          onClick={(e) => {
                            e.cancelBubble = true;
                            setNewWindows((prev) => prev.filter((item) => item.id !== windowItem.id));
                            clearCanvasSelection();
                            setHasUnsavedChanges(
                              newWalls.length > 0 ||
                              newStairs.length > 0 ||
                              newDoors.length > 0 ||
                              newWindows.length > 1 ||
                              deletedElements.length > 0 ||
                              Object.keys(modifiedWalls).length > 0 ||
                              Object.keys(modifiedElements).length > 0,
                            );
                          }}
                        />
                      </>
                    )}
                  </React.Fragment>
                );
              })}

              {/* Render Windows */}
              {!selectedDebugImage && showOpeningsOnCanvas && windows
                .filter((windowItem) => !deletedElements.some((del) => del.type === 'windows' && del.id === windowItem.id))
                .map((windowItem) => {
                  const current = getOpeningCurrentGeometry('windows', windowItem.id, windowItem);
                  const isSelected = (selectedElement?.type === 'window' && selectedElement?.id === windowItem.id)
                    || selectedElements.some((item) => item.type === 'window' && item.id === windowItem.id);
                  const isBlocked = isElementInteractionBlocked('window', windowItem.id);
                  const isHovered = hoveredElement?.type === 'window' && hoveredElement?.id === windowItem.id;
                  const isDragging = activeDrag?.type === 'windows' && activeDrag?.id === windowItem.id;
                  const windowColor = useArchitectBlack
                    ? '#111111'
                    : (isSelected ? '#003FB3' : (isHovered ? '#2F74FF' : '#0057D9'));
                  const halfWidth = current.width / 2;
                  const halfHeight = current.height / 2;
                  const lineOffset = Math.max(2, current.height * 0.18);
                  const edgeHandles = getOpeningEdgeHandles(current);
                  return (
                    <React.Fragment key={`window-modern-${windowItem.id}`}>
                      <Group
                        x={current.x + current.width / 2}
                        y={current.y + current.height / 2}
                        rotation={current.rotation_deg || 0}
                        opacity={isDragging ? 0.45 : 1}
                        listening={!isBlocked}
                        draggable={!isBlocked && selectedTool === 'select'}
                        onDragStart={!isBlocked ? ((e) => handleElementDragStart('windows', windowItem.id, e)) : undefined}
                        onDragMove={!isBlocked ? ((e) => handleElementDragMove('windows', windowItem.id, windowItem, e)) : undefined}
                        onDragEnd={!isBlocked ? ((e) => handleElementDragEnd('windows', windowItem.id, e)) : undefined}
                        onClick={!isBlocked ? ((e) => {
                          e.cancelBubble = true;
                          setSelectedElement({ type: 'window', id: windowItem.id, data: windowItem });
                          setSelectedElements([{ type: 'window', id: windowItem.id }]);
                        }) : undefined}
                        onMouseEnter={!isBlocked ? ((e) => handleCanvasElementEnter('window', windowItem.id, e)) : undefined}
                        onMouseMove={!isBlocked ? ((e) => handleCanvasElementMove('window', windowItem.id, e)) : undefined}
                        onMouseLeave={!isBlocked ? handleCanvasElementLeave : undefined}
                      >
                        <Rect
                          x={-halfWidth}
                          y={-halfHeight}
                          width={current.width}
                          height={current.height}
                          stroke={windowColor}
                          strokeWidth={2}
                          listening={false}
                        />
                        <Line
                          points={[-halfWidth + 2, -lineOffset, halfWidth - 2, -lineOffset]}
                          stroke={windowColor}
                          strokeWidth={2}
                          listening={false}
                        />
                        <Line
                          points={[-halfWidth + 2, lineOffset, halfWidth - 2, lineOffset]}
                          stroke={windowColor}
                          strokeWidth={2}
                          listening={false}
                        />
                        <Rect
                          x={-halfWidth}
                          y={-halfHeight}
                          width={current.width}
                          height={current.height}
                          opacity={0.01}
                        />
                      </Group>
                      {isSelected && edgeHandles && (
                        <>
                          <Circle
                            x={edgeHandles.start.x}
                            y={edgeHandles.start.y}
                            radius={5}
                            fill="white"
                            stroke={windowColor}
                            strokeWidth={2}
                            draggable
                            onDragStart={() => saveToHistory()}
                            onDragMove={(e) => handleOpeningResize('windows', windowItem, 'start', e)}
                            onDragEnd={(e) => handleOpeningResize('windows', windowItem, 'start', e)}
                          />
                          <Circle
                            x={edgeHandles.end.x}
                            y={edgeHandles.end.y}
                            radius={5}
                            fill="white"
                            stroke={windowColor}
                            strokeWidth={2}
                            draggable
                            onDragStart={() => saveToHistory()}
                            onDragMove={(e) => handleOpeningResize('windows', windowItem, 'end', e)}
                            onDragEnd={(e) => handleOpeningResize('windows', windowItem, 'end', e)}
                          />
                          <DeleteButton
                            x={current.x + current.width + 10}
                            y={current.y - 10}
                            onClick={(e) => {
                              e.cancelBubble = true;
                              handleDeleteElement('windows', windowItem.id);
                            }}
                          />
                        </>
                      )}
                    </React.Fragment>
                  );
                })}
              {false && !selectedDebugImage && showOpeningsOnCanvas && windows.filter(window => !deletedElements.some(del => del.type === 'windows' && del.id === window.id)).map((window) => {
                const isSelected = selectedElement?.type === 'window' && selectedElement?.id === window.id;
                const isHovered = hoveredElement?.type === 'window' && hoveredElement?.id === window.id;
                
                // Применяем сохраненные изменения позиции
                const windowMod = modifiedElements[`windows-${window.id}`] || {};
                const x = windowMod.x ?? window.x;
                const y = windowMod.y ?? window.y;
                const width = windowMod.width ?? window.width;
                const height = windowMod.height ?? window.height;
                const isHorizontal = width >= height;
                const windowColor = isPostZkspcView
                  ? '#111111'
                  : (isSelected ? '#0d6efd' : (isHovered ? '#3d8bfd' : '#0b5ed7'));
                
                return (
                  <React.Fragment key={`window-${window.id}`}>
                    <Rect
                      x={x}
                      y={y}
                      width={width}
                      height={height}
                      stroke={windowColor}
                      strokeWidth={2}
                      dash={[4, 2]}
                      listening={false}
                    />
                    <Line
                      points={isHorizontal
                        ? [x + 2, y + height / 3, x + width - 2, y + height / 3]
                        : [x + width / 3, y + 2, x + width / 3, y + height - 2]}
                      stroke={windowColor}
                      strokeWidth={2}
                      listening={false}
                    />
                    <Line
                      points={isHorizontal
                        ? [x + 2, y + (height * 2) / 3, x + width - 2, y + (height * 2) / 3]
                        : [x + (width * 2) / 3, y + 2, x + (width * 2) / 3, y + height - 2]}
                      stroke={windowColor}
                      strokeWidth={2}
                      listening={false}
                    />
                    <Rect
                      x={x}
                      y={y}
                      width={width}
                      height={height}
                      opacity={0.01}
                      draggable={selectedTool === 'select'}
                      onDragStart={(e) => handleElementDragStart('windows', window.id, e)}
                      onClick={(e) => {
                        e.cancelBubble = true;
                        setSelectedElement({ type: 'window', id: window.id, data: window });
                        setSelectedElements([{ type: 'window', id: window.id }]);
                      }}
                      onDragEnd={(e) => handleElementDragEnd('windows', window.id, e)}
                      onMouseEnter={(e) => {
                        handleCanvasElementEnter('window', window.id, e);
                      }}
                      onMouseMove={(e) => {
                        handleCanvasElementMove('window', window.id, e);
                      }}
                      onMouseLeave={handleCanvasElementLeave}
                    />
                    <Text
                      x={x + 2}
                      y={y - 12}
                      text={`О${windowNumberMap[window.id] ?? window.id}`}
                      fontSize={10}
                      fill={windowColor}
                    />
                    {isSelected && (
                      <>
                        <DeleteButton
                          x={x + width + 10}
                          y={y - 10}
                          onClick={(e) => {
                            e.cancelBubble = true;
                            handleDeleteElement('windows', window.id);
                          }}
                        />
                        <Group
                          x={x + width + 10}
                          y={y + 16}
                          onClick={(e) => {
                            e.cancelBubble = true;
                            rotateOpeningBy90('windows', window);
                          }}
                        >
                          <Circle radius={10} fill="#eef4ff" stroke={windowColor} strokeWidth={1.5} />
                          <Text text="↻" x={-5} y={-8} fill={windowColor} fontSize={14} />
                        </Group>
                      </>
                    )}
                  </React.Fragment>
                );
              })}

              {/* Render Rooms */}
              {showRoomsOnCanvas && rooms.filter(room => !deletedElements.some(del => del.type === 'rooms' && del.id === room.id)).map((room, index) => {
                if (!room.boundary_points || room.boundary_points.length < 3) return null;
                const points = room.boundary_points.flat();
                const isSelected = selectedElement?.type === 'room' && selectedElement?.id === room.id;
                const isBlocked = isElementInteractionBlocked('room', room.id);
                const isHovered = hoveredElement?.type === 'room' && hoveredElement?.id === room.id;
                const roomBounds = getBoundingBox(room.boundary_points);
                const isUnserviceable = unserviceableRoomIds.has(room.id);
                const zkspcRoomBlocked = currentViewStep === 'zkspc' && isUnserviceable;
                const zone = roomZoneMap[room.id] || null;
                const zoneColor = zone
                  ? (zkspcStyleMap[Number(zone.zone_number || 1)]?.color || getZkspcStyle(zone, floorPlan?.id).color)
                  : '#7c3aed';
                const roomStrokeColor = isPostZkspcView
                  ? '#111111'
                  : (currentViewStep === 'zkspc' || currentViewStep === 'devices_cables')
                    ? zoneColor
                  : (isSelected ? 'blue' : (isHovered ? 'darkmagenta' : 'purple'));
                const roomFillColor = isPostZkspcView
                  ? 'rgba(0,0,0,0)'
                  : (currentViewStep === 'zkspc' || currentViewStep === 'devices_cables')
                    ? `${zoneColor}33`
                  : (isSelected ? 'rgba(0, 100, 255, 0.2)' : (isHovered ? 'rgba(128, 0, 128, 0.3)' : 'rgba(128, 0, 128, 0.1)'));
                return (
                  <React.Fragment key={`room-${room.id}`}>
                    <Line
                      points={points}
                      stroke={roomStrokeColor}
                      strokeWidth={isSelected || isHovered ? 3 : 2}
                      closed
                      fill={roomFillColor}
                      listening={!isBlocked && !zkspcRoomBlocked}
                      draggable={!isBlocked && !zkspcRoomBlocked && isSelected && selectedTool === 'select'}
                      onDragEnd={!isBlocked ? ((e) => {
                        if (!room.boundary_points?.length) return;
                        const dx = e.target.x();
                        const dy = e.target.y();
                        e.target.position({ x: 0, y: 0 });
                        updateRoomBoundary(room.id, room.boundary_points.map(([x, y]) => [x + dx, y + dy]));
                      }) : undefined}
                      onClick={!isBlocked && !zkspcRoomBlocked ? ((e) => {
                        e.cancelBubble = true;
                        if (currentViewStep === 'zkspc') {
                          handleToggleZkspcRoom(room.id);
                        } else {
                          setSelectedElement({ type: 'room', id: room.id, data: room });
                          setSelectedElements([{ type: 'room', id: room.id }]);
                        }
                      }) : undefined}
                      onMouseEnter={!isBlocked && !zkspcRoomBlocked ? ((e) => {
                        handleCanvasElementEnter('room', room.id, e);
                      }) : undefined}
                      onMouseMove={!isBlocked && !zkspcRoomBlocked ? ((e) => {
                        handleCanvasElementMove('room', room.id, e);
                      }) : undefined}
                      onMouseLeave={!isBlocked && !zkspcRoomBlocked ? handleCanvasElementLeave : undefined}
                    />
                    {isUnserviceable && roomBounds && (
                      <>
                        <Line
                          points={[roomBounds.x, roomBounds.y, roomBounds.x + roomBounds.width, roomBounds.y + roomBounds.height]}
                          stroke="#c1121f"
                          strokeWidth={2}
                          listening={false}
                        />
                        <Line
                          points={[roomBounds.x + roomBounds.width, roomBounds.y, roomBounds.x, roomBounds.y + roomBounds.height]}
                          stroke="#c1121f"
                          strokeWidth={2}
                          listening={false}
                        />
                      </>
                    )}
                    {isSelected && roomBounds && (
                      <>
                        <Rect
                          x={roomBounds.x}
                          y={roomBounds.y}
                          width={roomBounds.width}
                          height={roomBounds.height}
                          stroke="#0d6efd"
                          strokeWidth={1}
                          dash={[5, 4]}
                          listening={false}
                        />
                        <Circle
                          x={roomBounds.x + roomBounds.width}
                          y={roomBounds.y + roomBounds.height}
                          radius={6}
                          fill="white"
                          stroke="#0d6efd"
                          strokeWidth={2}
                          draggable
                          dragBoundFunc={() => ({ x: roomBounds.x + roomBounds.width, y: roomBounds.y + roomBounds.height })}
                          onDragEnd={(e) => {
                            const pointer = getScaledPointer(e);
                            const scaleX = (pointer.x - roomBounds.x) / Math.max(1, roomBounds.width);
                            const scaleY = (pointer.y - roomBounds.y) / Math.max(1, roomBounds.height);
                            const factor = Math.max(0.1, Math.min(5, (scaleX + scaleY) / 2));
                            updateRoomBoundary(
                              room.id,
                              room.boundary_points.map(([x, y]) => ([
                                roomBounds.x + (x - roomBounds.x) * factor,
                                roomBounds.y + (y - roomBounds.y) * factor,
                              ]))
                            );
                          }}
                        />
                      </>
                    )}
                    {isSelected && room.center_x && room.center_y && (
                      <DeleteButton
                        x={room.center_x + 50}
                        y={room.center_y - 20}
                        onClick={(e) => {
                          e.cancelBubble = true;
                          handleDeleteElement('rooms', room.id);
                        }}
                      />
                    )}
                  </React.Fragment>
                );
              })}

              {showZkspcOverlayOnCanvas && currentZkspcZones.map((zone) => {
                const zoneStyle = zkspcStyleMap[Number(zone.zone_number || 1)] || getZkspcStyle(zone, floorPlan?.id);
                const anchor = zoneLabelAnchors[zone.id || zone.zone_number];
                const zoneRooms = visibleRooms.filter((room) => (
                  (zone.room_ids || []).includes(room.id)
                  && room.boundary_points?.length >= 3
                  && !unserviceableRoomIds.has(room.id)
                ));

                if (!zoneRooms.length) {
                  return null;
                }

                return (
                  <React.Fragment key={`zkspc-overlay-${zone.id || zone.zone_number}`}>
                    {zoneRooms.map((room) => {
                      const flatPoints = room.boundary_points.flat();
                      const roomBounds = getPolygonBounds(flatPoints);
                      if (!roomBounds) {
                        return null;
                      }
                      const hatchLines = buildZkspcHatchLines(roomBounds, zoneStyle.hatchSpacing);
                      return (
                        <Group key={`zkspc-room-overlay-${zone.id || zone.zone_number}-${room.id}`} listening={false}>
                          <Group
                            clipFunc={(ctx) => {
                              ctx.beginPath();
                              ctx.moveTo(flatPoints[0], flatPoints[1]);
                              for (let index = 2; index < flatPoints.length; index += 2) {
                                ctx.lineTo(flatPoints[index], flatPoints[index + 1]);
                              }
                              ctx.closePath();
                            }}
                          >
                            <Rect
                              x={roomBounds.x}
                              y={roomBounds.y}
                              width={roomBounds.width}
                              height={roomBounds.height}
                              fill={zoneStyle.fillColor}
                              listening={false}
                            />
                            {hatchLines.map((linePoints, lineIndex) => (
                              <Line
                                key={`zkspc-hatch-${zone.id || zone.zone_number}-${room.id}-${lineIndex}`}
                                points={linePoints}
                                stroke={zoneStyle.hatchColor}
                                strokeWidth={1.4}
                                listening={false}
                              />
                            ))}
                          </Group>
                          {currentViewStep === 'zkspc' && (
                            <Line
                              points={flatPoints}
                              stroke={zoneStyle.outlineColor}
                              strokeWidth={2}
                              closed
                              listening={false}
                            />
                          )}
                        </Group>
                      );
                    })}
                    {anchor && (
                      <Text
                        x={anchor.x - 120}
                        y={anchor.y - 10}
                        width={240}
                        align="center"
                        text={zoneStyle.label}
                        fontSize={16}
                        fontFamily="GOST A"
                        fill={zoneStyle.labelColor}
                        listening={false}
                      />
                    )}
                  </React.Fragment>
                );
              })}

              {isPostZkspcView && visibleRooms.map((room) => {
                const roomBounds = getBoundingBox(room.boundary_points || []);
                if (!unserviceableRoomIds.has(room.id) || !roomBounds) {
                  return null;
                }
                return (
                  <React.Fragment key={`post-zkspc-room-cross-${room.id}`}>
                    <Line
                      points={[roomBounds.x, roomBounds.y, roomBounds.x + roomBounds.width, roomBounds.y + roomBounds.height]}
                      stroke="#111111"
                      strokeWidth={2}
                      listening={false}
                    />
                    <Line
                      points={[roomBounds.x + roomBounds.width, roomBounds.y, roomBounds.x, roomBounds.y + roomBounds.height]}
                      stroke="#111111"
                      strokeWidth={2}
                      listening={false}
                    />
                  </React.Fragment>
                );
              })}

              {/* Render Dimensions */}
              {showDimensionsOnCanvas && visibleDimensions.map((dim) => (
                <Text
                  key={`dim-${dim.id}`}
                  x={dim.x}
                  y={dim.y}
                  text={dim.text || formatDimensionMeters(dim.value)}
                  fontSize={12}
                  fontFamily={CANVAS_FONT_FAMILY}
                  fill="red"
                />
              ))}

              {showCableRoutesOnCanvas && (
                <CableRoutesLayer
                  routes={visibleCableRoutes}
                  selectedElement={selectedElement}
                  hoveredElement={hoveredElement}
                  activeCableHandle={activeCableHandle}
                  isRouteBlocked={(routeId) => (
                    drawingToolActive
                    || (selectionLockActive && !isElementSelected('cable-route', routeId))
                  )}
                  onSelectRoute={(route) => {
                    setSelectedElement({ type: 'cable-route', id: route.id, data: route });
                    setSelectedElements([{ type: 'cable-route', id: route.id }]);
                  }}
                  onHoverEnter={(routeId, e) => handleCanvasElementEnter('cable-route', routeId, e)}
                  onHoverMove={(routeId, e) => handleCanvasElementMove('cable-route', routeId, e)}
                  onHoverLeave={handleCanvasElementLeave}
                  onHandleDragStart={(routeId, pointIndex) => setActiveCableHandle({ routeId, pointIndex })}
                  onHandleDragEnd={handleCableRouteHandleDragEnd}
                  onSegmentDragStart={(routeId, insertIndex) => setActiveCableHandle({ routeId, insertIndex })}
                  onSegmentDragEnd={handleCableRouteSegmentDragEnd}
                  onZcLabelDragEnd={handleZcLabelDragEnd}
                  labelObstacles={cableLabelObstacles}
                  stageBounds={stagePlanBounds}
                />
              )}

              {false && (showCableRoutesOnCanvas && visibleCableRoutes.map((route) => {
                const isSelected = selectedElement?.type === 'cable-route' && selectedElement?.id === route.id;
                const isHovered = hoveredElement?.type === 'cable-route' && hoveredElement?.id === route.id;
                return (
                  <React.Fragment key={`cable-route-${route.id}`}>
                    <Line
                      points={polylineToKonvaPoints(route.polyline_points)}
                      stroke={isSelected ? '#b91c1c' : (isHovered ? '#dc2626' : '#ef4444')}
                      strokeWidth={isSelected || isHovered ? 4 : 3}
                      lineCap="round"
                      lineJoin="round"
                      onClick={(e) => {
                        e.cancelBubble = true;
                        setSelectedElement({ type: 'cable-route', id: route.id, data: route });
                        setSelectedElements([{ type: 'cable-route', id: route.id }]);
                      }}
                      onMouseEnter={(e) => handleCanvasElementEnter('cable-route', route.id, e)}
                      onMouseMove={(e) => handleCanvasElementMove('cable-route', route.id, e)}
                      onMouseLeave={handleCanvasElementLeave}
                    />
                    {isSelected && (route.polyline_points || []).map((point, pointIndex) => (
                      <Circle
                        key={`cable-route-handle-${route.id}-${pointIndex}`}
                        x={point[0]}
                        y={point[1]}
                        radius={5}
                        fill={activeCableHandle?.routeId === route.id && activeCableHandle?.pointIndex === pointIndex ? '#fee2e2' : '#ffffff'}
                        stroke="#dc2626"
                        strokeWidth={2}
                        draggable={pointIndex !== 0 && pointIndex !== (route.polyline_points || []).length - 1}
                        onDragStart={() => setActiveCableHandle({ routeId: route.id, pointIndex })}
                        onDragEnd={(e) => handleCableRouteHandleDragEnd(route, pointIndex, e)}
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
                          draggable
                          onDragStart={() => setActiveCableHandle({ routeId: route.id, insertIndex: pointIndex + 1 })}
                          onDragEnd={(e) => handleCableRouteSegmentDragEnd(route, pointIndex + 1, e)}
                        />
                      );
                    })}
                  </React.Fragment>
                );
              }))}

              {showSignalInstrumentsOnCanvas && visibleSignalInstruments.map((instrument) => {
                const isSelected = selectedElement?.type === 'signal-instrument' && selectedElement?.id === instrument.id;
                const isHovered = hoveredElement?.type === 'signal-instrument' && hoveredElement?.id === instrument.id;
                const isBlocked = drawingToolActive || (selectionLockActive && !isElementSelected('signal-instrument', instrument.id));
                return (
                  <Group
                    key={`signal-instrument-${instrument.id}`}
                    x={instrument.x}
                    y={instrument.y}
                    listening={!isBlocked}
                    draggable={!isBlocked && selectedTool === 'select'}
                    onDragMove={!isBlocked ? ((e) => handleInstrumentDragMove(instrument, e)) : undefined}
                    onDragEnd={!isBlocked ? ((e) => handleInstrumentDragEnd(instrument.id, e)) : undefined}
                    onClick={!isBlocked ? ((e) => {
                      e.cancelBubble = true;
                      setSelectedElement({ type: 'signal-instrument', id: instrument.id, data: instrument });
                      setSelectedElements([{ type: 'signal-instrument', id: instrument.id }]);
                    }) : undefined}
                    onMouseEnter={!isBlocked ? ((e) => {
                      handleCanvasElementEnter('signal-instrument', instrument.id, e, 'move');
                    }) : undefined}
                    onMouseMove={!isBlocked ? ((e) => {
                      handleCanvasElementMove('signal-instrument', instrument.id, e);
                    }) : undefined}
                    onMouseLeave={!isBlocked ? handleCanvasElementLeave : undefined}
                  >
                    <SignalInstrumentSymbol
                      x={0}
                      y={0}
                      instrumentType={instrument.instrument_type}
                      isSelected={isSelected}
                      isHovered={isHovered}
                      listening={false}
                    />
                    {signalInstrumentLabelLayouts[instrument.id] && (
                      <Text
                        x={signalInstrumentLabelLayouts[instrument.id].x - instrument.x}
                        y={signalInstrumentLabelLayouts[instrument.id].y - instrument.y}
                        width={signalInstrumentLabelLayouts[instrument.id].width}
                        align="center"
                        text={getInstrumentLabelText(instrument)}
                        fontSize={11}
                        fontFamily={CANVAS_FONT_FAMILY}
                        fill="#111111"
                        listening={!isBlocked}
                        draggable={!isBlocked && selectedTool === 'select'}
                        onClick={(e) => {
                          e.cancelBubble = true;
                        }}
                        onDragEnd={(e) => handleSignalInstrumentLabelDragEnd(instrument, e)}
                      />
                    )}
                  </Group>
                );
              })}

              {/* Render Fire Alarms */}
              {showFireAlarmsOnCanvas && visibleFireAlarmItems.map(({ kind, alarm }) => {
                const current = getFireAlarmCurrentGeometry(kind, alarm.id, alarm);
                if (!current) {
                  return null;
                }
                const itemType = kind === 'new-fire-alarms' ? 'new-fire-alarm' : 'fire-alarm';
                const isSelected = (
                  (selectedElement?.type === itemType && selectedElement?.id === alarm.id)
                  || selectedElements.some((item) => item.type === itemType && item.id === alarm.id)
                );
                const isBlocked = isElementInteractionBlocked(itemType, alarm.id);
                const isHovered = hoveredElement?.type === itemType && hoveredElement?.id === alarm.id;
                const isDragging = activeDrag?.type === kind && activeDrag?.id === alarm.id;
                const coverageRadiusPx = current.coverage_radius
                  ? millimetersToPx(current.coverage_radius, floorPlan?.scale_factor)
                  : null;
                const room = current.room_id
                  ? rooms.find((item) => item.id === current.room_id)
                  : null;
                const roomBounds = room?.boundary_points?.length ? getBoundingBox(room.boundary_points) : null;
                const label = getFireAlarmCode(current);
                const labelColor = current.device_type === 'manual_call_point' ? '#b91c1c' : '#d32f2f';

                return (
                  <React.Fragment key={`alarm-${kind}-${alarm.id}`}>
                    {coverageRadiusPx && current.device_type !== 'manual_call_point' && (isSelected || isHovered) && (
                      <Circle
                        x={current.x}
                        y={current.y}
                        radius={coverageRadiusPx}
                        fill="rgba(217,45,32,0.08)"
                        stroke="rgba(217,45,32,0.45)"
                        strokeWidth={1.5}
                        dash={[8, 6]}
                        listening={false}
                      />
                    )}
                    {(isDragging || isSelected) && roomBounds && (
                      <>
                        <Line
                          points={[roomBounds.x, current.y, current.x, current.y]}
                          stroke="#d32f2f"
                          strokeWidth={1}
                          dash={[4, 4]}
                          listening={false}
                        />
                        <Line
                          points={[current.x, roomBounds.y, current.x, current.y]}
                          stroke="#d32f2f"
                          strokeWidth={1}
                          dash={[4, 4]}
                          listening={false}
                        />
                        {current.offset_left_m !== null && current.offset_left_m !== undefined && (
                          <Text
                            x={roomBounds.x + 4}
                            y={current.y - 18}
                            text={`${current.offset_left_m.toFixed(2)} м`}
                            fontSize={11}
                            fontFamily={CANVAS_FONT_FAMILY}
                            fill="#9f1239"
                          />
                        )}
                        {current.offset_top_m !== null && current.offset_top_m !== undefined && (
                          <Text
                            x={current.x + 6}
                            y={roomBounds.y + 4}
                            text={`${current.offset_top_m.toFixed(2)} м`}
                            fontSize={11}
                            fontFamily={CANVAS_FONT_FAMILY}
                            fill="#9f1239"
                          />
                        )}
                      </>
                    )}
                    <FireAlarmSymbol
                      x={current.x}
                      y={current.y}
                      deviceType={current.device_type}
                      isSelected={isSelected}
                      isHovered={isHovered}
                      opacity={isDragging ? 0.45 : 1}
                      listening={!isBlocked}
                      draggable={!isBlocked && selectedTool === 'select'}
                      onDragStart={!isBlocked ? ((e) => handleElementDragStart(kind, alarm.id, e)) : undefined}
                      onDragMove={!isBlocked ? ((e) => handleElementDragMove(kind, alarm.id, alarm, e)) : undefined}
                      onDragEnd={!isBlocked ? ((e) => handleElementDragEnd(kind, alarm.id, e)) : undefined}
                      onClick={!isBlocked ? ((e) => {
                        e.cancelBubble = true;
                        if (mergeModeActive) {
                          setSelectedElement(
                            mergeInstrumentId && visibleSignalInstruments.find((item) => item.id === mergeInstrumentId)
                              ? {
                                type: 'signal-instrument',
                                id: mergeInstrumentId,
                                data: visibleSignalInstruments.find((item) => item.id === mergeInstrumentId) || null,
                              }
                              : null,
                          );
                          setSelectedElements((prev) => {
                            const alreadySelected = prev.some((item) => item.type === itemType && item.id === alarm.id);
                            if (e.evt?.shiftKey) {
                              return alreadySelected
                                ? prev.filter((item) => !(item.type === itemType && item.id === alarm.id))
                                : [...prev, { type: itemType, id: alarm.id }];
                            }
                            return [{ type: itemType, id: alarm.id }];
                          });
                          return;
                        }
                        setSelectedElement({ type: itemType, id: alarm.id, data: current });
                        setSelectedElements([{ type: itemType, id: alarm.id }]);
                      }) : undefined}
                      onMouseEnter={!isBlocked ? ((e) => {
                        handleCanvasElementEnter(itemType, alarm.id, e, isSelected ? 'move' : 'pointer');
                      }) : undefined}
                      onMouseMove={!isBlocked ? ((e) => {
                        handleCanvasElementMove(itemType, alarm.id, e);
                      }) : undefined}
                      onMouseLeave={!isBlocked ? handleCanvasElementLeave : undefined}
                    />
                    <Text
                      x={(fireAlarmLabelLayouts[current.id] || estimateTextRect(label, current.x + 12, current.y - 18, 10)).x}
                      y={(fireAlarmLabelLayouts[current.id] || estimateTextRect(label, current.x + 12, current.y - 18, 10)).y}
                      width={(fireAlarmLabelLayouts[current.id] || estimateTextRect(label, current.x + 12, current.y - 18, 10)).width}
                      align="center"
                      text={label}
                      fontSize={10}
                      fontFamily={CANVAS_FONT_FAMILY}
                      fill={labelColor}
                      listening={!isBlocked}
                      draggable={!isBlocked && selectedTool === 'select'}
                      onClick={(e) => {
                        e.cancelBubble = true;
                      }}
                      onDragEnd={(e) => handleFireAlarmLabelDragEnd(kind, alarm.id, alarm, e)}
                    />
                    {isSelected && (
                      <DeleteButton
                        x={current.x + 20}
                        y={current.y - 20}
                        onClick={(e) => {
                          e.cancelBubble = true;
                          if (kind === 'new-fire-alarms') {
                            setNewFireAlarms((prev) => prev.filter((item) => item.id !== alarm.id));
                            setHasUnsavedChanges(true);
                            clearCanvasSelection();
                          } else {
                            handleDeleteElement('fire-alarms', alarm.id);
                          }
                        }}
                      />
                    )}
                  </React.Fragment>
                );
              })}
              {selectionRect && (
                <Rect
                  x={normalizeRect(selectionRect)?.x}
                  y={normalizeRect(selectionRect)?.y}
                  width={normalizeRect(selectionRect)?.width}
                  height={normalizeRect(selectionRect)?.height}
                  stroke="#0d6efd"
                  dash={[6, 4]}
                  strokeWidth={1.5}
                  fill="rgba(13,110,253,0.08)"
                  listening={false}
                />
              )}
              {roomZoneRect && (
                <Rect
                  x={normalizeRect(roomZoneRect)?.x}
                  y={normalizeRect(roomZoneRect)?.y}
                  width={normalizeRect(roomZoneRect)?.width}
                  height={normalizeRect(roomZoneRect)?.height}
                  stroke="#6f42c1"
                  dash={[6, 3]}
                  strokeWidth={1.5}
                  fill="rgba(111,66,193,0.12)"
                  listening={false}
                />
              )}
              {currentViewStep !== 'devices_cables' && selectedElements.length > 1 && selectedGroupBounds && (
                <>
                  <Rect
                    x={selectedGroupBounds.x}
                    y={selectedGroupBounds.y}
                    width={selectedGroupBounds.width}
                    height={selectedGroupBounds.height}
                    stroke="#0d6efd"
                    strokeWidth={1.5}
                    dash={[8, 4]}
                    draggable={selectedTool === 'select' || selectedTool === 'multi-select'}
                    onDragEnd={handleGroupDragEnd}
                    onMouseEnter={(e) => {
                      e.target.getStage().container().style.cursor = 'move';
                    }}
                    onMouseLeave={(e) => {
                      e.target.getStage().container().style.cursor = 'default';
                    }}
                  />
                  <Circle
                    x={selectedGroupBounds.x + selectedGroupBounds.width}
                    y={selectedGroupBounds.y + selectedGroupBounds.height}
                    radius={7}
                    fill="white"
                    stroke="#0d6efd"
                    strokeWidth={2}
                    draggable={selectedTool === 'select' || selectedTool === 'multi-select'}
                    dragBoundFunc={() => ({
                      x: selectedGroupBounds.x + selectedGroupBounds.width,
                      y: selectedGroupBounds.y + selectedGroupBounds.height,
                    })}
                    onDragEnd={handleGroupScaleHandleDragEnd}
                  />
                </>
              )}
              </Group>
            </Layer>
          </Stage>
          )}
        </div>
      </div>

      <div className="editor-right-sidebar">
        <div className="sidebar-section">
          <h3>Информация о плане</h3>
          <label style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginBottom: '8px' }}>
            <span>Название</span>
            <input value={planMetaDraft.name} onChange={(e) => setPlanMetaDraft((prev) => ({ ...prev, name: e.target.value }))} />
          </label>
          <label style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginBottom: '8px' }}>
            <span>Этаж</span>
            <input type="number" min="0" value={planMetaDraft.floor_number} onChange={(e) => setPlanMetaDraft((prev) => ({ ...prev, floor_number: e.target.value }))} />
          </label>
          <label style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginBottom: '8px' }}>
            <span>Высота потолка (м)</span>
            <input
              type="number"
              min="0"
              step="0.1"
              value={planMetaDraft.ceiling_height_m}
              onChange={(e) => setPlanMetaDraft((prev) => ({ ...prev, ceiling_height_m: e.target.value }))}
            />
          </label>
          <p><strong>Размер:</strong> {floorPlan.image_width} × {floorPlan.image_height}px</p>
          <p><strong>Масштаб:</strong> {floorPlan.scale_factor} мм/px</p>
          <p><strong>Обратный масштаб:</strong> 1 px = {formatMetersValue((floorPlan.scale_factor || 0) / 1000, 2)}</p>
          <div style={{ padding: '8px', border: '1px solid #dee2e6', borderRadius: '6px', marginBottom: '8px', background: '#f8f9fa' }}>
            <strong style={{ display: 'block', marginBottom: '6px' }}>Калибровка масштаба</strong>
            <div style={{ fontSize: '12px', color: '#6c757d', marginBottom: '6px' }}>
              Выберите инструмент "Калибровка", поставьте точки A и B на плане и укажите реальное расстояние.
            </div>
            <div style={{ fontSize: '12px', marginBottom: '4px' }}>
              A: {calibrationDraft.start ? `${calibrationDraft.start.x.toFixed(1)}, ${calibrationDraft.start.y.toFixed(1)}` : 'не выбрана'}
            </div>
            <div style={{ fontSize: '12px', marginBottom: '6px' }}>
              B: {calibrationDraft.end ? `${calibrationDraft.end.x.toFixed(1)}, ${calibrationDraft.end.y.toFixed(1)}` : 'не выбрана'}
            </div>
            <label style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginBottom: '6px' }}>
              <span>Реальное расстояние (м)</span>
              <input
                type="number"
                min="0"
                step="0.01"
                value={calibrationDraft.distance_m}
                onChange={(e) => setCalibrationDraft((prev) => ({ ...prev, distance_m: e.target.value }))}
              />
            </label>
            <div style={{ fontSize: '12px', color: '#6c757d' }}>
              px: {calibrationPixelDistance ? calibrationPixelDistance.toFixed(2) : '—'}
            </div>
            <div style={{ fontSize: '12px', color: '#6c757d' }}>
              Новый масштаб: {calibrationScalePreview ? `${calibrationScalePreview.toFixed(2)} мм/px` : '—'}
            </div>
          </div>
          <button className="tool-button" style={{ width: '100%' }} disabled={savingPlanMeta} onClick={handleSavePlanMeta}>
            {savingPlanMeta ? 'Сохранение...' : 'Сохранить параметры'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default FloorPlanEditor;



