import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';

import { backgroundTasksApi } from '../api/client';

const TASK_TYPE_LABELS = {
  recognition_process: 'Распознавание плана',
  pipeline_detect_walls: 'Распознавание стен',
  pipeline_detect_openings: 'Распознавание проемов',
  pipeline_detect_rooms: 'Распознавание помещений',
  pipeline_detect_zkspc: 'Распознавание ЗКСПС',
  fire_alarm_auto_layout: 'Авторасстановка извещателей',
  soue_auto_layout: 'Авторасстановка СОУЭ',
  recognition_training_run: 'Дообучение',
  project_pdf_generate: 'Генерация PDF',
};

const TASK_STATUS_LABELS = {
  queued: 'В очереди',
  running: 'В работе',
  succeeded: 'Выполнена',
  failed: 'Ошибка',
  canceled: 'Отменена',
};

const INITIAL_FILTERS = {
  status: '',
  task_type: '',
  requested_by_user_id: '',
  project_id: '',
  floor_plan_id: '',
};

function formatDateTime(value) {
  if (!value) {
    return '—';
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString('ru-RU');
}

function getTaskTypeLabel(taskType) {
  return TASK_TYPE_LABELS[taskType] || taskType || '—';
}

function getTaskStatusLabel(status) {
  return TASK_STATUS_LABELS[status] || status || '—';
}

export default function WorkerTasksPage() {
  const [tasks, setTasks] = useState([]);
  const [filters, setFilters] = useState(INITIAL_FILTERS);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');

  const loadTasks = useCallback(async ({ silent = false } = {}) => {
    if (silent) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    setError('');
    try {
      const data = await backgroundTasksApi.list({
        ...filters,
        limit: 300,
      });
      setTasks(data);
    } catch (loadError) {
      console.error('Error loading worker tasks:', loadError);
      setError(loadError.message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [filters]);

  useEffect(() => {
    loadTasks();
  }, [loadTasks]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      loadTasks({ silent: true });
    }, 4000);
    return () => window.clearInterval(timer);
  }, [loadTasks]);

  const availableTaskTypes = useMemo(() => (
    Array.from(new Set(tasks.map((task) => task.task_type).filter(Boolean))).sort()
  ), [tasks]);

  return (
    <div className="project-list-container">
      <div className="project-list-header">
        <div>
          <Link to="/" style={{ color: '#0f8f7c', textDecoration: 'none' }}>← Назад к проектам</Link>
          <h1 style={{ marginBottom: '0.35rem' }}>Очередь воркера</h1>
          <p style={{ margin: 0, color: '#645f57' }}>
            Статусы фоновых задач, инициатор, тип и связанные объекты.
          </p>
        </div>
        <button type="button" className="btn btn-secondary" onClick={() => loadTasks()} disabled={refreshing}>
          {refreshing ? 'Обновление...' : 'Обновить'}
        </button>
      </div>

      {error && <div className="training-banner training-banner-error">{error}</div>}

      <div className="training-card" style={{ marginBottom: '1rem' }}>
        <div className="training-filters">
          <label>
            Статус
            <select
              value={filters.status}
              onChange={(event) => setFilters((prev) => ({ ...prev, status: event.target.value }))}
            >
              <option value="">Все</option>
              <option value="queued">В очереди</option>
              <option value="running">В работе</option>
              <option value="succeeded">Выполнена</option>
              <option value="failed">Ошибка</option>
              <option value="canceled">Отменена</option>
            </select>
          </label>
          <label>
            Тип
            <select
              value={filters.task_type}
              onChange={(event) => setFilters((prev) => ({ ...prev, task_type: event.target.value }))}
            >
              <option value="">Все</option>
              {availableTaskTypes.map((taskType) => (
                <option key={taskType} value={taskType}>
                  {getTaskTypeLabel(taskType)}
                </option>
              ))}
            </select>
          </label>
          <label>
            ID пользователя
            <input
              type="number"
              min="1"
              value={filters.requested_by_user_id}
              onChange={(event) => setFilters((prev) => ({ ...prev, requested_by_user_id: event.target.value }))}
              placeholder="Все"
            />
          </label>
          <label>
            ID проекта
            <input
              type="number"
              min="1"
              value={filters.project_id}
              onChange={(event) => setFilters((prev) => ({ ...prev, project_id: event.target.value }))}
              placeholder="Все"
            />
          </label>
          <label>
            ID плана
            <input
              type="number"
              min="1"
              value={filters.floor_plan_id}
              onChange={(event) => setFilters((prev) => ({ ...prev, floor_plan_id: event.target.value }))}
              placeholder="Все"
            />
          </label>
          <button type="button" className="btn btn-primary" onClick={() => loadTasks()} disabled={loading || refreshing}>
            Применить
          </button>
        </div>
      </div>

      {loading ? (
        <div className="loading">Загрузка задач воркера...</div>
      ) : (
        <div className="training-table-wrap">
          <table className="training-table worker-tasks-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Статус</th>
                <th>Тип</th>
                <th>Поставил</th>
                <th>Проект</th>
                <th>План</th>
                <th>Попытки</th>
                <th>Создана</th>
                <th>Старт</th>
                <th>Финиш</th>
                <th>Ошибка / результат</th>
              </tr>
            </thead>
            <tbody>
              {tasks.map((task) => (
                <tr key={task.id}>
                  <td>{task.id}</td>
                  <td>
                    <span className={`training-status training-status-${task.status}`}>
                      {getTaskStatusLabel(task.status)}
                    </span>
                  </td>
                  <td>{getTaskTypeLabel(task.task_type)}</td>
                  <td>{task.requested_by_user?.full_name || task.requested_by_user_id || '—'}</td>
                  <td>{task.project_id || '—'}</td>
                  <td>{task.floor_plan_id || '—'}</td>
                  <td>{task.attempts ?? 0}</td>
                  <td>{formatDateTime(task.created_at)}</td>
                  <td>{formatDateTime(task.started_at)}</td>
                  <td>{formatDateTime(task.finished_at)}</td>
                  <td className="worker-tasks-table__message">
                    {task.error_message || task.resource_path || '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!tasks.length && (
            <div style={{ padding: '1rem', color: '#645f57' }}>
              По текущим фильтрам задач нет.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
