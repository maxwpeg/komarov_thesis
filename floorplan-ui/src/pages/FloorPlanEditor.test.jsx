import React from 'react';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { __getMockStageProps as getMockStageProps } from 'react-konva';

import FloorPlanEditor from './FloorPlanEditor';
import { buildDisplayCableRoutes, getZcLabelLayout } from './floorPlanEditor/CableRoutesLayer';
import { __setMockBackgroundImageSize } from './floorPlanEditor/CanvasPrimitives';
import { elementsApi, floorPlansApi, pipelineApi, recognitionApi } from '../api/client';
import { createViewportTransform, planPointToViewport } from '../utils/floorPlanGeometry';

const mockNavigate = jest.fn();

jest.mock('konva', () => ({
  Filters: {
    Grayscale: jest.fn(),
  },
}));

jest.mock('react-konva', () => {
  const ReactLocal = require('react');
  let stageProps = null;

  const createComponent = (name, renderText = false) => ReactLocal.forwardRef(({ children, text, ...props }, ref) => {
    if (name === 'Stage') {
      stageProps = props;
    }
    return (
      <div ref={ref} data-konva={name} data-testid={`konva-${name}`}>
        <div
          data-scale-x={props.scaleX}
          data-scale-y={props.scaleY}
          data-offset-x={props.offsetX}
          data-offset-y={props.offsetY}
          data-x={props.x}
          data-y={props.y}
          data-rotation={props.rotation}
        />
        {renderText ? text : children}
      </div>
    );
  });

  return {
    Stage: createComponent('Stage'),
    Layer: createComponent('Layer'),
    Line: createComponent('Line'),
    Rect: createComponent('Rect'),
    Circle: createComponent('Circle'),
    Text: createComponent('Text', true),
    Arc: createComponent('Arc'),
    Image: createComponent('Image'),
    Group: createComponent('Group'),
    __getMockStageProps: () => stageProps,
  };
});

jest.mock('./floorPlanEditor/CanvasPrimitives', () => {
  const ReactLocal = require('react');
  let mockBackgroundImageSize = { width: 400, height: 400 };

  return {
    DeleteButton: ({ onClick }) => <div data-testid="delete-button" onClick={onClick} />,
    BackgroundImage: ({ src, onImageLoad }) => {
      ReactLocal.useEffect(() => {
        if (src && onImageLoad) {
          onImageLoad(mockBackgroundImageSize);
        }
      }, [src, onImageLoad]);
      return src ? <div data-testid="background-image" /> : null;
    },
    FireAlarmSymbol: () => <div data-testid="fire-alarm-symbol" />,
    SignalInstrumentSymbol: () => <div data-testid="signal-instrument-symbol" />,
    __setMockBackgroundImageSize: (size) => {
      mockBackgroundImageSize = size;
    },
  };
});

jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useParams: () => ({ floorPlanId: '1' }),
  useNavigate: () => mockNavigate,
}));

jest.mock('../api/client', () => ({
  floorPlansApi: {
    get: jest.fn(),
    batchSave: jest.fn(),
    autoLayoutFireAlarms: jest.fn(),
    update: jest.fn(),
  },
  pipelineApi: {
    getState: jest.fn(),
    detectWalls: jest.fn(),
    commitWalls: jest.fn(),
    detectOpenings: jest.fn(),
    commitOpenings: jest.fn(),
    detectRooms: jest.fn(),
    commitRooms: jest.fn(),
    detectZkspc: jest.fn(),
    commitZkspc: jest.fn(),
  },
  recognitionApi: {
    process: jest.fn(),
    get: jest.fn(),
    submitFeedback: jest.fn(),
  },
  elementsApi: {
    updateWall: jest.fn(),
    updateRoom: jest.fn(),
    updateDoor: jest.fn(),
    updateWindow: jest.fn(),
    updateStair: jest.fn(),
    createSignalInstrument: jest.fn(),
    updateSignalInstrument: jest.fn(),
    deleteSignalInstrument: jest.fn(),
    recalculateCableRoutes: jest.fn(),
    updateCableRoute: jest.fn(),
  },
}));

