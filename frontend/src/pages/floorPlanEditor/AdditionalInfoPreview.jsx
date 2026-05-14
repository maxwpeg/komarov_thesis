import React from 'react';

function AdditionalInfoPreview({
  additionalInfo,
  loading = false,
  saving = false,
  error = '',
  onTextChange,
  onSave,
  onRefresh,
}) {
  if (loading) {
    return <div className="equipment-specification-preview__placeholder">Загрузка доп. сведений...</div>;
  }

  if (!additionalInfo) {
    return (
      <div className="equipment-specification-preview__placeholder">
        {error || 'Доп. сведения пока недоступны.'}
      </div>
    );
  }

  return (
    <div className="equipment-specification-preview additional-info-preview">
      <div className="equipment-specification-preview__toolbar">
        <div>
          <strong>Предпросмотр листа A4</strong>
          <div className="equipment-specification-preview__toolbar-note">
            Необязательный общий этап проекта. Текст попадет в конец PDF и будет разбит на абзацы.
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
        <input
          className="equipment-specification-preview__title"
          aria-label="Заголовок страницы доп. сведений"
          value={additionalInfo.page_title || ''}
          readOnly
        />
        <label className="additional-info-preview__field">
          <span>Текст</span>
          <textarea
            className="additional-info-preview__textarea"
            aria-label="Текст доп. сведений"
            value={additionalInfo.text || ''}
            onChange={(event) => onTextChange(event.target.value)}
            rows={18}
          />
        </label>
      </div>
    </div>
  );
}

export default AdditionalInfoPreview;
