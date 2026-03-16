import React from 'react';

import { SIGNAL_SYSTEM_OPTIONS, formatCableMeters, getSignalSystemLabel } from './helpers';

export default function SignalSystemSidebarSection({
  currentSignalSystem,
  signalBranchSummary,
  onSwitchSignalSystem,
}) {
  return (
    <div className="sidebar-section">
      <h3>Тип сигнализации</h3>
      <div style={{ display: 'grid', gap: '8px' }}>
        {SIGNAL_SYSTEM_OPTIONS.map((option) => (
          <button
            key={option.key}
            className={`tool-button ${currentSignalSystem === option.key ? 'active' : ''}`}
            style={{ textAlign: 'left' }}
            onClick={() => onSwitchSignalSystem(option.key)}
          >
            <div>{option.label}</div>
            <div style={{ fontSize: '11px', color: '#6c757d', fontWeight: 400 }}>{option.hint}</div>
          </button>
        ))}
      </div>
      <div style={{ marginTop: '10px', padding: '8px', background: '#f8f9fa', borderRadius: '6px', fontSize: '12px' }}>
        <div><strong>{getSignalSystemLabel(currentSignalSystem)}</strong></div>
        <div>Извещателей: {signalBranchSummary.detectorCount}</div>
        <div>Кабеля: {formatCableMeters(signalBranchSummary.cableLengthM)}</div>
      </div>
    </div>
  );
}
