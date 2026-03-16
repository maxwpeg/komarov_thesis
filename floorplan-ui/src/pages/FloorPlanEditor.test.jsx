import React from 'react';
import { render, screen, waitFor, within } from '@testing-library/react';

import FloorPlanEditor from './FloorPlanEditor';
import { elementsApi, floorPlansApi, pipelineApi } from '../api/client';

const mockNavigate = jest.fn();

jest.mock('konva', () => ({
  Filters: {
    Grayscale: jest.fn(),
  },
}));

jest.mock('react-konva', () => {
  const ReactLocal = require('react');

  const createComponent = (name, renderText = false) => ReactLocal.forwardRef(({ children, text }, ref) => (
    <div ref={ref} data-konva={name} data-testid={`konva-${name}`}>
      {renderText ? text : children}
    </div>
  ));

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
  floorPlansApi.get.mockResolvedValue(floorPlanResponse);
  floorPlansApi.batchSave.mockResolvedValue({ floor_plan: floorPlanResponse });
  floorPlansApi.autoLayoutFireAlarms.mockResolvedValue({ devices: [], warnings: [] });
  floorPlansApi.update.mockResolvedValue(floorPlanResponse);
  pipelineApi.getState.mockResolvedValue(pipelineStateResponse);
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

test('fire alarm step shows branch selector and step actions without old mixed-save UI', async () => {
  render(<FloorPlanEditor />);

  await waitFor(() => {
    expect(screen.getByRole('button', { name: 'Дымовой датчик' })).toBeInTheDocument();
  });

  expect(screen.getAllByRole('button', { name: 'Расставить' })).toHaveLength(1);
  expect(screen.getByRole('button', { name: /^Сохранить$/ })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /^Безадресная/i })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /^Адресная/i })).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /Сохранить изменения/i })).not.toBeInTheDocument();

  const stageQueries = within(screen.getByTestId('konva-Stage'));
  expect(stageQueries.queryByText(/^С1$/)).not.toBeInTheDocument();
  expect(stageQueries.queryByText(/^Л1$/)).not.toBeInTheDocument();
  expect(stageQueries.queryByText(/^Д1$/)).not.toBeInTheDocument();
  expect(stageQueries.queryByText(/^О1$/)).not.toBeInTheDocument();
  expect(stageQueries.queryByText('Тестовая комната')).not.toBeInTheDocument();
});

test('devices and cables step renders instrument summary and new numbered steps', async () => {
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
});
