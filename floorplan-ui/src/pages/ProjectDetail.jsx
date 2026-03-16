import React, { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import { floorPlansApi, projectsApi } from '../api/client';

function buildProjectForm(project) {
  return {
    project_type: project.project_type ?? '',
    year: project.year ?? new Date().getFullYear(),
    contractor: project.contractor ?? '',
    engineer: project.engineer ?? '',
    facility_address: project.facility_address ?? '',
    project_description: project.project_description ?? '',
  };
}

function ProjectDetail() {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const [project, setProject] = useState(null);
  const [projectForm, setProjectForm] = useState(null);
  const [floorPlans, setFloorPlans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploadingFloor, setUploadingFloor] = useState(false);
  const [generatingPDF, setGeneratingPDF] = useState(false);
  const [savingProject, setSavingProject] = useState(false);
  const [saveMessage, setSaveMessage] = useState('');

  useEffect(() => {
    const loadProject = async () => {
      try {
        const data = await projectsApi.get(projectId);
        setProject(data);
        setProjectForm(buildProjectForm(data));
      } catch (error) {
        console.error('Error fetching project:', error);
      } finally {
        setLoading(false);
      }
    };

    const loadFloorPlans = async () => {
      try {
        const data = await floorPlansApi.list(projectId);
        setFloorPlans(data);
      } catch (error) {
        console.error('Error fetching floor plans:', error);
      }
    };

    loadProject();
    loadFloorPlans();
  }, [projectId]);

  const handleProjectFieldChange = (event) => {
    const { name, value } = event.target;
    const nextValue = name === 'year'
      ? (value === '' ? '' : Number(value))
      : value;

    setProjectForm((prev) => ({
      ...prev,
      [name]: nextValue,
    }));
    setSaveMessage('');
  };

  const handleSaveProject = async () => {
    if (!projectForm) {
      return;
    }

    setSavingProject(true);
    setSaveMessage('');

    try {
      const updatedProject = await projectsApi.update(projectId, projectForm);
      setProject(updatedProject);
      setProjectForm(buildProjectForm(updatedProject));
      setSaveMessage('Изменения сохранены.');
    } catch (error) {
      console.error('Error updating project:', error);
      setSaveMessage(`Ошибка сохранения: ${error.message}`);
    } finally {
      setSavingProject(false);
    }
  };

  const refreshFloorPlans = async () => {
    try {
      const data = await floorPlansApi.list(projectId);
      setFloorPlans(data);
    } catch (error) {
      console.error('Error refreshing floor plans:', error);
    }
  };

  const handleUploadFloorPlan = async (event) => {
    const file = event.target.files[0];
    if (!file) {
      return;
    }

    setUploadingFloor(true);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('project_id', projectId);
    formData.append('floor_number', floorPlans.length + 1);
    formData.append('name', `Floor ${floorPlans.length + 1}`);
    formData.append('scale_factor', '10');

    try {
      const floorPlan = await floorPlansApi.create(formData);
      await refreshFloorPlans();
      navigate(`/floor-plans/${floorPlan.id}`);
    } catch (error) {
      console.error('Error uploading floor plan:', error);
      alert(`Ошибка загрузки плана этажа: ${error.message}`);
    } finally {
      setUploadingFloor(false);
      event.target.value = '';
    }
  };

  const handleGeneratePDF = async () => {
    setGeneratingPDF(true);

    try {
      const response = await projectsApi.generatePdf(projectId);
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;

      const contentDisposition = response.headers.get('Content-Disposition');
      let filename = `Проект_${project.code}_${new Date().toISOString().split('T')[0]}.pdf`;

      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
        if (filenameMatch && filenameMatch[1]) {
          filename = filenameMatch[1].replace(/['"]/g, '');
        }
      }

      link.download = filename;
      document.body.appendChild(link);
      link.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(link);
      alert('PDF успешно создан и загружен.');
    } catch (error) {
      console.error('Error generating PDF:', error);
      alert(`Ошибка при генерации PDF: ${error.message}`);
    } finally {
      setGeneratingPDF(false);
    }
  };

  const handleDeleteProject = async () => {
    if (!window.confirm(`Вы уверены, что хотите удалить проект "${project.facility}"? Это действие необратимо и удалит все планы этажей.`)) {
      return;
    }

    try {
      await projectsApi.remove(projectId);
      navigate('/');
    } catch (error) {
      console.error('Error deleting project:', error);
      alert(`Ошибка при удалении проекта: ${error.message}`);
    }
  };

  const handleDeleteFloorPlan = async (event, floorPlanId, floorPlanName) => {
    event.preventDefault();
    event.stopPropagation();

    if (!window.confirm(`Вы уверены, что хотите удалить план этажа "${floorPlanName}"? Это действие необратимо.`)) {
      return;
    }

    try {
      await floorPlansApi.remove(floorPlanId);
      setFloorPlans((prev) => prev.filter((item) => item.id !== floorPlanId));
    } catch (error) {
      console.error('Error deleting floor plan:', error);
      alert(`Ошибка при удалении плана этажа: ${error.message}`);
    }
  };

  if (loading) {
    return <div className="loading">Загрузка проекта...</div>;
  }

  if (!project || !projectForm) {
    return <div>Проект не найден</div>;
  }

  return (
    <div className="project-list-container">
      <div className="project-list-header">
        <div>
          <Link to="/" style={{ color: '#007bff', textDecoration: 'none' }}>
            ← Назад к проектам
          </Link>
          <h1>{project.facility}</h1>
          <p style={{ color: '#6c757d' }}>Шифр: {project.code}</p>
        </div>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button
            className="btn btn-success"
            onClick={handleGeneratePDF}
            disabled={generatingPDF}
          >
            {generatingPDF ? 'Генерация PDF...' : 'Сгенерировать PDF'}
          </button>
          <button
            className="btn btn-danger"
            onClick={handleDeleteProject}
            style={{ background: '#dc3545' }}
          >
            Удалить проект
          </button>
        </div>
      </div>

      <div style={{ marginBottom: '2rem' }}>
        <div style={{ alignItems: 'center', display: 'flex', justifyContent: 'space-between', gap: '1rem', marginBottom: '1rem' }}>
          <h2 style={{ margin: 0 }}>Детали проекта</h2>
          <button
            className="btn btn-primary"
            onClick={handleSaveProject}
            disabled={savingProject}
          >
            {savingProject ? 'Сохранение...' : 'Сохранить'}
          </button>
        </div>

        {saveMessage && (
          <div style={{ color: saveMessage.startsWith('Ошибка') ? '#dc3545' : '#198754', marginBottom: '1rem' }}>
            {saveMessage}
          </div>
        )}

        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <tbody>
            <tr style={{ borderBottom: '1px solid #dee2e6' }}>
              <td style={{ padding: '0.5rem', fontWeight: 'bold', width: '220px' }}>Тип:</td>
              <td style={{ padding: '0.5rem' }}>
                <input
                  type="text"
                  name="project_type"
                  value={projectForm.project_type}
                  onChange={handleProjectFieldChange}
                  style={{ width: '100%' }}
                />
              </td>
            </tr>
            <tr style={{ borderBottom: '1px solid #dee2e6' }}>
              <td style={{ padding: '0.5rem', fontWeight: 'bold' }}>Год:</td>
              <td style={{ padding: '0.5rem' }}>
                <input
                  type="number"
                  name="year"
                  value={projectForm.year}
                  onChange={handleProjectFieldChange}
                  min="2000"
                  style={{ maxWidth: '180px', width: '100%' }}
                />
              </td>
            </tr>
            <tr style={{ borderBottom: '1px solid #dee2e6' }}>
              <td style={{ padding: '0.5rem', fontWeight: 'bold' }}>Подрядчик:</td>
              <td style={{ padding: '0.5rem' }}>
                <input
                  type="text"
                  name="contractor"
                  value={projectForm.contractor}
                  onChange={handleProjectFieldChange}
                  style={{ width: '100%' }}
                />
              </td>
            </tr>
            <tr style={{ borderBottom: '1px solid #dee2e6' }}>
              <td style={{ padding: '0.5rem', fontWeight: 'bold' }}>Инженер:</td>
              <td style={{ padding: '0.5rem' }}>
                <input
                  type="text"
                  name="engineer"
                  value={projectForm.engineer}
                  onChange={handleProjectFieldChange}
                  style={{ width: '100%' }}
                />
              </td>
            </tr>
            <tr style={{ borderBottom: '1px solid #dee2e6' }}>
              <td style={{ padding: '0.5rem', fontWeight: 'bold' }}>Адрес:</td>
              <td style={{ padding: '0.5rem' }}>
                <input
                  type="text"
                  name="facility_address"
                  value={projectForm.facility_address}
                  onChange={handleProjectFieldChange}
                  style={{ width: '100%' }}
                />
              </td>
            </tr>
            <tr style={{ borderBottom: '1px solid #dee2e6' }}>
              <td style={{ padding: '0.5rem', fontWeight: 'bold', verticalAlign: 'top' }}>Описание:</td>
              <td style={{ padding: '0.5rem' }}>
                <textarea
                  name="project_description"
                  value={projectForm.project_description}
                  onChange={handleProjectFieldChange}
                  rows="4"
                  style={{ resize: 'vertical', width: '100%' }}
                />
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <h2>Планы этажей</h2>
          <label className="btn btn-primary" style={{ cursor: 'pointer' }}>
            {uploadingFloor ? 'Загрузка...' : '+ Загрузить план этажа'}
            <input
              type="file"
              accept="image/*"
              onChange={handleUploadFloorPlan}
              style={{ display: 'none' }}
              disabled={uploadingFloor}
            />
          </label>
        </div>

        {floorPlans.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '3rem', background: '#f8f9fa', borderRadius: '8px' }}>
            <p style={{ color: '#6c757d' }}>
              Пока нет планов этажей. Загрузите изображение плана этажа, чтобы начать работу.
            </p>
          </div>
        ) : (
          <div className="project-grid">
            {floorPlans.map((floorPlan) => (
              <div key={floorPlan.id} style={{ position: 'relative' }}>
                <Link
                  to={`/floor-plans/${floorPlan.id}`}
                  style={{ textDecoration: 'none' }}
                >
                  <div className="project-card">
                    <h3>{floorPlan.name}</h3>
                    <p><strong>Этаж:</strong> {floorPlan.floor_number}</p>
                    <p><strong>Размеры:</strong> {floorPlan.image_width} x {floorPlan.image_height}px</p>
                    <p><strong>Масштаб:</strong> {floorPlan.scale_factor} мм/px</p>
                  </div>
                </Link>
                <button
                  onClick={(event) => handleDeleteFloorPlan(event, floorPlan.id, floorPlan.name)}
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
                    zIndex: 10,
                  }}
                  title="Удалить план этажа"
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default ProjectDetail;
