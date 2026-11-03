<script setup lang="tsx">
import { computed, onScopeDispose, ref, shallowRef, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useClipboard } from '@vueuse/core';
import {
  executionKindRecord,
  nodeStatusRecord,
  runStatusRecord,
  runStatusTagType,
  triggerTypeLabels
} from '@/constants/business';
import {
  fetchCancelRun,
  fetchGetHostResultDetail,
  fetchGetNodeHostResults,
  fetchGetRunDetail,
  fetchGetRunNodes,
  fetchRerunRun,
  fetchRetryFailedRun,
  fetchRunLogFile
} from '@/service/api';
import { useAuth } from '@/hooks/business/auth';
import { useRunEventStream } from '@/hooks/business/run-event-stream';
import { $t } from '@/locales';
import AnsiConsole from './ansi-console.vue';

defineOptions({ name: 'TaskRunDetail' });

const route = useRoute();
const router = useRouter();
const { hasAuth } = useAuth();
const domain = computed<Api.Jobs.RunDomain>(() =>
  route.name === 'ops_run-detail' || route.query.domain === 'ops' ? 'ops' : 'task'
);
const historyRouteName = computed(() => (domain.value === 'ops' ? 'ops_history' : 'task_execution-history'));
let requestScope = new AbortController();
let runRequestId = 0;
let nodesRequestId = 0;

const runId = computed(() => {
  const parsed = Number(route.params.id);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
});

/** ============ 运行基础信息 ============ */

const run = shallowRef<Api.Jobs.RunRecord | null>(null);

async function loadRun() {
  if (runId.value === null) return;
  const scope = requestScope;
  runRequestId += 1;
  const requestId = runRequestId;
  const { data, error } = await fetchGetRunDetail(runId.value, domain.value, requestScope.signal);
  if (scope === requestScope && !scope.signal.aborted && requestId === runRequestId && !error && data) {
    run.value = data;
  }
}

const permissionPrefix = computed(() => (domain.value === 'ops' ? 'ops' : 'jobs'));
const mayRetry = computed(() => hasAuth(`${permissionPrefix.value}.workflow_run:retry`));
const activeStatuses = new Set<Api.Jobs.RunStatus>(['pending', 'queued', 'running', 'waiting', 'cancel_requested']);
const finishedStatuses = new Set<Api.Jobs.RunStatus>(['success', 'failed', 'timeout', 'canceled']);

const canCancel = computed(() =>
  Boolean(run.value && activeStatuses.has(run.value.status) && hasAuth(`${permissionPrefix.value}.workflow_run:cancel`))
);
const canRetry = computed(() => run.value?.status === 'failed' && mayRetry.value);
const canRerun = computed(() => Boolean(run.value && finishedStatuses.has(run.value.status) && mayRetry.value));
const hostExecutionTypes = new Set(['command', 'script', 'playbook', 'module']);

/** ============ 事件流（T14 同步协议） ============ */

const { events, terminal, connected, transportError } = useRunEventStream(runId, domain);

/** ============ 节点状态 ============ */

const nodes = shallowRef<Api.Jobs.NodeRunRecord[]>([]);
const nodesLoading = ref(false);
const executionNodes = computed(() =>
  nodes.value.filter(node => !['start', 'end', 'parallel_gateway', 'parallel_join'].includes(node.nodeType))
);
const finishedNodeStatuses = new Set<Api.Jobs.NodeStatus>([
  'success',
  'failed',
  'skipped',
  'ignored',
  'timeout',
  'canceled'
]);
const runProgress = computed(() => {
  if (!run.value) return 0;
  const completed = executionNodes.value.filter(node => finishedNodeStatuses.has(node.status)).length;
  if (!executionNodes.value.length) return finishedStatuses.has(run.value.status) ? 100 : 0;
  return Math.round((completed / executionNodes.value.length) * 100);
});

const selectedNodeId = ref<number | null>(null);
const selectedNode = computed(() => executionNodes.value.find(node => node.id === selectedNodeId.value) ?? null);
const followExecution = ref(true);
const completedStepCount = computed(
  () => executionNodes.value.filter(node => finishedNodeStatuses.has(node.status)).length
);
const firstFailedStep = computed(() => executionNodes.value.find(node => isFailedNode(node.status)) ?? null);
const hostResultsLoading = ref(false);
const hostResults = shallowRef<Api.Jobs.HostResultSummary[]>([]);
const hostResultSummary = shallowRef({ total: 0, success: 0, failed: 0 });
const hostResultTotal = ref(0);
const hostPage = ref(1);
const hostPageSize = ref(20);
const hostSearchInput = ref('');
const hostSearch = ref('');
const hostDrawerVisible = ref(false);
const hostOutputLoading = ref(false);
const hostResultNode = shallowRef<Api.Jobs.NodeRunRecord | null>(null);
const selectedHostResult = shallowRef<Api.Jobs.HostResultRecord | null>(null);
const hostResultFilter = ref<'all' | 'failed' | 'success'>('all');
const expandedHostOutput = ref(['host-output']);
const expandedStepConsole = ref(['step-console']);
const outputTab = ref<'stdout' | 'stderr'>('stdout');
let hostRefreshTimer: ReturnType<typeof setTimeout> | null = null;
let hostResultsRequestId = 0;
let hostDetailRequestId = 0;

