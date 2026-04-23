import React from 'react';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { __getMockStageProps as getMockStageProps } from 'react-konva';

import FloorPlanEditor, { getInstrumentLabelText } from './FloorPlanEditor';
import { buildDisplayCableRoutes, getZcLabelLayout, getZcTerminatorPoint } from './floorPlanEditor/CableRoutesLayer';
import { __setMockBackgroundImageSize } from './floorPlanEditor/CanvasPrimitives';
import { placePlanText, placementToObstacles } from './floorPlanEditor/textPlacement';
import { elementsApi, equipmentApi, floorPlansApi, pipelineApi, projectsApi, recognitionApi } from '../api/client';
import { createViewportTransform, planPointToViewport } from '../utils/floorPlanGeometry';

const mockNavigate = jest.fn();
let mockSearchParams = new URLSearchParams();
const mockSetSearchParams = jest.fn();

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
      <div
        ref={ref}
        data-konva={name}
        data-testid={`konva-${name}`}
        data-draggable={props.draggable ? 'true' : 'false'}
        data-listening={props.listening === false ? 'false' : 'true'}
      >
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
    FireAlarmSymbol: ({ x, y, rotation = 0 }) => (
      <div
        data-testid="fire-alarm-symbol"
        data-x={x}
        data-y={y}
        data-rotation={rotation}
      />
    ),
    SoueDeviceSymbol: ({ x, y, rotation = 0 }) => (
      <div
        data-testid="soue-device-symbol"
        data-x={x}
        data-y={y}
        data-rotation={rotation}
      />
    ),
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
  useSearchParams: () => [mockSearchParams, mockSetSearchParams],
}));

