import React from 'react';

const EDITABLE_SUMMARY_KEYS = new Set(['operation_time', 'correction_factor']);

function PowerConsumptionCalculationPreview({
  calculation,
  loading = false,
  saving = false,
  error = '',
  onTopLevelFieldChange,
  onIntroductoryTextChange,
  onCategoryTitleChange,
  onRowFieldChange,
  onSummaryFieldChange,
  onSave,
  onRefresh,
}) {
  if (loading) {
    return <div className="equipment-specification-preview__placeholder">Загрузка расчета токопотребления...</div>;
  }

  if (!calculation) {
    return (
      <div className="equipment-specification-preview__placeholder">
        {error || 'Расчет токопотребления пока недоступен.'}
      </div>
    );
  }

  return (
    <div className="equipment-specification-preview power-consumption-preview">
      <div className="equipment-specification-preview__toolbar">
        <div>
          <strong>Предпросмотр листа A4</strong>
          <div className="equipment-specification-preview__toolbar-note">
            Изменения сохраняются на уровне проекта и попадают в редактор и PDF после автопересчета.
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
        <input
          className="equipment-specification-preview__title"
          aria-label="Заголовок страницы расчета токопотребления"
          value={calculation.page_title || ''}
          onChange={(event) => onTopLevelFieldChange('page_title', event.target.value)}
        />

        <div className="power-consumption-preview__meta">
          <label className="power-consumption-preview__field power-consumption-preview__field--wide">
            <span>Вводный текст 1</span>
            <textarea
              aria-label="Вводный текст 1"
              rows={4}
              value={calculation.introductory_texts?.[0] || ''}
              onChange={(event) => onIntroductoryTextChange(0, event.target.value)}
            />
          </label>
          <label className="power-consumption-preview__field power-consumption-preview__field--wide">
            <span>Вводный текст 2</span>
            <textarea
              aria-label="Вводный текст 2"
              rows={2}
              value={calculation.introductory_texts?.[1] || ''}
              onChange={(event) => onIntroductoryTextChange(1, event.target.value)}
            />
          </label>
          <label className="power-consumption-preview__field">
            <span>Подпись таблицы</span>
            <input
              aria-label="Подпись таблицы расчета"
              value={calculation.table_caption || ''}
              onChange={(event) => onTopLevelFieldChange('table_caption', event.target.value)}
            />
          </label>
          <label className="power-consumption-preview__field power-consumption-preview__field--wide">
            <span>Заголовок таблицы</span>
            <input
              aria-label="Заголовок таблицы расчета"
              value={calculation.table_title || ''}
              onChange={(event) => onTopLevelFieldChange('table_title', event.target.value)}
            />
          </label>
          <label className="power-consumption-preview__field">
            <span>Напряжение АКБ, В</span>
            <input
              aria-label="Напряжение аккумулятора"
              value={String(calculation.battery_voltage_v ?? '')}
              onChange={(event) => onTopLevelFieldChange('battery_voltage_v', event.target.value)}
            />
          </label>
          <label className="power-consumption-preview__field">
            <span>Количество АКБ, шт.</span>
            <input
              aria-label="Количество аккумуляторов"
              value={String(calculation.battery_quantity ?? '')}
              onChange={(event) => onTopLevelFieldChange('battery_quantity', event.target.value)}
            />
          </label>
          <label className="power-consumption-preview__field">
            <span>Итоговая емкость, Ач</span>
            <input value={String(calculation.battery_capacity_ah ?? '')} readOnly />
          </label>
        </div>

        <table className="equipment-specification-preview__table power-consumption-preview__table">
          <thead>
            <tr>
              <th colSpan={8}>
                <input
                  className="power-consumption-preview__header-title"
                  aria-label="Заголовок таблицы в шапке"
                  value={calculation.table_title || ''}
                  onChange={(event) => onTopLevelFieldChange('table_title', event.target.value)}
                />
              </th>
            </tr>
            <tr>
              <th rowSpan={2}>№</th>
              <th rowSpan={2}>Наименование оборудования</th>
              <th rowSpan={2}>Ед. изм.</th>
              <th rowSpan={2}>Кол-во</th>
              <th colSpan={2}>Токопотребление, А</th>
              <th colSpan={2}>Токопотребление общее, А</th>
            </tr>
            <tr>
              <th>Дежурный режим</th>
              <th>Режим &quot;Пожар&quot;</th>
              <th>Дежурный режим</th>
              <th>Режим &quot;Пожар&quot;</th>
            </tr>
          </thead>
          <tbody>
            {(calculation.categories || []).map((category) => (
              <React.Fragment key={category.key}>
                <tr className="equipment-specification-preview__section-row power-consumption-preview__section-row">
                  <td colSpan={8}>
                    <input
                      aria-label={`Категория расчета ${category.key}`}
                      value={category.title || ''}
                      onChange={(event) => onCategoryTitleChange(category.key, event.target.value)}
                    />
                  </td>
                </tr>
                {(category.rows || []).map((row) => (
                  <tr key={row.source_key}>
                    <td>
                      <input
                        aria-label={`${row.source_key}:number`}
                        value={row.number || ''}
                        onChange={(event) => onRowFieldChange(category.key, row.source_key, 'number', event.target.value)}
                      />
                    </td>
                    <td>
                      <textarea
                        aria-label={`${row.source_key}:equipment_name`}
                        rows={3}
                        value={row.equipment_name || ''}
                        onChange={(event) => onRowFieldChange(category.key, row.source_key, 'equipment_name', event.target.value)}
                      />
                    </td>
                    <td>
                      <input
                        aria-label={`${row.source_key}:unit`}
                        value={row.unit || ''}
                        onChange={(event) => onRowFieldChange(category.key, row.source_key, 'unit', event.target.value)}
                      />
                    </td>
                    <td>
                      <input
                        aria-label={`${row.source_key}:quantity`}
                        value={row.quantity || ''}
                        onChange={(event) => onRowFieldChange(category.key, row.source_key, 'quantity', event.target.value)}
                      />
                    </td>
                    <td>
                      <input
                        aria-label={`${row.source_key}:standby_current`}
                        value={row.standby_current || ''}
                        onChange={(event) => onRowFieldChange(category.key, row.source_key, 'standby_current', event.target.value)}
                      />
                    </td>
                    <td>
                      <input
                        aria-label={`${row.source_key}:alarm_current`}
                        value={row.alarm_current || ''}
                        onChange={(event) => onRowFieldChange(category.key, row.source_key, 'alarm_current', event.target.value)}
                      />
                    </td>
                    <td className="power-consumption-preview__readonly">{row.standby_total || ''}</td>
                    <td className="power-consumption-preview__readonly">{row.alarm_total || ''}</td>
                  </tr>
                ))}
              </React.Fragment>
            ))}
            {(calculation.summary_rows || []).map((row) => {
              if (row.kind === 'summary_merged') {
                return (
                  <tr key={row.key} className="power-consumption-preview__summary-row">
                    <td colSpan={6}>
                      <input
                        className="power-consumption-preview__summary-label"
                        aria-label={`Итоговая строка ${row.key}`}
                        value={row.label || ''}
                        onChange={(event) => onSummaryFieldChange(row.key, 'label', event.target.value)}
                      />
                    </td>
                    <td colSpan={2} className="power-consumption-preview__readonly">
                      {row.value || ''}
                    </td>
                  </tr>
                );
              }

              const editableValues = EDITABLE_SUMMARY_KEYS.has(row.key);
              return (
                <tr key={row.key} className="power-consumption-preview__summary-row">
                  <td colSpan={6}>
                    <input
                      className="power-consumption-preview__summary-label"
                      aria-label={`Итоговая строка ${row.key}`}
                      value={row.label || ''}
                      onChange={(event) => onSummaryFieldChange(row.key, 'label', event.target.value)}
                    />
                  </td>
                  <td className={editableValues ? '' : 'power-consumption-preview__readonly'}>
                    {editableValues ? (
                      <input
                        aria-label={`Итоговое значение ${row.key}:standby`}
                        value={row.standby || ''}
                        onChange={(event) => onSummaryFieldChange(row.key, 'standby', event.target.value)}
                      />
                    ) : (
                      row.standby || ''
                    )}
                  </td>
                  <td className={editableValues ? '' : 'power-consumption-preview__readonly'}>
                    {editableValues ? (
                      <input
                        aria-label={`Итоговое значение ${row.key}:alarm`}
                        value={row.alarm || ''}
                        onChange={(event) => onSummaryFieldChange(row.key, 'alarm', event.target.value)}
                      />
                    ) : (
                      row.alarm || ''
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>

        <label className="power-consumption-preview__field power-consumption-preview__field--wide">
          <span>Итоговый текст</span>
          <textarea
            aria-label="Итоговый текст расчета"
            rows={3}
            value={calculation.final_text || ''}
            readOnly
          />
        </label>
      </div>
    </div>
  );
}

export default PowerConsumptionCalculationPreview;