function selectNode(node: Api.Jobs.NodeRunRecord, manual = false) {
  if (manual) followExecution.value = false;
  if (selectedNodeId.value === node.id) return;
  hostResultsRequestId += 1;
  if (hostRefreshTimer) clearTimeout(hostRefreshTimer);
  hostRefreshTimer = null;
  selectedNodeId.value = node.id;
  expandedStepConsole.value = ['step-console'];
  hostResultFilter.value = 'all';
  hostPage.value = 1;
  hostSearchInput.value = '';
  hostSearch.value = '';
  hostDrawerVisible.value = false;
  hostResults.value = [];
  selectedHostResult.value = null;
  hostOutputLoading.value = false;
  hostResultSummary.value = { total: 0, success: 0, failed: 0 };
  hostResultTotal.value = 0;
  hostDetailRequestId += 1;
  if (isHostExecution(node.nodeType)) {
    loadHostResults(node);
  } else {
    hostResults.value = [];
    hostResultNode.value = null;
  }
}

function followTarget(nodesToShow: Api.Jobs.NodeRunRecord[]): Api.Jobs.NodeRunRecord | undefined {
  if (run.value && finishedStatuses.has(run.value.status)) {
    return nodesToShow.find(node => isFailedNode(node.status)) ?? nodesToShow.at(-1);
  }
  const activeNode = nodesToShow.find(node => node.status === 'running' || node.status === 'queued');
  if (activeNode) return activeNode;
  return (
    nodesToShow.find(node => node.status === 'pending') ??
    nodesToShow.find(node => isFailedNode(node.status)) ??
    nodesToShow.at(-1)
  );
}

function handleFollowChange() {
  if (!followExecution.value) return;
  const target = followTarget(executionNodes.value);
  if (target) selectNode(target);
}

function scheduleHostResultsRefresh(node: Api.Jobs.NodeRunRecord) {
  if (hostRefreshTimer) return;
  hostRefreshTimer = setTimeout(() => {
    hostRefreshTimer = null;
    if (selectedNodeId.value === node.id && !requestScope.signal.aborted) loadHostResults(node);
  }, 800);
}

function focusFailedStep() {
  if (firstFailedStep.value) selectNode(firstFailedStep.value, true);
}

async function loadNodes() {
  if (runId.value === null) return;
  const scope = requestScope;
  nodesRequestId += 1;
  const requestId = nodesRequestId;
  nodesLoading.value = true;
  try {
    const { data, error } = await fetchGetRunNodes(runId.value, domain.value, requestScope.signal);
    if (scope === requestScope && !scope.signal.aborted && requestId === nodesRequestId && !error && data) {
      nodes.value = data;
      const visibleNodes = data.filter(
        node => !['start', 'end', 'parallel_gateway', 'parallel_join'].includes(node.nodeType)
      );
      const previousSelectedId = selectedNodeId.value;
      if (followExecution.value || !visibleNodes.some(node => node.id === selectedNodeId.value)) {
        const target = followTarget(visibleNodes);
        if (target && selectedNodeId.value !== target.id) selectNode(target);
      }
      if (selectedNodeId.value === previousSelectedId && selectedNodeId.value !== null) {
        const current = visibleNodes.find(node => node.id === selectedNodeId.value);
        if (current && isHostExecution(current.nodeType)) scheduleHostResultsRefresh(current);
      }
    }
  } finally {
    if (scope === requestScope && requestId === nodesRequestId) nodesLoading.value = false;
  }
}

function nodeStatusLabel(status: string): string {
  return $t(nodeStatusRecord[status as Api.Jobs.NodeStatus]);
}

/** ============ 当前步骤的主机结果与输出 ============ */

const showHostAddressColumn = computed(() => hostResults.value.some(row => row.ip && row.ip !== row.hostname));

function isCurrentHostResultsRequest(scope: AbortController, requestId: number, nodeId: number): boolean {
  return (
    scope === requestScope &&
    !scope.signal.aborted &&
    requestId === hostResultsRequestId &&
    hostResultNode.value?.id === nodeId
  );
}

async function loadHostResults(node: Api.Jobs.NodeRunRecord) {
  const scope = requestScope;
  hostResultsRequestId += 1;
  const requestId = hostResultsRequestId;
  hostResultNode.value = node;
  hostResultsLoading.value = true;
  try {
    const { data, error } = await fetchGetNodeHostResults(
      node.id,
      { current: hostPage.value, size: hostPageSize.value, status: hostResultFilter.value, search: hostSearch.value },
      scope.signal
    );
    if (!isCurrentHostResultsRequest(scope, requestId, node.id) || error || !data) return;
    hostResults.value = data.records;
    hostResultSummary.value = data.summary;
    hostResultTotal.value = data.total;
    if (selectedHostResult.value && !data.records.some(row => row.id === selectedHostResult.value?.id)) {
      selectedHostResult.value = null;
    }
  } finally {
    if (isCurrentHostResultsRequest(scope, requestId, node.id)) hostResultsLoading.value = false;
  }
}

async function showHostOutput(row: Api.Jobs.HostResultSummary) {
  const scope = requestScope;
  const nodeId = hostResultNode.value?.id;
  hostDetailRequestId += 1;
  const requestId = hostDetailRequestId;
  selectedHostResult.value = null;
  hostOutputLoading.value = true;
  try {
    const { data, error } = await fetchGetHostResultDetail(row.id, scope.signal);
    if (scope !== requestScope || scope.signal.aborted || requestId !== hostDetailRequestId || error || !data) return;
    if (nodeId !== hostResultNode.value?.id || data.nodeRun !== nodeId) return;
    selectedHostResult.value = data;
    outputTab.value = isFailedHostResult(data) && data.stderr ? 'stderr' : 'stdout';
  } finally {
    if (requestId === hostDetailRequestId) hostOutputLoading.value = false;
  }
}

