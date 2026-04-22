import React from 'react';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import EquipmentCatalogPage from './EquipmentCatalogPage';
import { equipmentApi } from '../api/client';

jest.mock('../api/client', () => ({
  equipmentApi: {
    list: jest.fn(),
    create: jest.fn(),
    update: jest.fn(),
    remove: jest.fn(),
    uploadImage: jest.fn(),
    uploadLabelPdf: jest.fn(),
    uploadManualPdf: jest.fn(),
  },
}));

const smokeItem = {
  id: 101,
  name: 'Smoke A',
  category: 'smoke',
  description: 'Smoke detector',
  price: 1200,
  manufacturer: 'Acme',
  service_life_years: 10,
  notes: 'Primary detector',
  specs: {
    addressing_mode: 'addressable',
    loop_voltage_v: { min: 12, max: 24 },
    standby_current_a: 0.0001,
    alarm_current_a: 0.0003,
  },
  smoke_addressing: 'addressable',
  image_path: null,
  label_pdf_path: 'uploads/label_101.pdf',
  manual_pdf_path: 'uploads/manual_101.pdf',
  compatible_equipment_ids: [],
};

const cableItem = {
  id: 201,
  name: 'Cable A',
  category: 'cable',
  description: 'Fire cable',
  price: 200,
  manufacturer: null,
  service_life_years: null,
  notes: null,
  specs: {
    conductors_count: 2,
    conductor_type: 'Cu',
    working_voltage_max_v: 300,
    attenuation_db_per_km_1khz_20c: 12,
    sale_multiple_m: 100,
  },
  smoke_addressing: null,
  image_path: null,
  label_pdf_path: null,
  manual_pdf_path: null,
  compatible_equipment_ids: [],
};

const instrumentItem = {
  id: 401,
  name: 'Console A',
  category: 'instrument',
  description: 'Control console',
  price: 5400,
  manufacturer: 'Bolid',
  service_life_years: 8,
  notes: 'Console notes',
  specs: {
    instrument_subtype: 'control_and_management_console',
    connected_instruments_count: 16,
    sections_count: 32,
    section_groups_count: 8,
    supply_voltage_v: { min: 12, max: 24 },
    current_12v_a: 0.120456,
    current_24v_a: 0.080123,
  },
  smoke_addressing: null,
  image_path: null,
  label_pdf_path: null,
  manual_pdf_path: null,
  compatible_equipment_ids: [],
};

const mountingItem = {
  id: 501,
  name: 'Clip Pack',
  category: 'mounting',
  description: 'Mounting kit',
  price: 350,
  manufacturer: 'FixIt',
  service_life_years: 5,
  notes: 'For cable trays',
  specs: {
    pack_quantity: 100,
    mounting_spacing_m: 0.4,
  },
  smoke_addressing: null,
  image_path: null,
  label_pdf_path: null,
  manual_pdf_path: null,
  compatible_equipment_ids: [],
};

