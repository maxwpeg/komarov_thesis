import React from 'react';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

import { useAuth } from '../auth/AuthContext';
import ProjectDetail from './ProjectDetail';
import { equipmentApi, floorPlansApi, projectsApi, usersApi } from '../api/client';
import { useDialogs } from '../ui/DialogProvider';

const mockNavigate = jest.fn();
let createElementSpy;
let consoleErrorSpy;
let consoleWarnSpy;
let originalImage;
let originalFetch;

jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useParams: () => ({ projectId: '10' }),
  useNavigate: () => mockNavigate,
}));

jest.mock('../auth/AuthContext', () => ({
  useAuth: jest.fn(),
}));

jest.mock('../ui/DialogProvider', () => ({
  useDialogs: jest.fn(),
}));

jest.mock('../api/client', () => ({
  floorPlansApi: {
    list: jest.fn(),
    create: jest.fn(),
    remove: jest.fn(),
  },
  projectsApi: {
    get: jest.fn(),
    update: jest.fn(),
    remove: jest.fn(),
    generatePdf: jest.fn(),
    getPdfPreview: jest.fn(),
    getEquipmentSpecification: jest.fn(),
    getAdditionalInfo: jest.fn(),
    listEquipment: jest.fn(),
    getEquipmentSelections: jest.fn(),
    updateEquipmentSelections: jest.fn(),
    attachEquipment: jest.fn(),
    createAndAttachEquipment: jest.fn(),
    removeEquipment: jest.fn(),
  },
  equipmentApi: {
    list: jest.fn(),
  },
  usersApi: {
    list: jest.fn(),
  },
}));

const projectResponse = {
  id: 10,
  name: 'Проект 01',
  facility: 'Объект',
  facility_genitive: 'Объекта',
  facility_instrumental: 'Объектом',
  code: 'P-01',
  project_type: 'СПС',
  year: 2026,
  contractor: 'Подрядчик',
  engineer: 'Инженер',
  owner_user_id: 21,
  owner_user: { id: 21, full_name: 'Engineer One', username: 'eng1', role: 'engineer' },
  facility_address: 'Адрес',
  project_description: 'Описание',
};

const smokeA = { id: 101, name: 'Smoke A', category: 'smoke', price: 1200, compatible_equipment_ids: [] };
const smokeB = { id: 102, name: 'Smoke B', category: 'smoke', price: 1300, compatible_equipment_ids: [] };
const sirenA = { id: 201, name: 'Siren A', category: 'siren', price: 900, compatible_equipment_ids: [] };
const cableA = { id: 301, name: 'Cable A', category: 'cable', price: 200, compatible_equipment_ids: [] };
const panelA = { id: 401, name: 'Panel A', category: 'instrument', price: 5000, compatible_equipment_ids: [] };
const mountingA = { id: 501, name: 'Clip Pack', category: 'mounting', price: 350, compatible_equipment_ids: [] };

const equipmentItemsResponse = [smokeA, smokeB, sirenA, cableA, panelA, mountingA];
const projectEquipmentResponse = {
  project_id: 10,
  items: [smokeA, sirenA, cableA, panelA],
};
const projectEquipmentSelectionsResponse = {
  project_id: 10,
  selections: {
    sps_cable: 301,
    soue_cable: null,
  },
};
const equipmentSpecificationResponse = {
  project_id: 10,
  sections: [
    {
      key: 'kipia',
      rows: [
        { source_key: 'instrument:401', quantity: '2' },
        { source_key: 'fire_alarm:101', quantity: '3' },
      ],
    },
    {
      key: 'fire_resistant_cable_line',
      rows: [
        { source_key: 'cable:301', quantity: '5.5' },
        { source_key: 'mounting:501', quantity: '4' },
      ],
    },
  ],
};

function mockImageLoad({ width = 400, height = 400, shouldFail = false } = {}) {
  window.Image = class MockImage {
    constructor() {
      this.onload = null;
      this.onerror = null;
      this.naturalWidth = width;
      this.naturalHeight = height;
      this.width = width;
      this.height = height;
    }

    set src(_value) {
      setTimeout(() => {
        if (shouldFail) {
          this.onerror?.(new Event('error'));
          return;
        }
        this.onload?.(new Event('load'));
      }, 0);
    }
  };
}