function isFailedHostResult(row: Api.Jobs.HostResultRecord | null): boolean {
  return row?.status === 'failed' || row?.status === 'unreachable';
}

function setHostResultFilter(value: 'all' | 'failed' | 'success') {
  if (hostResultFilter.value === value) return;
  hostResultFilter.value = value;
  hostPage.value = 1;
  selectedHostResult.value = null;
  hostDetailRequestId += 1;
  hostOutputLoading.value = false;
  if (hostResultNode.value) loadHostResults(hostResultNode.value);
}

function searchHostResults() {
  hostSearch.value = hostSearchInput.value.trim();
  hostPage.value = 1;
  selectedHostResult.value = null;
  hostDetailRequestId += 1;
  hostOutputLoading.value = false;
  if (hostResultNode.value) loadHostResults(hostResultNode.value);
}

function changeHostPage(page: number) {
  hostPage.value = page;
  selectedHostResult.value = null;
  hostDetailRequestId += 1;
  hostOutputLoading.value = false;
  if (hostResultNode.value) loadHostResults(hostResultNode.value);
}

function changeHostPageSize(size: number) {
  hostPageSize.value = size;
  changeHostPage(1);
}

function openHostResults() {
  followExecution.value = false;
  hostDrawerVisible.value = true;
  if (hostResultSummary.value.failed > 0 && hostResultFilter.value === 'all') {
    setHostResultFilter('failed');
  }
}

function setOutputTab(value: 'stdout' | 'stderr') {
  outputTab.value = value;
}

/** ============ 控制台日志复制 ============ */

const { copy: copyToClipboard, isSupported: clipboardSupported } = useClipboard({ copiedDuring: 1500 });

/** 日志行数（用于控制台标题角标） */
function consoleLineCount(text: string | null | undefined): number {
  return text ? text.split('\n').length : 0;
}

async function copyConsoleLog() {
  const text = selectedNode.value?.consoleOutput;
  if (!text) return;
  if (!clipboardSupported.value) {
    window.$message?.warning('当前浏览器不支持一键复制');
    return;
  }
  await copyToClipboard(text);
  window.$notification?.success(`已复制 ${consoleLineCount(text)} 行日志`);
}

function isHostExecution(nodeType: string): boolean {
  return hostExecutionTypes.has(nodeType);
}

function nodeDuration(node: Api.Jobs.NodeRunRecord): string {
  return formatDuration(node.durationMs);
}

/** 时长人性化：1 秒内保留一位小数，1 分钟以上显示「X分Y秒」 */
function formatDuration(ms: number | null): string {
  if (ms === null) return '-';
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
  const minutes = Math.floor(ms / 60_000);
  const seconds = Math.round((ms % 60_000) / 1000);
  return seconds ? `${minutes}分${seconds}秒` : `${minutes}分`;
}

/** 节点类型 → 中文（未收录显示原文） */
const NODE_TYPE_LABELS: Record<string, string> = {
  playbook: '剧本',
  command: '命令',
  script: '脚本',
  module: '模块',
  shell: 'Shell 命令'
};

function nodeTypeLabel(nodeType: string): string {
  return NODE_TYPE_LABELS[nodeType] ?? nodeType;
}

/** 主机结果状态 → 中文（与执行详情抽屉「成功(有变更)」语义一致） */
const HOST_STATUS_LABELS: Record<string, string> = {
  pending: '等待',
  running: '执行中',
  ok: '成功',
  changed: '成功(有变更)',
  failed: '失败',
  unreachable: '不可达',
  canceled: '已取消',
  skipped: '已跳过'
};

function hostStatusLabel(status: string): string {
  return HOST_STATUS_LABELS[status] ?? status;
}

function isFailedNode(status: string): boolean {
  return status === 'failed' || status === 'timeout';
}

/** 主机耗时：HostResultRecord 无 durationMs，由开始/结束时间计算 */
function hostDuration(row: Pick<Api.Jobs.HostResultRecord, 'startedAt' | 'finishedAt'>): string {
  if (!row.startedAt || !row.finishedAt) return '-';
  const ms = new Date(row.finishedAt).getTime() - new Date(row.startedAt).getTime();
  return ms >= 0 ? formatDuration(ms) : '-';
}

/** 触发方式 → 中文 */
function triggerTypeLabel(type: Api.Jobs.TriggerType): string {
  return triggerTypeLabels[type] ?? type;
}

/** 步骤/主机状态文字颜色 class（对齐原型：绿成功、红失败、蓝等待） */
function stateClass(status: string): string {
  if (status === 'success' || status === 'ok' || status === 'changed') return 'state-ok';
  if (status === 'failed' || status === 'timeout' || status === 'unreachable') return 'state-fail';
  return 'state-wait';
}

function backToHistory() {
  router.push({
    name: historyRouteName.value,
    query:
      domain.value === 'ops'
        ? {}
        : {
            workflowId: route.query.returnWorkflowId,
            workflowName: route.query.returnWorkflowName,
            ticketId: route.query.returnTicketId,
            ticketName: route.query.returnTicketName,
            scheduledJobId: route.query.returnScheduledJobId,
            scheduledJobName: route.query.returnScheduledJobName
          }
  });
}

function openRunDetail(id: number) {
  router.push({
    name: domain.value === 'ops' ? 'ops_run-detail' : 'task_run-detail',
    params: { id },
    query: {
      domain: domain.value,
      returnWorkflowId: route.query.returnWorkflowId,
      returnWorkflowName: route.query.returnWorkflowName,
      returnTicketId: route.query.returnTicketId,
      returnTicketName: route.query.returnTicketName,
      returnScheduledJobId: route.query.returnScheduledJobId,
      returnScheduledJobName: route.query.returnScheduledJobName
    }
  });
}

