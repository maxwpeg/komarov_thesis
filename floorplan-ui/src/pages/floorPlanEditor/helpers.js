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
    update_walls: [],
    update_stairs: [],
    update_doors: [],
    update_windows: [],
    update_rooms: [],
    update_fire_alarms: [],
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

const ZONE_COLORS = ['#fff1b8', '#d9f7be', '#bae7ff', '#ffd6e7', '#efdbff', '#ffd8bf'];

export function normalizeSignalSystemType(value) {
  return value === 'addressable' ? 'addressable' : 'non_addressable';
}

export function getSignalSystemLabel(value) {
  return normalizeSignalSystemType(value) === 'addressable' ? 'Адресная' : 'Безадресная';
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

export function getZkspcColor(zoneNumber) {
  return ZONE_COLORS[(Math.max(1, Number(zoneNumber || 1)) - 1) % ZONE_COLORS.length];
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

export function getBranchCableRoutes(routes, systemType) {
  return (routes || []).filter((route) => normalizeSignalSystemType(route.system_type) === normalizeSignalSystemType(systemType));
}

export function getBranchSignalInstruments(instruments, systemType) {
  return (instruments || []).filter((instrument) => normalizeSignalSystemType(instrument.system_type) === normalizeSignalSystemType(systemType));
}

export function getSignalBranchSummary({ fireAlarms = [], cableRoutes = [], systemType }) {
  const branchAlarms = getBranchFireAlarms(fireAlarms, systemType);
  const branchRoutes = getBranchCableRoutes(cableRoutes, systemType);
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
