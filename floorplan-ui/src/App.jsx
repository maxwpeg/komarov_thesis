import React, { useEffect, useMemo, useState } from 'react';
import {
  BrowserRouter as Router,
  Link,
  Route,
  Routes,
  matchPath,
  useLocation,
} from 'react-router-dom';

import './App.css';
import { floorPlansApi } from './api/client';
import CreateProject from './pages/CreateProject';
import EquipmentCatalogPage from './pages/EquipmentCatalogPage';
import FloorPlanEditor from './pages/FloorPlanEditor';
import ProjectDetail from './pages/ProjectDetail';
import ProjectList from './pages/ProjectList';
import RecognitionTrainingPage from './pages/RecognitionTrainingPage';

function AppShell() {
  const location = useLocation();
  const [floorPlanProjectId, setFloorPlanProjectId] = useState(null);

  const projectMatch = matchPath('/projects/:projectId', location.pathname);
  const floorPlanMatch = matchPath('/floor-plans/:floorPlanId', location.pathname);
  const floorPlanId = floorPlanMatch?.params?.floorPlanId || null;

  useEffect(() => {
    let isActive = true;

    if (!floorPlanId) {
      setFloorPlanProjectId(null);
      return () => {
        isActive = false;
      };
    }

    setFloorPlanProjectId(null);
    floorPlansApi.get(floorPlanId, false)
      .then((data) => {
        if (isActive) {
          setFloorPlanProjectId(data?.project_id ?? null);
        }
      })
      .catch((error) => {
        console.error('Error resolving floor plan project for navbar:', error);
        if (isActive) {
          setFloorPlanProjectId(null);
        }
      });

    return () => {
      isActive = false;
    };
  }, [floorPlanId]);

  const contextualBackLink = useMemo(() => {
    if (projectMatch?.params?.projectId) {
      return {
        to: '/',
        label: 'Назад к проектам',
      };
    }

    if (floorPlanId) {
      return {
        to: floorPlanProjectId ? `/projects/${floorPlanProjectId}` : '/',
        label: 'Назад к проекту',
      };
    }

    return null;
  }, [floorPlanId, floorPlanProjectId, projectMatch?.params?.projectId]);

  return (
    <>
      <nav className="navbar">
        <div className="navbar-brand">
          <Link to="/" className="logo">Кульман</Link>
          {contextualBackLink && (
            <Link to={contextualBackLink.to} className="nav-link navbar-context-link">
              ← {contextualBackLink.label}
            </Link>
          )}
        </div>
        <div className="navbar-links">
          <Link to="/" className="nav-link">Проекты</Link>
          <Link to="/create-project" className="nav-link">Новый проект</Link>
          <Link to="/equipment" className="nav-link">Оборудование</Link>
          <Link to="/recognition-training" className="nav-link">Дообучение</Link>
        </div>
      </nav>

      <main className="main-content">
        <Routes>
          <Route path="/" element={<ProjectList />} />
          <Route path="/create-project" element={<CreateProject />} />
          <Route path="/equipment" element={<EquipmentCatalogPage />} />
          <Route path="/projects/:projectId" element={<ProjectDetail />} />
          <Route path="/floor-plans/:floorPlanId" element={<FloorPlanEditor />} />
          <Route path="/recognition-training" element={<RecognitionTrainingPage />} />
        </Routes>
      </main>
    </>
  );
}

function App() {
  return (
    <Router>
      <div className="app">
        <AppShell />
      </div>
    </Router>
  );
}

export default App;