/** ============ 操作 ============ */

const operating = ref(false);

async function onCancel() {
  if (runId.value === null || operating.value) return;
  const id = runId.value;
  const runDomain = domain.value;
  const scope = requestScope;
  operating.value = true;
  try {
    try {
      await window.$messageBox?.confirm(
        '确认取消本次运行？涉及 Jenkins 时，取消将停止本平台等待；已触发的 Jenkins 构建可能继续运行。',
        '取消运行',
        { type: 'warning', confirmButtonText: '确认取消', cancelButtonText: '继续等待' }
      );
    } catch {
      return;
    }
    if (scope !== requestScope || scope.signal?.aborted || runId.value !== id || domain.value !== runDomain) return;
    const { error } = await fetchCancelRun(id, runDomain, scope.signal);
    if (!error) {
      window.$notification?.success($t('common.updateSuccess'));
      await Promise.all([loadRun(), loadNodes()]);
    }
  } finally {
    operating.value = false;
  }
}

async function onRetry() {
  if (runId.value === null) return;
  operating.value = true;
  try {
    const { data, error } = await fetchRetryFailedRun(runId.value, domain.value, requestScope.signal);
    if (!error && data) {
      window.$notification?.success($t('page.task.run.retryCreated'));
      openRunDetail(data.id);
    }
  } finally {
    operating.value = false;
  }
}

async function onRerun() {
  if (runId.value === null) return;
  operating.value = true;
  try {
    const { data, error } = await fetchRerunRun(runId.value, domain.value, requestScope.signal);
    if (!error && data) {
      window.$notification?.success($t('page.task.run.retryCreated'));
      openRunDetail(data.id);
    }
  } finally {
    operating.value = false;
  }
}