beforeEach(() => {
  jest.clearAllMocks();
  window.confirm = jest.fn(() => true);
  equipmentApi.list.mockResolvedValue([smokeItem, cableItem]);
  equipmentApi.create.mockResolvedValue({
    id: 301,
    name: 'Smoke B',
    category: 'smoke',
    description: 'Backup smoke detector',
    price: 500.12,
    manufacturer: 'Bolid',
    service_life_years: 12,
    notes: 'Created in test',
    specs: {
      addressing_mode: 'addressable',
      loop_voltage_v: { min: 12, max: 24 },
      standby_current_a: 0.0008,
      alarm_current_a: 0.0008,
    },
    smoke_addressing: 'addressable',
    image_path: null,
    label_pdf_path: null,
    manual_pdf_path: null,
    compatible_equipment_ids: [201],
  });
  equipmentApi.uploadImage.mockResolvedValue({
    id: 301,
    name: 'Smoke B',
    category: 'smoke',
    description: 'Backup smoke detector',
    price: 500.12,
    manufacturer: 'Bolid',
    service_life_years: 12,
    notes: 'Created in test',
    specs: {
      addressing_mode: 'addressable',
      loop_voltage_v: { min: 12, max: 24 },
      standby_current_a: 0.0008,
      alarm_current_a: 0.0008,
    },
    smoke_addressing: 'addressable',
    image_path: 'uploads/equipment_301.png',
    label_pdf_path: null,
    manual_pdf_path: null,
    compatible_equipment_ids: [201],
  });
  equipmentApi.uploadLabelPdf.mockResolvedValue({
    id: 301,
    name: 'Smoke B',
    category: 'smoke',
    description: 'Backup smoke detector',
    price: 500.12,
    manufacturer: 'Bolid',
    service_life_years: 12,
    notes: 'Created in test',
    specs: {
      addressing_mode: 'addressable',
      loop_voltage_v: { min: 12, max: 24 },
      standby_current_a: 0.0008,
      alarm_current_a: 0.0008,
    },
    smoke_addressing: 'addressable',
    image_path: 'uploads/equipment_301.png',
    label_pdf_path: 'uploads/label_301.pdf',
    manual_pdf_path: null,
    compatible_equipment_ids: [201],
  });
  equipmentApi.uploadManualPdf.mockResolvedValue({
    id: 301,
    name: 'Smoke B',
    category: 'smoke',
    description: 'Backup smoke detector',
    price: 500.12,
    manufacturer: 'Bolid',
    service_life_years: 12,
    notes: 'Created in test',
    specs: {
      addressing_mode: 'addressable',
      loop_voltage_v: { min: 12, max: 24 },
      standby_current_a: 0.0008,
      alarm_current_a: 0.0008,
    },
    smoke_addressing: 'addressable',
    image_path: 'uploads/equipment_301.png',
    label_pdf_path: 'uploads/label_301.pdf',
    manual_pdf_path: 'uploads/manual_301.pdf',
    compatible_equipment_ids: [201],
  });
});

test('shows compact cards, detector addressing in filtered view, and keeps documents as open-only assets', async () => {
  render(<EquipmentCatalogPage />);

  await screen.findByRole('heading', { name: 'Оборудование' });
  const smokeCard = await screen.findByRole('button', { name: /Smoke A/i });
  const cableCard = await screen.findByRole('button', { name: /Cable A/i });

  expect(within(smokeCard).getByText('Дымовые')).toBeInTheDocument();
  expect(within(smokeCard).getByText('Acme')).toBeInTheDocument();
  expect(within(smokeCard).getByText(/1200\.00/)).toBeInTheDocument();
  expect(within(cableCard).getByText('Кабели')).toBeInTheDocument();

  await userEvent.click(screen.getByRole('button', { name: 'Дымовые' }));
  expect(await screen.findByRole('button', { name: /Smoke A/i })).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /Cable A/i })).not.toBeInTheDocument();
  expect(within(screen.getByRole('button', { name: /Smoke A/i })).queryByText('Дымовые')).not.toBeInTheDocument();
  expect(within(screen.getByRole('button', { name: /Smoke A/i })).getByText('Адресный')).toBeInTheDocument();

  await userEvent.click(screen.getByRole('button', { name: 'Все' }));
  expect(await screen.findByRole('button', { name: /Cable A/i })).toBeInTheDocument();

  await userEvent.click(screen.getByRole('button', { name: /Smoke A/i }));
  expect(screen.getByRole('dialog', { name: 'Smoke A' })).toBeInTheDocument();
  expect(screen.getByText('0.0003')).toBeInTheDocument();
  expect(screen.queryByLabelText('Предпросмотр PDF: Этикетка')).not.toBeInTheDocument();
  expect(screen.getByText('label_101.pdf')).toBeInTheDocument();
  expect(screen.queryByLabelText('Предпросмотр PDF: Руководство')).not.toBeInTheDocument();
  expect(screen.getByText('manual_101.pdf')).toBeInTheDocument();
});

