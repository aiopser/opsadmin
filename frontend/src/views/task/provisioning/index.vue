<script setup lang="ts">
import { onMounted, ref, shallowRef } from 'vue';
import { fetchResourceApplications } from '@/service/api/provisioning';
import type { ResourceApplication } from '@/service/api/provisioning';
import SearchPanel from '@/components/advanced/search-panel.vue';
import ApplicationDrawer from './request-drawer.vue';
import ResourceDetail from './detail.vue';
import { statusLabel } from './shared';

defineOptions({ name: 'TaskProvisioning' });

const keyword = ref('');
const current = ref(1);
const total = ref(0);
const loading = ref(false);
const records = shallowRef<ResourceApplication[]>([]);
const createVisible = ref(false);
const detailId = ref<number>();
const detailVisible = ref(false);

async function load() {
  loading.value = true;
  try {
    const { data, error } = await fetchResourceApplications(current.value, keyword.value);
    if (!error && data) {
      records.value = data.list;
      total.value = data.total;
    }
  } finally {
    loading.value = false;
  }
}

function search() {
  current.value = 1;
  load();
}

function reset() {
  keyword.value = '';
  search();
}

function openCreate() {
  createVisible.value = true;
}

function openDetail(row: ResourceApplication) {
  detailId.value = row.id;
  detailVisible.value = true;
}

function created(id: number) {
  createVisible.value = false;
  detailId.value = id;
  detailVisible.value = true;
  load();
}

onMounted(load);
</script>

<template>
  <div class="flex-col-stretch gap-16px">
    <SearchPanel @search="search" @reset="reset">
      <ElForm label-width="80px" @submit.prevent="search">
        <ElFormItem label="关键词">
          <ElInput v-model="keyword" clearable placeholder="申请名称" @keyup.enter="search" />
        </ElFormItem>
      </ElForm>
    </SearchPanel>
    <ElCard class="card-wrapper" shadow="never">
      <div class="mb-16px flex items-center justify-between gap-12px">
        <span>资源申请</span>
        <ElSpace>
          <ElButton @click="load">刷新</ElButton>
          <ElButton type="primary" @click="openCreate">申请主机</ElButton>
        </ElSpace>
      </div>
      <ElTable v-loading="loading" :data="records" border>
        <ElTableColumn prop="id" label="ID" width="80" align="center" />
        <ElTableColumn prop="name" label="申请名称" min-width="160" show-overflow-tooltip />
        <ElTableColumn prop="source_name" label="云账号" min-width="150" align="center" show-overflow-tooltip />
        <ElTableColumn prop="region" label="地域" min-width="140" align="center" />
        <ElTableColumn label="数量" width="80" align="center">
          <template #default="{ row }">{{ row.parameters.count }}</template>
        </ElTableColumn>
        <ElTableColumn label="审批状态" width="110" align="center">
          <template #default="{ row }">{{ statusLabel(row.approval_status) }}</template>
        </ElTableColumn>
        <ElTableColumn label="执行状态" width="120" align="center">
          <template #default="{ row }">{{ statusLabel(row.execution_status) }}</template>
        </ElTableColumn>
        <ElTableColumn label="纳管状态" width="110" align="center">
          <template #default="{ row }">{{ statusLabel(row.inventory_status) }}</template>
        </ElTableColumn>
        <ElTableColumn label="操作" width="90" align="center">
          <template #default="{ row }"><ElButton link type="primary" @click="openDetail(row)">详情</ElButton></template>
        </ElTableColumn>
      </ElTable>
      <div class="mt-16px flex justify-end">
        <ElPagination
          v-model:current-page="current"
          :total="total"
          :page-size="10"
          layout="total, prev, pager, next"
          @current-change="load"
        />
      </div>
    </ElCard>
    <ApplicationDrawer v-model="createVisible" @created="created" />
    <ResourceDetail v-model="detailVisible" :request-id="detailId" @updated="load" />
  </div>
</template>
