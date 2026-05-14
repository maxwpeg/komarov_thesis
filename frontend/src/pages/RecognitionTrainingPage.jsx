import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';

import { recognitionTrainingApi } from '../api/client';
import { useDialogs } from '../ui/DialogProvider';
import { pollTaskUntilSettled } from '../utils/backgroundTasks';

const HINT_REASON_LABELS = {
  approved_examples_threshold_met: 'Готово по порогу примеров',
  idle_window_and_hard_examples_met: 'Готово по hard-примерам и окну простоя',
  idle_window_and_label_requirements_met: 'Готово по разметке и окну простоя',
  no_approved_examples: 'Нет одобренных примеров',
  insufficient_real_corrections: 'Слишком мало реальных исправлений',
  waiting_for_more_wall_examples: 'Нужно больше wall-примеров',
  waiting_for_more_opening_examples: 'Нужно больше opening-примеров',
  not_ready: 'Пакет еще не готов',
};

const RUN_STATUS_LABELS = {
  queued: 'В очереди',
  running: 'Обучается',
  succeeded: 'Успешно',
  failed: 'Ошибка',
  canceled: 'Отменен',
};

const INITIAL_FILTERS = {
  step: '',
  curation_status: '',
  project_id: '',
  floor_plan_id: '',
  changed_only: false,
  search: '',
  sort_by: 'submitted_at',
  sort_dir: 'desc',
};

const INITIAL_RUN_FILTERS = {
  step: '',
  status: '',
};

function buildImageUrl(urlOrPath) {
  if (!urlOrPath) {
    return null;
  }
  if (/^(https?:)?\/\//i.test(urlOrPath) || String(urlOrPath).startsWith('/')) {
    return urlOrPath;
  }
  return `/${String(urlOrPath).replace(/\\/g, '/')}`;
}

function formatDateTime(value) {
  if (!value) {
    return '—';
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString('ru-RU');
}

function getHintLabel(reason) {
  return HINT_REASON_LABELS[reason] || reason || '—';
}

function getRunStatusLabel(status) {
  return RUN_STATUS_LABELS[status] || status || '—';
}

function formatMetricValue(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return '—';
  }
  const numeric = Number(value);
  return Math.abs(numeric) >= 100 ? numeric.toFixed(1) : numeric.toFixed(3);
}

function getSnapshotOpenings(snapshot) {
  if (!snapshot) {
    return [];
  }
  if (Array.isArray(snapshot.openings)) {
    return snapshot.openings;
  }
  const doors = (snapshot.doors || []).map((door) => ({
    ...door,
    type: 'door',
    bbox: door.bbox || [door.x, door.y, door.x + door.width, door.y + door.height],
  }));
  const windows = (snapshot.windows || []).map((windowItem) => ({
    ...windowItem,
    type: 'window',
    bbox: windowItem.bbox || [windowItem.x, windowItem.y, windowItem.x + windowItem.width, windowItem.y + windowItem.height],
  }));
  return [...doors, ...windows];
}

function SnapshotOverlay({ snapshot, color, mode }) {
  if (!snapshot) {
    return null;
  }
  const image = snapshot.image || {};
  const scaleFactor = Number(image.scale_factor || 1) || 1;
  return (
    <>
      {(snapshot.walls || []).map((wall, index) => (
        <line
          key={`${mode}-wall-${wall.id || index}`}
          x1={wall.x1}
          y1={wall.y1}
          x2={wall.x2}
          y2={wall.y2}
          stroke={color}
          strokeOpacity={0.92}
          strokeWidth={Math.max(Number(wall.thickness || wall.thickness_px || 1) / scaleFactor, 1)}
          strokeLinecap="round"
        />
      ))}
      {getSnapshotOpenings(snapshot).map((opening, index) => {
        const bbox = opening.bbox || [opening.x, opening.y, opening.x + opening.width, opening.y + opening.height];
        return (
          <rect
            key={`${mode}-opening-${opening.id || index}`}
            x={bbox[0]}
            y={bbox[1]}
            width={Math.max(bbox[2] - bbox[0], 1)}
            height={Math.max(bbox[3] - bbox[1], 1)}
            fill={opening.type === 'door' ? `${color}33` : 'none'}
            stroke={color}
            strokeWidth={2}
            rx={2}
          />
        );
      })}
    </>
  );
}