beforeEach(() => {
  jest.clearAllMocks();
  originalImage = window.Image;
  originalFetch = global.fetch;
  mockImageLoad();
  useAuth.mockReturnValue({
    user: { id: 1, role: 'developer', full_name: 'Developer User' },
  });
  useDialogs.mockReturnValue({
    confirm: jest.fn().mockResolvedValue(true),
    toast: jest.fn(),
  });
  projectsApi.get.mockResolvedValue(projectResponse);
  floorPlansApi.list.mockResolvedValue([]);
  projectsApi.getEquipmentSpecification.mockResolvedValue(equipmentSpecificationResponse);
  equipmentApi.list.mockResolvedValue(equipmentItemsResponse);
  usersApi.list.mockResolvedValue([
    { id: 21, full_name: 'Engineer One', username: 'eng1', role: 'engineer', is_active: true },
    { id: 22, full_name: 'Engineer Two', username: 'eng2', role: 'engineer', is_active: true },
  ]);
  projectsApi.listEquipment.mockResolvedValue(projectEquipmentResponse);
  projectsApi.getAdditionalInfo.mockResolvedValue({
    page_title: 'Доп. сведения',
    text: '',
    is_empty: true,
  });
  projectsApi.getEquipmentSelections.mockResolvedValue(projectEquipmentSelectionsResponse);
  projectsApi.updateEquipmentSelections.mockResolvedValue(projectEquipmentSelectionsResponse);
  projectsApi.generatePdf.mockResolvedValue({
    id: 99,
    status: 'queued',
    task_type: 'project_pdf_generate',
  });
  projectsApi.getPdfPreview.mockResolvedValue({
    project_id: 10,
    pdf_path: null,
    pdf_url: null,
    generated_at: null,
    current_task: null,
  });
  global.fetch = jest.fn().mockResolvedValue({
    ok: true,
    blob: jest.fn().mockResolvedValue(new Blob(['pdf'], { type: 'application/pdf' })),
  });
  window.alert = jest.fn();
  window.confirm = jest.fn(() => true);
  window.URL.createObjectURL = jest.fn(() => 'blob:test-pdf');
  window.URL.revokeObjectURL = jest.fn();

  const originalCreateElement = document.createElement.bind(document);
  createElementSpy = jest.spyOn(document, 'createElement').mockImplementation((tagName, options) => {
    const element = originalCreateElement(tagName, options);
    if (String(tagName).toLowerCase() === 'a') {
      element.click = jest.fn();
    }
    return element;
  });
  consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
  consoleWarnSpy = jest.spyOn(console, 'warn').mockImplementation(() => {});
});

afterEach(() => {
  createElementSpy?.mockRestore();
  consoleErrorSpy?.mockRestore();
  consoleWarnSpy?.mockRestore();
  window.Image = originalImage;
  global.fetch = originalFetch;
});

function renderProjectDetail() {
  return render(
    <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <ProjectDetail />
    </MemoryRouter>,
  );
}

function getEquipmentGroup(name) {
  return screen.getByRole('heading', { name }).closest('.project-equipment-group');
}

test('queues PDF generation and downloads the latest ready PDF', async () => {
  projectsApi.getPdfPreview.mockResolvedValue({
    project_id: 10,
    pdf_path: 'outputs/project-10.pdf',
    pdf_url: '/api/assets/outputs/project-10.pdf',
    generated_at: '2026-05-12T10:00:00Z',
    current_task: null,
  });

  renderProjectDetail();

  await screen.findByRole('heading', { name: 'Объект' });
  const previewLink = screen.getByRole('link', { name: 'Просмотр PDF' });
  expect(previewLink).toHaveAttribute('href', '/projects/10/preview');
  expect(previewLink).toHaveAttribute('target', '_blank');

  await userEvent.click(screen.getByRole('button', { name: 'Скачать PDF' }));

  await waitFor(() => {
    expect(global.fetch).toHaveBeenCalledWith('/api/assets/outputs/project-10.pdf', { credentials: 'include' });
  });
  expect(window.URL.createObjectURL).toHaveBeenCalled();
  expect(window.URL.revokeObjectURL).toHaveBeenCalledWith('blob:test-pdf');

  await userEvent.click(screen.getByRole('button', { name: /Сгенерировать PDF/i }));

  await waitFor(() => {
    expect(projectsApi.generatePdf).toHaveBeenCalledWith('10');
  });

  expect(window.alert).not.toHaveBeenCalled();
});

