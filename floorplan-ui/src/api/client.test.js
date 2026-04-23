import {
  authApi,
  elementsApi,
  equipmentApi,
  floorPlansApi,
  pipelineApi,
  projectsApi,
  recognitionApi,
  recognitionTrainingApi,
  setUnauthorizedHandler,
  usersApi,
} from './client';

function createResponse({
  ok = true,
  status = 200,
  payload = { ok: true },
  contentType = 'application/json',
} = {}) {
  return {
    ok,
    status,
    headers: {
      get: () => contentType,
    },
    json: jest.fn().mockResolvedValue(payload),
    text: jest.fn().mockResolvedValue(typeof payload === 'string' ? payload : JSON.stringify(payload)),
  };
}

describe('client API helpers', () => {
  beforeEach(() => {
    global.fetch = jest.fn();
  });

  afterEach(() => {
    jest.resetAllMocks();
    setUnauthorizedHandler(null);
  });

  test('calls project, auth, user, equipment, floor plan, pipeline, recognition and element endpoints', async () => {
    global.fetch.mockImplementation(() => Promise.resolve(createResponse()));

    const formData = new FormData();
    formData.append('file', new Blob(['x']), 'plan.png');

    await projectsApi.list();
    await projectsApi.get(7);
    await projectsApi.create({ name: 'Project' });
    await projectsApi.update(7, { name: 'Updated' });
    await projectsApi.getGeneralData(7);
    await projectsApi.updateGeneralData(7, { page_title: 'Общие данные' });
    await projectsApi.getGeneralInstructions(7);
    await projectsApi.updateGeneralInstructions(7, { page_title: 'Общие указания' });
    await projectsApi.getPowerConsumptionCalculation(7);
    await projectsApi.updatePowerConsumptionCalculation(7, { page_title: 'Расчет' });
    await projectsApi.getEquipmentSpecification(7);
    await projectsApi.updateEquipmentSpecification(7, { page_title: 'Спецификация' });
    await projectsApi.getAdditionalInfo(7);
    await projectsApi.updateAdditionalInfo(7, { text: 'Доп. сведения' });
    await projectsApi.listEquipment(7);
    await projectsApi.attachEquipment(7, { equipment_id: 1 });
    await projectsApi.createAndAttachEquipment(7, { name: 'Smoke' });
    await projectsApi.removeEquipment(7, 3);
    await projectsApi.getEquipmentSelections(7);
    await projectsApi.updateEquipmentSelections(7, { selections: { common_instrument: 2 } });

    await authApi.login({ username: 'dev', password: 'secret' });
    await authApi.me();
    await authApi.logout();

    await usersApi.list();
    await usersApi.create({ username: 'eng', full_name: 'Engineer', role: 'engineer', password: 'secret' });
    await usersApi.update(5, { full_name: 'Updated Engineer' });
    await usersApi.resetPassword(5, { password: 'new-secret' });

    await equipmentApi.list();
    await equipmentApi.get(2);
    await equipmentApi.create({ name: 'Smoke' });
    await equipmentApi.update(2, { name: 'Heat' });
    await equipmentApi.remove(2);
    await equipmentApi.uploadImage(2, new File(['img'], 'device.png', { type: 'image/png' }));
    await equipmentApi.uploadLabelPdf(2, new File(['pdf'], 'label.pdf', { type: 'application/pdf' }));
    await equipmentApi.uploadManualPdf(2, new File(['pdf'], 'manual.pdf', { type: 'application/pdf' }));

    await floorPlansApi.get(11, false);
    await floorPlansApi.list(7);
    await floorPlansApi.create(formData);
    await floorPlansApi.update(11, { scale_factor: 10 });
    await floorPlansApi.remove(11);
    await floorPlansApi.batchSave(11, { create_walls: [] });
    await floorPlansApi.autoLayoutFireAlarms(11, 'addressable');
    await floorPlansApi.autoLayoutSoueDevices(11);

    await pipelineApi.getState(11);
    await pipelineApi.detectWalls(11);
    await pipelineApi.commitWalls(11, { walls: [] });
    await pipelineApi.detectOpenings(11);
    await pipelineApi.commitOpenings(11, { doors: [], windows: [] });
    await pipelineApi.submitStepFeedback(11, 'walls', { issue_tags: ['gap'] });
    await pipelineApi.getFeedbackStats();
    await pipelineApi.detectRooms(11);
    await pipelineApi.commitRooms(11, { rooms: [] });
    await pipelineApi.detectZkspc(11);
    await pipelineApi.commitZkspc(11, { zones: [] });

    await recognitionApi.process(11, true);
    await recognitionApi.get(11, true);
    await recognitionApi.submitFeedback(11);

    await recognitionTrainingApi.getOverview();
    await recognitionTrainingApi.listExamples({ step: 'walls', changed_only: true, search: 'door', empty: '' });
    await recognitionTrainingApi.getExample(5);
    await recognitionTrainingApi.updateExample(5, { notes: 'checked' });
    await recognitionTrainingApi.bulkCurate({ example_ids: [5], curation_status: 'approved' });
    await recognitionTrainingApi.listRuns();
    await recognitionTrainingApi.getRun('run-1');
    await recognitionTrainingApi.listActiveModels();
    await recognitionTrainingApi.getRunLog('run-1', 50);
    await recognitionTrainingApi.createRun({ step: 'walls' });
    await recognitionTrainingApi.activateRun('run-1');

    await elementsApi.createStair({ floor_plan_id: 11 });
    await elementsApi.createDoor({ floor_plan_id: 11 });
    await elementsApi.createWindow({ floor_plan_id: 11 });
    await elementsApi.createFireAlarm({ floor_plan_id: 11 });
    await elementsApi.createSoueDevice({ floor_plan_id: 11 });
    await elementsApi.createRoom({ floor_plan_id: 11 });
    await elementsApi.updateWall(1, { thickness: 300 });
    await elementsApi.updateStair(1, { step_count: 6 });
    await elementsApi.updateRoom(1, { name: '101' });
    await elementsApi.updateDoor(1, { width: 20 });
    await elementsApi.updateWindow(1, { width: 30 });
    await elementsApi.listZkspcZones(11);
    await elementsApi.createSignalInstrument({ floor_plan_id: 11 });
    await elementsApi.commitSignalInstrumentsStep(11, { system_type: 'non_addressable' });
    await elementsApi.listSignalInstruments(11, 'addressable');
    await elementsApi.updateSignalInstrument(1, { name: 'ARK' });
    await elementsApi.mergeRoutesForInstrument(1, { device_ids: [1], subsystem_type: 'sps', system_type: 'addressable' });
    await elementsApi.deleteSignalInstrument(1);
    await elementsApi.listCableRoutes(11, 'addressable');
    await elementsApi.listCableRoutesBySubsystem(11, 'addressable', 'soue');
    await elementsApi.recalculateCableRoutes(11, { system_type: 'addressable', subsystem_type: 'sps', use_shared_trunk: true });
    await elementsApi.commitCableRoutesStep(11, { system_type: 'addressable', subsystem_type: 'sps', use_shared_trunk: false });
    await elementsApi.updateCableRoute(1, { polyline_points: [[0, 0], [10, 10]] });

    expect(global.fetch).toHaveBeenCalled();
    expect(global.fetch.mock.calls.map((call) => call[0])).toEqual(
      expect.arrayContaining([
        '/api/projects',
        '/api/projects/7/general-data',
        '/api/projects/7/general-instructions',
        '/api/projects/7/power-consumption-calculation',
        '/api/projects/7/equipment-specification',
        '/api/auth/login',
        '/api/auth/me',
        '/api/auth/logout',
        '/api/users',
        '/api/users/5',
        '/api/users/5/reset-password',
        '/api/equipment',
        '/api/floor-plans/11?include_elements=false',
        '/api/floor-plans/11/pipeline/walls/detect',
        '/api/floor-plans/11/process?debug=true',
        '/api/recognition-training/examples?step=walls&changed_only=true&search=door',
        '/api/signal-instruments/1/merge-routes',
        '/api/floor-plans/11/cable-routes?system_type=addressable&subsystem_type=soue',
      ]),
    );

    global.fetch.mock.calls.forEach(([, options]) => {
      expect(options?.credentials).toBe('include');
    });
  });

  test('supports raw responses, 204, text payloads and error parsing', async () => {
    const rawResponse = createResponse({ payload: { file: true } });
    global.fetch
      .mockResolvedValueOnce(rawResponse)
      .mockResolvedValueOnce(createResponse({ status: 204, contentType: 'application/json' }))
      .mockResolvedValueOnce(createResponse({ payload: 'plain text', contentType: 'text/plain' }))
      .mockResolvedValueOnce(createResponse({ ok: false, status: 400, payload: { detail: 'Некорректные данные' } }))
      .mockResolvedValueOnce(createResponse({ ok: false, status: 409, payload: { code: 'project_conflict' } }))
      .mockResolvedValueOnce({
        ok: false,
        status: 500,
        headers: { get: () => 'text/plain' },
        json: jest.fn().mockRejectedValue(new Error('bad json')),
        text: jest.fn().mockResolvedValue('Server error'),
      });

    await expect(projectsApi.generatePdf(9)).resolves.toBe(rawResponse);
    await expect(projectsApi.remove(9)).resolves.toBeNull();
    await expect(projectsApi.list()).resolves.toBe('plain text');
    await expect(projectsApi.create({ name: 'Bad' })).rejects.toMatchObject({ message: 'Некорректные данные', status: 400 });
    await expect(projectsApi.update(9, { name: 'Conflict' })).rejects.toMatchObject({ message: 'project_conflict', status: 409 });
    await expect(projectsApi.get(9)).rejects.toMatchObject({ message: 'Request failed with status 500', status: 500 });
  });

  test('notifies the unauthorized handler on 401 responses', async () => {
    const handler = jest.fn();
    setUnauthorizedHandler(handler);
    global.fetch.mockResolvedValueOnce(createResponse({ ok: false, status: 401, payload: { code: 'auth_required' } }));

    await expect(projectsApi.list()).rejects.toMatchObject({ status: 401, message: 'auth_required' });
    expect(handler).toHaveBeenCalledTimes(1);
  });
});
