<script setup lang="tsx">
import { nextTick, ref } from 'vue';
import { useRouter } from 'vue-router';
import { ElButton, ElTag } from 'element-plus';
import { runStatusRecord, runStatusTagType } from '@/constants/business';
import {
  fetchDeleteTaskTicket,
  fetchGetTaskTicketList,
  fetchPreviewTaskTicket,
  fetchRunTaskTicket
} from '@/service/api';
import { defaultTransform, useUIPaginatedTable } from '@/hooks/common/table';
import { useAuth } from '@/hooks/business/auth';
import { $t } from '@/locales';
import RunPreviewDialog from '@/components/business/run-preview-dialog/index.vue';
import TicketCreateDrawer from './modules/ticket-create-drawer.vue';
import TicketDetailDrawer from './modules/ticket-detail-drawer.vue';

defineOptions({ name: 'TaskRun' });

const router = useRouter();
const { hasAuth } = useAuth();

/** ============ 任务单 ============ */

const ticketSearch = ref<Api.Jobs.TaskTicketSearchParams>({ current: 1, size: 10 });

const ticketCreateVisible = ref(false);
const ticketDetailVisible = ref(false);
/** 编辑目标；null 表示新增 */
const ticketEditTarget = ref<Api.Jobs.TaskTicketRecord | null>(null);
const ticketDetailId = ref<number | null>(null);
const ticketOperatingId = ref<number | null>(null);
const previewVisible = ref(false);
const preview = ref<Api.Jobs.RunPreview | null>(null);
const previewTicketId = ref<number | null>(null);

const {
  columns: ticketColumns,
  columnChecks: ticketColumnChecks,
  data: ticketRecords,
  loading: ticketLoading,
  getData: getTickets,
  getDataByPage: getTicketsByPage,
  mobilePagination: ticketPagination
} = useUIPaginatedTable({
  paginationProps: {
    currentPage: ticketSearch.value.current,
    pageSize: ticketSearch.value.size
  },
  api: () => fetchGetTaskTicketList(ticketSearch.value),
  transform: response => defaultTransform(response),
  onPaginationParamsChange: params => {
    ticketSearch.value.current = params.currentPage ?? 1;
    ticketSearch.value.size = params.pageSize ?? 10;
  },
  columns: () => [
    { prop: 'id', label: 'ID', width: 70, align: 'center', className: 'tabular-nums' },
    { prop: 'name', label: '任务名称', minWidth: 150, showOverflowTooltip: true },
    {
      prop: 'workflowName',
      label: '流程版本',
      minWidth: 150,
      showOverflowTooltip: true,
      formatter: row => `${row.workflowName || '-'} · v${row.workflowVersion ?? '-'}`
    },
    {
      prop: 'hostIds',
      label: '目标选择',
      minWidth: 200,
      align: 'center',
      formatter: row => `主机 ${row.hostIds.length} · 分组 ${row.groupIds.length} · 标签 ${row.tagIds.length}`
    },
    { prop: 'runCount', label: '运行次数', width: 90, align: 'center', className: 'tabular-nums' },
    {
      prop: 'lastRunStatus',
      label: '最近状态',
      width: 110,
      align: 'center',
      formatter: row =>
        row.lastRunStatus ? (
          <ElTag type={runStatusTagType[row.lastRunStatus] ?? 'info'}>{$t(runStatusRecord[row.lastRunStatus])}</ElTag>
        ) : (
          '-'
        )
    },
    {
      prop: 'lastRunStartedAt',
      label: '最近运行时间',
      width: 170,
      formatter: row => row.lastRunStartedAt || '-'
    },
    { prop: 'createdByName', label: '创建人', width: 100, formatter: row => row.createdByName || '-' },
    {
      prop: 'operate',
      label: $t('common.operate'),
      width: 200,
      align: 'center',
      fixed: 'right',
      formatter: row => (
        <div class="flex justify-center gap-4px">
          {hasAuth('jobs.workflow_ticket:run') ? (
            <ElButton
              type="primary"
              plain
              size="small"
              disabled={row.runCount > 0 && !row.workflowVersionId}
              loading={ticketOperatingId.value === row.id}
              onClick={() => onRunTicket(row)}
            >
              运行
            </ElButton>
          ) : null}
          <ElButton type="primary" plain size="small" onClick={() => openTicketDetail(row.id)}>
            {$t('common.detail')}
          </ElButton>
          {hasAuth('jobs.workflow_ticket:delete') ? (
            <ElButton type="danger" plain size="small" onClick={() => onDeleteTicket(row)}>
              {$t('common.delete')}
            </ElButton>
          ) : null}
        </div>
      )
    }
  ]
});

