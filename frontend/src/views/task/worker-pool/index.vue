<script setup lang="ts">
import { onScopeDispose, ref, shallowRef } from 'vue';
import { fetchGetWorkerPoolList } from '@/service/api';

defineOptions({ name: 'TaskWorkerPool' });

const loading = ref(false);
const rows = shallowRef<Api.Jobs.WorkerPoolRecord[]>([]);
const keyword = ref('');
const appliedKeyword = ref('');
const currentPage = ref(1);
const pageSize = ref(20);
const total = ref(0);
const loadError = ref(false);
let disposed = false;
let currentRequest: AbortController | undefined;

const executionKindLabels: Record<string, string> = {
  workflow: '流程',
  quick_command: '脚本',
  playbook: 'Playbook',
  module: 'Ansible 模块'
};

function executionKindsText(kinds: string[]): string {
  return kinds.map(kind => executionKindLabels[kind] ?? kind).join('、') || '-';
}

async function load() {
  currentRequest?.abort();
  const controller = new AbortController();
  currentRequest = controller;
  loading.value = true;
  try {
    const { data, error } = await fetchGetWorkerPoolList(
      { current: currentPage.value, size: pageSize.value, search: appliedKeyword.value },
      controller.signal
    );
    if (disposed || currentRequest !== controller) return;
    loadError.value = Boolean(error);
    if (error) {
      rows.value = [];
      total.value = 0;
      window.$message?.error('加载执行节点池失败');
    } else if (data) {
      rows.value = data.records;
      total.value = data.total;
    }
  } catch {
    if (!disposed && currentRequest === controller && !controller.signal.aborted) {
      loadError.value = true;
      rows.value = [];
      total.value = 0;
      window.$message?.error('加载执行节点池失败');
    }
  } finally {
    if (!disposed && currentRequest === controller) loading.value = false;
  }
}

function search() {
  appliedKeyword.value = keyword.value.trim();
  currentPage.value = 1;
  load();
}

function resetSearch() {
  keyword.value = '';
  search();
}

function changePage(page: number) {
  currentPage.value = page;
  load();
}

function changePageSize(size: number) {
  pageSize.value = size;
  currentPage.value = 1;
  load();
}

load();

onScopeDispose(() => {
  disposed = true;
  currentRequest?.abort();
});
</script>

<template>
  <div class="min-h-500px flex-col-stretch gap-16px overflow-hidden lt-sm:overflow-auto">
    <SearchPanel @reset="resetSearch" @search="search">
      <ElForm label-width="80px" @submit.prevent="search">
        <ElFormItem label="关键词">
          <ElInput v-model="keyword" clearable placeholder="名称或编码" @keyup.enter="search" />
        </ElFormItem>
      </ElForm>
    </SearchPanel>

    <ElCard class="card-wrapper sm:flex-1-hidden">
      <template #header>
        <div class="flex flex-wrap items-center justify-between gap-12px">
          <div class="min-w-0">
            <p>执行节点池</p>
            <p class="mt-4px text-12px text-gray-500">任务按执行类型和地域分配到可用节点池</p>
          </div>
          <ElButton :loading="loading" @click="load">刷新</ElButton>
        </div>
      </template>
      <div class="h-[calc(100%-52px)] overflow-x-auto">
        <ElSkeleton v-if="loading && !rows.length" :rows="4" animated />
        <ElEmpty
          v-else-if="!rows.length"
          :description="
            loadError ? '加载执行节点池失败' : appliedKeyword ? '没有符合条件的执行节点池' : '暂无执行节点池'
          "
          :image-size="80"
        >
          <ElButton v-if="appliedKeyword && !loadError" @click="resetSearch">清除筛选</ElButton>
          <ElButton v-else @click="load">重新加载</ElButton>
        </ElEmpty>
        <ElTable
          v-else
          v-loading="loading"
          :data="rows"
          row-key="id"
          border
          height="100%"
          class="min-w-900px sm:h-full"
        >
          <ElTableColumn prop="name" label="名称" min-width="160" show-overflow-tooltip>
            <template #default="{ row }">
              <span>{{ row.name }}</span>
              <ElTag v-if="row.isDefault" class="ml-8px" size="small" type="info">默认</ElTag>
            </template>
          </ElTableColumn>
          <ElTableColumn prop="code" label="编码" min-width="140" show-overflow-tooltip />
          <ElTableColumn prop="queueName" label="队列" min-width="160" show-overflow-tooltip />
          <ElTableColumn prop="region" label="地域" min-width="120">
            <template #default="{ row }">{{ row.region || '-' }}</template>
          </ElTableColumn>
          <ElTableColumn label="并发上限" width="110" align="center">
            <template #default="{ row }">
              <span class="tabular-nums">{{ row.concurrencyLimit }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn label="支持的执行类型" min-width="220" show-overflow-tooltip>
            <template #default="{ row }">{{ executionKindsText(row.executionKinds) }}</template>
          </ElTableColumn>
          <ElTableColumn label="状态" width="90" align="center">
            <template #default="{ row }">
              <ElTag :type="row.isActive ? 'success' : 'info'">{{ row.isActive ? '启用' : '停用' }}</ElTag>
            </template>
          </ElTableColumn>
        </ElTable>
      </div>
      <div class="mt-20px flex justify-end overflow-x-auto">
        <ElPagination
          v-if="total"
          :current-page="currentPage"
          :page-size="pageSize"
          :total="total"
          :page-sizes="[20, 50, 100]"
          layout="total,prev,pager,next,sizes"
          @current-change="changePage"
          @size-change="changePageSize"
        />
      </div>
    </ElCard>
  </div>
</template>
