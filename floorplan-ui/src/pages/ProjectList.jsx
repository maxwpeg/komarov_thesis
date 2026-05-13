import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import { useAuth } from '../auth/AuthContext';
import { projectsApi } from '../api/client';
import { useDialogs } from '../ui/DialogProvider';

function ProjectList() {
  const { user } = useAuth();
  const { confirm, toast } = useDialogs();
  const [projects, setProjects] = useState([]);
  const [trashedProjects, setTrashedProjects] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let isActive = true;

    const fetchProjects = async () => {
      try {
        const [data, trashData] = await Promise.all([
          projectsApi.list(),
          user?.role === 'developer' ? projectsApi.listTrash() : Promise.resolve([]),
        ]);
        if (isActive) {
          setProjects(data);
          setTrashedProjects(trashData);
        }
      } catch (error) {
        console.error('Error fetching projects:', error);
      } finally {
        if (isActive) {
          setLoading(false);
        }
      }
    };

    fetchProjects();

    return () => {
      isActive = false;
    };
  }, [user?.role]);

  const reloadProjects = async () => {
    const [data, trashData] = await Promise.all([
      projectsApi.list(),
      user?.role === 'developer' ? projectsApi.listTrash() : Promise.resolve([]),
    ]);
    setProjects(data);
    setTrashedProjects(trashData);
  };

  const handleDeleteProject = async (event, projectId, projectName) => {
    event.preventDefault();
    event.stopPropagation();

    const isConfirmed = await confirm(
      `Переместить проект "${projectName}" в корзину? Он исчезнет из рабочего списка.`,
      { confirmLabel: 'В корзину', cancelLabel: 'Отмена' },
    );
    if (!isConfirmed) {
      return;
    }

    try {
      await projectsApi.remove(projectId);
      await reloadProjects();
      toast('Проект перемещен в корзину.', { tone: 'info' });
    } catch (error) {
      console.error('Error deleting project:', error);
      toast('Ошибка при удалении проекта.', { tone: 'error' });
    }
  };

  const handlePermanentDeleteProject = async (event, projectId, projectName) => {
    event.preventDefault();
    event.stopPropagation();

    const isConfirmed = await confirm(
      `Удалить проект "${projectName}" окончательно? Это действие нельзя отменить.`,
      { confirmLabel: 'Удалить окончательно', cancelLabel: 'Отмена' },
    );
    if (!isConfirmed) {
      return;
    }

    try {
      await projectsApi.permanentlyRemove(projectId);
      await reloadProjects();
      toast('Проект удален окончательно.', { tone: 'info' });
    } catch (error) {
      console.error('Error permanently deleting project:', error);
      toast('Ошибка при окончательном удалении проекта.', { tone: 'error' });
    }
  };

  const renderProjectCard = (project, { trashed = false } = {}) => {
    const displayName = project.facility || project.name;
    const ownerLabel = project.owner_user?.full_name || 'Без владельца';
    const deletedByLabel = project.deleted_by_user?.full_name || project.deleted_by_user_id || '—';
    const card = (
      <div className="project-card">
        <h3>{displayName}</h3>
        <p><strong>Шифр:</strong> {project.code}</p>
        <p><strong>Тип:</strong> {project.project_type}</p>
        <p><strong>Этажей:</strong> {project.number_of_floors}</p>
        <p><strong>Подрядчик:</strong> {project.contractor}</p>
        {user?.role === 'developer' && (
          <p><strong>Владелец:</strong> {ownerLabel}</p>
        )}
        {trashed ? (
          <>
            <p><strong>Удалил:</strong> {deletedByLabel}</p>
            <p style={{ fontSize: '0.8rem', marginTop: '1rem' }}>
              В корзине: {project.deleted_at ? new Date(project.deleted_at).toLocaleDateString('ru-RU') : '—'}
            </p>
          </>
        ) : (
          <p style={{ fontSize: '0.8rem', marginTop: '1rem' }}>
            Создан: {project.created_at ? new Date(project.created_at).toLocaleDateString('ru-RU') : '—'}
          </p>
        )}
      </div>
    );

    return (
      <div key={project.id} className="project-card-shell">
        {trashed ? card : (
          <Link
            to={`/projects/${project.id}`}
            style={{ textDecoration: 'none' }}
          >
            {card}
          </Link>
        )}
        <div className="project-card-actions">
          <button
            type="button"
            className="project-card-actions__delete"
            onClick={(event) => (
              trashed
                ? handlePermanentDeleteProject(event, project.id, displayName)
                : handleDeleteProject(event, project.id, displayName)
            )}
            title={trashed ? 'Удалить проект окончательно' : 'Переместить проект в корзину'}
          >
            ×
          </button>
        </div>
      </div>
    );
  };

  if (loading) {
    return <div className="loading">Загрузка проектов...</div>;
  }

  return (
    <div className="project-list-container">
      <div className="project-list-header">
        <h1>Проекты</h1>
      </div>

      {projects.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '3rem', color: '#6c757d' }}>
          <p>Пока нет проектов. Создайте первый проект, чтобы начать работу.</p>
        </div>
      ) : (
        <div className="project-grid">
          {projects.map((project) => renderProjectCard(project))}
        </div>
      )}

      {user?.role === 'developer' && (
        <section style={{ marginTop: '2rem' }}>
          <div className="project-list-header">
            <h2 style={{ margin: 0 }}>Корзина проектов</h2>
          </div>
          {trashedProjects.length === 0 ? (
            <div style={{ padding: '1rem 0', color: '#6c757d' }}>
              В корзине нет проектов.
            </div>
          ) : (
            <div className="project-grid">
              {trashedProjects.map((project) => renderProjectCard(project, { trashed: true }))}
            </div>
          )}
        </section>
      )}
    </div>
  );
}

export default ProjectList;
