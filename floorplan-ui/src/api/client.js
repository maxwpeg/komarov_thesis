let unauthorizedHandler = null;

export function setUnauthorizedHandler(handler) {
  unauthorizedHandler = typeof handler === 'function' ? handler : null;
}

async function apiRequest(path, options = {}) {
  const response = await fetch(path, {
    credentials: 'include',
    ...options,
  });

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
    if (response.status === 401 && unauthorizedHandler) {
      unauthorizedHandler(error);
    }
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

export const authApi = {
  login(payload) {
    return apiRequest('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  },
  logout() {
    return apiRequest('/api/auth/logout', {
      method: 'POST',
    });
  },
  me() {
    return apiRequest('/api/auth/me');
  },
};

export const usersApi = {
  list() {
    return apiRequest('/api/users');
  },
  create(payload) {
    return apiRequest('/api/users', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  },
  update(userId, payload) {
    return apiRequest(`/api/users/${userId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  },
  resetPassword(userId, payload) {
    return apiRequest(`/api/users/${userId}/reset-password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  },
};

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
  getEquipmentSpecification(projectId) {
    return apiRequest(`/api/projects/${projectId}/equipment-specification`);
  },
  updateEquipmentSpecification(projectId, payload) {
    return apiRequest(`/api/projects/${projectId}/equipment-specification`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  },
  getGeneralData(projectId) {
    return apiRequest(`/api/projects/${projectId}/general-data`);
  },
  updateGeneralData(projectId, payload) {
    return apiRequest(`/api/projects/${projectId}/general-data`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  },
  getGeneralInstructions(projectId) {
    return apiRequest(`/api/projects/${projectId}/general-instructions`);
  },
  updateGeneralInstructions(projectId, payload) {
    return apiRequest(`/api/projects/${projectId}/general-instructions`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  },
  getPowerConsumptionCalculation(projectId) {
    return apiRequest(`/api/projects/${projectId}/power-consumption-calculation`);
  },
  updatePowerConsumptionCalculation(projectId, payload) {
    return apiRequest(`/api/projects/${projectId}/power-consumption-calculation`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  },
  getAdditionalInfo(projectId) {
    return apiRequest(`/api/projects/${projectId}/additional-info`);
  },
  updateAdditionalInfo(projectId, payload) {
    return apiRequest(`/api/projects/${projectId}/additional-info`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  },
  listEquipment(projectId) {
    return apiRequest(`/api/projects/${projectId}/equipment`);
  },
  attachEquipment(projectId, payload) {
    return apiRequest(`/api/projects/${projectId}/equipment`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  },
  createAndAttachEquipment(projectId, payload) {
    return apiRequest(`/api/projects/${projectId}/equipment/create`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  },
  removeEquipment(projectId, equipmentId) {
    return apiRequest(`/api/projects/${projectId}/equipment/${equipmentId}`, {
      method: 'DELETE',
    });
  },
  getEquipmentSelections(projectId) {
    return apiRequest(`/api/projects/${projectId}/equipment-selections`);
  },
  updateEquipmentSelections(projectId, payload) {
    return apiRequest(`/api/projects/${projectId}/equipment-selections`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  },
};

export const equipmentApi = {
  list() {
    return apiRequest('/api/equipment');
  },
  get(equipmentId) {
    return apiRequest(`/api/equipment/${equipmentId}`);
  },
  create(payload) {
    return apiRequest('/api/equipment', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  },
  update(equipmentId, payload) {
    return apiRequest(`/api/equipment/${equipmentId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  },
  remove(equipmentId) {
    return apiRequest(`/api/equipment/${equipmentId}`, {
      method: 'DELETE',
    });
  },
  uploadImage(equipmentId, file) {
    const formData = new FormData();
    formData.append('image', file);
    return apiRequest(`/api/equipment/${equipmentId}/image`, {
      method: 'POST',
      body: formData,
    });
  },
  uploadLabelPdf(equipmentId, file) {
    const formData = new FormData();
    formData.append('file', file);
    return apiRequest(`/api/equipment/${equipmentId}/label-pdf`, {
      method: 'POST',
      body: formData,
    });
  },
  uploadManualPdf(equipmentId, file) {
    const formData = new FormData();
    formData.append('file', file);
    return apiRequest(`/api/equipment/${equipmentId}/manual-pdf`, {
      method: 'POST',
      body: formData,
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
  autoLayoutSoueDevices(floorPlanId, systemType = 'non_addressable') {
    return apiRequest(`/api/floor-plans/${floorPlanId}/soue-devices/auto-layout?system_type=${systemType}`, {
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
  submitStepFeedback(floorPlanId, step, payload) {
    return apiRequest(`/api/floor-plans/${floorPlanId}/pipeline/${step}/feedback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  },
  getFeedbackStats() {
    return apiRequest('/api/recognition-feedback/stats');
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
  submitFeedback(floorPlanId) {
    return apiRequest(`/api/floor-plans/${floorPlanId}/recognition-feedback`, { method: 'POST' });
  },
};

export const recognitionTrainingApi = {
  getOverview() {
    return apiRequest('/api/recognition-training/overview');
  },
  listExamples(filters = {}) {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value === undefined || value === null || value === '' || value === false) {
        return;
      }
      params.set(key, String(value));
    });
    const suffix = params.toString() ? `?${params.toString()}` : '';
    return apiRequest(`/api/recognition-training/examples${suffix}`);
  },
  getExample(exampleId) {
    return apiRequest(`/api/recognition-training/examples/${exampleId}`);
  },
  updateExample(exampleId, payload) {
    return apiRequest(`/api/recognition-training/examples/${exampleId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  },
  bulkCurate(payload) {
    return apiRequest('/api/recognition-training/examples/bulk-curate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  },
  listRuns() {
    return apiRequest('/api/recognition-training/runs');
  },
  getRun(runId) {
    return apiRequest(`/api/recognition-training/runs/${runId}`);
  },
  listActiveModels() {
    return apiRequest('/api/recognition-training/active-models');
  },
  getRunLog(runId, tail = 200) {
    return apiRequest(`/api/recognition-training/runs/${runId}/log?tail=${tail}`);
  },
  createRun(payload) {
    return apiRequest('/api/recognition-training/runs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  },
  activateRun(runId) {
    return apiRequest(`/api/recognition-training/runs/${runId}/activate`, {
      method: 'POST',
    });
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
  createSoueDevice(payload) {
    return apiRequest('/api/soue-devices', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  },
  createRoom(payload) {
    return apiRequest('/api/rooms', {
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
  commitSignalInstrumentsStep(floorPlanId, payload) {
    return apiRequest(`/api/floor-plans/${floorPlanId}/signal-instruments/commit`, {
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
  mergeRoutesForInstrument(instrumentId, payload) {
    return apiRequest(`/api/signal-instruments/${instrumentId}/merge-routes`, {
      method: 'POST',
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
  listCableRoutesBySubsystem(floorPlanId, systemType, subsystemType = 'sps') {
    const params = new URLSearchParams();
    if (systemType) {
      params.set('system_type', systemType);
    }
    if (subsystemType) {
      params.set('subsystem_type', subsystemType);
    }
    const suffix = params.toString() ? `?${params.toString()}` : '';
    return apiRequest(`/api/floor-plans/${floorPlanId}/cable-routes${suffix}`);
  },
  recalculateCableRoutes(floorPlanId, payload) {
    return apiRequest(`/api/floor-plans/${floorPlanId}/cable-routes/recalculate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  },
  commitCableRoutesStep(floorPlanId, payload) {
    return apiRequest(`/api/floor-plans/${floorPlanId}/cable-routes/commit`, {
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