function resetTicketSearch() {
  ticketSearch.value = { current: 1, size: 10, search: undefined };
  getTicketsByPage();
}

function openTicketCreate() {
  ticketEditTarget.value = null;
  ticketCreateVisible.value = true;
}

function openTicketDetail(id: number) {
  ticketDetailId.value = id;
  ticketDetailVisible.value = true;
}

async function onRunTicket(row: Api.Jobs.TaskTicketRecord) {
  ticketOperatingId.value = row.id;
  try {
    const { data, error } = await fetchPreviewTaskTicket(row.id);
    if (error || !data) return;
    preview.value = data;
    previewTicketId.value = row.id;
    previewVisible.value = true;
  } finally {
    ticketOperatingId.value = null;
  }
}

async function confirmRunTicket() {
  if (!previewTicketId.value || !preview.value) return;
  ticketOperatingId.value = previewTicketId.value;
  try {
    const { data, error } = await fetchRunTaskTicket(previewTicketId.value, preview.value);
    if (!error && data) {
      previewVisible.value = false;
      window.$notification?.success('任务单已发起运行');
      getTickets();
      router.push({ name: 'task_run-detail', params: { id: data.id }, query: { domain: 'task' } });
    }
  } finally {
    ticketOperatingId.value = null;
  }
}

async function onDeleteTicket(row: Api.Jobs.TaskTicketRecord) {
  try {
    await window.$messageBox?.confirm(`确认删除任务单「${row.name}」？运行历史不受影响。`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消'
    });
  } catch {
    return;
  }
  const { error } = await fetchDeleteTaskTicket(row.id);
  if (!error) {
    window.$notification?.success('删除成功');
    getTickets();
  }
}

function onTicketSaved() {
  getTickets();
}

async function onTicketEditRequested(ticket: Api.Jobs.TaskTicketRecord) {
  ticketDetailVisible.value = false;
  await nextTick();
  ticketEditTarget.value = ticket;
  ticketCreateVisible.value = true;
}
</script>

<template>
  <div class="min-h-500px flex-col-stretch gap-16px overflow-hidden lt-sm:overflow-auto">
    <SearchPanel @reset="resetTicketSearch" @search="getTicketsByPage">
      <ElForm :model="ticketSearch" label-width="80px" @submit.prevent="getTicketsByPage">
        <ElFormItem label="关键词">
          <ElInput
            v-model="ticketSearch.search"
            clearable
            placeholder="任务名称 / 流程名称"
            @keyup.enter="getTicketsByPage()"
          />
        </ElFormItem>
      </ElForm>
    </SearchPanel>

    <ElCard class="card-wrapper sm:flex-1-hidden">
      <template #header>
        <div class="flex items-center justify-between">
          <p>任务单</p>
          <div class="flex items-center gap-8px">
            <ElButton v-if="hasAuth('jobs.workflow_ticket:create')" type="primary" @click="openTicketCreate">
              新增任务单
            </ElButton>
            <TableHeaderOperation
              v-model:columns="ticketColumnChecks"
              :loading="ticketLoading"
              :show-add="false"
              :show-batch-delete="false"
              @refresh="getTickets"
            />
          </div>
        </div>
      </template>
      <div class="h-[calc(100%-52px)]">
        <ElTable v-loading="ticketLoading" height="100%" border class="sm:h-full" :data="ticketRecords" row-key="id">
          <ElTableColumn v-for="col in ticketColumns" :key="col.prop" v-bind="col" />
        </ElTable>
      </div>
      <div class="mt-20px flex justify-end">
        <ElPagination
          v-if="ticketPagination.total"
          layout="total,prev,pager,next,sizes"
          v-bind="ticketPagination"
          @current-change="ticketPagination['current-change']"
          @size-change="ticketPagination['size-change']"
        />
      </div>
    </ElCard>

    <TicketCreateDrawer v-model:visible="ticketCreateVisible" :edit-ticket="ticketEditTarget" @saved="onTicketSaved" />
    <TicketDetailDrawer
      v-model:visible="ticketDetailVisible"
      :ticket-id="ticketDetailId"
      :can-edit="hasAuth('jobs.workflow_ticket:update')"
      @edit="onTicketEditRequested"
    />
    <RunPreviewDialog
      v-model:visible="previewVisible"
      :preview="preview"
      :loading="ticketOperatingId !== null"
      @confirm="confirmRunTicket"
    />
  </div>
</template>
