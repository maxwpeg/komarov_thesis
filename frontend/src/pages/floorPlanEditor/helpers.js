export function getWallThicknessPx(wall, scaleFactor) {
  const scale = scaleFactor && scaleFactor > 0 ? scaleFactor : 1;
  const thicknessMm = wall?.thickness ?? 200;
  return Math.max(4, thicknessMm / scale);
}

export function getWallBoundarySegments(x1, y1, x2, y2, thicknessPx) {
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

export const COMMON_SIGNAL_SYSTEM = 'common';

export function formatDimensionMeters(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return '—';
  }
  return `${Number(value).toFixed(2)} м`;
}

export function getWallPixelLength(wall) {
  if (!wall) {
    return 0;
  }
  const dx = (wall.x2 ?? 0) - (wall.x1 ?? 0);
  const dy = (wall.y2 ?? 0) - (wall.y1 ?? 0);
  return Math.sqrt(dx * dx + dy * dy);
}

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

export function buildDisplayNumberMap(items) {
  return Object.fromEntries(items.map((item, index) => [item.id, index + 1]));
}

export function getDerivedWallLengthMeters(wall, scaleFactor) {
  return pxToMeters(getWallPixelLength(wall), scaleFactor);
}

export function getAutoStairStepCount(stair) {
  const axis = stair?.step_axis || ((stair?.width || 0) >= (stair?.height || 0) ? 'horizontal' : 'vertical');
  const span = axis === 'horizontal' ? Number(stair?.width || 0) : Number(stair?.height || 0);
  return Math.max(2, Math.min(14, Math.round(span / 28)));
}

export function createEmptyBatchPayload() {
  return {
    deleted: [],
    create_walls: [],
    create_stairs: [],
    create_doors: [],
    create_windows: [],
    create_fire_alarms: [],
    create_soue_devices: [],
    update_walls: [],
    update_stairs: [],
    update_doors: [],
    update_windows: [],
    update_rooms: [],
    update_fire_alarms: [],
    update_soue_devices: [],
  };
}

export function parseModifiedElementKey(key) {
  const separator = key.lastIndexOf('-');
  return {
    type: key.slice(0, separator),
    id: parseInt(key.slice(separator + 1), 10),
  };
}

export function formatMetersValue(value, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return '—';
  }
  return `${Number(value).toFixed(digits)} м`;
}

export function normalizeAngle360(angle) {
  const normalized = angle % 360;
  return normalized < 0 ? normalized + 360 : normalized;
}