jest.mock('../api/client', () => ({
  floorPlansApi: {
    get: jest.fn(),
    batchSave: jest.fn(),
    autoLayoutFireAlarms: jest.fn(),
    autoLayoutSoueDevices: jest.fn(),
    update: jest.fn(),
  },
  pipelineApi: {
    getState: jest.fn(),
    detectWalls: jest.fn(),
    commitWalls: jest.fn(),
    detectOpenings: jest.fn(),
    commitOpenings: jest.fn(),
    submitStepFeedback: jest.fn(),
    getFeedbackStats: jest.fn(),
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
  equipmentApi: {
    list: jest.fn(),
  },
  projectsApi: {
    listEquipment: jest.fn(),
    getEquipmentSelections: jest.fn(),
    getGeneralData: jest.fn(),
    updateGeneralData: jest.fn(),
    getGeneralInstructions: jest.fn(),
    updateGeneralInstructions: jest.fn(),
    getPowerConsumptionCalculation: jest.fn(),
    updatePowerConsumptionCalculation: jest.fn(),
    getEquipmentSpecification: jest.fn(),
    updateEquipmentSpecification: jest.fn(),
    getAdditionalInfo: jest.fn(),
    updateAdditionalInfo: jest.fn(),
    attachEquipment: jest.fn(),
  },
  elementsApi: {
    createRoom: jest.fn(),
    updateWall: jest.fn(),
    updateRoom: jest.fn(),
    updateDoor: jest.fn(),
    updateWindow: jest.fn(),
    updateStair: jest.fn(),
    createSignalInstrument: jest.fn(),
    updateSignalInstrument: jest.fn(),
    deleteSignalInstrument: jest.fn(),
    commitSignalInstrumentsStep: jest.fn(),
    mergeRoutesForInstrument: jest.fn(),
    recalculateCableRoutes: jest.fn(),
    commitCableRoutesStep: jest.fn(),
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
  soue_devices: [],
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
      system_type: 'common',
      instrument_type: 'control_panel',
      equipment_id: 401,
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

const equipmentItemsResponse = [
  {
    id: 401,
    name: 'Panel A',
    category: 'instrument',
    price: 5000,
  },
  {
    id: 402,
    name: 'Keyboard A',
    category: 'keyboard',
    price: 1900,
  },
];

const projectEquipmentResponse = {
  project_id: 10,
  items: [equipmentItemsResponse[0]],
};
const projectEquipmentSelectionsResponse = {
  project_id: 10,
  selections: {
    sps_cable: null,
    soue_cable: null,
  },
};
const generalDataResponse = {
  project_id: 10,
  page_title: 'Общие данные',
  left_table_title: 'ВЕДОМОСТЬ ССЫЛОЧНЫХ И ПРИЛАГАЕМЫХ ДОКУМЕНТОВ',
  right_table_title: 'ВЕДОМОСТЬ РАБОЧИХ ЧЕРТЕЖЕЙ ОСНОВНОГО КОМПЛЕКТА',
  reference_category_title: 'Ссылочные документы',
  attached_category_title: 'Прилагаемые документы',
  reference_documents: [
    {
      key: 'reference_document_1',
      designation: 'СП 76.13330.2016',
      name: 'Свод правил. Электротехнические устройства',
      note: '',
    },
  ],
  attached_documents: [
    {
      key: 'attached_document_specification',
      designation: 'P-01',
      name: 'Спецификация оборудования и материалов',
      note: '',
    },
  ],
  drawing_manifest_rows: [
    {
      key: 'general_data',
      name: 'Общие данные',
      sheet_count: 1,
      note: '',
    },
  ],
  statement_text: 'Технические решения соответствуют действующим нормам.',
  gip_name: 'Иванов И.И.',
};
const generalInstructionsResponse = {
  project_id: 10,
  page_title: 'Общие указания',
  heading: 'ОБЩИЕ УКАЗАНИЯ.',
  local_sheet_title: 'Общие указания',
  blocks: [
    {
      key: 'block_1',
      kind: 'section_heading',
      text: '1. Введение',
    },
    {
      key: 'block_2',
      kind: 'paragraph',
      text: 'Рабочая документация подготовлена для объекта.',
    },
    {
      key: 'block_3',
      kind: 'bullet_list',
      items: ['Первый пункт', 'Второй пункт'],
    },
  ],
};
const powerConsumptionCalculationResponse = {
  project_id: 10,
  page_title: 'Расчет токопотребления системы',
  introductory_texts: [
    'Первый вводный абзац.',
    'Второй вводный абзац.',
  ],
  table_caption: 'Таблица 1.',
  table_title: 'Расчет токопотребления системы',
  categories: [
    {
      key: 'instruments',
      title: '1. Приборы',
      rows: [
        {
          source_key: 'instruments:401',
          number: '1',
          equipment_name: 'Panel A',
          unit: 'шт.',
          quantity: '1',
          standby_current: '0,12',
          alarm_current: '0,18',
          standby_total: '0,12',
          alarm_total: '0,18',
        },
      ],
    },
    { key: 'detectors', title: '2. Извещатели', rows: [] },
    { key: 'notification_devices', title: '3. Оповещатели и устройства коммутационные', rows: [] },
  ],
  summary_rows: [
    { key: 'instruments_and_detectors_total', kind: 'summary', label: 'I (Итого по токопотреблению приборов и извещателей), А:', standby: '0,12', alarm: '0,18' },
    { key: 'notification_total', kind: 'summary', label: 'I (Итого по токопотреблению оповещателей и устройств коммутационных), А:', standby: '0', alarm: '0' },
    { key: 'overall_total', kind: 'summary', label: 'I (Итого по токопотреблению), А:', standby: '0,12', alarm: '0,18' },
    { key: 'operation_time', kind: 'summary', label: 'Т (Время работы), час:', standby: '24', alarm: '1' },
    { key: 'capacity', kind: 'summary', label: 'W=I*T (Итого ёмкость аккумулятора), А/ч:', standby: '2,88', alarm: '0,18' },
    { key: 'correction_factor', kind: 'summary', label: 'Поправочный коэффициент:', standby: '1,1', alarm: '1,1' },
    { key: 'corrected_capacity', kind: 'summary', label: 'Итого с поправочным коэффициентом:', standby: '3,168', alarm: '0,198' },
    { key: 'total_capacity', kind: 'summary_merged', label: 'Wобщ (Общая ёмкость аккумулятора), А/ч:', value: '3,366' },
  ],
  battery_voltage_v: '12',
  battery_capacity_ah: 4,
  battery_quantity: '1',
  final_text: 'Исходя из расчетов принимаем использование аккумуляторной батареи 12 В, 4 Ач - 1 шт.',
  computed_values: {
    total_capacity: 3.366,
    battery_capacity_rounded: 4,
  },
};
const equipmentSpecificationResponse = {
  project_id: 10,
  page_title: 'Спецификация используемого оборудования',
  column_headers: [
    'Позиция',
    'Наименование и техническая характеристика',
    'Тип, марка, обозначение документа, опросного листа',
    'Код оборудования, изделия, материала',
    'Производитель',
    'Единица измерения',
    'Количество',
    'Масса единицы, кг',
    'Примечание',
  ],
  sections: [
    {
      key: 'kipia',
      title: 'КИПиА',
      rows: [
        {
          source_key: 'instrument:401',
          position: '1',
          technical_name: 'Прибор приемно-контрольный охранно-пожарный',
          type_mark: 'Panel A',
          code: '',
          manufacturer: 'ACME',
          unit: 'шт.',
          quantity: '1',
          unit_mass_kg: '',
          note: '',
        },
      ],
    },
    {
      key: 'fire_resistant_cable_line',
      title: 'Огнестойкая кабельная линия',
      rows: [],
    },
  ],
  warnings: [],
};
const additionalInfoResponse = {
  page_title: 'Доп. сведения',
  text: '',
  is_empty: true,
};

const pipelineStateResponse = {
  active_step: 'zkspc',
  active_signal_system_type: 'non_addressable',
  steps: {
    walls: { status: 'validated', revision: 1, feedback_status: null, feedback_example_id: null, feedback_submitted_revision: null },
    openings: { status: 'validated', revision: 1, feedback_status: null, feedback_example_id: null, feedback_submitted_revision: null },
    rooms: { status: 'validated' },
    zkspc: { status: 'validated' },
  },
  branches: {
    common: {
      active_step: 'signal_instruments',
      steps: {
        signal_instruments: { status: 'validated' },
        fire_alarms: { status: 'locked' },
        devices_cables: { status: 'locked' },
        soue_devices: { status: 'locked' },
        soue_cables: { status: 'locked' },
      },
    },
    non_addressable: {
      active_step: 'fire_alarms',
      steps: {
        signal_instruments: { status: 'locked' },
        fire_alarms: { status: 'draft' },
        devices_cables: { status: 'locked' },
        soue_devices: { status: 'locked' },
        soue_cables: { status: 'locked' },
      },
    },
    addressable: {
      active_step: 'fire_alarms',
      steps: {
        signal_instruments: { status: 'locked' },
        fire_alarms: { status: 'draft' },
        devices_cables: { status: 'locked' },
        soue_devices: { status: 'locked' },
        soue_cables: { status: 'locked' },
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
  mockSearchParams = new URLSearchParams();
  mockSetSearchParams.mockReset();
  __setMockBackgroundImageSize({ width: 400, height: 400 });
  floorPlansApi.get.mockResolvedValue(floorPlanResponse);
  floorPlansApi.batchSave.mockResolvedValue({ floor_plan: floorPlanResponse });
  floorPlansApi.autoLayoutFireAlarms.mockResolvedValue({ devices: [], warnings: [] });
  floorPlansApi.autoLayoutSoueDevices.mockResolvedValue({ devices: [], warnings: [] });
  floorPlansApi.update.mockResolvedValue(floorPlanResponse);
  pipelineApi.getState.mockResolvedValue(pipelineStateResponse);
  pipelineApi.commitWalls.mockResolvedValue({ floor_plan: floorPlanResponse, pipeline_state: pipelineStateResponse });
  pipelineApi.commitOpenings.mockResolvedValue({ floor_plan: floorPlanResponse, pipeline_state: pipelineStateResponse });
  pipelineApi.submitStepFeedback.mockResolvedValue({
    feedback_id: 901,
    step: 'walls',
    status: 'approved',
    submitted_revision: 1,
    pending_counts: { approved: 1, batched: 0, exported: 0, used: 0, total: 1 },
    next_batch_hint: { step: 'walls', eligible: false, reason: 'waiting_for_more_wall_examples' },
  });
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
  equipmentApi.list.mockResolvedValue(equipmentItemsResponse);
  projectsApi.listEquipment.mockResolvedValue(projectEquipmentResponse);
  projectsApi.getEquipmentSelections.mockResolvedValue(projectEquipmentSelectionsResponse);
  projectsApi.getGeneralData.mockResolvedValue(generalDataResponse);
  projectsApi.updateGeneralData.mockImplementation(async (_projectId, payload) => ({
    ...generalDataResponse,
    ...payload,
  }));
  projectsApi.getGeneralInstructions.mockResolvedValue(generalInstructionsResponse);
  projectsApi.updateGeneralInstructions.mockImplementation(async (_projectId, payload) => ({
    ...generalInstructionsResponse,
    ...payload,
  }));
  projectsApi.getPowerConsumptionCalculation.mockResolvedValue(powerConsumptionCalculationResponse);
  projectsApi.updatePowerConsumptionCalculation.mockResolvedValue(powerConsumptionCalculationResponse);
  projectsApi.getEquipmentSpecification.mockResolvedValue(equipmentSpecificationResponse);
  projectsApi.updateEquipmentSpecification.mockResolvedValue(equipmentSpecificationResponse);
  projectsApi.getAdditionalInfo.mockResolvedValue(additionalInfoResponse);
  projectsApi.updateAdditionalInfo.mockResolvedValue({
    ...additionalInfoResponse,
    text: 'Сохраненный текст',
    is_empty: false,
  });
  projectsApi.attachEquipment.mockResolvedValue(projectEquipmentResponse);
  elementsApi.createSignalInstrument.mockResolvedValue(floorPlanResponse.signal_instruments[0]);
  elementsApi.createRoom.mockResolvedValue({
    id: 81,
    floor_plan_id: 1,
    name: null,
    room_type: 'базовое',
    room_number: null,
    boundary_points: [[60, 80], [160, 80], [160, 180], [60, 180]],
    center_x: 110,
    center_y: 130,
    area_sqm: 10,
  });
  elementsApi.updateSignalInstrument.mockResolvedValue(floorPlanResponse.signal_instruments[0]);
  elementsApi.deleteSignalInstrument.mockResolvedValue({ message: 'deleted' });
  elementsApi.commitSignalInstrumentsStep.mockResolvedValue({ success: true });
  elementsApi.mergeRoutesForInstrument.mockResolvedValue(floorPlanResponse.cable_routes);
  elementsApi.recalculateCableRoutes.mockResolvedValue(floorPlanResponse.cable_routes);
  elementsApi.commitCableRoutesStep.mockResolvedValue({ success: true });
  elementsApi.updateCableRoute.mockResolvedValue({
    ...floorPlanResponse.cable_routes[0],
    is_manual: true,
  });
  window.alert = jest.fn();
  window.confirm = jest.fn(() => true);
  window.prompt = jest.fn(() => '1');
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

function getButtonByTextContent(...fragments) {
  return screen.getAllByRole('button').find((button) => (
    fragments.some((fragment) => button.textContent?.includes(fragment))
  ));
}

test.skip('opens shared power consumption step from query parameter', async () => {
  mockSearchParams = new URLSearchParams(`step=power_consumption_calculation`);

  render(<FloorPlanEditor />);

  await waitFor(() => {
    expect(document.querySelector('.power-consumption-preview')).toBeInTheDocument();
  });
  expect(screen.queryByText('РџРѕС€Р°РіРѕРІС‹Р№ РїР°Р№РїР»Р°Р№РЅ')).not.toBeInTheDocument();
  expect(screen.queryByText('РРЅС„РѕСЂРјР°С†РёСЏ Рѕ РїР»Р°РЅРµ')).not.toBeInTheDocument();
});

test.skip('opens equipment specification step and saves edited specification', async () => {
  pipelineApi.getState.mockResolvedValueOnce({
    ...pipelineStateResponse,
    branches: {
      common: {
        active_step: 'soue_cables',
        steps: {
          signal_instruments: { status: 'validated' },
          fire_alarms: { status: 'validated' },
          devices_cables: { status: 'validated' },
          soue_devices: { status: 'validated' },
          soue_cables: { status: 'validated' },
        },
      },
      non_addressable: {
        active_step: 'soue_cables',
        steps: {
          signal_instruments: { status: 'validated' },
          fire_alarms: { status: 'validated' },
          devices_cables: { status: 'validated' },
          soue_devices: { status: 'validated' },
          soue_cables: { status: 'validated' },
        },
      },
    },
  });
  projectsApi.updatePowerConsumptionCalculation.mockImplementation(async (_projectId, payload) => ({
    ...powerConsumptionCalculationResponse,
    ...payload,
    battery_capacity_ah: 5,
    final_text: 'Исходя из расчетов принимаем использование аккумуляторной батареи 24 В, 5 Ач - 2 шт.',
    summary_rows: (payload.summary_rows || powerConsumptionCalculationResponse.summary_rows).map((row) => (
      row.key === 'total_capacity' ? { ...row, value: '4,158' } : row
    )),
  }));
  projectsApi.updateEquipmentSpecification.mockImplementation(async (_projectId, payload) => payload);

  render(<FloorPlanEditor />);

  fireEvent.click(await screen.findByText('12. Расчет токопотребления'));

  const powerTitleInput = await screen.findByLabelText('Заголовок страницы расчета токопотребления');
  fireEvent.change(powerTitleInput, { target: { value: 'Расчет проекта' } });
  fireEvent.change(screen.getByLabelText('Количество аккумуляторов'), { target: { value: '2' } });
  fireEvent.change(screen.getByLabelText('Итоговое значение operation_time:standby'), { target: { value: '12' } });
  const powerPreview = document.querySelector('.power-consumption-preview');
  fireEvent.click(within(powerPreview).getByRole('button', { name: 'Сохранить' }));

  await waitFor(() => {
    expect(projectsApi.updatePowerConsumptionCalculation).toHaveBeenCalledWith(
      10,
      expect.objectContaining({
        page_title: 'Расчет проекта',
        battery_quantity: '2',
      }),
    );
  });

  fireEvent.click(await screen.findByText('13. Спецификация'));

  const titleInput = await screen.findByDisplayValue('Спецификация используемого оборудования');
  fireEvent.change(titleInput, { target: { value: 'Спецификация проекта' } });
  expect(screen.queryByText('РџРѕС€Р°РіРѕРІС‹Р№ РїР°Р№РїР»Р°Р№РЅ')).not.toBeInTheDocument();
  expect(screen.queryByText('РРЅС„РѕСЂРјР°С†РёСЏ Рѕ РїР»Р°РЅРµ')).not.toBeInTheDocument();
  const specificationPreview = document.querySelector('.equipment-specification-preview');
  fireEvent.click(within(specificationPreview).getByRole('button', { name: 'Сохранить' }));

  await waitFor(() => {
    expect(projectsApi.updateEquipmentSpecification).toHaveBeenCalledWith(
      10,
      expect.objectContaining({
        page_title: 'Спецификация проекта',
      }),
    );
  });
});

test('opens shared power consumption step from query parameter and hides side panels', async () => {
  mockSearchParams = new URLSearchParams('step=power_consumption_calculation');

  render(<FloorPlanEditor />);

  await waitFor(() => {
    expect(document.querySelector('.power-consumption-preview')).toBeInTheDocument();
  });
  expect(screen.queryByText('Пошаговый пайплайн')).not.toBeInTheDocument();
  expect(screen.queryByText('Информация о плане')).not.toBeInTheDocument();
});

test('opens general data step from query parameter and saves edits without side panels', async () => {
  mockSearchParams = new URLSearchParams('step=general_data');
  projectsApi.updateGeneralData.mockImplementation(async (_projectId, payload) => ({
    ...generalDataResponse,
    ...payload,
  }));

  render(<FloorPlanEditor />);

  const titleInput = await screen.findByLabelText('Название листа общих данных');
  fireEvent.change(titleInput, { target: { value: 'Общие данные проекта' } });
  fireEvent.change(screen.getByLabelText('Категория ссылочных документов'), {
    target: { value: 'Нормативные документы' },
  });

  expect(screen.queryByText('Пошаговый пайплайн')).not.toBeInTheDocument();
  expect(screen.queryByText('Информация о плане')).not.toBeInTheDocument();

  const preview = document.querySelector('.general-data-preview');
  fireEvent.click(within(preview).getByRole('button', { name: 'Сохранить' }));

  await waitFor(() => {
    expect(projectsApi.updateGeneralData).toHaveBeenCalledWith(
      10,
      expect.objectContaining({
        page_title: 'Общие данные проекта',
        reference_category_title: 'Нормативные документы',
      }),
    );
  });
});

test('opens general instructions step from query parameter and saves edits without side panels', async () => {
  mockSearchParams = new URLSearchParams('step=general_instructions');
  projectsApi.updateGeneralInstructions.mockImplementation(async (_projectId, payload) => ({
    ...generalInstructionsResponse,
    ...payload,
  }));

  render(<FloorPlanEditor />);

  const titleInput = await screen.findByLabelText('Название листа общих указаний');
  fireEvent.change(titleInput, { target: { value: 'Общие указания проекта' } });
  fireEvent.change(screen.getByLabelText('Блок общих указаний block_2'), {
    target: { value: 'Обновленный вводный текст.' },
  });

  expect(screen.queryByText('Пошаговый пайплайн')).not.toBeInTheDocument();
  expect(screen.queryByText('Информация о плане')).not.toBeInTheDocument();

  const preview = document.querySelector('.general-instructions-preview');
  fireEvent.click(within(preview).getByRole('button', { name: 'Сохранить' }));

  await waitFor(() => {
    expect(projectsApi.updateGeneralInstructions).toHaveBeenCalledWith(
      10,
      expect.objectContaining({
        page_title: 'Общие указания проекта',
        blocks: expect.arrayContaining([
          expect.objectContaining({
            key: 'block_2',
            text: 'Обновленный вводный текст.',
          }),
        ]),
      }),
    );
  });
});

test('opens equipment specification step and saves edited specification without side panels', async () => {
  pipelineApi.getState.mockResolvedValueOnce({
    ...pipelineStateResponse,
    branches: {
      common: {
        active_step: 'soue_cables',
        steps: {
          signal_instruments: { status: 'validated' },
          fire_alarms: { status: 'validated' },
          devices_cables: { status: 'validated' },
          soue_devices: { status: 'validated' },
          soue_cables: { status: 'validated' },
        },
      },
      non_addressable: {
        active_step: 'soue_cables',
        steps: {
          signal_instruments: { status: 'validated' },
          fire_alarms: { status: 'validated' },
          devices_cables: { status: 'validated' },
          soue_devices: { status: 'validated' },
          soue_cables: { status: 'validated' },
        },
      },
    },
  });
  projectsApi.updatePowerConsumptionCalculation.mockImplementation(async (_projectId, payload) => ({
    ...powerConsumptionCalculationResponse,
    ...payload,
    battery_capacity_ah: 5,
    final_text: 'Исходя из расчетов принимаем использование аккумуляторной батареи 24 В, 5 Ач - 2 шт.',
    summary_rows: (payload.summary_rows || powerConsumptionCalculationResponse.summary_rows).map((row) => (
      row.key === 'total_capacity' ? { ...row, value: '4,158' } : row
    )),
  }));
  projectsApi.updateEquipmentSpecification.mockImplementation(async (_projectId, payload) => payload);

  mockSearchParams = new URLSearchParams('step=power_consumption_calculation');
  const { unmount } = render(<FloorPlanEditor />);

  const powerTitleInput = await screen.findByLabelText('Заголовок страницы расчета токопотребления');
  fireEvent.change(powerTitleInput, { target: { value: 'Расчет проекта' } });
  fireEvent.change(screen.getByLabelText('Количество аккумуляторов'), { target: { value: '2' } });
  fireEvent.change(screen.getByLabelText('Итоговое значение operation_time:standby'), { target: { value: '12' } });
  expect(screen.queryByText('Пошаговый пайплайн')).not.toBeInTheDocument();
  expect(screen.queryByText('Информация о плане')).not.toBeInTheDocument();
  const powerPreview = document.querySelector('.power-consumption-preview');
  fireEvent.click(within(powerPreview).getByRole('button', { name: 'Сохранить' }));

  await waitFor(() => {
    expect(projectsApi.updatePowerConsumptionCalculation).toHaveBeenCalledWith(
      10,
      expect.objectContaining({
        page_title: 'Расчет проекта',
        battery_quantity: '2',
      }),
    );
  });

  unmount();
  mockSearchParams = new URLSearchParams('step=equipment_specification');

  render(<FloorPlanEditor />);

  const titleInput = await screen.findByDisplayValue('Спецификация используемого оборудования');
  fireEvent.change(titleInput, { target: { value: 'Спецификация проекта' } });
  expect(screen.queryByText('Пошаговый пайплайн')).not.toBeInTheDocument();
  expect(screen.queryByText('Информация о плане')).not.toBeInTheDocument();
  const specificationPreview = document.querySelector('.equipment-specification-preview');
  fireEvent.click(within(specificationPreview).getByRole('button', { name: 'Сохранить' }));

  await waitFor(() => {
    expect(projectsApi.updateEquipmentSpecification).toHaveBeenCalledWith(
      10,
      expect.objectContaining({
        page_title: 'Спецификация проекта',
      }),
    );
  });
});

test('opens additional info step and saves edited text without side panels', async () => {
  mockSearchParams = new URLSearchParams('step=additional_info');
  projectsApi.updateAdditionalInfo.mockImplementation(async (_projectId, payload) => ({
    page_title: 'Доп. сведения',
    text: payload.text,
    is_empty: !String(payload.text || '').trim(),
  }));

  render(<FloorPlanEditor />);

  const additionalInfoTextarea = await screen.findByLabelText('Текст доп. сведений');
  fireEvent.change(additionalInfoTextarea, { target: { value: 'Первый абзац.\n\nВторой абзац.' } });

  expect(screen.queryByText('Пошаговый пайплайн')).not.toBeInTheDocument();
  expect(screen.queryByText('Информация о плане')).not.toBeInTheDocument();

  const preview = document.querySelector('.additional-info-preview');
  fireEvent.click(within(preview).getByRole('button', { name: 'Сохранить' }));

  await waitFor(() => {
    expect(projectsApi.updateAdditionalInfo).toHaveBeenCalledWith(10, {
      text: 'Первый абзац.\n\nВторой абзац.',
    });
  });
});

test('default floor plan editor sidebar does not show shared project steps', async () => {
  render(<FloorPlanEditor />);

  await waitFor(() => {
    expect(screen.getByText('Пошаговый пайплайн')).toBeInTheDocument();
  });

  expect(screen.queryByText(/^10\. Общие данные$/)).not.toBeInTheDocument();
  expect(screen.queryByText(/^11\. Общие указания$/)).not.toBeInTheDocument();
  expect(screen.queryByText(/^12\. Расчет токопотребления$/)).not.toBeInTheDocument();
  expect(screen.queryByText(/^13\. Спецификация$/)).not.toBeInTheDocument();
  expect(screen.queryByText(/^14\. Доп\. сведения$/)).not.toBeInTheDocument();
});

test('fire alarm step shows branch selector and zkspc overlay without old mixed-save UI', async () => {
  render(<FloorPlanEditor />);

  await waitFor(() => {
    expect(screen.getByRole('button', { name: 'Дымовой датчик' })).toBeInTheDocument();
  });

  expect(screen.getAllByRole('button', { name: 'Расставить' }).length).toBeGreaterThanOrEqual(1);
  expect(screen.getAllByRole('button', { name: /^Подтвердить$/ }).length).toBeGreaterThanOrEqual(1);
  expect(screen.getByRole('button', { name: /^Безадресная/i })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /^Адресная/i })).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /Сохранить изменения/i })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /^Сохранить$/ })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /Свести/i })).not.toBeInTheDocument();

  const stageQueries = within(screen.getByTestId('konva-Stage'));
  expect(stageQueries.queryByText(/^С1$/)).not.toBeInTheDocument();
  expect(stageQueries.queryByText(/^Л1$/)).not.toBeInTheDocument();
  expect(stageQueries.queryByText(/^Д1$/)).not.toBeInTheDocument();
  expect(stageQueries.queryByText(/^О1$/)).not.toBeInTheDocument();
  expect(stageQueries.queryByText('Тестовая комната')).not.toBeInTheDocument();
});