test('creates a smoke card with voltage range, compatibility picker and uploads image plus two pdf files', async () => {
  const createdItem = {
    id: 301,
    name: 'Smoke B',
    category: 'smoke',
    description: 'Backup smoke detector',
    price: 500.12,
    manufacturer: 'Bolid',
    service_life_years: 12,
    notes: 'Created in test',
    specs: {
      addressing_mode: 'addressable',
      loop_voltage_v: { min: 12, max: 24 },
      standby_current_a: 0.0008,
      alarm_current_a: 0.0008,
    },
    smoke_addressing: 'addressable',
    image_path: 'uploads/equipment_301.png',
    label_pdf_path: 'uploads/label_301.pdf',
    manual_pdf_path: 'uploads/manual_301.pdf',
    compatible_equipment_ids: [201],
  };
  equipmentApi.list
    .mockResolvedValueOnce([cableItem])
    .mockResolvedValueOnce([createdItem, cableItem]);

  render(<EquipmentCatalogPage />);

  await screen.findByRole('heading', { name: 'Оборудование' });
  await userEvent.click(screen.getByRole('button', { name: 'Добавить оборудование' }));

  await userEvent.type(screen.getByLabelText('Название'), 'Smoke B');
  await userEvent.selectOptions(screen.getByLabelText('Тип'), 'smoke');
  await userEvent.type(screen.getByLabelText('Цена'), '500.12');
  await userEvent.type(screen.getByLabelText('Производитель'), 'Bolid');
  await userEvent.type(screen.getByLabelText('Срок службы, лет'), '12');
  await userEvent.selectOptions(screen.getByLabelText('Адресный/безадресный'), 'addressable');

  const voltageField = screen
    .getByText('Напряжение питания в шлейфе, В')
    .closest('.equipment-spec-field');
  const voltageInputs = within(voltageField).getAllByRole('spinbutton');
  await userEvent.type(voltageInputs[0], '12');
  await userEvent.type(voltageInputs[1], '24');
  await userEvent.type(screen.getByLabelText('Токопотребление в дежурном режиме, А'), '0.0008');

  await userEvent.click(screen.getByRole('button', { name: '+ Добавить совместимое оборудование' }));
  await userEvent.click(within(screen.getByRole('listbox', { name: 'Оборудование в системе' })).getByRole('button', { name: /Cable A/i }));
  expect(screen.getByLabelText('Убрать Cable A')).toBeInTheDocument();

  await userEvent.upload(
    screen.getByLabelText('Изображение'),
    new File(['image'], 'smoke.png', { type: 'image/png' }),
  );
  await userEvent.upload(
    screen.getByLabelText('Этикетка'),
    new File(['label'], 'label.jpg', { type: 'image/jpeg' }),
  );
  await userEvent.upload(
    screen.getByLabelText('Руководство'),
    new File(['manual'], 'manual.jpg', { type: 'image/jpeg' }),
  );
  await userEvent.click(screen.getByRole('button', { name: 'Сохранить' }));

  await waitFor(() => {
    expect(equipmentApi.create).toHaveBeenCalledWith(expect.objectContaining({
      name: 'Smoke B',
      category: 'smoke',
      price: 500.12,
      manufacturer: 'Bolid',
      service_life_years: 12,
      specs: {
        addressing_mode: 'addressable',
        loop_voltage_v: { min: 12, max: 24 },
        standby_current_a: 0.0008,
        alarm_current_a: 0.0008,
      },
      compatible_equipment_ids: [201],
    }));
  });
  await waitFor(() => {
    expect(equipmentApi.uploadImage).toHaveBeenCalledWith(301, expect.any(File));
    expect(equipmentApi.uploadLabelPdf).toHaveBeenCalledWith(301, expect.any(File));
    expect(equipmentApi.uploadManualPdf).toHaveBeenCalledWith(301, expect.any(File));
  });

  expect(await screen.findByRole('dialog', { name: 'Smoke B' })).toBeInTheDocument();
  expect(screen.getAllByText(/500\.12/).length).toBeGreaterThan(0);
});

