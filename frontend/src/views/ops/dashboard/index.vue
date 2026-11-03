<script setup lang="ts">
import { computed } from 'vue';
import { useRouter } from 'vue-router';
import {
  dashboardRecentTypeText,
  dashboardSuccessRateText,
  runStatusRecord,
  runStatusTagType
} from '@/constants/business';
import { useRunDashboard } from '@/hooks/business/run-dashboard';
import { formatLocalDateTime } from '@/utils/common';
import { $t } from '@/locales';

defineOptions({ name: 'OpsDashboard' });

const router = useRouter();

const { stats, statsLoading, statsError, recentRows, recentLoading, recentError, loadStats, loadRecent } =
  useRunDashboard('ops');

const statCards = computed(() => [
  {
    label: '今日执行',
    value: stats.value?.todayExecutions ?? '-',
    icon: 'mdi:play-circle-outline',
    color: 'var(--el-color-primary)'
  },
  {
    label: '今日成功率',
    value: dashboardSuccessRateText(stats.value?.successRate),
    icon: 'mdi:check-circle-outline',
    color: 'var(--el-color-success)'
  },
  {
    label: '平均耗时（秒）',
    value: stats.value?.avgResponseSeconds ?? '-',
    icon: 'mdi:timer-outline',
    color: 'var(--el-color-warning)'
  },
  {
    label: '本月拦截命令',
    value: stats.value?.blockedCommands ?? '-',
    icon: 'mdi:shield-alert-outline',
    color: 'var(--el-color-danger)'
  }
]);

function goDetail(row: Api.Jobs.DashboardRecentItem) {
  router.push({ name: 'ops_run-detail', params: { id: row.id } });
}

function runStatusTypeOf(status: Api.Jobs.RunStatus): UI.ThemeColor {
  return runStatusTagType[status] ?? 'info';
}

function runStatusText(status: Api.Jobs.RunStatus): string {
  const key = runStatusRecord[status];
  return key ? $t(key) : String(status ?? '-');
}
</script>

<template>
  <div class="min-h-500px flex-col-stretch gap-16px overflow-hidden lt-sm:overflow-auto">
    <ElAlert v-if="statsError" type="warning" :closable="false" show-icon>
      <template #title>
        <span>{{ stats ? '概览统计更新失败，当前显示上次数据' : '概览统计加载失败' }}</span>
        <ElButton class="ml-8px" text type="primary" :loading="statsLoading" @click="loadStats">重新加载</ElButton>
      </template>
    </ElAlert>
    <ElRow :gutter="16" class="gap-y-16px">
      <ElCol v-for="card in statCards" :key="card.label" :xl="6" :lg="12" :md="12" :sm="12" :xs="24">
        <ElCard class="min-h-110px card-wrapper">
          <ElSkeleton v-if="statsLoading && !stats" :rows="2" animated />
          <div v-else class="flex items-center justify-between gap-12px">
            <div class="min-w-0">
              <p class="text-14px text-gray-500">{{ card.label }}</p>
              <p class="mt-8px text-26px font-bold tabular-nums sm:text-28px">{{ card.value }}</p>
            </div>
            <span class="shrink-0 text-44px" :style="{ color: card.color }">
              <SvgIcon :icon="card.icon" />
            </span>
          </div>
        </ElCard>
      </ElCol>
    </ElRow>

    <ElCard class="card-wrapper sm:flex-1-hidden">
      <template #header>
        <div class="flex flex-wrap items-center justify-between gap-8px">
          <p>最近作业</p>
          <div class="flex flex-wrap items-center gap-8px">
            <span v-if="recentError && recentRows.length" class="text-12px text-[var(--el-color-warning)]">
              更新失败，显示上次数据
            </span>
            <ElButton text type="primary" :loading="recentLoading" @click="loadRecent">刷新</ElButton>
          </div>
        </div>
      </template>
      <div class="h-[calc(100%-52px)] overflow-x-auto">
        <ElSkeleton v-if="recentLoading && !recentRows.length" :rows="4" animated />
        <ElEmpty
          v-else-if="!recentRows.length"
          :description="recentError ? '加载最近作业失败' : '暂无作业运行记录'"
          :image-size="80"
        >
          <ElButton @click="loadRecent">{{ recentError ? '重新加载' : '刷新' }}</ElButton>
        </ElEmpty>
        <ElTable
          v-else
          v-loading="recentLoading"
          :data="recentRows"
          border
          height="100%"
          row-key="id"
          class="min-w-900px"
        >
          <ElTableColumn prop="id" label="ID" width="80" align="center" class-name="tabular-nums" />
          <ElTableColumn prop="name" label="作业名称" min-width="180" show-overflow-tooltip />
          <ElTableColumn label="执行类型" width="120">
            <template #default="{ row }">{{ dashboardRecentTypeText(row.type) }}</template>
          </ElTableColumn>
          <ElTableColumn prop="target" label="目标" min-width="160" show-overflow-tooltip />
          <ElTableColumn label="状态" width="110" align="center">
            <template #default="{ row }">
              <ElTag :type="runStatusTypeOf(row.status)">{{ runStatusText(row.status) }}</ElTag>
            </template>
          </ElTableColumn>
          <ElTableColumn prop="executor" label="执行人" width="120" />
          <ElTableColumn label="发起时间" width="175">
            <template #default="{ row }">
              <span class="tabular-nums">{{ formatLocalDateTime(row.time) }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn label="操作" width="90" align="center" fixed="right">
            <template #default="{ row }">
              <ElButton type="primary" plain size="small" @click="goDetail(row)">详情</ElButton>
            </template>
          </ElTableColumn>
        </ElTable>
      </div>
    </ElCard>
  </div>
</template>
