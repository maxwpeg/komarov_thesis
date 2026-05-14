import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import { backgroundTasksApi } from '../api/client';
import { useDialogs } from '../ui/DialogProvider';
import WorkerTasksPage from './WorkerTasksPage';

jest.mock('../api/client', () => ({
  backgroundTasksApi: {
    list: jest.fn(),
    cancel: jest.fn(),
  },
}));

jest.mock('../ui/DialogProvider', () => ({
  useDialogs: jest.fn(),
}));

describe('WorkerTasksPage', () => {
  beforeEach(() => {
    useDialogs.mockReturnValue({
      confirm: jest.fn().mockResolvedValue(true),
      toast: jest.fn(),
    });
  });

  afterEach(() => {
    jest.resetAllMocks();
  });

  test('renders queued tasks and lets admin cancel them', async () => {
    backgroundTasksApi.list
      .mockResolvedValueOnce([
        {
          id: 12,
          task_type: 'project_pdf_generate',
          status: 'queued',
          requested_by_user: { full_name: 'Admin' },
          project_id: 7,
          attempts: 0,
          created_at: '2026-04-22T10:00:00Z',
        },
      ])
      .mockResolvedValueOnce([
        {
          id: 12,
          task_type: 'project_pdf_generate',
          status: 'canceled',
          requested_by_user: { full_name: 'Admin' },
          project_id: 7,
          attempts: 0,
          created_at: '2026-04-22T10:00:00Z',
          finished_at: '2026-04-22T10:01:00Z',
        },
      ]);
    backgroundTasksApi.cancel.mockResolvedValue({ id: 12, status: 'canceled' });

    render(
      <MemoryRouter>
        <WorkerTasksPage />
      </MemoryRouter>,
    );

    expect(await screen.findByRole('cell', { name: 'Генерация PDF' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Отменить' }));

    await waitFor(() => {
      expect(backgroundTasksApi.cancel).toHaveBeenCalledWith(12);
    });
    await waitFor(() => {
      expect(screen.getByText('Отменена', { selector: '.training-status' })).toBeInTheDocument();
    });
  });
});