test('instrument form switches subtype-specific fields and submits console specs', async () => {
  equipmentApi.create.mockResolvedValueOnce({
    ...instrumentItem,
    id: 402,
    name: 'Console B',
    specs: {
      instrument_subtype: 'control_and_management_console',
      connected_instruments_count: 12,
      sections_count: 24,
      section_groups_count: 6,
      supply_voltage_v: 24,
      current_12v_a: 0.123456,
      current_24v_a: 0.234567,
    },
  });

  render(<EquipmentCatalogPage />);

  await screen.findByRole('heading', { name: 'Оборудование' });
  await userEvent.click(screen.getByRole('button', { name: 'Добавить оборудование' }));
  await userEvent.type(screen.getByLabelText('Название'), 'Console B');
  await userEvent.selectOptions(screen.getByLabelText('Тип'), 'instrument');

  expect(screen.getByLabelText('Подкатегория прибора')).toBeInTheDocument();
  expect(screen.getByRole('option', { name: 'Приемно-контрольные охранно-пожарные' })).toBeInTheDocument();
  expect(screen.getByRole('option', { name: 'Пульт контроля и управления' })).toBeInTheDocument();
  expect(screen.getByRole('option', { name: 'Блок индикации' })).toBeInTheDocument();
  expect(screen.getByLabelText('Кол-во зон')).toBeInTheDocument();
  expect(screen.getByLabelText('Кол-во ШС')).toBeInTheDocument();
  expect(screen.getByLabelText('Напряжение на клеммах для подключения ШС, В от')).toBeInTheDocument();
  expect(screen.queryByLabelText('Кол-во подключаемых приборов')).not.toBeInTheDocument();

  await userEvent.selectOptions(screen.getByLabelText('Подкатегория прибора'), 'control_and_management_console');

  expect(screen.queryByLabelText('Кол-во зон')).not.toBeInTheDocument();
  expect(screen.queryByLabelText('Кол-во ШС')).not.toBeInTheDocument();
  expect(screen.getByLabelText('Кол-во подключаемых приборов')).toBeInTheDocument();
  expect(screen.getByLabelText('Кол-во разделов')).toBeInTheDocument();
  expect(screen.getByLabelText('Кол-во групп разделов')).toBeInTheDocument();
  expect(screen.getByLabelText('Напряжение, В от')).toBeInTheDocument();
  expect(screen.getByLabelText('Токопотребление 12В, А')).toBeInTheDocument();
  expect(screen.getByLabelText('Токопотребление 24В, А')).toBeInTheDocument();
  expect(screen.getByRole('option', { name: 'Аккумуляторы' })).toBeInTheDocument();
  expect(screen.queryByRole('option', { name: 'Клавиатуры' })).not.toBeInTheDocument();

  await userEvent.selectOptions(screen.getByLabelText('Подкатегория прибора'), 'indication_unit');
  expect(screen.queryByLabelText('Кол-во подключаемых приборов')).not.toBeInTheDocument();
  expect(screen.queryByLabelText('Токопотребление 12В, А')).not.toBeInTheDocument();
  expect(screen.getByLabelText('Напряжение, В от')).toBeInTheDocument();
  expect(screen.getByLabelText('Токопотребление в дежурном режиме, А')).toBeInTheDocument();
  expect(screen.getByLabelText('Токопотребление в режиме "Пожар", А')).toBeInTheDocument();

  await userEvent.selectOptions(screen.getByLabelText('Подкатегория прибора'), 'control_and_management_console');

  await userEvent.type(screen.getByLabelText('Цена'), '5400');
  await userEvent.type(screen.getByLabelText('Кол-во подключаемых приборов'), '12');
  await userEvent.type(screen.getByLabelText('Кол-во разделов'), '24');
  await userEvent.type(screen.getByLabelText('Кол-во групп разделов'), '6');
  await userEvent.type(screen.getByLabelText('Напряжение, В от'), '24');
  await userEvent.type(screen.getByLabelText('Токопотребление 12В, А'), '0.123456');
  await userEvent.type(screen.getByLabelText('Токопотребление 24В, А'), '0.234567');
  await userEvent.click(screen.getByRole('button', { name: 'Сохранить' }));

  await waitFor(() => {
    expect(equipmentApi.create).toHaveBeenCalledWith(expect.objectContaining({
      name: 'Console B',
      category: 'instrument',
      price: 5400,
      specs: {
        instrument_subtype: 'control_and_management_console',
        connected_instruments_count: 12,
        sections_count: 24,
        section_groups_count: 6,
        supply_voltage_v: 24,
        current_12v_a: 0.123456,
        current_24v_a: 0.234567,
      },
    }));
  });
});

