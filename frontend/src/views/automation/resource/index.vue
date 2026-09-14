<script setup lang="tsx">
import { ref } from 'vue';
import { fetchPublishedWorkflowVersions } from '@/service/api';
defineOptions({ name: 'AutomationResource' });
const loading = ref(false);
const rows = ref<Api.Jobs.WorkflowVersionOption[]>([]);
async function load() {
  loading.value = true;
  const { data } = await fetchPublishedWorkflowVersions();
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
          <span>自动化配置</span>
          <ElButton :loading="loading" @click="load">刷新</ElButton>
        </div>
      </template>
      <ElTable v-loading="loading" :data="rows" border height="100%">
        <ElTableColumn prop="id" label="ID" width="80" />
        <ElTableColumn prop="workflowCode" label="编码" min-width="160" />
        <ElTableColumn prop="workflowName" label="名称" min-width="180" />
        <ElTableColumn prop="version" label="版本" width="90" />
        <ElTableColumn prop="status" label="状态" width="110" />
      </ElTable>
    </ElCard>
  </div>
</template>
