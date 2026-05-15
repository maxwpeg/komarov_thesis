import { backgroundTasksApi } from '../api/client';

export const TERMINAL_TASK_STATUSES = new Set(['succeeded', 'failed', 'canceled']);

export async function pollTaskUntilSettled(taskId, options = {}) {
  const intervalMs = options.intervalMs ?? 1500;
  const onUpdate = typeof options.onUpdate === 'function' ? options.onUpdate : null;

  while (true) {
    const task = await backgroundTasksApi.get(taskId);
    if (onUpdate) {
      onUpdate(task);
    }
    if (TERMINAL_TASK_STATUSES.has(task.status)) {
      return task;
    }
    // eslint-disable-next-line no-await-in-loop
    await new Promise((resolve) => window.setTimeout(resolve, intervalMs));
  }
}
