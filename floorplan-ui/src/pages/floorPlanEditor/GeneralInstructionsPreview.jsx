import React from 'react';

function GeneralInstructionsPreview({
  instructions,
  loading = false,
  saving = false,
  error = '',
  onTopLevelFieldChange,
  onBlockTextChange,
  onBlockItemsChange,
  onSave,
  onRefresh,
}) {
  if (loading) {
    return <div className="equipment-specification-preview__placeholder">Загрузка общих указаний...</div>;
  }

  if (!instructions) {
    return (
      <div className="equipment-specification-preview__placeholder">
        {error || 'Общие указания пока недоступны.'}
      </div>
    );
  }

  return (
    <div className="equipment-specification-preview general-instructions-preview">
      <div className="equipment-specification-preview__toolbar">
        <div>
          <strong>Предпросмотр листов A4</strong>
          <div className="equipment-specification-preview__toolbar-note">
            Автоматически собранный текст можно отредактировать перед генерацией PDF.
          </div>
        </div>
        <div className="equipment-specification-preview__toolbar-actions">
          <button className="tool-button" type="button" onClick={onRefresh} disabled={loading || saving}>
            Обновить
          </button>
          <button className="tool-button" type="button" onClick={onSave} disabled={saving}>
            {saving ? 'Сохранение...' : 'Сохранить'}
          </button>
        </div>
      </div>

      {error ? <div className="equipment-specification-preview__warning equipment-specification-preview__warning--error">{error}</div> : null}

      <div className="equipment-specification-preview__page additional-info-preview__page">
        <label className="additional-info-preview__field">
          <span>Название листа в основной надписи</span>
          <input
            className="equipment-specification-preview__title"
            aria-label="Название листа общих указаний"
            value={instructions.page_title || ''}
            onChange={(event) => onTopLevelFieldChange('page_title', event.target.value)}
          />
        </label>
        <label className="additional-info-preview__field">
          <span>Заголовок</span>
          <input
            className="additional-info-preview__textarea"
            aria-label="Заголовок общих указаний"
            value={instructions.heading || ''}
            onChange={(event) => onTopLevelFieldChange('heading', event.target.value)}
          />
        </label>
        <label className="additional-info-preview__field">
          <span>Локальное название листа</span>
          <input
            className="additional-info-preview__textarea"
            aria-label="Локальное название листа общих указаний"
            value={instructions.local_sheet_title || ''}
            onChange={(event) => onTopLevelFieldChange('local_sheet_title', event.target.value)}
          />
        </label>
        {(instructions.blocks || []).map((block, index) => (
          <label className="additional-info-preview__field" key={block.key || `block-${index}`}>
            <span>
              {block.kind === 'section_heading'
                ? `Подзаголовок ${index + 1}`
                : block.kind === 'bullet_list'
                  ? `Список ${index + 1}`
                  : `Абзац ${index + 1}`}
            </span>
            {block.kind === 'bullet_list' ? (
              <textarea
                className="additional-info-preview__textarea"
                aria-label={`Блок общих указаний ${block.key || index}`}
                value={(block.items || []).join('\n')}
                onChange={(event) => onBlockItemsChange(block.key, event.target.value)}
                rows={Math.max(4, (block.items || []).length || 1)}
              />
            ) : (
              <textarea
                className="additional-info-preview__textarea"
                aria-label={`Блок общих указаний ${block.key || index}`}
                value={block.text || ''}
                onChange={(event) => onBlockTextChange(block.key, event.target.value)}
                rows={block.kind === 'section_heading' ? 2 : 4}
              />
            )}
          </label>
        ))}
      </div>
    </div>
  );
}

export default GeneralInstructionsPreview;
