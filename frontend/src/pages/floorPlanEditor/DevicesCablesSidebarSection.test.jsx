import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';

import DevicesCablesSidebarSection from './DevicesCablesSidebarSection';

function getButtonByTextContent(...fragments) {
  return screen.getAllByRole('button').find((button) => (
    fragments.some((fragment) => button.textContent?.includes(fragment))
  ));
}

test('renders the sidebar controls and uses the normalized delete cross label', () => {
  const onDeleteSignalInstrument = jest.fn();

  render(
    <DevicesCablesSidebarSection
      selectedTool="control_panel"
      visibleSignalInstruments={[
        {
          id: 10,
          name: '\u041f\u041f\u041a\u041f',
          instrument_type: 'control_panel',
          system_type: 'common',
        },
      ]}
      visibleCableRoutes={[]}
      selectedElement={null}
      mergeInstrumentId={null}
      mergeSelectionCount={0}
      onSelectTool={jest.fn()}
      onSelectInstrument={jest.fn()}
      onStartMerge={jest.fn()}
      onApplyMerge={jest.fn()}
      onCancelMerge={jest.fn()}
      onDeleteSignalInstrument={onDeleteSignalInstrument}
    />,
  );

  expect(screen.getByRole('heading', { name: /\u041f\u0440\u0438\u0431\u043e\u0440\u044b \u0438 \u043a\u0430\u0431\u0435\u043b\u0438/i })).toBeInTheDocument();
  expect(getButtonByTextContent('\u0412\u044b\u0431\u0440\u0430\u0442\u044c')).toBeTruthy();

  fireEvent.click(screen.getByRole('button', { name: '\u00d7' }));
  expect(onDeleteSignalInstrument).toHaveBeenCalledWith(10, 'common');
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
          name: '\u041f\u041f\u041a\u041f',
          instrument_type: 'control_panel',
          system_type: 'common',
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

  fireEvent.click(getButtonByTextContent('\u0421\u0432\u0435\u0441\u0442\u0438 \u0438\u0437\u0432\u0435\u0449\u0430\u0442\u0435\u043b\u0438'));
  expect(onStartMerge).toHaveBeenCalled();

  rerender(
    <DevicesCablesSidebarSection
      selectedTool="multi-select"
      visibleSignalInstruments={[
        {
          id: 10,
          name: '\u041f\u041f\u041a\u041f',
          instrument_type: 'control_panel',
          system_type: 'common',
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

  expect(screen.getByText(/\u0412\u044b\u0431\u0440\u0430\u043d\u043e \u0438\u0437\u0432\u0435\u0449\u0430\u0442\u0435\u043b\u0435\u0439:\s*2/i)).toBeInTheDocument();
  fireEvent.click(getButtonByTextContent('\u041f\u0440\u0438\u043c\u0435\u043d\u0438\u0442\u044c'));
  expect(onApplyMerge).toHaveBeenCalled();
  fireEvent.click(getButtonByTextContent('\u041e\u0442\u043c\u0435\u043d\u0430'));
  expect(onCancelMerge).toHaveBeenCalled();
});
