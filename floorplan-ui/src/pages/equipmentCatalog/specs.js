const NUMBER_FORMATTER = new Intl.NumberFormat('ru-RU', {
  maximumFractionDigits: 3,
});

const CURRENT_FIELD_NAMES = new Set([
  'standby_current_a',
  'alarm_current_a',
  'current_12v_a',
  'current_24v_a',
]);

const ADDRESSING_OPTIONS = [
  { value: 'addressable', label: 'Адресный' },
  { value: 'non_addressable', label: 'Безадресный' },
];

const ADDRESSED_DETECTOR_CATEGORIES = new Set(['smoke', 'heat', 'linear', 'manual']);

const INSTRUMENT_SUBTYPE_OPTIONS = [
  { value: 'security_fire_control_panel', label: 'Приемно-контрольные охранно-пожарные' },
  { value: 'control_and_management_console', label: 'Пульт контроля и управления' },
  { value: 'indication_unit', label: 'Блок индикации' },
];

const CATEGORY_SPEC_FIELDS = {
  smoke: [
    { name: 'addressing_mode', label: 'Адресный/безадресный', type: 'select', options: ADDRESSING_OPTIONS },
    { name: 'loop_voltage_v', label: 'Напряжение питания в шлейфе, В', type: 'voltage_range' },
    { name: 'standby_current_a', label: 'Токопотребление в дежурном режиме, А', type: 'number', min: '0', step: '0.000001' },
    { name: 'alarm_current_a', label: 'Токопотребление в режиме "Пожар", А', type: 'number', min: '0', step: '0.000001' },
  ],
  heat: [
    { name: 'addressing_mode', label: 'Адресный/безадресный', type: 'select', options: ADDRESSING_OPTIONS },
    { name: 'loop_voltage_v', label: 'Напряжение питания в шлейфе, В', type: 'voltage_range' },
    { name: 'standby_current_a', label: 'Токопотребление в дежурном режиме, А', type: 'number', min: '0', step: '0.000001' },
    { name: 'alarm_current_a', label: 'Токопотребление в режиме "Пожар", А', type: 'number', min: '0', step: '0.000001' },
  ],
  linear: [
    { name: 'addressing_mode', label: 'Адресный/безадресный', type: 'select', options: ADDRESSING_OPTIONS },
    { name: 'loop_voltage_v', label: 'Напряжение питания в шлейфе, В', type: 'voltage_range' },
    { name: 'standby_current_a', label: 'Токопотребление в дежурном режиме, А', type: 'number', min: '0', step: '0.000001' },
    { name: 'alarm_current_a', label: 'Токопотребление в режиме "Пожар", А', type: 'number', min: '0', step: '0.000001' },
    { name: 'range_m', label: 'Дальность действия, м', type: 'number', min: '0', step: '0.01' },
  ],
  manual: [
    { name: 'addressing_mode', label: 'Адресный/безадресный', type: 'select', options: ADDRESSING_OPTIONS },
    { name: 'loop_voltage_v', label: 'Напряжение питания в шлейфе, В', type: 'voltage_range' },
    { name: 'standby_current_a', label: 'Токопотребление в дежурном режиме, А', type: 'number', min: '0', step: '0.000001' },
    { name: 'alarm_current_a', label: 'Токопотребление в режиме "Пожар", А', type: 'number', min: '0', step: '0.000001' },
  ],
  exit_sign: [
    { name: 'supply_voltage_v', label: 'Напряжение питания, В', type: 'voltage_range' },
    { name: 'standby_current_a', label: 'Токопотребление в дежурном режиме, А', type: 'number', min: '0', step: '0.000001' },
    { name: 'alarm_current_a', label: 'Токопотребление в режиме "Пожар", А', type: 'number', min: '0', step: '0.000001' },
  ],
  siren: [
    { name: 'sound_pressure_db', label: 'Уровень звукового давления, дБ', type: 'number', min: '0', step: '0.01' },
    { name: 'supply_voltage_v', label: 'Напряжение питания, В', type: 'voltage_range' },
    { name: 'standby_current_a', label: 'Токопотребление в дежурном режиме, А', type: 'number', min: '0', step: '0.000001' },
    { name: 'alarm_current_a', label: 'Токопотребление в режиме "Пожар", А', type: 'number', min: '0', step: '0.000001' },
  ],
  cable: [
    { name: 'conductors_count', label: 'Кол-во проводников, шт', type: 'number', min: '0', step: '1' },
    { name: 'conductor_type', label: 'Тип проводника', type: 'text' },
    { name: 'working_voltage_max_v', label: 'Рабочее напряжение, В', type: 'voltage_range' },
    { name: 'attenuation_db_per_km_1khz_20c', label: 'Коэффициент затухания при 1 кГц и 20°C, дБ/км', type: 'number', min: '0', step: '0.01' },
    { name: 'sale_multiple_m', label: 'Кратность продажи, м', type: 'number', min: '0', step: '0.01' },
  ],
  instrument: [
    {
      name: 'instrument_subtype',
      label: 'Подкатегория прибора',
      type: 'select',
      options: INSTRUMENT_SUBTYPE_OPTIONS,
      defaultValue: 'security_fire_control_panel',
    },
    {
      name: 'zone_count',
      label: 'Кол-во зон',
      type: 'number',
      min: '0',
      step: '1',
      hidden: (specs) => specs?.instrument_subtype !== 'security_fire_control_panel',
    },
    {
      name: 'shs_count',
      label: 'Кол-во ШС',
      type: 'number',
      min: '0',
      step: '1',
      hidden: (specs) => specs?.instrument_subtype !== 'security_fire_control_panel',
    },
    {
      name: 'shs_terminal_voltage_v',
      label: 'Напряжение на клеммах для подключения ШС, В',
      type: 'voltage_range',
      hidden: (specs) => specs?.instrument_subtype !== 'security_fire_control_panel',
    },
    {
      name: 'standby_current_a',
      label: 'Токопотребление в дежурном режиме, А',
      type: 'number',
      min: '0',
      step: '0.000001',
      hidden: (specs) => !['security_fire_control_panel', 'indication_unit'].includes(specs?.instrument_subtype),
    },
    {
      name: 'alarm_current_a',
      label: 'Токопотребление в режиме "Пожар", А',
      type: 'number',
      min: '0',
      step: '0.000001',
      hidden: (specs) => !['security_fire_control_panel', 'indication_unit'].includes(specs?.instrument_subtype),
    },
    {
      name: 'connected_instruments_count',
      label: 'Кол-во подключаемых приборов',
      type: 'number',
      min: '0',
      step: '1',
      hidden: (specs) => specs?.instrument_subtype !== 'control_and_management_console',
    },
    {
      name: 'sections_count',
      label: 'Кол-во разделов',
      type: 'number',
      min: '0',
      step: '1',
      hidden: (specs) => specs?.instrument_subtype !== 'control_and_management_console',
    },
    {
      name: 'section_groups_count',
      label: 'Кол-во групп разделов',
      type: 'number',
      min: '0',
      step: '1',
      hidden: (specs) => specs?.instrument_subtype !== 'control_and_management_console',
    },
    {
      name: 'supply_voltage_v',
      label: 'Напряжение, В',
      type: 'voltage_range',
      hidden: (specs) => !['control_and_management_console', 'indication_unit'].includes(specs?.instrument_subtype),
    },
    {
      name: 'current_12v_a',
      label: 'Токопотребление 12В, А',
      type: 'number',
      min: '0',
      step: '0.000001',
      hidden: (specs) => specs?.instrument_subtype !== 'control_and_management_console',
    },
    {
      name: 'current_24v_a',
      label: 'Токопотребление 24В, А',
      type: 'number',
      min: '0',
      step: '0.000001',
      hidden: (specs) => specs?.instrument_subtype !== 'control_and_management_console',
    },
  ],
  keyboard: [],
  speech: [],
  battery: [],
  mounting: [
    { name: 'pack_quantity', label: '\u041a\u043e\u043b-\u0432\u043e \u0448\u0442\u0443\u043a \u0432 \u043f\u0430\u0447\u043a\u0435, \u0448\u0442', type: 'number', min: '1', step: '1' },
    { name: 'mounting_spacing_m', label: '\u041a\u0440\u0430\u0442\u043d\u043e\u0441\u0442\u044c \u043a\u0440\u0435\u043f\u043b\u0435\u043d\u0438\u044f, \u043c', type: 'number', min: '0.1', step: '0.1' },
  ],
  other: [],
};

