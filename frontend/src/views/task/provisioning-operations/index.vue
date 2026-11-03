<script setup lang="ts">
import { onMounted, ref, shallowRef } from 'vue';
import { fetchProvisioningHealth } from '@/service/api/provisioning';
import type { ProvisioningHealth } from '@/service/api/provisioning';
import { formatLocalDateTime } from '@/utils/common';

defineOptions({ name: 'ProvisioningOperations' });
const loading = ref(false);
const health = shallowRef<ProvisioningHealth>();

async function load() {
  if (loading.value) return;
  loading.value = true;
  try {
    const { data, error } = await fetchProvisioningHealth();
    if (!error && data) health.value = data;
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div class="flex-col gap-16px">
    <ElCard shadow="never">
      <div class="flex flex-wrap items-center justify-between gap-12px">
        <span>交付运行状况</span>
        <div class="flex items-center gap-12px">
          <span v-if="health" class="text-color-secondary">更新于 {{ formatLocalDateTime(health.observedAt) }}</span>
          <ElButton :loading="loading" @click="load">刷新</ElButton>
        </div>
      </div>
    </ElCard>
    <ElSkeleton v-if="!health" :loading="loading" animated :rows="8" />
    <template v-else>
      <ElCard shadow="never">
        <ElDescriptions :column="3" border>
          <ElDescriptionsItem label="等待执行">{{ health.queued }} 项</ElDescriptionsItem>
          <ElDescriptionsItem label="结果待核实">{{ health.uncertain }} 项</ElDescriptionsItem>
          <ElDescriptionsItem label="状态存储">
            <ElTag :type="health.storage.ready ? 'success' : 'warning'" size="small">
              {{ health.storage.ready ? '已就绪' : '未就绪' }}
            </ElTag>
          </ElDescriptionsItem>
        </ElDescriptions>
        <p class="text-color-secondary mb-0 mt-12px">{{ health.storage.message }}</p>
      </ElCard>
      <ElCard shadow="never">
        <div class="mb-16px">专用执行节点</div>
        <ElTable :data="health.workers" border empty-text="尚无专用 Worker 心跳，请检查 provisioning 队列">
          <ElTableColumn prop="id" label="节点" min-width="240" show-overflow-tooltip />
          <ElTableColumn label="状态" width="120" align="center">
            <template #default="{ row }">
              <ElTag :type="row.online ? 'success' : 'warning'" size="small">
                {{ row.online ? '在线' : '心跳超时' }}
              </ElTag>
            </template>
          </ElTableColumn>
          <ElTableColumn label="执行环境" min-width="160" align="center">
            <template #default="{ row }">
              {{
                row.checks.versionMatched && row.checks.providerLocks && row.checks.linux
                  ? '检查通过'
                  : '请检查 CLI、镜像与版本锁定'
              }}
            </template>
          </ElTableColumn>
          <ElTableColumn label="最近心跳" min-width="180" align="center">
            <template #default="{ row }">{{ formatLocalDateTime(row.lastSeenAt) }}</template>
          </ElTableColumn>
        </ElTable>
      </ElCard>
      <ElCard shadow="never">
        <div class="mb-16px">当前异常</div>
        <ElTable :data="health.incidents" border empty-text="暂无已记录异常">
          <ElTableColumn prop="message" label="异常说明" min-width="300" show-overflow-tooltip />
          <ElTableColumn label="记录时间" min-width="180" align="center">
            <template #default="{ row }">{{ formatLocalDateTime(row.created_at) }}</template>
          </ElTableColumn>
        </ElTable>
        <p class="text-color-secondary mb-0 mt-16px">
          计划与诊断制品保留
          {{ health.retention.planDays }} 天；活动资源的状态备份持续保留。清理通过管理命令预览后执行。
        </p>
      </ElCard>
    </template>
  </div>
</template>
