import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';

import AdditionalInfoPreview from './AdditionalInfoPreview';
import EquipmentSpecificationPreview from './EquipmentSpecificationPreview';
import GeneralDataPreview from './GeneralDataPreview';
import GeneralInstructionsPreview from './GeneralInstructionsPreview';
import PowerConsumptionCalculationPreview from './PowerConsumptionCalculationPreview';

describe('document preview components', () => {
  test('AdditionalInfoPreview handles loading, editing and toolbar actions', () => {
    const onTextChange = jest.fn();
    const onSave = jest.fn();
    const onRefresh = jest.fn();

    const { rerender } = render(<AdditionalInfoPreview loading />);
    expect(screen.getByText(/Загрузка доп\. сведений/i)).toBeInTheDocument();

    rerender(
      <AdditionalInfoPreview
        additionalInfo={{ page_title: 'Доп. сведения', text: 'Исходный текст', is_empty: false }}
        onTextChange={onTextChange}
        onSave={onSave}
        onRefresh={onRefresh}
      />,
    );

    fireEvent.change(screen.getByLabelText(/Текст доп\. сведений/i), { target: { value: 'Новый текст' } });
    fireEvent.click(screen.getByRole('button', { name: /Сохранить/i }));
    fireEvent.click(screen.getByRole('button', { name: /Обновить/i }));

    expect(onTextChange).toHaveBeenCalledWith('Новый текст');
    expect(onSave).toHaveBeenCalled();
    expect(onRefresh).toHaveBeenCalled();
  });

  test('EquipmentSpecificationPreview renders warnings and forwards cell edits', () => {
    const onPageTitleChange = jest.fn();
    const onHeaderChange = jest.fn();
    const onSectionTitleChange = jest.fn();
    const onCellChange = jest.fn();

    render(
      <EquipmentSpecificationPreview
        specification={{
          page_title: 'Спецификация',
          column_headers: ['Поз.', 'Наименование', 'Тип', 'Код', 'Производитель', 'Ед.', 'Кол-во', 'Масса', 'Примечание'],
          warnings: ['Предупреждение 1'],
          sections: [
            {
              key: 'sec-1',
              title: 'Раздел 1',
              rows: [
                {
                  source_key: 'row-1',
                  position: '1',
                  technical_name: 'Извещатель',
                  type_mark: 'Тип',
                  code: 'Код',
                  manufacturer: 'Болид',
                  unit: 'шт.',
                  quantity: '2',
                  unit_mass_kg: '0.1',
                  note: 'Прим.',
                },
              ],
            },
          ],
        }}
        onPageTitleChange={onPageTitleChange}
        onHeaderChange={onHeaderChange}
        onSectionTitleChange={onSectionTitleChange}
        onCellChange={onCellChange}
        onSave={jest.fn()}
        onRefresh={jest.fn()}
      />,
    );

    expect(screen.getByText(/Предупреждение 1/i)).toBeInTheDocument();
    fireEvent.change(screen.getByDisplayValue('Спецификация'), { target: { value: 'Новая спецификация' } });
    fireEvent.change(screen.getByDisplayValue('Поз.'), { target: { value: 'Позиция' } });
    fireEvent.change(screen.getByDisplayValue('Раздел 1'), { target: { value: 'Приборы' } });
    fireEvent.change(screen.getByDisplayValue('Извещатель'), { target: { value: 'Датчик' } });

    expect(onPageTitleChange).toHaveBeenCalledWith('Новая спецификация');
    expect(onHeaderChange).toHaveBeenCalledWith(0, 'Позиция');
    expect(onSectionTitleChange).toHaveBeenCalledWith('sec-1', 'Приборы');
    expect(onCellChange).toHaveBeenCalledWith('sec-1', 'row-1', 1, 'Датчик');
  });

  test('GeneralDataPreview forwards top-level and row edits', () => {
    const onTopLevelFieldChange = jest.fn();
    const onDocumentRowFieldChange = jest.fn();
    const onManifestRowFieldChange = jest.fn();

    render(
      <GeneralDataPreview
        generalData={{
          page_title: 'Общие данные',
          left_table_title: 'Левая таблица',
          right_table_title: 'Правая таблица',
          reference_category_title: 'Ссылочные документы',
          attached_category_title: 'Прилагаемые документы',
          gip_name: 'Петров П.П.',
          statement_text: 'Исходный текст',
          reference_documents: [{ key: 'ref-1', designation: 'СП 1', name: 'Документ', note: '' }],
          attached_documents: [{ key: 'att-1', designation: 'Шифр', name: 'Спецификация', note: '' }],
          drawing_manifest_rows: [{ key: 'draw-1', name: 'Общие данные', note: 'на 2-х листах' }],
        }}
        onTopLevelFieldChange={onTopLevelFieldChange}
        onDocumentRowFieldChange={onDocumentRowFieldChange}
        onManifestRowFieldChange={onManifestRowFieldChange}
        onSave={jest.fn()}
        onRefresh={jest.fn()}
      />,
    );

    fireEvent.change(screen.getByLabelText(/Название листа общих данных/i), { target: { value: 'Измененный заголовок' } });
    fireEvent.change(screen.getByLabelText('ref-1:name'), { target: { value: 'Новый документ' } });
    fireEvent.change(screen.getByLabelText('draw-1:manifest-name'), { target: { value: 'Новые общие данные' } });

    expect(onTopLevelFieldChange).toHaveBeenCalledWith('page_title', 'Измененный заголовок');
    expect(onDocumentRowFieldChange).toHaveBeenCalledWith('reference_documents', 'ref-1', 'name', 'Новый документ');
    expect(onManifestRowFieldChange).toHaveBeenCalledWith('draw-1', 'name', 'Новые общие данные');
  });

  test('GeneralInstructionsPreview edits paragraph and bullet blocks', () => {
    const onTopLevelFieldChange = jest.fn();
    const onBlockTextChange = jest.fn();
    const onBlockItemsChange = jest.fn();

    render(
      <GeneralInstructionsPreview
        instructions={{
          page_title: 'Общие указания',
          heading: 'ОБЩИЕ УКАЗАНИЯ.',
          local_sheet_title: 'Общие указания',
          blocks: [
            { key: 'heading-1', kind: 'section_heading', text: '1. Введение', items: [] },
            { key: 'paragraph-1', kind: 'paragraph', text: 'Первый абзац', items: [] },
            { key: 'list-1', kind: 'bullet_list', text: null, items: ['Пункт 1', 'Пункт 2'] },
          ],
        }}
        onTopLevelFieldChange={onTopLevelFieldChange}
        onBlockTextChange={onBlockTextChange}
        onBlockItemsChange={onBlockItemsChange}
        onSave={jest.fn()}
        onRefresh={jest.fn()}
      />,
    );

    fireEvent.change(screen.getByLabelText(/Заголовок общих указаний/i), { target: { value: 'НОВЫЙ ЗАГОЛОВОК' } });
    fireEvent.change(screen.getByLabelText(/Блок общих указаний paragraph-1/i), { target: { value: 'Новый абзац' } });
    fireEvent.change(screen.getByLabelText(/Блок общих указаний list-1/i), { target: { value: 'Строка 1\nСтрока 2' } });

    expect(onTopLevelFieldChange).toHaveBeenCalledWith('heading', 'НОВЫЙ ЗАГОЛОВОК');
    expect(onBlockTextChange).toHaveBeenCalledWith('paragraph-1', 'Новый абзац');
    expect(onBlockItemsChange).toHaveBeenCalledWith('list-1', 'Строка 1\nСтрока 2');
  });

  test('PowerConsumptionCalculationPreview edits rows and summary values', () => {
    const onTopLevelFieldChange = jest.fn();
    const onIntroductoryTextChange = jest.fn();
    const onCategoryTitleChange = jest.fn();
    const onRowFieldChange = jest.fn();
    const onSummaryFieldChange = jest.fn();

    render(
      <PowerConsumptionCalculationPreview
        calculation={{
          page_title: 'Расчет токопотребления системы',
          introductory_texts: ['Абзац 1', 'Абзац 2'],
          table_caption: 'Таблица 1.',
          table_title: 'Расчет токопотребления системы',
          battery_voltage_v: 12,
          battery_quantity: 1,
          battery_capacity_ah: 8,
          final_text: 'Итоговый текст',
          categories: [
            {
              key: 'instruments',
              title: 'Приборы',
              rows: [
                {
                  source_key: 'row-1',
                  number: '1',
                  equipment_name: 'ППКОП',
                  unit: 'шт.',
                  quantity: '1',
                  standby_current: '0.1',
                  alarm_current: '0.2',
                  standby_total: '0.1',
                  alarm_total: '0.2',
                },
              ],
            },
          ],
          summary_rows: [
            { key: 'operation_time', kind: 'summary_pair', label: 'Время работы', standby: '24', alarm: '1', value: null },
            { key: 'total_capacity', kind: 'summary_merged', label: 'Wобщ', standby: null, alarm: null, value: '8.2' },
          ],
        }}
        onTopLevelFieldChange={onTopLevelFieldChange}
        onIntroductoryTextChange={onIntroductoryTextChange}
        onCategoryTitleChange={onCategoryTitleChange}
        onRowFieldChange={onRowFieldChange}
        onSummaryFieldChange={onSummaryFieldChange}
        onSave={jest.fn()}
        onRefresh={jest.fn()}
      />,
    );

    fireEvent.change(screen.getByLabelText(/Вводный текст 1/i), { target: { value: 'Новый абзац' } });
    fireEvent.change(screen.getByLabelText(/Категория расчета instruments/i), { target: { value: 'Обновленные приборы' } });
    fireEvent.change(screen.getByLabelText('row-1:equipment_name'), { target: { value: 'Контроллер' } });
    fireEvent.change(screen.getByLabelText(/Итоговое значение operation_time:standby/i), { target: { value: '48' } });

    expect(onIntroductoryTextChange).toHaveBeenCalledWith(0, 'Новый абзац');
    expect(onCategoryTitleChange).toHaveBeenCalledWith('instruments', 'Обновленные приборы');
    expect(onRowFieldChange).toHaveBeenCalledWith('instruments', 'row-1', 'equipment_name', 'Контроллер');
    expect(onSummaryFieldChange).toHaveBeenCalledWith('operation_time', 'standby', '48');
    expect(screen.getByDisplayValue('Итоговый текст')).toHaveAttribute('readonly');
  });
});
