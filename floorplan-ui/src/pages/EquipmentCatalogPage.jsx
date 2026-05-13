import React, { useCallback, useEffect, useMemo, useState } from 'react';

import { equipmentApi } from '../api/client';
import { useDialogs } from '../ui/DialogProvider';
import FileDropField from '../ui/FileDropField';
import {
  buildEquipmentAssetUrl,
  EQUIPMENT_CATEGORY_OPTIONS,
  formatEquipmentPrice,
  getEquipmentCategoryLabel,
} from './equipmentCatalog/constants';
import {
  buildSpecsPayload,
  createDefaultSpecs,
  getAddressingModeLabel,
  getEquipmentSpecEntries,
  getSpecFieldDefinitions,
  isAddressedDetectorCategory,
  normalizeSpecsDraft,
} from './equipmentCatalog/specs';

function createEmptyEquipmentDraft(category = 'linear') {
  return {
    id: null,
    name: '',
    category,
    description: '',
    price: '',
    manufacturer: '',
    service_life_years: '',
    notes: '',
    specs: createDefaultSpecs(category),
    compatible_equipment_ids: [],
    image_path: null,
    connection_diagram_path: null,
    label_pdf_path: null,
    manual_pdf_path: null,
    image_url: null,
    connection_diagram_url: null,
    label_pdf_url: null,
    manual_pdf_url: null,
  };
}

function draftFromItem(item) {
  const category = item.category ?? 'linear';
  return {
    id: item.id,
    name: item.name ?? '',
    category,
    description: item.description ?? '',
    price: item.price === null || item.price === undefined ? '' : Number(item.price).toFixed(2),
    manufacturer: item.manufacturer ?? '',
    service_life_years: item.service_life_years === null || item.service_life_years === undefined
      ? ''
      : String(item.service_life_years),
    notes: item.notes ?? '',
    specs: normalizeSpecsDraft(category, item.specs || {}),
    compatible_equipment_ids: (item.compatible_equipment_ids || []).map((value) => String(value)),
    image_path: item.image_path ?? null,
    connection_diagram_path: item.connection_diagram_path ?? null,
    label_pdf_path: item.label_pdf_path ?? null,
    manual_pdf_path: item.manual_pdf_path ?? null,
    image_url: item.image_url ?? null,
    connection_diagram_url: item.connection_diagram_url ?? null,
    label_pdf_url: item.label_pdf_url ?? null,
    manual_pdf_url: item.manual_pdf_url ?? null,
  };
}

function buildEquipmentPayload(draft) {
  return {
    name: draft.name.trim(),
    category: draft.category,
    description: draft.description.trim() || null,
    price: draft.price === '' ? null : Number(Number(draft.price).toFixed(2)),
    manufacturer: draft.manufacturer.trim() || null,
    service_life_years: draft.service_life_years === '' ? null : Number(draft.service_life_years),
    notes: draft.notes.trim() || null,
    specs: buildSpecsPayload(draft.category, draft.specs),
    compatible_equipment_ids: (draft.compatible_equipment_ids || []).map((value) => Number(value)),
  };
}

