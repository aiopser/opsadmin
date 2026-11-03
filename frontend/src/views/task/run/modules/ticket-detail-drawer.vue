<script setup lang="tsx">
import { ref, shallowRef, watch } from 'vue';
import { useRouter } from 'vue-router';
import { runStatusRecord, runStatusTagType } from '@/constants/business';
import { fetchGetTaskRunList, fetchGetTaskTicket } from '@/service/api';
import { defaultTransform, useUIPaginatedTable } from '@/hooks/common/table';
import { $t } from '@/locales';

defineOptions({ name: 'TicketDetailDrawer' });

interface Props {
  visible: boolean;
  ticketId?: number | null;
  canEdit?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  ticketId: null,
  canEdit: false
});

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void;
  (e: 'edit', ticket: Api.Jobs.TaskTicketRecord): void;
}>();

const router = useRouter();

/** ============ 详情数据 ============ */

const ticket = shallowRef<Api.Jobs.TaskTicketRecord | null>(null);
const detailLoading = ref(false);

const strategyRecord: Record<string, string> = {
  parallel: '并行',
  serial: '串行',
  rolling: '滚动'
};

async function loadTicket() {
  if (!props.ticketId) return;
  detailLoading.value = true;
  try {
    const { data, error } = await fetchGetTaskTicket(props.ticketId);
    if (!error && data) {
      ticket.value = data;
    }
  } finally {
    detailLoading.value = false;
  }
}

/** ============ 运行历史 ============ */

const runSearchParams = ref({ current: 1, size: 5 });

const {
  columns: runColumns,
  data: runRecords,
  loading: runLoading,
  getDataByPage: getRunsByPage
} = useUIPaginatedTable({
  paginationProps: {
    currentPage: runSearchParams.value.current,
    pageSize: runSearchParams.value.size
  },
  api: () => fetchGetTaskRunList({ ...runSearchParams.value, ticketId: props.ticketId }),
  transform: response => defaultTransform(response),
  onPaginationParamsChange: params => {
    runSearchParams.value.current = params.currentPage ?? 1;
    runSearchParams.value.size = params.pageSize ?? 5;
  },
  columns: () => [
    { prop: 'id', label: $t('page.task.run.id'), width: 80, align: 'center', className: 'tabular-nums' },
    {
      prop: 'status',
      label: $t('page.task.run.statusLabel'),
      width: 110,
      align: 'center',
      formatter: row => <ElTag type={runStatusTagType[row.status] ?? 'info'}>{$t(runStatusRecord[row.status])}</ElTag>
    },
    { prop: 'triggeredByName', label: $t('page.task.run.triggeredBy'), width: 110 },
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
      width: 80,
      align: 'center',
      formatter: row => (
        <ElButton type="primary" plain size="small" onClick={() => goRunDetail(row.id)}>
          {$t('common.detail')}
        </ElButton>
      )
    }
  ]
});

function goRunDetail(id: number) {
  router.push({
    name: 'task_run-detail',
    params: { id },
    query: {
      domain: 'task',
      returnTicketId: props.ticketId ? String(props.ticketId) : undefined,
      returnTicketName: ticket.value?.name
    }
  });
}

function viewAllRunHistory() {
  router.push({
    name: 'task_execution-history',
    query: {
      ticketId: props.ticketId ? String(props.ticketId) : undefined,
      ticketName: ticket.value?.name
    }
  });
}

function formatTime(value: string | null) {
  return value || '-';
}

function handleClose() {
  emit('update:visible', false);
}

/** 打开抽屉：加载详情与运行历史 */
watch(
  () => props.visible,
  visible => {
    if (!visible) return;
    ticket.value = null;
    runSearchParams.value = { current: 1, size: 5 };
    loadTicket();
    getRunsByPage();
  }
);
</script>

<template>
  <ElDrawer
    :model-value="visible"
    title="任务单详情"
    size="720px"
    :close-on-click-modal="false"
    @update:model-value="handleClose"
  >
    <div v-loading="detailLoading" class="flex flex-col gap-16px">
      <div v-if="ticket" class="flex flex-col gap-16px">
        <div class="flex items-center justify-between">
          <div class="text-16px font-600">{{ ticket.name }}</div>
          <div class="flex items-center gap-8px">
            <ElButton v-if="canEdit" plain @click="emit('edit', ticket)">编辑任务单</ElButton>
          </div>
        </div>

        <ElDescriptions :column="2" border>
          <ElDescriptionsItem label="流程版本">
            {{ ticket.workflowName || '-' }} · v{{ ticket.workflowVersion ?? '-' }}
          </ElDescriptionsItem>
          <ElDescriptionsItem label="目标选择">
            主机 {{ ticket.hostIds.length }} · 分组 {{ ticket.groupIds.length }} · 标签 {{ ticket.tagIds.length }}
          </ElDescriptionsItem>
          <ElDescriptionsItem label="执行策略">
            {{ ticket.hostStrategy ? strategyRecord[ticket.hostStrategy] : '继承全局' }}
          </ElDescriptionsItem>
          <ElDescriptionsItem label="执行节点池">{{ ticket.workerPoolName || '-' }}</ElDescriptionsItem>
          <ElDescriptionsItem label="连接网关">{{ ticket.gatewayName || '-' }}</ElDescriptionsItem>
          <ElDescriptionsItem label="并发数">{{ ticket.forks ?? '继承全局' }}</ElDescriptionsItem>
          <ElDescriptionsItem label="整个流程超时（秒）">{{ ticket.timeoutSeconds ?? '继承全局' }}</ElDescriptionsItem>
          <ElDescriptionsItem label="运行次数">{{ ticket.runCount }}</ElDescriptionsItem>
          <ElDescriptionsItem label="最近状态">
            <ElTag v-if="ticket.lastRunStatus" :type="runStatusTagType[ticket.lastRunStatus] ?? 'info'">
              {{ $t(runStatusRecord[ticket.lastRunStatus]) }}
            </ElTag>
            <span v-else>-</span>
          </ElDescriptionsItem>
          <ElDescriptionsItem label="最近运行时间">{{ formatTime(ticket.lastRunStartedAt) }}</ElDescriptionsItem>
          <ElDescriptionsItem label="创建人">{{ ticket.createdByName || '-' }}</ElDescriptionsItem>
          <ElDescriptionsItem label="备注">{{ ticket.remark || '-' }}</ElDescriptionsItem>
        </ElDescriptions>

        <div class="flex items-center justify-between">
          <span class="text-14px font-600">最近运行记录</span>
          <ElButton link type="primary" @click="viewAllRunHistory">查看全部执行历史</ElButton>
        </div>
        <ElTable v-loading="runLoading" border :data="runRecords" row-key="id">
          <ElTableColumn v-for="col in runColumns" :key="col.prop" v-bind="col" />
        </ElTable>
      </div>
      <ElEmpty v-else-if="!detailLoading" description="未选择任务" />
    </div>
  </ElDrawer>
</template>
