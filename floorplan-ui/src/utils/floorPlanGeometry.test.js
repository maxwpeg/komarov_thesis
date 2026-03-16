import {
  clampHoverPanelPosition,
  metersToPx,
  normalizeOpeningToWall,
  pxToMeters,
} from './floorPlanGeometry';

describe('floorPlanGeometry', () => {
  test('converts between pixels and meters using scale factor', () => {
    expect(pxToMeters(100, 20)).toBeCloseTo(2);
    expect(metersToPx(2, 20)).toBeCloseTo(100);
  });

  test('normalizes opening to nearest wall and syncs thickness', () => {
    const walls = [
      { id: 1, x1: 0, y1: 0, x2: 100, y2: 0, thickness: 200 },
    ];

    const opening = normalizeOpeningToWall(
      { x: 85, y: 25, width: 40, height: 10 },
      walls,
      10,
      { useBoundingRect: false },
    );

    expect(opening.wall_id).toBe(1);
    expect(opening.width).toBeCloseTo(40);
    expect(opening.height).toBeCloseTo(20);
    expect(opening.x).toBeCloseTo(60);
    expect(opening.y).toBeCloseTo(-10);
  });

  test('keeps hover panel inside container bounds', () => {
    const result = clampHoverPanelPosition(
      { x: 790, y: 590 },
      { left: 0, top: 0, width: 800, height: 600 },
      { width: 290, height: 220 },
      12,
    );

    expect(result.left).toBeLessThanOrEqual(800 - 290 - 12);
    expect(result.top).toBeLessThanOrEqual(600 - 220 - 12);
    expect(result.left + 290).toBeLessThanOrEqual(790 - 28);
  });
});
