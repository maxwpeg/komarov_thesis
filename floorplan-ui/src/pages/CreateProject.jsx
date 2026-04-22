import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { projectsApi } from '../api/client';

const CURRENT_YEAR = new Date().getFullYear();

function CreateProject() {
  const navigate = useNavigate();
  const [formData, setFormData] = useState({
    name: '',
    project_type: 'ПС',
    year: CURRENT_YEAR,
    contractor: 'ООО "Флагман-СБ"',
    engineer: 'Комарова Н.С.',
    cpe: 'Гостев В.В.',
    checker: 'Комаров С.Л.',
    facility: '',
    facility_genitive: '',
    facility_instrumental: '',
    facility_address: '',
    project_description: 'Система пожарной сигнализации и система оповещения и управления эвакуацией людей при пожаре',
    stage: 'Р',
    number_of_floors: 1,
  });
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleChange = (event) => {
    const { name, value } = event.target;
    const nextValue = name === 'year' || name === 'number_of_floors'
      ? (value === '' ? '' : Number(value))
      : value;

    setFormData((prev) => {
      const nextState = {
        ...prev,
        [name]: nextValue,
      };
      if (name === 'facility') {
        if (!prev.facility_genitive || prev.facility_genitive === prev.facility) {
          nextState.facility_genitive = value;
        }
        if (!prev.facility_instrumental || prev.facility_instrumental === prev.facility) {
          nextState.facility_instrumental = value;
        }
      }
      return nextState;
    });
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setIsSubmitting(true);

    try {
      const project = await projectsApi.create(formData);
      navigate(`/projects/${project.id}`);
    } catch (error) {
      console.error('Error creating project:', error);
      alert(`Ошибка создания проекта: ${error.message}`);
    } finally {
      setIsSubmitting(false);
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
          <label>Название объекта (родительный падеж)</label>
          <input
            type="text"
            name="facility_genitive"
            value={formData.facility_genitive}
            onChange={handleChange}
          />
        </div>

        <div className="form-group">
          <label>Название объекта (творительный падеж)</label>
          <input
            type="text"
            name="facility_instrumental"
            value={formData.facility_instrumental}
            onChange={handleChange}
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
          <label>Год</label>
          <input
            type="number"
            name="year"
            value={formData.year}
            onChange={handleChange}
            min="2000"
            required
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
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => navigate('/')}
            disabled={isSubmitting}
          >
            Отмена
          </button>
          <button type="submit" className="btn btn-primary" disabled={isSubmitting}>
            {isSubmitting ? 'Создание...' : 'Создать проект'}
          </button>
        </div>
      </form>
    </div>
  );
}

export default CreateProject;