test('devices and cables step renders instrument summary and shows merge actions', async () => {
  pipelineApi.getState.mockResolvedValueOnce({
    ...pipelineStateResponse,
    branches: {
      ...pipelineStateResponse.branches,
      non_addressable: {
        ...pipelineStateResponse.branches.non_addressable,
        active_step: 'devices_cables',
        steps: {
          signal_instruments: { status: 'validated' },
          fire_alarms: { status: 'validated' },
          devices_cables: { status: 'draft' },
          soue_devices: { status: 'locked' },
          soue_cables: { status: 'locked' },
        },
      },
    },
  });
  render(<FloorPlanEditor />);
  await waitFor(() => {
    expect(screen.getByText('\u0036. \u0421\u041f\u0421')).toBeInTheDocument();
  });
  const spsGroup = screen.getByTestId('sps-steps-group');
  expect(within(spsGroup).getByText('\u0418\u0437\u0432\u0435\u0449\u0430\u0442\u0435\u043b\u0438')).toBeInTheDocument();
  expect(within(spsGroup).getByText('\u041a\u0430\u0431\u0435\u043b\u0438')).toBeInTheDocument();
  expect(within(spsGroup).getByTestId('signal-system-section-embedded')).toBeInTheDocument();
  expect(screen.getByText('\u0034. \u0417\u041a\u0421\u041f\u0421')).toBeInTheDocument();
  expect(screen.getByText('\u0035. \u041f\u0440\u0438\u0431\u043e\u0440\u044b')).toBeInTheDocument();
  expect(within(spsGroup).getByText(/\u0418\u0437\u0432\u0435\u0449\u0430\u0442\u0435\u043b\u0435\u0439:/i)).toBeInTheDocument();
  expect(within(spsGroup).getByText(/\u041a\u0430\u0431\u0435\u043b\u044f:/i)).toBeInTheDocument();
  expect(within(spsGroup).getAllByRole('button', { name: /^\u041f\u043e\u0434\u0442\u0432\u0435\u0440\u0434\u0438\u0442\u044c$/ }).length).toBeGreaterThanOrEqual(2);
  expect(screen.getAllByText('Panel A').length).toBeGreaterThan(0);
  expect(screen.getByRole('button', { name: /\u0421\u0432\u0435\u0441\u0442\u0438 \u0438\u0437\u0432\u0435\u0449\u0430\u0442\u0435\u043b\u0438/i })).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /^\u0421\u043e\u0445\u0440\u0430\u043d\u0438\u0442\u044c$/ })).not.toBeInTheDocument();
});