test('project detail uploads a valid floor plan image', async () => {
  floorPlansApi.create.mockResolvedValueOnce({ id: 88 });
  floorPlansApi.list
    .mockResolvedValueOnce([])
    .mockResolvedValueOnce([
      {
        id: 88,
        name: 'Этаж 1',
        floor_number: 1,
        image_width: 800,
        image_height: 600,
      },
    ]);

  renderProjectDetail();

  await screen.findByRole('heading', { name: /Объект/i });
  const fileInput = document.querySelector('input[type="file"]');
  const file = new File(['image'], 'plan.png', { type: 'image/png' });

  await userEvent.upload(fileInput, file);

  await waitFor(() => {
    expect(floorPlansApi.create).toHaveBeenCalledTimes(1);
  });

  expect(mockNavigate).toHaveBeenCalledWith('/floor-plans/88');
});

test('project detail blocks uploading a non-image floor plan file', async () => {
  renderProjectDetail();

  await screen.findByRole('heading', { name: /Объект/i });
  const fileInput = document.querySelector('input[type="file"]');
  const file = new File(['pdf'], 'plan.pdf', { type: 'application/pdf' });

  await userEvent.upload(fileInput, file);

  await waitFor(() => {
    expect(useDialogs().toast).toHaveBeenCalledWith(expect.stringContaining('200x200'), { tone: 'error' });
  });

  expect(floorPlansApi.create).not.toHaveBeenCalled();
  expect(mockNavigate).not.toHaveBeenCalled();
});

test('project detail blocks uploading a floor plan image smaller than 200x200', async () => {
  mockImageLoad({ width: 199, height: 250 });

  renderProjectDetail();

  await screen.findByRole('heading', { name: /Объект/i });
  const fileInput = document.querySelector('input[type="file"]');
  const file = new File(['image'], 'small-plan.png', { type: 'image/png' });

  await userEvent.upload(fileInput, file);

  await waitFor(() => {
    expect(useDialogs().toast).toHaveBeenCalledWith(expect.stringContaining('200x200'), { tone: 'error' });
  });

  expect(floorPlansApi.create).not.toHaveBeenCalled();
  expect(mockNavigate).not.toHaveBeenCalled();
});

test('project details save updated facility field', async () => {
  projectsApi.update.mockResolvedValueOnce({
    ...projectResponse,
    facility: 'Новый объект',
    facility_genitive: 'Нового объекта',
    facility_instrumental: 'Новым объектом',
  });

  renderProjectDetail();

  await screen.findByRole('heading', { name: 'Объект' });
  const facilityInput = screen.getByDisplayValue('Объект');
  const genitiveInput = screen.getByDisplayValue('Объекта');
  const instrumentalInput = screen.getByDisplayValue('Объектом');

  await userEvent.clear(facilityInput);
  await userEvent.type(facilityInput, 'Новый объект');
  await userEvent.clear(genitiveInput);
  await userEvent.type(genitiveInput, 'Нового объекта');
  await userEvent.clear(instrumentalInput);
  await userEvent.type(instrumentalInput, 'Новым объектом');
  await userEvent.click(screen.getByRole('button', { name: 'Сохранить' }));

  await waitFor(() => {
    expect(projectsApi.update).toHaveBeenCalledWith('10', expect.objectContaining({
      facility: 'Новый объект',
      facility_genitive: 'Нового объекта',
      facility_instrumental: 'Новым объектом',
    }));
  });
});

test('project owner selection syncs engineer before saving', async () => {
  projectsApi.update.mockResolvedValueOnce({
    ...projectResponse,
    engineer: 'Engineer Two',
    owner_user_id: 22,
    owner_user: { id: 22, full_name: 'Engineer Two', username: 'eng2', role: 'engineer' },
  });

  renderProjectDetail();

  await waitFor(() => {
    const ownerOption = document.querySelector('select[name="owner_user_id"] option[value="22"]');
    expect(ownerOption).not.toBeNull();
  });
  const ownerSelect = document.querySelector('select[name="owner_user_id"]');
  await userEvent.selectOptions(ownerSelect, '22');

  expect(document.querySelector('input[name="engineer"]')).toHaveValue('Engineer Two');

  const saveButton = document.querySelector('.project-detail-card__header button.btn-primary');
  await userEvent.click(saveButton);

  await waitFor(() => {
    expect(projectsApi.update).toHaveBeenCalledWith('10', expect.objectContaining({
      engineer: 'Engineer Two',
      owner_user_id: 22,
    }));
  });
});

