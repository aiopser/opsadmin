<script setup lang="ts">
import { computed, ref } from 'vue';
import { fetchGetDashboardHealth } from '@/service/api';

defineOptions({ name: 'HomeHealthStatus' });

interface HealthView {
  environment?: Api.Jobs.DashboardHealth['environment'];
  redisOk: boolean | null;
  workersHealthy: boolean | null;
  workerCount: number | null;
  queuesHealthy: boolean | null;
  queueCount: number;
  queuedTasks: number;
  websocketHealthy: boolean | null;
  websocketBackend: string;
  sevenDayTotal: number | null;
  sevenDaySuccessRate: number | null;
  checkedAt: string;
}

const health = ref<HealthView | null>(null);
const loading = ref(false);
const emptyHealth: HealthView = {
  redisOk: null,
  workersHealthy: null,
  workerCount: null,
  queuesHealthy: null,
  queueCount: 0,
  queuedTasks: 0,
  websocketHealthy: null,
  websocketBackend: '-',
  sevenDayTotal: null,
  sevenDaySuccessRate: null,
  checkedAt: '-'
};
const healthSnapshot = computed(() => health.value ?? emptyHealth);

function normalizeQueueHealth(
  raw: Api.Jobs.DashboardHealth
): Pick<HealthView, 'queuesHealthy' | 'queueCount' | 'queuedTasks'> {
  const queues = raw.queues ?? {};
  return {
    queuesHealthy: Array.isArray(raw.workers?.missingQueues) ? raw.workers.missingQueues.length === 0 : null,
    queueCount: Object.keys(queues).length,
    queuedTasks: Object.values(queues).reduce((total, count) => total + count, 0)
  };
}

function normalizeHealth(raw: Api.Jobs.DashboardHealth): HealthView {
  const queueHealth = normalizeQueueHealth(raw);
  return {
    environment: raw.environment,
    redisOk: typeof raw.redis?.healthy === 'boolean' ? raw.redis.healthy : null,
    workersHealthy: typeof raw.workers?.healthy === 'boolean' ? raw.workers.healthy : null,
    workerCount: typeof raw.workers?.count === 'number' ? raw.workers.count : null,
    ...queueHealth,
    websocketHealthy: typeof raw.websocket?.healthy === 'boolean' ? raw.websocket.healthy : null,
    websocketBackend: raw.websocket?.backend || '-',
    sevenDayTotal: typeof raw.sevenDay?.total === 'number' ? raw.sevenDay.total : null,
    sevenDaySuccessRate: typeof raw.sevenDay?.successRate === 'number' ? raw.sevenDay.successRate : null,
    checkedAt: raw.checkedAt ?? '-'
  };
}

async function loadHealth() {
  loading.value = true;
  try {
    const { data, error } = await fetchGetDashboardHealth();
    if (error || !data) {
      if (error) window.$message?.error('加载作业与任务运行健康状态失败');
      return;
    }
    health.value = normalizeHealth(data);
  } finally {
    loading.value = false;
  }
}

function statusType(ok: boolean | null): UI.ThemeColor {
  if (ok === null) return 'info';
  return ok ? 'success' : 'danger';
}

function statusText(ok: boolean | null): string {
  if (ok === null) return '未知';
  return ok ? '正常' : '异常';
}

const healthCards = computed(() => [
  {
    label: 'Redis',
    description: '任务队列与实时事件依赖',
    icon: 'mdi:database-outline',
    status: healthSnapshot.value.redisOk,
    value: statusText(healthSnapshot.value.redisOk),
    detail: '缓存与消息代理'
  },
  {
    label: 'Worker 进程',
    description: 'Worker 节点可用性',
    icon: 'mdi:server-outline',
    status: healthSnapshot.value.workersHealthy,
    value: statusText(healthSnapshot.value.workersHealthy),
    detail: `${healthSnapshot.value.workerCount ?? '-'} 个执行进程`
  },
  {
    label: '执行队列',
    description: `${healthSnapshot.value.queueCount} 条队列 · ${healthSnapshot.value.queuedTasks} 个等待任务`,
    icon: 'mdi:format-list-bulleted',
    status: healthSnapshot.value.queuesHealthy,
    value: statusText(healthSnapshot.value.queuesHealthy),
    detail: 'Worker 队列订阅状态'
  },
  {
    label: '实时通道',
    description: healthSnapshot.value.websocketBackend,
    icon: 'mdi:access-point-network',
    status: healthSnapshot.value.websocketHealthy,
    value: statusText(healthSnapshot.value.websocketHealthy),
    detail: 'WebSocket 后端'
  },
  {
    label: '近 7 日执行',
    description: '作业与任务执行汇总',
    icon: 'mdi:chart-line',
    status: null,
    value: `${healthSnapshot.value.sevenDayTotal ?? '-'} 次`,
    detail: `成功率 ${healthSnapshot.value.sevenDaySuccessRate ?? '-'}%`
  }
]);

