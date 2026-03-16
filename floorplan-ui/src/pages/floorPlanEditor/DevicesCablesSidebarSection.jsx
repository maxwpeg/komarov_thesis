import React from 'react';

import { SIGNAL_INSTRUMENT_OPTIONS, formatCableMeters, getSignalInstrumentDefinition } from './helpers';

export default function DevicesCablesSidebarSection({
  selectedTool,
  visibleSignalInstruments,
  visibleCableRoutes,
  selectedElement,
  onSelectTool,
  onSelectInstrument,
  onMergeCableRoutes,
  onDeleteSignalInstrument,
}) {
  return (
    <div className="editor-sidebar" style={{ borderLeft: '1px solid var(--panel-border)' }}>
      <div className="sidebar-section">
        <h3>Приборы и кабели</h3>
        <div style={{ display: 'grid', gap: '6px', marginBottom: '10px' }}>
          {SIGNAL_INSTRUMENT_OPTIONS.map((option) => (
            <button
              key={option.key}
              className={`tool-button ${selectedTool === option.key ? 'active' : ''}`}
              onClick={() => onSelectTool(option.key)}
            >
              {option.label}
            </button>
          ))}
        </div>
        <ul className="element-list">
          {visibleSignalInstruments.map((instrument) => (
            <li
              key={`instrument-${instrument.id}`}
              className={`element-item ${selectedElement?.type === 'signal-instrument' && selectedElement?.id === instrument.id ? 'selected' : ''}`}
              onClick={() => onSelectInstrument(instrument)}
            >
              <div>
                <div>{instrument.name || getSignalInstrumentDefinition(instrument.instrument_type).label}</div>
                <small>{getSignalInstrumentDefinition(instrument.instrument_type).label}</small>
              </div>
              {instrument.supports_cable_merge && (
                <button
                  className="tool-button"
                  style={{ fontSize: '11px', padding: '3px 6px' }}
                  onClick={(e) => {
                    e.stopPropagation();
                    onMergeCableRoutes(instrument);
                  }}
                >
                  Свести
                </button>
              )}
              <button
                className="element-delete"
                onClick={(e) => {
                  e.stopPropagation();
                  onDeleteSignalInstrument(instrument.id, instrument.system_type);
                }}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
        <div style={{ marginTop: '10px', fontSize: '12px', color: 'var(--muted-text)' }}>
          {visibleCableRoutes.map((route) => (
            <div key={`route-${route.id}`} style={{ marginBottom: '6px' }}>
              {route.route_kind} #{route.route_number}: {formatCableMeters(route.length_m)}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