function ExamplePreview({ detail, overlayMode }) {
  if (!detail) {
    return <div style={{ color: '#645f57' }}>Выберите пример из таблицы, чтобы увидеть diff и историю.</div>;
  }
  const imageMeta = detail.corrected_snapshot?.image || detail.source_snapshot?.image || {};
  const imageUrl = buildImageUrl(detail.original_image_url || detail.original_image_path || imageMeta.original_image_url || imageMeta.original_image_path);
  const width = Math.max(Number(imageMeta.width || 0), 1);
  const height = Math.max(Number(imageMeta.height || 0), 1);
  const showSource = overlayMode === 'source' || overlayMode === 'diff';
  const showCorrected = overlayMode === 'corrected' || overlayMode === 'diff';
  return (
    <div>
      {imageUrl ? (
        <div style={{ position: 'relative', borderRadius: '18px', overflow: 'hidden', border: '1px solid #d9d2c8', background: '#fff' }}>
          <img src={imageUrl} alt="План" style={{ display: 'block', width: '100%', height: 'auto' }} />
          <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="xMidYMid meet" style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }}>
            {showSource && <SnapshotOverlay snapshot={detail.source_snapshot} color="#d43d33" mode="source" />}
            {showCorrected && <SnapshotOverlay snapshot={detail.corrected_snapshot} color="#0f8f7c" mode="corrected" />}
          </svg>
        </div>
      ) : (
        <div style={{ padding: '1rem', borderRadius: '16px', background: '#f3efe8', color: '#645f57' }}>
          Исходное изображение плана недоступно.
        </div>
      )}
    </div>
  );
}