function toInputValue(value) {
  if (value === null || value === undefined) {
    return '';
  }
  return String(value);
}

function createVoltageRangeDraft(value) {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    return {
      min: toInputValue(value.min),
      max: toInputValue(value.max),
    };
  }
  return {
    min: toInputValue(value),
    max: '',
  };
}

function formatNumericValue(value, { precision } = {}) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return '—';
  }
  if (precision !== undefined) {
    return numeric
      .toFixed(precision)
      .replace(/(\.\d*?[1-9])0+$/u, '$1')
      .replace(/\.0+$/u, '');
  }
  return NUMBER_FORMATTER.format(numeric);
}

function formatVoltageValue(value) {
  if (value === null || value === undefined || value === '') {
    return '—';
  }
  if (typeof value === 'object' && !Array.isArray(value)) {
    const minValue = value.min;
    const maxValue = value.max;
    if (minValue === null || minValue === undefined || minValue === '') {
      return formatNumericValue(maxValue);
    }
    if (maxValue === null || maxValue === undefined || maxValue === '') {
      return formatNumericValue(minValue);
    }
    return `${formatNumericValue(minValue)} - ${formatNumericValue(maxValue)}`;
  }
  return formatNumericValue(value);
}

function formatFieldValue(field, value) {
  if (value === null || value === undefined || value === '') {
    return '—';
  }
  if (field.type === 'select') {
    return field.options.find((option) => option.value === value)?.label || value;
  }
  if (field.type === 'voltage_range') {
    return formatVoltageValue(value);
  }
  if (field.type === 'number') {
    return formatNumericValue(value, {
      precision: CURRENT_FIELD_NAMES.has(field.name) ? 6 : undefined,
    });
  }
  return String(value);
}

