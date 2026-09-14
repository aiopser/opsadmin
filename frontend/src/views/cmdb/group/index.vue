<script setup lang="tsx">
import { ref } from 'vue';
import { fetchGetCmdbResourceList } from '@/service/api/cmdb';
defineOptions({ name: 'CmdbGroup' });
const loading = ref(false);
const rows = ref<Array<Record<string, unknown>>>([]);
async function load() {
  loading.value = true;
  const { data } = await fetchGetCmdbResourceList('host-groups');
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
          <span>主机分组</span>
          <ElButton :loading="loading" @click="load">刷新</ElButton>
        </div>
      </template>
      <ElTable v-loading="loading" :data="rows" border height="100%">
        <ElTableColumn prop="name" label="名称" min-width="180" />
        <ElTableColumn prop="groupType" label="类型" width="120" />
        <ElTableColumn prop="description" label="描述" min-width="240" />
        <ElTableColumn prop="isActive" label="状态" width="90" />
      </ElTable>
    </ElCard>
  </div>
</template>
