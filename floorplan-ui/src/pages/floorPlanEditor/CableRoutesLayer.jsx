import React from 'react';
import { Circle, Line, Rect } from 'react-konva';

import { polylineToKonvaPoints } from './helpers';

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
}) {
  return routes.map((route) => {
    const isSelected = selectedElement?.type === 'cable-route' && selectedElement?.id === route.id;
    const isHovered = hoveredElement?.type === 'cable-route' && hoveredElement?.id === route.id;
    const isBlocked = typeof isRouteBlocked === 'function' ? isRouteBlocked(route.id) : false;
    return (
      <React.Fragment key={`cable-route-${route.id}`}>
        <Line
          points={polylineToKonvaPoints(route.polyline_points)}
          stroke={isSelected ? '#b91c1c' : (isHovered ? '#dc2626' : '#ef4444')}
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
