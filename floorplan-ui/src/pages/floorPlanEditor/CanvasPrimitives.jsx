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
        text="x"
        fontSize={18}
        fontFamily="GOST A"
        fill="#ffffff"
        fontStyle="bold"
        x={-4.5}
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

export function BackgroundImage({ src, grayscale = true, onImageLoad }) {
  const [image, setImage] = useState(null);
  const imageRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    setImage(null);
    if (!src) {
      return undefined;
    }
    const img = new window.Image();
    img.onload = () => {
      if (cancelled) {
        return;
      }
      setImage(img);
      onImageLoad?.({
        width: Number(img.naturalWidth || img.width || 0),
        height: Number(img.naturalHeight || img.height || 0),
      });
    };
    img.src = `${src}${src.includes('?') ? '&' : '?'}t=${Date.now()}`;
    return () => {
      cancelled = true;
    };
  }, [onImageLoad, src]);

  useEffect(() => {
    if (imageRef.current?.cache && imageRef.current?.getLayer) {
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
      width={Number(image.naturalWidth || image.width || 0)}
      height={Number(image.naturalHeight || image.height || 0)}
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

export function SignalInstrumentSymbol({
  x,
  y,
  instrumentType,
  isSelected,
  isHovered,
  onClick,
  ...rest
}) {
  const highlight = isSelected ? '#0d6efd' : (isHovered ? '#60a5fa' : null);
  const standardStroke = '#111111';

  if (instrumentType === 'control_panel') {
    const width = 40;
    const height = 20;
    return (
      <Group x={x} y={y} onClick={onClick} {...rest}>
        {highlight && (
          <Rect
            x={-(width / 2) - 4}
            y={-(height / 2) - 4}
            width={width + 8}
            height={height + 8}
            stroke={highlight}
            strokeWidth={2}
            cornerRadius={4}
            dash={isSelected ? undefined : [4, 3]}
            listening={false}
          />
        )}
        <Rect
          x={-width / 2}
          y={-height / 2}
          width={width}
          height={height}
          fill="#ffffff"
          stroke={standardStroke}
          strokeWidth={2}
          listening={false}
        />
        <Rect
          x={-width / 2}
          y={-height / 2}
          width={width / 2}
          height={height / 2}
          fill={standardStroke}
          listening={false}
        />
      </Group>
    );
  }

  const size = 28;
  const text = instrumentType === 'loop_controller' ? '\u041a' : '\u041e';
  return (
    <Group x={x} y={y} onClick={onClick} {...rest}>
      {highlight && (
        <Rect
          x={-(size / 2) - 4}
          y={-(size / 2) - 4}
          width={size + 8}
          height={size + 8}
          stroke={highlight}
          strokeWidth={2}
          cornerRadius={6}
          dash={isSelected ? undefined : [4, 3]}
          listening={false}
        />
      )}
      <Rect
        x={-size / 2}
        y={-size / 2}
        width={size}
        height={size}
        fill="#ffffff"
        stroke={standardStroke}
        strokeWidth={2}
        cornerRadius={4}
        listening={false}
      />
      <Text
        text={text}
        x={-6}
        y={-9}
        fontSize={15}
        fill={standardStroke}
        fontFamily="GOST A"
        listening={false}
      />
    </Group>
  );
}
