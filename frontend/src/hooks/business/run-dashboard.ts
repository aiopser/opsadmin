import { onScopeDispose, ref, shallowRef } from 'vue';
import { fetchGetDashboardRecent, fetchGetDashboardStats } from '@/service/api';

export function useRunDashboard(domain: Api.Jobs.RunDomain) {
  const stats = shallowRef<Api.Jobs.DashboardStats | null>(null);
  const statsLoading = ref(false);
  const statsError = ref(false);
  const recentRows = shallowRef<Api.Jobs.DashboardRecentItem[]>([]);
  const recentLoading = ref(false);
  const recentError = ref(false);

  let disposed = false;
  let pollTimer: number | undefined;
  let statsRequest: AbortController | undefined;
  let recentRequest: AbortController | undefined;

  async function loadStats() {
    statsRequest?.abort();
    const controller = new AbortController();
    statsRequest = controller;
    statsLoading.value = true;
    try {
      const { data, error } = await fetchGetDashboardStats(domain, controller.signal);
      if (disposed || statsRequest !== controller) return;
      statsError.value = Boolean(error || !data);
      if (!error && data) stats.value = data;
    } catch {
      if (!disposed && statsRequest === controller && !controller.signal.aborted) {
        statsError.value = true;
      }
    } finally {
      if (!disposed && statsRequest === controller) statsLoading.value = false;
    }
  }

  async function loadRecent() {
    recentRequest?.abort();
    const controller = new AbortController();
    recentRequest = controller;
    recentLoading.value = true;
    try {
      const { data, error } = await fetchGetDashboardRecent(domain, controller.signal);
      if (disposed || recentRequest !== controller) return;
      recentError.value = Boolean(error || !Array.isArray(data));
      if (!error && Array.isArray(data)) recentRows.value = data;
    } catch {
      if (!disposed && recentRequest === controller && !controller.signal.aborted) {
        recentError.value = true;
      }
    } finally {
      if (!disposed && recentRequest === controller) recentLoading.value = false;
    }
  }

  async function pollLoop() {
    await Promise.allSettled([loadStats(), loadRecent()]);
    if (!disposed) pollTimer = window.setTimeout(pollLoop, 30_000);
  }

  pollLoop();

  onScopeDispose(() => {
    disposed = true;
    if (pollTimer) window.clearTimeout(pollTimer);
    statsRequest?.abort();
    recentRequest?.abort();
  });

  return { stats, statsLoading, statsError, recentRows, recentLoading, recentError, loadStats, loadRecent };
}
