<script setup lang="tsx">
import { computed, onScopeDispose, ref, shallowRef, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { executionKindRecord, nodeStatusRecord, runDomainRecord, runStatusRecord } from '@/constants/business';
import {
  fetchCancelRun,
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

defineOptions({ name: 'TaskRunDetail' });

const route = useRoute();
const router = useRouter();
const { hasAuth } = useAuth();
const domain = computed<Api.Jobs.RunDomain>(() => (route.query.domain === 'ops' ? 'ops' : 'task'));
let requestScope = new AbortController();

const runId = computed(() => {
  const parsed = Number(route.params.id);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
});

/** ============ 运行基础信息 ============ */

const run = shallowRef<Api.Jobs.RunRecord | null>(null);

async function loadRun() {
  if (runId.value === null) return;
  const scope = requestScope;
  const { data, error } = await fetchGetRunDetail(runId.value, domain.value, requestScope.signal);
  if (scope === requestScope && !scope.signal.aborted && !error && data) {
    run.value = data;
  }
}

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

const permissionPrefix = computed(() => (domain.value === 'ops' ? 'ops' : 'jobs'));
const mayRetry = computed(() => hasAuth(`${permissionPrefix.value}.workflow_run:retry`));
const activeStatuses = new Set<Api.Jobs.RunStatus>(['pending', 'queued', 'running', 'waiting', 'cancel_requested']);
const finishedStatuses = new Set<Api.Jobs.RunStatus>(['success', 'failed', 'timeout', 'canceled']);

const canCancel = computed(() =>
  Boolean(run.value && activeStatuses.has(run.value.status) && hasAuth(`${permissionPrefix.value}.workflow_run:cancel`))
);
const canRetry = computed(() => run.value?.status === 'failed' && mayRetry.value);
const canRerun = computed(() => Boolean(run.value && finishedStatuses.has(run.value.status) && mayRetry.value));

/** ============ 事件流（T14 同步协议） ============ */

const { events, terminal, connected, transportError } = useRunEventStream(runId, domain);

const eventListRef = shallowRef<HTMLElement | null>(null);

const eventTimeLine = computed(() =>
  events.value.map(item => ({
    id: item.id,
    sequence: item.sequence,
    eventType: item.normalizedEventType || item.eventType,
    message: item.message,
    createdAt: item.createdAt
  }))
);

/** ============ 节点状态 ============ */

const nodes = shallowRef<Api.Jobs.NodeRunRecord[]>([]);
const nodesLoading = ref(false);

async function loadNodes() {
  if (runId.value === null) return;
  const scope = requestScope;
  nodesLoading.value = true;
  try {
    const { data, error } = await fetchGetRunNodes(runId.value, domain.value, requestScope.signal);
    if (scope === requestScope && !scope.signal.aborted && !error && data) {
      nodes.value = data;
    }
  } finally {
    if (scope === requestScope) nodesLoading.value = false;
  }
}

const nodeStatusTagType: Record<Api.Jobs.NodeStatus, UI.ThemeColor> = {
  pending: 'info',
  queued: 'info',
  running: 'primary',
  success: 'success',
  failed: 'danger',
  skipped: 'info',
  ignored: 'info',
  timeout: 'danger',
  canceled: 'warning'
};

function nodeTagType(status: string): UI.ThemeColor {
  return nodeStatusTagType[status as Api.Jobs.NodeStatus] ?? 'info';
}

function nodeStatusLabel(status: string): string {
  return $t(nodeStatusRecord[status as Api.Jobs.NodeStatus]);
}

/** ============ 主机结果抽屉 ============ */

const hostResultsVisible = ref(false);
const hostResultsLoading = ref(false);
const hostResults = shallowRef<Api.Jobs.HostResultRecord[]>([]);
const hostResultNode = shallowRef<Api.Jobs.NodeRunRecord | null>(null);
const selectedHostResult = shallowRef<Api.Jobs.HostResultRecord | null>(null);

async function showHostResults(node: Api.Jobs.NodeRunRecord) {
  const scope = requestScope;
  hostResults.value = [];
  selectedHostResult.value = null;
  hostResultNode.value = node;
  hostResultsVisible.value = true;
  hostResultsLoading.value = true;
  try {
    const { data, error } = await fetchGetNodeHostResults(node.id, scope.signal);
    if (scope === requestScope && !scope.signal.aborted && hostResultNode.value?.id === node.id && !error && data) {
      hostResults.value = data;
    }
  } finally {
    if (scope === requestScope && hostResultNode.value?.id === node.id) hostResultsLoading.value = false;
  }
}

function showHostOutput(row: Api.Jobs.HostResultRecord) {
  selectedHostResult.value = row;
}

const hostResultTagType: Record<Api.Jobs.HostResultStatus, UI.ThemeColor> = {
  pending: 'info',
  running: 'primary',
  ok: 'success',
  changed: 'warning',
  failed: 'danger',
  unreachable: 'danger',
  canceled: 'warning',
  skipped: 'info'
};

function hostTagType(status: string): UI.ThemeColor {
  return hostResultTagType[status as Api.Jobs.HostResultStatus] ?? 'info';
}

/** ============ 操作 ============ */

const operating = ref(false);

async function onCancel() {
  if (runId.value === null) return;
  operating.value = true;
  try {
    const { error } = await fetchCancelRun(runId.value, domain.value, requestScope.signal);
    if (!error) {
      window.$message?.success($t('common.updateSuccess'));
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
      window.$message?.success($t('page.task.run.retryCreated'));
      router.push({ name: 'task_run-detail', params: { id: data.id }, query: { domain: domain.value } });
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
      window.$message?.success($t('page.task.run.retryCreated'));
      router.push({ name: 'task_run-detail', params: { id: data.id }, query: { domain: domain.value } });
    }
  } finally {
    operating.value = false;
  }
}

async function onDownloadLog() {
  if (runId.value === null) return;
  const blob = await fetchRunLogFile(runId.value, domain.value, requestScope.signal);
  if (!blob) return;
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `run-${runId.value}.log`;
  link.click();
  URL.revokeObjectURL(url);
}

watch(
  () => events.value.at(-1)?.sequence,
  async () => {
    const el = eventListRef.value;
    if (el) el.scrollTop = el.scrollHeight;
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
    run.value = null;
    nodes.value = [];
    hostResults.value = [];
    hostResultsVisible.value = false;
    refresh();
  },
  { immediate: true }
);
onScopeDispose(() => requestScope.abort());
</script>

<template>
  <div class="min-h-500px flex-col-stretch gap-16px overflow-hidden lt-sm:overflow-auto">
    <ElCard class="card-wrapper">
      <template v-if="run">
        <div class="mb-12px flex items-center justify-between">
          <div class="flex items-center gap-12px">
            <span class="text-18px font-bold">#{{ run.id }}</span>
            <ElTag :type="runStatusTagType[run.status]" size="large">
              {{ $t(runStatusRecord[run.status]) }}
            </ElTag>
            <ElTag v-if="!terminal && connected" type="success" size="small" effect="plain">
              {{ $t('page.task.detail.live') }}
            </ElTag>
            <ElTag v-else-if="!terminal && transportError" type="info" size="small" effect="plain">
              {{ $t('page.task.detail.fallback') }}
            </ElTag>
          </div>
          <ElSpace>
            <ElButton v-if="canCancel" type="warning" plain :loading="operating" @click="onCancel">
              {{ $t('page.task.run.cancel') }}
            </ElButton>
            <ElButton v-if="canRetry" type="danger" plain :loading="operating" @click="onRetry">
              {{ $t('page.task.run.retry') }}
            </ElButton>
            <ElButton v-if="canRerun" plain :loading="operating" @click="onRerun">
              {{ $t('page.task.run.rerun') }}
            </ElButton>
            <ElButton plain @click="onDownloadLog">
              {{ $t('page.task.run.log') }}
            </ElButton>
            <ElButton @click="refresh">
              <template #icon>
                <icon-mdi-refresh class="text-icon" />
              </template>
              {{ $t('common.refresh') }}
            </ElButton>
          </ElSpace>
        </div>
        <ElDescriptions :column="3" border size="small">
          <ElDescriptionsItem :label="$t('page.task.run.workflowName')">
            {{ run.workflowName }}
          </ElDescriptionsItem>
          <ElDescriptionsItem :label="$t('page.task.run.executionKind')">
            {{ $t(executionKindRecord[run.executionKind]) }}
          </ElDescriptionsItem>
          <ElDescriptionsItem :label="$t('page.task.run.runDomain')">
            {{ $t(runDomainRecord[run.runDomain]) }}
          </ElDescriptionsItem>
          <ElDescriptionsItem :label="$t('page.task.run.triggeredBy')">
            {{ run.triggeredByName || '-' }}
          </ElDescriptionsItem>
          <ElDescriptionsItem :label="$t('page.task.run.targetCount')">
            {{ run.targetCount }}
          </ElDescriptionsItem>
          <ElDescriptionsItem :label="$t('page.task.run.startedAt')">
            {{ run.startedAt || '-' }}
          </ElDescriptionsItem>
          <ElDescriptionsItem :label="$t('page.task.run.finishedAt')">
            {{ run.finishedAt || '-' }}
          </ElDescriptionsItem>
          <ElDescriptionsItem :label="$t('page.task.run.duration')">
            {{ run.durationMs === null ? '-' : `${(run.durationMs / 1000).toFixed(1)}s` }}
          </ElDescriptionsItem>
          <ElDescriptionsItem :label="$t('page.task.run.workerPool')">
            {{ run.workerPoolName || '-' }}
          </ElDescriptionsItem>
          <ElDescriptionsItem v-if="run.failureReason" :label="$t('page.task.run.failureReason')" :span="3">
            <span class="text-error">{{ run.failureReason }}</span>
          </ElDescriptionsItem>
        </ElDescriptions>
      </template>
      <ElSkeleton v-else :rows="3" animated />
    </ElCard>

    <ElCard
      class="flex-1 overflow-hidden card-wrapper"
      :body-style="{ height: '100%', display: 'flex', flexDirection: 'column', gap: '16px', overflow: 'hidden' }"
    >
      <div class="flex-1 overflow-hidden">
        <p class="mb-8px font-bold">{{ $t('page.task.detail.node.title') }}</p>
        <ElTable v-loading="nodesLoading" height="240px" border size="small" :data="nodes" row-key="id">
          <ElTableColumn
            prop="nodeKey"
            :label="$t('page.task.detail.node.key')"
            min-width="120"
            show-overflow-tooltip
          />
          <ElTableColumn prop="node_type" :label="$t('page.task.detail.node.type')" width="90" align="center" />
          <ElTableColumn
            prop="commandName"
            :label="$t('page.task.detail.node.command')"
            min-width="120"
            show-overflow-tooltip
          />
          <ElTableColumn :label="$t('page.task.run.statusLabel')" width="90" align="center">
            <template #default="{ row }">
              <ElTag :type="nodeTagType(row.status)" size="small">
                {{ nodeStatusLabel(row.status) }}
              </ElTag>
            </template>
          </ElTableColumn>
          <ElTableColumn prop="attemptCount" :label="$t('page.task.detail.node.attempts')" width="80" align="center" />
          <ElTableColumn prop="exitCode" :label="$t('page.task.detail.node.exitCode')" width="80" align="center">
            <template #default="{ row }">{{ row.exitCode ?? '-' }}</template>
          </ElTableColumn>
          <ElTableColumn :label="$t('page.task.run.duration')" width="90" align="center">
            <template #default="{ row }">
              {{ row.durationMs === null ? '-' : `${(row.durationMs / 1000).toFixed(1)}s` }}
            </template>
          </ElTableColumn>
          <ElTableColumn
            prop="failureReason"
            :label="$t('page.task.run.failureReason')"
            min-width="140"
            show-overflow-tooltip
          >
            <template #default="{ row }">{{ row.failureReason || '-' }}</template>
          </ElTableColumn>
          <ElTableColumn :label="$t('common.operate')" width="110" align="center" fixed="right">
            <template #default="{ row }">
              <ElButton
                v-if="['command', 'script', 'playbook', 'module'].includes(row.node_type)"
                type="primary"
                plain
                size="small"
                @click="showHostResults(row)"
              >
                {{ $t('page.task.detail.node.hostResults') }}
              </ElButton>
            </template>
          </ElTableColumn>
        </ElTable>
      </div>

      <div class="flex-1 overflow-hidden">
        <div class="mb-8px flex items-center justify-between">
          <p class="font-bold">{{ $t('page.task.detail.event.title') }}</p>
          <span class="text-12px text-gray-400">{{ events.length }}</span>
        </div>
        <div
          ref="eventListRef"
          class="h-[calc(100%-28px)] overflow-y-auto rounded-4px bg-gray-50 p-8px dark:bg-#1e1e1e"
        >
          <ElEmpty v-if="!eventTimeLine.length" :description="$t('common.noData')" :image-size="60" />
          <div
            v-for="item in eventTimeLine"
            :key="item.id"
            class="flex gap-8px border-b border-gray-100 py-4px text-12px dark:border-#2d2d2d last:border-none"
          >
            <span class="w-150px shrink-0 text-gray-400">{{ item.createdAt }}</span>
            <span class="w-40px shrink-0 text-right text-gray-400">#{{ item.sequence }}</span>
            <span class="w-160px shrink-0 truncate font-mono">{{ item.eventType }}</span>
            <span class="break-all">{{ item.message }}</span>
          </div>
        </div>
      </div>
    </ElCard>

    <ElDrawer v-model="hostResultsVisible" :title="$t('page.task.detail.node.hostResults')" size="720px">
      <template v-if="hostResultNode">
        <p class="mb-8px text-13px">{{ hostResultNode.nodeName }}（{{ hostResultNode.nodeKey }}）</p>
        <ElTable v-loading="hostResultsLoading" border size="small" :data="hostResults" row-key="id">
          <ElTableColumn
            prop="hostname"
            :label="$t('page.task.detail.host.hostname')"
            min-width="110"
            show-overflow-tooltip
          />
          <ElTableColumn prop="ip" :label="$t('page.task.detail.host.ip')" width="120" />
          <ElTableColumn :label="$t('page.task.run.statusLabel')" width="110" align="center">
            <template #default="{ row }">
              <ElTag :type="hostTagType(row.status)" size="small">
                {{ row.status }}
              </ElTag>
            </template>
          </ElTableColumn>
          <ElTableColumn prop="exitCode" :label="$t('page.task.detail.node.exitCode')" width="80" align="center">
            <template #default="{ row }">{{ row.exitCode ?? '-' }}</template>
          </ElTableColumn>
          <ElTableColumn prop="finishedAt" :label="$t('page.task.run.finishedAt')" width="170">
            <template #default="{ row }">{{ row.finishedAt || '-' }}</template>
          </ElTableColumn>
          <ElTableColumn :label="$t('common.action')" width="90" align="center" fixed="right">
            <template #default="{ row }">
              <ElButton link type="primary" size="small" @click="showHostOutput(row)">
                {{ $t('page.task.detail.host.viewOutput') }}
              </ElButton>
            </template>
          </ElTableColumn>
        </ElTable>

        <template v-if="selectedHostResult">
          <div class="mb-8px mt-16px flex items-center gap-8px">
            <span class="text-14px font-600">{{ selectedHostResult.hostname }}</span>
            <ElTag :type="hostTagType(selectedHostResult.status)" size="small">{{ selectedHostResult.status }}</ElTag>
          </div>
          <div class="mb-8px">
            <p class="mb-4px text-12px text-gray-500">{{ $t('page.task.detail.host.stdout') }}</p>
            <pre class="max-h-360px overflow-auto rounded-4px bg-gray-100 p-8px text-12px dark:bg-gray-800">{{
              selectedHostResult.stdout || '-'
            }}</pre>
          </div>
          <div v-if="selectedHostResult.stderr">
            <p class="mb-4px text-12px text-gray-500">{{ $t('page.task.detail.host.stderr') }}</p>
            <pre class="max-h-240px overflow-auto rounded-4px bg-gray-100 p-8px text-12px dark:bg-gray-800">{{
              selectedHostResult.stderr
            }}</pre>
          </div>
        </template>
      </template>
    </ElDrawer>
  </div>
</template>

<style scoped></style>
