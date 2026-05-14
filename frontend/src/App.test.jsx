import React from 'react';
import { render, screen } from '@testing-library/react';

import { useAuth } from './auth/AuthContext';
import App from './App';

jest.mock('./auth/AuthContext', () => ({
  AuthProvider: ({ children }) => children,
  useAuth: jest.fn(),
}));

jest.mock('./pages/ProjectList', () => () => <div>project-list-page</div>);
jest.mock('./pages/CreateProject', () => () => <div>create-project-page</div>);
jest.mock('./pages/EquipmentCatalogPage', () => () => <div>equipment-page</div>);
jest.mock('./pages/RecognitionTrainingPage', () => () => <div>recognition-page</div>);
jest.mock('./pages/ProjectDetail', () => () => <div>project-detail-page</div>);
jest.mock('./pages/FloorPlanEditor', () => () => <div>editor-page</div>);
jest.mock('./pages/LoginPage', () => () => <div>login-page</div>);
jest.mock('./pages/UsersPage', () => () => <div>users-page</div>);

function setAuthState(overrides = {}) {
  useAuth.mockReturnValue({
    user: { full_name: 'Developer User', role: 'developer' },
    isLoading: false,
    isAuthenticated: true,
    logout: jest.fn(),
    welcomeState: { visible: false, fullName: '' },
    dismissWelcome: jest.fn(),
    ...overrides,
  });
}

beforeEach(() => {
  window.history.pushState({}, '', '/');
  jest.clearAllMocks();
});

test('developer navbar exposes recognition training and users sections', () => {
  setAuthState();
  render(<App />);

  expect(screen.getByRole('link', { name: 'Оборудование' })).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Дообучение' })).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Пользователи' })).toBeInTheDocument();
  expect(screen.getByText('project-list-page')).toBeInTheDocument();
});

test('engineer navbar hides developer-only sections', () => {
  setAuthState({
    user: { full_name: 'Engineer User', role: 'engineer' },
  });
  render(<App />);

  expect(screen.getByRole('link', { name: 'Оборудование' })).toBeInTheDocument();
  expect(screen.queryByRole('link', { name: 'Дообучение' })).not.toBeInTheDocument();
  expect(screen.queryByRole('link', { name: 'Пользователи' })).not.toBeInTheDocument();
});

test('redirects anonymous users to the login page', () => {
  setAuthState({
    user: null,
    isAuthenticated: false,
  });
  render(<App />);

  expect(screen.getByText('login-page')).toBeInTheDocument();
});
