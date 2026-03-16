import { useCallback } from 'react';

import { normalizeSignalSystemType } from './helpers';

export function useSignalBranchState(setPipelineState) {
  return useCallback((systemType, updates = {}) => {
    const normalizedSystem = normalizeSignalSystemType(systemType);
    setPipelineState((prev) => {
      if (!prev) {
        return prev;
      }
      const currentBranch = prev.branches?.[normalizedSystem] || { active_step: 'fire_alarms', steps: {} };
      return {
        ...prev,
        active_signal_system_type: normalizedSystem,
        branches: {
          ...(prev.branches || {}),
          [normalizedSystem]: {
            ...currentBranch,
            active_step: updates.activeStep || currentBranch.active_step || 'fire_alarms',
            steps: {
              ...currentBranch.steps,
              fire_alarms: {
                ...(currentBranch.steps?.fire_alarms || { status: 'draft', revision: 0 }),
                ...(updates.fireAlarmsStatus ? { status: updates.fireAlarmsStatus } : {}),
              },
              devices_cables: {
                ...(currentBranch.steps?.devices_cables || { status: 'draft', revision: 0 }),
                ...(updates.devicesCablesStatus ? { status: updates.devicesCablesStatus } : {}),
              },
            },
          },
        },
      };
    });
  }, [setPipelineState]);
}
