import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import App from './App';

jest.mock('./pages/ProjectList', () => () => <div>project-list-page</div>);
jest.mock('./pages/CreateProject', () => () => <div>create-project-page</div>);
jest.mock('./pages/EquipmentCatalogPage', () => () => <div>equipment-page</div>);
jest.mock('./pages/RecognitionTrainingPage', () => () => <div>recognition-page</div>);
jest.mock('./pages/ProjectDetail', () => () => <div>project-detail-page</div>);
jest.mock('./pages/FloorPlanEditor', () => () => <div>editor-page</div>);

test('navbar exposes equipment tab and routes to the equipment page', async () => {
  render(<App />);

  expect(screen.getByRole('link', { name: 'Оборудование' })).toBeInTheDocument();

  await userEvent.click(screen.getByRole('link', { name: 'Оборудование' }));

  expect(screen.getByText('equipment-page')).toBeInTheDocument();
});
