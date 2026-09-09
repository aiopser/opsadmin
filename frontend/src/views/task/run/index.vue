<script setup lang="tsx">
import { computed, onScopeDispose, ref } from 'vue';
import { useRouter } from 'vue-router';
import { executionKindRecord, runDomainRecord, runStatusRecord } from '@/constants/business';
import {
  fetchCancelRun,
  fetchGetTaskRunList,
  fetchRerunRun,
  fetchRetryFailedRun,
  fetchRunLogFile
} from '@/service/api';
import { defaultTransform, useUIPaginatedTable } from '@/hooks/common/table';
import { useAuth } from '@/hooks/business/auth';
import { $t } from '@/locales';
import RunCreateDrawer from './modules/run-create-drawer.vue';

defineOptions({ name: 'TaskRun' });

const router = useRouter();
const createVisible = ref(false);
const requestScope = new AbortController();
onScopeDispose(() => requestScope.abort());
function openCreate() {
  createVisible.value = true;
}
function onCreated(run: Api.Jobs.RunRecord) {
  goDetail(run.id, run.runDomain);
}
const { hasAuth } = useAuth();

const runStatusOptions = (Object.keys(runStatusRecord) as Api.Jobs.RunStatus[]).map(value => ({
  value,
  label: $t(runStatusRecord[value])
}));

const executionKindOptions = (Object.keys(executionKindRecord) as Api.Jobs.ExecutionKind[]).map(value => ({
  value,
  label: $t(executionKindRecord[value])
}));

const runDomainOptions = (Object.keys(runDomainRecord) as Api.Jobs.RunDomain[]).map(value => ({
  value,
  label: $t(runDomainRecord[value])
}));

function getInitSearchParams(): Api.Jobs.RunSearchParams {
  return {
    current: 1,
    size: 10,
    status: undefined,
    executionKind: undefined,
    runDomain: undefined,
    search: undefined
  };
}

const searchParams = ref<Api.Jobs.RunSearchParams>(getInitSearchParams());

const runStatusTagType: Record<Api.Jobs.RunStatus, UI.ThemeColor> = {
  pending: 'info',
  queued: 'info',
  running: 'primary',
  waiting: 'primary',
  cancel_requested: 'warning',
  success: 'success',
  failed: 'danger',
  timeout: 'danger',
  canceled: 'info'
};

const activeStatuses = new Set<Api.Jobs.RunStatus>(['pending', 'queued', 'running', 'waiting', 'cancel_requested']);
const finishedStatuses = new Set<Api.Jobs.RunStatus>(['success', 'failed', 'timeout', 'canceled']);

const canCancel = (status: Api.Jobs.RunStatus) => activeStatuses.has(status);
const canRerun = (status: Api.Jobs.RunStatus) => finishedStatuses.has(status);

const operatingId = ref<number | null>(null);

const { columns, columnChecks, data, getData, getDataByPage, loading, mobilePagination } = useUIPaginatedTable({
  paginationProps: {
    currentPage: searchParams.value.current,
    pageSize: searchParams.value.size
  },
  api: () => fetchGetTaskRunList(searchParams.value),
  transform: response => defaultTransform(response),
  onPaginationParamsChange: params => {
    searchParams.value.current = params.currentPage ?? 1;
    searchParams.value.size = params.pageSize ?? 10;
  },
  columns: () => [
    { prop: 'id', label: $t('page.task.run.id'), width: 80 },
    { prop: 'workflowName', label: $t('page.task.run.workflowName'), minWidth: 140, showOverflowTooltip: true },
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
      width: 100,
      align: 'center',
      formatter: row => $t(executionKindRecord[row.executionKind])
    },
    {
      prop: 'runDomain',
      label: $t('page.task.run.runDomain'),
      width: 90,
      align: 'center',
      formatter: row => $t(runDomainRecord[row.runDomain])
    },
    { prop: 'targetCount', label: $t('page.task.run.targetCount'), width: 80, align: 'center' },
    { prop: 'triggeredByName', label: $t('page.task.run.triggeredBy'), width: 100 },
    { prop: 'startedAt', label: $t('page.task.run.startedAt'), width: 170, formatter: row => row.startedAt || '-' },
    {
      prop: 'durationMs',
      label: $t('page.task.run.duration'),
      width: 100,
      align: 'center',
      formatter: row => (row.durationMs === null ? '-' : `${(row.durationMs / 1000).toFixed(1)}s`)
    },
    {
      prop: 'operate',
      label: $t('common.operate'),
      align: 'center',
      width: 230,
      fixed: 'right',
      formatter: row => (
        <div class="flex justify-center gap-4px">
          <ElButton type="primary" plain size="small" onClick={() => goDetail(row.id)}>
            {$t('common.detail')}
          </ElButton>
          {canCancel(row.status) && hasAuth(`${row.runDomain === 'ops' ? 'ops' : 'jobs'}.workflow_run:cancel`) ? (
            <ElButton
              type="warning"
              plain
              size="small"
              loading={operatingId.value === row.id}
              onClick={() => onCancel(row.id)}
            >
              {$t('page.task.run.cancel')}
            </ElButton>
          ) : null}
          {row.status === 'failed' && hasAuth(`${row.runDomain === 'ops' ? 'ops' : 'jobs'}.workflow_run:retry`) ? (
            <ElButton
              type="danger"
              plain
              size="small"
              loading={operatingId.value === row.id}
              onClick={() => onRetry(row.id)}
            >
              {$t('page.task.run.retry')}
            </ElButton>
          ) : null}
          {canRerun(row.status) && hasAuth(`${row.runDomain === 'ops' ? 'ops' : 'jobs'}.workflow_run:retry`) ? (
            <ElButton plain size="small" loading={operatingId.value === row.id} onClick={() => onRerun(row.id)}>
              {$t('page.task.run.rerun')}
            </ElButton>
          ) : null}
          <ElButton plain size="small" onClick={() => onDownloadLog(row.id)}>
            {$t('page.task.run.log')}
          </ElButton>
        </div>
      )
    }
  ]
});

