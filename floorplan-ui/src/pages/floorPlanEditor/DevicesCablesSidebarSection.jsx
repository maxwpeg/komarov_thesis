import React from 'react';

import { SIGNAL_INSTRUMENT_OPTIONS, formatCableMeters, getSignalInstrumentDefinition } from './helpers';

export default function DevicesCablesSidebarSection({
  selectedTool,
  visibleSignalInstruments,
  visibleCableRoutes,
  selectedElement,
  mergeInstrumentId,
  mergeSelectionCount,
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
        <h3>РџСЂРёР±РѕСЂС‹ Рё РєР°Р±РµР»Рё</h3>
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

        {mergeInstrumentId && (
          <div style={{ marginBottom: '10px', padding: '8px', borderRadius: '8px', background: 'rgba(15, 143, 124, 0.08)' }}>
            <div style={{ fontSize: '12px', marginBottom: '6px' }}>
              Р’С‹Р±СЂР°РЅРѕ РґР°С‚С‡РёРєРѕРІ: {mergeSelectionCount}
            </div>
            <div style={{ display: 'flex', gap: '6px' }}>
              <button className="tool-button" onClick={onApplyMerge} disabled={!mergeSelectionCount}>
                РџСЂРёРјРµРЅРёС‚СЊ
              </button>
              <button className="tool-button" onClick={onCancelMerge}>
                РћС‚РјРµРЅР°
              </button>
            </div>
          </div>
        )}

        <ul className="element-list">
          {visibleSignalInstruments.map((instrument) => {
            const definition = getSignalInstrumentDefinition(instrument.instrument_type);
            const supportsMerge = Boolean(definition.supportsMerge);
            const mergeActive = mergeInstrumentId === instrument.id;
            return (
              <li
                key={`instrument-${instrument.id}`}
                className={`element-item ${selectedElement?.type === 'signal-instrument' && selectedElement?.id === instrument.id ? 'selected' : ''}`}
                onClick={() => onSelectInstrument(instrument)}
              >
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div>{instrument.name || definition.label}</div>
                  <small>{definition.label}</small>
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
                        {mergeActive ? 'РџСЂРёРјРµРЅРёС‚СЊ' : 'РЎРІРµСЃС‚Рё РґР°С‚С‡РёРєРё'}
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
                  Г—
                </button>
              </li>
            );
          })}
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
