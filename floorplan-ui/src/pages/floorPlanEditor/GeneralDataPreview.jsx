import React from 'react';

function GeneralDataPreview({
  generalData,
  loading = false,
  saving = false,
  error = '',
  onTopLevelFieldChange,
  onDocumentRowFieldChange,
  onManifestRowFieldChange,
  onSave,
  onRefresh,
}) {
  if (loading) {
    return <div className="equipment-specification-preview__placeholder">Загрузка общих данных...</div>;
  }

  if (!generalData) {
    return (
      <div className="equipment-specification-preview__placeholder">
        {error || 'Общие данные пока недоступны.'}
      </div>
    );
  }

  return (
    <div className="equipment-specification-preview general-data-preview">
      <div className="equipment-specification-preview__toolbar">
        <div>
          <strong>Предпросмотр листа A3</strong>
          <div className="equipment-specification-preview__toolbar-note">
            Автоматически собранные таблицы и текст можно скорректировать перед генерацией PDF.
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

      <div className="equipment-specification-preview__page power-consumption-preview__page">
        <div className="power-consumption-preview__meta">
          <label className="power-consumption-preview__field power-consumption-preview__field--wide">
            <span>Название листа</span>
            <input
              aria-label="Название листа общих данных"
              value={generalData.page_title || ''}
              onChange={(event) => onTopLevelFieldChange('page_title', event.target.value)}
            />
          </label>
          <label className="power-consumption-preview__field power-consumption-preview__field--wide">
            <span>Заголовок левой таблицы</span>
            <input
              aria-label="Заголовок левой таблицы общих данных"
              value={generalData.left_table_title || ''}
              onChange={(event) => onTopLevelFieldChange('left_table_title', event.target.value)}
            />
          </label>
          <label className="power-consumption-preview__field power-consumption-preview__field--wide">
            <span>Заголовок правой таблицы</span>
            <input
              aria-label="Заголовок правой таблицы общих данных"
              value={generalData.right_table_title || ''}
              onChange={(event) => onTopLevelFieldChange('right_table_title', event.target.value)}
            />
          </label>
          <label className="power-consumption-preview__field">
            <span>Категория ссылочных документов</span>
            <input
              aria-label="Категория ссылочных документов"
              value={generalData.reference_category_title || ''}
              onChange={(event) => onTopLevelFieldChange('reference_category_title', event.target.value)}
            />
          </label>
          <label className="power-consumption-preview__field">
            <span>Категория прилагаемых документов</span>
            <input
              aria-label="Категория прилагаемых документов"
              value={generalData.attached_category_title || ''}
              onChange={(event) => onTopLevelFieldChange('attached_category_title', event.target.value)}
            />
          </label>
          <label className="power-consumption-preview__field">
            <span>ГИП</span>
            <input
              aria-label="ГИП проекта"
              value={generalData.gip_name || ''}
              onChange={(event) => onTopLevelFieldChange('gip_name', event.target.value)}
            />
          </label>
        </div>

        <table className="equipment-specification-preview__table">
          <thead>
            <tr>
              <th colSpan={3}>Ссылочные документы</th>
            </tr>
            <tr>
              <th>Обозначение</th>
              <th>Наименование</th>
              <th>Примечание</th>
            </tr>
          </thead>
          <tbody>
            {(generalData.reference_documents || []).map((row) => (
              <tr key={row.key}>
                <td>
                  <textarea
                    aria-label={`${row.key}:designation`}
                    rows={2}
                    value={row.designation || ''}
                    onChange={(event) => onDocumentRowFieldChange('reference_documents', row.key, 'designation', event.target.value)}
                  />
                </td>
                <td>
                  <textarea
                    aria-label={`${row.key}:name`}
                    rows={3}
                    value={row.name || ''}
                    onChange={(event) => onDocumentRowFieldChange('reference_documents', row.key, 'name', event.target.value)}
                  />
                </td>
                <td>
                  <textarea
                    aria-label={`${row.key}:note`}
                    rows={2}
                    value={row.note || ''}
                    onChange={(event) => onDocumentRowFieldChange('reference_documents', row.key, 'note', event.target.value)}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        <table className="equipment-specification-preview__table">
          <thead>
            <tr>
              <th colSpan={3}>Прилагаемые документы</th>
            </tr>
            <tr>
              <th>Обозначение</th>
              <th>Наименование</th>
              <th>Примечание</th>
            </tr>
          </thead>
          <tbody>
            {(generalData.attached_documents || []).map((row) => (
              <tr key={row.key}>
                <td>
                  <textarea
                    aria-label={`${row.key}:designation`}
                    rows={2}
                    value={row.designation || ''}
                    onChange={(event) => onDocumentRowFieldChange('attached_documents', row.key, 'designation', event.target.value)}
                  />
                </td>
                <td>
                  <textarea
                    aria-label={`${row.key}:name`}
                    rows={3}
                    value={row.name || ''}
                    onChange={(event) => onDocumentRowFieldChange('attached_documents', row.key, 'name', event.target.value)}
                  />
                </td>
                <td>
                  <textarea
                    aria-label={`${row.key}:note`}
                    rows={2}
                    value={row.note || ''}
                    onChange={(event) => onDocumentRowFieldChange('attached_documents', row.key, 'note', event.target.value)}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        <table className="equipment-specification-preview__table">
          <thead>
            <tr>
              <th>Лист</th>
              <th>Наименование</th>
              <th>Примечание</th>
            </tr>
          </thead>
          <tbody>
            {(generalData.drawing_manifest_rows || []).map((row, index) => (
              <tr key={row.key}>
                <td>{index + 1}</td>
                <td>
                  <textarea
                    aria-label={`${row.key}:manifest-name`}
                    rows={2}
                    value={row.name || ''}
                    onChange={(event) => onManifestRowFieldChange(row.key, 'name', event.target.value)}
                  />
                </td>
                <td>{row.note || ''}</td>
              </tr>
            ))}
          </tbody>
        </table>

        <label className="power-consumption-preview__field power-consumption-preview__field--wide">
          <span>Текст под таблицей</span>
          <textarea
            aria-label="Текст заявления общих данных"
            rows={5}
            value={generalData.statement_text || ''}
            onChange={(event) => onTopLevelFieldChange('statement_text', event.target.value)}
          />
        </label>
      </div>
    </div>
  );
}

export default GeneralDataPreview;