const floorPlanResponse = {
  id: 1,
  project_id: 10,
  name: 'Тестовый план',
  floor_number: 1,
  ceiling_height_mm: 3000,
  scale_factor: 10,
  original_image_path: null,
  processed_image_path: null,
  image_width: 400,
  image_height: 400,
  active_signal_system_type: 'non_addressable',
  walls: [
    {
      id: 1,
      floor_plan_id: 1,
      x1: 20,
      y1: 20,
      x2: 220,
      y2: 20,
      thickness: 200,
      length_m: 20,
      length_source: 'manual',
    },
  ],
  stairs: [
    {
      id: 2,
      floor_plan_id: 1,
      x: 40,
      y: 60,
      width: 50,
      height: 90,
      rotation_deg: 0,
      step_count: 5,
      step_axis: 'vertical',
    },
  ],
  doors: [
    {
      id: 3,
      floor_plan_id: 1,
      x: 80,
      y: 20,
      width: 24,
      height: 10,
      rotation_deg: 0,
      wall_id: 1,
    },
  ],
  windows: [
    {
      id: 4,
      floor_plan_id: 1,
      x: 140,
      y: 20,
      width: 28,
      height: 10,
      rotation_deg: 0,
      wall_id: 1,
    },
  ],
  rooms: [
    {
      id: 5,
      floor_plan_id: 1,
      name: 'Тестовая комната',
      room_number: '101',
      boundary_points: [[20, 20], [220, 20], [220, 220], [20, 220]],
      center_x: 120,
      center_y: 120,
      area_sqm: 40,
    },
  ],
  dimensions: [],
  fire_alarms: [],
  zkspc_zones: [
    {
      id: 20,
      floor_plan_id: 1,
      zone_number: 1,
      name: 'ЗКСПС 1',
      area_sqm: 40,
      room_count: 1,
      room_ids: [5],
      is_manual: false,
      is_locked: false,
      compliance_warnings: [],
    },
  ],
  signal_instruments: [
    {
      id: 30,
      floor_plan_id: 1,
      system_type: 'non_addressable',
      instrument_type: 'control_panel',
      x: 30,
      y: 30,
      name: 'ППКП',
      supports_cable_merge: true,
    },
  ],
  cable_routes: [
    {
      id: 40,
      floor_plan_id: 1,
      system_type: 'non_addressable',
      instrument_id: 30,
      route_kind: 'zone_loop',
      route_number: 1,
      polyline_points: [[30, 30], [30, 120], [120, 120]],
      device_ids: [],
      warnings: [],
      length_m: 1.8,
      is_manual: false,
    },
  ],
};

const pipelineStateResponse = {
  active_step: 'zkspc',
  active_signal_system_type: 'non_addressable',
  steps: {
    walls: { status: 'validated' },
    openings: { status: 'validated' },
    rooms: { status: 'validated' },
    zkspc: { status: 'validated' },
  },
  branches: {
    non_addressable: {
      active_step: 'fire_alarms',
      steps: {
        fire_alarms: { status: 'draft' },
        devices_cables: { status: 'draft' },
      },
    },
    addressable: {
      active_step: 'fire_alarms',
      steps: {
        fire_alarms: { status: 'draft' },
        devices_cables: { status: 'draft' },
      },
    },
  },
};

beforeAll(() => {
  Object.defineProperty(HTMLElement.prototype, 'getBoundingClientRect', {
    configurable: true,
    value() {
      return {
        x: 0,
        y: 0,
        top: 0,
        left: 0,
        right: 1200,
        bottom: 800,
        width: 1200,
        height: 800,
        toJSON() {
          return this;
        },
      };
    },
  });
});

beforeEach(() => {
  jest.clearAllMocks();
  __setMockBackgroundImageSize({ width: 400, height: 400 });
  floorPlansApi.get.mockResolvedValue(floorPlanResponse);
  floorPlansApi.batchSave.mockResolvedValue({ floor_plan: floorPlanResponse });
  floorPlansApi.autoLayoutFireAlarms.mockResolvedValue({ devices: [], warnings: [] });
  floorPlansApi.update.mockResolvedValue(floorPlanResponse);
  pipelineApi.getState.mockResolvedValue(pipelineStateResponse);
  pipelineApi.commitWalls.mockResolvedValue({ floor_plan: floorPlanResponse, pipeline_state: pipelineStateResponse });
  pipelineApi.commitOpenings.mockResolvedValue({ floor_plan: floorPlanResponse, pipeline_state: pipelineStateResponse });
  pipelineApi.commitRooms.mockResolvedValue({ floor_plan: floorPlanResponse, pipeline_state: pipelineStateResponse });
  pipelineApi.commitZkspc.mockResolvedValue({ floor_plan: floorPlanResponse, pipeline_state: pipelineStateResponse });
  recognitionApi.get.mockResolvedValue({
    id: 501,
    floor_plan_id: 1,
    status: 'completed',
    recognition_result: {
      walls: [{ id: 1 }],
      openings: [{ id: 1 }],
      rooms: [{ id: 1 }],
      dimensions: [],
    },
    debug_images: [],
  });
  recognitionApi.submitFeedback.mockResolvedValue({
    id: 900,
    recognition_id: 501,
    status: 'approved',
    submitted_at: '2026-04-07T10:00:00Z',
    exported_at: null,
  });
  elementsApi.createSignalInstrument.mockResolvedValue(floorPlanResponse.signal_instruments[0]);
  elementsApi.updateSignalInstrument.mockResolvedValue(floorPlanResponse.signal_instruments[0]);
  elementsApi.deleteSignalInstrument.mockResolvedValue({ message: 'deleted' });
  elementsApi.recalculateCableRoutes.mockResolvedValue(floorPlanResponse.cable_routes);
  elementsApi.updateCableRoute.mockResolvedValue({
    ...floorPlanResponse.cable_routes[0],
    is_manual: true,
  });
  window.alert = jest.fn();
  window.confirm = jest.fn(() => true);
});

