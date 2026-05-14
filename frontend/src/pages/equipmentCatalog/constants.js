const EQUIPMENT_CATEGORY_LABELS = {
  linear: 'Линейные',
  smoke: 'Дымовые',
  heat: 'Тепловые',
  manual: 'Ручные',
  siren: 'Сирены',
  exit_sign: 'Табло',
  speech: 'Речевое',
  instrument: 'Приборы',
  keyboard: 'Клавиатуры',
  cable: 'Кабели',
  battery: 'Аккумуляторы',
  mounting: 'Крепления',
  other: 'Другое',
};

export const EQUIPMENT_CATEGORY_OPTIONS = [
  { key: 'linear', label: EQUIPMENT_CATEGORY_LABELS.linear },
  { key: 'smoke', label: EQUIPMENT_CATEGORY_LABELS.smoke },
  { key: 'heat', label: EQUIPMENT_CATEGORY_LABELS.heat },
  { key: 'manual', label: EQUIPMENT_CATEGORY_LABELS.manual },
  { key: 'siren', label: EQUIPMENT_CATEGORY_LABELS.siren },
  { key: 'exit_sign', label: EQUIPMENT_CATEGORY_LABELS.exit_sign },
  { key: 'speech', label: EQUIPMENT_CATEGORY_LABELS.speech },
  { key: 'instrument', label: EQUIPMENT_CATEGORY_LABELS.instrument },
  { key: 'cable', label: EQUIPMENT_CATEGORY_LABELS.cable },
  { key: 'battery', label: EQUIPMENT_CATEGORY_LABELS.battery },
  { key: 'mounting', label: EQUIPMENT_CATEGORY_LABELS.mounting },
  { key: 'other', label: EQUIPMENT_CATEGORY_LABELS.other },
];

export const PROJECT_EQUIPMENT_GROUPS = [
  {
    key: 'sps',
    label: 'СПС',
    categories: ['linear', 'smoke', 'heat', 'manual', 'cable'],
    description: 'Извещатели и связанные кабельные позиции для системы пожарной сигнализации.',
  },
  {
    key: 'soue',
    label: 'СОУЭ',
    categories: ['siren', 'exit_sign', 'speech', 'cable'],
    description: 'Оповещатели, табло, речевые устройства и кабельные позиции СОУЭ.',
  },
  {
    key: 'instruments',
    label: 'Приборы',
    categories: ['instrument', 'keyboard'],
    description: 'ППКП, контроллеры, клавиатуры и другие приборные позиции.',
  },
  {
    key: 'mounting',
    label: '\u041a\u0440\u0435\u043f\u043b\u0435\u043d\u0438\u044f',
    categories: ['mounting'],
    description: '\u041a\u0440\u0435\u043f\u0435\u0436\u043d\u044b\u0435 \u043a\u043e\u043c\u043f\u043b\u0435\u043a\u0442\u044b \u0434\u043b\u044f \u043c\u043e\u043d\u0442\u0430\u0436\u0430 \u043a\u0430\u0431\u0435\u043b\u044c\u043d\u044b\u0445 \u043b\u0438\u043d\u0438\u0439.',
  },
  {
    key: 'other',
    label: 'Другое',
    categories: ['battery', 'other'],
    description: 'Прочие позиции, которые не относятся к основным подсистемам.',
  },
];

export const PROJECT_EQUIPMENT_GROUP_BY_CATEGORY = PROJECT_EQUIPMENT_GROUPS.reduce((result, group) => {
  group.categories.forEach((category) => {
    result[category] = group.key;
  });
  return result;
}, {});

export const FIRE_ALARM_EQUIPMENT_CATEGORIES = {
  linear_detector: ['linear'],
  smoke_detector: ['smoke'],
  heat_detector: ['heat'],
  manual_call_point: ['manual'],
};

export const SOUE_DEVICE_EQUIPMENT_CATEGORIES = {
  siren: ['siren'],
  exit_sign: ['exit_sign'],
  speech_device: ['speech'],
};

export const SIGNAL_INSTRUMENT_EQUIPMENT_CATEGORIES = {
  control_panel: ['instrument', 'keyboard'],
  loop_controller: ['instrument', 'keyboard'],
  annunciator: ['instrument', 'keyboard'],
};

export function getEquipmentCategoryLabel(categoryKey) {
  return EQUIPMENT_CATEGORY_LABELS[categoryKey] || categoryKey;
}

export function getProjectEquipmentGroup(groupKey) {
  return PROJECT_EQUIPMENT_GROUPS.find((group) => group.key === groupKey) || null;
}

export function getProjectEquipmentGroupForCategory(categoryKey) {
  return getProjectEquipmentGroup(PROJECT_EQUIPMENT_GROUP_BY_CATEGORY[categoryKey] || 'other');
}

export function formatEquipmentPrice(price) {
  if (price === null || price === undefined || price === '') {
    return '—';
  }
  const numeric = Number(price);
  if (!Number.isFinite(numeric)) {
    return '—';
  }
  return numeric.toFixed(2);
}

function getEquipmentAssetBaseOrigin() {
  if (typeof window === 'undefined') {
    return '';
  }
  const { origin, protocol, hostname, port } = window.location;
  if (
    (hostname === 'localhost' || hostname === '127.0.0.1')
    && ['3000', '3001', '5173'].includes(String(port || ''))
  ) {
    return `${protocol}//${hostname}:8000`;
  }
  return origin;
}

export function buildEquipmentAssetUrl(assetPath) {
  if (!assetPath) {
    return null;
  }
  if (/^https?:\/\//i.test(assetPath)) {
    return encodeURI(assetPath);
  }
  const normalizedPath = String(assetPath).replace(/^\/+/, '');
  const baseOrigin = getEquipmentAssetBaseOrigin();
  return encodeURI(baseOrigin ? `${baseOrigin}/${normalizedPath}` : `/${normalizedPath}`);
}

export function buildEquipmentImageUrl(imagePath) {
  return buildEquipmentAssetUrl(imagePath);
}
