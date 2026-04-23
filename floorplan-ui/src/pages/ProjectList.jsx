import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import { useAuth } from '../auth/AuthContext';
import { projectsApi } from '../api/client';
import { useDialogs } from '../ui/DialogProvider';

function ProjectList() {
  const { user } = useAuth();
  const { confirm, toast } = useDialogs();
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let isActive = true;

    const fetchProjects = async () => {
      try {
        const data = await projectsApi.list();
        if (isActive) {
          setProjects(data);
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
  }, []);

  const reloadProjects = async () => {
    const data = await projectsApi.list();
    setProjects(data);
  };

  const handleDeleteProject = async (event, projectId, projectName) => {
    event.preventDefault();
    event.stopPropagation();

    const isConfirmed = await confirm(
      `Удалить проект "${projectName}"? Это действие необратимо.`,
      { confirmLabel: 'Удалить', cancelLabel: 'Отмена' },
    );
    if (!isConfirmed) {
      return;
    }

    try {
      await projectsApi.remove(projectId);
      await reloadProjects();
    } catch (error) {
      console.error('Error deleting project:', error);
      toast('Ошибка при удалении проекта.', { tone: 'error' });
    }
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
          {projects.map((project) => {
            const displayName = project.facility || project.name;
            const ownerLabel = project.owner_user?.full_name || 'Без владельца';
            return (
              <div key={project.id} className="project-card-shell">
                <Link
                  to={`/projects/${project.id}`}
                  style={{ textDecoration: 'none' }}
                >
                  <div className="project-card">
                    <h3>{displayName}</h3>
                    <p><strong>Шифр:</strong> {project.code}</p>
                    <p><strong>Тип:</strong> {project.project_type}</p>
                    <p><strong>Этажей:</strong> {project.number_of_floors}</p>
                    <p><strong>Подрядчик:</strong> {project.contractor}</p>
                    {user?.role === 'developer' && (
                      <p><strong>Владелец:</strong> {ownerLabel}</p>
                    )}
                    <p style={{ fontSize: '0.8rem', marginTop: '1rem' }}>
                      Создан: {project.created_at ? new Date(project.created_at).toLocaleDateString('ru-RU') : '—'}
                    </p>
                  </div>
                </Link>
                <div className="project-card-actions">
                  <button
                    type="button"
                    className="project-card-actions__delete"
                    onClick={(event) => handleDeleteProject(event, project.id, displayName)}
                    title="Удалить проект"
                  >
                    ×
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default ProjectList;