loadHealth();
</script>

<template>
  <ElCard v-loading="loading" class="card-wrapper">
    <template #header>
      <div class="flex flex-wrap items-center justify-between gap-8px">
        <div class="flex items-center gap-8px">
          <SvgIcon icon="mdi:chart-box-outline" class="text-20px text-primary" />
          <span>作业与任务运行健康</span>
        </div>
        <div class="flex items-center gap-8px">
          <span class="text-12px text-gray-500">检查时间：{{ healthSnapshot.checkedAt }}</span>
          <ElButton text type="primary" @click="loadHealth">刷新</ElButton>
        </div>
      </div>
    </template>
    <div class="grid grid-cols-1 gap-16px lg:grid-cols-3 sm:grid-cols-2 xl:grid-cols-5">
      <div v-for="item in healthCards" :key="item.label" class="flex">
        <div class="border-lighter h-full min-h-88px w-full flex items-center gap-12px border p-12px">
          <SvgIcon :icon="item.icon" class="shrink-0 text-30px text-primary" />
          <div class="min-w-0 flex-1">
            <div class="flex flex-wrap items-center gap-8px">
              <span class="text-13px font-600">{{ item.label }}</span>
              <ElTag v-if="item.status !== null" :type="statusType(item.status)" size="small">
                {{ item.value }}
              </ElTag>
              <strong v-else class="text-16px">{{ item.value }}</strong>
            </div>
            <p class="mt-4px truncate text-12px text-gray-500">{{ item.detail }}</p>
            <p class="mt-2px truncate text-12px text-gray-500">{{ item.description }}</p>
          </div>
        </div>
      </div>
    </div>
    <ElDescriptions v-if="healthSnapshot.environment" :column="2" border class="mt-12px">
      <ElDescriptionsItem label="云资产 SDK">
        <div class="flex flex-wrap gap-8px">
          <ElTag
            v-for="sdk in healthSnapshot.environment.sdks"
            :key="sdk.name"
            :type="sdk.available ? 'success' : 'warning'"
            size="small"
          >
            {{ sdk.name.startsWith('alibabacloud') ? '阿里云' : '腾讯云' }}：{{
              sdk.available ? sdk.version || '已安装' : '未安装'
            }}
          </ElTag>
        </div>
      </ElDescriptionsItem>
      <ElDescriptionsItem label="凭据加密">
        <ElTag :type="healthSnapshot.environment.credentialsEncryptionValid ? 'success' : 'warning'" size="small">
          {{
            healthSnapshot.environment.credentialsEncryptionValid
              ? '配置有效'
              : healthSnapshot.environment.credentialsEncryptionConfigured
                ? '密钥格式无效'
                : '未配置'
          }}
        </ElTag>
      </ElDescriptionsItem>
      <ElDescriptionsItem label="API 版本">
        {{ healthSnapshot.environment.apiVersion === 'unknown' ? '未标记' : healthSnapshot.environment.apiVersion }}
      </ElDescriptionsItem>
      <ElDescriptionsItem label="Worker 版本">
        <ElTag
          :type="healthSnapshot.environment.workersVersionStatus === 'matched' ? 'success' : 'warning'"
          size="small"
        >
          {{
            healthSnapshot.environment.workersVersionStatus === 'matched'
              ? '与 API 一致'
              : healthSnapshot.environment.workersVersionStatus === 'mismatch'
                ? '与 API 不一致，请核对部署'
                : '尚未上报或未标记版本'
          }}
        </ElTag>
      </ElDescriptionsItem>
    </ElDescriptions>
  </ElCard>
</template>