async function onDownloadLog() {
  if (runId.value === null) return;
  const result = await fetchRunLogFile(runId.value, domain.value, requestScope.signal);
  if (!result) return;
  const url = URL.createObjectURL(result.blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `run-${runId.value}.log`;
  link.click();
  URL.revokeObjectURL(url);
  if (result.truncated) {
    window.$message?.warning($t('page.task.run.logTruncated'));
  }
}

function onMoreCommand(command: string) {
  if (command === 'rerun') onRerun();
  if (command === 'download') onDownloadLog();
  if (command === 'refresh') refresh();
}

watch(
  () => events.value.at(-1)?.sequence,
  async () => {
    await Promise.all([loadRun(), loadNodes()]);
  },
  { flush: 'post' }
);

/** 终态时最后刷新一次全量状态 */
watch(terminal, async finished => {
  if (finished) {
    await Promise.all([loadRun(), loadNodes()]);
  }
});

function refresh() {
  Promise.all([loadRun(), loadNodes()]);
}

watch(
  [runId, domain],
  () => {
    requestScope.abort();
    requestScope = new AbortController();
    runRequestId += 1;
    nodesRequestId += 1;
    run.value = null;
    nodes.value = [];
    nodesLoading.value = false;
    selectedNodeId.value = null;
    followExecution.value = true;
    hostResults.value = [];
    hostResultSummary.value = { total: 0, success: 0, failed: 0 };
    hostResultTotal.value = 0;
    hostResultsLoading.value = false;
    hostOutputLoading.value = false;
    selectedHostResult.value = null;
    hostResultNode.value = null;
    hostResultsRequestId += 1;
    hostDetailRequestId += 1;
    hostDrawerVisible.value = false;
    hostPage.value = 1;
    hostResultFilter.value = 'all';
    hostSearch.value = '';
    hostSearchInput.value = '';
    if (hostRefreshTimer) clearTimeout(hostRefreshTimer);
    hostRefreshTimer = null;
    refresh();
  },
  { immediate: true }
);
onScopeDispose(() => {
  requestScope.abort();
  if (hostRefreshTimer) clearTimeout(hostRefreshTimer);
});
</script>

<template>
  <div class="min-h-500px flex-col-stretch gap-16px overflow-y-auto">
    <ElCard class="shrink-0 card-wrapper">
      <template v-if="run">
        <div class="flex flex-wrap items-start justify-between gap-16px">
          <div class="min-w-0">
            <div class="flex flex-wrap items-center gap-10px">
              <h1 class="run-title">{{ run.name || run.workflowName || `运行 #${run.id}` }}</h1>
              <ElTag :type="runStatusTagType[run.status] ?? 'info'" size="large">
                {{ $t(runStatusRecord[run.status]) }}
              </ElTag>
              <span class="text-13px text-gray-500">#{{ run.id }}</span>
            </div>
            <div class="run-subtitle mt-8px">
              <span v-if="run.executionKind === 'workflow' && run.workflowName && run.workflowName !== run.name">
                流程「{{ run.workflowName }}」:
                <template v-if="run.workflowVersion">v{{ run.workflowVersion }}</template>
              </span>
              <span v-else-if="run.executionKind === 'workflow' && run.workflowVersion">
                流程版本 v{{ run.workflowVersion }}
              </span>
              <span>{{ $t(executionKindRecord[run.executionKind]) }} · {{ triggerTypeLabel(run.triggerType) }}</span>
              <span v-if="run.scheduledJobName">定时任务：{{ run.scheduledJobName }}</span>
              <span>发起人：{{ run.triggeredByName || '-' }}</span>
              <span v-if="!terminal && connected" class="text-success">● {{ $t('page.task.detail.live') }}</span>
              <span v-else-if="!terminal && transportError">{{ $t('page.task.detail.fallback') }}</span>
            </div>
          </div>
          <div class="run-actions flex flex-wrap items-center gap-8px">
            <ElButton @click="backToHistory">返回{{ domain === 'ops' ? '作业历史' : '执行历史' }}</ElButton>
            <ElTooltip v-if="canRetry" :content="$t('page.task.run.snapshotExecutionHint')" placement="bottom">
              <ElButton type="primary" :loading="operating" @click="onRetry">{{ $t('page.task.run.retry') }}</ElButton>
            </ElTooltip>
            <ElButton v-if="canCancel" type="warning" plain :loading="operating" @click="onCancel">
              {{ $t('page.task.run.cancel') }}
            </ElButton>
            <ElDropdown trigger="click" @command="onMoreCommand">
              <ElButton>
                更多
                <icon-ep-arrow-down class="ml-4px text-icon" />
              </ElButton>
              <template #dropdown>
                <ElDropdownMenu>
                  <ElDropdownItem v-if="canRerun" command="rerun">{{ $t('page.task.run.rerun') }}</ElDropdownItem>
                  <ElDropdownItem command="download">{{ $t('page.task.run.log') }}</ElDropdownItem>
                  <ElDropdownItem command="refresh">{{ $t('common.refresh') }}</ElDropdownItem>
                </ElDropdownMenu>
              </template>
            </ElDropdown>
          </div>
        </div>
        <ElProgress
          class="mt-20px"
          :percentage="runProgress"
          :show-text="false"
          :status="
            run.status === 'failed' || run.status === 'timeout'
              ? 'exception'
              : run.status === 'success'
                ? 'success'
                : undefined
          "
          :stroke-width="7"
        />
        <div class="run-summary mt-18px">
          <div class="run-summary-item">
            <span>执行步骤</span>
            <strong>
              {{ completedStepCount }} / {{ executionNodes.length }}
              <span class="run-summary-unit">已结束</span>
            </strong>
          </div>
          <div class="run-summary-item">
            <span>目标主机</span>
            <strong>
              {{ run.targetCount }}
              <span class="run-summary-unit">台</span>
            </strong>
          </div>
          <div class="run-summary-item">
            <span>失败主机</span>
            <strong :class="{ 'text-error': (run.failedHostCount ?? 0) > 0 }">
              {{ run.failedHostCount ?? 0 }}
              <span class="run-summary-unit">台</span>
            </strong>
          </div>
          <div class="run-summary-item">
            <span>开始时间</span>
            <strong>{{ run.startedAt || '-' }}</strong>
          </div>
          <div class="run-summary-item">
            <span>总耗时</span>
            <strong>{{ formatDuration(run.durationMs) }}</strong>
          </div>
          <div class="run-summary-item">
            <span>执行节点池</span>
            <strong>{{ run.workerPoolName || '-' }}</strong>
          </div>
        </div>
        <ElAlert v-if="firstFailedStep" class="mt-18px" type="error" :closable="false" show-icon>
          <template #title>
            <span>步骤「{{ firstFailedStep.nodeName || firstFailedStep.nodeKey }}」执行失败</span>
            <ElButton link type="danger" class="ml-8px" @click="focusFailedStep">定位失败步骤</ElButton>
          </template>
          <span v-if="run.failureReason">{{ run.failureReason }}</span>
        </ElAlert>
        <ElAlert
          v-else-if="run.failureReason"
          class="mt-18px"
          type="error"
          :title="run.failureReason"
          :closable="false"
          show-icon
        />
      </template>
      <ElSkeleton v-else :rows="4" animated />
    </ElCard>

    <div class="run-workspace">
      <ElCard class="run-steps-panel card-wrapper">
        <template #header>
          <div class="flex items-center justify-between">
            <strong class="run-section-title">执行步骤</strong>
            <div class="flex items-center gap-10px">
              <span class="text-12px text-gray-500">共 {{ executionNodes.length }} 步</span>
              <template v-if="run && activeStatuses.has(run.status)">
                <span class="text-12px text-gray-500">自动跟随</span>
                <ElSwitch
                  v-model="followExecution"
                  size="small"
                  aria-label="自动跟随执行步骤"
                  @change="handleFollowChange"
                />
              </template>
            </div>
          </div>
        </template>
        <ElSkeleton v-if="nodesLoading && !nodes.length" :rows="4" animated />
        <ElEmpty v-else-if="!executionNodes.length" description="暂无步骤运行记录" :image-size="72" />
        <div v-else class="run-step-list">
          <button
            v-for="(node, index) in executionNodes"
            :key="node.id"
            type="button"
            class="run-step-button"
            :class="{ 'is-selected': selectedNodeId === node.id, 'is-failed': isFailedNode(node.status) }"
            :aria-current="selectedNodeId === node.id ? 'step' : undefined"
            @click="selectNode(node, true)"
          >
            <span class="run-step-number" :class="stateClass(node.status)">
              {{ index + 1 }}
            </span>
            <span class="min-w-0 flex-1 text-left">
              <span class="flex items-center justify-between gap-8px">
                <strong class="truncate">{{ node.nodeName || node.nodeKey }}</strong>
                <span class="shrink-0 text-12px" :class="stateClass(node.status)">
                  {{ node.status === 'skipped' && node.failureReason ? '未执行' : nodeStatusLabel(node.status) }}
                </span>
              </span>
              <span class="run-step-description">{{ nodeTypeLabel(node.nodeType) }} · {{ nodeDuration(node) }}</span>
            </span>
          </button>
        </div>
      </ElCard>

      <ElCard class="run-result-panel card-wrapper">
        <Transition name="run-step-panel" mode="out-in">
          <div v-if="selectedNode" :key="selectedNode.id">
            <div class="min-w-0">
              <h2 class="m-0 text-16px font-500">
                步骤 {{ executionNodes.findIndex(node => node.id === selectedNode?.id) + 1 }} ·
                {{ selectedNode.nodeName || selectedNode.nodeKey }}
              </h2>
            </div>
            <div class="run-step-diagnostics mt-10px flex flex-wrap gap-x-20px gap-y-6px">
              <span>
                耗时
                <strong>{{ nodeDuration(selectedNode) }}</strong>
              </span>
              <span>
                开始
                <strong>{{ selectedNode.startedAt || '-' }}</strong>
              </span>
              <span>
                结束
                <strong>{{ selectedNode.finishedAt || '-' }}</strong>
              </span>
              <span>
                尝试
                <strong>{{ selectedNode.attemptCount }} 次</strong>
              </span>
              <span v-if="!isHostExecution(selectedNode.nodeType) || !hostResultSummary.total">
                退出码
                <strong>{{ selectedNode.exitCode ?? '-' }}</strong>
              </span>
            </div>
            <ElAlert
              v-if="selectedNode.failureReason"
              class="mt-16px"
              :type="selectedNode.status === 'skipped' ? 'info' : 'error'"
              :title="selectedNode.failureReason"
              :closable="false"
              show-icon
            />
            <div v-if="isHostExecution(selectedNode.nodeType)" class="mt-16px">
              <div
                v-if="hostResultSummary.total"
                class="run-host-overview flex flex-wrap items-center justify-between gap-12px"
              >
                <div class="flex flex-wrap items-center gap-x-12px gap-y-6px text-13px">
                  <span class="run-section-title">主机执行结果</span>
                  <span class="text-12px text-gray-500">共 {{ hostResultSummary.total }} 台</span>
                  <span class="run-host-chip">
                    <span class="run-host-dot state-ok" aria-hidden="true"></span>
                    成功 {{ hostResultSummary.success }}
                  </span>
                  <span class="run-host-chip" :class="{ 'is-alert': hostResultSummary.failed > 0 }">
                    <span
                      class="run-host-dot"
                      :class="hostResultSummary.failed > 0 ? 'state-fail' : ''"
                      aria-hidden="true"
                    ></span>
                    失败 {{ hostResultSummary.failed }}
                  </span>
                </div>
                <ElButton :loading="hostResultsLoading" @click="openHostResults">查看主机结果</ElButton>
              </div>
              <p v-else class="m-0 text-13px text-gray-500">
                {{
                  isFailedNode(selectedNode.status)
                    ? '步骤在连接主机前失败，暂无主机执行结果。请检查上方错误信息。'
                    : '尚未收到主机执行结果'
                }}
              </p>
              <ElCollapse
                v-if="selectedNode.consoleOutput"
                v-model="expandedStepConsole"
                class="advanced-collapse run-detail-collapse mt-16px"
              >
                <ElCollapseItem name="step-console">
                  <template #title>
                    <div class="min-w-0 flex flex-1 items-center justify-between gap-8px">
                      <span class="flex items-center gap-8px">
                        步骤控制台输出
                        <span v-if="consoleLineCount(selectedNode.consoleOutput)" class="text-12px text-gray-500">
                          {{ consoleLineCount(selectedNode.consoleOutput) }} 行
                        </span>
                      </span>
                      <ElButton size="small" link :disabled="!selectedNode.consoleOutput" @click.stop="copyConsoleLog">
                        复制日志
                      </ElButton>
                    </div>
                  </template>
                  <AnsiConsole :text="selectedNode.consoleOutput" />
                </ElCollapseItem>
              </ElCollapse>
            </div>
            <div v-else class="mt-20px">
              <ElCollapse v-model="expandedStepConsole" class="advanced-collapse run-detail-collapse">
                <ElCollapseItem name="step-console">
                  <template #title>
                    <div class="min-w-0 flex flex-1 items-center justify-between gap-8px">
                      <span class="flex items-center gap-8px">
                        步骤控制台输出
                        <span v-if="consoleLineCount(selectedNode.consoleOutput)" class="text-12px text-gray-500">
                          {{ consoleLineCount(selectedNode.consoleOutput) }} 行
                        </span>
                      </span>
                      <ElButton size="small" link :disabled="!selectedNode.consoleOutput" @click.stop="copyConsoleLog">
                        复制日志
                      </ElButton>
                    </div>
                  </template>
                  <AnsiConsole :text="selectedNode.consoleOutput || '此步骤暂无控制台输出'" />
                </ElCollapseItem>
              </ElCollapse>
            </div>
          </div>
          <ElEmpty v-else description="选择左侧步骤查看执行结果" :image-size="72" />
        </Transition>
      </ElCard>
    </div>
    <ElDrawer
      v-model="hostDrawerVisible"
      :title="`主机执行结果 · ${selectedNode?.nodeName || selectedNode?.nodeKey || ''}`"
      size="min(960px, 100%)"
    >
      <div class="flex flex-col gap-16px">
        <div class="flex flex-wrap items-center justify-between gap-12px">
          <div class="flex flex-wrap items-center gap-x-12px gap-y-6px text-13px">
            <span class="text-12px text-gray-500">共 {{ hostResultSummary.total }} 台</span>
            <span class="run-host-chip">
              <span class="run-host-dot state-ok" aria-hidden="true"></span>
              成功 {{ hostResultSummary.success }}
            </span>
            <span class="run-host-chip" :class="{ 'is-alert': hostResultSummary.failed > 0 }">
              <span
                class="run-host-dot"
                :class="hostResultSummary.failed > 0 ? 'state-fail' : ''"
                aria-hidden="true"
              ></span>
              失败 {{ hostResultSummary.failed }}
            </span>
          </div>
          <div class="flex flex-wrap items-center gap-8px">
            <ElInput
              v-model="hostSearchInput"
              clearable
              class="w-220px"
              placeholder="搜索主机名或 IP"
              @keyup.enter="searchHostResults"
              @clear="searchHostResults"
            />
            <ElButton @click="searchHostResults">搜索</ElButton>
          </div>
        </div>
        <div class="run-filter" role="group" aria-label="筛选主机结果">
          <button type="button" :aria-pressed="hostResultFilter === 'all'" @click="setHostResultFilter('all')">
            全部
          </button>
          <button type="button" :aria-pressed="hostResultFilter === 'failed'" @click="setHostResultFilter('failed')">
            失败
          </button>
          <button type="button" :aria-pressed="hostResultFilter === 'success'" @click="setHostResultFilter('success')">
            成功
          </button>
        </div>
        <ElTable
          v-loading="hostResultsLoading"
          :data="hostResults"
          border
          size="small"
          row-key="id"
          max-height="360"
          class="w-full"
          highlight-current-row
          :current-row-key="selectedHostResult?.id"
          @row-click="showHostOutput"
        >
          <ElTableColumn label="主机" min-width="160" align="center" header-align="center" show-overflow-tooltip>
            <template #default="{ row }">
              <ElButton
                link
                class="run-host-name"
                :aria-label="`查看 ${row.hostname} 的输出`"
                @click.stop="showHostOutput(row)"
              >
                {{ row.hostname }}
              </ElButton>
            </template>
          </ElTableColumn>
          <ElTableColumn
            v-if="showHostAddressColumn"
            prop="ip"
            label="执行地址"
            min-width="140"
            align="center"
            header-align="center"
            show-overflow-tooltip
          />
          <ElTableColumn label="状态" width="110" align="center" header-align="center">
            <template #default="{ row }">
              <span class="text-12px" :class="stateClass(row.status)">● {{ hostStatusLabel(row.status) }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn label="耗时" width="90" align="center" class-name="tabular-nums">
            <template #default="{ row }">
              <span class="tabular-nums">{{ hostDuration(row) }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn label="退出码" width="90" align="center" class-name="tabular-nums">
            <template #default="{ row }">
              <span class="tabular-nums">{{ row.exitCode ?? '-' }}</span>
            </template>
          </ElTableColumn>
        </ElTable>
        <div class="flex justify-end">
          <ElPagination
            :current-page="hostPage"
            :page-size="hostPageSize"
            :page-sizes="[20, 50, 100]"
            :total="hostResultTotal"
            layout="total, sizes, prev, pager, next"
            @current-change="changeHostPage"
            @size-change="changeHostPageSize"
          />
        </div>
        <ElCollapse v-model="expandedHostOutput" class="advanced-collapse run-detail-collapse">
          <ElCollapseItem name="host-output">
            <template #title>
              <span>主机输出</span>
              <span v-if="selectedHostResult" class="ml-8px text-12px text-gray-500">
                {{ selectedHostResult.hostname }}
              </span>
            </template>
            <div v-loading="hostOutputLoading" class="min-h-80px pt-8px">
              <div
                v-if="selectedHostResult?.stderr"
                class="run-output-tabs mb-8px"
                role="group"
                aria-label="切换输出内容"
              >
                <button type="button" :aria-pressed="outputTab === 'stdout'" @click="setOutputTab('stdout')">
                  标准输出
                </button>
                <button type="button" :aria-pressed="outputTab === 'stderr'" @click="setOutputTab('stderr')">
                  错误输出
                </button>
              </div>
              <AnsiConsole
                :text="selectedHostResult ? selectedHostResult[outputTab] || '无输出' : '选择上方主机后查看执行输出'"
                :error="outputTab === 'stderr'"
              />
            </div>
          </ElCollapseItem>
        </ElCollapse>
      </div>
    </ElDrawer>
  </div>
</template>

<style scoped>
.run-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  line-height: 1.45;
  text-wrap: balance;
}

.run-subtitle {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 12px;
  color: var(--el-text-color-regular);
  font-size: 13px;
  line-height: 1.5;
  text-wrap: pretty;
}

.run-actions {
  flex: none;
}

.run-summary {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 24px;
}

.run-summary-item {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 6px;
}

.run-summary-item > span {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.run-summary-item > strong {
  overflow-wrap: anywhere;
  color: var(--el-text-color-primary);
  font-size: 16px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.run-summary-unit {
  margin-left: 3px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  font-weight: 400;
}

.run-workspace {
  display: grid;
  /* 两栏等高：左右卡片拉伸至同一行高（与原型一致） */
  grid-template-columns: 300px minmax(0, 1fr);
  gap: 16px;
}

.run-steps-panel,
.run-result-panel {
  min-width: 0;
}

.run-step-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin: -6px;
}

.run-step-button {
  position: relative;
  display: flex;
  width: 100%;
  min-height: 72px;
  align-items: flex-start;
  gap: 12px;
  padding: 13px 11px;
  border: 1px solid transparent;
  background: transparent;
  color: var(--el-text-color-primary);
  cursor: pointer;
  text-align: left;
  transition:
    background-color 180ms ease-out,
    border-color 180ms ease-out;
}

/* 步骤时间轴连接线：从序号圆点底部延伸到下一个圆点顶部 */
.run-step-button:not(:last-child)::after {
  content: '';
  position: absolute;
  top: 41px; /* 1px 边框 + 13px 内边距 + 25px 圆点 + 2px 间隙 */
  bottom: -18px; /* 跨过 4px 列表间距 + 下一个按钮 14px 顶部内边距，接到下一个圆点 */
  left: 23.5px; /* 1px 边框 + 11px 内边距 + 12.5px 圆点半径，对齐圆点中心 */
  width: 2px;
  background: var(--el-border-color);
}

.run-step-button:hover {
  background: var(--el-fill-color-light);
}

.run-step-button.is-selected {
  border-color: var(--el-border-color);
  background: var(--el-fill-color-light);
  box-shadow: inset 2px 0 var(--el-color-primary);
}

.run-step-panel-enter-active {
  transition:
    opacity 180ms ease-out,
    transform 180ms ease-out;
}

.run-step-panel-leave-active {
  transition:
    opacity 150ms ease-in,
    transform 150ms ease-in;
}

.run-step-panel-enter-from,
.run-step-panel-leave-to {
  opacity: 0;
  transform: translateY(6px);
}

@media (prefers-reduced-motion: reduce) {
  .run-step-panel-enter-active,
  .run-step-panel-leave-active {
    transition: none;
  }
}

.run-step-button:focus-visible {
  outline: 2px solid var(--el-color-primary);
  outline-offset: 2px;
}

.run-step-button:active,
.run-filter button:active,
.run-output-tabs button:active {
  transform: scale(0.96);
}

.run-step-button strong {
  font-size: 13px;
  font-weight: 400;
}

.run-step-description {
  display: block;
  overflow: hidden;
  margin-top: 7px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}

.run-step-diagnostics {
  color: var(--el-text-color-secondary);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}

.run-step-diagnostics strong {
  margin-left: 4px;
  color: var(--el-text-color-primary);
  font-size: 13px;
  font-weight: 600;
}

.run-step-number {
  display: grid;
  width: 25px;
  height: 25px;
  flex: none;
  place-items: center;
  border-radius: 50%;
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
  font-size: 12px;
}

/* 徽标随状态着色：绿成功、红失败、蓝等待 */
.run-step-number.state-ok {
  background: var(--el-color-success-light-9);
  color: var(--el-color-success);
}

.run-step-number.state-fail {
  background: var(--el-color-danger-light-9);
  color: var(--el-color-danger);
}

.run-section-title {
  color: var(--el-text-color-primary);
  font-size: 14px;
  font-weight: 500;
}

.run-host-name {
  min-height: 32px;
  padding: 0;
  color: var(--el-text-color-primary);
  font-weight: 400;
}

.run-host-name:hover {
  color: var(--el-color-primary);
}

/* 主机结果统计 chips：色点 + 数字，状态不只靠颜色 */
.run-host-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 2px 8px;
  border: 1px solid var(--el-border-color-lighter);
  background: var(--el-fill-color-light);
  color: var(--el-text-color-regular);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}

.run-host-chip.is-alert {
  border-color: var(--el-color-danger-light-5);
  background: var(--el-color-danger-light-9);
  color: var(--el-color-danger);
}

.run-host-dot {
  width: 6px;
  height: 6px;
  flex: none;
  border-radius: 50%;
  background: var(--el-text-color-secondary);
}

.run-host-dot.state-ok {
  background: var(--el-color-success);
}

.run-host-dot.state-fail {
  background: var(--el-color-danger);
}

.run-filter,
.run-output-tabs {
  display: flex;
  align-items: center;
  gap: 5px;
}

.run-filter button,
.run-output-tabs button {
  min-height: 32px;
  border: 1px solid var(--el-border-color);
  background: var(--el-fill-color-blank);
  color: var(--el-text-color-regular);
  cursor: pointer;
  font-size: 12px;
  transition:
    background-color 180ms ease-out,
    border-color 180ms ease-out;
}

.run-filter button {
  padding: 0 10px;
}

.run-output-tabs button {
  border: 0;
  border-bottom: 2px solid transparent;
  padding: 0 4px;
}

.run-filter button[aria-pressed='true'] {
  border-color: var(--el-color-primary-light-5);
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
}

.run-output-tabs button[aria-pressed='true'] {
  border-bottom-color: var(--el-color-primary);
  color: var(--el-color-primary);
}

.run-filter button:focus-visible,
.run-output-tabs button:focus-visible {
  outline: 2px solid var(--el-color-primary);
  outline-offset: 2px;
}

/* 步骤/主机状态文字色（对齐原型：绿成功、红失败、蓝等待） */
.state-ok {
  color: var(--el-color-success);
}

.state-fail {
  color: var(--el-color-danger);
}

.state-wait {
  color: var(--el-color-primary);
}

@media (max-width: 1100px) {
  .run-summary {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .run-workspace {
    grid-template-columns: minmax(0, 1fr);
  }

  .run-step-list {
    flex-direction: row;
    overflow-x: auto;
    margin: 0;
  }

  /* 移动端步骤列表横向排列，纵向时间轴连接线关闭 */
  .run-step-button:not(:last-child)::after {
    display: none;
  }

  .run-step-button {
    min-width: 210px;
  }

  .run-summary {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
