async function apiRequest(path, options = {}) {
  const response = await fetch(path, options);

  if (!response.ok) {
    let detail = `Request failed with status ${response.status}`;
    let payload = null;
    try {
      payload = await response.json();
      if (typeof payload?.detail === 'string') {
        detail = payload.detail;
      } else if (typeof payload?.code === 'string') {
        detail = payload.code;
      }
    } catch (_error) {
      // Ignore JSON parse failures and keep the HTTP status message.
    }
    const error = new Error(detail);
    error.status = response.status;
    error.payload = payload;
    throw error;
  }

  if (options.rawResponse) {
    return response;
  }

  if (response.status === 204) {
    return null;
  }

  const contentType = response.headers.get('Content-Type') || '';
  if (contentType.includes('application/json')) {
    return response.json();
  }

  return response.text();
}

export const projectsApi = {
  list() {
    return apiRequest('/api/projects');
  },
  get(projectId) {
    return apiRequest(`/api/projects/${projectId}`);
  },
  create(payload) {
    return apiRequest('/api/projects', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  },
  update(projectId, payload) {
    return apiRequest(`/api/projects/${projectId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  },
  remove(projectId) {
    return apiRequest(`/api/projects/${projectId}`, { method: 'DELETE' });
  },
  generatePdf(projectId) {
    return apiRequest(`/api/projects/${projectId}/generate-pdf`, {
      method: 'POST',
      rawResponse: true,
    });
  },
};

export const floorPlansApi = {
  get(floorPlanId, includeElements = true) {
    return apiRequest(`/api/floor-plans/${floorPlanId}?include_elements=${includeElements}`);
  },
  list(projectId) {
    return apiRequest(`/api/projects/${projectId}/floor-plans`);
  },
  create(formData) {
    return apiRequest('/api/floor-plans', {
      method: 'POST',
      body: formData,
    });
  },
  update(floorPlanId, payload) {
    return apiRequest(`/api/floor-plans/${floorPlanId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  },
  remove(floorPlanId) {
    return apiRequest(`/api/floor-plans/${floorPlanId}`, { method: 'DELETE' });
  },
  batchSave(floorPlanId, payload) {
    return apiRequest(`/api/floor-plans/${floorPlanId}/batch-save`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  },
  autoLayoutFireAlarms(floorPlanId, systemType = 'non_addressable') {
    return apiRequest(`/api/floor-plans/${floorPlanId}/fire-alarms/auto-layout?system_type=${systemType}`, {
      method: 'POST',
    });
  },
};

export const pipelineApi = {
  getState(floorPlanId) {
    return apiRequest(`/api/floor-plans/${floorPlanId}/pipeline-state`);
  },
  detectWalls(floorPlanId) {
    return apiRequest(`/api/floor-plans/${floorPlanId}/pipeline/walls/detect`, {
      method: 'POST',
    });
  },
  commitWalls(floorPlanId, payload) {
    return apiRequest(`/api/floor-plans/${floorPlanId}/pipeline/walls/commit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  },
  detectOpenings(floorPlanId) {
    return apiRequest(`/api/floor-plans/${floorPlanId}/pipeline/openings/detect`, {
      method: 'POST',
    });
  },
  commitOpenings(floorPlanId, payload) {
    return apiRequest(`/api/floor-plans/${floorPlanId}/pipeline/openings/commit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  },
  detectRooms(floorPlanId) {
    return apiRequest(`/api/floor-plans/${floorPlanId}/pipeline/rooms/detect`, {
      method: 'POST',
    });
  },
  commitRooms(floorPlanId, payload) {
    return apiRequest(`/api/floor-plans/${floorPlanId}/pipeline/rooms/commit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  },
  detectZkspc(floorPlanId) {
    return apiRequest(`/api/floor-plans/${floorPlanId}/pipeline/zkspc/detect`, {
      method: 'POST',
    });
  },
  commitZkspc(floorPlanId, payload) {
    return apiRequest(`/api/floor-plans/${floorPlanId}/pipeline/zkspc/commit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  },
};

export const recognitionApi = {
  process(floorPlanId, debug = false) {
    const suffix = debug ? '?debug=true' : '';
    return apiRequest(`/api/floor-plans/${floorPlanId}/process${suffix}`, { method: 'POST' });
  },
  get(floorPlanId, debug = false) {
    const suffix = debug ? '?debug=true' : '';
    return apiRequest(`/api/floor-plans/${floorPlanId}/recognition${suffix}`);
  },
};

export const elementsApi = {
  createStair(payload) {
    return apiRequest('/api/stairs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  },
  createDoor(payload) {
    return apiRequest('/api/doors', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  },
  createWindow(payload) {
    return apiRequest('/api/windows', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  },
  createFireAlarm(payload) {
    return apiRequest('/api/fire-alarms', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  },
  updateWall(wallId, payload) {
    return apiRequest(`/api/walls/${wallId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  },
  updateStair(stairId, payload) {
    return apiRequest(`/api/stairs/${stairId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  },
  updateRoom(roomId, payload) {
    return apiRequest(`/api/rooms/${roomId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  },
  updateDoor(doorId, payload) {
    return apiRequest(`/api/doors/${doorId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  },
  updateWindow(windowId, payload) {
    return apiRequest(`/api/windows/${windowId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  },
  listZkspcZones(floorPlanId) {
    return apiRequest(`/api/floor-plans/${floorPlanId}/zkspc-zones`);
  },
  createSignalInstrument(payload) {
    return apiRequest('/api/signal-instruments', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  },
  listSignalInstruments(floorPlanId, systemType) {
    const suffix = systemType ? `?system_type=${systemType}` : '';
    return apiRequest(`/api/floor-plans/${floorPlanId}/signal-instruments${suffix}`);
  },
  updateSignalInstrument(instrumentId, payload) {
    return apiRequest(`/api/signal-instruments/${instrumentId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  },
  deleteSignalInstrument(instrumentId) {
    return apiRequest(`/api/signal-instruments/${instrumentId}`, {
      method: 'DELETE',
    });
  },
  listCableRoutes(floorPlanId, systemType) {
    const suffix = systemType ? `?system_type=${systemType}` : '';
    return apiRequest(`/api/floor-plans/${floorPlanId}/cable-routes${suffix}`);
  },
  recalculateCableRoutes(floorPlanId, payload) {
    return apiRequest(`/api/floor-plans/${floorPlanId}/cable-routes/recalculate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  },
  updateCableRoute(routeId, payload) {
    return apiRequest(`/api/cable-routes/${routeId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  },
};
