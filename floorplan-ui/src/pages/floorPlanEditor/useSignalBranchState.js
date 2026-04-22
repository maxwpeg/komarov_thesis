import { useCallback } from 'react';

import { COMMON_SIGNAL_SYSTEM, normalizeSignalSystemType } from './helpers';

function createStepState(status = 'locked') {
  return { status, revision: 0 };
}

export function useSignalBranchState(setPipelineState) {
  return useCallback((systemType, updates = {}) => {
    const normalizedSystem = normalizeSignalSystemType(systemType);
    setPipelineState((prev) => {
      if (!prev) {
        return prev;
      }

      const currentBranch = prev.branches?.[normalizedSystem] || { active_step: 'signal_instruments', steps: {} };
      const currentSteps = currentBranch.steps || {};

      const nextBranch = {
        ...currentBranch,
        active_step: updates.activeStep || currentBranch.active_step || 'signal_instruments',
        steps: {
          signal_instruments: {
            ...createStepState(normalizedSystem === COMMON_SIGNAL_SYSTEM ? 'draft' : 'locked'),
            ...(currentSteps.signal_instruments || {}),
            ...(updates.signalInstrumentsStatus ? { status: updates.signalInstrumentsStatus } : {}),
          },
          fire_alarms: {
            ...createStepState('locked'),
            ...(currentSteps.fire_alarms || {}),
            ...(updates.fireAlarmsStatus ? { status: updates.fireAlarmsStatus } : {}),
          },
          devices_cables: {
            ...createStepState('locked'),
            ...(currentSteps.devices_cables || {}),
            ...(updates.devicesCablesStatus ? { status: updates.devicesCablesStatus } : {}),
          },
          soue_devices: {
            ...createStepState('locked'),
            ...(currentSteps.soue_devices || {}),
            ...(updates.soueDevicesStatus ? { status: updates.soueDevicesStatus } : {}),
          },
          soue_cables: {
            ...createStepState('locked'),
            ...(currentSteps.soue_cables || {}),
            ...(updates.soueCablesStatus ? { status: updates.soueCablesStatus } : {}),
          },
        },
      };

      return {
        ...prev,
        active_signal_system_type: normalizedSystem === COMMON_SIGNAL_SYSTEM
          ? prev.active_signal_system_type
          : normalizedSystem,
        branches: {
          ...(prev.branches || {}),
          [normalizedSystem]: nextBranch,
        },
      };
    });
  }, [setPipelineState]);
}