export function getBoundingBox(points) {
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

export function normalizeRect(rect) {
  if (!rect) {
    return null;
  }
  const x = Math.min(rect.x, rect.x + rect.width);
  const y = Math.min(rect.y, rect.y + rect.height);
  const width = Math.abs(rect.width);
  const height = Math.abs(rect.height);
  return { x, y, width, height };
}

export function rectsIntersect(a, b) {
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

export function pointInPolygon(point, polygon) {
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

export function getRoomMetadataForPoint(point, rooms, scaleFactor) {
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

export function createFireAlarmDraftId() {
  return `temp_fire_alarm_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

export function getFireAlarmDisplayLabel(deviceType) {
  return deviceType === 'manual_call_point' ? 'Ручной извещатель' : 'Дымовой датчик';
}

export function getFireAlarmShortTypeLabel(deviceType) {
  return deviceType === 'manual_call_point' ? 'Ручной' : 'Дымовой';
}

export function getFireAlarmCodePrefix(deviceType) {
  return deviceType === 'manual_call_point' ? 'BTM' : 'BTH';
}

export function getFireAlarmDisplayCode(alarm, floorNumber, fallbackNumber = 1, overrides = {}) {
  const planFloor = floorNumber !== null && floorNumber !== undefined ? String(floorNumber) : '1';
  const loop = String(overrides.zone ?? alarm?.zone ?? '1').trim() || '1';
  const address = String(overrides.address ?? alarm?.address ?? fallbackNumber).trim() || String(fallbackNumber);
  return `${planFloor}${getFireAlarmCodePrefix(alarm?.device_type)}${loop}.${address}`;
}

export function getFireAlarmRoomCoordinates(alarm, rooms, scaleFactor) {
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

export function shouldShowRouteTerminator(route) {
  if (String(route?.subsystem_type || 'sps') !== 'sps') {
    return false;
  }
  const systemType = String(route?.system_type || 'non_addressable');
  const routeKind = String(route?.route_kind || '');
  return systemType === 'non_addressable' && ['zone_loop', 'manual_line'].includes(routeKind);
}

export function roomContainsStair(room, stairs) {
  if (!room?.boundary_points?.length || !stairs?.length) {
    return false;
  }
  return stairs.some((stair) => {
    const centerX = stair.x + (stair.width || 0) / 2;
    const centerY = stair.y + (stair.height || 0) / 2;
    return pointInPolygon([centerX, centerY], room.boundary_points);
  });
}

export const HOVER_PANEL_SIZE = { width: 160, height: 170 };

export const SIGNAL_SYSTEM_OPTIONS = [
  {
    key: 'non_addressable',
    label: 'Безадресная',
    hint: 'Примерная стоимость будет добавлена позже',
  },
  {
    key: 'addressable',
    label: 'Адресная',
    hint: 'Примерная стоимость будет добавлена позже',
  },
];

export const SIGNAL_INSTRUMENT_OPTIONS = [
  { key: 'control_panel', label: 'Контрольный прибор', supportsMerge: true },
  { key: 'loop_controller', label: 'Контроллер шлейфа', supportsMerge: true },
  { key: 'annunciator', label: 'Оповещатель', supportsMerge: false },
];

export const SOUE_VISUAL_STYLE = {
  base: '#0000FF',
  hover: '#2a37ff',
  selected: '#0000c7',
  fill: '#ffffff',
};

function hexToRgb(hexColor) {
  const normalized = String(hexColor || '').replace('#', '');
  if (normalized.length !== 6) {
    return { r: 124, g: 58, b: 237 };
  }
  return {
    r: Number.parseInt(normalized.slice(0, 2), 16),
    g: Number.parseInt(normalized.slice(2, 4), 16),
    b: Number.parseInt(normalized.slice(4, 6), 16),
  };
}

function rgbaFromHex(hexColor, alpha) {
  const { r, g, b } = hexToRgb(hexColor);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function getZoneSeed(zoneNumber, floorPlanId = 0) {
  const safeZone = Math.max(1, Number(zoneNumber || 1));
  const safeFloor = Math.max(0, Number(floorPlanId || 0));
  return Math.abs(((safeFloor + 1) * 92821) + (safeZone * 68917));
}

const ZKSPC_COLOR_PALETTE = [
  '#d94841',
  '#2563eb',
  '#15803d',
  '#f08c00',
  '#7c3aed',
  '#0f766e',
  '#c026d3',
  '#0891b2',
];

function colorDistance(leftHex, rightHex) {
  const left = hexToRgb(leftHex);
  const right = hexToRgb(rightHex);
  return Math.sqrt(
    ((left.r - right.r) ** 2)
    + ((left.g - right.g) ** 2)
    + ((left.b - right.b) ** 2)
  );
}

function roomBoundsTouch(boundsA, boundsB) {
  if (!boundsA || !boundsB) {
    return false;
  }
  const tolerance = 14;
  const minimumOverlap = 18;
  const horizontalOverlap = Math.min(boundsA.x + boundsA.width, boundsB.x + boundsB.width) - Math.max(boundsA.x, boundsB.x);
  const verticalOverlap = Math.min(boundsA.y + boundsA.height, boundsB.y + boundsB.height) - Math.max(boundsA.y, boundsB.y);
  return (
    (
      verticalOverlap >= minimumOverlap
      && (
        Math.abs((boundsA.x + boundsA.width) - boundsB.x) <= tolerance
        || Math.abs((boundsB.x + boundsB.width) - boundsA.x) <= tolerance
      )
    )
    || (
      horizontalOverlap >= minimumOverlap
      && (
        Math.abs((boundsA.y + boundsA.height) - boundsB.y) <= tolerance
        || Math.abs((boundsB.y + boundsB.height) - boundsA.y) <= tolerance
      )
    )
  );
}

function buildZkspcStyle(zoneNumber, floorPlanId, color) {
  const seed = getZoneSeed(zoneNumber, floorPlanId);
  return {
    color,
    fillColor: rgbaFromHex(color, 0.14),
    hatchColor: rgbaFromHex(color, 0.78),
    outlineColor: rgbaFromHex(color, 0.92),
    labelColor: '#111111',
    hatchSpacing: 18 + ((seed % 5) * 3),
    label: `\u0417\u041a\u0421\u041f\u0421 \u2116${zoneNumber}`,
  };
}

export function buildZkspcStyleMap(zones = [], rooms = [], floorPlanId = 0) {
  const preparedZones = (zones || [])
    .filter((zone) => zone?.zone_number !== null && zone?.zone_number !== undefined)
    .map((zone) => ({ ...zone, zone_number: Math.max(1, Number(zone.zone_number || 1)) }));
  if (!preparedZones.length) {
    return {};
  }

  const roomsById = Object.fromEntries((rooms || [])
    .filter((room) => room?.id !== null && room?.id !== undefined)
    .map((room) => [room.id, room]));
  const zoneNumbers = preparedZones.map((zone) => zone.zone_number);
  const adjacency = Object.fromEntries(zoneNumbers.map((zoneNumber) => [zoneNumber, new Set()]));
  const zoneRoomBounds = Object.fromEntries(zoneNumbers.map((zoneNumber) => [zoneNumber, []]));

  preparedZones.forEach((zone) => {
    (zone.room_ids || []).forEach((roomId) => {
      const room = roomsById[roomId];
      const bounds = room?.boundary_points?.length ? getBoundingBox(room.boundary_points) : null;
      if (bounds) {
        zoneRoomBounds[zone.zone_number].push(bounds);
      }
    });
  });

  for (let leftIndex = 0; leftIndex < zoneNumbers.length; leftIndex += 1) {
    const leftZone = zoneNumbers[leftIndex];
    for (let rightIndex = leftIndex + 1; rightIndex < zoneNumbers.length; rightIndex += 1) {
      const rightZone = zoneNumbers[rightIndex];
      const touches = zoneRoomBounds[leftZone].some((leftBounds) => (
        zoneRoomBounds[rightZone].some((rightBounds) => roomBoundsTouch(leftBounds, rightBounds))
      ));
      if (touches) {
        adjacency[leftZone].add(rightZone);
        adjacency[rightZone].add(leftZone);
      }
    }
  }

  const paletteUsage = Array.from({ length: ZKSPC_COLOR_PALETTE.length }, () => 0);
  const assignedIndexes = {};
  const zoneOrder = [...zoneNumbers].sort((leftZone, rightZone) => {
    const degreeDelta = adjacency[rightZone].size - adjacency[leftZone].size;
    if (degreeDelta !== 0) {
      return degreeDelta;
    }
    return leftZone - rightZone;
  });

  zoneOrder.forEach((zoneNumber) => {
    const seedIndex = getZoneSeed(zoneNumber, floorPlanId) % ZKSPC_COLOR_PALETTE.length;
    const rotationRank = Object.fromEntries(
      ZKSPC_COLOR_PALETTE.map((_, offset) => [((seedIndex + offset) % ZKSPC_COLOR_PALETTE.length), offset]),
    );
    const usedNeighborIndexes = [...adjacency[zoneNumber]]
      .filter((neighborZone) => assignedIndexes[neighborZone] !== undefined)
      .map((neighborZone) => assignedIndexes[neighborZone]);
    const candidates = ZKSPC_COLOR_PALETTE
      .map((_, index) => index)
      .filter((index) => !usedNeighborIndexes.includes(index));
    const candidatePool = candidates.length ? candidates : ZKSPC_COLOR_PALETTE.map((_, index) => index);
    candidatePool.sort((leftIndex, rightIndex) => {
      const leftDistance = usedNeighborIndexes.length
        ? Math.min(...usedNeighborIndexes.map((neighborIndex) => colorDistance(ZKSPC_COLOR_PALETTE[leftIndex], ZKSPC_COLOR_PALETTE[neighborIndex])))
        : Number.POSITIVE_INFINITY;
      const rightDistance = usedNeighborIndexes.length
        ? Math.min(...usedNeighborIndexes.map((neighborIndex) => colorDistance(ZKSPC_COLOR_PALETTE[rightIndex], ZKSPC_COLOR_PALETTE[neighborIndex])))
        : Number.POSITIVE_INFINITY;
      if (rightDistance !== leftDistance) {
        return rightDistance - leftDistance;
      }
      if (paletteUsage[leftIndex] !== paletteUsage[rightIndex]) {
        return paletteUsage[leftIndex] - paletteUsage[rightIndex];
      }
      return rotationRank[leftIndex] - rotationRank[rightIndex];
    });
    const chosenIndex = candidatePool[0];
    assignedIndexes[zoneNumber] = chosenIndex;
    paletteUsage[chosenIndex] += 1;
  });

  return Object.fromEntries(zoneNumbers.map((zoneNumber) => {
    const paletteIndex = assignedIndexes[zoneNumber] ?? (getZoneSeed(zoneNumber, floorPlanId) % ZKSPC_COLOR_PALETTE.length);
    return [zoneNumber, buildZkspcStyle(zoneNumber, floorPlanId, ZKSPC_COLOR_PALETTE[paletteIndex])];
  }));
}

export function normalizeSignalSystemType(value) {
  if (value === COMMON_SIGNAL_SYSTEM) {
    return COMMON_SIGNAL_SYSTEM;
  }
  return value === 'addressable' ? 'addressable' : 'non_addressable';
}

export function getSignalSystemLabel(value) {
  const normalized = normalizeSignalSystemType(value);
  if (normalized === COMMON_SIGNAL_SYSTEM) {
    return 'Общий контур';
  }
  return normalized === 'addressable' ? 'Адресная' : 'Безадресная';
}

export function formatCableMeters(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return '0.00 м';
  }
  return `${Number(value).toFixed(2)} м`;
}

export function getSignalInstrumentDefinition(type) {
  return SIGNAL_INSTRUMENT_OPTIONS.find((option) => option.key === type) || SIGNAL_INSTRUMENT_OPTIONS[0];
}

export function getZkspcStyle(zoneOrNumber, floorPlanId = 0) {
  const zoneNumber = typeof zoneOrNumber === 'object'
    ? Number(zoneOrNumber?.zone_number || 1)
    : Number(zoneOrNumber || 1);
  const resolvedFloorPlanId = typeof zoneOrNumber === 'object'
    ? Number(zoneOrNumber?.floor_plan_id || floorPlanId || 0)
    : Number(floorPlanId || 0);
  const color = ZKSPC_COLOR_PALETTE[getZoneSeed(zoneNumber, resolvedFloorPlanId) % ZKSPC_COLOR_PALETTE.length];
  return buildZkspcStyle(zoneNumber, resolvedFloorPlanId, color);
}

export function getZkspcColor(zoneOrNumber, floorPlanId = 0) {
  return getZkspcStyle(zoneOrNumber, floorPlanId).color;
}

function zonePointKey(point) {
  return `${Number(point?.[0] || 0).toFixed(3)}:${Number(point?.[1] || 0).toFixed(3)}`;
}

function zoneEdgeKey(start, end) {
  const startKey = zonePointKey(start);
  const endKey = zonePointKey(end);
  return startKey < endKey ? `${startKey}|${endKey}` : `${endKey}|${startKey}`;
}

export function buildZoneDisplayGeometry(zoneRooms = []) {
  const polygons = (zoneRooms || [])
    .map((room) => (Array.isArray(room?.boundary_points) ? room.boundary_points : room))
    .filter((polygon) => Array.isArray(polygon) && polygon.length >= 3)
    .map((polygon) => polygon.map((point) => [Number(point[0]), Number(point[1])]));

  if (!polygons.length) {
    return [];
  }
  if (polygons.length === 1) {
    return polygons;
  }

  const edgeUsage = new Map();
  polygons.forEach((polygon) => {
    polygon.forEach((point, index) => {
      const nextPoint = polygon[(index + 1) % polygon.length];
      const key = zoneEdgeKey(point, nextPoint);
      edgeUsage.set(key, (edgeUsage.get(key) || 0) + 1);
    });
  });

  const remainingEdges = [];
  polygons.forEach((polygon) => {
    polygon.forEach((point, index) => {
      const nextPoint = polygon[(index + 1) % polygon.length];
      if (edgeUsage.get(zoneEdgeKey(point, nextPoint)) === 1) {
        remainingEdges.push({
          start: [point[0], point[1]],
          end: [nextPoint[0], nextPoint[1]],
        });
      }
    });
  });

  if (!remainingEdges.length) {
    return polygons;
  }

  const rings = [];
  const used = new Set();
  while (used.size < remainingEdges.length) {
    const firstIndex = remainingEdges.findIndex((_, index) => !used.has(index));
    if (firstIndex < 0) {
      break;
    }
    used.add(firstIndex);
    const ring = [[...remainingEdges[firstIndex].start]];
    let cursor = [...remainingEdges[firstIndex].end];
    const firstKey = zonePointKey(remainingEdges[firstIndex].start);

    while (zonePointKey(cursor) !== firstKey) {
      ring.push([...cursor]);
      const nextIndex = remainingEdges.findIndex((edge, index) => (
        !used.has(index)
        && (zonePointKey(edge.start) === zonePointKey(cursor) || zonePointKey(edge.end) === zonePointKey(cursor))
      ));
      if (nextIndex < 0) {
        return polygons;
      }
      used.add(nextIndex);
      const nextEdge = remainingEdges[nextIndex];
      cursor = zonePointKey(nextEdge.start) === zonePointKey(cursor)
        ? [...nextEdge.end]
        : [...nextEdge.start];
    }

    if (ring.length >= 3) {
      rings.push(ring);
    }
  }

  return rings.length ? rings : polygons;
}

export function buildRoomZoneMap(zones) {
  return zones.reduce((acc, zone) => {
    (zone.room_ids || []).forEach((roomId) => {
      acc[roomId] = zone;
    });
    return acc;
  }, {});
}

export function getBranchFireAlarms(fireAlarms, systemType) {
  return (fireAlarms || []).filter((alarm) => normalizeSignalSystemType(alarm.system_type) === normalizeSignalSystemType(systemType));
}

export function getBranchSoueDevices(devices, systemType) {
  return (devices || []).filter((device) => normalizeSignalSystemType(device.system_type) === normalizeSignalSystemType(systemType));
}

export function getBranchCableRoutes(routes, systemType, subsystemType = null) {
  return (routes || []).filter((route) => {
    if (normalizeSignalSystemType(route.system_type) !== normalizeSignalSystemType(systemType)) {
      return false;
    }
    if (!subsystemType) {
      return true;
    }
    return String(route.subsystem_type || 'sps') === String(subsystemType);
  });
}

export function getBranchSignalInstruments(instruments, systemType) {
  return (instruments || []).filter((instrument) => normalizeSignalSystemType(instrument.system_type) === normalizeSignalSystemType(systemType));
}

export function getSignalBranchSummary({ fireAlarms = [], cableRoutes = [], systemType, subsystemType = 'sps' }) {
  const branchAlarms = getBranchFireAlarms(fireAlarms, systemType);
  const branchRoutes = getBranchCableRoutes(cableRoutes, systemType, subsystemType);
  return {
    detectorCount: branchAlarms.length,
    cableLengthM: branchRoutes.reduce((sum, route) => sum + Number(route.length_m || 0), 0),
  };
}

export function groupFireAlarmsByZone(fireAlarms, zones) {
  const zonesById = (zones || []).reduce((acc, zone) => {
    acc[zone.id || zone.zone_number] = zone;
    return acc;
  }, {});
  return (fireAlarms || []).reduce((acc, alarm) => {
    const key = alarm.zkspc_zone_id || alarm.zone || 'ungrouped';
    if (!acc[key]) {
      acc[key] = {
        zone: zonesById[key] || null,
        items: [],
      };
    }
    acc[key].items.push(alarm);
    return acc;
  }, {});
}

export function polylineToKonvaPoints(polyline) {
  return (polyline || []).flatMap((point) => [point[0], point[1]]);
}
