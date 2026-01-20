import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import ProjectList from './pages/ProjectList';
import ProjectDetail from './pages/ProjectDetail';
import FloorPlanEditor from './pages/FloorPlanEditor';
import CreateProject from './pages/CreateProject';
import './App.css';

function App() {
  return (
    <Router>
      <div className="app">
        <nav className="navbar">
          <div className="navbar-brand">
            <Link to="/" className="logo">Менеджер планов этажей</Link>
          </div>
          <div className="navbar-links">
            <Link to="/" className="nav-link">Проекты</Link>
            <Link to="/create-project" className="nav-link">Новый проект</Link>
          </div>
        </nav>

        <main className="main-content">
          <Routes>
            <Route path="/" element={<ProjectList />} />
            <Route path="/create-project" element={<CreateProject />} />
            <Route path="/projects/:projectId" element={<ProjectDetail />} />
            <Route path="/floor-plans/:floorPlanId" element={<FloorPlanEditor />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;



