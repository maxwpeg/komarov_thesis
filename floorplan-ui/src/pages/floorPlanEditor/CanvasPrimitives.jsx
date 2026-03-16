import React, { useEffect, useRef, useState } from 'react';
import { Circle, Group, Image as KonvaImage, Line, Rect, Text } from 'react-konva';
import Konva from 'konva';

export function DeleteButton({ x, y, onClick }) {
  return (
    <Group x={x} y={y}>
      <Circle
        radius={12}
        fill="#df3d35"
        stroke="#b42318"
        strokeWidth={2}
        onClick={onClick}
        onMouseEnter={(e) => {
          e.target.getStage().container().style.cursor = 'pointer';
        }}
        onMouseLeave={(e) => {
          e.target.getStage().container().style.cursor = 'default';
        }}
      />
      <Text
        text="×"
        fontSize={18}
        fontFamily="Arial"
        fill="#ffffff"
        fontStyle="bold"
        x={-5}
        y={-9}
        onClick={onClick}
        onMouseEnter={(e) => {
          e.target.getStage().container().style.cursor = 'pointer';
        }}
        onMouseLeave={(e) => {
          e.target.getStage().container().style.cursor = 'default';
        }}
      />
    </Group>
  );
}

export function BackgroundImage({ src, grayscale = true }) {
  const [image, setImage] = useState(null);
  const imageRef = useRef(null);

  useEffect(() => {
    const img = new window.Image();
    img.src = `${src}?t=${Date.now()}`;
    img.onload = () => {
      setImage(img);
    };
  }, [src]);

  useEffect(() => {
    if (imageRef.current) {
      imageRef.current.cache();
      imageRef.current.getLayer().batchDraw();
    }
  }, [image]);

  if (!image) {
    return null;
  }

  return (
    <KonvaImage
      ref={imageRef}
      image={image}
      filters={grayscale ? [Konva.Filters.Grayscale] : []}
      listening={false}
    />
  );
}

export function FireAlarmSymbol({ x, y, deviceType, isSelected, isHovered, onClick, ...rest }) {
  const stroke = isSelected ? '#d32f2f' : '#f04438';
  const fill = isHovered ? '#fff7f5' : '#ffffff';
  const size = isSelected || isHovered ? 22 : 18;
  const half = size / 2;

  return (
    <Group x={x} y={y} onClick={onClick} {...rest}>
      <Rect
        x={-half}
        y={-half}
        width={size}
        height={size}
        fill={fill}
        stroke={stroke}
        strokeWidth={2}
        cornerRadius={2}
      />
      {deviceType === 'manual_call_point' ? (
        <Group listening={false}>
          <Line
            points={[-5.5, -3.5, -4.8, -0.2, -3, 2.4, 0, 3.2, 3, 2.4, 4.8, -0.2, 5.5, -3.5]}
            stroke={stroke}
            strokeWidth={2.6}
            lineCap="round"
            lineJoin="round"
            listening={false}
          />
          <Line
            points={[0, 3.2, 0, 8]}
            stroke={stroke}
            strokeWidth={2.6}
            lineCap="round"
            listening={false}
          />
        </Group>
      ) : (
        <Group listening={false}>
          <Line
            points={[2.2, -6.6, -1.2, -0.8, 2.6, -0.8, -2.2, 6.6, 1.2, 0.8, -2.6, 0.8]}
            stroke={stroke}
            strokeWidth={2.8}
            lineCap="round"
            lineJoin="round"
            listening={false}
          />
        </Group>
      )}
    </Group>
  );
}