test('soue devices step exposes auto-layout, confirm, and manual device tools', async () => {
  pipelineApi.getState.mockResolvedValueOnce({
    ...pipelineStateResponse,
    branches: {
      ...pipelineStateResponse.branches,
      common: {
        ...pipelineStateResponse.branches.common,
        active_step: 'soue_devices',
        steps: {
          ...pipelineStateResponse.branches.common.steps,
          signal_instruments: { status: 'validated' },
          soue_devices: { status: 'draft' },
          soue_cables: { status: 'locked' },
        },
      },
      non_addressable: {
        ...pipelineStateResponse.branches.non_addressable,
        active_step: 'soue_devices',
        steps: {
          signal_instruments: { status: 'locked' },
          fire_alarms: { status: 'validated' },
          devices_cables: { status: 'validated' },
          soue_devices: { status: 'locked' },
          soue_cables: { status: 'locked' },
        },
      },
    },
  });
  render(<FloorPlanEditor />);
  await waitFor(() => {
    expect(screen.getByText('\u0038. \u0421\u041e\u0423\u042d')).toBeInTheDocument();
  });
  const soueGroup = screen.getByTestId('soue-steps-group');
  expect(within(soueGroup).getByText('\u0422\u0430\u0431\u043b\u043e \u0438 \u0441\u0438\u0440\u0435\u043d\u044b')).toBeInTheDocument();
  expect(within(soueGroup).getByText('\u041a\u0430\u0431\u0435\u043b\u0438')).toBeInTheDocument();
  expect(screen.getAllByRole('button', { name: '\u0420\u0430\u0441\u0441\u0442\u0430\u0432\u0438\u0442\u044c' }).length).toBeGreaterThanOrEqual(1);
  expect(screen.getAllByRole('button', { name: /^\u041f\u043e\u0434\u0442\u0432\u0435\u0440\u0434\u0438\u0442\u044c$/ }).length).toBeGreaterThanOrEqual(1);
  expect(screen.getByRole('button', { name: '\u0421\u0438\u0440\u0435\u043d\u0430' })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: '\u0422\u0430\u0431\u043b\u043e' })).toBeInTheDocument();
  expect(screen.getByText(/\u0423\u0441\u0442\u0440\u043e\u0439\u0441\u0442\u0432 \u0421\u041e\u0423\u042d:/i)).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /^\u0421\u043e\u0445\u0440\u0430\u043d\u0438\u0442\u044c$/ })).not.toBeInTheDocument();
});

