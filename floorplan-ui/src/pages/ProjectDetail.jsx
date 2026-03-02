import React, { useState, useEffect } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';

function ProjectDetail() {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const [project, setProject] = useState(null);
  const [floorPlans, setFloorPlans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploadingFloor, setUploadingFloor] = useState(false);
  const [generatingPDF, setGeneratingPDF] = useState(false);

  useEffect(() => {
    fetchProject();
    fetchFloorPlans();
  }, [projectId]);

  const fetchProject = async () => {
    try {
      const response = await fetch(`/api/projects/${projectId}`);
      const data = await response.json();
      setProject(data);
      setLoading(false);
    } catch (error) {
      console.error('Error fetching project:', error);
      setLoading(false);
    }
  };

  const fetchFloorPlans = async () => {
    try {
      const response = await fetch(`/api/projects/${projectId}/floor-plans`);
      const data = await response.json();
      setFloorPlans(data);
    } catch (error) {
      console.error('Error fetching floor plans:', error);
    }
  };

  const handleUploadFloorPlan = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setUploadingFloor(true);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('project_id', projectId);
    formData.append('floor_number', floorPlans.length + 1);
    formData.append('name', `Floor ${floorPlans.length + 1}`);
    formData.append('scale_factor', '10'); // 10mm per pixel default

    try {
      const response = await fetch('/api/floor-plans', {
        method: 'POST',
        body: formData,
      });

      if (response.ok) {
        const floorPlan = await response.json();
        // Process the floor plan image
        await fetch(`/api/floor-plans/${floorPlan.id}/process`, {
          method: 'POST',
        });
        fetchFloorPlans();
        navigate(`/floor-plans/${floorPlan.id}`);
      }
    } catch (error) {
      console.error('Error uploading floor plan:', error);
    } finally {
      setUploadingFloor(false);
    }
  };

  const handleGeneratePDF = async () => {
    setGeneratingPDF(true);
    
    try {
      const response = await fetch(`/api/projects/${projectId}/generate-pdf`, {
        method: 'POST',
      });

      if (response.ok) {
        // Получаем PDF как blob
        const blob = await response.blob();
        
        // Создаем URL для скачивания
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        
        // Получаем имя файла из заголовка ответа или используем дефолтное
        const contentDisposition = response.headers.get('Content-Disposition');
        let filename = `Проект_${project.code}_${new Date().toISOString().split('T')[0]}.pdf`;
        
        if (contentDisposition) {
          const filenameMatch = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
          if (filenameMatch && filenameMatch[1]) {
            filename = filenameMatch[1].replace(/['"]/g, '');
          }
        }
        
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        
        // Очистка
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        
        alert('PDF успешно создан и загружен!');
      } else {
        const error = await response.json();
        alert(`Ошибка генерации PDF: ${error.detail || 'Неизвестная ошибка'}`);
      }
    } catch (error) {
      console.error('Error generating PDF:', error);
      alert('Ошибка при генерации PDF. Проверьте консоль для деталей.');
    } finally {
      setGeneratingPDF(false);
    }
  };

  const handleDeleteProject = async () => {
    if (!window.confirm(`Вы уверены, что хотите удалить проект "${project.facility}"? Это действие необратимо и удалит все планы этажей.`)) {
      return;
    }

    try {
      const response = await fetch(`/api/projects/${projectId}`, {
        method: 'DELETE',
      });

      if (response.ok) {
        navigate('/');
      } else {
        alert('Ошибка при удалении проекта');
      }
    } catch (error) {
      console.error('Error deleting project:', error);
      alert('Ошибка при удалении проекта');
    }
  };

  const handleDeleteFloorPlan = async (e, floorPlanId, floorPlanName) => {
    e.preventDefault();
    e.stopPropagation();

    if (!window.confirm(`Вы уверены, что хотите удалить план этажа "${floorPlanName}"? Это действие необратимо.`)) {
      return;
    }

    try {
      const response = await fetch(`/api/floor-plans/${floorPlanId}`, {
        method: 'DELETE',
      });

      if (response.ok) {
        // Сразу обновляем локальное состояние
        setFloorPlans(floorPlans.filter(fp => fp.id !== floorPlanId));
      } else {
        alert('Ошибка при удалении плана этажа');
      }
    } catch (error) {
      console.error('Error deleting floor plan:', error);
      alert('Ошибка при удалении плана этажа');
    }
  };

  if (loading) {
    return <div className="loading">Загрузка проекта...</div>;
  }

  if (!project) {
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
        <h2>Детали проекта</h2>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <tbody>
            <tr style={{ borderBottom: '1px solid #dee2e6' }}>
              <td style={{ padding: '0.5rem', fontWeight: 'bold' }}>Тип:</td>
              <td style={{ padding: '0.5rem' }}>{project.project_type}</td>
            </tr>
            <tr style={{ borderBottom: '1px solid #dee2e6' }}>
              <td style={{ padding: '0.5rem', fontWeight: 'bold' }}>Подрядчик:</td>
              <td style={{ padding: '0.5rem' }}>{project.contractor}</td>
            </tr>
            <tr style={{ borderBottom: '1px solid #dee2e6' }}>
              <td style={{ padding: '0.5rem', fontWeight: 'bold' }}>Инженер:</td>
              <td style={{ padding: '0.5rem' }}>{project.engineer}</td>
            </tr>
            <tr style={{ borderBottom: '1px solid #dee2e6' }}>
              <td style={{ padding: '0.5rem', fontWeight: 'bold' }}>Адрес:</td>
              <td style={{ padding: '0.5rem' }}>{project.facility_address}</td>
            </tr>
            <tr style={{ borderBottom: '1px solid #dee2e6' }}>
              <td style={{ padding: '0.5rem', fontWeight: 'bold' }}>Описание:</td>
              <td style={{ padding: '0.5rem' }}>{project.project_description}</td>
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
            <p style={{ color: '#6c757d' }}>Пока нет планов этажей. Загрузите изображение плана этажа, чтобы начать работу!</p>
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
                    <p><strong>Размеры:</strong> {floorPlan.image_width} × {floorPlan.image_height}px</p>
                    <p><strong>Масштаб:</strong> {floorPlan.scale_factor} мм/px</p>
                  </div>
                </Link>
                <button
                  onClick={(e) => handleDeleteFloorPlan(e, floorPlan.id, floorPlan.name)}
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
                    zIndex: 10
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
