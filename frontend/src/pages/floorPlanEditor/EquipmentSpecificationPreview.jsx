import React from 'react';

function getCellClassName(index) {
  if (index === 0 || index === 5 || index === 6 || index === 7) {
    return 'equipment-specification-preview__cell equipment-specification-preview__cell--compact';
  }
  return 'equipment-specification-preview__cell';
}

function EquipmentSpecificationPreview({
  specification,
  loading = false,
  saving = false,
  error = '',
  onPageTitleChange,
  onHeaderChange,
  onSectionTitleChange,
  onCellChange,
  onSave,
  onRefresh,
}) {
  if (loading) {
    return <div className="equipment-specification-preview__placeholder">Загрузка спецификации...</div>;
  }

  if (!specification) {
    return (
      <div className="equipment-specification-preview__placeholder">
        {error || 'Спецификация пока недоступна.'}
      </div>
    );
  }

  return (
    <div className="equipment-specification-preview">
      <div className="equipment-specification-preview__toolbar">
        <div>
          <strong>Предпросмотр листа A3</strong>
          <div className="equipment-specification-preview__toolbar-note">
            Изменения сохраняются на уровне проекта и попадут в PDF.
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
      {specification.warnings?.length ? (
        <div className="equipment-specification-preview__warning">
          <strong>Предупреждения</strong>
          <ul>
            {specification.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="equipment-specification-preview__page">
        <input
          className="equipment-specification-preview__title"
          value={specification.page_title || ''}
          onChange={(event) => onPageTitleChange(event.target.value)}
        />

        <table className="equipment-specification-preview__table">
          <thead>
            <tr>
              {specification.column_headers.map((header, index) => (
                <th key={`header-${index}`}>
                  <textarea
                    value={header || ''}
                    onChange={(event) => onHeaderChange(index, event.target.value)}
                    rows={3}
                  />
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {specification.sections.map((section) => (
              <React.Fragment key={section.key}>
                <tr className="equipment-specification-preview__section-row">
                  <td colSpan={specification.column_headers.length}>
                    <input
                      value={section.title || ''}
                      onChange={(event) => onSectionTitleChange(section.key, event.target.value)}
                    />
                  </td>
                </tr>
                {section.rows.map((row) => (
                  <tr key={row.source_key}>
                    {[
                      row.position,
                      row.technical_name,
                      row.type_mark,
                      row.code,
                      row.manufacturer,
                      row.unit,
                      row.quantity,
                      row.unit_mass_kg,
                      row.note,
                    ].map((value, index) => (
                      <td key={`${row.source_key}-${index}`} className={getCellClassName(index)}>
                        {index === 1 || index === 2 || index === 8 ? (
                          <textarea
                            value={value || ''}
                            onChange={(event) => onCellChange(section.key, row.source_key, index, event.target.value)}
                            rows={3}
                          />
                        ) : (
                          <input
                            value={value || ''}
                            onChange={(event) => onCellChange(section.key, row.source_key, index, event.target.value)}
                          />
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default EquipmentSpecificationPreview;
