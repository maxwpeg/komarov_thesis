import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';

import { projectsApi } from '../api/client';
import { useDialogs } from '../ui/DialogProvider';
import { pollTaskUntilSettled } from '../utils/backgroundTasks';

export default function ProjectPdfPreviewPage() {
  const { projectId } = useParams();
  const [searchParams] = useSearchParams();
  const { toast } = useDialogs();
  const [preview, setPreview] = useState(null);
  const [pdfObjectUrl, setPdfObjectUrl] = useState('');
  const [loading, setLoading] = useState(true);
  const [queueing, setQueueing] = useState(false);
  const [error, setError] = useState('');
  const stageKey = searchParams.get('stageKey') || '';
  const floorPlanId = searchParams.get('floorPlanId') || '';
  const previewQuery = useMemo(() => ({
    stage_key: stageKey || undefined,
    floor_plan_id: floorPlanId || undefined,
  }), [floorPlanId, stageKey]);

  const loadPreview = useCallback(async () => {
    const data = await projectsApi.getPdfPreview(projectId, previewQuery);
    setPreview(data);
    return data;
  }, [previewQuery, projectId]);

  const waitForTask = useCallback(async (taskId) => {
    const task = await pollTaskUntilSettled(taskId, {
      onUpdate: (nextTask) => {
        setPreview((prev) => ({
          ...(prev || { project_id: Number(projectId) }),
          current_task: nextTask,
        }));
      },
    });
    if (task.status !== 'succeeded') {
      throw new Error(task.error_message || 'Генерация PDF завершилась с ошибкой');
    }
    return loadPreview();
  }, [loadPreview, projectId]);

  const ensurePreview = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await loadPreview();
      if (data?.pdf_url) {
        return;
      }
      if (data?.current_task?.id) {
        await waitForTask(data.current_task.id);
        return;
      }
      setQueueing(true);
      const task = await projectsApi.generatePdf(projectId);
      setPreview((prev) => ({ ...(prev || data || {}), current_task: task }));
      await waitForTask(task.id);
      toast('PDF готов и открыт для предпросмотра.', { tone: 'info' });
    } catch (loadError) {
      console.error('Error preparing PDF preview:', loadError);
      setError(loadError.message);
    } finally {
      setLoading(false);
      setQueueing(false);
    }
  }, [loadPreview, projectId, toast, waitForTask]);

  useEffect(() => {
    ensurePreview();
  }, [ensurePreview]);

  useEffect(() => {
    let isActive = true;
    let nextObjectUrl = '';

    if (!preview?.pdf_url) {
      setPdfObjectUrl('');
      return undefined;
    }

    setPdfObjectUrl('');

    const loadPdfBlob = async () => {
      try {
        const response = await fetch(preview.pdf_url, {
          credentials: 'include',
        });
        if (!response.ok) {
          throw new Error(`Не удалось открыть PDF (HTTP ${response.status})`);
        }
        const blob = await response.blob();
        nextObjectUrl = window.URL.createObjectURL(blob);
        if (isActive) {
          setPdfObjectUrl(nextObjectUrl);
        }
      } catch (loadBlobError) {
        if (isActive) {
          setError(loadBlobError.message);
        }
      }
    };

    loadPdfBlob();

    return () => {
      isActive = false;
      if (nextObjectUrl) {
        window.URL.revokeObjectURL(nextObjectUrl);
      }
    };
  }, [preview?.pdf_url]);

  const iframeSrc = useMemo(() => {
    if (!pdfObjectUrl) {
      return '';
    }
    if (!preview?.page_number) {
      return pdfObjectUrl;
    }
    return `${pdfObjectUrl}#page=${preview.page_number}`;
  }, [pdfObjectUrl, preview?.page_number]);

  const subtitle = preview?.page_title
    ? `Этап: ${preview.page_title}`
    : 'Открываем готовый документ проекта.';

  return (
    <div className="project-list-container">
      <div className="project-list-header" style={{ alignItems: 'center' }}>
        <div>
          <Link to={`/projects/${projectId}`} style={{ color: '#0f8f7c', textDecoration: 'none' }}>← Назад к проекту</Link>
          <h1 style={{ marginBottom: '0.35rem' }}>Предпросмотр PDF</h1>
          <p style={{ margin: 0, color: '#645f57' }}>
            {subtitle}
          </p>
          <p style={{ margin: '0.35rem 0 0', color: '#8b7866' }}>
            {preview?.generated_at
              ? `Последняя генерация: ${new Date(preview.generated_at).toLocaleString('ru-RU')}`
              : 'Подготавливаем PDF для просмотра.'}
          </p>
        </div>
        <button type="button" className="btn btn-primary" onClick={ensurePreview} disabled={queueing}>
          {queueing ? 'Ставим в очередь...' : 'Обновить PDF'}
        </button>
      </div>

      {loading && (
        <div className="project-detail-empty-state">
          <p style={{ color: '#645f57' }}>
            {preview?.current_task?.status === 'running' || preview?.current_task?.status === 'queued'
              ? 'Документ генерируется в фоне. Страница обновится автоматически.'
              : 'Подготавливаем PDF для проекта.'}
          </p>
        </div>
      )}

      {!loading && error && (
        <div className="training-banner training-banner-error">{error}</div>
      )}

      {!loading && !error && preview?.pdf_url && !pdfObjectUrl && (
        <div className="project-detail-empty-state">
          <p style={{ color: '#645f57' }}>Загружаем PDF для встроенного предпросмотра.</p>
        </div>
      )}

      {!loading && !error && preview?.pdf_url && pdfObjectUrl && preview?.page_number === null && preview?.page_title && (
        <div className="project-detail-toolbar__status" style={{ marginBottom: '1rem' }}>
          Для этого этапа пока нет отдельной страницы в PDF, поэтому открыт весь документ.
        </div>
      )}

      {!loading && !error && preview?.pdf_url && pdfObjectUrl && (
        <div style={{ borderRadius: '18px', overflow: 'hidden', border: '1px solid #d9d2c8', background: '#fff', minHeight: '70vh' }}>
          <iframe
            src={iframeSrc}
            title="PDF preview"
            style={{ width: '100%', minHeight: '70vh', border: 'none' }}
          />
        </div>
      )}
    </div>
  );
}