test('shows instrument subtype-specific values in preview modal', async () => {
  equipmentApi.list.mockResolvedValueOnce([instrumentItem, smokeItem, cableItem]);

  render(<EquipmentCatalogPage />);

  await screen.findByRole('heading', { name: 'Оборудование' });
  await userEvent.click(await screen.findByRole('button', { name: /Console A/i }));
  expect(screen.getByRole('dialog', { name: 'Console A' })).toBeInTheDocument();
  expect(screen.getByText('Пульт контроля и управления')).toBeInTheDocument();
  expect(screen.getByText('0.120456')).toBeInTheDocument();
  expect(screen.getByText('0.080123')).toBeInTheDocument();
});

test.skip('mounting form shows fastening fields and submits mounting specs', async () => {
  equipmentApi.create.mockResolvedValueOnce({
    ...mountingItem,
    id: 502,
    name: 'Clip Pack B',
    specs: {
      pack_quantity: 120,
      mounting_spacing_m: 0.5,
    },
  });

  render(<EquipmentCatalogPage />);

  await screen.findByRole('heading', { name: 'РћР±РѕСЂСѓРґРѕРІР°РЅРёРµ' });
  await userEvent.click(screen.getByRole('button', { name: 'Р”РѕР±Р°РІРёС‚СЊ РѕР±РѕСЂСѓРґРѕРІР°РЅРёРµ' }));
  await userEvent.type(screen.getByLabelText('РќР°Р·РІР°РЅРёРµ'), 'Clip Pack B');
  await userEvent.selectOptions(screen.getByLabelText('РўРёРї'), 'mounting');
  await userEvent.type(screen.getByLabelText('РљРѕР»-РІРѕ С€С‚СѓРє РІ РїР°С‡РєРµ, С€С‚'), '120');
  await userEvent.type(screen.getByLabelText('РљСЂР°С‚РЅРѕСЃС‚СЊ РєСЂРµРїР»РµРЅРёСЏ, Рј'), '0.5');
  await userEvent.click(screen.getByRole('button', { name: 'РЎРѕС…СЂР°РЅРёС‚СЊ' }));

  await waitFor(() => {
    expect(equipmentApi.create).toHaveBeenCalledWith(expect.objectContaining({
      name: 'Clip Pack B',
      category: 'mounting',
      specs: {
        pack_quantity: 120,
        mounting_spacing_m: 0.5,
      },
    }));
  });
});

test('mounting form shows fastening fields and submits mounting specs with readable labels', async () => {
  equipmentApi.create.mockResolvedValueOnce({
    ...mountingItem,
    id: 502,
    name: 'Clip Pack B',
    specs: {
      pack_quantity: 120,
      mounting_spacing_m: 0.5,
    },
  });

  render(<EquipmentCatalogPage />);

  await screen.findByRole('heading', { name: 'Оборудование' });
  await userEvent.click(screen.getByRole('button', { name: 'Добавить оборудование' }));
  await userEvent.type(screen.getByLabelText('Название'), 'Clip Pack B');
  await userEvent.selectOptions(screen.getByLabelText('Тип'), 'mounting');
  await userEvent.type(screen.getByLabelText('Кол-во штук в пачке, шт'), '120');
  await userEvent.type(screen.getByLabelText('Кратность крепления, м'), '0.5');
  await userEvent.click(screen.getByRole('button', { name: 'Сохранить' }));

  await waitFor(() => {
    expect(equipmentApi.create).toHaveBeenCalledWith(expect.objectContaining({
      name: 'Clip Pack B',
      category: 'mounting',
      specs: {
        pack_quantity: 120,
        mounting_spacing_m: 0.5,
      },
    }));
  });
});
