import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

import RecognitionTrainingPage from './RecognitionTrainingPage';
import { backgroundTasksApi, recognitionTrainingApi } from '../api/client';
import { useDialogs } from '../ui/DialogProvider';

jest.mock('../api/client', () => ({
  backgroundTasksApi: {
    get: jest.fn(),
  },
  recognitionTrainingApi: {
    getOverview: jest.fn(),
    listExamples: jest.fn(),
    getExample: jest.fn(),
    updateExample: jest.fn(),
    bulkCurate: jest.fn(),
    listRuns: jest.fn(),
    getRunLog: jest.fn(),
    createRun: jest.fn(),
  },
}));

jest.mock('../ui/DialogProvider', () => ({
  useDialogs: jest.fn(),
}));

const overviewResponse = {
  detector_version: 'cv.hybrid.v1',
  steps: [
    {
      step: 'walls',
      detector_version: 'cv.hybrid.v1',
      approved_examples: 5,
      excluded_examples: 1,
      selected_for_batch: 4,
      recommended_batch_size: 50,
      thresholds: { approved_examples: 50, minimum_hard_examples: 10, minimum_labeled_openings: null, max_idle_days: 14, minimum_real_correction_ratio: 0.2 },
      next_batch_hint: { reason: 'waiting_for_more_wall_examples', eligible: false },
      last_successful_run: null,
      training_defaults: { model: 'yolov8n-seg.pt', epochs: 80, imgsz: 1024, batch: -1, patience: 15, device: 'auto' },
    },
    {
      step: 'openings',
      detector_version: 'cv.hybrid.v1',
      approved_examples: 7,
      excluded_examples: 0,
      selected_for_batch: 6,
      recommended_batch_size: 75,
      thresholds: { approved_examples: 75, minimum_hard_examples: null, minimum_labeled_openings: 200, max_idle_days: 14, minimum_real_correction_ratio: 0.2 },
      next_batch_hint: { reason: 'approved_examples_threshold_met', eligible: true },
      last_successful_run: null,
      training_defaults: { model: 'yolov8n-seg.pt', epochs: 120, imgsz: 1280, batch: -1, patience: 20, device: 'auto' },
    },
  ],
};

const examplesResponse = [
  {
    id: 101,
    step: 'walls',
    floor_plan_id: 11,
    floor_plan_name: 'Этаж 1',
    floor_number: 1,
    project_id: 7,
    project_name: 'Объект',
    project_code: 'P-01',
    submitted_at: '2026-04-16T10:00:00Z',
    hardness_score: 4.5,
    changed: true,
    issue_tags: ['missed'],
    notes: 'Исходная заметка',
    curation_status: 'approved',
    times_used: 2,
  },
];

const detailResponse = {
  ...examplesResponse[0],
  step_revision: 3,
  detector_version: 'cv.hybrid.v1',
  source_snapshot: { image: { width: 400, height: 300, original_image_path: 'uploads/test-floor.png', scale_factor: 10 }, walls: [{ id: 1, x1: 10, y1: 30, x2: 200, y2: 30, thickness: 200 }] },
  corrected_snapshot: { image: { width: 400, height: 300, original_image_path: 'uploads/test-floor.png', scale_factor: 10 }, walls: [{ id: 1, x1: 10, y1: 35, x2: 220, y2: 35, thickness: 200 }] },
  diff_summary: { changed: true, hardness_score: 4.5 },
  original_image_path: 'uploads/test-floor.png',
  batches: [],
  runs: [],
};

beforeEach(() => {
  jest.clearAllMocks();
  useDialogs.mockReturnValue({
    confirm: jest.fn().mockResolvedValue(true),
    toast: jest.fn(),
  });
  recognitionTrainingApi.getOverview.mockResolvedValue(overviewResponse);
  recognitionTrainingApi.listExamples.mockResolvedValue(examplesResponse);
  recognitionTrainingApi.getExample.mockResolvedValue(detailResponse);
  recognitionTrainingApi.updateExample.mockResolvedValue(detailResponse);
  recognitionTrainingApi.bulkCurate.mockResolvedValue({ updated_count: 1, curation_status: 'excluded' });
  recognitionTrainingApi.listRuns.mockResolvedValue([]);
  recognitionTrainingApi.getRunLog.mockResolvedValue({ run_id: 'run-1', log_path: 'stdout.log', content: 'line 1' });
  backgroundTasksApi.get.mockResolvedValue({ id: 1001, status: 'succeeded' });
  recognitionTrainingApi.createRun.mockResolvedValue({
    id: 1001,
    status: 'queued',
    task_type: 'recognition_training_run',
  });
});

function renderPage() {
  return render(
    <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <RecognitionTrainingPage />
    </MemoryRouter>,
  );
}

test('renders overview and loads the selected example detail', async () => {
  renderPage();

  await screen.findByRole('heading', { name: 'Дообучение распознавания' });
  expect(await screen.findByDisplayValue('Исходная заметка')).toBeInTheDocument();
  await waitFor(() => {
    expect(recognitionTrainingApi.getExample).toHaveBeenCalledWith(101);
  });
});

test('bulk exclude and create run call the expected APIs', async () => {
  renderPage();

  await screen.findByRole('heading', { name: 'Дообучение распознавания' });
  await waitFor(() => {
    expect(recognitionTrainingApi.getExample).toHaveBeenCalledWith(101);
  });

  await userEvent.click(screen.getAllByRole('checkbox')[1]);
  await userEvent.click(screen.getByRole('button', { name: 'Exclude' }));

  await waitFor(() => {
    expect(recognitionTrainingApi.bulkCurate).toHaveBeenCalledWith({
      example_ids: [101],
      curation_status: 'excluded',
    });
  });

  await userEvent.click(screen.getByRole('button', { name: 'Запустить walls' }));

  await waitFor(() => {
    expect(recognitionTrainingApi.createRun).toHaveBeenCalledWith({
      step: 'walls',
      epochs: 80,
      imgsz: 1024,
      batch: -1,
      patience: 15,
      force: true,
    });
  });
  expect(useDialogs().confirm).toHaveBeenCalled();
});

test('shows readable missing image message in the example preview', async () => {
  recognitionTrainingApi.getExample.mockResolvedValue({
    ...detailResponse,
    original_image_path: '',
    original_image_url: '',
    source_snapshot: { image: { width: 400, height: 300 }, walls: [] },
    corrected_snapshot: { image: { width: 400, height: 300 }, walls: [] },
  });

  renderPage();

  expect(await screen.findByText('Исходное изображение плана недоступно.')).toBeInTheDocument();
});
