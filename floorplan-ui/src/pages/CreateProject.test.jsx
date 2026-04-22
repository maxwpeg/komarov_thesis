import React from 'react';
import { render, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

import CreateProject from './CreateProject';
import { projectsApi } from '../api/client';

const mockNavigate = jest.fn();

jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useNavigate: () => mockNavigate,
}));

jest.mock('../api/client', () => ({
  projectsApi: {
    create: jest.fn(),
  },
}));

beforeEach(() => {
  jest.clearAllMocks();
  projectsApi.create.mockResolvedValue({ id: 55 });
});

test('create project submits facility case fields and auto-fills them from facility name', async () => {
  const { container } = render(
    <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <CreateProject />
    </MemoryRouter>,
  );

  const nameInput = container.querySelector('input[name="name"]');
  const facilityInput = container.querySelector('input[name="facility"]');
  const genitiveInput = container.querySelector('input[name="facility_genitive"]');
  const instrumentalInput = container.querySelector('input[name="facility_instrumental"]');
  const submitButton = container.querySelector('button[type="submit"]');

  expect(nameInput).not.toBeNull();
  expect(facilityInput).not.toBeNull();
  expect(genitiveInput).not.toBeNull();
  expect(instrumentalInput).not.toBeNull();
  expect(submitButton).not.toBeNull();

  await userEvent.type(nameInput, 'Проект 01');
  await userEvent.type(facilityInput, 'Административное здание');

  expect(genitiveInput).toHaveValue('Административное здание');
  expect(instrumentalInput).toHaveValue('Административное здание');

  await userEvent.clear(genitiveInput);
  await userEvent.type(genitiveInput, 'Административного здания');
  await userEvent.clear(instrumentalInput);
  await userEvent.type(instrumentalInput, 'Административным зданием');
  await userEvent.click(submitButton);

  await waitFor(() => {
    expect(projectsApi.create).toHaveBeenCalledWith(expect.objectContaining({
      name: 'Проект 01',
      facility: 'Административное здание',
      facility_genitive: 'Административного здания',
      facility_instrumental: 'Административным зданием',
    }));
  });

  expect(mockNavigate).toHaveBeenCalledWith('/projects/55');
});
