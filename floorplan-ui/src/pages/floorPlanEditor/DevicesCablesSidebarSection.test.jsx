import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';

import DevicesCablesSidebarSection from './DevicesCablesSidebarSection';

test('renders readable devices and cables heading and delete button label', () => {
  const onSelectTool = jest.fn();
  const onSelectInstrument = jest.fn();
  const onDeleteSignalInstrument = jest.fn();

  render(
    <DevicesCablesSidebarSection
      selectedTool="control_panel"
      visibleSignalInstruments={[
        {
          id: 10,
          name: 'РџРџРљРџ',
          instrument_type: 'control_panel',
          system_type: 'non_addressable',
        },
      ]}
      visibleCableRoutes={[]}
      selectedElement={null}
      mergeInstrumentId={null}
      mergeSelectionCount={0}
      onSelectTool={onSelectTool}
      onSelectInstrument={onSelectInstrument}
      onStartMerge={jest.fn()}
      onApplyMerge={jest.fn()}
      onCancelMerge={jest.fn()}
      onDeleteSignalInstrument={onDeleteSignalInstrument}
    />,
  );

  expect(screen.getByRole('heading', { name: 'РџСЂРёР±РѕСЂС‹ Рё РєР°Р±РµР»Рё' })).toBeInTheDocument();
  expect(screen.queryByText('\\u041f\\u0440\\u0438\\u0431\\u043e\\u0440\\u044b')).not.toBeInTheDocument();

  fireEvent.click(screen.getByRole('button', { name: 'Г—' }));
  expect(onDeleteSignalInstrument).toHaveBeenCalledWith(10, 'non_addressable');
});

test('shows merge actions for merge-capable instrument', () => {
  const onStartMerge = jest.fn();
  const onApplyMerge = jest.fn();
  const onCancelMerge = jest.fn();

  const { rerender } = render(
    <DevicesCablesSidebarSection
      selectedTool="control_panel"
      visibleSignalInstruments={[
        {
          id: 10,
          name: 'РџРџРљРџ',
          instrument_type: 'control_panel',
          system_type: 'non_addressable',
        },
      ]}
      visibleCableRoutes={[]}
      selectedElement={null}
      mergeInstrumentId={null}
      mergeSelectionCount={0}
      onSelectTool={jest.fn()}
      onSelectInstrument={jest.fn()}
      onStartMerge={onStartMerge}
      onApplyMerge={onApplyMerge}
      onCancelMerge={onCancelMerge}
      onDeleteSignalInstrument={jest.fn()}
    />,
  );

  fireEvent.click(screen.getByRole('button', { name: 'РЎРІРµСЃС‚Рё РґР°С‚С‡РёРєРё' }));
  expect(onStartMerge).toHaveBeenCalled();

  rerender(
    <DevicesCablesSidebarSection
      selectedTool="multi-select"
      visibleSignalInstruments={[
        {
          id: 10,
          name: 'РџРџРљРџ',
          instrument_type: 'control_panel',
          system_type: 'non_addressable',
        },
      ]}
      visibleCableRoutes={[]}
      selectedElement={null}
      mergeInstrumentId={10}
      mergeSelectionCount={2}
      onSelectTool={jest.fn()}
      onSelectInstrument={jest.fn()}
      onStartMerge={onStartMerge}
      onApplyMerge={onApplyMerge}
      onCancelMerge={onCancelMerge}
      onDeleteSignalInstrument={jest.fn()}
    />,
  );

  fireEvent.click(screen.getAllByRole('button', { name: 'РџСЂРёРјРµРЅРёС‚СЊ' })[0]);
  expect(onApplyMerge).toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'РћС‚РјРµРЅР°' }));
  expect(onCancelMerge).toHaveBeenCalled();
});
