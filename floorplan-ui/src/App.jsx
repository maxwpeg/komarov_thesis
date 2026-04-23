import React, { useEffect, useMemo, useState } from 'react';
import {
  BrowserRouter as Router,
  Link,
  Navigate,
  Route,
  Routes,
  matchPath,
  useLocation,
} from 'react-router-dom';

import './App.css';
import { floorPlansApi } from './api/client';
import { AuthProvider, useAuth } from './auth/AuthContext';
import CreateProject from './pages/CreateProject';
import EquipmentCatalogPage from './pages/EquipmentCatalogPage';
import FloorPlanEditor from './pages/FloorPlanEditor';
import LoginPage from './pages/LoginPage';
import ProjectDetail from './pages/ProjectDetail';
import ProjectList from './pages/ProjectList';
import RecognitionTrainingPage from './pages/RecognitionTrainingPage';
import UsersPage from './pages/UsersPage';

function AuthLoadingGate() {
  return (
    <div className="auth-loading">
      <div className="auth-loading__panel">
        <div className="auth-loading__pulse" />
        <div>Проверяем сессию...</div>
      </div>
    </div>
  );
}

function WelcomeOverlay() {
  const { welcomeState, dismissWelcome } = useAuth();

  useEffect(() => {
    if (!welcomeState.visible) {
      return undefined;
    }
    const timer = window.setTimeout(() => {
      dismissWelcome();
    }, 1100);
    return () => window.clearTimeout(timer);
  }, [dismissWelcome, welcomeState.visible]);

  if (!welcomeState.visible) {
    return null;
  }

  return (
    <div className="welcome-overlay" aria-live="polite">
      <div className="welcome-overlay__card">
        <div className="welcome-overlay__label">Сессия открыта</div>
        <div className="welcome-overlay__title">Добро пожаловать, {welcomeState.fullName}</div>
      </div>
    </div>
  );
}

function ProtectedAppShell() {
  const location = useLocation();
  const { user, logout } = useAuth();
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
        if (error?.status !== 401) {
          console.error('Error resolving floor plan project for navbar:', error);
        }
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

  const navItems = user?.role === 'developer'
    ? [
      { to: '/', label: 'Проекты' },
      { to: '/create-project', label: 'Новый проект' },
      { to: '/equipment', label: 'Оборудование' },
      { to: '/recognition-training', label: 'Дообучение' },
      { to: '/users', label: 'Пользователи' },
    ]
    : [
      { to: '/', label: 'Проекты' },
      { to: '/create-project', label: 'Новый проект' },
      { to: '/equipment', label: 'Оборудование' },
    ];

  return (
    <>
      <WelcomeOverlay />

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
          {navItems.map((item) => (
            <Link key={item.to} to={item.to} className="nav-link">
              {item.label}
            </Link>
          ))}
        </div>

        <div className="navbar-user">
          <div className="navbar-user__meta">
            <strong>{user?.full_name}</strong>
            <span>{user?.role === 'developer' ? 'Разработчик' : 'Инженер'}</span>
          </div>
          <button type="button" className="btn btn-secondary navbar-user__logout" onClick={logout}>
            Выйти
          </button>
        </div>
      </nav>

      <main className="main-content">
        <Routes>
          <Route path="/" element={<ProjectList />} />
          <Route path="/create-project" element={<CreateProject />} />
          <Route path="/equipment" element={<EquipmentCatalogPage />} />
          <Route path="/projects/:projectId" element={<ProjectDetail />} />
          <Route path="/floor-plans/:floorPlanId" element={<FloorPlanEditor />} />
          <Route
            path="/recognition-training"
            element={user?.role === 'developer' ? <RecognitionTrainingPage /> : <Navigate to="/" replace />}
          />
          <Route
            path="/users"
            element={user?.role === 'developer' ? <UsersPage /> : <Navigate to="/" replace />}
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </>
  );
}

function AppRoutes() {
  const location = useLocation();
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return <AuthLoadingGate />;
  }

  return (
    <Routes>
      <Route
        path="/login"
        element={isAuthenticated ? <Navigate to="/" replace /> : <LoginPage />}
      />
      <Route
        path="*"
        element={
          isAuthenticated
            ? <ProtectedAppShell />
            : <Navigate to="/login" replace state={{ from: location }} />
        }
      />
    </Routes>
  );
}

function App() {
  return (
    <Router>
      <AuthProvider>
        <div className="app">
          <AppRoutes />
        </div>
      </AuthProvider>
    </Router>
  );
}

export default App;
