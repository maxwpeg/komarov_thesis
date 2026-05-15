import {
  COMMON_SIGNAL_SYSTEM,
  buildDisplayNumberMap,
  buildRoomZoneMap,
  buildZkspcStyleMap,
  createEmptyBatchPayload,
  formatCableMeters,
  formatDimensionMeters,
  formatMetersValue,
  getAutoStairStepCount,
  getBoundingBox,
  getBranchCableRoutes,
  getBranchFireAlarms,
  getBranchSignalInstruments,
  getBranchSoueDevices,
  getDerivedWallLengthMeters,
  getFireAlarmCodePrefix,
  getFireAlarmDisplayCode,
  getFireAlarmDisplayLabel,
  getFireAlarmRoomCoordinates,
  getRoomMetadataForPoint,
  getSignalBranchSummary,
  getSignalSystemLabel,
  getWallBoundarySegments,
  getWallPixelLength,
  getWallThicknessPx,
  metersToPx,
  normalizeAngle360,
  normalizeRect,
  normalizeSignalSystemType,
  parseModifiedElementKey,
  pointInPolygon,
  polylineToKonvaPoints,
  pxToMeters,
  rectsIntersect,
  roomContainsStair,
  shouldShowRouteTerminator,
} from './helpers';

describe('floor plan editor helpers', () => {
  test('computes wall geometry, conversions and formatting helpers', () => {
    expect(getWallThicknessPx({ thickness: 300 }, 10)).toBe(30);
    expect(getWallThicknessPx(null, 0)).toBe(200);
    expect(getWallBoundarySegments(0, 0, 100, 0, 20)).toEqual({
      top: [0, 10, 100, 10],
      bottom: [0, -10, 100, -10],
    });
    expect(formatDimensionMeters(1.234)).toBe('1.23 м');
    expect(formatDimensionMeters(null)).toBe('—');
    expect(getWallPixelLength({ x1: 0, y1: 0, x2: 30, y2: 40 })).toBe(50);
    expect(pxToMeters(50, 10)).toBe(0.5);
    expect(metersToPx(0.5, 10)).toBe(50);
    expect(buildDisplayNumberMap([{ id: 7 }, { id: 9 }])).toEqual({ 7: 1, 9: 2 });
    expect(getDerivedWallLengthMeters({ x1: 0, y1: 0, x2: 30, y2: 40 }, 10)).toBe(0.5);
    expect(getAutoStairStepCount({ width: 140, height: 56, step_axis: 'horizontal' })).toBe(5);
    expect(createEmptyBatchPayload()).toMatchObject({ create_walls: [], update_fire_alarms: [] });
    expect(parseModifiedElementKey('wall-27')).toEqual({ type: 'wall', id: 27 });
    expect(formatMetersValue(2.456, 1)).toBe('2.5 м');
    expect(normalizeAngle360(-30)).toBe(330);
  });

  test('works with bounding boxes, polygons, room metadata and route helpers', () => {
    const polygon = [[0, 0], [100, 0], [100, 100], [0, 100]];
    const bounds = getBoundingBox(polygon);
    expect(bounds).toEqual({ x: 0, y: 0, width: 100, height: 100 });
    expect(normalizeRect({ x: 10, y: 20, width: -5, height: -10 })).toEqual({ x: 5, y: 10, width: 5, height: 10 });
    expect(rectsIntersect({ x: 0, y: 0, width: 10, height: 10 }, { x: 5, y: 5, width: 10, height: 10 })).toBe(true);
    expect(pointInPolygon([50, 50], polygon)).toBe(true);
    expect(pointInPolygon([150, 150], polygon)).toBe(false);

    const rooms = [{ id: 1, boundary_points: polygon }];
    expect(getRoomMetadataForPoint({ x: 20, y: 30 }, rooms, 10)).toEqual({
      room: rooms[0],
      roomId: 1,
      offsetLeftM: 0.2,
      offsetTopM: 0.3,
    });
    expect(getFireAlarmDisplayLabel('manual_call_point')).toMatch(/Ручной/i);
    expect(getFireAlarmCodePrefix('manual_call_point')).toBe('BTM');
    expect(getFireAlarmDisplayCode({ device_type: 'smoke_detector', zone: '2', address: '4' }, 3)).toBe('3BTH2.4');
    expect(getFireAlarmRoomCoordinates({ room_id: 1, offset_left_m: 0.2, offset_top_m: 0.1 }, rooms, 10)).toEqual({
      x: 0.2,
      y: 0.9,
    });
    expect(shouldShowRouteTerminator({ system_type: 'non_addressable', subsystem_type: 'sps', route_kind: 'zone_loop' })).toBe(true);
    expect(roomContainsStair({ boundary_points: polygon }, [{ x: 20, y: 20, width: 20, height: 20 }])).toBe(true);
    expect(polylineToKonvaPoints([[0, 1], [2, 3]])).toEqual([0, 1, 2, 3]);
  });

  test('filters branch data and builds zkspc-related structures', () => {
    const zones = [
      { id: 1, zone_number: 1, room_ids: [1], floor_plan_id: 10 },
      { id: 2, zone_number: 2, room_ids: [2], floor_plan_id: 10 },
    ];
    const rooms = [
      { id: 1, boundary_points: [[0, 0], [50, 0], [50, 50], [0, 50]] },
      { id: 2, boundary_points: [[50, 0], [100, 0], [100, 50], [50, 50]] },
    ];
    const styleMap = buildZkspcStyleMap(zones, rooms, 10);
    expect(styleMap[1].label).toBe('ЗКСПС №1');
    expect(styleMap[2].color).not.toBe(styleMap[1].color);
    expect(buildRoomZoneMap(zones)).toEqual({ 1: zones[0], 2: zones[1] });

    const fireAlarms = [
      { id: 1, system_type: 'addressable' },
      { id: 2, system_type: 'non_addressable' },
    ];
    const devices = [
      { id: 1, system_type: 'addressable' },
      { id: 2, system_type: 'non_addressable' },
    ];
    const routes = [
      { id: 1, system_type: 'addressable', subsystem_type: 'sps', length_m: 12.4 },
      { id: 2, system_type: 'addressable', subsystem_type: 'soue', length_m: 4.1 },
    ];
    const instruments = [
      { id: 1, system_type: 'common' },
      { id: 2, system_type: 'addressable' },
    ];

    expect(normalizeSignalSystemType(COMMON_SIGNAL_SYSTEM)).toBe(COMMON_SIGNAL_SYSTEM);
    expect(normalizeSignalSystemType('unexpected')).toBe('non_addressable');
    expect(getSignalSystemLabel('addressable')).toMatch(/Адресная/i);
    expect(formatCableMeters(3.456)).toBe('3.46 м');
    expect(getBranchFireAlarms(fireAlarms, 'addressable')).toHaveLength(1);
    expect(getBranchSoueDevices(devices, 'addressable')).toHaveLength(1);
    expect(getBranchCableRoutes(routes, 'addressable', 'soue')).toHaveLength(1);
    expect(getBranchSignalInstruments(instruments, 'common')).toHaveLength(1);
    expect(getSignalBranchSummary({ fireAlarms, cableRoutes: routes, systemType: 'addressable', subsystemType: 'sps' })).toEqual({
      detectorCount: 1,
      cableLengthM: 12.4,
    });
  });
});
