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
      const thicknessPx = getWallThicknessPx(wall, scaleFactor);
      const fits =
        projection.along >= -projectionMargin &&
        projection.along <= projection.axis.length + projectionMargin &&
        Math.abs(projection.normal) <= Math.max(thicknessPx * 1.5, projectionMargin);
      return {
        wall,
        projection,
        fits,
        distance: Math.abs(projection.normal),
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
  const thicknessPx = getWallThicknessPx(best.wall, scaleFactor);
  const span = Math.min(openingSpanFromInput(opening, useBoundingRect), axis.length);
  const halfSpan = span / 2;
  const clampedAlong = Math.min(
    Math.max(best.projection.along, halfSpan),
    Math.max(halfSpan, axis.length - halfSpan),
  );
  const centerX = axis.x1 + axis.ux * clampedAlong;
  const centerY = axis.y1 + axis.uy * clampedAlong;

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