function StepTrainingCard({ stepOverview, runForm, onRunFieldChange, onCreateRun, creating }) {
  const step = stepOverview.step;
  const lastRun = stepOverview.last_successful_run;
  const activeModel = stepOverview.active_model;
  const recommendedBatchSize = Number(stepOverview.recommended_batch_size || 0);
  const selectedCount = Number(stepOverview.selected_for_batch || 0);

  return (
    <div className="training-card">
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', alignItems: 'flex-start', marginBottom: '1rem' }}>
        <div>
          <h3 style={{ margin: 0, textTransform: 'capitalize' }}>{step}</h3>
          <p style={{ margin: '0.35rem 0 0', color: '#645f57' }}>
            {getHintLabel(stepOverview.next_batch_hint?.reason)}. Selected: <strong>{selectedCount}</strong>
          </p>
        </div>
        <div style={{ background: '#f3efe8', padding: '0.55rem 0.8rem', borderRadius: '999px', color: '#645f57', fontSize: '0.92rem' }}>
          Detector: {stepOverview.detector_version}
        </div>
      </div>
      <div className="training-card-stats">
        <div><span>Approved</span><strong>{stepOverview.approved_examples}</strong></div>
        <div><span>Excluded</span><strong>{stepOverview.excluded_examples}</strong></div>
        <div><span>Selected</span><strong>{selectedCount}</strong></div>
        <div><span>Recommended batch</span><strong>{recommendedBatchSize || '—'}</strong></div>
      </div>
      <div style={{ color: '#645f57', marginBottom: '0.5rem' }}>
        Последний успешный run: <strong>{lastRun ? `${lastRun.run_id} · ${formatDateTime(lastRun.finished_at || lastRun.requested_at)}` : 'еще не было'}</strong>
      </div>
      <div style={{ color: '#645f57', marginBottom: '0.9rem' }}>
        Активная модель: <strong>{activeModel?.run_id || 'не выбрана'}</strong>
        {activeModel && <span> · {formatDateTime(activeModel.activated_at)}</span>}
      </div>
      {recommendedBatchSize > 0 && selectedCount < recommendedBatchSize && (
        <div style={{ marginBottom: '0.9rem', color: '#8a5b00', fontSize: '0.92rem' }}>
          Текущий batch меньше рекомендуемого: {selectedCount} из {recommendedBatchSize}.
        </div>
      )}
      <div className="training-run-form">
        <label>Epochs<input type="number" min="1" value={runForm.epochs} onChange={(event) => onRunFieldChange(step, 'epochs', event.target.value)} /></label>
        <label>Img size<input type="number" min="64" step="32" value={runForm.imgsz} onChange={(event) => onRunFieldChange(step, 'imgsz', event.target.value)} /></label>
        <label>Batch<input type="number" value={runForm.batch} onChange={(event) => onRunFieldChange(step, 'batch', event.target.value)} /></label>
        <label>Patience<input type="number" min="1" value={runForm.patience} onChange={(event) => onRunFieldChange(step, 'patience', event.target.value)} /></label>
      </div>
      <div style={{ marginTop: '1rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
        <span style={{ color: '#645f57', fontSize: '0.92rem' }}>
          Базовая модель: <strong>{stepOverview.training_defaults.model}</strong>, device: <strong>{stepOverview.training_defaults.device}</strong>
        </span>
        <button className="btn btn-primary" onClick={() => onCreateRun(step)} disabled={creating}>
          {creating ? 'Запуск...' : `Запустить ${step}`}
        </button>
      </div>
    </div>
  );
}

function RunArtifacts({ artifacts }) {
  if (!artifacts) {
    return null;
  }
  return (
    <div style={{ marginTop: '0.6rem', color: '#645f57', fontSize: '0.9rem' }}>
      <div>best.pt: {artifacts.has_best_checkpoint ? artifacts.best_checkpoint_path : 'нет'}</div>
      <div>last.pt: {artifacts.has_last_checkpoint ? artifacts.last_checkpoint_path : 'нет'}</div>
      <div>metrics.json: {artifacts.metrics_json_path || 'нет'}</div>
    </div>
  );
}

function RunCard({
  run,
  selected,
  collapsed,
  deleting,
  onSelect,
  onToggleCollapse,
  onActivate,
  onDelete,
  activating,
  runLog,
}) {
  const metrics = run.metrics_summary || {};
  const results = metrics.results || {};
  const resultEntries = Object.entries(results).slice(0, 4);
  const splitCounts = metrics.split_counts || run.batch?.summary?.split_counts || {};
  const hasBestCheckpoint = Boolean(run.artifacts?.has_best_checkpoint);
  const canDelete = ['succeeded', 'failed', 'canceled'].includes(run.status) && !run.is_active_for_step;
  const taskProgress = Math.max(0, Math.min(Number(run.background_task?.progress_percent || 0), 100));

  return (
    <div
      className={`training-run-item ${selected ? 'selected' : ''}`}
      onClick={() => onSelect(run.run_id)}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          onSelect(run.run_id);
        }
      }}
      role="button"
      tabIndex={0}
      style={{ width: '100%', textAlign: 'left', cursor: 'pointer' }}
    >
      <div className="training-run-item__header">
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
          <button
            type="button"
            className="training-run-item__toggle"
            onClick={(event) => {
              event.stopPropagation();
              onToggleCollapse(run.run_id);
            }}
            aria-label={collapsed ? 'Развернуть запуск' : 'Свернуть запуск'}
          >
            {collapsed ? '▸' : '▾'}
          </button>
          <strong>{run.run_id}</strong>
          <span className={`training-status training-status-${run.status}`}>{getRunStatusLabel(run.status)}</span>
          {run.is_active_for_step && <span className="training-status" style={{ background: '#d7f5ef', color: '#0f766e' }}>Активна</span>}
        </div>
        <div className="training-run-item__actions">
          <button
            type="button"
            className="btn btn-secondary"
            onClick={(event) => {
              event.stopPropagation();
              onSelect(run.run_id);
            }}
          >
            Выбрать
          </button>
          {canDelete && (
            <button
              type="button"
              className="btn btn-danger"
              onClick={(event) => {
                event.stopPropagation();
                onDelete(run.run_id);
              }}
              disabled={deleting}
            >
              {deleting ? 'Удаление...' : 'Удалить'}
            </button>
          )}
        </div>
      </div>

      <div style={{ marginTop: '0.45rem', color: '#645f57' }}>
        <strong>{run.step}</strong> · {formatDateTime(run.finished_at || run.started_at || run.requested_at)}
      </div>

      {run.background_task && (
        <div className="worker-task-progress training-run-progress">
          <div className="worker-task-progress__track">
            <span style={{ width: `${taskProgress}%` }} />
          </div>
          <small>{taskProgress}% {run.background_task.progress_stage || ''}</small>
        </div>
      )}

      {!collapsed && (
        <div className="training-run-item__body">
          <div style={{ marginTop: '0.35rem', color: '#645f57', fontSize: '0.92rem' }}>
            Samples: {run.batch?.summary?.sample_count ?? metrics.sample_count ?? 0}
            {' '}· dataset items: {metrics.dataset_item_count ?? run.batch?.summary?.dataset_item_count ?? '—'}
          </div>

          <div style={{ marginTop: '0.35rem', color: '#645f57', fontSize: '0.92rem' }}>
            Epochs {run.config?.epochs ?? '—'} · Img {run.config?.imgsz ?? '—'} · Batch {run.config?.batch ?? '—'} · Patience {run.config?.patience ?? '—'}
          </div>

          <div style={{ marginTop: '0.35rem', color: '#645f57', fontSize: '0.92rem' }}>
            Device: {metrics.requested_device || run.config?.device || '—'} → {metrics.resolved_device || '—'}
          </div>

          <div style={{ marginTop: '0.35rem', color: '#645f57', fontSize: '0.92rem' }}>
            Split: train {splitCounts.train ?? '—'} · val {splitCounts.val ?? '—'}
          </div>

          {resultEntries.length > 0 && (
            <div style={{ marginTop: '0.35rem', color: '#645f57', fontSize: '0.92rem' }}>
              {resultEntries.map(([key, value]) => `${key}: ${formatMetricValue(value)}`).join(' · ')}
            </div>
          )}

          <RunArtifacts artifacts={run.artifacts} />

          {run.error_message && (
            <div style={{ marginTop: '0.6rem', color: '#b91c1c', fontSize: '0.92rem' }}>
              {run.error_message}
            </div>
          )}

          {selected && (
            <>
              <div className="training-run-item__meta" style={{ marginTop: '0.85rem' }}>
                <div><span>Batch</span><strong>{run.config?.batch ?? '—'}</strong></div>
                <div><span>Epochs</span><strong>{run.config?.epochs ?? '—'}</strong></div>
                <div><span>Img size</span><strong>{run.config?.imgsz ?? '—'}</strong></div>
                <div><span>Task ID</span><strong>{run.background_task_id ?? '—'}</strong></div>
              </div>
              <pre className="training-log training-run-item__log">{runLog || 'Лог пока не появился.'}</pre>
            </>
          )}

          <div style={{ marginTop: '0.8rem', display: 'flex', gap: '0.6rem', flexWrap: 'wrap' }}>
            {!run.is_active_for_step && run.status === 'succeeded' && hasBestCheckpoint && (
              <button
                type="button"
                className="btn btn-primary"
                disabled={activating}
                onClick={(event) => {
                  event.stopPropagation();
                  onActivate(run.run_id);
                }}
              >
                {activating ? 'Активация...' : 'Сделать активной'}
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function RecognitionTrainingPage() {
  const { confirm, toast } = useDialogs();
  const [overview, setOverview] = useState(null);
  const [examples, setExamples] = useState([]);
  const [runs, setRuns] = useState([]);
  const [selectedIds, setSelectedIds] = useState([]);
  const [selectedExampleId, setSelectedExampleId] = useState(null);
  const [selectedExample, setSelectedExample] = useState(null);
  const [selectedRunId, setSelectedRunId] = useState(null);
  const [collapsedRunIds, setCollapsedRunIds] = useState({});
  const [runLog, setRunLog] = useState('');
  const [runForms, setRunForms] = useState({});
  const [overlayMode, setOverlayMode] = useState('diff');
  const [filters, setFilters] = useState(INITIAL_FILTERS);
  const [runFilters, setRunFilters] = useState(INITIAL_RUN_FILTERS);
  const [editForm, setEditForm] = useState({ curation_status: 'approved', issue_tags: '', notes: '' });
  const [loading, setLoading] = useState(true);
  const [examplesLoading, setExamplesLoading] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [runsLoading, setRunsLoading] = useState(false);
  const [savingDetail, setSavingDetail] = useState(false);
  const [creatingRunForStep, setCreatingRunForStep] = useState('');
  const [activatingRunId, setActivatingRunId] = useState('');
  const [deletingRunId, setDeletingRunId] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  const activeRun = runs.find((item) => item.status === 'queued' || item.status === 'running') || null;

  const projectOptions = useMemo(() => {
    const map = new Map();
    examples.forEach((item) => {
      if (item.project_id && !map.has(item.project_id)) {
        map.set(item.project_id, { value: item.project_id, label: `${item.project_name || 'Проект'} (${item.project_code || 'без кода'})` });
      }
    });
    return Array.from(map.values());
  }, [examples]);

  const floorPlanOptions = useMemo(() => {
    const map = new Map();
    examples.forEach((item) => {
      if (item.floor_plan_id && !map.has(item.floor_plan_id)) {
        map.set(item.floor_plan_id, { value: item.floor_plan_id, label: `${item.floor_plan_name || 'План'} · этаж ${item.floor_number ?? '—'}` });
      }
    });
    return Array.from(map.values());
  }, [examples]);

  const visibleRuns = useMemo(() => runs.filter((run) => (
    (!runFilters.step || run.step === runFilters.step)
    && (!runFilters.status || run.status === runFilters.status)
  )), [runFilters, runs]);

  useEffect(() => {
    let cancelled = false;
    const loadInitial = async () => {
      setLoading(true);
      setError('');
      try {
        const [overviewResponse, examplesResponse, runsResponse] = await Promise.all([
          recognitionTrainingApi.getOverview(),
          recognitionTrainingApi.listExamples(INITIAL_FILTERS),
          recognitionTrainingApi.listRuns(),
        ]);
        if (cancelled) {
          return;
        }
        setOverview(overviewResponse);
        setExamples(examplesResponse);
        setRuns(runsResponse);
        setSelectedExampleId((prev) => prev || examplesResponse[0]?.id || null);
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError.message);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };
    loadInitial();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!overview?.steps?.length) {
      return;
    }
    setRunForms((prev) => {
      const next = { ...prev };
      overview.steps.forEach((stepItem) => {
        if (!next[stepItem.step]) {
          next[stepItem.step] = {
            epochs: stepItem.training_defaults.epochs,
            imgsz: stepItem.training_defaults.imgsz,
            batch: stepItem.training_defaults.batch,
            patience: stepItem.training_defaults.patience,
          };
        }
      });
      return next;
    });
  }, [overview]);

  useEffect(() => {
    if (!selectedExampleId) {
      setSelectedExample(null);
      return undefined;
    }
    let cancelled = false;
    const loadDetail = async () => {
      setDetailLoading(true);
      try {
        const detail = await recognitionTrainingApi.getExample(selectedExampleId);
        if (cancelled) {
          return;
        }
        setSelectedExample(detail);
        setEditForm({
          curation_status: detail.curation_status || 'approved',
          issue_tags: (detail.issue_tags || []).join(', '),
          notes: detail.notes || '',
        });
      } catch (detailError) {
        if (!cancelled) {
          setError(detailError.message);
        }
      } finally {
        if (!cancelled) {
          setDetailLoading(false);
        }
      }
    };
    loadDetail();
    return () => {
      cancelled = true;
    };
  }, [selectedExampleId]);

  useEffect(() => {
    if (!selectedRunId) {
      setRunLog('');
      return undefined;
    }
    let cancelled = false;
    const loadLog = async () => {
      try {
        const response = await recognitionTrainingApi.getRunLog(selectedRunId, 200);
        if (!cancelled) {
          setRunLog(response.content || '');
        }
      } catch (logError) {
        if (!cancelled) {
          setRunLog(logError.message);
        }
      }
    };
    loadLog();
    return () => {
      cancelled = true;
    };
  }, [selectedRunId]);

  useEffect(() => {
    if (!activeRun && !selectedRunId) {
      return undefined;
    }
    const timer = window.setInterval(async () => {
      try {
        const [runsResponse, overviewResponse] = await Promise.all([
          recognitionTrainingApi.listRuns(),
          recognitionTrainingApi.getOverview(),
        ]);
        setRuns(runsResponse);
        setOverview(overviewResponse);
        if (selectedRunId) {
          const response = await recognitionTrainingApi.getRunLog(selectedRunId, 200);
          setRunLog(response.content || '');
        }
      } catch (_error) {
        // Silent refresh during polling.
      }
    }, 5000);
    return () => window.clearInterval(timer);
  }, [activeRun, selectedRunId]);

  const refreshExamples = async () => {
    setExamplesLoading(true);
    try {
      const data = await recognitionTrainingApi.listExamples(filters);
      setExamples(data);
      setSelectedIds((prev) => prev.filter((id) => data.some((item) => item.id === id)));
      if (selectedExampleId && !data.some((item) => item.id === selectedExampleId)) {
        setSelectedExampleId(data[0]?.id || null);
      }
    } catch (refreshError) {
      setError(refreshError.message);
    } finally {
      setExamplesLoading(false);
    }
  };

  const refreshRuns = async () => {
    setRunsLoading(true);
    try {
      const data = await recognitionTrainingApi.listRuns();
      setRuns(data);
      if (selectedRunId && !data.some((item) => item.run_id === selectedRunId)) {
        setSelectedRunId(data[0]?.run_id || null);
      }
      return data;
    } catch (refreshError) {
      setError(refreshError.message);
      return [];
    } finally {
      setRunsLoading(false);
    }
  };

  const refreshOverview = async () => {
    try {
      setOverview(await recognitionTrainingApi.getOverview());
    } catch (refreshError) {
      setError(refreshError.message);
    }
  };

  const toggleRunCollapsed = (runId) => {
    setCollapsedRunIds((prev) => ({
      ...prev,
      [runId]: !prev[runId],
    }));
  };

  const handleSelectRun = (runId) => {
    setSelectedRunId(runId);
    setCollapsedRunIds((prev) => ({
      ...prev,
      [runId]: false,
    }));
  };

  const handleApplyFilters = async () => {
    setMessage('');
    await refreshExamples();
  };

  const handleToggleSelectAll = (checked) => {
    setSelectedIds(checked ? examples.map((item) => item.id) : []);
  };

  const handleToggleSelected = (exampleId, checked) => {
    setSelectedIds((prev) => (
      checked
        ? [...prev.filter((item) => item !== exampleId), exampleId]
        : prev.filter((item) => item !== exampleId)
    ));
  };

  const handleBulkCurate = async (curationStatus) => {
    if (!selectedIds.length) {
      setError('Сначала выберите примеры в таблице.');
      return;
    }
    setError('');
    setMessage('');
    try {
      const response = await recognitionTrainingApi.bulkCurate({ example_ids: selectedIds, curation_status: curationStatus });
      setMessage(`Обновлено примеров: ${response.updated_count}`);
      await Promise.all([refreshOverview(), refreshExamples()]);
    } catch (bulkError) {
      setError(bulkError.message);
    }
  };

  const handleSaveExample = async () => {
    if (!selectedExampleId) {
      return;
    }
    setSavingDetail(true);
    setError('');
    setMessage('');
    try {
      const detail = await recognitionTrainingApi.updateExample(selectedExampleId, {
        curation_status: editForm.curation_status,
        issue_tags: editForm.issue_tags.split(',').map((item) => item.trim()).filter(Boolean),
        notes: editForm.notes,
      });
      setSelectedExample(detail);
      setMessage('Карточка примера обновлена.');
      await Promise.all([refreshOverview(), refreshExamples()]);
    } catch (saveError) {
      setError(saveError.message);
    } finally {
      setSavingDetail(false);
    }
  };

  const handleCreateRun = async (step) => {
    const stepOverview = (overview?.steps || []).find((item) => item.step === step) || null;
    const recommendedBatchSize = Number(stepOverview?.recommended_batch_size || 0);
    const selectedCount = Number(stepOverview?.selected_for_batch || 0);
    const force = !Boolean(stepOverview?.next_batch_hint?.eligible);
    if (force) {
      const reasonLabel = getHintLabel(stepOverview?.next_batch_hint?.reason);
      const confirmationText = recommendedBatchSize > 0 && selectedCount < recommendedBatchSize
        ? `Сейчас в batch ${selectedCount} примеров при рекомендуемом размере ${recommendedBatchSize}. ${reasonLabel}. Запустить дообучение принудительно?`
        : `Batch для ${step} еще не соответствует рекомендуемым условиям. ${reasonLabel}. Запустить дообучение принудительно?`;
      const isConfirmed = await confirm(confirmationText, {
        confirmLabel: 'Запустить',
        cancelLabel: 'Отмена',
      });
      if (!isConfirmed) {
        return;
      }
    }

    setCreatingRunForStep(step);
    setError('');
    setMessage('');
    try {
      const payload = {
        step,
        epochs: Number(runForms[step]?.epochs),
        imgsz: Number(runForms[step]?.imgsz),
        batch: Number(runForms[step]?.batch),
        patience: Number(runForms[step]?.patience),
        force,
      };
      const task = await recognitionTrainingApi.createRun(payload);
      setMessage(`Задача #${task.id} поставлена в очередь.`);
      const [nextRuns] = await Promise.all([refreshRuns(), refreshOverview(), refreshExamples()]);
      const queuedRun = nextRuns.find((item) => item.background_task_id === task.id) || null;
      if (queuedRun) {
        setSelectedRunId(queuedRun.run_id);
        setCollapsedRunIds((prev) => ({ ...prev, [queuedRun.run_id]: false }));
      }
      pollTaskUntilSettled(task.id)
        .then((settledTask) => {
          if (settledTask.status === 'succeeded') {
            toast(`Задача #${task.id} завершена.`, { tone: 'info' });
          }
        })
        .catch((pollError) => {
          console.error('Error polling training task:', pollError);
        });
    } catch (runError) {
      setError(runError.message);
    } finally {
      setCreatingRunForStep('');
    }
  };

  const handleActivateRun = async (runId) => {
    setActivatingRunId(runId);
    setError('');
    setMessage('');
    try {
      const activeModel = await recognitionTrainingApi.activateRun(runId);
      setMessage(`Активирована модель ${activeModel.run_id || runId} для шага ${activeModel.step}.`);
      await Promise.all([refreshOverview(), refreshRuns()]);
    } catch (activationError) {
      setError(activationError.message);
    } finally {
      setActivatingRunId('');
    }
  };

  const handleDeleteRun = async (runId) => {
    const run = runs.find((item) => item.run_id === runId) || null;
    if (!run) {
      return;
    }
    const isConfirmed = await confirm(`Удалить запуск ${runId}?`, {
      confirmLabel: 'Удалить',
      cancelLabel: 'Отмена',
    });
    if (!isConfirmed) {
      return;
    }

    setDeletingRunId(runId);
    setError('');
    setMessage('');
    try {
      await recognitionTrainingApi.deleteRun(runId);
      setMessage(`Запуск ${runId} удалён.`);
      if (selectedRunId === runId) {
        setSelectedRunId(null);
        setRunLog('');
      }
      await Promise.all([refreshRuns(), refreshOverview()]);
    } catch (deleteError) {
      setError(deleteError.message);
    } finally {
      setDeletingRunId('');
    }
  };

  const handleRunFieldChange = (step, field, value) => {
    setRunForms((prev) => ({ ...prev, [step]: { ...prev[step], [field]: value } }));
  };

  if (loading) {
    return <div className="loading">Загрузка центра дообучения...</div>;
  }

  return (
    <div className="project-list-container">
      <div className="project-list-header">
        <div>
          <Link to="/" style={{ color: '#0f8f7c', textDecoration: 'none' }}>← Назад к проектам</Link>
          <h1 style={{ marginBottom: '0.35rem' }}>Дообучение распознавания</h1>
          <p style={{ margin: 0, color: '#645f57' }}>
            Общая очередь feedback-примеров для `walls` и `openings`, история запусков, артефакты и выбор активной модели для pipeline detect.
          </p>
        </div>
      </div>

      {error && <div className="training-banner training-banner-error">{error}</div>}
      {message && <div className="training-banner training-banner-success">{message}</div>}

      <div className="training-summary-grid">
        {(overview?.steps || []).map((stepItem) => (
          <StepTrainingCard
            key={stepItem.step}
            stepOverview={stepItem}
            runForm={runForms[stepItem.step] || stepItem.training_defaults}
            onRunFieldChange={handleRunFieldChange}
            onCreateRun={handleCreateRun}
            creating={creatingRunForStep === stepItem.step}
          />
        ))}
      </div>

      <div className="training-card" style={{ marginTop: '1.25rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', alignItems: 'center', flexWrap: 'wrap', marginBottom: '1rem' }}>
          <h3 style={{ margin: 0 }}>Накопленные примеры</h3>
          <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
            <button className="btn btn-secondary" onClick={() => handleBulkCurate('approved')}>Restore</button>
            <button className="btn btn-danger" onClick={() => handleBulkCurate('excluded')}>Exclude</button>
          </div>
        </div>
        <div className="training-filters">
          <label>Шаг<select value={filters.step} onChange={(event) => setFilters((prev) => ({ ...prev, step: event.target.value }))}><option value="">Все</option><option value="walls">Walls</option><option value="openings">Openings</option></select></label>
          <label>Курация<select value={filters.curation_status} onChange={(event) => setFilters((prev) => ({ ...prev, curation_status: event.target.value }))}><option value="">Все</option><option value="approved">Approved</option><option value="excluded">Excluded</option></select></label>
          <label>Проект<select value={filters.project_id} onChange={(event) => setFilters((prev) => ({ ...prev, project_id: event.target.value }))}><option value="">Все</option>{projectOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
          <label>План<select value={filters.floor_plan_id} onChange={(event) => setFilters((prev) => ({ ...prev, floor_plan_id: event.target.value }))}><option value="">Все</option>{floorPlanOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
          <label>Сортировка<select value={filters.sort_by} onChange={(event) => setFilters((prev) => ({ ...prev, sort_by: event.target.value }))}><option value="submitted_at">По дате</option><option value="hardness">По hardness</option></select></label>
          <label>Направление<select value={filters.sort_dir} onChange={(event) => setFilters((prev) => ({ ...prev, sort_dir: event.target.value }))}><option value="desc">Сначала новые</option><option value="asc">Сначала старые</option></select></label>
          <label className="training-search">Поиск<input value={filters.search} onChange={(event) => setFilters((prev) => ({ ...prev, search: event.target.value }))} placeholder="Проект, код, теги, заметки" /></label>
          <label className="training-checkbox"><input type="checkbox" checked={filters.changed_only} onChange={(event) => setFilters((prev) => ({ ...prev, changed_only: event.target.checked }))} />Только реальные исправления</label>
          <button className="btn btn-primary" onClick={handleApplyFilters} disabled={examplesLoading}>{examplesLoading ? 'Загрузка...' : 'Применить'}</button>
        </div>
        <div className="training-table-wrap">
          <table className="training-table">
            <thead>
              <tr>
                <th><input type="checkbox" checked={Boolean(examples.length) && selectedIds.length === examples.length} onChange={(event) => handleToggleSelectAll(event.target.checked)} /></th>
                <th>ID</th>
                <th>Шаг</th>
                <th>Проект</th>
                <th>План</th>
                <th>Changed</th>
                <th>Hardness</th>
                <th>Курация</th>
                <th>Использований</th>
                <th>Дата</th>
              </tr>
            </thead>
            <tbody>
              {examples.map((item) => (
                <tr key={item.id} className={item.id === selectedExampleId ? 'selected' : ''} onClick={() => setSelectedExampleId(item.id)}>
                  <td onClick={(event) => event.stopPropagation()}><input type="checkbox" checked={selectedIds.includes(item.id)} onChange={(event) => handleToggleSelected(item.id, event.target.checked)} /></td>
                  <td>{item.id}</td>
                  <td>{item.step}</td>
                  <td>{item.project_name || '—'}</td>
                  <td>{item.floor_plan_name || '—'}</td>
                  <td>{item.changed ? 'Да' : 'Нет'}</td>
                  <td>{Number(item.hardness_score || 0).toFixed(1)}</td>
                  <td>{item.curation_status}</td>
                  <td>{item.times_used}</td>
                  <td>{formatDateTime(item.submitted_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!examples.length && <div style={{ padding: '1rem', color: '#645f57' }}>По текущим фильтрам примеров нет.</div>}
        </div>
      </div>

      <div className="training-main-grid">
        <div className="training-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap' }}>
            <h3 style={{ margin: 0 }}>Карточка примера</h3>
            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
              {['source', 'corrected', 'diff'].map((mode) => (
                <button key={mode} className={overlayMode === mode ? 'btn btn-primary' : 'btn btn-secondary'} onClick={() => setOverlayMode(mode)}>
                  {mode}
                </button>
              ))}
            </div>
          </div>
          {detailLoading ? <div style={{ color: '#645f57' }}>Загрузка detail...</div> : (
            <>
              <ExamplePreview detail={selectedExample} overlayMode={overlayMode} />
              {selectedExample && (
                <>
                  <div className="training-detail-grid">
                    <label>Курация<select value={editForm.curation_status} onChange={(event) => setEditForm((prev) => ({ ...prev, curation_status: event.target.value }))}><option value="approved">approved</option><option value="excluded">excluded</option></select></label>
                    <label>Теги<input value={editForm.issue_tags} onChange={(event) => setEditForm((prev) => ({ ...prev, issue_tags: event.target.value }))} placeholder="missed, wrong_class" /></label>
                  </div>
                  <label style={{ display: 'block', marginTop: '1rem' }}>
                    Заметки
                    <textarea rows="4" value={editForm.notes} onChange={(event) => setEditForm((prev) => ({ ...prev, notes: event.target.value }))} style={{ width: '100%', marginTop: '0.35rem' }} />
                  </label>
                  <div style={{ marginTop: '1rem', display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
                    <button className="btn btn-primary" onClick={handleSaveExample} disabled={savingDetail}>{savingDetail ? 'Сохранение...' : 'Сохранить карточку'}</button>
                    <button className="btn btn-secondary" onClick={() => setEditForm({ curation_status: selectedExample.curation_status || 'approved', issue_tags: (selectedExample.issue_tags || []).join(', '), notes: selectedExample.notes || '' })}>Сбросить</button>
                  </div>
                  <div className="training-history-grid">
                    <div>
                      <h4 style={{ marginBottom: '0.5rem' }}>История batch</h4>
                      {(selectedExample.batches || []).length ? (
                        <ul className="training-history-list">
                          {selectedExample.batches.map((batchItem) => (
                            <li key={`${batchItem.batch_id}-${batchItem.included_at}`}>
                              <strong>{batchItem.batch_id}</strong>
                              <span>{formatDateTime(batchItem.included_at)}</span>
                            </li>
                          ))}
                        </ul>
                      ) : <div style={{ color: '#645f57' }}>Еще не входил в export batch.</div>}
                    </div>
                    <div>
                      <h4 style={{ marginBottom: '0.5rem' }}>История run</h4>
                      {(selectedExample.runs || []).length ? (
                        <ul className="training-history-list">
                          {selectedExample.runs.map((runItem) => (
                            <li key={runItem.run_id}>
                              <strong>{runItem.run_id}</strong>
                              <span>{getRunStatusLabel(runItem.status)} · {formatDateTime(runItem.finished_at || runItem.requested_at)}{runItem.is_active_for_step ? ' · активна' : ''}</span>
                            </li>
                          ))}
                        </ul>
                      ) : <div style={{ color: '#645f57' }}>Run-ов по этому примеру пока нет.</div>}
                    </div>
                  </div>
                </>
              )}
            </>
          )}
        </div>

        <div className="training-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap' }}>
            <h3 style={{ margin: 0 }}>Каталог запусков</h3>
            <button className="btn btn-secondary" onClick={refreshRuns} disabled={runsLoading}>{runsLoading ? 'Обновление...' : 'Обновить'}</button>
          </div>

          <div className="training-filters" style={{ marginBottom: '1rem' }}>
            <label>Шаг<select value={runFilters.step} onChange={(event) => setRunFilters((prev) => ({ ...prev, step: event.target.value }))}><option value="">Все</option><option value="walls">Walls</option><option value="openings">Openings</option></select></label>
            <label>Статус<select value={runFilters.status} onChange={(event) => setRunFilters((prev) => ({ ...prev, status: event.target.value }))}><option value="">Все</option><option value="queued">Queued</option><option value="running">Running</option><option value="succeeded">Succeeded</option><option value="failed">Failed</option><option value="canceled">Canceled</option></select></label>
          </div>

          <div className="training-runs-layout">
            <div className="training-runs-list">
              {visibleRuns.map((run) => (
                <RunCard
                  key={run.run_id}
                  run={run}
                  selected={selectedRunId === run.run_id}
                  collapsed={Boolean(collapsedRunIds[run.run_id])}
                  deleting={deletingRunId === run.run_id}
                  onSelect={handleSelectRun}
                  onToggleCollapse={toggleRunCollapsed}
                  onActivate={handleActivateRun}
                  onDelete={handleDeleteRun}
                  activating={activatingRunId === run.run_id}
                  runLog={selectedRunId === run.run_id ? runLog : ''}
                />
              ))}
              {!visibleRuns.length && <div style={{ color: '#645f57' }}>По текущим фильтрам запусков нет.</div>}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default RecognitionTrainingPage;
