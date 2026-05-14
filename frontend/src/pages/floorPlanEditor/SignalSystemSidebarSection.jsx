import React from 'react';

import { SIGNAL_SYSTEM_OPTIONS, formatCableMeters } from './helpers';

const TOGGLE_TRACK_STYLE = {
  display: 'grid',
  gridTemplateColumns: `repeat(${SIGNAL_SYSTEM_OPTIONS.length}, minmax(0, 1fr))`,
  gap: '2px',
  padding: '2px',
  borderRadius: '999px',
  border: '1px solid rgba(15, 143, 124, 0.18)',
  background: 'rgba(15, 143, 124, 0.06)',
  minWidth: '230px',
};

export default function SignalSystemSidebarSection({
  currentSignalSystem,
  signalBranchSummary,
  summaryItems = null,
  deviceCountLabel = '\u0418\u0437\u0432\u0435\u0449\u0430\u0442\u0435\u043b\u0435\u0439',
  onSwitchSignalSystem,
  embedded = false,
}) {
  const resolvedSummaryItems = summaryItems?.length
    ? summaryItems
    : [
      { key: 'devices', label: deviceCountLabel, value: signalBranchSummary.detectorCount },
      { key: 'cable', label: '\u041a\u0430\u0431\u0435\u043b\u044f', value: formatCableMeters(signalBranchSummary.cableLengthM) },
    ];

  const content = (
    <div style={{ display: 'grid', gap: '10px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'nowrap' }}>
        <div style={TOGGLE_TRACK_STYLE}>
          {SIGNAL_SYSTEM_OPTIONS.map((option) => {
            const active = currentSignalSystem === option.key;
            return (
              <button
                key={option.key}
                type="button"
                className={`tool-button ${active ? 'active' : ''}`}
                style={{
                  minHeight: '32px',
                  padding: '0.45rem 0.9rem',
                  borderRadius: '999px',
                  boxShadow: 'none',
                  transform: 'none',
                  border: 'none',
                  background: active ? 'var(--accent)' : 'transparent',
                  color: active ? '#ffffff' : 'var(--text-secondary)',
                  whiteSpace: 'nowrap',
                }}
                onClick={() => onSwitchSignalSystem(option.key)}
              >
                {option.label}
              </button>
            );
          })}
        </div>
      </div>
      <div style={{ padding: '8px 10px', background: '#f8f9fa', borderRadius: '10px', fontSize: '12px', color: 'var(--text-secondary)' }}>
        {resolvedSummaryItems.map((item) => (
          <div key={item.key}>
            {item.label}
            {': '}
            {item.value}
          </div>
        ))}
      </div>
    </div>
  );

  if (embedded) {
    return (
      <div data-testid="signal-system-section-embedded">
        {content}
      </div>
    );
  }

  return (
    <div className="sidebar-section">
      {content}
    </div>
  );
}
