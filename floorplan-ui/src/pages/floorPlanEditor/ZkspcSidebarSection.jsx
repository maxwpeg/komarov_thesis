import React from 'react';

import { getZkspcColor } from './helpers';

export default function ZkspcSidebarSection({
  currentZkspcZones,
  visibleRooms,
  roomDisplayNumberMap,
  selectedZkspcRooms,
  pipelineActionLoading,
  roomsValidated,
  onDetect,
  onCommit,
  onMergeSelected,
  onToggleRoom,
  onMoveSelectedRoomsToZone,
  onToggleLock,
  onSplit,
}) {
  return (
    <div className="sidebar-section">
      <h3>ЗКСПС ({currentZkspcZones.length})</h3>
      <div style={{ display: 'flex', gap: '6px', marginBottom: '8px', flexWrap: 'wrap' }}>
        <button className="tool-button" onClick={onDetect} disabled={pipelineActionLoading || !roomsValidated}>
          Распознать
        </button>
        <button className="tool-button" onClick={onCommit} disabled={pipelineActionLoading || !currentZkspcZones.length}>
          Подтвердить
        </button>
        <button className="tool-button" onClick={onMergeSelected} disabled={selectedZkspcRooms.length < 2}>
          Объединить
        </button>
      </div>
      <ul className="element-list">
        {currentZkspcZones.map((zone) => (
          <li key={`zkspc-${zone.id ?? zone.zone_number}`} className="element-item" style={{ alignItems: 'flex-start' }}>
            <div style={{ width: '100%' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{ width: '12px', height: '12px', borderRadius: '50%', background: getZkspcColor(zone.zone_number), display: 'inline-block' }} />
                <strong>{zone.name || `ЗКСПС ${zone.zone_number}`}</strong>
              </div>
              <div style={{ fontSize: '11px', color: '#6c757d' }}>
                Площадь: {Number(zone.area_sqm || 0).toFixed(2)} м2 • Помещений: {zone.room_ids?.length || 0}
              </div>
              <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginTop: '6px' }}>
                {(zone.room_ids || []).map((roomId) => {
                  const room = visibleRooms.find((item) => item.id === roomId);
                  return (
                    <button
                      key={`zkspc-room-${zone.id ?? zone.zone_number}-${roomId}`}
                      className={`tool-button ${selectedZkspcRooms.includes(roomId) ? 'active' : ''}`}
                      style={{ fontSize: '11px', padding: '3px 6px' }}
                      onClick={() => onToggleRoom(roomId)}
                    >
                      {room?.name || `Помещение ${roomDisplayNumberMap[roomId] ?? roomId}`}
                    </button>
                  );
                })}
              </div>
              {(zone.compliance_warnings || []).map((warning, index) => (
                <div key={`zkspc-warning-${zone.id ?? zone.zone_number}-${index}`} style={{ fontSize: '11px', color: '#b45309', marginTop: '4px' }}>
                  {warning}
                </div>
              ))}
            </div>
            <div style={{ display: 'flex', gap: '4px', marginLeft: '8px' }}>
              <button
                className="tool-button"
                style={{ fontSize: '11px', padding: '3px 6px' }}
                onClick={() => onMoveSelectedRoomsToZone(zone.id ?? zone.zone_number)}
                disabled={!selectedZkspcRooms.length}
              >
                Перенести
              </button>
              <button className="tool-button" style={{ fontSize: '11px', padding: '3px 6px' }} onClick={() => onToggleLock(zone.id ?? zone.zone_number)}>
                {zone.is_locked ? 'Unlock' : 'Lock'}
              </button>
              <button className="tool-button" style={{ fontSize: '11px', padding: '3px 6px' }} onClick={() => onSplit(zone.id ?? zone.zone_number)}>
                Split
              </button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