test('soue cables step shows confirm buttons for device and cable cards', async () => {
  pipelineApi.getState.mockResolvedValueOnce({
    ...pipelineStateResponse,
    branches: {
      ...pipelineStateResponse.branches,
      common: {
        ...pipelineStateResponse.branches.common,
        active_step: 'soue_cables',
        steps: {
          ...pipelineStateResponse.branches.common.steps,
          signal_instruments: { status: 'validated' },
          soue_devices: { status: 'validated' },
          soue_cables: { status: 'draft' },
        },
      },
      non_addressable: {
        ...pipelineStateResponse.branches.non_addressable,
        active_step: 'soue_cables',
        steps: {
          signal_instruments: { status: 'validated' },
          fire_alarms: { status: 'validated' },
          devices_cables: { status: 'validated' },
          soue_devices: { status: 'validated' },
          soue_cables: { status: 'draft' },
        },
      },
    },
  });

  render(<FloorPlanEditor />);

  await waitFor(() => {
    expect(screen.getByText('\u0038. \u0421\u041e\u0423\u042d')).toBeInTheDocument();
  });

  const soueGroup = screen.getByTestId('soue-steps-group');
  expect(within(soueGroup).getAllByRole('button', { name: /^\u041f\u043e\u0434\u0442\u0432\u0435\u0440\u0434\u0438\u0442\u044c$/ }).length).toBeGreaterThanOrEqual(2);
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

test('signal instruments move by figure while the label stays non-draggable', async () => {
  render(<FloorPlanEditor />);

  await screen.findByRole('button', { name: 'Дымовой датчик' });

  const instrumentSymbol = screen.getByTestId('signal-instrument-symbol');
  const instrumentGroup = instrumentSymbol.closest('[data-konva="Group"]');
  const instrumentLabel = within(screen.getByTestId('konva-Stage')).getByText('ARK');
  const instrumentLabelNode = instrumentLabel.closest('[data-konva="Text"]');

  expect(instrumentGroup).not.toBeNull();
  expect(instrumentGroup).toHaveAttribute('data-draggable', 'true');
  expect(instrumentLabelNode).not.toBeNull();
  expect(instrumentLabelNode).toHaveAttribute('data-draggable', 'false');
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

test('walls step feedback button submits the current validated revision', async () => {
  render(<FloorPlanEditor />);

  const feedbackButton = await screen.findByRole('button', {
    name: 'Отправить подтвержденные стены для обучения',
  });

  expect(feedbackButton).toBeEnabled();
  fireEvent.click(feedbackButton);

  await waitFor(() => {
    expect(pipelineApi.submitStepFeedback).toHaveBeenCalledWith('1', 'walls', {
      step_revision: 1,
      issue_tags: [],
      notes: null,
    });
  });
  expect(screen.getByText('Подтвержденные стены добавлены в обучающую выборку.')).toBeInTheDocument();
});

test('step feedback button stays disabled when the current revision is already submitted', async () => {
  pipelineApi.getState.mockResolvedValueOnce({
    ...pipelineStateResponse,
    steps: {
      ...pipelineStateResponse.steps,
      walls: {
        ...pipelineStateResponse.steps.walls,
        feedback_status: 'approved',
        feedback_example_id: 777,
        feedback_submitted_revision: 1,
      },
    },
  });

  render(<FloorPlanEditor />);

  const feedbackButton = await screen.findByRole('button', {
    name: 'Отправить подтвержденные стены для обучения',
  });

  expect(feedbackButton).toBeDisabled();
  expect(screen.getByText('Образец для текущей ревизии стен уже отправлен.')).toBeInTheDocument();
});

test('devices and cables canvas shows ZC terminator for non-addressable route', async () => {
  pipelineApi.getState.mockResolvedValueOnce({
    ...pipelineStateResponse,
    branches: {
      ...pipelineStateResponse.branches,
      non_addressable: {
        ...pipelineStateResponse.branches.non_addressable,
        active_step: 'devices_cables',
        steps: {
          signal_instruments: { status: 'validated' },
          fire_alarms: { status: 'validated' },
          devices_cables: { status: 'draft' },
          soue_devices: { status: 'locked' },
          soue_cables: { status: 'locked' },
        },
      },
    },
  });
  render(<FloorPlanEditor />);
  await waitFor(() => {
    expect(within(screen.getByTestId('konva-Stage')).getByText('ZC')).toBeInTheDocument();
  });
});
test('devices and cables canvas shows ARK label for the control panel', async () => {
  floorPlansApi.get.mockResolvedValueOnce({
    ...floorPlanResponse,
    signal_instruments: floorPlanResponse.signal_instruments.map((instrument) => ({
      ...instrument,
      name: '',
    })),
  });
  pipelineApi.getState.mockResolvedValueOnce({
    ...pipelineStateResponse,
    branches: {
      ...pipelineStateResponse.branches,
      non_addressable: {
        ...pipelineStateResponse.branches.non_addressable,
        active_step: 'devices_cables',
        steps: {
          signal_instruments: { status: 'validated' },
          fire_alarms: { status: 'validated' },
          devices_cables: { status: 'draft' },
          soue_devices: { status: 'locked' },
          soue_cables: { status: 'locked' },
        },
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
  });
  expect(getMockStageProps()?.height).toBe(800);
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
  });
  expect(pipelineApi.commitOpenings).toHaveBeenCalled();

  expect(floorPlansApi.update.mock.invocationCallOrder[0]).toBeLessThan(
    pipelineApi.commitOpenings.mock.invocationCallOrder[0],
  );
});

test('display cable routes spread two overlapping routes symmetrically with cable-width spacing', () => {
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

  const displayRoutes = buildDisplayCableRoutes(routes);

  expect(displayRoutes[1][0][0]).toBe(-1.5);
  expect(displayRoutes[1][1][0]).toBe(-1.5);
  expect(displayRoutes[2][0][0]).toBe(1.5);
  expect(displayRoutes[2][1][0]).toBe(1.5);
  expect(displayRoutes[1][2][1]).toBe(18.5);
  expect(displayRoutes[2][2][1]).toBe(21.5);
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

  expect(displayRoutes[10][0][0]).toBe(-1.5);
  expect(displayRoutes[11][0][0]).toBe(1.5);
  expect(displayRoutes[10][1][0]).toBe(-1.5);
  expect(displayRoutes[11][1][0]).toBe(1.5);
});

test('display cable routes keep four overlapping routes in deterministic parallel lanes', () => {
  const routes = [
    { id: 1, route_number: 1, polyline_points: [[0, 0], [0, 20]] },
    { id: 2, route_number: 2, polyline_points: [[0, 0], [0, 20]] },
    { id: 3, route_number: 3, polyline_points: [[0, 0], [0, 20]] },
    { id: 4, route_number: 4, polyline_points: [[0, 0], [0, 20]] },
  ];

  const displayRoutes = buildDisplayCableRoutes(routes);

  expect(displayRoutes[1][0][0]).toBe(-4.5);
  expect(displayRoutes[2][0][0]).toBe(-1.5);
  expect(displayRoutes[3][0][0]).toBe(1.5);
  expect(displayRoutes[4][0][0]).toBe(4.5);
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

test('zc terminator picks a side candidate when the forward side is blocked', () => {
  const zcPoint = getZcTerminatorPoint({
    route: { device_ids: [11] },
    polyline: [[0, 0], [26, 0], [40, 0]],
    deviceLookup: {
      11: { x: 40, y: 0 },
    },
    obstacles: [
      { x: 48, y: -8, width: 20, height: 16 },
    ],
  });

  expect(zcPoint).toEqual([40, -19.4]);
});

test('placePlanText gives the next label a different non-overlapping slot', () => {
  const bounds = { x: -40, y: -40, width: 160, height: 120 };
  const first = placePlanText({
    text: 'ARK',
    fontSize: 11,
    anchor: { x: 20, y: 20 },
    symbolHalfWidth: 12,
    symbolHalfHeight: 12,
    bounds,
  });

  const second = placePlanText({
    text: 'XBIAS1.1',
    fontSize: 11,
    anchor: { x: 20, y: 20 },
    symbolHalfWidth: 12,
    symbolHalfHeight: 12,
    bounds,
    obstacles: placementToObstacles(first),
  });

  expect(first).not.toBeNull();
  expect(second).not.toBeNull();
  expect(second.rect).not.toEqual(first.rect);
});

test('control panels use ARK as the on-plan label', () => {
  expect(getInstrumentLabelText({
    instrument_type: 'control_panel',
    equipment_name: 'Прибор Рубеж',
    name: 'Щит 1',
  })).toBe('ARK');

  expect(getInstrumentLabelText({
    instrument_type: 'loop_controller',
    equipment_name: 'Контроллер С2000-КДЛ',
    name: 'КДЛ',
  })).toBe('Контроллер С2000-КДЛ');
});

test('placePlanText returns null instead of forcing an overlapping fallback', () => {
  const layout = placePlanText({
    text: 'ZC',
    fontSize: 10,
    anchor: { x: 40, y: 20 },
    symbolHalfWidth: 8,
    symbolHalfHeight: 8,
    bounds: { x: 0, y: 0, width: 80, height: 40 },
    obstacles: [{ x: 0, y: 0, width: 80, height: 40 }],
  });

  expect(layout).toBeNull();
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
    expect(Number(getViewportGroupNode()?.dataset.scaleX)).toBeCloseTo(expectedScale, 4);
  });
  const viewportGroup = getViewportGroupNode();
  expect(Number(viewportGroup?.dataset.offsetX)).toBeCloseTo(500, 4);
  expect(Number(viewportGroup?.dataset.offsetY)).toBeCloseTo(250, 4);
  expect(Number(viewportGroup?.dataset.scaleX)).not.toBeCloseTo(fallbackScale, 4);
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
  });
  expect(Number(getViewportGroupNode()?.dataset.offsetY)).toBeCloseTo(250, 4);

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
  });
  expect(Number(getViewportGroupNode()?.dataset.y)).toBeCloseTo((panningStageProps.height / 2) + expectedMaxPanY, 4);
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

  const drawWallButton = await screen.findByRole('button', { name: 'Нарисовать стену' });

  expect(screen.getByRole('spinbutton', { name: 'Толщина новой стены, м' })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Свободно' })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Прилипание' })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Приклеить все стены' })).toBeInTheDocument();

  fireEvent.click(drawWallButton);

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

test('rooms step exposes the add-room drawing action', async () => {
  pipelineApi.getState.mockResolvedValueOnce({
    active_step: 'rooms',
    active_signal_system_type: 'non_addressable',
    steps: {
      walls: { status: 'validated' },
      openings: { status: 'validated' },
      rooms: { status: 'draft' },
      zkspc: { status: 'draft' },
    },
    branches: pipelineStateResponse.branches,
  });

  const { container } = render(<FloorPlanEditor />);

  const toolbar = container.querySelector('.editor-toolbar');
  expect(toolbar).not.toBeNull();
  const addRoomButton = await within(toolbar).findByRole('button', { name: 'Добавить помещение' });
  fireEvent.click(addRoomButton);
  expect(addRoomButton).toHaveClass('active');
  expect(screen.getByText('Протяните прямоугольник на плане, чтобы добавить помещение.')).toBeInTheDocument();
});
