import {
  buildLineObstacle,
  buildPlanDrawingBounds,
  buildPointObstacle,
  buildPolylineObstacles,
  inflateRect,
  isRectInsideBounds,
  measurePlanText,
  measureTextRectAtTopLeft,
  measureTextRectFromCenter,
  mergeBounds,
  placePlanText,
  placementToObstacles,
} from './textPlacement';

describe('textPlacement utilities', () => {
  test('builds bounds and obstacle helpers', () => {
    expect(inflateRect({ x: 10, y: 20, width: 30, height: 40 }, 5)).toEqual({
      x: 5,
      y: 15,
      width: 40,
      height: 50,
    });
    expect(isRectInsideBounds({ x: 10, y: 10, width: 20, height: 20 }, { x: 0, y: 0, width: 100, height: 100 })).toBe(true);
    expect(mergeBounds([{ x: 0, y: 0, width: 10, height: 10 }, { x: 5, y: 4, width: 10, height: 12 }])).toEqual({
      x: 0,
      y: 0,
      width: 15,
      height: 16,
    });
    expect(buildPlanDrawingBounds({ imageWidth: 100, imageHeight: 50, geometryBounds: { x: -10, y: 0, width: 20, height: 20 }, padding: 10 })).toEqual({
      x: -20,
      y: -10,
      width: 130,
      height: 70,
    });
    expect(buildLineObstacle({ x: 0, y: 0 }, { x: 10, y: 10 }, 2)).toEqual({
      x: -2,
      y: -2,
      width: 14,
      height: 14,
    });
    expect(buildPolylineObstacles([[0, 0], [10, 10], [10, 20]], 2)).toHaveLength(2);
    expect(buildPointObstacle({ x: 10, y: 10 }, 10, 2)).toEqual({
      x: 3,
      y: 3,
      width: 14,
      height: 14,
    });
  });

  test('measures text and finds a placement inside bounds', () => {
    const metrics = measurePlanText('ARK', 12);
    expect(metrics.width).toBeGreaterThan(0);
    expect(metrics.height).toBeGreaterThan(0);
    expect(measureTextRectAtTopLeft('ARK', 10, 20, 12)).toMatchObject({ x: 10, y: 20 });
    expect(measureTextRectFromCenter('ARK', 50, 60, 12)).toMatchObject({ width: metrics.width, height: metrics.height });

    const placement = placePlanText({
      text: 'ARK',
      fontSize: 12,
      anchor: { x: 50, y: 50 },
      symbolHalfWidth: 10,
      symbolHalfHeight: 10,
      obstacles: [{ x: 45, y: 45, width: 20, height: 20 }],
      bounds: { x: 0, y: 0, width: 200, height: 200 },
    });

    expect(placement).not.toBeNull();
    expect(placement.rect.width).toBeGreaterThan(0);
    expect(placementToObstacles(placement).length).toBeGreaterThan(0);
  });
});
