<script setup lang="tsx">
import { ref } from 'vue';
import { fetchGetWorkerPools } from '@/service/api';

defineOptions({ name: 'TaskWorkerPool' });
const loading = ref(false);
const rows = ref<Api.Jobs.WorkerPoolOption[]>([]);
async function load() {
  loading.value = true;
  const { data } = await fetchGetWorkerPools();
  rows.value = data?.list ?? [];
  loading.value = false;
}
load();
</script>

<template>
  <div class="min-h-500px flex-col-stretch gap-16px overflow-hidden">
    <ElCard class="card-wrapper sm:flex-1-hidden">
      <template #header>
        <div class="flex items-center justify-between">
          <span>Worker 池</span>
          <ElButton :loading="loading" @click="load">刷新</ElButton>
        </div>
      </template>
      <ElTable v-loading="loading" :data="rows" border height="100%">
        <ElTableColumn prop="code" label="编码" min-width="140" />
        <ElTableColumn prop="name" label="名称" min-width="140" />
        <ElTableColumn prop="queueName" label="队列" min-width="160" />
        <ElTableColumn prop="region" label="地域" width="120">
          <template #default="{ row }">{{ row.region || '-' }}</template>
        </ElTableColumn>
        <ElTableColumn prop="concurrencyLimit" label="并发限制" width="110" />
        <ElTableColumn prop="executionKinds" label="执行类型" min-width="180" />
        <ElTableColumn prop="isActive" label="状态" width="90">
          <template #default="{ row }">
            <ElTag :type="row.isActive ? 'success' : 'info'">{{ row.isActive ? '启用' : '停用' }}</ElTag>
          </template>
        </ElTableColumn>
      </ElTable>
    </ElCard>
  </div>
</template>
