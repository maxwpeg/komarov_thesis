import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import { useAuth } from '../auth/AuthContext';
import { projectsApi } from '../api/client';
import ProjectList from './ProjectList';

jest.mock('../auth/AuthContext', () => ({
  useAuth: jest.fn(),
}));

jest.mock('../api/client', () => ({
  projectsApi: {
    list: jest.fn(),
    remove: jest.fn(),
  },
}));

describe('ProjectList', () => {
  beforeEach(() => {
    window.confirm = jest.fn(() => true);
    window.alert = jest.fn();
    useAuth.mockReturnValue({
      user: { role: 'developer', full_name: 'Dev User' },
    });
  });

  afterEach(() => {
    jest.resetAllMocks();
  });

  test('loads and renders projects with owner, then deletes a project after confirmation', async () => {
    projectsApi.list
      .mockResolvedValueOnce([
        {
          id: 1,
          name: 'Project 1',
          facility: 'Объект 1',
          code: 'PRJ-001',
          project_type: 'PS',
          number_of_floors: 2,
          contractor: 'ООО Подрядчик',
          owner_user: { full_name: 'Engineer One' },
          created_at: '2026-04-22T10:00:00Z',
        },
      ])
      .mockResolvedValueOnce([]);
    projectsApi.remove.mockResolvedValue({});

    render(
      <MemoryRouter>
        <ProjectList />
      </MemoryRouter>,
    );

    expect(screen.getByText(/Загрузка проектов/i)).toBeInTheDocument();
    expect(await screen.findByText('Объект 1')).toBeInTheDocument();
    expect(screen.getByText(/PRJ-001/i)).toBeInTheDocument();
    expect(screen.getByText(/Engineer One/i)).toBeInTheDocument();

    fireEvent.click(screen.getByTitle(/Удалить проект/i));

    await waitFor(() => {
      expect(window.confirm).toHaveBeenCalled();
      expect(projectsApi.remove).toHaveBeenCalledWith(1);
    });
    expect(await screen.findByText(/Пока нет проектов/i)).toBeInTheDocument();
  });

  test('shows alert when deleting a project fails', async () => {
    projectsApi.list.mockResolvedValue([
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
    ]);
    projectsApi.remove.mockRejectedValue(new Error('boom'));

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
