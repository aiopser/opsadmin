<script setup lang="tsx">
import { computed, ref } from 'vue';
import { useRoute } from 'vue-router';
import { fetchGetCmdbResourceList } from '@/service/api/cmdb';
const route = useRoute();
const resource = computed(() => String(route.name).replace('cmdb_', ''));
const title = computed(
  () =>
    (
      ({ business: '业务', source: '资产源', sync: '同步记录', tag: '主机标签', tree: '服务树' }) as Record<
        string,
        string
      >
    )[resource.value] || resource.value
);
const rows = ref<Array<Record<string, unknown>>>([]);
const loading = ref(false);

const RESOURCE_PATHS: Record<string, string> = {
  business: 'businesses',
  source: 'asset-sources',
  sync: 'asset-sync-records',
  tag: 'tags',
  tree: 'service-tree-nodes'
};

async function load() {
  loading.value = true;
  const { data } = await fetchGetCmdbResourceList(RESOURCE_PATHS[resource.value] ?? 'businesses');
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
          <span>{{ title }}</span>
          <ElButton :loading="loading" @click="load">刷新</ElButton>
        </div>
      </template>
      <ElTable v-loading="loading" :data="rows" border height="100%">
        <ElTableColumn
          v-for="key in ['id', 'name', 'code', 'status', 'type', 'description', 'isActive', 'createdAt']"
          :key="key"
          :prop="key"
          :label="key"
          min-width="140"
        />
      </ElTable>
    </ElCard>
  </div>
</template>