function getAssetName(assetPath) {
  if (!assetPath) {
    return '';
  }
  const normalized = String(assetPath)
    .split(/[?#]/u)[0]
    .split('/')
    .filter(Boolean);
  return normalized[normalized.length - 1] || assetPath;
}

const DOCUMENT_ACCEPT = 'application/pdf,.pdf,image/jpeg,.jpg,.jpeg';
const CONNECTION_DIAGRAM_ACCEPT = 'image/*';
const CONNECTION_DIAGRAM_CATEGORIES = new Set([
  'linear',
  'smoke',
  'heat',
  'manual',
  'siren',
  'exit_sign',
  'speech',
  'instrument',
  'keyboard',
]);

function supportsConnectionDiagram(category) {
  return CONNECTION_DIAGRAM_CATEGORIES.has(category);
}

function getCompatibleEquipmentNames(item, equipmentItems) {
  return (item?.compatible_equipment_ids || []).map((id) => (
    equipmentItems.find((equipment) => equipment.id === id)?.name || `#${id}`
  ));
}

function getCompatibleEquipmentItems(selectedIds, equipmentItems) {
  return (selectedIds || []).map((id) => {
    const numericId = Number(id);
    return equipmentItems.find((equipment) => equipment.id === numericId) || {
      id: numericId,
      name: `#${numericId}`,
      category: 'other',
    };
  });
}

function resolveEquipmentAssetUrl(assetUrl, assetPath) {
  return buildEquipmentAssetUrl(assetUrl || assetPath);
}

function EquipmentAssetField({
  label,
  accept,
  pendingFile,
  savedPath,
  savedUrl,
  onChange,
  className = '',
}) {
  const assetUrl = resolveEquipmentAssetUrl(savedUrl, savedPath);
  const displayName = pendingFile?.name || getAssetName(savedPath) || 'Файл не выбран';

  return (
    <div className={`equipment-upload-field${className ? ` ${className}` : ''}`}>
      <div className="equipment-upload-field__label">{label}</div>
      <div className="equipment-upload-field__actions">
        <FileDropField
          className="equipment-upload-field__dropzone"
          compact
          accept={accept}
          title={label}
          description={pendingFile || savedPath ? 'Перетащите новый файл или кликните для замены.' : 'Перетащите файл или выберите его вручную.'}
          buttonLabel={pendingFile || savedPath ? 'Заменить файл' : 'Выбрать файл'}
          onSelect={onChange}
        />
        {assetUrl && (
          <a className="btn btn-secondary" href={assetUrl} target="_blank" rel="noreferrer">
            Открыть
          </a>
        )}
      </div>
      <div className="equipment-helper-text">{displayName}</div>
    </div>
  );
}

// Legacy pdf-only preview kept temporarily while assets migrate to mixed pdf/jpg rendering.
// eslint-disable-next-line no-unused-vars
function EquipmentPdfPreview({ label, assetPath }) {
  const assetUrl = buildEquipmentAssetUrl(assetPath);
  const previewUrl = assetUrl ? `${assetUrl}#toolbar=1&navpanes=0&scrollbar=1&view=FitH` : null;

  return (
    <div className="equipment-document-preview">
      <div className="equipment-document-preview__header">
        <span>{label}</span>
        {assetUrl && (
          <a className="btn btn-secondary" href={assetUrl} target="_blank" rel="noreferrer">
            Открыть PDF
          </a>
        )}
      </div>
      {previewUrl ? (
        <object
          aria-label={`Предпросмотр PDF: ${label}`}
          className="equipment-document-preview__frame"
          data={previewUrl}
          type="application/pdf"
        >
          <iframe
            className="equipment-document-preview__frame"
            src={previewUrl}
            title={`Предпросмотр PDF: ${label}`}
          />
        </object>
      ) : (
        <div className="equipment-document-preview__empty">PDF пока не загружен</div>
      )}
    </div>
  );
}

function EquipmentAssetLinkCard({ label, assetPath, assetUrl: persistedUrl, emptyText = 'Файл пока не загружен' }) {
  const assetUrl = resolveEquipmentAssetUrl(persistedUrl, assetPath);
  const assetName = getAssetName(assetPath);

  return (
    <div className="equipment-document-preview">
      <div className="equipment-document-preview__header">
        <span>{label}</span>
        {assetUrl && (
          <a className="btn btn-secondary" href={assetUrl} target="_blank" rel="noreferrer">
            Открыть
          </a>
        )}
      </div>
      {assetUrl ? (
        <div className="equipment-view-assets__row">
          <strong>{assetName || 'Файл загружен'}</strong>
        </div>
      ) : (
        <div className="equipment-document-preview__empty">{emptyText}</div>
      )}
    </div>
  );
}

function CompatibleEquipmentSelector({
  options,
  selectedIds,
  onAdd,
  onRemove,
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');

  const selectedSet = useMemo(
    () => new Set((selectedIds || []).map((value) => String(value))),
    [selectedIds],
  );

  const filteredOptions = useMemo(() => {
    const normalizedQuery = searchTerm.trim().toLowerCase();
    return options.filter((item) => {
      if (selectedSet.has(String(item.id))) {
        return false;
      }
      if (!normalizedQuery) {
        return true;
      }
      return `${item.name} ${item.manufacturer || ''}`.toLowerCase().includes(normalizedQuery);
    });
  }, [options, searchTerm, selectedSet]);

  const selectedItems = useMemo(
    () => getCompatibleEquipmentItems(selectedIds, options),
    [options, selectedIds],
  );

  return (
    <div className="equipment-compatibility-picker">
      <div className="equipment-compatibility-picker__header">
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => setIsOpen((prev) => !prev)}
        >
          + Добавить совместимое оборудование
        </button>
      </div>

      {selectedItems.length > 0 ? (
        <div className="equipment-chip-list">
          {selectedItems.map((item) => (
            <div key={item.id} className="equipment-chip">
              <span>{item.name}</span>
              <button
                type="button"
                className="equipment-chip__remove"
                onClick={() => onRemove(String(item.id))}
                aria-label={`Убрать ${item.name}`}
              >
                ×
              </button>
            </div>
          ))}
        </div>
      ) : (
        <div className="equipment-form__hint">
          Пока не выбрано совместимое оборудование.
        </div>
      )}

      {isOpen && (
        <div className="equipment-compatibility-picker__popover">
          <label className="equipment-compatibility-picker__search">
            Поиск
            <input
              type="text"
              value={searchTerm}
              onChange={(event) => setSearchTerm(event.target.value)}
              placeholder="Название или производитель"
            />
          </label>
          <div className="equipment-compatibility-picker__list" role="listbox" aria-label="Оборудование в системе">
            {filteredOptions.length > 0 ? (
              filteredOptions.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className="equipment-compatibility-picker__option"
                  onClick={() => {
                    onAdd(String(item.id));
                    setIsOpen(false);
                    setSearchTerm('');
                  }}
                >
                  <strong>{item.name}</strong>
                  <span>{getEquipmentCategoryLabel(item.category)}</span>
                  <small>{item.manufacturer || 'Без производителя'}</small>
                </button>
              ))
            ) : (
              <div className="equipment-compatibility-picker__empty">
                Нет доступных карточек для добавления.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function EquipmentSpecFields({ category, specs, onChange }) {
  const fields = getSpecFieldDefinitions(category, specs);

  if (fields.length === 0) {
    return (
      <div className="equipment-spec-panel equipment-form__full-width">
        <div className="equipment-spec-panel__header">Параметры</div>
        <div className="equipment-form__hint">
          Для этой категории пока используются только общие поля карточки.
        </div>
      </div>
    );
  }

  return (
    <div className="equipment-spec-panel equipment-form__full-width">
      <div className="equipment-spec-panel__header">Параметры</div>
      <div className="equipment-spec-grid">
        {fields.map((field) => {
          if (field.type === 'voltage_range') {
            return (
              <div key={field.name} className="equipment-spec-field">
                <span>{field.label}</span>
                <div className="equipment-range-input">
                  <input
                    aria-label={`${field.label} от`}
                    type="number"
                    min="0"
                    step="0.01"
                    placeholder="От"
                    value={specs?.[field.name]?.min ?? ''}
                    onChange={(event) => onChange(field.name, (previousValue) => ({
                      ...((previousValue && typeof previousValue === 'object') ? previousValue : { min: '', max: '' }),
                      min: event.target.value,
                    }))}
                  />
                  <input
                    aria-label={`${field.label} до`}
                    type="number"
                    min="0"
                    step="0.01"
                    placeholder="До"
                    value={specs?.[field.name]?.max ?? ''}
                    onChange={(event) => onChange(field.name, (previousValue) => ({
                      ...((previousValue && typeof previousValue === 'object') ? previousValue : { min: '', max: '' }),
                      max: event.target.value,
                    }))}
                  />
                </div>
              </div>
            );
          }

          return (
            <label key={field.name}>
              {field.label}
              {field.type === 'select' ? (
                <select
                  aria-label={field.label}
                  value={specs?.[field.name] ?? ''}
                  onChange={(event) => onChange(field.name, event.target.value)}
                >
                  <option value="">Не указано</option>
                  {field.options.map((option) => (
                    <option key={option.value} value={option.value}>{option.label}</option>
                  ))}
                </select>
              ) : field.type === 'text' ? (
                <input
                  aria-label={field.label}
                  type="text"
                  value={specs?.[field.name] ?? ''}
                  onChange={(event) => onChange(field.name, event.target.value)}
                />
              ) : (
                <input
                  aria-label={field.label}
                  type="number"
                  min={field.min}
                  step={field.step}
                  value={specs?.[field.name] ?? ''}
                  onChange={(event) => onChange(field.name, event.target.value)}
                />
              )}
            </label>
          );
        })}
      </div>
    </div>
  );
}

function EquipmentSpecSummary({ category, specs }) {
  const entries = getEquipmentSpecEntries(category, specs).filter((entry) => entry.hasValue);

  if (entries.length === 0) {
    return null;
  }

  return (
    <div className="equipment-spec-list">
      {entries.map((entry) => (
        <div key={entry.key} className="equipment-spec-list__row">
          <span>{entry.label}</span>
          <strong>{entry.value}</strong>
        </div>
      ))}
    </div>
  );
}

export default function EquipmentCatalogPage() {
  const { confirm } = useDialogs();
  const [equipmentItems, setEquipmentItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [activeCategory, setActiveCategory] = useState(null);
  const [modalState, setModalState] = useState({ isOpen: false, mode: 'view', itemId: null });
  const [equipmentDraft, setEquipmentDraft] = useState(createEmptyEquipmentDraft());
  const [pendingImageFile, setPendingImageFile] = useState(null);
  const [pendingConnectionDiagramFile, setPendingConnectionDiagramFile] = useState(null);
  const [pendingLabelFile, setPendingLabelFile] = useState(null);
  const [pendingManualFile, setPendingManualFile] = useState(null);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [modalError, setModalError] = useState('');

  const loadEquipmentItems = useCallback(async () => {
    setLoading(true);
    setLoadError('');
    try {
      const data = await equipmentApi.list();
      setEquipmentItems(data);
    } catch (error) {
      console.error('Error loading equipment catalog:', error);
      setLoadError(`Не удалось загрузить оборудование: ${error.message}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadEquipmentItems();
  }, [loadEquipmentItems]);

  const filteredItems = useMemo(() => (
    activeCategory
      ? equipmentItems.filter((item) => item.category === activeCategory)
      : equipmentItems
  ), [activeCategory, equipmentItems]);

  const selectedItem = useMemo(() => (
    modalState.itemId !== null
      ? equipmentItems.find((item) => item.id === modalState.itemId) || null
      : null
  ), [equipmentItems, modalState.itemId]);

  const compatibilityOptions = useMemo(() => (
    equipmentItems.filter((item) => item.id !== equipmentDraft.id)
  ), [equipmentDraft.id, equipmentItems]);

  const resetUploads = () => {
    setPendingImageFile(null);
    setPendingConnectionDiagramFile(null);
    setPendingLabelFile(null);
    setPendingManualFile(null);
  };

  const openCreateModal = () => {
    setModalState({ isOpen: true, mode: 'create', itemId: null });
    setEquipmentDraft(createEmptyEquipmentDraft());
    resetUploads();
    setModalError('');
  };

  const openViewModal = (item) => {
    setModalState({ isOpen: true, mode: 'view', itemId: item.id });
    setEquipmentDraft(draftFromItem(item));
    resetUploads();
    setModalError('');
  };

  const openEditModal = (item) => {
    setModalState({ isOpen: true, mode: 'edit', itemId: item.id });
    setEquipmentDraft(draftFromItem(item));
    resetUploads();
    setModalError('');
  };

  const closeModal = () => {
    setModalState({ isOpen: false, mode: 'view', itemId: null });
    setEquipmentDraft(createEmptyEquipmentDraft());
    resetUploads();
    setModalError('');
  };

  const handleDraftFieldChange = (event) => {
    const { name, value } = event.target;
    setEquipmentDraft((prev) => {
      if (name === 'category') {
        return {
          ...prev,
          category: value,
          specs: createDefaultSpecs(value),
        };
      }
      return {
        ...prev,
        [name]: value,
      };
    });
    setModalError('');
  };

  const handleSpecFieldChange = (fieldName, value) => {
    setEquipmentDraft((prev) => ({
      ...prev,
      specs: {
        ...prev.specs,
        [fieldName]: typeof value === 'function' ? value(prev.specs?.[fieldName]) : value,
      },
    }));
    setModalError('');
  };

  const handleCompatibilityAdd = (value) => {
    setEquipmentDraft((prev) => {
      if (prev.compatible_equipment_ids.includes(value)) {
        return prev;
      }
      return {
        ...prev,
        compatible_equipment_ids: [...prev.compatible_equipment_ids, value],
      };
    });
    setModalError('');
  };

  const handleCompatibilityRemove = (value) => {
    setEquipmentDraft((prev) => ({
      ...prev,
      compatible_equipment_ids: prev.compatible_equipment_ids.filter((itemId) => itemId !== value),
    }));
    setModalError('');
  };

  const handleSaveEquipment = async () => {
    setSaving(true);
    setModalError('');
    try {
      const payload = buildEquipmentPayload(equipmentDraft);
      let savedItem = equipmentDraft.id
        ? await equipmentApi.update(equipmentDraft.id, payload)
        : await equipmentApi.create(payload);

      if (pendingImageFile) {
        savedItem = await equipmentApi.uploadImage(savedItem.id, pendingImageFile);
      }
      if (pendingConnectionDiagramFile && supportsConnectionDiagram(savedItem.category)) {
        savedItem = await equipmentApi.uploadConnectionDiagram(savedItem.id, pendingConnectionDiagramFile);
      }
      if (pendingLabelFile) {
        savedItem = await equipmentApi.uploadLabelPdf(savedItem.id, pendingLabelFile);
      }
      if (pendingManualFile) {
        savedItem = await equipmentApi.uploadManualPdf(savedItem.id, pendingManualFile);
      }

      await loadEquipmentItems();
      setModalState({ isOpen: true, mode: 'view', itemId: savedItem.id });
      setEquipmentDraft(draftFromItem(savedItem));
      resetUploads();
    } catch (error) {
      console.error('Error saving equipment item:', error);
      setModalError(`Не удалось сохранить карточку: ${error.message}`);
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteEquipment = async () => {
    if (!selectedItem) {
      return;
    }
    const isConfirmed = await confirm(`Удалить оборудование "${selectedItem.name}"?`, {
      confirmLabel: 'Удалить',
      cancelLabel: 'Отмена',
    });
    if (!isConfirmed) {
      return;
    }

    setDeleting(true);
    setModalError('');
    try {
      await equipmentApi.remove(selectedItem.id);
      await loadEquipmentItems();
      closeModal();
    } catch (error) {
      console.error('Error deleting equipment item:', error);
      setModalError(`Не удалось удалить карточку: ${error.message}`);
    } finally {
      setDeleting(false);
    }
  };

  const modalItem = modalState.mode === 'create' ? null : selectedItem;
  const isEditing = modalState.mode === 'edit' || modalState.mode === 'create';
  const modalTitle = modalState.mode === 'create'
    ? 'Новая карточка оборудования'
    : (modalItem?.name || 'Оборудование');
  const modalImageUrl = pendingImageFile
    ? null
    : resolveEquipmentAssetUrl(
      isEditing ? equipmentDraft.image_url : modalItem?.image_url,
      isEditing ? equipmentDraft.image_path : modalItem?.image_path,
    );
  const modalSpecEntries = getEquipmentSpecEntries(
    modalItem?.category || equipmentDraft.category,
    modalItem?.specs || (isEditing ? buildSpecsPayload(equipmentDraft.category, equipmentDraft.specs) : {}),
  ).filter((entry) => entry.hasValue);
  const compatibleNames = getCompatibleEquipmentNames(modalItem, equipmentItems);
  const showConnectionDiagramField = supportsConnectionDiagram(equipmentDraft.category);
  const showConnectionDiagramAsset = supportsConnectionDiagram(modalItem?.category);

  return (
    <div className="project-list-container equipment-page">
      <div className="project-list-header equipment-page__header">
        <div>
          <h1>Оборудование</h1>
          <p className="equipment-page__subtitle">
            Каталог карточек оборудования для проектов, спецификаций и привязки элементов на плане.
          </p>
        </div>
        <button type="button" className="btn btn-primary" onClick={openCreateModal}>
          Добавить оборудование
        </button>
      </div>

      <div className="equipment-filter-row" role="tablist" aria-label="Фильтр оборудования">
        <button
          type="button"
          className={`equipment-filter-chip ${activeCategory === null ? 'equipment-filter-chip--active' : ''}`}
          onClick={() => setActiveCategory(null)}
        >
          Все
        </button>
        {EQUIPMENT_CATEGORY_OPTIONS.map((option) => (
          <button
            key={option.key}
            type="button"
            className={`equipment-filter-chip ${activeCategory === option.key ? 'equipment-filter-chip--active' : ''}`}
            onClick={() => setActiveCategory(option.key)}
          >
            {option.label}
          </button>
        ))}
      </div>

      {loading && <div className="loading">Загрузка оборудования...</div>}
      {loadError && <div className="equipment-inline-error">{loadError}</div>}

      {!loading && !loadError && filteredItems.length === 0 && (
        <div className="equipment-empty-state">
          Пока нет карточек оборудования для выбранного фильтра.
        </div>
      )}

      {!loading && !loadError && filteredItems.length > 0 && (
        <div className="equipment-grid equipment-grid--compact">
          {filteredItems.map((item) => (
            <button
              key={item.id}
              type="button"
              className="equipment-card equipment-card--compact"
              onClick={() => openViewModal(item)}
            >
              <div className="equipment-card__body equipment-card__body--compact">
                <h3>{item.name}</h3>
                {activeCategory === null && (
                  <div className="equipment-card__meta">{getEquipmentCategoryLabel(item.category)}</div>
                )}
                {activeCategory !== null && isAddressedDetectorCategory(item.category) && item.specs?.addressing_mode && (
                  <div className="equipment-card__meta">{getAddressingModeLabel(item.specs.addressing_mode)}</div>
                )}
                <div className="equipment-card__row">
                  <span>Производитель</span>
                  <strong>{item.manufacturer || '—'}</strong>
                </div>
                <div className="equipment-card__row">
                  <span>Цена</span>
                  <strong>{formatEquipmentPrice(item.price)} ₽</strong>
                </div>
              </div>
            </button>
          ))}
        </div>
      )}

      {modalState.isOpen && (
        <div className="equipment-modal-backdrop" onClick={closeModal}>
          <div
            className="equipment-modal equipment-modal--large"
            role="dialog"
            aria-modal="true"
            aria-label={modalTitle}
            onClick={(event) => event.stopPropagation()}
          >
            <div className="equipment-modal__header">
              <div>
                <h2>{modalTitle}</h2>
                {!isEditing && modalItem && (
                  <div className="equipment-modal__category">{getEquipmentCategoryLabel(modalItem.category)}</div>
                )}
              </div>
              <button type="button" className="tool-button" onClick={closeModal}>×</button>
            </div>

            {modalError && <div className="equipment-inline-error">{modalError}</div>}

            {isEditing ? (
              <div className="equipment-modal__content equipment-modal__content--large">
                <div className="equipment-modal__image-panel">
                  {modalImageUrl ? (
                    <img src={modalImageUrl} alt={equipmentDraft.name || 'Изображение оборудования'} className="equipment-modal__image equipment-modal__image--large" />
                  ) : (
                    <div className="equipment-modal__image equipment-modal__image--large equipment-modal__image--placeholder">Пока без изображения</div>
                  )}
                  <div className="equipment-modal__asset-grid">
                    <EquipmentAssetField
                      label="Изображение"
                      className="equipment-upload-field--image"
                      accept="image/*"
                      pendingFile={pendingImageFile}
                      savedPath={equipmentDraft.image_path}
                      savedUrl={equipmentDraft.image_url}
                      onChange={setPendingImageFile}
                    />
                    {showConnectionDiagramField && (
                      <EquipmentAssetField
                        label="Схема подключения"
                        className="equipment-upload-field--connection-diagram"
                        accept={CONNECTION_DIAGRAM_ACCEPT}
                        pendingFile={pendingConnectionDiagramFile}
                        savedPath={equipmentDraft.connection_diagram_path}
                        savedUrl={equipmentDraft.connection_diagram_url}
                        onChange={setPendingConnectionDiagramFile}
                      />
                    )}
                    <EquipmentAssetField
                      label="Этикетка"
                      className="equipment-upload-field--label"
                      accept={DOCUMENT_ACCEPT}
                      pendingFile={pendingLabelFile}
                      savedPath={equipmentDraft.label_pdf_path}
                      savedUrl={equipmentDraft.label_pdf_url}
                      onChange={setPendingLabelFile}
                    />
                    <EquipmentAssetField
                      label="Руководство"
                      className="equipment-upload-field--manual"
                      accept={DOCUMENT_ACCEPT}
                      pendingFile={pendingManualFile}
                      savedPath={equipmentDraft.manual_pdf_path}
                      savedUrl={equipmentDraft.manual_pdf_url}
                      onChange={setPendingManualFile}
                    />
                  </div>
                </div>

                <div className="equipment-form equipment-form--large">
                  <label>
                    Название
                    <input type="text" name="name" value={equipmentDraft.name} onChange={handleDraftFieldChange} />
                  </label>
                  <label>
                    Тип
                    <select name="category" value={equipmentDraft.category} onChange={handleDraftFieldChange}>
                      {EQUIPMENT_CATEGORY_OPTIONS.map((option) => (
                        <option key={option.key} value={option.key}>{option.label}</option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Цена
                    <input type="number" min="0" step="0.01" name="price" value={equipmentDraft.price} onChange={handleDraftFieldChange} />
                  </label>
                  <label>
                    Производитель
                    <input type="text" name="manufacturer" value={equipmentDraft.manufacturer} onChange={handleDraftFieldChange} />
                  </label>
                  <label>
                    Срок службы, лет
                    <input type="number" min="0" step="1" name="service_life_years" value={equipmentDraft.service_life_years} onChange={handleDraftFieldChange} />
                  </label>
                  <label className="equipment-form__full-width">
                    Описание изделия
                    <textarea rows="4" name="description" value={equipmentDraft.description} onChange={handleDraftFieldChange} />
                  </label>
                  <div className="equipment-form__full-width project-equipment-role">
                    <span>Совместимое оборудование</span>
                    <CompatibleEquipmentSelector
                      options={compatibilityOptions}
                      selectedIds={equipmentDraft.compatible_equipment_ids}
                      onAdd={handleCompatibilityAdd}
                      onRemove={handleCompatibilityRemove}
                    />
                  </div>
                  <label className="equipment-form__full-width">
                    Примечания
                    <textarea rows="4" name="notes" value={equipmentDraft.notes} onChange={handleDraftFieldChange} />
                  </label>
                  <EquipmentSpecFields
                    category={equipmentDraft.category}
                    specs={equipmentDraft.specs}
                    onChange={handleSpecFieldChange}
                  />
                </div>
              </div>
            ) : (
              <div className="equipment-modal__content equipment-modal__content--large">
                <div className="equipment-modal__image-panel">
                  {modalImageUrl ? (
                    <img src={modalImageUrl} alt={modalItem?.name || 'Изображение оборудования'} className="equipment-modal__image equipment-modal__image--large" />
                  ) : (
                    <div className="equipment-modal__image equipment-modal__image--large equipment-modal__image--placeholder">Пока без изображения</div>
                  )}
                  <div className="equipment-document-grid">
                    {showConnectionDiagramAsset && (
                      <EquipmentAssetLinkCard
                        label="Схема подключения"
                        assetPath={modalItem?.connection_diagram_path}
                        assetUrl={modalItem?.connection_diagram_url}
                        emptyText="Схема подключения пока не загружена"
                      />
                    )}
                    <EquipmentAssetLinkCard label="Этикетка" assetPath={modalItem?.label_pdf_path} assetUrl={modalItem?.label_pdf_url} />
                    <EquipmentAssetLinkCard label="Руководство" assetPath={modalItem?.manual_pdf_path} assetUrl={modalItem?.manual_pdf_url} />
                  </div>
                </div>
                <div className="equipment-detail-grid equipment-detail-grid--large">
                  <div><span>Тип</span><strong>{modalItem ? getEquipmentCategoryLabel(modalItem.category) : '—'}</strong></div>
                  <div><span>Цена</span><strong>{formatEquipmentPrice(modalItem?.price)} ₽</strong></div>
                  <div><span>Производитель</span><strong>{modalItem?.manufacturer || '—'}</strong></div>
                  <div><span>Срок службы</span><strong>{modalItem?.service_life_years ? `${modalItem.service_life_years} лет` : '—'}</strong></div>
                  <div className="equipment-detail-grid__full-width">
                    <span>Описание изделия</span>
                    <strong>{modalItem?.description || '—'}</strong>
                  </div>
                  <div className="equipment-detail-grid__full-width">
                    <span>Совместимое оборудование</span>
                    <strong>{compatibleNames.length > 0 ? compatibleNames.join(', ') : '—'}</strong>
                  </div>
                  <div className="equipment-detail-grid__full-width">
                    <span>Примечания</span>
                    <strong>{modalItem?.notes || '—'}</strong>
                  </div>
                  {modalSpecEntries.length > 0 && (
                    <div className="equipment-detail-grid__full-width">
                      <span>Параметры</span>
                      <EquipmentSpecSummary category={modalItem?.category} specs={modalItem?.specs || {}} />
                    </div>
                  )}
                </div>
              </div>
            )}

            <div className="equipment-modal__footer">
              {isEditing ? (
                <>
                  <button type="button" className="btn btn-primary" onClick={handleSaveEquipment} disabled={saving}>
                    {saving ? 'Сохранение...' : 'Сохранить'}
                  </button>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => {
                      if (modalState.mode === 'create') {
                        closeModal();
                      } else if (selectedItem) {
                        openViewModal(selectedItem);
                      }
                    }}
                    disabled={saving}
                  >
                    Отмена
                  </button>
                </>
              ) : (
                <>
                  <button type="button" className="btn btn-primary" onClick={() => selectedItem && openEditModal(selectedItem)}>
                    Редактировать
                  </button>
                  <button type="button" className="btn btn-danger" onClick={handleDeleteEquipment} disabled={deleting}>
                    {deleting ? 'Удаление...' : 'Удалить'}
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
