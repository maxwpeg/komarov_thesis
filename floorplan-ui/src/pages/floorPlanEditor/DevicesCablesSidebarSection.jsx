import React from 'react';

import { SIGNAL_INSTRUMENT_OPTIONS, formatCableMeters, getSignalInstrumentDefinition } from './helpers';

const DEFAULT_TITLE = '\u041f\u0440\u0438\u0431\u043e\u0440\u044b \u0438 \u043a\u0430\u0431\u0435\u043b\u0438';
const DEFAULT_MERGE_SELECTION_LABEL = '\u0412\u044b\u0431\u0440\u0430\u043d\u043e \u0438\u0437\u0432\u0435\u0449\u0430\u0442\u0435\u043b\u0435\u0439';
const DEFAULT_MERGE_BUTTON_LABEL = '\u0421\u0432\u0435\u0441\u0442\u0438 \u0438\u0437\u0432\u0435\u0449\u0430\u0442\u0435\u043b\u0438';

export default function DevicesCablesSidebarSection({
  selectedTool,
  visibleSignalInstruments,
  visibleCableRoutes,
  selectedElement,
  mergeInstrumentId,
  mergeSelectionCount,
  title = DEFAULT_TITLE,
  instrumentOptions = SIGNAL_INSTRUMENT_OPTIONS,
  actionButtons = [],
  showToolSelector = true,
  showRouteSummary = true,
  allowMerge = true,
  mergeSelectionLabel = DEFAULT_MERGE_SELECTION_LABEL,
  mergeButtonLabel = DEFAULT_MERGE_BUTTON_LABEL,
  onSelectTool,
  onSelectInstrument,
  onStartMerge,
  onApplyMerge,
  onCancelMerge,
  onDeleteSignalInstrument,
}) {
  return (
    <div className="editor-sidebar" style={{ borderLeft: '1px solid var(--panel-border)' }}>
      <div className="sidebar-section">
        <h3>{title}</h3>
        {actionButtons.length > 0 && (
          <div style={{ display: 'grid', gap: '6px', marginBottom: '10px' }}>
            {actionButtons.map((action) => (
              <button
                key={action.key}
                className="tool-button"
                disabled={Boolean(action.disabled)}
                onClick={action.onClick}
              >
                {action.label}
              </button>
            ))}
          </div>
        )}
        {showToolSelector && (
          <div style={{ display: 'grid', gap: '6px', marginBottom: '10px' }}>
            <button
              className={`tool-button ${selectedTool === 'select' ? 'active' : ''}`}
              onClick={() => onSelectTool('select')}
            >
              {'\u0412\u044b\u0431\u0440\u0430\u0442\u044c'}
            </button>
            {instrumentOptions.map((option) => (
              <button
                key={option.key}
                className={`tool-button ${selectedTool === option.key ? 'active' : ''}`}
                onClick={() => onSelectTool(option.key)}
              >
                {option.label}
              </button>
            ))}
          </div>
        )}

        {allowMerge && mergeInstrumentId && (
          <div style={{ marginBottom: '10px', padding: '8px', borderRadius: '8px', background: 'rgba(15, 143, 124, 0.08)' }}>
            <div style={{ fontSize: '12px', marginBottom: '6px' }}>
              {mergeSelectionLabel}
              {': '}
              {mergeSelectionCount}
            </div>
            <div style={{ display: 'flex', gap: '6px' }}>
              <button className="tool-button" onClick={onApplyMerge} disabled={!mergeSelectionCount}>
                {'\u041f\u0440\u0438\u043c\u0435\u043d\u0438\u0442\u044c'}
              </button>
              <button className="tool-button" onClick={onCancelMerge}>
                {'\u041e\u0442\u043c\u0435\u043d\u0430'}
              </button>
            </div>
          </div>
        )}

        <ul className="element-list">
          {visibleSignalInstruments.map((instrument) => {
            const definition = getSignalInstrumentDefinition(instrument.instrument_type);
            const primaryLabel = instrument.equipment_name || instrument.name || definition.label;
            const secondaryLabel = instrument.equipment_name
              ? `${definition.label}${instrument.name && instrument.name !== instrument.equipment_name ? ` • ${instrument.name}` : ''}`
              : definition.label;
            const supportsMerge = allowMerge && Boolean(definition.supportsMerge);
            const mergeActive = mergeInstrumentId === instrument.id;
            return (
              <li
                key={`instrument-${instrument.id}`}
                className={`element-item ${selectedElement?.type === 'signal-instrument' && selectedElement?.id === instrument.id ? 'selected' : ''}`}
                onClick={() => onSelectInstrument(instrument)}
              >
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div>{primaryLabel}</div>
                  <small>{secondaryLabel}</small>
                  {supportsMerge && (
                    <div style={{ marginTop: '6px' }}>
                      <button
                        className="tool-button"
                        style={{ fontSize: '11px', padding: '3px 7px' }}
                        onClick={(e) => {
                          e.stopPropagation();
                          if (mergeActive) {
                            onApplyMerge();
                          } else {
                            onStartMerge(instrument);
                          }
                        }}
                      >
                        {mergeActive ? '\u041f\u0440\u0438\u043c\u0435\u043d\u0438\u0442\u044c' : mergeButtonLabel}
                      </button>
                    </div>
                  )}
                </div>
                <button
                  className="element-delete"
                  onClick={(e) => {
                    e.stopPropagation();
                    onDeleteSignalInstrument(instrument.id, instrument.system_type);
                  }}
                >
                  {'\u00d7'}
                </button>
              </li>
            );
          })}
        </ul>
        {showRouteSummary && (
          <div style={{ marginTop: '10px', fontSize: '12px', color: 'var(--muted-text)' }}>
            {visibleCableRoutes.map((route) => (
              <div key={`route-${route.id}`} style={{ marginBottom: '6px' }}>
                {route.route_kind}
                {' #'}
                {route.route_number}
                {': '}
                {formatCableMeters(route.length_m)}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
