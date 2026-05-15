import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import { auditApi } from '../api/client';

const INITIAL_AUDIT_FILTERS = {
  user_id: '',
  project_id: '',
  floor_plan_id: '',
  category: '',
  action: '',
  use_case: '',
  date_from: '',
  date_to: '',
};

function formatDateTime(value) {
  if (!value) {
    return '—';
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString('ru-RU');
}

function formatPayload(payload) {
  if (!payload || Object.keys(payload).length === 0) {
    return '—';
  }
  return JSON.stringify(payload);
}

export default function AuditPage() {
  const [events, setEvents] = useState([]);
  const [filters, setFilters] = useState(INITIAL_AUDIT_FILTERS);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loadEvents = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await auditApi.list({ ...filters, limit: 500 });
      setEvents(data);
    } catch (loadError) {
      console.error('Error loading audit log:', loadError);
      setError(loadError.message);
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    loadEvents();
  }, [loadEvents]);

  const exportFilters = { ...filters, limit: 5000 };

  return (
    <div className="project-list-container">
      <div className="project-list-header">
        <div>
          <Link to="/" style={{ color: '#0f8f7c', textDecoration: 'none' }}>← Назад к проектам</Link>
          <h1 style={{ marginBottom: '0.35rem' }}>Аудит</h1>
          <p style={{ margin: 0, color: '#645f57' }}>
            Журнал действий пользователей и системных операций.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <a className="btn btn-secondary" href={auditApi.exportUrl({ ...exportFilters, format: 'csv' })}>
            CSV
          </a>
          <a className="btn btn-secondary" href={auditApi.exportUrl({ ...exportFilters, format: 'json' })}>
            JSON
          </a>
        </div>
      </div>

      {error && <div className="training-banner training-banner-error">{error}</div>}

      <div className="training-card" style={{ marginBottom: '1rem' }}>
        <div className="training-filters">
          <label>
            Пользователь ID
            <input
              type="number"
              min="1"
              value={filters.user_id}
              onChange={(event) => setFilters((prev) => ({ ...prev, user_id: event.target.value }))}
              placeholder="Все"
            />
          </label>
          <label>
            Проект ID
            <input
              type="number"
              min="1"
              value={filters.project_id}
              onChange={(event) => setFilters((prev) => ({ ...prev, project_id: event.target.value }))}
              placeholder="Все"
            />
          </label>
          <label>
            План ID
            <input
              type="number"
              min="1"
              value={filters.floor_plan_id}
              onChange={(event) => setFilters((prev) => ({ ...prev, floor_plan_id: event.target.value }))}
              placeholder="Все"
            />
          </label>
          <label>
            Категория
            <input
              type="search"
              value={filters.category}
              onChange={(event) => setFilters((prev) => ({ ...prev, category: event.target.value }))}
              placeholder="Все"
            />
          </label>
          <label>
            Действие
            <input
              type="search"
              value={filters.action}
              onChange={(event) => setFilters((prev) => ({ ...prev, action: event.target.value }))}
              placeholder="event_name"
            />
          </label>
          <label>
            Use case
            <input
              type="search"
              value={filters.use_case}
              onChange={(event) => setFilters((prev) => ({ ...prev, use_case: event.target.value }))}
              placeholder="Все"
            />
          </label>
          <label>
            С даты
            <input
              type="datetime-local"
              value={filters.date_from}
              onChange={(event) => setFilters((prev) => ({ ...prev, date_from: event.target.value }))}
            />
          </label>
          <label>
            По дату
            <input
              type="datetime-local"
              value={filters.date_to}
              onChange={(event) => setFilters((prev) => ({ ...prev, date_to: event.target.value }))}
            />
          </label>
          <button type="button" className="btn btn-secondary" onClick={() => setFilters(INITIAL_AUDIT_FILTERS)}>
            Сбросить
          </button>
        </div>
      </div>

      {loading ? (
        <div className="loading">Загрузка журнала...</div>
      ) : (
        <div className="training-table-wrap">
          <table className="training-table audit-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Время</th>
                <th>Пользователь</th>
                <th>Категория</th>
                <th>Действие</th>
                <th>Use case</th>
                <th>Проект</th>
                <th>План</th>
                <th>Payload</th>
              </tr>
            </thead>
            <tbody>
              {events.map((event) => (
                <tr key={event.id}>
                  <td>{event.id}</td>
                  <td>{formatDateTime(event.created_at)}</td>
                  <td>{event.user_id || '—'}</td>
                  <td>{event.category}</td>
                  <td>{event.event_name}</td>
                  <td>{event.use_case}</td>
                  <td>{event.project_id || '—'}</td>
                  <td>{event.floor_plan_id || '—'}</td>
                  <td className="audit-table__payload">{formatPayload(event.payload)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!events.length && (
            <div style={{ padding: '1rem', color: '#645f57' }}>
              По текущим фильтрам событий нет.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
