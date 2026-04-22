import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import ProjectList from './ProjectList';

describe('ProjectList', () => {
  beforeEach(() => {
    global.fetch = jest.fn();
    window.confirm = jest.fn(() => true);
    window.alert = jest.fn();
  });

  afterEach(() => {
    jest.resetAllMocks();
  });

  test('loads and renders projects, then deletes a project after confirmation', async () => {
    global.fetch
      .mockResolvedValueOnce({
        ok: true,
        json: jest.fn().mockResolvedValue([
          {
            id: 1,
            name: 'Project 1',
            facility: 'Объект 1',
            code: 'PRJ-001',
            project_type: 'PS',
            number_of_floors: 2,
            contractor: 'ООО Подрядчик',
            created_at: '2026-04-22T10:00:00Z',
          },
        ]),
      })
      .mockResolvedValueOnce({ ok: true, json: jest.fn().mockResolvedValue({}) })
      .mockResolvedValueOnce({
        ok: true,
        json: jest.fn().mockResolvedValue([]),
      });

    render(
      <MemoryRouter>
        <ProjectList />
      </MemoryRouter>,
    );

    expect(screen.getByText(/Загрузка проектов/i)).toBeInTheDocument();
    expect(await screen.findByText('Объект 1')).toBeInTheDocument();
    expect(screen.getByText(/PRJ-001/i)).toBeInTheDocument();

    fireEvent.click(screen.getByTitle(/Удалить проект/i));

    await waitFor(() => {
      expect(window.confirm).toHaveBeenCalled();
      expect(global.fetch).toHaveBeenCalledWith('/api/projects/1', { method: 'DELETE' });
    });
    expect(await screen.findByText(/Пока нет проектов/i)).toBeInTheDocument();
  });

  test('shows alert when deleting a project fails', async () => {
    global.fetch
      .mockResolvedValueOnce({
        ok: true,
        json: jest.fn().mockResolvedValue([
          {
            id: 2,
            name: 'Project 2',
            facility: 'Объект 2',
            code: 'PRJ-002',
            project_type: 'PS',
            number_of_floors: 1,
            contractor: 'ООО Подрядчик',
            created_at: '2026-04-22T10:00:00Z',
          },
        ]),
      })
      .mockResolvedValueOnce({ ok: false, json: jest.fn().mockResolvedValue({}) });

    render(
      <MemoryRouter>
        <ProjectList />
      </MemoryRouter>,
    );

    expect(await screen.findByText('Объект 2')).toBeInTheDocument();
    fireEvent.click(screen.getByTitle(/Удалить проект/i));

    await waitFor(() => {
      expect(window.alert).toHaveBeenCalled();
    });
  });
});
