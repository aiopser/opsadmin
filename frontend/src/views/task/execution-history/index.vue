<script setup lang="tsx">
import { computed, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import {
  executionKindRecord,
  runDomainRecord,
  runStatusRecord,
  runStatusTagType,
  triggerTypeLabels
} from '@/constants/business';
import { fetchGetTaskRunList } from '@/service/api';
import { defaultTransform, useUIPaginatedTable } from '@/hooks/common/table';
import { $t } from '@/locales';

defineOptions({ name: 'TaskExecutionHistory' });

const route = useRoute();
const router = useRouter();
const workflowName = computed(() => (typeof route.query.workflowName === 'string' ? route.query.workflowName : ''));
const ticketName = computed(() => (typeof route.query.ticketName === 'string' ? route.query.ticketName : ''));
const scheduledJobName = computed(() =>
  typeof route.query.scheduledJobName === 'string' ? route.query.scheduledJobName : ''
);
const triggerOptions = (Object.keys(triggerTypeLabels) as Api.Jobs.TriggerType[]).map(value => ({
  value,
  label: triggerTypeLabels[value]
}));

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
  const workflowId = Number(route.query.workflowId);
  const ticketId = Number(route.query.ticketId);
  const scheduledJobId = Number(route.query.scheduledJobId);
  return {
    current: 1,
    size: 10,
    status: undefined,
    executionKind: undefined,
    triggerType: undefined,
    scheduledJobId: Number.isSafeInteger(scheduledJobId) && scheduledJobId > 0 ? scheduledJobId : undefined,
    runDomain: undefined,
    search: undefined,
    workflowId: Number.isSafeInteger(workflowId) && workflowId > 0 ? workflowId : undefined,
    ticketId: Number.isSafeInteger(ticketId) && ticketId > 0 ? ticketId : undefined
  };
}

const searchParams = ref<Api.Jobs.RunSearchParams>(getInitSearchParams());

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
    { prop: 'id', label: $t('page.task.run.id'), width: 80, align: 'center', className: 'tabular-nums' },
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
    {
      prop: 'triggerType',
      label: '触发方式',
      width: 110,
      align: 'center',
      formatter: row => triggerTypeLabels[row.triggerType] ?? row.triggerType
    },
    {
      prop: 'scheduledJobName',
      label: '来源定时任务',
      minWidth: 150,
      showOverflowTooltip: true,
      formatter: row => row.scheduledJobName || '-'
    },
    {
      prop: 'targetCount',
      label: $t('page.task.run.targetCount'),
      width: 80,
      align: 'center',
      className: 'tabular-nums'
    },
    { prop: 'triggeredByName', label: $t('page.task.run.triggeredBy'), width: 100 },
    { prop: 'startedAt', label: $t('page.task.run.startedAt'), width: 170, formatter: row => row.startedAt || '-' },
    {
      prop: 'durationMs',
      label: $t('page.task.run.duration'),
      width: 100,
      align: 'center',
      className: 'tabular-nums',
      formatter: row => (row.durationMs === null ? '-' : `${(row.durationMs / 1000).toFixed(1)}s`)
    },
    {
      prop: 'operate',
      label: $t('common.operate'),
      align: 'center',
      width: 90,
      fixed: 'right',
      formatter: row => (
        <div class="flex justify-center gap-4px">
          <ElButton type="primary" plain size="small" onClick={() => goDetail(row.id)}>
            {$t('common.detail')}
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
  router.push({
    name: 'task_run-detail',
    params: { id },
    query: {
      domain,
      returnWorkflowId: searchParams.value.workflowId ? String(searchParams.value.workflowId) : undefined,
      returnWorkflowName: workflowName.value || undefined,
      returnTicketId: searchParams.value.ticketId ? String(searchParams.value.ticketId) : undefined,
      returnTicketName: ticketName.value || undefined,
      returnScheduledJobId: searchParams.value.scheduledJobId ? String(searchParams.value.scheduledJobId) : undefined,
      returnScheduledJobName: scheduledJobName.value || undefined
    }
  });
}

function resetSearchParams() {
  searchParams.value = {
    ...getInitSearchParams(),
    workflowId: searchParams.value.workflowId,
    ticketId: searchParams.value.ticketId
  };
  getDataByPage();
}

function clearContextFilter() {
  router.replace({
    query: {
      ...route.query,
      workflowId: undefined,
      workflowName: undefined,
      ticketId: undefined,
      ticketName: undefined,
      scheduledJobId: undefined,
      scheduledJobName: undefined
    }
  });
}

watch(
  () => [route.name, route.query.workflowId, route.query.ticketId, route.query.scheduledJobId],
  () => {
    if (route.name !== 'task_execution-history') return;
    const context = getInitSearchParams();
    searchParams.value = {
      ...searchParams.value,
      current: 1,
      workflowId: context.workflowId,
      ticketId: context.ticketId,
      scheduledJobId: context.scheduledJobId
    };
    getDataByPage();
  }
);
</script>

<template>
  <div class="min-h-500px flex-col-stretch gap-16px overflow-hidden lt-sm:overflow-auto">
    <ElAlert v-if="searchParams.workflowId" type="info" :closable="false" show-icon>
      <template #title>模板「{{ workflowName || `#${searchParams.workflowId}` }}」的执行历史</template>
      <template #default>
        <ElButton link type="primary" @click="clearContextFilter">查看全部执行历史</ElButton>
      </template>
    </ElAlert>
    <ElAlert v-else-if="searchParams.ticketId" type="info" :closable="false" show-icon>
      <template #title>任务单「{{ ticketName || `#${searchParams.ticketId}` }}」的执行历史</template>
      <template #default>
        <ElButton link type="primary" @click="clearContextFilter">查看全部执行历史</ElButton>
      </template>
    </ElAlert>
    <ElAlert v-else-if="searchParams.scheduledJobId" type="info" :closable="false" show-icon>
      <template #title>定时任务「{{ scheduledJobName || `#${searchParams.scheduledJobId}` }}」的执行历史</template>
      <ElButton link type="primary" @click="clearContextFilter">查看全部执行历史</ElButton>
    </ElAlert>
    <SearchPanel @reset="resetSearchParams" @search="getDataByPage">
      <ElForm :model="searchParams" label-width="80px" @submit.prevent="getDataByPage">
        <ElFormItem label="触发方式">
          <ElSelect v-model="searchParams.triggerType" clearable placeholder="全部触发方式">
            <ElOption v-for="item in triggerOptions" :key="item.value" :label="item.label" :value="item.value" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem :label="$t('page.task.run.statusLabel')">
          <ElSelect v-model="searchParams.status" clearable :placeholder="$t('page.task.run.statusLabel')">
            <ElOption v-for="item in runStatusOptions" :key="item.value" :label="item.label" :value="item.value" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem :label="$t('page.task.run.executionKind')">
          <ElSelect v-model="searchParams.executionKind" clearable :placeholder="$t('page.task.run.executionKind')">
            <ElOption v-for="item in executionKindOptions" :key="item.value" :label="item.label" :value="item.value" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem :label="$t('page.task.run.runDomain')">
          <ElSelect v-model="searchParams.runDomain" clearable :placeholder="$t('page.task.run.runDomain')">
            <ElOption v-for="item in runDomainOptions" :key="item.value" :label="item.label" :value="item.value" />
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