function getViewportGroupNode() {
  return document.querySelector('[data-konva="Group"] > div[data-scale-x]');
}

function createMockStageTarget(pointer) {
  const stage = {
    attrs: {},
    className: 'Stage',
    container: () => ({ style: {} }),
    getPointerPosition: () => pointer,
    getStage() {
      return stage;
    },
    getLayer() {
      return stage;
    },
  };
  return stage;
}

test('fire alarm step shows branch selector and zkspc overlay without old mixed-save UI', async () => {
  render(<FloorPlanEditor />);

  await waitFor(() => {
    expect(screen.getByRole('button', { name: 'Дымовой датчик' })).toBeInTheDocument();
  });

  expect(screen.getAllByRole('button', { name: 'Расставить' })).toHaveLength(1);
  expect(screen.getByRole('button', { name: /^Сохранить$/ })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /^Безадресная/i })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /^Адресная/i })).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /Сохранить изменения/i })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /Свести/i })).not.toBeInTheDocument();

  const stageQueries = within(screen.getByTestId('konva-Stage'));
  expect(stageQueries.queryByText(/^С1$/)).not.toBeInTheDocument();
  expect(stageQueries.queryByText(/^Л1$/)).not.toBeInTheDocument();
  expect(stageQueries.queryByText(/^Д1$/)).not.toBeInTheDocument();
  expect(stageQueries.queryByText(/^О1$/)).not.toBeInTheDocument();
  expect(stageQueries.queryByText('Тестовая комната')).not.toBeInTheDocument();
});

test('devices and cables step renders instrument summary and keeps merge actions hidden', async () => {
  pipelineApi.getState.mockResolvedValueOnce({
    ...pipelineStateResponse,
    branches: {
      ...pipelineStateResponse.branches,
      non_addressable: {
        ...pipelineStateResponse.branches.non_addressable,
        active_step: 'devices_cables',
      },
    },
  });

  render(<FloorPlanEditor />);

  await waitFor(() => {
    expect(screen.getByText('6. Приборы и кабели')).toBeInTheDocument();
  });

  expect(screen.getByText('4. ЗКСПС')).toBeInTheDocument();
  expect(screen.getByText('5. Пожарные извещатели')).toBeInTheDocument();
  expect(screen.getByText(/Извещателей:/i)).toBeInTheDocument();
  expect(screen.getByText(/Кабеля:/i)).toBeInTheDocument();
  expect(screen.getByText('ППКП')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /Свести/i })).not.toBeInTheDocument();
});

test('escape always returns the active tool to select', async () => {
  render(<FloorPlanEditor />);

  const selectButton = await screen.findByRole('button', { name: 'Выбрать' });
  const smokeDetectorButton = screen.getByRole('button', { name: 'Дымовой датчик' });

  fireEvent.click(smokeDetectorButton);
  expect(smokeDetectorButton).toHaveClass('active');

  fireEvent.keyDown(window, { key: 'Escape' });

  await waitFor(() => {
    expect(selectButton).toHaveClass('active');
  });
});

test('recognition feedback button appears after recognition and submits corrected sample', async () => {
  render(<FloorPlanEditor />);

  const feedbackButton = await screen.findByRole('button', {
    name: 'Отправить исправленный результат для обучения',
  });

  expect(feedbackButton).toBeEnabled();
  fireEvent.click(feedbackButton);

  await waitFor(() => {
    expect(recognitionApi.submitFeedback).toHaveBeenCalledWith('1');
  });
  expect(screen.getByText('Исправленный результат добавлен в обучающую выборку.')).toBeInTheDocument();
});