test('project detail renders shared project stages for general data, instructions, power calculation and specification', async () => {
  floorPlansApi.list.mockResolvedValueOnce([
    {
      id: 77,
      name: 'Этаж 1',
      floor_number: 1,
      image_width: 1600,
      image_height: 900,
    },
  ]);

  renderProjectDetail();

  expect(await screen.findByRole('heading', { name: 'Этапы проекта' })).toBeInTheDocument();

  const floorPlanLink = screen.getByRole('link', { name: /Этаж 1/i });
  const generalDataLink = screen.getByRole('link', { name: /Общие данные/i });
  const generalInstructionsLink = screen.getByRole('link', { name: /Общие указания/i });
  const powerLink = screen.getByRole('link', { name: /Расчет токопотребления/i });
  const specificationLink = screen.getByRole('link', { name: /Спецификация/i });
  const additionalInfoLink = screen.getByRole('link', { name: /Доп\. сведения/i });

  expect(floorPlanLink.getAttribute('href')).toContain('/floor-plans/77');
  expect(generalDataLink.getAttribute('href')).toContain('/floor-plans/77?step=general_data');
  expect(generalInstructionsLink.getAttribute('href')).toContain('/floor-plans/77?step=general_instructions');
  expect(powerLink.getAttribute('href')).toContain('/floor-plans/77?step=power_consumption_calculation');
  expect(specificationLink.getAttribute('href')).toContain('/floor-plans/77?step=equipment_specification');
  expect(additionalInfoLink.getAttribute('href')).toContain('/floor-plans/77?step=additional_info');
  expect(additionalInfoLink.querySelector('.project-stage-card')).toHaveClass('project-stage-card--subtle');
  expect(screen.getByRole('heading', { name: '\u041a\u0440\u0435\u043f\u043b\u0435\u043d\u0438\u044f' })).toBeInTheDocument();
});

test('project detail shows approximate project cost from the equipment specification', async () => {
  renderProjectDetail();

  expect(await screen.findByText('Примерная стоимость проекта')).toBeInTheDocument();
  expect(screen.getByText('16100.00 ₽')).toBeInTheDocument();
});

test('project detail attaches an existing catalog item into the selected group', async () => {
  projectsApi.attachEquipment.mockResolvedValueOnce({
    project_id: 10,
    items: [...projectEquipmentResponse.items, smokeB],
  });

  renderProjectDetail();

  await screen.findByRole('heading', { name: 'Оборудование проекта' });
  const spsGroup = getEquipmentGroup('СПС');

  await userEvent.click(within(spsGroup).getByRole('button', { name: /\+ Добавить/i }));
  await userEvent.selectOptions(screen.getByLabelText('Карточка оборудования'), '102');
  await userEvent.click(screen.getByRole('button', { name: 'Добавить в проект' }));

  await waitFor(() => {
    expect(projectsApi.attachEquipment).toHaveBeenCalledWith('10', { equipment_id: 102 });
  });

  expect(await screen.findByText('Smoke B')).toBeInTheDocument();
});

test('project detail shows separate SPS and SOUE cable selectors', async () => {
  renderProjectDetail();

  await screen.findByLabelText('Кабель СПС');

  const spsCableSelect = screen.getByLabelText('Кабель СПС');
  const soueCableSelect = screen.getByLabelText('Кабель СОУЭ');

  expect(within(spsCableSelect).getByRole('option', { name: /Cable A/ })).toBeInTheDocument();
  expect(spsCableSelect).toHaveValue('301');
  expect(soueCableSelect).toHaveValue('');

  await userEvent.selectOptions(soueCableSelect, '301');

  await waitFor(() => {
    expect(projectsApi.updateEquipmentSelections).toHaveBeenCalledWith('10', {
      selections: {
        sps_linear_detector: null,
        sps_smoke_detector: null,
        sps_heat_detector: null,
        sps_manual_call_point: null,
        sps_cable: 301,
        soue_siren: null,
        soue_exit_sign: null,
        soue_speech_device: null,
        soue_cable: 301,
        common_instrument: null,
        common_keyboard: null,
        common_other: null,
      },
    });
  });
});

