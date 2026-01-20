import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { Stage, Layer, Line, Rect, Circle, Text, Image as KonvaImage, Group } from 'react-konva';
import Konva from 'konva';

// Delete Button Component for Canvas
function DeleteButton({ x, y, onClick }) {
  return (
    <Group x={x} y={y}>
      <Circle
        radius={12}
        fill="red"
        stroke="darkred"
        strokeWidth={2}
        onClick={onClick}
        onMouseEnter={(e) => {
          e.target.getStage().container().style.cursor = 'pointer';
        }}
        onMouseLeave={(e) => {
          e.target.getStage().container().style.cursor = 'default';
        }}
      />
      <Text
        text="×"
        fontSize={18}
        fontFamily="Arial"
        fill="white"
        fontStyle="bold"
        x={-5}
        y={-9}
        onClick={onClick}
        onMouseEnter={(e) => {
          e.target.getStage().container().style.cursor = 'pointer';
        }}
        onMouseLeave={(e) => {
          e.target.getStage().container().style.cursor = 'default';
        }}
      />
    </Group>
  );
}

// Background Image Component
function BackgroundImage({ src }) {
  const [image, setImage] = useState(null);
  const imageRef = useRef(null);
  
  useEffect(() => {
    const img = new window.Image();
    // Добавляем timestamp для обхода кэша браузера
    img.src = `${src}?t=${Date.now()}`;
    img.onload = () => {
      setImage(img);
    };
  }, [src]);
  
  useEffect(() => {
    if (imageRef.current) {
      imageRef.current.cache();
      imageRef.current.getLayer().batchDraw();
    }
  }, [image]);
  
  if (!image) return null;
  return <KonvaImage ref={imageRef} image={image} filters={[Konva.Filters.Grayscale]} listening={false} />;
}

