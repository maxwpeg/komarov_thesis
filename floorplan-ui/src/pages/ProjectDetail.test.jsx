import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

import ProjectDetail from './ProjectDetail';
import { floorPlansApi, projectsApi } from '../api/client';

const mockNavigate = jest.fn();
let createElementSpy;
let consoleErrorSpy;
let consoleWarnSpy;

jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useParams: () => ({ projectId: '10' }),
  useNavigate: () => mockNavigate,
}));

jest.mock('../api/client', () => ({
  floorPlansApi: {
    list: jest.fn(),
    create: jest.fn(),
    remove: jest.fn(),
  },
  projectsApi: {
    get: jest.fn(),
    update: jest.fn(),
    remove: jest.fn(),
    generatePdf: jest.fn(),
  },
}));

const projectResponse = {
  id: 10,
  facility: 'Объект',
  code: 'P-01',
  project_type: 'СПС',
  year: 2026,
  contractor: 'Подрядчик',
  engineer: 'Инженер',
  facility_address: 'Адрес',
  project_description: 'Описание',
};

beforeEach(() => {
  jest.clearAllMocks();
  projectsApi.get.mockResolvedValue(projectResponse);
  floorPlansApi.list.mockResolvedValue([]);
  projectsApi.generatePdf.mockResolvedValue({
    blob: jest.fn().mockResolvedValue(new Blob(['pdf'], { type: 'application/pdf' })),
    headers: {
      get: jest.fn(() => 'attachment; filename="generated.pdf"'),
    },
  });
  window.alert = jest.fn();
  window.confirm = jest.fn(() => true);
  window.URL.createObjectURL = jest.fn(() => 'blob:test-pdf');
  window.URL.revokeObjectURL = jest.fn();

  const originalCreateElement = document.createElement.bind(document);
  createElementSpy = jest.spyOn(document, 'createElement').mockImplementation((tagName, options) => {
    const element = originalCreateElement(tagName, options);
    if (String(tagName).toLowerCase() === 'a') {
      element.click = jest.fn();
    }
    return element;
  });
  consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
  consoleWarnSpy = jest.spyOn(console, 'warn').mockImplementation(() => {});
});

afterEach(() => {
  createElementSpy?.mockRestore();
  consoleErrorSpy?.mockRestore();
  consoleWarnSpy?.mockRestore();
});

function renderProjectDetail() {
  return render(
    <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <ProjectDetail />
    </MemoryRouter>,
  );
}

test('successful PDF generation downloads without showing a success alert', async () => {
  renderProjectDetail();

  await screen.findByRole('heading', { name: 'Объект' });
  userEvent.click(screen.getByRole('button', { name: /Сгенерировать PDF/i }));

  await waitFor(() => {
    expect(projectsApi.generatePdf).toHaveBeenCalledWith('10');
  });

  expect(window.URL.createObjectURL).toHaveBeenCalled();
  expect(window.URL.revokeObjectURL).toHaveBeenCalledWith('blob:test-pdf');
  expect(window.alert).not.toHaveBeenCalled();
});

test('failed PDF generation still shows the error alert', async () => {
  projectsApi.generatePdf.mockRejectedValueOnce(new Error('boom'));

  renderProjectDetail();

  await screen.findByRole('heading', { name: 'Объект' });
  userEvent.click(screen.getByRole('button', { name: /Сгенерировать PDF/i }));

  await waitFor(() => {
    expect(window.alert).toHaveBeenCalledTimes(1);
  });

  expect(window.alert.mock.calls[0][0]).toMatch(/Ошибка при генерации PDF/i);
});
