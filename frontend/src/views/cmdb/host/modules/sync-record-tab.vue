<script setup lang="tsx">
import { computed, onMounted, ref } from 'vue';
import { fetchGetAssetSourceList, fetchGetSyncRecordList } from '@/service/api';
import { defaultTransform, useUIPaginatedTable } from '@/hooks/common/table';

defineOptions({ name: 'CmdbSyncRecordTab' });

/** ============ 枚举文案 ============ */

const statusOptions = [
  { value: 'queued', label: '待执行' },
  { value: 'running', label: '同步中' },
  { value: 'succeeded', label: '成功' },
  { value: 'failed', label: '失败' }
];
const statusText: Record<string, string> = Object.fromEntries(statusOptions.map(item => [item.value, item.label]));

const statusTagType: Record<string, UI.ThemeColor> = {
  queued: 'info',
  running: 'warning',
  succeeded: 'success',
  failed: 'danger'
};

/** ============ 搜索 ============ */

function getInitSearchParams() {
  return {
    current: 1,
    size: 10,
    search: undefined as string | undefined,
    source: undefined as number | undefined,
    status: undefined as Api.Cmdb.AssetSyncStatus | undefined
  };
}

const searchParams = ref(getInitSearchParams());

/** ============ 列表（只读） ============ */

const { columns, columnChecks, data, getData, getDataByPage, loading, mobilePagination } = useUIPaginatedTable({
  paginationProps: {
    currentPage: searchParams.value.current,
    pageSize: searchParams.value.size
  },
  api: () => fetchGetSyncRecordList(searchParams.value),
  transform: response => defaultTransform(response),
  onPaginationParamsChange: params => {
    searchParams.value.current = params.currentPage ?? 1;
    searchParams.value.size = params.pageSize ?? 10;
  },
  columns: () => [
    { prop: 'id', label: 'ID', width: 70 },
    { prop: 'sourceName', label: '资产来源', width: 130, showOverflowTooltip: true },
    {
      prop: 'status',
      label: '状态',
      width: 90,
      align: 'center',
      formatter: row => <ElTag type={statusTagType[row.status] ?? 'info'}>{statusText[row.status] ?? row.status}</ElTag>
    },
    {
      prop: 'task_id',
      label: '任务 ID',
      width: 140,
      showOverflowTooltip: true,
      formatter: row => <span class="text-12px font-mono">{row.task_id || '-'}</span>
    },
    { prop: 'total_count', label: '总数', width: 70, align: 'center' },
    { prop: 'created_count', label: '新增', width: 70, align: 'center' },
    { prop: 'updated_count', label: '更新', width: 70, align: 'center' },
    { prop: 'skipped_count', label: '跳过', width: 70, align: 'center' },
    { prop: 'started_at', label: '开始时间', width: 170, formatter: row => row.started_at || '-' },
    { prop: 'finished_at', label: '结束时间', width: 170, formatter: row => row.finished_at || '-' },
    {
      prop: 'error_message',
      label: '错误信息',
      minWidth: 180,
      showOverflowTooltip: true,
      formatter: row => row.error_message || '-'
    },
    { prop: 'created_at', label: '创建时间', width: 170, formatter: row => row.created_at || '-' }
  ]
});

const hasFilter = computed(() =>
  Boolean(searchParams.value.search || searchParams.value.source || searchParams.value.status)
);

function resetSearchParams() {
  searchParams.value = getInitSearchParams();
  getDataByPage();
}

/** 来源选项（挂载时静默加载） */
const sourceOptions = ref<{ value: number; label: string }[]>([]);

onMounted(async () => {
  const { error, data: resData } = await fetchGetAssetSourceList({ current: 1, size: 100 });
  if (!error) {
    sourceOptions.value = (resData.records ?? []).map(item => ({ value: item.id, label: item.name }));
  }
});
</script>

<template>
  <div class="flex-col-stretch gap-12px">
    <ElForm :model="searchParams" label-width="70px" inline @submit.prevent>
      <ElFormItem label="资产来源">
        <ElSelect v-model="searchParams.source" clearable filterable placeholder="全部" class="w-180px">
          <ElOption v-for="item in sourceOptions" :key="item.value" :label="item.label" :value="item.value" />
        </ElSelect>
      </ElFormItem>
      <ElFormItem label="状态">
        <ElSelect v-model="searchParams.status" clearable placeholder="全部" class="w-120px">
          <ElOption v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
        </ElSelect>
      </ElFormItem>
      <ElFormItem label="关键词">
        <ElInput
          v-model="searchParams.search"
          clearable
          placeholder="任务 ID/错误信息"
          class="w-200px"
          @keyup.enter="getDataByPage()"
        />
      </ElFormItem>
      <ElFormItem>
        <ElButton type="primary" @click="getDataByPage()">查询</ElButton>
        <ElButton :disabled="!hasFilter" @click="resetSearchParams">重置</ElButton>
      </ElFormItem>
    </ElForm>

    <div class="flex items-center justify-between">
      <p class="font-medium">资产同步记录</p>
      <TableHeaderOperation
        v-model:columns="columnChecks"
        :loading="loading"
        :show-add="false"
        :show-batch-delete="false"
        @refresh="getData"
      />
    </div>

    <ElTable v-loading="loading" height="520px" border :data="data" row-key="id">
      <ElTableColumn v-for="col in columns" :key="col.prop" v-bind="col" />
    </ElTable>

    <div class="flex justify-end">
      <ElPagination
        v-if="mobilePagination.total"
        layout="total,prev,pager,next,sizes"
        v-bind="mobilePagination"
        @current-change="mobilePagination['current-change']"
        @size-change="mobilePagination['size-change']"
      />
    </div>
  </div>
</template>

<style scoped></style>
