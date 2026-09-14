<script setup lang="ts">
import { computed, onScopeDispose, ref } from 'vue';
import { useRouter } from 'vue-router';
import { fetchGetDashboardHealth, fetchGetDashboardRecent, fetchGetDashboardStats } from '@/service/api';

defineOptions({ name: 'OpsDashboard' });

const router = useRouter();

/** ============ 概览统计 ============ */

const stats = ref<Api.Jobs.DashboardStats | null>(null);
const statsLoading = ref(false);

async function loadStats() {
  statsLoading.value = true;
  const { data, error } = await fetchGetDashboardStats();
  if (!error) stats.value = data;
  statsLoading.value = false;
}

const statCards = computed(() => [
  { label: '今日执行', value: stats.value?.todayExecutions ?? '-', icon: 'mdi:play-circle-outline', color: '#409eff' },
  {
    label: '成功率',
    value: stats.value ? `${stats.value.successRate}%` : '-',
    icon: 'mdi:check-circle-outline',
    color: '#67c23a'
  },
  { label: '平均耗时(s)', value: stats.value?.avgResponseSeconds ?? '-', icon: 'mdi:timer-outline', color: '#e6a23c' },
  {
    label: '本月拦截命令',
    value: stats.value?.blockedCommands ?? '-',
    icon: 'mdi:shield-alert-outline',
    color: '#f56c6c'
  }
]);

/** ============ 健康状态 ============ */

interface HealthView {
  redisOk: boolean | null;
  workersHealthy: boolean | null;
  workerCount: number | null;
  queuesHealthy: boolean | null;
  queueBackend: string;
  sevenDayTotal: number | null;
  sevenDaySuccessRate: number | null;
  checkedAt: string;
}

const health = ref<HealthView | null>(null);
const healthLoading = ref(false);

async function loadHealth() {
  healthLoading.value = true;
  const { data, error } = await fetchGetDashboardHealth();
  if (!error) {
    const raw = (data ?? {}) as Record<string, any>;
    health.value = {
      redisOk: typeof raw.redis === 'boolean' ? raw.redis : (raw.redis?.ok ?? null),
      workersHealthy: raw.workers?.healthy ?? null,
      workerCount: raw.workers?.count ?? null,
      queuesHealthy: raw.queues?.healthy ?? null,
      queueBackend: raw.queues?.backend ?? '-',
      sevenDayTotal: raw.sevenDay?.total ?? null,
      sevenDaySuccessRate: raw.sevenDay?.successRate ?? null,
      checkedAt: raw.checkedAt ?? '-'
    };
  }
  healthLoading.value = false;
}

function statusTagType(ok: boolean | null): 'info' | 'success' | 'danger' {
  if (ok === null) return 'info';
  return ok ? 'success' : 'danger';
}

function statusText(ok: boolean | null) {
  if (ok === null) return '未知';
  return ok ? '正常' : '异常';
}

/** ============ 最近运行 ============ */

const recentLoading = ref(false);
const recentRows = ref<Array<Record<string, unknown>>>([]);

const runStatusTagType: Record<string, string> = {
  pending: 'info',
  queued: 'info',
  running: 'primary',
  waiting: 'warning',
  cancel_requested: 'warning',
  success: 'success',
  failed: 'danger',
  timeout: 'danger',
  canceled: 'info'
};

async function loadRecent() {
  recentLoading.value = true;
  const { data, error } = await fetchGetDashboardRecent();
  if (!error) recentRows.value = data?.items ?? [];
  recentLoading.value = false;
}

function goDetail(row: Record<string, unknown>) {
  router.push({ path: `/task/run-detail/${row.id}`, query: { domain: 'ops' } });
}

function loadAll() {
  loadStats();
  loadHealth();
  loadRecent();
}

loadAll();

const timer = window.setInterval(loadStats, 60_000);

onScopeDispose(() => {
  window.clearInterval(timer);
});
</script>

<template>
  <div class="min-h-500px flex-col-stretch gap-16px overflow-hidden lt-sm:overflow-auto">
    <ElRow :gutter="16">
      <ElCol v-for="card in statCards" :key="card.label" :xl="6" :lg="12" :md="12" :sm="12" :xs="12">
        <ElCard v-loading="statsLoading" class="card-wrapper">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-14px text-gray-500">{{ card.label }}</p>
              <p class="mt-8px text-28px font-bold">{{ card.value }}</p>
            </div>
            <span class="text-44px" :style="{ color: card.color }">
              <component :is="card.icon" />
            </span>
          </div>
        </ElCard>
      </ElCol>
    </ElRow>

    <ElRow :gutter="16">
      <ElCol :span="24">
        <ElCard v-loading="healthLoading" class="card-wrapper">
          <template #header>
            <div class="flex items-center justify-between">
              <p>系统健康</p>
              <ElButton text type="primary" @click="loadHealth">刷新</ElButton>
            </div>
          </template>
          <ElDescriptions v-if="health" :column="4" border>
            <ElDescriptionsItem label="Redis">
              <ElTag :type="statusTagType(health.redisOk)">{{ statusText(health.redisOk) }}</ElTag>
            </ElDescriptionsItem>
            <ElDescriptionsItem label="Worker 进程">
              <ElTag :type="statusTagType(health.workersHealthy)">{{ statusText(health.workersHealthy) }}</ElTag>
              （{{ health.workerCount ?? '-' }} 个）
            </ElDescriptionsItem>
            <ElDescriptionsItem label="队列">
              <ElTag :type="statusTagType(health.queuesHealthy)">{{ statusText(health.queuesHealthy) }}</ElTag>
              （{{ health.queueBackend }}）
            </ElDescriptionsItem>
            <ElDescriptionsItem label="7 日执行">
              {{ health.sevenDayTotal ?? '-' }} 次 / 成功率 {{ health.sevenDaySuccessRate ?? '-' }}%
            </ElDescriptionsItem>
          </ElDescriptions>
          <p class="mt-8px text-right text-12px text-gray-400">检查时间：{{ health?.checkedAt ?? '-' }}</p>
        </ElCard>
      </ElCol>
    </ElRow>

    <ElCard class="card-wrapper sm:flex-1-hidden">
      <template #header>
        <div class="flex items-center justify-between">
          <p>最近执行</p>
          <ElButton text type="primary" @click="loadRecent">刷新</ElButton>
        </div>
      </template>
      <ElTable v-loading="recentLoading" :data="recentRows" border height="100%" row-key="id">
        <ElTableColumn prop="id" label="ID" width="80" />
        <ElTableColumn prop="name" label="作业名称" min-width="180" show-overflow-tooltip />
        <ElTableColumn prop="type" label="类型" width="120" />
        <ElTableColumn prop="target" label="目标" min-width="160" show-overflow-tooltip />
        <ElTableColumn label="状态" width="110" align="center">
          <template #default="{ row }">
            <ElTag :type="(runStatusTagType[row.status] ?? 'info') as any">{{ row.status }}</ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn prop="executor" label="执行人" width="120" />
        <ElTableColumn prop="time" label="时间" width="170" />
        <ElTableColumn label="操作" width="90" align="center" fixed="right">
          <template #default="{ row }">
            <ElButton type="primary" plain size="small" @click="goDetail(row)">详情</ElButton>
          </template>
        </ElTableColumn>
      </ElTable>
    </ElCard>
  </div>
</template>