function FloorPlanEditor() {
  const { floorPlanId } = useParams();
  const stageRef = useRef(null);
  const [floorPlan, setFloorPlan] = useState(null);
  const [walls, setWalls] = useState([]);
  const [doors, setDoors] = useState([]);
  const [windows, setWindows] = useState([]);
  const [rooms, setRooms] = useState([]);
  const [dimensions, setDimensions] = useState([]);
  const [fireAlarms, setFireAlarms] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedTool, setSelectedTool] = useState('select');
  const [selectedElement, setSelectedElement] = useState(null);
  const [hoveredElement, setHoveredElement] = useState(null);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [deletedElements, setDeletedElements] = useState([]);
  const [newWalls, setNewWalls] = useState([]);
  const [modifiedWalls, setModifiedWalls] = useState({});
  const [modifiedElements, setModifiedElements] = useState({});
  const [drawingWall, setDrawingWall] = useState(null);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const [editingWall, setEditingWall] = useState(null);
  const [shiftPressed, setShiftPressed] = useState(false);
  const [history, setHistory] = useState([]);

  const fetchFloorPlan = useCallback(async () => {
    try {
      const response = await fetch(`/api/floor-plans/${floorPlanId}?include_elements=true`);
      const data = await response.json();
      setFloorPlan(data);
      setWalls(data.walls || []);
      setDoors(data.doors || []);
      setWindows(data.windows || []);
      setRooms(data.rooms || []);
      setDimensions(data.dimensions || []);
      setFireAlarms(data.fire_alarms || []);
      setLoading(false);
    } catch (error) {
      console.error('Error fetching floor plan:', error);
      setLoading(false);
    }
  }, [floorPlanId]);

  useEffect(() => {
    fetchFloorPlan();
  }, [fetchFloorPlan]);

  const saveToHistory = useCallback(() => {
    setHistory(prev => [...prev, {
      deletedElements: [...deletedElements],
      newWalls: [...newWalls],
      modifiedWalls: { ...modifiedWalls },
      modifiedElements: { ...modifiedElements }
    }]);
  }, [deletedElements, newWalls, modifiedWalls, modifiedElements]);

  const handleDeleteElement = useCallback((type, id) => {
    // Сохраняем состояние в историю
    setHistory(prev => [...prev, {
      deletedElements: [...deletedElements],
      newWalls: [...newWalls],
      modifiedWalls: { ...modifiedWalls },
      modifiedElements: { ...modifiedElements }
    }]);
    
    // Добавляем элемент в список удаленных
    setDeletedElements(prev => [...prev, { type, id }]);
    setSelectedElement(null);
    setHasUnsavedChanges(true);
  }, [deletedElements, newWalls, modifiedWalls, modifiedElements]);

  const handleSaveChanges = useCallback(async () => {
    // Если нет изменений, ничего не делаем
    if (!hasUnsavedChanges) return;
    
    try {
      // Отправляем все удаления на сервер
      for (const element of deletedElements) {
        const endpoint = `/api/${element.type}/${element.id}`;
        await fetch(endpoint, { method: 'DELETE' });
      }
      
      // Отправляем все новые стены на сервер
      for (const wall of newWalls) {
        await fetch('/api/walls', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            x1: wall.x1,
            y1: wall.y1,
            x2: wall.x2,
            y2: wall.y2,
            floor_plan_id: parseInt(floorPlanId),
          }),
        });
      }
      
      // Отправляем все измененные стены на сервер
      for (const [wallId, modifications] of Object.entries(modifiedWalls)) {
        const wall = walls.find(w => w.id === parseInt(wallId));
        if (!wall) continue;
        
        // Собираем полный набор координат с учетом изменений
        const fullUpdate = {
          floor_plan_id: wall.floor_plan_id,
          x1: modifications.x1 !== undefined ? modifications.x1 : wall.x1,
          y1: modifications.y1 !== undefined ? modifications.y1 : wall.y1,
          x2: modifications.x2 !== undefined ? modifications.x2 : wall.x2,
          y2: modifications.y2 !== undefined ? modifications.y2 : wall.y2,
          thickness: wall.thickness,
          is_load_bearing: wall.is_load_bearing,
          material: wall.material,
        };
        
        await fetch(`/api/walls/${wallId}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(fullUpdate),
        });
      }

      // Отправляем изменения позиций других элементов
      for (const [key, newPos] of Object.entries(modifiedElements)) {
        const [type, id] = key.split('-');
        await fetch(`/api/${type}/${id}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(newPos),
        });
      }
      
      // Перезагружаем данные с сервера для синхронизации
      await fetchFloorPlan();
      
      // Очищаем список удаленных элементов, новых стен и измененных стен после загрузки
      setDeletedElements([]);
      setNewWalls([]);
      setModifiedWalls({});
      setModifiedElements({});
      setHasUnsavedChanges(false);
      setHistory([]); // Очищаем историю после сохранения
    } catch (error) {
      console.error('Error saving changes:', error);
    }
  }, [hasUnsavedChanges, deletedElements, newWalls, modifiedWalls, modifiedElements, walls, floorPlanId, fetchFloorPlan]);

  // Обработка клавиатурных событий
  useEffect(() => {
    const handleKeyDown = (e) => {
      // Shift для углов кратных 45°
      if (e.key === 'Shift') {
        setShiftPressed(true);
      }
      
      // Delete для удаления выделенного элемента
      if (e.key === 'Delete' && selectedElement) {
        e.preventDefault();
        const type = selectedElement.type === 'new-wall' ? 'new-walls' : 
                     selectedElement.type === 'fire-alarm' ? 'fire-alarms' : 
                     selectedElement.type + 's';
        handleDeleteElement(type, selectedElement.id);
      }
      
      // Ctrl+Z для отмены последнего действия (работает в любой раскладке)
      if (e.ctrlKey && e.code === 'KeyZ') {
        e.preventDefault();
        if (history.length > 0) {
          const previousState = history[history.length - 1];
          setDeletedElements(previousState.deletedElements);
          setNewWalls(previousState.newWalls);
          setModifiedWalls(previousState.modifiedWalls);
          setModifiedElements(previousState.modifiedElements);
          setHistory(prev => prev.slice(0, -1));
          
          // Проверяем, остались ли изменения после отмены
          const hasChanges = previousState.deletedElements.length > 0 ||
                           previousState.newWalls.length > 0 ||
                           Object.keys(previousState.modifiedWalls).length > 0 ||
                           Object.keys(previousState.modifiedElements).length > 0;
          setHasUnsavedChanges(hasChanges);
        }
      }
      
      // Ctrl+S для сохранения изменений (работает в любой раскладке)
      if (e.ctrlKey && e.code === 'KeyS') {
        e.preventDefault();
        handleSaveChanges();
      }
    };

    const handleKeyUp = (e) => {
      if (e.key === 'Shift') {
        setShiftPressed(false);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);

    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
    };
  }, [selectedElement, history, deletedElements, newWalls, modifiedWalls, modifiedElements, handleDeleteElement, handleSaveChanges]);

  // eslint-disable-next-line no-unused-vars
  const handleWallUpdate = async (wallId, updates) => {
    try {
      const response = await fetch(`/api/walls/${wallId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates),
      });
      if (response.ok) {
        fetchFloorPlan();
      }
    } catch (error) {
      console.error('Error updating wall:', error);
    }
  };

  // eslint-disable-next-line no-unused-vars
  const handleRoomUpdate = async (roomId, updates) => {
    try {
      const response = await fetch(`/api/rooms/${roomId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...updates, floor_plan_id: parseInt(floorPlanId) }),
      });
      if (response.ok) {
        fetchFloorPlan();
      }
    } catch (error) {
      console.error('Error updating room:', error);
    }
  };

  // Функция для расчета координат с учетом углов кратных 45°
  const snapTo45Degrees = (x1, y1, x2, y2) => {
    const dx = x2 - x1;
    const dy = y2 - y1;
    const angle = Math.atan2(dy, dx);
    const distance = Math.sqrt(dx * dx + dy * dy);
    
    // Приводим угол к ближайшему кратному 45° (π/4)
    const snappedAngle = Math.round(angle / (Math.PI / 4)) * (Math.PI / 4);
    
    return {
      x: x1 + distance * Math.cos(snappedAngle),
      y: y1 + distance * Math.sin(snappedAngle)
    };
  };

  const handleStageClick = (e) => {
    if (selectedTool === 'wall') {
      const stage = e.target.getStage();
      const point = stage.getPointerPosition();

      if (!drawingWall) {
        // Начало рисования стены
        setDrawingWall({ x1: point.x, y1: point.y });
      } else {
        // Завершение рисования стены - добавляем локально
        saveToHistory();
        
        let x2 = point.x;
        let y2 = point.y;
        
        // Если зажат Shift, привязываем к углам кратным 45°
        if (shiftPressed) {
          const snapped = snapTo45Degrees(drawingWall.x1, drawingWall.y1, x2, y2);
          x2 = snapped.x;
          y2 = snapped.y;
        }
        
        const newWall = {
          id: `temp_${Date.now()}`, // Временный ID
          x1: drawingWall.x1,
          y1: drawingWall.y1,
          x2: x2,
          y2: y2,
        };

        setNewWalls(prev => [...prev, newWall]);
        setDrawingWall(null);
        setHasUnsavedChanges(true);
      }
    } else if (selectedTool === 'select' && e.target === e.target.getStage()) {
      // Сброс выбора при клике на пустую область в режиме выбора
      setSelectedElement(null);
    }
  };

  const handleElementDragEnd = (type, id, e) => {
    saveToHistory();
    
    const node = e.target;
    const newPos = {
      x: node.x(),
      y: node.y(),
    };

    // Сохраняем изменения локально
    setModifiedElements(prev => ({
      ...prev,
      [`${type}-${id}`]: newPos
    }));
    setHasUnsavedChanges(true);
  };

  const handleWallDrag = (wallId, e) => {
    const node = e.target;
    const dx = node.x();
    const dy = node.y();
    
    setEditingWall({ id: wallId, isDragging: true, dx, dy });
  };

  const handleWallDragEnd = (wallId, originalWall, e) => {
    if (!editingWall || !editingWall.isDragging) return;
    
    saveToHistory();
    
    const node = e.target;
    const dx = node.x();
    const dy = node.y();

    // Вычисляем текущие координаты с учетом уже сохраненных изменений
    let currentX1 = originalWall.x1;
    let currentY1 = originalWall.y1;
    let currentX2 = originalWall.x2;
    let currentY2 = originalWall.y2;
    
    if (modifiedWalls[wallId]) {
      if (modifiedWalls[wallId].x1 !== undefined) currentX1 = modifiedWalls[wallId].x1;
      if (modifiedWalls[wallId].y1 !== undefined) currentY1 = modifiedWalls[wallId].y1;
      if (modifiedWalls[wallId].x2 !== undefined) currentX2 = modifiedWalls[wallId].x2;
      if (modifiedWalls[wallId].y2 !== undefined) currentY2 = modifiedWalls[wallId].y2;
    }

    // Сохраняем смещение обеих точек стены
    setModifiedWalls(prev => ({
      ...prev,
      [wallId]: {
        x1: currentX1 + dx,
        y1: currentY1 + dy,
        x2: currentX2 + dx,
        y2: currentY2 + dy,
      }
    }));
    
    // Сбрасываем позицию элемента обратно к (0,0)
    node.position({ x: 0, y: 0 });
    
    setHasUnsavedChanges(true);
    setEditingWall(null);
  };

  const handleWallPointDrag = (wallId, point, e) => {
    const stage = e.target.getStage();
    let pos = stage.getPointerPosition();
    
    // Если зажат Shift, привязываем к углам кратных 45°
    if (shiftPressed) {
      const wall = walls.find(w => w.id === wallId);
      if (wall) {
        const modifications = modifiedWalls[wallId] || {};
        const x1 = point === 'start' ? pos.x : (modifications.x1 !== undefined ? modifications.x1 : wall.x1);
        const y1 = point === 'start' ? pos.y : (modifications.y1 !== undefined ? modifications.y1 : wall.y1);
        const x2 = point === 'end' ? pos.x : (modifications.x2 !== undefined ? modifications.x2 : wall.x2);
        const y2 = point === 'end' ? pos.y : (modifications.y2 !== undefined ? modifications.y2 : wall.y2);
        
        if (point === 'start') {
          const snapped = snapTo45Degrees(x2, y2, x1, y1);
          pos = { x: snapped.x, y: snapped.y };
        } else {
          const snapped = snapTo45Degrees(x1, y1, x2, y2);
          pos = { x: snapped.x, y: snapped.y };
        }
      }
    }
    
    setEditingWall({ id: wallId, point, x: pos.x, y: pos.y });
  };

  const handleWallPointDragEnd = async (wallId, point, e) => {
    saveToHistory();
    
    const stage = e.target.getStage();
    let pos = stage.getPointerPosition();
    
    // Если зажат Shift, привязываем к углам кратных 45°
    if (shiftPressed) {
      const wall = walls.find(w => w.id === wallId);
      if (wall) {
        const modifications = modifiedWalls[wallId] || {};
        const x1 = point === 'start' ? pos.x : (modifications.x1 !== undefined ? modifications.x1 : wall.x1);
        const y1 = point === 'start' ? pos.y : (modifications.y1 !== undefined ? modifications.y1 : wall.y1);
        const x2 = point === 'end' ? pos.x : (modifications.x2 !== undefined ? modifications.x2 : wall.x2);
        const y2 = point === 'end' ? pos.y : (modifications.y2 !== undefined ? modifications.y2 : wall.y2);
        
        if (point === 'start') {
          const snapped = snapTo45Degrees(x2, y2, x1, y1);
          pos = { x: snapped.x, y: snapped.y };
        } else {
          const snapped = snapTo45Degrees(x1, y1, x2, y2);
          pos = { x: snapped.x, y: snapped.y };
        }
      }
    }
    
    const updates = point === 'start' 
      ? { x1: pos.x, y1: pos.y }
      : { x2: pos.x, y2: pos.y };

    // Сохраняем изменения локально
    setModifiedWalls(prev => ({
      ...prev,
      [wallId]: {
        ...prev[wallId],
        ...updates
      }
    }));
    
    setEditingWall(null);
    setHasUnsavedChanges(true);
  };

  if (loading) {
    return <div className="loading">Загрузка плана этажа...</div>;
  }

  if (!floorPlan) {
    return <div>План этажа не найден</div>;
  }

  const imageUrl = floorPlan.original_image_path 
    ? `http://localhost:8000/${floorPlan.original_image_path.replace(/\\/g, '/')}`
    : null;

  // Use the actual floor plan dimensions for the stage
  const stageWidth = floorPlan.image_width || 800;
  const stageHeight = floorPlan.image_height || 600;

  return (
    <div className="editor-container">
      <div className="editor-sidebar">
        <div className="sidebar-section">
          <h3>Информация о плане</h3>
          <p><strong>Название:</strong> {floorPlan.name}</p>
          <p><strong>Этаж:</strong> {floorPlan.floor_number}</p>
          <p><strong>Размер:</strong> {floorPlan.image_width} × {floorPlan.image_height}px</p>
          <p><strong>Масштаб:</strong> {floorPlan.scale_factor} мм/px</p>
        </div>

        <div className="sidebar-section">
          <h3>Стены ({walls.filter(wall => !deletedElements.some(del => del.type === 'walls' && del.id === wall.id)).length})</h3>
          <ul className="element-list">
            {walls.filter(wall => !deletedElements.some(del => del.type === 'walls' && del.id === wall.id)).map((wall, index) => (
              <li
                key={wall.id}
                className={`element-item ${selectedElement?.type === 'wall' && selectedElement?.id === wall.id ? 'selected' : ''}`}
                onClick={() => setSelectedElement({ type: 'wall', id: wall.id, data: wall })}
              >
                <span>Стена {index + 1}</span>
                <button
                  className="element-delete"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDeleteElement('walls', wall.id);
                  }}
                >
                  ×
                </button>
              </li>
            ))}
          </ul>
        </div>

        <div className="sidebar-section">
          <h3>Двери ({doors.filter(door => !deletedElements.some(del => del.type === 'doors' && del.id === door.id)).length})</h3>
          <ul className="element-list">
            {doors.filter(door => !deletedElements.some(del => del.type === 'doors' && del.id === door.id)).map((door, index) => (
              <li
                key={door.id}
                className={`element-item ${selectedElement?.type === 'door' && selectedElement?.id === door.id ? 'selected' : ''}`}
                onClick={() => setSelectedElement({ type: 'door', id: door.id, data: door })}
              >
                <span>Дверь {index + 1}</span>
                <button
                  className="element-delete"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDeleteElement('doors', door.id);
                  }}
                >
                  ×
                </button>
              </li>
            ))}
          </ul>
        </div>

        <div className="sidebar-section">
          <h3>Окна ({windows.filter(window => !deletedElements.some(del => del.type === 'windows' && del.id === window.id)).length})</h3>
          <ul className="element-list">
            {windows.filter(window => !deletedElements.some(del => del.type === 'windows' && del.id === window.id)).map((window, index) => (
              <li
                key={window.id}
                className={`element-item ${selectedElement?.type === 'window' && selectedElement?.id === window.id ? 'selected' : ''}`}
                onClick={() => setSelectedElement({ type: 'window', id: window.id, data: window })}
              >
                <span>Окно {index + 1}</span>
                <button
                  className="element-delete"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDeleteElement('windows', window.id);
                  }}
                >
                  ×
                </button>
              </li>
            ))}
          </ul>
        </div>

        <div className="sidebar-section">
          <h3>Помещения ({rooms.filter(room => !deletedElements.some(del => del.type === 'rooms' && del.id === room.id)).length})</h3>
          <ul className="element-list">
            {rooms.filter(room => !deletedElements.some(del => del.type === 'rooms' && del.id === room.id)).map((room, index) => (
              <li
                key={room.id}
                className={`element-item ${selectedElement?.type === 'room' && selectedElement?.id === room.id ? 'selected' : ''}`}
                onClick={() => setSelectedElement({ type: 'room', id: room.id, data: room })}
              >
                <div>
                  <div>{room.name || `Помещение ${index + 1}`}</div>
                  <small>{room.area_sqm ? `${room.area_sqm.toFixed(2)} м²` : 'Площадь не рассчитана'}</small>
                </div>
                <button
                  className="element-delete"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDeleteElement('rooms', room.id);
                  }}
                >
                  ×
                </button>
              </li>
            ))}
          </ul>
        </div>

        <div className="sidebar-section">
          <h3>Размеры ({dimensions.filter(dim => !deletedElements.some(del => del.type === 'dimensions' && del.id === dim.id)).length})</h3>
          <ul className="element-list">
            {dimensions.filter(dim => !deletedElements.some(del => del.type === 'dimensions' && del.id === dim.id)).map((dim, index) => (
              <li
                key={dim.id}
                className="element-item"
              >
                <span>{dim.text || `Размер ${index + 1}: ${dim.value} ${dim.unit}`}</span>
                <button
                  className="element-delete"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDeleteElement('dimensions', dim.id);
                  }}
                >
                  ×
                </button>
              </li>
            ))}
          </ul>
        </div>

        <div className="sidebar-section">
          <h3>Пожарная сигнализация ({fireAlarms.filter(alarm => !deletedElements.some(del => del.type === 'fire-alarms' && del.id === alarm.id)).length})</h3>
          <ul className="element-list">
            {fireAlarms.filter(alarm => !deletedElements.some(del => del.type === 'fire-alarms' && del.id === alarm.id)).map((alarm, index) => (
              <li
                key={alarm.id}
                className="element-item"
              >
                <span>{alarm.device_type} №{index + 1}</span>
                <button
                  className="element-delete"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDeleteElement('fire-alarms', alarm.id);
                  }}
                >
                  ×
                </button>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="editor-canvas">
        <div className="editor-toolbar">
          <button
            className={`tool-button ${selectedTool === 'select' ? 'active' : ''}`}
            onClick={() => setSelectedTool('select')}
          >
            Выбрать
          </button>
          <button
            className={`tool-button ${selectedTool === 'wall' ? 'active' : ''}`}
            onClick={() => setSelectedTool('wall')}
          >
            Нарисовать стену
          </button>
          <button
            className={`tool-button ${selectedTool === 'door' ? 'active' : ''}`}
            onClick={() => setSelectedTool('door')}
          >
            Добавить дверь
          </button>
          <button
            className={`tool-button ${selectedTool === 'window' ? 'active' : ''}`}
            onClick={() => setSelectedTool('window')}
          >
            Добавить окно
          </button>
          <button
            className={`tool-button ${selectedTool === 'dimension' ? 'active' : ''}`}
            onClick={() => setSelectedTool('dimension')}
          >
            Добавить размер
          </button>
          <button
            className={`tool-button ${selectedTool === 'fire-alarm' ? 'active' : ''}`}
            onClick={() => setSelectedTool('fire-alarm')}
          >
            Добавить датчик
          </button>
          <button
            className="btn btn-success"
            style={{ marginLeft: 'auto' }}
            onClick={handleSaveChanges}
          >
            Сохранить изменения {hasUnsavedChanges && '●'}
          </button>
        </div>

        <div className="editor-stage" id="editor-stage-container" style={{ overflow: 'auto' }}>
          <Stage
            width={stageWidth}
            height={stageHeight}
            ref={stageRef}
            onClick={handleStageClick}
            onMouseMove={(e) => {
              const stage = e.target.getStage();
              const point = stage.getPointerPosition();
              setMousePos({ x: point.x, y: point.y });
            }}
          >
            <Layer onClick={handleStageClick}>
              {/* Background Image */}
              {imageUrl && <BackgroundImage src={imageUrl} />}

              {/* Drawing Wall Preview */}
              {drawingWall && (() => {
                let x2 = mousePos.x;
                let y2 = mousePos.y;
                
                // Если зажат Shift, привязываем к углам кратным 45°
                if (shiftPressed) {
                  const snapped = snapTo45Degrees(drawingWall.x1, drawingWall.y1, x2, y2);
                  x2 = snapped.x;
                  y2 = snapped.y;
                }
                
                return (
                  <Line
                    points={[drawingWall.x1, drawingWall.y1, x2, y2]}
                    stroke="red"
                    strokeWidth={3}
                    dash={[10, 5]}
                  />
                );
              })()}

              {/* Render Walls */}
              {walls.filter(wall => !deletedElements.some(del => del.type === 'walls' && del.id === wall.id)).map((wall) => {
                const isSelected = selectedElement?.type === 'wall' && selectedElement?.id === wall.id;
                const isHovered = hoveredElement?.type === 'wall' && hoveredElement?.id === wall.id;
                
                // Применяем локальные изменения если есть
                const modifications = modifiedWalls[wall.id] || {};
                let x1 = modifications.x1 !== undefined ? modifications.x1 : wall.x1;
                let y1 = modifications.y1 !== undefined ? modifications.y1 : wall.y1;
                let x2 = modifications.x2 !== undefined ? modifications.x2 : wall.x2;
                let y2 = modifications.y2 !== undefined ? modifications.y2 : wall.y2;
                
                // Для отображения кругов во время перетаскивания всей стены
                let circleX1 = x1, circleY1 = y1, circleX2 = x2, circleY2 = y2;
                
                // Если стена редактируется точками, используем временные координаты
                if (editingWall?.id === wall.id && editingWall.point) {
                  if (editingWall.point === 'start') {
                    circleX1 = editingWall.x;
                    circleY1 = editingWall.y;
                    x1 = editingWall.x;
                    y1 = editingWall.y;
                  } else if (editingWall.point === 'end') {
                    circleX2 = editingWall.x;
                    circleY2 = editingWall.y;
                    x2 = editingWall.x;
                    y2 = editingWall.y;
                  }
                } else if (editingWall?.id === wall.id && editingWall.isDragging) {
                  // При перетаскивании всей стены смещаем круги
                  circleX1 += editingWall.dx;
                  circleY1 += editingWall.dy;
                  circleX2 += editingWall.dx;
                  circleY2 += editingWall.dy;
                }
                
                return (
                  <React.Fragment key={`wall-${wall.id}`}>
                    <Line
                      points={[x1, y1, x2, y2]}
                      stroke={isSelected ? 'blue' : (isHovered ? 'orange' : 'brown')}
                      strokeWidth={isSelected || isHovered ? 5 : 3}
                      draggable={isSelected && selectedTool === 'select'}
                      onDragMove={(e) => handleWallDrag(wall.id, e)}
                      onDragEnd={(e) => handleWallDragEnd(wall.id, wall, e)}
                      onClick={(e) => {
                        e.cancelBubble = true;
                        setSelectedElement({ type: 'wall', id: wall.id, data: wall });
                      }}
                      onMouseEnter={(e) => {
                        e.target.getStage().container().style.cursor = isSelected ? 'move' : 'pointer';
                        setHoveredElement({ type: 'wall', id: wall.id });
                      }}
                      onMouseLeave={(e) => {
                        e.target.getStage().container().style.cursor = 'default';
                        setHoveredElement(null);
                      }}
                    />
                    {isSelected && (
                      <>
                        {/* Точка начала стены */}
                        <Circle
                          x={circleX1}
                          y={circleY1}
                          radius={6}
                          fill="white"
                          stroke="blue"
                          strokeWidth={2}
                          draggable
                          dragBoundFunc={() => ({ x: circleX1, y: circleY1 })}
                          onDragMove={(e) => handleWallPointDrag(wall.id, 'start', e)}
                          onDragEnd={(e) => handleWallPointDragEnd(wall.id, 'start', e)}
                          onMouseEnter={(e) => {
                            e.target.getStage().container().style.cursor = 'move';
                          }}
                          onMouseLeave={(e) => {
                            e.target.getStage().container().style.cursor = 'default';
                          }}
                        />
                        {/* Точка конца стены */}
                        <Circle
                          x={circleX2}
                          y={circleY2}
                          radius={6}
                          fill="white"
                          stroke="blue"
                          strokeWidth={2}
                          draggable
                          dragBoundFunc={() => ({ x: circleX2, y: circleY2 })}
                          onDragMove={(e) => handleWallPointDrag(wall.id, 'end', e)}
                          onDragEnd={(e) => handleWallPointDragEnd(wall.id, 'end', e)}
                          onMouseEnter={(e) => {
                            e.target.getStage().container().style.cursor = 'move';
                          }}
                          onMouseLeave={(e) => {
                            e.target.getStage().container().style.cursor = 'default';
                          }}
                        />
                        <DeleteButton
                          x={circleX2 + 10}
                          y={circleY2 - 10}
                          onClick={(e) => {
                            e.cancelBubble = true;
                            handleDeleteElement('walls', wall.id);
                          }}
                        />
                      </>
                    )}
                  </React.Fragment>
                );
              })}

              {/* Render New Walls (not yet saved) */}
              {newWalls.map((wall) => {
                const isSelected = selectedElement?.type === 'new-wall' && selectedElement?.id === wall.id;
                const isHovered = hoveredElement?.type === 'new-wall' && hoveredElement?.id === wall.id;
                return (
                  <React.Fragment key={`new-wall-${wall.id}`}>
                    <Line
                      points={[wall.x1, wall.y1, wall.x2, wall.y2]}
                      stroke={isSelected ? 'blue' : (isHovered ? 'orange' : 'green')}
                      strokeWidth={isSelected || isHovered ? 5 : 3}
                      onClick={(e) => {
                        e.cancelBubble = true;
                        setSelectedElement({ type: 'new-wall', id: wall.id, data: wall });
                      }}
                      onMouseEnter={(e) => {
                        e.target.getStage().container().style.cursor = 'pointer';
                        setHoveredElement({ type: 'new-wall', id: wall.id });
                      }}
                      onMouseLeave={(e) => {
                        e.target.getStage().container().style.cursor = 'default';
                        setHoveredElement(null);
                      }}
                    />
                    {isSelected && (
                      <DeleteButton
                        x={wall.x2 + 10}
                        y={wall.y2 - 10}
                        onClick={(e) => {
                          e.cancelBubble = true;
                          setNewWalls(prev => prev.filter(w => w.id !== wall.id));
                          setSelectedElement(null);
                          if (newWalls.length === 1 && deletedElements.length === 0) {
                            setHasUnsavedChanges(false);
                          }
                        }}
                      />
                    )}
                  </React.Fragment>
                );
              })}

              {/* Render Doors */}
              {doors.filter(door => !deletedElements.some(del => del.type === 'doors' && del.id === door.id)).map((door) => {
                const isSelected = selectedElement?.type === 'door' && selectedElement?.id === door.id;
                const isHovered = hoveredElement?.type === 'door' && hoveredElement?.id === door.id;
                
                // Применяем сохраненные изменения позиции
                const x = modifiedElements[`doors-${door.id}`]?.x ?? door.x;
                const y = modifiedElements[`doors-${door.id}`]?.y ?? door.y;
                
                return (
                  <React.Fragment key={`door-${door.id}`}>
                    <Rect
                      x={x}
                      y={y}
                      width={door.width}
                      height={door.height}
                      fill={isSelected ? 'rgba(0, 100, 255, 0.7)' : (isHovered ? 'rgba(0, 255, 0, 0.6)' : 'rgba(0, 255, 0, 0.3)')}
                      stroke={isSelected ? 'blue' : (isHovered ? 'darkgreen' : 'green')}
                      strokeWidth={isSelected || isHovered ? 3 : 2}
                      draggable={selectedTool === 'select'}
                      onClick={(e) => {
                        e.cancelBubble = true;
                        setSelectedElement({ type: 'door', id: door.id, data: door });
                      }}
                      onDragEnd={(e) => handleElementDragEnd('doors', door.id, e)}
                      onMouseEnter={(e) => {
                        e.target.getStage().container().style.cursor = 'pointer';
                        setHoveredElement({ type: 'door', id: door.id });
                      }}
                      onMouseLeave={(e) => {
                        e.target.getStage().container().style.cursor = 'default';
                        setHoveredElement(null);
                      }}
                    />
                    {isSelected && (
                      <DeleteButton
                        x={x + door.width + 10}
                        y={y - 10}
                        onClick={(e) => {
                          e.cancelBubble = true;
                          handleDeleteElement('doors', door.id);
                        }}
                      />
                    )}
                  </React.Fragment>
                );
              })}

              {/* Render Windows */}
              {windows.filter(window => !deletedElements.some(del => del.type === 'windows' && del.id === window.id)).map((window) => {
                const isSelected = selectedElement?.type === 'window' && selectedElement?.id === window.id;
                const isHovered = hoveredElement?.type === 'window' && hoveredElement?.id === window.id;
                
                // Применяем сохраненные изменения позиции
                const x = modifiedElements[`windows-${window.id}`]?.x ?? window.x;
                const y = modifiedElements[`windows-${window.id}`]?.y ?? window.y;
                
                return (
                  <React.Fragment key={`window-${window.id}`}>
                    <Rect
                      x={x}
                      y={y}
                      width={window.width}
                      height={window.height}
                      fill={isSelected ? 'rgba(0, 100, 255, 0.7)' : (isHovered ? 'rgba(0, 0, 255, 0.6)' : 'rgba(0, 0, 255, 0.3)')}
                      stroke={isSelected ? 'blue' : (isHovered ? 'darkblue' : 'blue')}
                      strokeWidth={isSelected || isHovered ? 3 : 2}
                      draggable={selectedTool === 'select'}
                      onClick={(e) => {
                        e.cancelBubble = true;
                        setSelectedElement({ type: 'window', id: window.id, data: window });
                      }}
                      onDragEnd={(e) => handleElementDragEnd('windows', window.id, e)}
                      onMouseEnter={(e) => {
                        e.target.getStage().container().style.cursor = 'pointer';
                        setHoveredElement({ type: 'window', id: window.id });
                      }}
                      onMouseLeave={(e) => {
                        e.target.getStage().container().style.cursor = 'default';
                        setHoveredElement(null);
                      }}
                    />
                    {isSelected && (
                      <DeleteButton
                        x={x + window.width + 10}
                        y={y - 10}
                        onClick={(e) => {
                          e.cancelBubble = true;
                          handleDeleteElement('windows', window.id);
                        }}
                      />
                    )}
                  </React.Fragment>
                );
              })}

              {/* Render Rooms */}
              {rooms.filter(room => !deletedElements.some(del => del.type === 'rooms' && del.id === room.id)).map((room, index) => {
                if (!room.boundary_points || room.boundary_points.length < 3) return null;
                const points = room.boundary_points.flat();
                const isSelected = selectedElement?.type === 'room' && selectedElement?.id === room.id;
                const isHovered = hoveredElement?.type === 'room' && hoveredElement?.id === room.id;
                return (
                  <React.Fragment key={`room-${room.id}`}>
                    <Line
                      points={points}
                      stroke={isSelected ? 'blue' : (isHovered ? 'darkmagenta' : 'purple')}
                      strokeWidth={isSelected || isHovered ? 3 : 2}
                      closed
                      fill={isSelected ? 'rgba(0, 100, 255, 0.2)' : (isHovered ? 'rgba(128, 0, 128, 0.3)' : 'rgba(128, 0, 128, 0.1)')}
                      onClick={(e) => {
                        e.cancelBubble = true;
                        setSelectedElement({ type: 'room', id: room.id, data: room });
                      }}
                      onMouseEnter={(e) => {
                        e.target.getStage().container().style.cursor = 'pointer';
                        setHoveredElement({ type: 'room', id: room.id });
                      }}
                      onMouseLeave={(e) => {
                        e.target.getStage().container().style.cursor = 'default';
                        setHoveredElement(null);
                      }}
                    />
                    {room.center_x && room.center_y && (
                      <Text
                        x={room.center_x - 30}
                        y={room.center_y - 10}
                        text={room.name || `Помещение ${index + 1}`}
                        fontSize={14}
                        fill="purple"
                      />
                    )}
                    {isSelected && room.center_x && room.center_y && (
                      <DeleteButton
                        x={room.center_x + 50}
                        y={room.center_y - 20}
                        onClick={(e) => {
                          e.cancelBubble = true;
                          handleDeleteElement('rooms', room.id);
                        }}
                      />
                    )}
                  </React.Fragment>
                );
              })}

              {/* Render Dimensions */}
              {dimensions.filter(dim => !deletedElements.some(del => del.type === 'dimensions' && del.id === dim.id)).map((dim) => (
                <Text
                  key={`dim-${dim.id}`}
                  x={dim.x}
                  y={dim.y}
                  text={dim.text || `${dim.value} ${dim.unit}`}
                  fontSize={12}
                  fill="red"
                />
              ))}

              {/* Render Fire Alarms */}
              {fireAlarms.filter(alarm => !deletedElements.some(del => del.type === 'fire-alarms' && del.id === alarm.id)).map((alarm) => {
                const isSelected = selectedElement?.type === 'fire-alarm' && selectedElement?.id === alarm.id;
                const isHovered = hoveredElement?.type === 'fire-alarm' && hoveredElement?.id === alarm.id;
                
                // Применяем сохраненные изменения позиции
                const x = modifiedElements[`fire-alarms-${alarm.id}`]?.x ?? alarm.x;
                const y = modifiedElements[`fire-alarms-${alarm.id}`]?.y ?? alarm.y;
                
                return (
                  <React.Fragment key={`alarm-${alarm.id}`}>
                    <Circle
                      x={x}
                      y={y}
                      radius={isSelected || isHovered ? 12 : 10}
                      fill={isSelected ? 'blue' : (isHovered ? 'orange' : 'red')}
                      stroke={isSelected ? 'darkblue' : 'darkred'}
                      strokeWidth={isSelected ? 3 : 2}
                      draggable={selectedTool === 'select'}
                      onClick={(e) => {
                        e.cancelBubble = true;
                        setSelectedElement({ type: 'fire-alarm', id: alarm.id, data: alarm });
                      }}
                      onDragEnd={(e) => handleElementDragEnd('fire-alarms', alarm.id, e)}
                      onMouseEnter={(e) => {
                        e.target.getStage().container().style.cursor = 'pointer';
                        setHoveredElement({ type: 'fire-alarm', id: alarm.id });
                      }}
                      onMouseLeave={(e) => {
                        e.target.getStage().container().style.cursor = 'default';
                        setHoveredElement(null);
                      }}
                    />
                    {isSelected && (
                      <DeleteButton
                        x={x + 20}
                        y={y - 20}
                        onClick={(e) => {
                          e.cancelBubble = true;
                          handleDeleteElement('fire-alarms', alarm.id);
                        }}
                      />
                    )}
                  </React.Fragment>
                );
              })}
            </Layer>
          </Stage>
        </div>
      </div>
    </div>
  );
}

export default FloorPlanEditor;