test('recognition feedback button stays disabled until architecture steps are validated', async () => {
  pipelineApi.getState.mockResolvedValueOnce({
    ...pipelineStateResponse,
    steps: {
      ...pipelineStateResponse.steps,
      rooms: { status: 'draft' },
    },
  });

  render(<FloorPlanEditor />);

  const feedbackButton = await screen.findByRole('button', {
    name: 'Отправить исправленный результат для обучения',
  });

  expect(feedbackButton).toBeDisabled();
});

test('devices and cables canvas shows ZC terminator for non-addressable route', async () => {
  pipelineApi.getState.mockResolvedValueOnce({
    ...pipelineStateResponse,
    branches: {
      ...pipelineStateResponse.branches,
      non_addressable: {
        ...pipelineStateResponse.branches.non_addressable,
        active_step: 'devices_cables',
      },
    },
  });

  render(<FloorPlanEditor />);

  await waitFor(() => {
    expect(within(screen.getByTestId('konva-Stage')).getByText('ZC')).toBeInTheDocument();
  });
});

test('devices and cables canvas shows ARK label for the control panel', async () => {
  pipelineApi.getState.mockResolvedValueOnce({
    ...pipelineStateResponse,
    branches: {
      ...pipelineStateResponse.branches,
      non_addressable: {
        ...pipelineStateResponse.branches.non_addressable,
        active_step: 'devices_cables',
      },
    },
  });

  render(<FloorPlanEditor />);

  await waitFor(() => {
    expect(within(screen.getByTestId('konva-Stage')).getByText('ARK')).toBeInTheDocument();
  });
});

test('opening step renders the PDF-style door symbol without a swing arc', async () => {
  pipelineApi.getState.mockResolvedValueOnce({
    active_step: 'openings',
    active_signal_system_type: 'non_addressable',
    steps: {
      walls: { status: 'validated' },
      openings: { status: 'draft' },
      rooms: { status: 'draft' },
      zkspc: { status: 'draft' },
    },
    branches: pipelineStateResponse.branches,
  });

  render(<FloorPlanEditor />);

  await waitFor(() => {
    expect(screen.getByText('3. Помещения')).toBeInTheDocument();
  });

  expect(screen.queryAllByTestId('konva-Arc')).toHaveLength(0);
});

test('stage uses measured editor viewport size after loading instead of the 800x600 fallback', async () => {
  render(<FloorPlanEditor />);

  await waitFor(() => {
    const stageProps = getMockStageProps();
    expect(stageProps?.width).toBe(1200);
    expect(stageProps?.height).toBe(800);
  });
});

test('committing a pipeline step persists plan metadata before the step commit request', async () => {
  render(<FloorPlanEditor />);

  await waitFor(() => {
    expect(screen.getAllByRole('textbox').length).toBeGreaterThan(0);
  });

  fireEvent.change(screen.getAllByRole('textbox')[0], {
    target: { value: 'Floor 1 updated' },
  });

  const commitButtons = screen.getAllByRole('button', { name: /Подтвердить/i });
  fireEvent.click(commitButtons[1]);

  await waitFor(() => {
    expect(floorPlansApi.update).toHaveBeenCalled();
    expect(pipelineApi.commitOpenings).toHaveBeenCalled();
  });

  expect(floorPlansApi.update.mock.invocationCallOrder[0]).toBeLessThan(
    pipelineApi.commitOpenings.mock.invocationCallOrder[0],
  );
});

test('display cable routes keep the selected route on axis and offset overlapping neighbors', () => {
  const routes = [
    {
      id: 1,
      route_number: 1,
      polyline_points: [[0, 0], [0, 20], [20, 20]],
    },
    {
      id: 2,
      route_number: 2,
      polyline_points: [[0, 0], [0, 20], [20, 20]],
    },
  ];

  const displayRoutes = buildDisplayCableRoutes(routes, 1);

  expect(displayRoutes[1]).toEqual(routes[0].polyline_points);
  expect(displayRoutes[2][0][0]).not.toBe(routes[1].polyline_points[0][0]);
  expect(displayRoutes[2][1][0]).toBe(displayRoutes[2][0][0]);
  expect(displayRoutes[2][2][1]).not.toBe(routes[1].polyline_points[2][1]);
});

