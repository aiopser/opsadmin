<script setup lang="tsx">
import { computed, ref } from 'vue';
import { useRouter } from 'vue-router';
import { fetchCancelRun, fetchGetTaskRunList } from '@/service/api';
import { defaultTransform, useUIPaginatedTable } from '@/hooks/common/table';

defineOptions({ name: 'OpsHistory' });

const router = useRouter();

/** ============ 搜索 ============ */

const statusOptions = [
  { value: 'pending', label: '待执行' },
  { value: 'queued', label: '排队中' },
  { value: 'running', label: '执行中' },
  { value: 'waiting', label: '等待中' },
  { value: 'success', label: '成功' },
  { value: 'failed', label: '失败' },
  { value: 'timeout', label: '超时' },
  { value: 'canceled', label: '已取消' }
];

const statusText: Record<string, string> = Object.fromEntries(statusOptions.map(item => [item.value, item.label]));

const statusTagType: Record<string, string> = {
  pending: 'info',
  queued: 'info',
  running: 'primary',
  waiting: 'warning',
  cancel_requested: 'warning',
  success: 'success',
  failed: 'danger',
  timeout: 'danger',
  canceled: 'info'
};

function getInitSearchParams() {
  return {
    current: 1,
    size: 10,
    status: undefined as string | undefined,
    search: undefined as string | undefined
  };
}

const searchParams = ref(getInitSearchParams());

/** ============ 列表 ============ */

const { columns, columnChecks, data, getData, getDataByPage, loading, mobilePagination } = useUIPaginatedTable({
  paginationProps: {
    currentPage: searchParams.value.current,
    pageSize: searchParams.value.size
  },
  api: () =>
    fetchGetTaskRunList({
      current: searchParams.value.current,
      size: searchParams.value.size,
      runDomain: 'ops',
      status: searchParams.value.status as Api.Jobs.RunStatus | null | undefined,
      search: searchParams.value.search
    }),
  transform: response => defaultTransform(response),
  onPaginationParamsChange: params => {
    searchParams.value.current = params.currentPage ?? 1;
    searchParams.value.size = params.pageSize ?? 10;
  },
  columns: () => [
    { prop: 'id', label: 'ID', width: 80 },
    { prop: 'workflowName', label: '作业名称', minWidth: 160, showOverflowTooltip: true },
    {
      prop: 'status',
      label: '状态',
      width: 100,
      align: 'center',
      formatter: row => (
        <ElTag type={(statusTagType[row.status] ?? 'info') as any}>{statusText[row.status] ?? row.status}</ElTag>
      )
    },
    {
      prop: 'executionKind',
      label: '执行类型',
      width: 110,
      align: 'center',
      formatter: row =>
        ({ workflow: '工作流', quick_command: '快速命令', playbook: 'Playbook', module: 'Module' })[
          row.executionKind
        ] ?? row.executionKind
    },
    {
      prop: 'triggerType',
      label: '触发方式',
      width: 100,
      align: 'center',
      formatter: row => ({ manual: '手动', api: 'API', scheduled: '定时' })[row.triggerType] ?? row.triggerType
    },
    { prop: 'targetCount', label: '目标数', width: 80, align: 'center' },
    { prop: 'workerPoolName', label: 'Worker 池', width: 130, showOverflowTooltip: true },
    { prop: 'triggeredByName', label: '触发人', width: 110, formatter: row => row.triggeredByName || '-' },
    { prop: 'startedAt', label: '开始时间', width: 170, formatter: row => row.startedAt || '-' },
    {
      prop: 'durationMs',
      label: '耗时',
      width: 100,
      align: 'center',
      formatter: row => (row.durationMs ? `${(row.durationMs / 1000).toFixed(1)}s` : '-')
    },
    {
      prop: 'operate',
      label: '操作',
      width: 150,
      align: 'center',
      fixed: 'right',
      formatter: row => (
        <>
          <ElButton type="primary" plain size="small" onClick={() => goDetail(row.id)}>
            详情
          </ElButton>
          {['pending', 'queued', 'running', 'waiting', 'cancel_requested'].includes(row.status) && (
            <ElPopconfirm title="确认取消该执行？" onConfirm={() => handleCancel(row.id)}>
              {{
                reference: () => (
                  <ElButton type="danger" plain size="small">
                    取消
                  </ElButton>
                )
              }}
            </ElPopconfirm>
          )}
        </>
      )
    }
  ]
});

const hasFilter = computed(() => Boolean(searchParams.value.status || searchParams.value.search));

function resetSearchParams() {
  searchParams.value = getInitSearchParams();
  getDataByPage();
}

function goDetail(id: number) {
  router.push({ name: 'task_run-detail', params: { id: String(id) }, query: { domain: 'ops' } });
}

async function handleCancel(id: number) {
  const { error } = await fetchCancelRun(id, 'ops');

  if (!error) {
    window.$message?.success('取消请求已提交');
    getData();
  }
}
</script>

<template>
  <div class="min-h-500px flex-col-stretch gap-16px overflow-hidden lt-sm:overflow-auto">
    <ElCard class="card-wrapper">
      <ElForm :model="searchParams" label-width="70px" inline @submit.prevent>
        <ElFormItem label="状态">
          <ElSelect v-model="searchParams.status" clearable placeholder="全部" class="w-140px">
            <ElOption v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="关键词">
          <ElInput
            v-model="searchParams.search"
            clearable
            placeholder="作业名称/触发人"
            class="w-200px"
            @keyup.enter="getDataByPage()"
          />
        </ElFormItem>
        <ElFormItem>
          <ElButton type="primary" @click="getDataByPage()">查询</ElButton>
          <ElButton :disabled="!hasFilter" @click="resetSearchParams">重置</ElButton>
        </ElFormItem>
      </ElForm>
    </ElCard>

    <ElCard class="card-wrapper sm:flex-1-hidden">
      <template #header>
        <div class="flex items-center justify-between">
          <p>作业历史</p>
          <TableHeaderOperation
            v-model:columns="columnChecks"
            :loading="loading"
            :show-add="false"
            :show-batch-delete="false"
            @refresh="getData"
          />
        </div>
      </template>
      <div class="h-[calc(100%-52px)]">
        <ElTable v-loading="loading" height="100%" border class="sm:h-full" :data="data" row-key="id">
          <ElTableColumn v-for="col in columns" :key="col.prop" v-bind="col" />
        </ElTable>
      </div>
      <div class="mt-20px flex justify-end">
        <ElPagination
          v-if="mobilePagination.total"
          layout="total,prev,pager,next,sizes"
          v-bind="mobilePagination"
          @current-change="mobilePagination['current-change']"
          @size-change="mobilePagination['size-change']"
        />
      </div>
    </ElCard>
  </div>
</template>