test('project detail creates a new equipment card and attaches it to the project', async () => {
  const createdItem = {
    id: 777,
    name: 'Panel X',
    category: 'instrument',
    price: 123.46,
    compatible_equipment_ids: [],
  };
  projectsApi.createAndAttachEquipment.mockResolvedValueOnce({
    project_id: 10,
    items: [...projectEquipmentResponse.items, createdItem],
  });
  equipmentApi.list.mockResolvedValue([...equipmentItemsResponse, createdItem]);

  renderProjectDetail();

  await screen.findByRole('heading', { name: 'Оборудование проекта' });
  const instrumentsGroup = getEquipmentGroup('Приборы');

  await userEvent.click(within(instrumentsGroup).getByRole('button', { name: /\+ Добавить/i }));
  await userEvent.click(screen.getByRole('button', { name: 'Новая карточка' }));
  await userEvent.type(screen.getByLabelText('Название'), 'Panel X');
  await userEvent.selectOptions(screen.getByLabelText('Категория'), 'instrument');
  await userEvent.type(screen.getByLabelText('Цена'), '123.456');
  await userEvent.type(screen.getByLabelText('Описание'), 'Пульт управления');
  await userEvent.click(screen.getByRole('button', { name: 'Добавить в проект' }));

  await waitFor(() => {
    expect(projectsApi.createAndAttachEquipment).toHaveBeenCalledWith('10', expect.objectContaining({
      name: 'Panel X',
      category: 'instrument',
      price: 123.46,
    }));
  });

  expect(await screen.findByText('Panel X')).toBeInTheDocument();
});

test('project detail creates a mounting card with fastening parameters', async () => {
  const createdItem = {
    id: 778,
    name: 'Clip Pack B',
    category: 'mounting',
    price: 420,
    compatible_equipment_ids: [],
  };
  projectsApi.createAndAttachEquipment.mockResolvedValueOnce({
    project_id: 10,
    items: [...projectEquipmentResponse.items, createdItem],
  });
  equipmentApi.list.mockResolvedValue([...equipmentItemsResponse, createdItem]);

  renderProjectDetail();

  await screen.findByRole('heading', { name: '\u041e\u0431\u043e\u0440\u0443\u0434\u043e\u0432\u0430\u043d\u0438\u0435 \u043f\u0440\u043e\u0435\u043a\u0442\u0430' });
  const mountingGroup = getEquipmentGroup('\u041a\u0440\u0435\u043f\u043b\u0435\u043d\u0438\u044f');

  await userEvent.click(within(mountingGroup).getByRole('button', { name: /\+ \u0414\u043e\u0431\u0430\u0432\u0438\u0442\u044c/i }));
  await userEvent.click(screen.getByRole('button', { name: '\u041d\u043e\u0432\u0430\u044f \u043a\u0430\u0440\u0442\u043e\u0447\u043a\u0430' }));
  await userEvent.type(screen.getByLabelText('\u041d\u0430\u0437\u0432\u0430\u043d\u0438\u0435'), 'Clip Pack B');
  await userEvent.type(screen.getByLabelText('\u0426\u0435\u043d\u0430'), '420');
  await userEvent.type(screen.getByLabelText('\u041a\u043e\u043b-\u0432\u043e \u0448\u0442\u0443\u043a \u0432 \u043f\u0430\u0447\u043a\u0435'), '120');
  await userEvent.type(screen.getByLabelText('\u041a\u0440\u0430\u0442\u043d\u043e\u0441\u0442\u044c \u043a\u0440\u0435\u043f\u043b\u0435\u043d\u0438\u044f, \u043c'), '0.5');
  await userEvent.click(screen.getByRole('button', { name: '\u0414\u043e\u0431\u0430\u0432\u0438\u0442\u044c \u0432 \u043f\u0440\u043e\u0435\u043a\u0442' }));

  await waitFor(() => {
    expect(projectsApi.createAndAttachEquipment).toHaveBeenCalledWith('10', expect.objectContaining({
      name: 'Clip Pack B',
      category: 'mounting',
      price: 420,
      specs: {
        pack_quantity: 120,
        mounting_spacing_m: 0.5,
      },
    }));
  });
});
