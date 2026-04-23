import React, { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import { useAuth } from '../auth/AuthContext';
import { equipmentApi, floorPlansApi, projectsApi, usersApi } from '../api/client';
import {
  formatEquipmentPrice,
  getEquipmentCategoryLabel,
  PROJECT_EQUIPMENT_GROUPS,
} from './equipmentCatalog/constants';

const GENERAL_DATA_STEP_KEY = 'general_data';
const GENERAL_INSTRUCTIONS_STEP_KEY = 'general_instructions';
const POWER_CONSUMPTION_STEP_KEY = 'power_consumption_calculation';
const EQUIPMENT_SPECIFICATION_STEP_KEY = 'equipment_specification';
const ADDITIONAL_INFO_STEP_KEY = 'additional_info';
const MIN_FLOOR_PLAN_IMAGE_SIZE_PX = 200;
const FLOOR_PLAN_UPLOAD_VALIDATION_MESSAGE = `Можно загрузить только изображение размером не меньше ${MIN_FLOOR_PLAN_IMAGE_SIZE_PX}x${MIN_FLOOR_PLAN_IMAGE_SIZE_PX} пикселей.`;

function readImageDimensions(file) {
  return new Promise((resolve, reject) => {
    const objectUrl = window.URL.createObjectURL(file);
    const image = new window.Image();

    const cleanup = () => {
      window.URL.revokeObjectURL(objectUrl);
    };

    image.onload = () => {
      cleanup();
      resolve({
        width: Number(image.naturalWidth || image.width || 0),
        height: Number(image.naturalHeight || image.height || 0),
      });
    };

    image.onerror = () => {
      cleanup();
      reject(new Error('Failed to read image dimensions'));
    };

    image.src = objectUrl;
  });
}

async function validateFloorPlanFile(file) {
  const normalizedType = String(file?.type || '').toLowerCase();
  if (normalizedType && !normalizedType.startsWith('image/')) {
    return false;
  }

  try {
    const { width, height } = await readImageDimensions(file);
    return width >= MIN_FLOOR_PLAN_IMAGE_SIZE_PX && height >= MIN_FLOOR_PLAN_IMAGE_SIZE_PX;
  } catch (_error) {
    return false;
  }
}

function buildProjectForm(project) {
  return {
    facility: project.facility ?? '',
    facility_genitive: project.facility_genitive ?? project.facility ?? '',
    facility_instrumental: project.facility_instrumental ?? project.facility ?? '',
    project_type: project.project_type ?? '',
    year: project.year ?? new Date().getFullYear(),
    contractor: project.contractor ?? '',
    engineer: project.engineer ?? '',
    facility_address: project.facility_address ?? '',
    project_description: project.project_description ?? '',
    owner_user_id: project.owner_user_id ?? '',
  };
}

function buildSharedStageHref(floorPlanId, stepKey) {
  if (!floorPlanId) {
    return null;
  }
  return `/floor-plans/${floorPlanId}?step=${stepKey}`;
}

function createProjectEquipmentDraft(defaultCategory = 'other') {
  return {
    name: '',
    category: defaultCategory,
    description: '',
    price: '',
    pack_quantity: '',
    mounting_spacing_m: '',
  };
}

const PROJECT_EQUIPMENT_SELECTION_ROLES = [
  'sps_linear_detector',
  'sps_smoke_detector',
  'sps_heat_detector',
  'sps_manual_call_point',
  'sps_cable',
  'soue_siren',
  'soue_exit_sign',
  'soue_speech_device',
  'soue_cable',
  'common_instrument',
  'common_keyboard',
  'common_other',
];

function filterItemsForGroup(items, group) {
  return items.filter((item) => group.categories.includes(item.category));
}

function buildProjectEquipmentPayload(draft) {
  const mountingSpecs = draft.category === 'mounting'
    ? {
      ...(draft.pack_quantity === '' ? {} : { pack_quantity: Number(draft.pack_quantity) }),
      ...(draft.mounting_spacing_m === '' ? {} : { mounting_spacing_m: Number(draft.mounting_spacing_m) }),
    }
    : {};
  return {
    name: draft.name.trim(),
    category: draft.category,
    description: draft.description.trim() || null,
    price: draft.price === '' ? null : Number(Number(draft.price).toFixed(2)),
    manufacturer: null,
    service_life_years: null,
    notes: null,
    specs: mountingSpecs,
    coverage_summary: null,
    standby_current_ma: null,
    alarm_current_ma: null,
    smoke_addressing: null,
    compatible_equipment_ids: [],
  };
}

function parseSpecificationQuantity(value) {
  if (value === null || value === undefined || value === '') {
    return 0;
  }
  const normalized = String(value).replace(/\s+/g, '').replace(',', '.');
  const match = normalized.match(/-?\d+(?:\.\d+)?/);
  if (!match) {
    return 0;
  }
  const numeric = Number(match[0]);
  return Number.isFinite(numeric) ? numeric : 0;
}

function getSpecificationEquipmentId(sourceKey) {
  if (!sourceKey) {
    return null;
  }
  const [, rawId] = String(sourceKey).split(':');
  const numericId = Number(rawId);
  return Number.isFinite(numericId) ? numericId : null;
}

function ProjectDetail() {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const isDeveloper = user?.role === 'developer';

  const [project, setProject] = useState(null);
  const [projectForm, setProjectForm] = useState(null);
  const [floorPlans, setFloorPlans] = useState([]);
  const [ownerUsers, setOwnerUsers] = useState([]);
  const [equipmentItems, setEquipmentItems] = useState([]);
  const [projectEquipmentItems, setProjectEquipmentItems] = useState([]);
  const [projectEquipmentSelections, setProjectEquipmentSelections] = useState({});
  const [additionalInfoMeta, setAdditionalInfoMeta] = useState(null);
  const [equipmentSpecification, setEquipmentSpecification] = useState(null);

  const [loading, setLoading] = useState(true);
  const [equipmentLoading, setEquipmentLoading] = useState(true);
  const [uploadingFloor, setUploadingFloor] = useState(false);
  const [generatingPDF, setGeneratingPDF] = useState(false);
  const [savingProject, setSavingProject] = useState(false);
  const [equipmentSaving, setEquipmentSaving] = useState(false);

  const [saveMessage, setSaveMessage] = useState('');
  const [equipmentMessage, setEquipmentMessage] = useState('');
  const [equipmentDialog, setEquipmentDialog] = useState({
    isOpen: false,
    groupKey: null,
    mode: 'attach',
    selectedEquipmentId: '',
    draft: createProjectEquipmentDraft(),
  });

  const projectEquipmentByGroup = useMemo(() => (
    PROJECT_EQUIPMENT_GROUPS.reduce((result, group) => {
      result[group.key] = filterItemsForGroup(projectEquipmentItems, group);
      return result;
    }, {})
  ), [projectEquipmentItems]);

  const projectCableOptions = useMemo(
    () => projectEquipmentItems.filter((item) => item.category === 'cable'),
    [projectEquipmentItems],
  );

  const availableEquipmentByGroup = useMemo(() => (
    PROJECT_EQUIPMENT_GROUPS.reduce((result, group) => {
      const linkedIds = new Set((projectEquipmentByGroup[group.key] || []).map((item) => item.id));
      result[group.key] = filterItemsForGroup(equipmentItems, group).filter((item) => !linkedIds.has(item.id));
      return result;
    }, {})
  ), [equipmentItems, projectEquipmentByGroup]);

  const approximateProjectCost = useMemo(() => {
    if (!equipmentSpecification) {
      return null;
    }

    const equipmentById = new Map();
    [...equipmentItems, ...projectEquipmentItems].forEach((item) => {
      const numericId = Number(item?.id);
      if (Number.isFinite(numericId)) {
        equipmentById.set(numericId, item);
      }
    });

    let total = 0;
    (equipmentSpecification.sections || []).forEach((section) => {
      (section.rows || []).forEach((row) => {
        const equipmentId = getSpecificationEquipmentId(row.source_key);
        if (!Number.isFinite(equipmentId)) {
          return;
        }
        const equipment = equipmentById.get(equipmentId);
        const price = Number(equipment?.price);
        if (!Number.isFinite(price)) {
          return;
        }
        total += price * parseSpecificationQuantity(row.quantity);
      });
    });
    return total;
  }, [equipmentItems, equipmentSpecification, projectEquipmentItems]);

  const loadEquipmentSpecification = async () => {
    try {
      const specification = await projectsApi.getEquipmentSpecification(projectId);
      setEquipmentSpecification(specification);
    } catch (error) {
      console.error('Error loading equipment specification:', error);
      setEquipmentSpecification(null);
    }
  };

  useEffect(() => {
    const loadProject = async () => {
      try {
        const [projectData, floorPlansData, additionalInfo, specification] = await Promise.all([
          projectsApi.get(projectId),
          floorPlansApi.list(projectId),
          projectsApi.getAdditionalInfo(projectId).catch(() => ({
            page_title: 'Доп. сведения',
            text: '',
            is_empty: true,
          })),
          projectsApi.getEquipmentSpecification(projectId).catch(() => null),
        ]);
        setProject(projectData);
        setProjectForm(buildProjectForm(projectData));
        setFloorPlans(floorPlansData);
        setAdditionalInfoMeta(additionalInfo);
        setEquipmentSpecification(specification);
      } catch (error) {
        console.error('Error fetching project:', error);
        setAdditionalInfoMeta({ page_title: 'Доп. сведения', text: '', is_empty: true });
        setEquipmentSpecification(null);
      } finally {
        setLoading(false);
      }
    };

    const loadEquipment = async () => {
      setEquipmentLoading(true);
      setEquipmentMessage('');
      try {
        const [catalogItems, projectEquipment, selections] = await Promise.all([
          equipmentApi.list(),
          projectsApi.listEquipment(projectId),
          projectsApi.getEquipmentSelections(projectId),
        ]);
        setEquipmentItems(catalogItems);
        setProjectEquipmentItems(projectEquipment?.items || []);
        setProjectEquipmentSelections(selections?.selections || {});
      } catch (error) {
        console.error('Error loading equipment data:', error);
        setEquipmentItems([]);
        setProjectEquipmentItems([]);
        setProjectEquipmentSelections({});
        setEquipmentMessage(`Ошибка загрузки оборудования: ${error.message}`);
      } finally {
        setEquipmentLoading(false);
      }
    };

    loadProject();
    loadEquipment();
  }, [projectId]);

  useEffect(() => {
    if (!isDeveloper) {
      setOwnerUsers([]);
      return;
    }

    let isActive = true;
    usersApi.list()
      .then((items) => {
        if (isActive) {
          setOwnerUsers(items.filter((item) => item.role === 'engineer' && item.is_active));
        }
      })
      .catch((error) => {
        console.error('Error loading project owners:', error);
      });

    return () => {
      isActive = false;
    };
  }, [isDeveloper]);

  const handleProjectFieldChange = (event) => {
    const { name, value } = event.target;
    setProjectForm((prev) => {
      const nextState = {
        ...prev,
        [name]: name === 'year' || name === 'owner_user_id'
          ? (value === '' ? '' : Number(value))
          : value,
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
    setSaveMessage('');
  };

  const handleSaveProject = async () => {
    if (!projectForm) {
      return;
    }

    setSavingProject(true);
    setSaveMessage('');
    try {
      const payload = {
        ...projectForm,
        owner_user_id: isDeveloper
          ? (projectForm.owner_user_id === '' ? null : Number(projectForm.owner_user_id))
          : undefined,
      };
      if (!isDeveloper) {
        delete payload.owner_user_id;
      }
      const updatedProject = await projectsApi.update(projectId, payload);
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

  const openEquipmentDialog = (groupKey) => {
    const group = PROJECT_EQUIPMENT_GROUPS.find((item) => item.key === groupKey);
    setEquipmentDialog({
      isOpen: true,
      groupKey,
      mode: 'attach',
      selectedEquipmentId: '',
      draft: createProjectEquipmentDraft(group?.categories?.[0] || 'other'),
    });
    setEquipmentMessage('');
  };

  const closeEquipmentDialog = () => {
    setEquipmentDialog({
      isOpen: false,
      groupKey: null,
      mode: 'attach',
      selectedEquipmentId: '',
      draft: createProjectEquipmentDraft(),
    });
  };

  const handleProjectCableSelectionChange = async (role, value) => {
    setEquipmentSaving(true);
    setEquipmentMessage('');
    try {
      const nextSelections = PROJECT_EQUIPMENT_SELECTION_ROLES.reduce((result, roleKey) => {
        result[roleKey] = null;
        return result;
      }, {});
      Object.assign(nextSelections, projectEquipmentSelections, {
        [role]: value ? Number(value) : null,
      });
      const response = await projectsApi.updateEquipmentSelections(projectId, {
        selections: nextSelections,
      });
      setProjectEquipmentSelections(response?.selections || {});
      await loadEquipmentSpecification();
      setEquipmentMessage('Кабель для проекта обновлён.');
    } catch (error) {
      console.error('Error updating project equipment selections:', error);
      setEquipmentMessage(`Ошибка обновления кабеля: ${error.message}`);
    } finally {
      setEquipmentSaving(false);
    }
  };

  const handleAttachEquipment = async () => {
    if (!equipmentDialog.selectedEquipmentId) {
      return;
    }
    setEquipmentSaving(true);
    setEquipmentMessage('');
    try {
      const response = await projectsApi.attachEquipment(projectId, {
        equipment_id: Number(equipmentDialog.selectedEquipmentId),
      });
      const selections = await projectsApi.getEquipmentSelections(projectId);
      setProjectEquipmentItems(response?.items || []);
      setProjectEquipmentSelections(selections?.selections || {});
      await loadEquipmentSpecification();
      setEquipmentMessage('Оборудование добавлено в проект.');
      closeEquipmentDialog();
    } catch (error) {
      console.error('Error attaching equipment to project:', error);
      setEquipmentMessage(`Ошибка добавления оборудования: ${error.message}`);
    } finally {
      setEquipmentSaving(false);
    }
  };

  const handleCreateAndAttachEquipment = async () => {
    setEquipmentSaving(true);
    setEquipmentMessage('');
    try {
      const response = await projectsApi.createAndAttachEquipment(
        projectId,
        buildProjectEquipmentPayload(equipmentDialog.draft),
      );
      const [refreshedCatalog, selections] = await Promise.all([
        equipmentApi.list(),
        projectsApi.getEquipmentSelections(projectId),
      ]);
      setEquipmentItems(refreshedCatalog);
      setProjectEquipmentItems(response?.items || []);
      setProjectEquipmentSelections(selections?.selections || {});
      await loadEquipmentSpecification();
      setEquipmentMessage('Карточка создана и добавлена в проект.');
      closeEquipmentDialog();
    } catch (error) {
      console.error('Error creating project equipment:', error);
      setEquipmentMessage(`Ошибка создания оборудования: ${error.message}`);
    } finally {
      setEquipmentSaving(false);
    }
  };

  const handleRemoveProjectEquipment = async (item) => {
    if (!window.confirm(`Убрать "${item.name}" из оборудования проекта?`)) {
      return;
    }
    setEquipmentSaving(true);
    setEquipmentMessage('');
    try {
      const response = await projectsApi.removeEquipment(projectId, item.id);
      const selections = await projectsApi.getEquipmentSelections(projectId);
      setProjectEquipmentItems(response?.items || []);
      setProjectEquipmentSelections(selections?.selections || {});
      await loadEquipmentSpecification();
      setEquipmentMessage('Оборудование убрано из проекта.');
    } catch (error) {
      console.error('Error removing project equipment:', error);
      setEquipmentMessage(`Ошибка удаления оборудования: ${error.message}`);
    } finally {
      setEquipmentSaving(false);
    }
  };

  const refreshFloorPlans = async () => {
    try {
      const data = await floorPlansApi.list(projectId);
      setFloorPlans(data);
      await loadEquipmentSpecification();
    } catch (error) {
      console.error('Error refreshing floor plans:', error);
    }
  };

  const handleUploadFloorPlan = async (event) => {
    const input = event.target;
    const file = input.files?.[0];
    if (!file) {
      return;
    }

    const isValidFile = await validateFloorPlanFile(file);
    if (!isValidFile) {
      alert(FLOOR_PLAN_UPLOAD_VALIDATION_MESSAGE);
      input.value = '';
      return;
    }

    setUploadingFloor(true);
    const formData = new FormData();
    formData.append('file', file);
    formData.append('project_id', projectId);
    formData.append('floor_number', floorPlans.length + 1);
    formData.append('name', `Этаж ${floorPlans.length + 1}`);
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
      input.value = '';
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
        if (filenameMatch?.[1]) {
          filename = filenameMatch[1].replace(/['"]/g, '');
        }
      }

      link.download = filename;
      document.body.appendChild(link);
      link.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(link);
    } catch (error) {
      console.error('Error generating PDF:', error);
      alert(`Ошибка при генерации PDF: ${error.message}`);
    } finally {
      setGeneratingPDF(false);
    }
  };

  const handleDeleteProject = async () => {
    const displayProjectName = project?.facility || project?.name || `#${projectId}`;
    if (!window.confirm(`Удалить проект "${displayProjectName}"? Это действие необратимо и удалит все планы этажей.`)) {
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

    if (!window.confirm(`Удалить план этажа "${floorPlanName}"? Это действие необратимо.`)) {
      return;
    }

    try {
      await floorPlansApi.remove(floorPlanId);
      setFloorPlans((prev) => prev.filter((item) => item.id !== floorPlanId));
      await loadEquipmentSpecification();
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

  const displayName = project.facility || project.name;
  const dialogGroup = PROJECT_EQUIPMENT_GROUPS.find((group) => group.key === equipmentDialog.groupKey) || null;
  const dialogOptions = dialogGroup ? (availableEquipmentByGroup[dialogGroup.key] || []) : [];
  const sharedStageFloorPlanId = floorPlans[0]?.id ?? null;
  const projectStageCards = [
    ...floorPlans.map((floorPlan) => ({
      key: `floor-${floorPlan.id}`,
      title: floorPlan.name,
      badge: `Этаж ${floorPlan.floor_number}`,
      meta: `${floorPlan.image_width} × ${floorPlan.image_height}px`,
      href: `/floor-plans/${floorPlan.id}`,
      isShared: false,
      isDisabled: false,
      floorPlanId: floorPlan.id,
      floorPlanName: floorPlan.name,
    })),
    {
      key: GENERAL_DATA_STEP_KEY,
      title: 'Общие данные',
      badge: 'Общий этап проекта',
      meta: 'Редактируемый лист с ведомостями и текстом подтверждения.',
      href: buildSharedStageHref(sharedStageFloorPlanId, GENERAL_DATA_STEP_KEY),
      isShared: true,
      isDisabled: !sharedStageFloorPlanId,
    },
    {
      key: GENERAL_INSTRUCTIONS_STEP_KEY,
      title: 'Общие указания',
      badge: 'Общий этап проекта',
      meta: 'Редактируемый автоматический текст раздела перед генерацией PDF.',
      href: buildSharedStageHref(sharedStageFloorPlanId, GENERAL_INSTRUCTIONS_STEP_KEY),
      isShared: true,
      isDisabled: !sharedStageFloorPlanId,
    },
    {
      key: POWER_CONSUMPTION_STEP_KEY,
      title: 'Расчет токопотребления',
      badge: 'Общий этап проекта',
      meta: 'Учитывает все оборудование проекта',
      href: buildSharedStageHref(sharedStageFloorPlanId, POWER_CONSUMPTION_STEP_KEY),
      isShared: true,
      isDisabled: !sharedStageFloorPlanId,
    },
    {
      key: EQUIPMENT_SPECIFICATION_STEP_KEY,
      title: 'Спецификация',
      badge: 'Общий этап проекта',
      meta: 'Формируется по всему оборудованию проекта',
      href: buildSharedStageHref(sharedStageFloorPlanId, EQUIPMENT_SPECIFICATION_STEP_KEY),
      isShared: true,
      isDisabled: !sharedStageFloorPlanId,
    },
    {
      key: ADDITIONAL_INFO_STEP_KEY,
      title: 'Доп. сведения',
      badge: 'Общий этап проекта',
      meta: additionalInfoMeta?.is_empty === false
        ? 'Необязательный текстовый раздел, который будет добавлен в конец PDF.'
        : 'Необязательный текстовый раздел. Пока пустой и подсвечен полупрозрачно.',
      href: buildSharedStageHref(sharedStageFloorPlanId, ADDITIONAL_INFO_STEP_KEY),
      isShared: true,
      isDisabled: !sharedStageFloorPlanId,
      isSubtle: additionalInfoMeta?.is_empty !== false,
    },
  ];

  const floorPlansContent = floorPlans.length === 0 ? (
    <div className="project-detail-empty-state">
      <p style={{ color: '#6c757d' }}>
        Пока нет планов этажей. Загрузите изображение плана этажа, чтобы начать работу.
      </p>
    </div>
  ) : (
    <div className="project-grid project-detail-floor-plans-grid">
      {floorPlans.map((floorPlan) => (
        <div key={floorPlan.id} style={{ position: 'relative' }}>
          <Link to={`/floor-plans/${floorPlan.id}`} style={{ textDecoration: 'none' }}>
            <div className="project-card">
              <h3>{floorPlan.name}</h3>
              <p><strong>Этаж:</strong> {floorPlan.floor_number}</p>
              <p><strong>Размеры:</strong> {floorPlan.image_width} × {floorPlan.image_height}px</p>
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
  );

  return (
    <div className="project-detail-page">
      <div className="project-list-container project-detail-page__panel">
        <div className="project-list-header">
          <div className="project-list-header__info">
            <div>
              <h1>{displayName}</h1>
              <p style={{ color: '#6c757d' }}>Шифр: {project.code}</p>
            </div>
            <div className="project-list-header__cost">
              <span className="project-list-header__cost-label">Примерная стоимость проекта</span>
              <strong className="project-list-header__cost-value">
                {approximateProjectCost === null ? '—' : `${formatEquipmentPrice(approximateProjectCost)} ₽`}
              </strong>
            </div>
          </div>
          <div style={{ display: 'flex', gap: '10px' }}>
            <button className="btn btn-success" onClick={handleGeneratePDF} disabled={generatingPDF}>
              {generatingPDF ? 'Генерация PDF...' : 'Сгенерировать PDF'}
            </button>
            <button className="btn btn-danger" onClick={handleDeleteProject} style={{ background: '#dc3545' }}>
              Удалить проект
            </button>
          </div>
        </div>

        <section className="project-detail-stages">
          <div className="project-detail-stages__header">
            <div>
              <h2 style={{ margin: 0 }}>Этапы проекта</h2>
              <p className="project-detail-stages__subtitle">
                Этажи, общий расчет токопотребления и спецификация проекта. Общие этапы используют все оборудование проекта.
              </p>
            </div>
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

          <div className="project-stage-strip">
            {projectStageCards.map((card) => {
              const cardContent = (
                <div className={`project-card project-stage-card${card.isDisabled ? ' project-stage-card--disabled' : ''}${card.isSubtle ? ' project-stage-card--subtle' : ''}`}>
                  <span className={`project-stage-card__badge${card.isShared ? ' project-stage-card__badge--shared' : ''}`}>
                    {card.badge}
                  </span>
                  <h3>{card.title}</h3>
                  <p>{card.meta}</p>
                  {card.isDisabled && (
                    <p className="project-stage-card__hint">
                      Сначала загрузите хотя бы один план этажа, чтобы открыть этот общий этап.
                    </p>
                  )}
                </div>
              );

              return (
                <div key={card.key} className="project-stage-card-wrapper">
                  {card.href ? (
                    <Link to={card.href} className="project-stage-card-link">
                      {cardContent}
                    </Link>
                  ) : (
                    cardContent
                  )}
                  {!card.isShared && (
                    <button
                      onClick={(event) => handleDeleteFloorPlan(event, card.floorPlanId, card.floorPlanName)}
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
                  )}
                </div>
              );
            })}
          </div>

          {floorPlans.length === 0 && (
            <div className="project-detail-empty-state">
              <p style={{ color: '#6c757d' }}>
                Пока нет планов этажей. Загрузите изображение плана этажа, чтобы начать работу с этапами проекта.
              </p>
            </div>
          )}
        </section>

        {false && (
        <section className="project-detail-overview">
          <h2 style={{ margin: 0 }}>Детали проекта</h2>
          <div className="project-detail-overview__grid">
            <div className="project-detail-card">
              <div className="project-detail-card__header">
                <h3 style={{ margin: 0 }}>Реквизиты проекта</h3>
                <button className="btn btn-primary" onClick={handleSaveProject} disabled={savingProject}>
                  {savingProject ? 'Сохранение...' : 'Сохранить'}
                </button>
              </div>

              {saveMessage && (
                <div style={{ color: saveMessage.startsWith('Ошибка') ? '#dc3545' : '#198754' }}>
                  {saveMessage}
                </div>
              )}

              <table className="project-detail-table">
                <tbody>
                  <tr style={{ borderBottom: '1px solid #dee2e6' }}>
                    <td style={{ padding: '0.5rem', fontWeight: 'bold', width: '220px' }}>Объект:</td>
                    <td style={{ padding: '0.5rem' }}>
                      <input type="text" name="facility" value={projectForm.facility} onChange={handleProjectFieldChange} style={{ width: '100%' }} />
                    </td>
                  </tr>
                  <tr style={{ borderBottom: '1px solid #dee2e6' }}>
                    <td style={{ padding: '0.5rem', fontWeight: 'bold' }}>Объект, род. падеж:</td>
                    <td style={{ padding: '0.5rem' }}>
                      <input type="text" name="facility_genitive" value={projectForm.facility_genitive} onChange={handleProjectFieldChange} style={{ width: '100%' }} />
                    </td>
                  </tr>
                  <tr style={{ borderBottom: '1px solid #dee2e6' }}>
                    <td style={{ padding: '0.5rem', fontWeight: 'bold' }}>Объект, твор. падеж:</td>
                    <td style={{ padding: '0.5rem' }}>
                      <input type="text" name="facility_instrumental" value={projectForm.facility_instrumental} onChange={handleProjectFieldChange} style={{ width: '100%' }} />
                    </td>
                  </tr>
                  <tr style={{ borderBottom: '1px solid #dee2e6' }}>
                    <td style={{ padding: '0.5rem', fontWeight: 'bold' }}>Тип:</td>
                    <td style={{ padding: '0.5rem' }}>
                      <input type="text" name="project_type" value={projectForm.project_type} onChange={handleProjectFieldChange} style={{ width: '100%' }} />
                    </td>
                  </tr>
                  <tr style={{ borderBottom: '1px solid #dee2e6' }}>
                    <td style={{ padding: '0.5rem', fontWeight: 'bold' }}>Год:</td>
                    <td style={{ padding: '0.5rem' }}>
                      <input type="number" name="year" value={projectForm.year} onChange={handleProjectFieldChange} min="2000" style={{ maxWidth: '180px', width: '100%' }} />
                    </td>
                  </tr>
                  <tr style={{ borderBottom: '1px solid #dee2e6' }}>
                    <td style={{ padding: '0.5rem', fontWeight: 'bold' }}>Подрядчик:</td>
                    <td style={{ padding: '0.5rem' }}>
                      <input type="text" name="contractor" value={projectForm.contractor} onChange={handleProjectFieldChange} style={{ width: '100%' }} />
                    </td>
                  </tr>
                  <tr style={{ borderBottom: '1px solid #dee2e6' }}>
                    <td style={{ padding: '0.5rem', fontWeight: 'bold' }}>Инженер:</td>
                    <td style={{ padding: '0.5rem' }}>
                      <input type="text" name="engineer" value={projectForm.engineer} onChange={handleProjectFieldChange} style={{ width: '100%' }} />
                    </td>
                  </tr>
                  {isDeveloper && (
                    <tr style={{ borderBottom: '1px solid #dee2e6' }}>
                      <td style={{ padding: '0.5rem', fontWeight: 'bold' }}>Владелец проекта:</td>
                      <td style={{ padding: '0.5rem' }}>
                        <select name="owner_user_id" value={projectForm.owner_user_id} onChange={handleProjectFieldChange} style={{ width: '100%' }}>
                          <option value="">Без владельца</option>
                          {ownerUsers.map((owner) => (
                            <option key={owner.id} value={owner.id}>
                              {owner.full_name} ({owner.username})
                            </option>
                          ))}
                        </select>
                      </td>
                    </tr>
                  )}
                  <tr style={{ borderBottom: '1px solid #dee2e6' }}>
                    <td style={{ padding: '0.5rem', fontWeight: 'bold' }}>Адрес:</td>
                    <td style={{ padding: '0.5rem' }}>
                      <input type="text" name="facility_address" value={projectForm.facility_address} onChange={handleProjectFieldChange} style={{ width: '100%' }} />
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

            <div className="project-detail-card">
              <div className="project-detail-card__header">
                <h3 style={{ margin: 0 }}>Планы этажей</h3>
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
              {floorPlansContent}
            </div>
          </div>
        </section>
        )}

        <section className="project-detail-overview">
          <h2 style={{ margin: 0 }}>Детали проекта</h2>
          <div className="project-detail-overview__grid">
            <div className="project-detail-card">
              <div className="project-detail-card__header">
                <h3 style={{ margin: 0 }}>Реквизиты проекта</h3>
                <button className="btn btn-primary" onClick={handleSaveProject} disabled={savingProject}>
                  {savingProject ? 'Сохранение...' : 'Сохранить'}
                </button>
              </div>

              {saveMessage && (
                <div style={{ color: saveMessage.startsWith('Ошибка') ? '#dc3545' : '#198754' }}>
                  {saveMessage}
                </div>
              )}

              <table className="project-detail-table">
                <tbody>
                  <tr style={{ borderBottom: '1px solid #dee2e6' }}>
                    <td style={{ padding: '0.5rem', fontWeight: 'bold', width: '220px' }}>Объект:</td>
                    <td style={{ padding: '0.5rem' }}>
                      <input type="text" name="facility" value={projectForm.facility} onChange={handleProjectFieldChange} style={{ width: '100%' }} />
                    </td>
                  </tr>
                  <tr style={{ borderBottom: '1px solid #dee2e6' }}>
                    <td style={{ padding: '0.5rem', fontWeight: 'bold' }}>Объект, род. падеж:</td>
                    <td style={{ padding: '0.5rem' }}>
                      <input type="text" name="facility_genitive" value={projectForm.facility_genitive} onChange={handleProjectFieldChange} style={{ width: '100%' }} />
                    </td>
                  </tr>
                  <tr style={{ borderBottom: '1px solid #dee2e6' }}>
                    <td style={{ padding: '0.5rem', fontWeight: 'bold' }}>Объект, твор. падеж:</td>
                    <td style={{ padding: '0.5rem' }}>
                      <input type="text" name="facility_instrumental" value={projectForm.facility_instrumental} onChange={handleProjectFieldChange} style={{ width: '100%' }} />
                    </td>
                  </tr>
                  <tr style={{ borderBottom: '1px solid #dee2e6' }}>
                    <td style={{ padding: '0.5rem', fontWeight: 'bold' }}>Тип:</td>
                    <td style={{ padding: '0.5rem' }}>
                      <input type="text" name="project_type" value={projectForm.project_type} onChange={handleProjectFieldChange} style={{ width: '100%' }} />
                    </td>
                  </tr>
                  <tr style={{ borderBottom: '1px solid #dee2e6' }}>
                    <td style={{ padding: '0.5rem', fontWeight: 'bold' }}>Год:</td>
                    <td style={{ padding: '0.5rem' }}>
                      <input type="number" name="year" value={projectForm.year} onChange={handleProjectFieldChange} min="2000" style={{ maxWidth: '180px', width: '100%' }} />
                    </td>
                  </tr>
                  <tr style={{ borderBottom: '1px solid #dee2e6' }}>
                    <td style={{ padding: '0.5rem', fontWeight: 'bold' }}>Подрядчик:</td>
                    <td style={{ padding: '0.5rem' }}>
                      <input type="text" name="contractor" value={projectForm.contractor} onChange={handleProjectFieldChange} style={{ width: '100%' }} />
                    </td>
                  </tr>
                  <tr style={{ borderBottom: '1px solid #dee2e6' }}>
                    <td style={{ padding: '0.5rem', fontWeight: 'bold' }}>Инженер:</td>
                    <td style={{ padding: '0.5rem' }}>
                      <input type="text" name="engineer" value={projectForm.engineer} onChange={handleProjectFieldChange} style={{ width: '100%' }} />
                    </td>
                  </tr>
                  <tr style={{ borderBottom: '1px solid #dee2e6' }}>
                    <td style={{ padding: '0.5rem', fontWeight: 'bold' }}>Адрес:</td>
                    <td style={{ padding: '0.5rem' }}>
                      <input type="text" name="facility_address" value={projectForm.facility_address} onChange={handleProjectFieldChange} style={{ width: '100%' }} />
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
              {isDeveloper && (
                <div className="project-detail-owner-field">
                  <label className="project-equipment-role">
                    <span>Владелец проекта</span>
                    <select name="owner_user_id" value={projectForm.owner_user_id} onChange={handleProjectFieldChange}>
                      <option value="">Без владельца</option>
                      {ownerUsers.map((owner) => (
                        <option key={owner.id} value={owner.id}>
                          {owner.full_name} ({owner.username})
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
              )}
            </div>

            <div className="project-detail-card">
              <div className="project-equipment-section__header">
                <div>
                  <h3 style={{ margin: 0 }}>Оборудование проекта</h3>
                  <p className="project-equipment-section__subtitle">
                    В проект добавляются конкретные карточки оборудования. Они используются в редакторе плана, расчете токопотребления и спецификации.
                  </p>
                </div>
              </div>

              {equipmentMessage && (
                <div style={{ color: equipmentMessage.startsWith('Ошибка') ? '#dc3545' : '#198754', marginBottom: '1rem' }}>
                  {equipmentMessage}
                </div>
              )}

              {equipmentLoading ? (
                <div className="loading">Загрузка оборудования проекта...</div>
              ) : (
                <div className="project-equipment-groups">
                  {PROJECT_EQUIPMENT_GROUPS.map((group) => {
                    const linkedItems = projectEquipmentByGroup[group.key] || [];
                    const cableRole = group.key === 'sps'
                      ? 'sps_cable'
                      : (group.key === 'soue' ? 'soue_cable' : null);
                    const visibleLinkedItems = cableRole
                      ? linkedItems.filter((item) => item.category !== 'cable')
                      : linkedItems;
                    const selectedCableId = cableRole ? String(projectEquipmentSelections[cableRole] || '') : '';

                    return (
                      <div key={group.key} className="project-equipment-group project-equipment-group--linked">
                        <div className="project-equipment-group__header">
                          <div>
                            <h3>{group.label}</h3>
                            <p>{group.description}</p>
                          </div>
                          <button
                            type="button"
                            className="btn btn-primary project-equipment-group__add"
                            onClick={() => openEquipmentDialog(group.key)}
                            disabled={equipmentSaving}
                          >
                            + Добавить
                          </button>
                        </div>

                        {visibleLinkedItems.length === 0 ? (
                          <div className="project-equipment-empty">
                            В этом разделе пока нет карточек оборудования.
                          </div>
                        ) : (
                          <div className="project-equipment-linked-list">
                            {visibleLinkedItems.map((item) => (
                              <div key={item.id} className="project-equipment-linked-item">
                                <div className="project-equipment-linked-item__main">
                                  <strong>{item.name}</strong>
                                  <span>{getEquipmentCategoryLabel(item.category)}</span>
                                </div>
                                <div className="project-equipment-linked-item__meta">
                                  <span>{formatEquipmentPrice(item.price)} ₽</span>
                                  <button
                                    type="button"
                                    className="btn btn-secondary"
                                    onClick={() => handleRemoveProjectEquipment(item)}
                                    disabled={equipmentSaving}
                                  >
                                    Убрать
                                  </button>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}

                        {cableRole && (
                          <div className="project-equipment-role project-equipment-cable-field">
                            <span>{group.key === 'sps' ? 'Кабель СПС' : 'Кабель СОУЭ'}</span>
                            {projectCableOptions.length > 0 ? (
                              <select
                                aria-label={group.key === 'sps' ? 'Кабель СПС' : 'Кабель СОУЭ'}
                                value={selectedCableId}
                                onChange={(event) => handleProjectCableSelectionChange(cableRole, event.target.value)}
                                disabled={equipmentSaving}
                              >
                                <option value="">Не выбран</option>
                                {projectCableOptions.map((item) => (
                                  <option key={`${cableRole}-${item.id}`} value={item.id}>
                                    {item.name} — {formatEquipmentPrice(item.price)} ₽
                                  </option>
                                ))}
                              </select>
                            ) : (
                              <div className="project-equipment-empty">
                                Сначала добавьте в проект хотя бы одну карточку кабеля.
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </section>

        {false && (
        <section className="project-equipment-section">
          <div className="project-equipment-section__header">
            <div>
              <h2 style={{ margin: 0 }}>Оборудование проекта</h2>
              <p className="project-equipment-section__subtitle">
                В проект теперь добавляются конкретные карточки оборудования. Именно они будут использоваться
                в редакторе плана и в подсчётах.
              </p>
            </div>
          </div>

          {equipmentMessage && (
            <div style={{ color: equipmentMessage.startsWith('Ошибка') ? '#dc3545' : '#198754', marginBottom: '1rem' }}>
              {equipmentMessage}
            </div>
          )}

          {equipmentLoading ? (
            <div className="loading">Загрузка оборудования проекта...</div>
          ) : (
            <div className="project-equipment-groups">
              {PROJECT_EQUIPMENT_GROUPS.map((group) => {
                const linkedItems = projectEquipmentByGroup[group.key] || [];
                const cableRole = group.key === 'sps'
                  ? 'sps_cable'
                  : (group.key === 'soue' ? 'soue_cable' : null);
                const visibleLinkedItems = cableRole
                  ? linkedItems.filter((item) => item.category !== 'cable')
                  : linkedItems;
                const selectedCableId = cableRole ? String(projectEquipmentSelections[cableRole] || '') : '';

                return (
                  <div key={group.key} className="project-equipment-group project-equipment-group--linked">
                    <div className="project-equipment-group__header">
                      <div>
                        <h3>{group.label}</h3>
                        <p>{group.description}</p>
                      </div>
                      <button
                        type="button"
                        className="btn btn-primary project-equipment-group__add"
                        onClick={() => openEquipmentDialog(group.key)}
                        disabled={equipmentSaving}
                      >
                        + Добавить
                      </button>
                    </div>

                    {visibleLinkedItems.length === 0 ? (
                      <div className="project-equipment-empty">
                        В этом разделе пока нет карточек оборудования.
                      </div>
                    ) : (
                      <div className="project-equipment-linked-list">
                        {visibleLinkedItems.map((item) => (
                          <div key={item.id} className="project-equipment-linked-item">
                            <div className="project-equipment-linked-item__main">
                              <strong>{item.name}</strong>
                              <span>{getEquipmentCategoryLabel(item.category)}</span>
                            </div>
                            <div className="project-equipment-linked-item__meta">
                              <span>{formatEquipmentPrice(item.price)} ₽</span>
                              <button
                                type="button"
                                className="btn btn-secondary"
                                onClick={() => handleRemoveProjectEquipment(item)}
                                disabled={equipmentSaving}
                              >
                                Убрать
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}

                    {cableRole && (
                      <div className="project-equipment-role project-equipment-cable-field">
                        <span>{group.key === 'sps' ? 'Кабель СПС' : 'Кабель СОУЭ'}</span>
                        {projectCableOptions.length > 0 ? (
                          <select
                            aria-label={group.key === 'sps' ? 'Кабель СПС' : 'Кабель СОУЭ'}
                            value={selectedCableId}
                            onChange={(event) => handleProjectCableSelectionChange(cableRole, event.target.value)}
                            disabled={equipmentSaving}
                          >
                            <option value="">Не выбран</option>
                            {projectCableOptions.map((item) => (
                              <option key={`${cableRole}-${item.id}`} value={item.id}>
                                {item.name} — {formatEquipmentPrice(item.price)} ₽
                              </option>
                            ))}
                          </select>
                        ) : (
                          <div className="project-equipment-empty">
                            Сначала добавьте в проект хотя бы одну карточку кабеля.
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </section>
        )}

        {equipmentDialog.isOpen && dialogGroup && (
          <div className="equipment-modal-backdrop" onClick={closeEquipmentDialog}>
            <div
              className="equipment-modal project-equipment-dialog"
              role="dialog"
              aria-modal="true"
              aria-label={`Добавить оборудование в раздел ${dialogGroup.label}`}
              onClick={(event) => event.stopPropagation()}
            >
              <div className="equipment-modal__header">
                <div>
                  <h2>Добавить в раздел «{dialogGroup.label}»</h2>
                  <div className="equipment-modal__category">
                    Можно привязать карточку из каталога или создать новую на месте.
                  </div>
                </div>
                <button type="button" className="tool-button" onClick={closeEquipmentDialog}>×</button>
              </div>

              <div className="project-equipment-dialog__mode">
                <button
                  type="button"
                  className={`tool-button ${equipmentDialog.mode === 'attach' ? 'active' : ''}`}
                  onClick={() => setEquipmentDialog((prev) => ({ ...prev, mode: 'attach' }))}
                >
                  Из каталога
                </button>
                <button
                  type="button"
                  className={`tool-button ${equipmentDialog.mode === 'create' ? 'active' : ''}`}
                  onClick={() => setEquipmentDialog((prev) => ({ ...prev, mode: 'create' }))}
                >
                  Новая карточка
                </button>
              </div>

              {equipmentDialog.mode === 'attach' ? (
                <div className="project-equipment-dialog__body">
                  <label className="project-equipment-role">
                    <span>Карточка оборудования</span>
                    <select
                      aria-label="Карточка оборудования"
                      value={equipmentDialog.selectedEquipmentId}
                      onChange={(event) => setEquipmentDialog((prev) => ({
                        ...prev,
                        selectedEquipmentId: event.target.value,
                      }))}
                    >
                      <option value="">Выберите карточку</option>
                      {dialogOptions.map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.name} — {getEquipmentCategoryLabel(item.category)} — {formatEquipmentPrice(item.price)} ₽
                        </option>
                      ))}
                    </select>
                  </label>

                  {dialogOptions.length === 0 && (
                    <div className="project-equipment-empty">
                      Для этого раздела в каталоге не осталось свободных карточек. Можно создать новую
                      карточку прямо здесь.
                    </div>
                  )}
                </div>
              ) : (
                <div className="project-equipment-dialog__body project-equipment-dialog__body--form">
                  <label className="project-equipment-role">
                    <span>Название</span>
                    <input
                      type="text"
                      value={equipmentDialog.draft.name}
                      onChange={(event) => setEquipmentDialog((prev) => ({
                        ...prev,
                        draft: {
                          ...prev.draft,
                          name: event.target.value,
                        },
                      }))}
                    />
                  </label>
                  <label className="project-equipment-role">
                    <span>Категория</span>
                    <select
                      value={equipmentDialog.draft.category}
                      onChange={(event) => setEquipmentDialog((prev) => ({
                        ...prev,
                        draft: {
                          ...prev.draft,
                          category: event.target.value,
                        },
                      }))}
                    >
                      {dialogGroup.categories.map((category) => (
                        <option key={category} value={category}>
                          {getEquipmentCategoryLabel(category)}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="project-equipment-role">
                    <span>Цена</span>
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      value={equipmentDialog.draft.price}
                      onChange={(event) => setEquipmentDialog((prev) => ({
                        ...prev,
                        draft: {
                          ...prev.draft,
                          price: event.target.value,
                        },
                      }))}
                    />
                  </label>
                  {equipmentDialog.draft.category === 'mounting' && (
                    <>
                      <label className="project-equipment-role">
                        <span>{'\u041a\u043e\u043b-\u0432\u043e \u0448\u0442\u0443\u043a \u0432 \u043f\u0430\u0447\u043a\u0435'}</span>
                        <input
                          type="number"
                          min="1"
                          step="1"
                          value={equipmentDialog.draft.pack_quantity}
                          onChange={(event) => setEquipmentDialog((prev) => ({
                            ...prev,
                            draft: {
                              ...prev.draft,
                              pack_quantity: event.target.value,
                            },
                          }))}
                        />
                      </label>
                      <label className="project-equipment-role">
                        <span>{'\u041a\u0440\u0430\u0442\u043d\u043e\u0441\u0442\u044c \u043a\u0440\u0435\u043f\u043b\u0435\u043d\u0438\u044f, \u043c'}</span>
                        <input
                          type="number"
                          min="0.1"
                          step="0.1"
                          value={equipmentDialog.draft.mounting_spacing_m}
                          onChange={(event) => setEquipmentDialog((prev) => ({
                            ...prev,
                            draft: {
                              ...prev.draft,
                              mounting_spacing_m: event.target.value,
                            },
                          }))}
                        />
                      </label>
                    </>
                  )}
                  <label className="project-equipment-role project-equipment-role--full">
                    <span>Описание</span>
                    <textarea
                      rows="4"
                      value={equipmentDialog.draft.description}
                      onChange={(event) => setEquipmentDialog((prev) => ({
                        ...prev,
                        draft: {
                          ...prev.draft,
                          description: event.target.value,
                        },
                      }))}
                    />
                  </label>
                </div>
              )}

              <div className="equipment-modal__footer">
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={equipmentDialog.mode === 'attach' ? handleAttachEquipment : handleCreateAndAttachEquipment}
                  disabled={equipmentSaving || (equipmentDialog.mode === 'attach' && !equipmentDialog.selectedEquipmentId)}
                >
                  {equipmentSaving ? 'Сохранение...' : 'Добавить в проект'}
                </button>
                <button type="button" className="btn btn-secondary" onClick={closeEquipmentDialog} disabled={equipmentSaving}>
                  Отмена
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default ProjectDetail;
