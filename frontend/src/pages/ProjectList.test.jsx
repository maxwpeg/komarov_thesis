import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import { useAuth } from '../auth/AuthContext';
import { projectsApi } from '../api/client';
import { useDialogs } from '../ui/DialogProvider';
import ProjectList from './ProjectList';

jest.mock('../auth/AuthContext', () => ({
  useAuth: jest.fn(),
}));

jest.mock('../api/client', () => ({
  projectsApi: {
    list: jest.fn(),
    listTrash: jest.fn(),
    remove: jest.fn(),
    permanentlyRemove: jest.fn(),
  },
}));

jest.mock('../ui/DialogProvider', () => ({
  useDialogs: jest.fn(),
}));

describe('ProjectList', () => {
  beforeEach(() => {
    useAuth.mockReturnValue({
      user: { role: 'developer', full_name: 'Dev User' },
    });
    useDialogs.mockReturnValue({
      confirm: jest.fn().mockResolvedValue(true),
      toast: jest.fn(),
    });
  });

  afterEach(() => {
    jest.resetAllMocks();
  });

  test('loads and renders projects with owner, then moves a project to trash after confirmation', async () => {
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
    projectsApi.listTrash
      .mockResolvedValueOnce([])
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
          deleted_by_user: { full_name: 'Dev User' },
          deleted_at: '2026-04-23T10:00:00Z',
          created_at: '2026-04-22T10:00:00Z',
        },
      ]);
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

    fireEvent.click(screen.getByTitle(/Переместить проект/i));

    await waitFor(() => {
      expect(useDialogs().confirm).toHaveBeenCalled();
      expect(projectsApi.remove).toHaveBeenCalledWith(1);
    });
    expect(await screen.findByText(/Пока нет проектов/i)).toBeInTheDocument();
    expect(await screen.findByText(/Корзина проектов/i)).toBeInTheDocument();
    expect(screen.getByText(/Dev User/i)).toBeInTheDocument();
  });

  test('shows toast when deleting a project fails', async () => {
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
    projectsApi.listTrash.mockResolvedValue([]);
    projectsApi.remove.mockRejectedValue(new Error('boom'));
    const dialogs = {
      confirm: jest.fn().mockResolvedValue(true),
      toast: jest.fn(),
    };
    useDialogs.mockReturnValue(dialogs);

    render(
      <MemoryRouter>
        <ProjectList />
      </MemoryRouter>,
    );

    expect(await screen.findByText('Объект 2')).toBeInTheDocument();
    fireEvent.click(screen.getByTitle(/Переместить проект/i));

    await waitFor(() => {
      expect(dialogs.toast).toHaveBeenCalledWith('Ошибка при удалении проекта.', { tone: 'error' });
    });
  });

  test('developer can permanently delete a project from trash', async () => {
    projectsApi.list.mockResolvedValue([]);
    projectsApi.listTrash
      .mockResolvedValueOnce([
        {
          id: 5,
          name: 'Trash',
          facility: 'Проект в корзине',
          code: 'TR-005',
          project_type: 'PS',
          number_of_floors: 1,
          contractor: 'ООО Подрядчик',
          deleted_at: '2026-04-22T10:00:00Z',
        },
      ])
      .mockResolvedValueOnce([]);
    projectsApi.permanentlyRemove.mockResolvedValue({});

    render(
      <MemoryRouter>
        <ProjectList />
      </MemoryRouter>,
    );

    expect(await screen.findByText('Проект в корзине')).toBeInTheDocument();
    fireEvent.click(screen.getByTitle(/Удалить проект окончательно/i));

    await waitFor(() => {
      expect(projectsApi.permanentlyRemove).toHaveBeenCalledWith(5);
    });
  });
});
