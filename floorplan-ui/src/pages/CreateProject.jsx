import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';

function CreateProject() {
  const navigate = useNavigate();
  const [formData, setFormData] = useState({
    name: '',
    project_type: 'ПС',
    contractor: 'ООО "Флагман-СБ"',
    engineer: 'Комарова Н.С.',
    cpe: 'Гостев В.В.',
    checker: 'Комаров С.Л.',
    facility: '',
    facility_address: '',
    project_description: 'Система пожарной сигнализации и система оповещения и управления эвакуацией людей при пожаре',
    stage: '«Р»',
    number_of_floors: 1
  });

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    try {
      const response = await fetch('/api/projects', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(formData),
      });

      if (response.ok) {
        const project = await response.json();
        navigate(`/projects/${project.id}`);
      } else {
        alert('Ошибка создания проекта');
      }
    } catch (error) {
      console.error('Error:', error);
      alert('Ошибка создания проекта');
    }
  };

  return (
    <div className="form-container">
      <h1>Создать новый проект</h1>
      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label>Название проекта *</label>
          <input
            type="text"
            name="name"
            value={formData.name}
            onChange={handleChange}
            required
          />
        </div>

        <div className="form-group">
          <label>Название объекта *</label>
          <input
            type="text"
            name="facility"
            value={formData.facility}
            onChange={handleChange}
            required
          />
        </div>

        <div className="form-group">
          <label>Адрес объекта</label>
          <input
            type="text"
            name="facility_address"
            value={formData.facility_address}
            onChange={handleChange}
          />
        </div>

        <div className="form-group">
          <label>Тип проекта</label>
          <input
            type="text"
            name="project_type"
            value={formData.project_type}
            onChange={handleChange}
          />
        </div>

        <div className="form-group">
          <label>Подрядчик</label>
          <input
            type="text"
            name="contractor"
            value={formData.contractor}
            onChange={handleChange}
          />
        </div>

        <div className="form-group">
          <label>Инженер</label>
          <input
            type="text"
            name="engineer"
            value={formData.engineer}
            onChange={handleChange}
          />
        </div>

        <div className="form-group">
          <label>Главный инженер проекта (ГИП)</label>
          <input
            type="text"
            name="cpe"
            value={formData.cpe}
            onChange={handleChange}
          />
        </div>

        <div className="form-group">
          <label>Проверяющий</label>
          <input
            type="text"
            name="checker"
            value={formData.checker}
            onChange={handleChange}
          />
        </div>

        <div className="form-group">
          <label>Описание проекта</label>
          <textarea
            name="project_description"
            value={formData.project_description}
            onChange={handleChange}
          />
        </div>

        <div className="form-group">
          <label>Стадия</label>
          <input
            type="text"
            name="stage"
            value={formData.stage}
            onChange={handleChange}
          />
        </div>

        <div className="form-group">
          <label>Количество этажей</label>
          <input
            type="number"
            name="number_of_floors"
            value={formData.number_of_floors}
            onChange={handleChange}
            min="1"
          />
        </div>

        <div className="form-actions">
          <button type="button" className="btn btn-secondary" onClick={() => navigate('/')}>
            Отмена
          </button>
          <button type="submit" className="btn btn-primary">
            Создать проект
          </button>
        </div>
      </form>
    </div>
  );
}

export default CreateProject;