function domainFor(id: number): Api.Jobs.RunDomain {
  return data.value.find(run => run.id === id)?.runDomain ?? searchParams.value.runDomain ?? 'task';
}

function goDetail(id: number, domain = domainFor(id)) {
  router.push({ name: 'task_run-detail', params: { id }, query: { domain } });
}

async function onCancel(id: number) {
  operatingId.value = id;
  try {
    const { error } = await fetchCancelRun(id, domainFor(id));
    if (!error) {
      window.$message?.success($t('common.updateSuccess'));
      getData();
    }
  } finally {
    operatingId.value = null;
  }
}

async function onRetry(id: number) {
  operatingId.value = id;
  try {
    const { data: newRun, error } = await fetchRetryFailedRun(id, domainFor(id));
    if (!error && newRun) {
      window.$message?.success($t('page.task.run.retryCreated'));
      goDetail(newRun.id, newRun.runDomain);
    }
  } finally {
    operatingId.value = null;
  }
}

async function onRerun(id: number) {
  operatingId.value = id;
  try {
    const { data: newRun, error } = await fetchRerunRun(id, domainFor(id));
    if (!error && newRun) {
      window.$message?.success($t('page.task.run.retryCreated'));
      goDetail(newRun.id, newRun.runDomain);
    }
  } finally {
    operatingId.value = null;
  }
}

async function onDownloadLog(id: number) {
  const blob = await fetchRunLogFile(id, domainFor(id), requestScope.signal);
  if (!blob) return;
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `run-${id}.log`;
  link.click();
  URL.revokeObjectURL(url);
}

const hasFilter = computed(() =>
  Boolean(
    searchParams.value.status ||
    searchParams.value.executionKind ||
    searchParams.value.runDomain ||
    searchParams.value.search
  )
);

function resetSearchParams() {
  searchParams.value = getInitSearchParams();
  getDataByPage();
}
</script>

<template>
  <div class="min-h-500px flex-col-stretch gap-16px overflow-hidden lt-sm:overflow-auto">
    <ElCard class="card-wrapper">
      <ElForm :model="searchParams" label-width="80px" inline>
        <ElFormItem :label="$t('page.task.run.statusLabel')">
          <ElSelect
            v-model="searchParams.status"
            clearable
            :placeholder="$t('page.task.run.statusLabel')"
            class="w-160px"
          >
            <ElOption v-for="item in runStatusOptions" :key="item.value" :label="item.label" :value="item.value" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem :label="$t('page.task.run.executionKind')">
          <ElSelect
            v-model="searchParams.executionKind"
            clearable
            :placeholder="$t('page.task.run.executionKind')"
            class="w-150px"
          >
            <ElOption v-for="item in executionKindOptions" :key="item.value" :label="item.label" :value="item.value" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem :label="$t('page.task.run.runDomain')">
          <ElSelect
            v-model="searchParams.runDomain"
            clearable
            :placeholder="$t('page.task.run.runDomain')"
            class="w-140px"
          >
            <ElOption v-for="item in runDomainOptions" :key="item.value" :label="item.label" :value="item.value" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem :label="$t('page.task.run.keyword')">
          <ElInput
            v-model="searchParams.search"
            clearable
            :placeholder="$t('common.keywordSearch')"
            class="w-220px"
            @keyup.enter="getDataByPage()"
          />
        </ElFormItem>
        <ElFormItem>
          <ElButton type="primary" @click="getDataByPage()">
            {{ $t('common.search') }}
          </ElButton>
          <ElButton :disabled="!hasFilter" @click="resetSearchParams">
            {{ $t('common.reset') }}
          </ElButton>
        </ElFormItem>
      </ElForm>
    </ElCard>

    <ElCard class="card-wrapper sm:flex-1-hidden">
      <template #header>
        <div class="flex items-center justify-between">
          <p>{{ $t('page.task.run.title') }}</p>
          <ElButton v-if="hasAuth('jobs.workflow_run:create')" type="primary" @click="openCreate">发起任务</ElButton>
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
    <RunCreateDrawer v-model:visible="createVisible" @created="onCreated" />
  </div>
</template>

<style scoped></style>
