import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import { useAuth } from '../auth/AuthContext';
import { projectsApi } from '../api/client';

function ProjectList() {
  const { user } = useAuth();
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

    if (!window.confirm(`Удалить проект "${projectName}"? Это действие необратимо.`)) {
      return;
    }

    try {
      await projectsApi.remove(projectId);
      await reloadProjects();
    } catch (error) {
      console.error('Error deleting project:', error);
      alert('Ошибка при удалении проекта');
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
              <div key={project.id} style={{ position: 'relative' }}>
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
                <button
                  onClick={(event) => handleDeleteProject(event, project.id, displayName)}
                  style={{
                    position: 'absolute',
                    top: '10px',
                    right: '10px',
                    background: '#dc3545',
                    color: 'white',
                    border: 'none',
                    borderRadius: '4px',
                    padding: '5px 10px',
                    cursor: 'pointer',
                    fontSize: '18px',
                    fontWeight: 'bold',
                    fontFamily: 'Arial, sans-serif',
                    zIndex: 10,
                  }}
                  title="Удалить проект"
                >
                  ×
                </button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default ProjectList;
