import React, { useEffect, useState } from 'react';
import { render, screen } from '@testing-library/react';

import { useSignalBranchState } from './useSignalBranchState';

function HookHarness({ systemType = 'addressable', updates = {} }) {
  const [pipelineState, setPipelineState] = useState({
    active_signal_system_type: 'non_addressable',
    branches: {},
  });
  const updateBranch = useSignalBranchState(setPipelineState);

  useEffect(() => {
    updateBranch(systemType, updates);
  }, [systemType, updates, updateBranch]);

  return <pre>{JSON.stringify(pipelineState)}</pre>;
}

describe('useSignalBranchState', () => {
  test('creates or updates a branch and keeps common branch from overriding active signal type', async () => {
    const { rerender } = render(
      <HookHarness
        systemType="addressable"
        updates={{ activeStep: 'fire_alarms', signalInstrumentsStatus: 'validated', fireAlarmsStatus: 'draft' }}
      />,
    );

    expect(await screen.findByText(/"active_signal_system_type":"addressable"/)).toBeInTheDocument();
    expect(screen.getByText(/"active_step":"fire_alarms"/)).toBeInTheDocument();
    expect(screen.getByText(/"signal_instruments":{"status":"validated","revision":0}/)).toBeInTheDocument();

    rerender(
      <HookHarness
        systemType="common"
        updates={{ signalInstrumentsStatus: 'draft', soueCablesStatus: 'validated' }}
      />,
    );

    expect(await screen.findByText(/"active_signal_system_type":"addressable"/)).toBeInTheDocument();
    expect(screen.getByText(/"common":/)).toBeInTheDocument();
    expect(screen.getByText(/"soue_cables":{"status":"validated","revision":0}/)).toBeInTheDocument();
  });
});