test('display cable routes spread identical segments symmetrically without a selection', () => {
  const routes = [
    {
      id: 10,
      route_number: 1,
      polyline_points: [[0, 0], [0, 20]],
    },
    {
      id: 11,
      route_number: 2,
      polyline_points: [[0, 0], [0, 20]],
    },
  ];

  const displayRoutes = buildDisplayCableRoutes(routes);

  expect(displayRoutes[10][0][0]).toBe(-2);
  expect(displayRoutes[11][0][0]).toBe(2);
  expect(displayRoutes[10][1][0]).toBe(-2);
  expect(displayRoutes[11][1][0]).toBe(2);
});

test('zc label moves to a side candidate when the forward placement is blocked', () => {
  const defaultLayout = getZcLabelLayout({
    polyline: [[0, 0], [20, 0]],
    stageBounds: { x: -40, y: -40, width: 120, height: 80 },
  });
  const blockedLayout = getZcLabelLayout({
    polyline: [[0, 0], [20, 0]],
    stageBounds: { x: -40, y: -40, width: 120, height: 80 },
    obstacles: [defaultLayout],
  });

  expect(blockedLayout).not.toEqual(defaultLayout);
  expect(blockedLayout.x).toBeGreaterThan(20);
  expect(blockedLayout.y).not.toBe(defaultLayout.y);
});

test('zc label falls back behind the terminator when forward and side candidates leave the stage', () => {
  const layout = getZcLabelLayout({
    polyline: [[0, 0], [20, 0]],
    stageBounds: { x: -10, y: -6, width: 36, height: 12 },
  });

  expect(layout.x).toBeLessThan(20);
});

test('panning a zoomed plan does not crash after mouseup clears the pan ref', async () => {
  render(<FloorPlanEditor />);

  await waitFor(() => {
    expect(screen.getByRole('slider')).toBeInTheDocument();
  });

  fireEvent.change(screen.getByRole('slider'), {
    target: { value: '200' },
  });

  const pointer = { x: 200, y: 180 };
  const stage = {
    attrs: {},
    className: 'Stage',
    container: () => ({ style: {} }),
    getPointerPosition: () => pointer,
    getStage() {
      return stage;
    },
    getLayer() {
      return stage;
    },
  };
  const stageProps = getMockStageProps();

  expect(() => {
    act(() => {
      stageProps.onMouseDown({ target: stage });
      pointer.x = 260;
      pointer.y = 240;
      stageProps.onMouseMove({ target: stage });
      stageProps.onMouseUp({ target: stage });
      pointer.x = 300;
      pointer.y = 260;
      stageProps.onMouseMove({ target: stage });
    });
  }).not.toThrow();
});

test('background image load recalculates viewport scale using rendered image dimensions', async () => {
  __setMockBackgroundImageSize({ width: 1000, height: 500 });
  floorPlansApi.get.mockResolvedValueOnce({
    ...floorPlanResponse,
    original_image_path: 'uploads/test-floor.jpeg',
    image_width: 400,
    image_height: 400,
  });
  pipelineApi.getState.mockResolvedValueOnce({
    active_step: 'walls',
    active_signal_system_type: 'non_addressable',
    steps: {
      walls: { status: 'validated' },
      openings: { status: 'draft' },
      rooms: { status: 'draft' },
      zkspc: { status: 'draft' },
    },
    branches: pipelineStateResponse.branches,
  });

  render(<FloorPlanEditor />);

  await screen.findByTestId('background-image');
  const stageProps = getMockStageProps();
  const expectedScale = Math.min(stageProps.width / 1000, stageProps.height / 500);
  const fallbackScale = Math.min(stageProps.width / 400, stageProps.height / 400);

  await waitFor(() => {
    expect(Number(getViewportGroupNode()?.dataset.offsetX)).toBeCloseTo(500, 4);
    expect(Number(getViewportGroupNode()?.dataset.offsetY)).toBeCloseTo(250, 4);
    expect(Number(getViewportGroupNode()?.dataset.scaleX)).toBeCloseTo(expectedScale, 4);
    expect(Number(getViewportGroupNode()?.dataset.scaleX)).not.toBeCloseTo(fallbackScale, 4);
  });
});

