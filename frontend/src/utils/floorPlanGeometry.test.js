import {
  clampViewportPan,
  clampHoverPanelPosition,
  createViewportTransform,
  getVisibleWallBoundarySegments,
  getWallOutlineGeometry,
  metersToPx,
  normalizeOpeningToWall,
  normalizeQuarterTurns,
  normalizeWallIntersections,
  planPointToViewport,
  pxToMeters,
  resolveWallEndpointSnap,
  viewportPointToPlan,
} from './floorPlanGeometry';

describe('floorPlanGeometry', () => {
  test('converts between pixels and meters using scale factor', () => {
    expect(pxToMeters(100, 20)).toBeCloseTo(2);
    expect(metersToPx(2, 20)).toBeCloseTo(100);
  });

  test('normalizes openings using center-only wall thickness even for legacy alignments', () => {
    const walls = [
      { id: 1, x1: 0, y1: 0, x2: 100, y2: 0, thickness: 200, alignment: 'left' },
    ];

    const opening = normalizeOpeningToWall(
      { x: 20, y: 5, width: 40, height: 10 },
      walls,
      10,
    );

    expect(opening.wall_id).toBe(1);
    expect(opening.height).toBeCloseTo(20);
    expect(opening.y).toBeCloseTo(-10);
  });

  test('snaps a dragged endpoint to the nearest long wall boundary within thickness threshold', () => {
    const snapped = resolveWallEndpointSnap(
      { x1: 50, y1: 0, x2: 50, y2: 95, thickness: 200, alignment: 'center' },
      { x: 50, y: 95 },
      [{ id: 1, x1: 0, y1: 100, x2: 100, y2: 100, thickness: 200, alignment: 'center' }],
      10,
      { movingEndpoint: 'end' },
    );

    expect(snapped.x).toBeCloseTo(50);
    expect(snapped.y).toBeCloseTo(90);
  });

  test('keeps the raw endpoint position when the cursor is farther than wall thickness from a boundary', () => {
    const snapped = resolveWallEndpointSnap(
      { x1: 50, y1: 0, x2: 50, y2: 60, thickness: 200, alignment: 'center' },
      { x: 50, y: 60 },
      [{ id: 1, x1: 0, y1: 100, x2: 100, y2: 100, thickness: 200, alignment: 'center' }],
      10,
      { movingEndpoint: 'end' },
    );

    expect(snapped).toEqual({ x: 50, y: 60 });
  });

  test('normalizes a wall end by trimming its short edge to the crossed wall boundary', () => {
    const normalized = normalizeWallIntersections([
      { id: 1, x1: 0, y1: 100, x2: 100, y2: 100, thickness: 200, alignment: 'center' },
      { id: 2, x1: 50, y1: 0, x2: 50, y2: 95, thickness: 200, alignment: 'center' },
    ], 10);

    const trimmedWall = normalized.find((wall) => wall.id === 2);
    expect(trimmedWall.x2).toBeCloseTo(50);
    expect(trimmedWall.y2).toBeCloseTo(90);
    expect(trimmedWall.length_source).toBe('derived');
  });

  test('normalizes a wall start symmetrically when the start short edge crosses another wall', () => {
    const normalized = normalizeWallIntersections([
      { id: 1, x1: 0, y1: 100, x2: 100, y2: 100, thickness: 200, alignment: 'center' },
      { id: 2, x1: 50, y1: 105, x2: 50, y2: 190, thickness: 200, alignment: 'center' },
    ], 10);

    const trimmedWall = normalized.find((wall) => wall.id === 2);
    expect(trimmedWall.x1).toBeCloseTo(50);
    expect(trimmedWall.y1).toBeCloseTo(110);
    expect(trimmedWall.length_source).toBe('derived');
  });

  test('treats left and right alignments identically in center-only wall geometry', () => {
    const leftOutline = getWallOutlineGeometry(
      { x1: 0, y1: 0, x2: 100, y2: 0, thickness: 200, alignment: 'left' },
      10,
    );
    const rightOutline = getWallOutlineGeometry(
      { x1: 0, y1: 0, x2: 100, y2: 0, thickness: 200, alignment: 'right' },
      10,
    );

    expect(leftOutline.top).toEqual(rightOutline.top);
    expect(leftOutline.bottom).toEqual(rightOutline.bottom);
    expect(leftOutline.polygon).toEqual(rightOutline.polygon);
  });

  test('visible wall boundaries omit the shared internal seam at a T-junction', () => {
    const segments = getVisibleWallBoundarySegments([
      { id: 1, x1: 0, y1: 100, x2: 100, y2: 100, thickness: 200, alignment: 'center' },
      { id: 2, x1: 50, y1: 0, x2: 50, y2: 90, thickness: 200, alignment: 'center' },
    ], 10);

    const hasInternalSeam = segments.some(({ points }) => (
      Math.abs(points[1] - 90) < 1e-6
      && Math.abs(points[3] - 90) < 1e-6
      && Math.min(points[0], points[2]) < 50
      && Math.max(points[0], points[2]) > 50
    ));
    expect(hasInternalSeam).toBe(false);
  });

  test('visible wall boundaries keep the far overlap boundary when a wall ends on the opposite face', () => {
    const segments = getVisibleWallBoundarySegments([
      { id: 1, x1: 0, y1: 100, x2: 100, y2: 100, thickness: 200, alignment: 'center' },
      { id: 2, x1: 50, y1: 0, x2: 50, y2: 110, thickness: 200, alignment: 'center' },
    ], 10);

    const hasFarBoundary = segments.some(({ points }) => (
      Math.abs(points[1] - 110) < 1e-6
      && Math.abs(points[3] - 110) < 1e-6
      && Math.min(points[0], points[2]) <= 40 + 1e-6
      && Math.max(points[0], points[2]) >= 60 - 1e-6
    ));
    expect(hasFarBoundary).toBe(true);
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

  test('normalizes viewport quarter turns', () => {
    expect(normalizeQuarterTurns(0)).toBe(0);
    expect(normalizeQuarterTurns(5)).toBe(1);
    expect(normalizeQuarterTurns(-1)).toBe(3);
  });

  test('maps points through rotated viewport transform and back', () => {
    const transform = createViewportTransform({
      containerWidth: 1000,
      containerHeight: 700,
      imageWidth: 400,
      imageHeight: 200,
      zoom: 1.2,
      pan: { x: 30, y: -20 },
      rotationQuarterTurns: 1,
    });
    const point = { x: 340, y: 60 };

    const viewportPoint = planPointToViewport(point, transform);
    const restoredPoint = viewportPointToPlan(viewportPoint, transform);

    expect(restoredPoint.x).toBeCloseTo(point.x, 4);
    expect(restoredPoint.y).toBeCloseTo(point.y, 4);
  });

  test('fits the plan into the full available stage area by default', () => {
    const transform = createViewportTransform({
      containerWidth: 1000,
      containerHeight: 700,
      imageWidth: 400,
      imageHeight: 200,
      zoom: 1,
    });

    expect(transform.baseScale).toBeCloseTo(2.5);
    expect(transform.scaledWidth).toBeCloseTo(1000);
    expect(transform.scaledHeight).toBeCloseTo(500);
  });

  test('clamps viewport pan to the visible content bounds', () => {
    const clamped = clampViewportPan(
      { x: 500, y: -500 },
      {
        containerWidth: 1000,
        containerHeight: 700,
        imageWidth: 400,
        imageHeight: 200,
        zoom: 2,
      },
    );

    expect(clamped.x).toBeCloseTo(500);
    expect(clamped.y).toBeCloseTo(-150);
  });

  test('resets pan on an axis where the content still fits inside the stage', () => {
    const clamped = clampViewportPan(
      { x: 120, y: 220 },
      {
        containerWidth: 1000,
        containerHeight: 700,
        imageWidth: 400,
        imageHeight: 200,
        zoom: 1,
      },
    );

    expect(clamped.x).toBe(0);
    expect(clamped.y).toBe(0);
  });
});
