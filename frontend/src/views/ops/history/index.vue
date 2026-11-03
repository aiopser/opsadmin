<script setup lang="tsx">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { ElButton, ElTag } from 'element-plus';
import { executionKindRecord, runStatusRecord, runStatusTagType } from '@/constants/business';
import { fetchGetTaskRunList } from '@/service/api';
import { defaultTransform, useUIPaginatedTable } from '@/hooks/common/table';
import { $t } from '@/locales';

defineOptions({ name: 'OpsHistory' });

const router = useRouter();

/** ============ 搜索 ============ */

const statusOptions = (Object.keys(runStatusRecord) as Api.Jobs.RunStatus[]).map(value => ({
  value,
  label: $t(runStatusRecord[value])
}));

const executionKindOptions = (Object.keys(executionKindRecord) as Api.Jobs.ExecutionKind[]).map(value => ({
  value,
  label: $t(executionKindRecord[value])
}));

function getInitSearchParams() {
  return {
    current: 1,
    size: 10,
    status: undefined as string | undefined,
    executionKind: undefined as Api.Jobs.ExecutionKind | undefined,
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
      executionKind: searchParams.value.executionKind,
      search: searchParams.value.search
    }),
  transform: response => defaultTransform(response),
  onPaginationParamsChange: params => {
    searchParams.value.current = params.currentPage ?? 1;
    searchParams.value.size = params.pageSize ?? 10;
  },
  columns: () => [
    { prop: 'id', label: $t('page.task.run.id'), width: 80, align: 'center', className: 'tabular-nums' },
    {
      prop: 'name',
      label: '作业名称',
      minWidth: 150,
      showOverflowTooltip: true,
      formatter: row => row.name || row.workflowName || '-'
    },
    {
      prop: 'status',
      label: $t('page.task.run.statusLabel'),
      width: 110,
      align: 'center',
      formatter: row => <ElTag type={runStatusTagType[row.status] ?? 'info'}>{$t(runStatusRecord[row.status])}</ElTag>
    },
    {
      prop: 'executionKind',
      label: $t('page.task.run.executionKind'),
      width: 120,
      align: 'center',
      formatter: row => $t(executionKindRecord[row.executionKind])
    },
    {
      prop: 'targetCount',
      label: $t('page.task.run.targetCount'),
      width: 90,
      align: 'center',
      className: 'tabular-nums'
    },
    {
      prop: 'triggeredByName',
      label: $t('page.task.run.triggeredBy'),
      width: 120,
      formatter: row => row.triggeredByName || '-'
    },
    {
      prop: 'startedAt',
      label: $t('page.task.run.startedAt'),
      width: 170,
      formatter: row => row.startedAt || '-'
    },
    {
      prop: 'durationMs',
      label: $t('page.task.run.duration'),
      width: 110,
      align: 'center',
      className: 'tabular-nums',
      formatter: row => (row.durationMs === null ? '-' : `${(row.durationMs / 1000).toFixed(1)}s`)
    },
    {
      prop: 'operate',
      label: $t('common.operate'),
      width: 90,
      align: 'center',
      fixed: 'right',
      formatter: row => (
        <div class="flex justify-center gap-4px">
          <ElButton type="primary" plain size="small" onClick={() => openDetail(row.id)}>
            {$t('common.detail')}
          </ElButton>
        </div>
      )
    }
  ]
});

function resetSearchParams() {
  searchParams.value = getInitSearchParams();
  getDataByPage();
}

function openDetail(id: number) {
  router.push({
    name: 'ops_run-detail',
    params: { id }
  });
}
</script>

<template>
  <div class="min-h-500px flex-col-stretch gap-16px overflow-hidden lt-sm:overflow-auto">
    <SearchPanel @reset="resetSearchParams" @search="getDataByPage">
      <ElForm :model="searchParams" label-width="80px" @submit.prevent="getDataByPage">
        <ElFormItem :label="$t('page.task.run.statusLabel')">
          <ElSelect v-model="searchParams.status" clearable :placeholder="$t('page.task.run.statusLabel')">
            <ElOption v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem :label="$t('page.task.run.executionKind')">
          <ElSelect v-model="searchParams.executionKind" clearable :placeholder="$t('page.task.run.executionKind')">
            <ElOption v-for="item in executionKindOptions" :key="item.value" :label="item.label" :value="item.value" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem :label="$t('page.task.run.keyword')">
          <ElInput
            v-model="searchParams.search"
            clearable
            :placeholder="$t('common.keywordSearch')"
            @keyup.enter="getDataByPage()"
          />
        </ElFormItem>
      </ElForm>
    </SearchPanel>

    <ElCard class="card-wrapper sm:flex-1-hidden">
      <template #header>
        <div class="flex items-center justify-between">
          <p>{{ $t('page.task.run.title') }}</p>
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

<style scoped></style>