test('zoomed pan clamps against rendered image bounds instead of stale api metadata', async () => {
  __setMockBackgroundImageSize({ width: 1000, height: 500 });
  floorPlansApi.get.mockResolvedValueOnce({
    ...floorPlanResponse,
    original_image_path: 'uploads/test-floor.jpeg',
    image_width: 400,
    image_height: 400,
  });
  pipelineApi.getState.mockResolvedValueOnce({
    active_step: 'walls',
    active_signal_system_type: 'non_addressable',
    steps: {
      walls: { status: 'validated' },
      openings: { status: 'draft' },
      rooms: { status: 'draft' },
      zkspc: { status: 'draft' },
    },
    branches: pipelineStateResponse.branches,
  });

  render(<FloorPlanEditor />);

  await screen.findByTestId('background-image');
  const initialStageProps = getMockStageProps();
  const zoomedScale = Math.min(initialStageProps.width / 1000, initialStageProps.height / 500) * 2;
  const expectedMaxPanX = Math.max(0, ((1000 * zoomedScale) - initialStageProps.width) / 2);
  const expectedMaxPanY = Math.max(0, ((500 * zoomedScale) - initialStageProps.height) / 2);
  await waitFor(() => {
    expect(Number(getViewportGroupNode()?.dataset.offsetX)).toBeCloseTo(500, 4);
    expect(Number(getViewportGroupNode()?.dataset.offsetY)).toBeCloseTo(250, 4);
  });

  fireEvent.change(screen.getByRole('slider'), {
    target: { value: '200' },
  });

  const pointer = { x: 200, y: 180 };
  const stage = {
    attrs: {},
    className: 'Stage',
    container: () => ({ style: {} }),
    getPointerPosition: () => pointer,
    getStage() {
      return stage;
    },
    getLayer() {
      return stage;
    },
  };
  const stageProps = getMockStageProps();
  act(() => {
    stageProps.onMouseDown({ target: stage });
  });

  const panningStageProps = getMockStageProps();
  act(() => {
    pointer.x = 1200;
    pointer.y = 1180;
    panningStageProps.onMouseMove({ target: stage });
    panningStageProps.onMouseUp({ target: stage });
  });

  await waitFor(() => {
    expect(Number(getViewportGroupNode()?.dataset.x)).toBeCloseTo((panningStageProps.width / 2) + expectedMaxPanX, 4);
    expect(Number(getViewportGroupNode()?.dataset.y)).toBeCloseTo((panningStageProps.height / 2) + expectedMaxPanY, 4);
  });
});

test('wall toolbar uses thickness and snap controls, and drawing keeps the released endpoint when no snap boundary is hit', async () => {
  pipelineApi.getState.mockResolvedValueOnce({
    active_step: 'walls',
    active_signal_system_type: 'non_addressable',
    steps: {
      walls: { status: 'draft' },
      openings: { status: 'draft' },
      rooms: { status: 'draft' },
      zkspc: { status: 'draft' },
    },
    branches: pipelineStateResponse.branches,
  });

  render(<FloorPlanEditor />);

  await waitFor(() => {
    expect(getMockStageProps()?.width).toBe(1200);
  });

  await waitFor(() => {
    expect(document.querySelectorAll('.editor-toolbar .tool-button').length).toBeGreaterThan(2);
  });

  expect(screen.getByRole('spinbutton', { name: 'Толщина новой стены, м' })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Свободно' })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Прилипание' })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Приклеить все стены' })).toBeInTheDocument();

  const toolbarButtons = document.querySelectorAll('.editor-toolbar .tool-button');
  fireEvent.click(toolbarButtons[2]);

  const stageProps = getMockStageProps();
  const transform = createViewportTransform({
    containerWidth: stageProps.width,
    containerHeight: stageProps.height,
    imageWidth: 400,
    imageHeight: 400,
    zoom: 1,
    pan: { x: 0, y: 0 },
    rotationQuarterTurns: 0,
  });
  const pointer = planPointToViewport({ x: 10, y: 20 }, transform);
  const stage = createMockStageTarget(pointer);

  act(() => {
    stageProps.onClick({ target: stage });
  });

  Object.assign(pointer, planPointToViewport({ x: 100, y: 20 }, transform));

  act(() => {
    getMockStageProps().onClick({ target: stage });
  });

  fireEvent.click(screen.getAllByRole('button', { name: /Подтвердить/i })[0]);

  await waitFor(() => {
    expect(pipelineApi.commitWalls).toHaveBeenCalled();
  });

  const changes = pipelineApi.commitWalls.mock.calls[0][1].changes;
  expect(changes.create_walls).toHaveLength(1);
  expect(changes.create_walls[0]).toMatchObject({
    x1: 10,
    y1: 20,
    x2: 100,
    y2: 20,
    alignment: 'center',
  });
});