function buildVoltagePayload(rangeDraft) {
  const minValue = rangeDraft?.min?.trim?.() ?? '';
  const maxValue = rangeDraft?.max?.trim?.() ?? '';
  if (!minValue && !maxValue) {
    return null;
  }
  if (minValue && maxValue) {
    const minNumeric = Number(minValue);
    const maxNumeric = Number(maxValue);
    if (minNumeric === maxNumeric) {
      return minNumeric;
    }
    return { min: minNumeric, max: maxNumeric };
  }
  return Number(minValue || maxValue);
}

export function getSpecFieldDefinitions(category, specs = {}) {
  return (CATEGORY_SPEC_FIELDS[category] || []).filter((field) => {
    if (typeof field.hidden === 'function') {
      return !field.hidden(specs);
    }
    return true;
  });
}

export function createDefaultSpecs(category) {
  return Object.fromEntries(
    (CATEGORY_SPEC_FIELDS[category] || []).map((field) => {
      if (field.type === 'voltage_range') {
        return [field.name, createVoltageRangeDraft(null)];
      }
      return [field.name, toInputValue(field.defaultValue ?? '')];
    }),
  );
}

export function normalizeSpecsDraft(category, specs) {
  const defaults = createDefaultSpecs(category);
  const rawSpecs = specs && typeof specs === 'object' ? specs : {};
  Object.entries(defaults).forEach(([fieldName]) => {
    const definition = (CATEGORY_SPEC_FIELDS[category] || []).find((field) => field.name === fieldName);
    if (definition?.type === 'voltage_range') {
      defaults[fieldName] = createVoltageRangeDraft(rawSpecs[fieldName]);
      return;
    }
    defaults[fieldName] = toInputValue(
      rawSpecs[fieldName] === undefined ? definition?.defaultValue ?? defaults[fieldName] : rawSpecs[fieldName],
    );
  });
  return defaults;
}

export function buildSpecsPayload(category, specsDraft) {
  const result = {};
  const fields = CATEGORY_SPEC_FIELDS[category] || [];
  fields.forEach((field) => {
    if (typeof field.hidden === 'function' && field.hidden(specsDraft || {})) {
      return;
    }
    const rawValue = specsDraft?.[field.name];
    if (field.type === 'voltage_range') {
      const voltageValue = buildVoltagePayload(rawValue);
      if (voltageValue !== null) {
        result[field.name] = voltageValue;
      }
      return;
    }
    if (rawValue === null || rawValue === undefined || rawValue === '') {
      return;
    }
    if (field.type === 'number') {
      result[field.name] = Number(rawValue);
      return;
    }
    const normalized = String(rawValue).trim();
    if (!normalized) {
      return;
    }
    result[field.name] = normalized;
  });

  if (
    category === 'instrument'
    && ['security_fire_control_panel', 'indication_unit'].includes(result.instrument_subtype)
    && Object.prototype.hasOwnProperty.call(result, 'standby_current_a')
    && !Object.prototype.hasOwnProperty.call(result, 'alarm_current_a')
  ) {
    result.alarm_current_a = result.standby_current_a;
  }
  if (
    category !== 'instrument'
    && Object.prototype.hasOwnProperty.call(result, 'standby_current_a')
    && !Object.prototype.hasOwnProperty.call(result, 'alarm_current_a')
  ) {
    result.alarm_current_a = result.standby_current_a;
  }
  return result;
}

export function getAddressingModeLabel(value) {
  return ADDRESSING_OPTIONS.find((option) => option.value === value)?.label || value || '';
}

export function isAddressedDetectorCategory(category) {
  return ADDRESSED_DETECTOR_CATEGORIES.has(String(category || ''));
}

export function getEquipmentSpecEntries(category, specs) {
  return getSpecFieldDefinitions(category, specs).map((field) => ({
    key: field.name,
    label: field.label,
    value: formatFieldValue(field, specs?.[field.name]),
    hasValue: !(
      specs?.[field.name] === null
      || specs?.[field.name] === undefined
      || specs?.[field.name] === ''
    ),
  }));
}
