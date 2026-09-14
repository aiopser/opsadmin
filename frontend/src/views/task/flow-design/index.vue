<script setup lang="ts">
import { computed, ref, shallowRef, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import {
  fetchGetApiEndpointList,
  fetchGetCommandList,
  fetchGetCommandVersions,
  fetchGetJenkinsJobList,
  fetchGetNotificationTemplateList,
  fetchGetWorkflowGraph,
  fetchGetWorkflowVersions,
  fetchPublishWorkflowVersion,
  fetchUpdateWorkflowGraph,
  fetchUpdateWorkflowVersion,
  fetchValidateWorkflowVersion
} from '@/service/api';
import CodeEditor from '@/components/common/code-editor/index.vue';

defineOptions({ name: 'TaskFlowDesign' });

const route = useRoute();
const router = useRouter();

/** ============ 步骤类型定义（v1 顺序编排能力边界） ============ */

type StepType = 'command' | 'script' | 'playbook' | 'module' | 'api' | 'jenkins' | 'notify';

const STEP_TYPES: { value: StepType; label: string; needHost: boolean }[] = [
  { value: 'command', label: '命令', needHost: true },
  { value: 'script', label: '脚本', needHost: true },
  { value: 'playbook', label: 'Playbook', needHost: true },
  { value: 'module', label: '模块', needHost: true },
  { value: 'api', label: 'API 调用', needHost: false },
  { value: 'jenkins', label: 'Jenkins 任务', needHost: false },
  { value: 'notify', label: '通知', needHost: false }
];

const STEP_TYPE_TEXT: Record<string, string> = Object.fromEntries(STEP_TYPES.map(item => [item.value, item.label]));

const ANSIBLE_TYPES = new Set<StepType>(['command', 'script', 'playbook', 'module']);
const STEP_TYPE_SET = new Set<string>(STEP_TYPES.map(item => item.value));

const HOST_STRATEGY_OPTIONS = [
  { value: 'parallel', label: '并行（多主机同时执行）' },
  { value: 'rolling', label: '滚动（分批执行）' },
  { value: 'serial', label: '串行（逐台执行）' }
];

const FAILURE_POLICY_OPTIONS = [
  { value: 'stop', label: '失败终止' },
  { value: 'ignore', label: '忽略失败继续' }
];

/** 步骤内部节点标识（node_key）：重排/复制配置时保持稳定，仅新建时生成 */
function genStepKey() {
  return `step_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 6)}`;
}

interface StepItem {
  key: string;
  name: string;
  type: StepType;
  commandId: number | null;
  commandVersionId: number | null;
  resourceId: number | null;
  hostStrategy: 'parallel' | 'rolling' | 'serial';
  forks: number | null;
  serialBatch: number | null;
  checkMode: boolean;
  inputMappingText: string;
  timeoutSeconds: number;
  maxAttempts: number;
  failurePolicy: 'stop' | 'ignore';
}

function createStep(type: StepType): StepItem {
  return {
    key: genStepKey(),
    name: STEP_TYPE_TEXT[type] ?? type,
    type,
    commandId: null,
    commandVersionId: null,
    resourceId: null,
    hostStrategy: 'parallel',
    forks: null,
    serialBatch: null,
    checkMode: false,
    inputMappingText: '',
    timeoutSeconds: 600,
    maxAttempts: 1,
    failurePolicy: 'stop'
  };
}

/** ============ 版本上下文 ============ */

const templateId = Number(route.query.templateId) || null;
const targetVersionId = Number(route.query.versionId) || null;

const missingParams = ref(!templateId || !targetVersionId);
const pageLoading = ref(false);
const versionInfo = shallowRef<Api.Automation.WorkflowVersionRecord | null>(null);

const versionStatusText: Record<string, string> = {
  draft: '草稿',
  published: '已发布',
  archived: '已归档'
};

const versionStatusTagType: Record<string, string> = {
  draft: 'info',
  published: 'success',
  archived: 'warning'
};

/** ============ 图加载与线性检测 ============ */

const graphData = shallowRef<Api.Automation.WorkflowGraph | null>(null);
const isLinear = ref(true);
const structureReason = ref('');

function analyzeGraph(graph: Api.Automation.WorkflowGraph): { linear: boolean; reason: string } {
  const nodes = graph.nodes ?? [];
  if (!nodes.length) return { linear: true, reason: '' };
  const starts = nodes.filter(node => node.type === 'start');
  const ends = nodes.filter(node => node.type === 'end');
  if (starts.length !== 1) return { linear: false, reason: '流程缺少唯一「开始」节点' };
  if (ends.length !== 1) return { linear: false, reason: '流程缺少唯一「结束」节点' };
  const edges = graph.edges ?? [];
  const byId = new Map(nodes.map(node => [node.id, node]));
  const visited = new Set<string>();
  let currentId = starts[0].id;
  while (true) {
    const cur = currentId;
    const outs = edges.filter(edge => edge.source === cur);
    if (outs.length !== 1) return { linear: false, reason: '存在分支或并行结构，步骤编辑器无法表达' };
    const edge = outs[0];
    if (edge.condition) return { linear: false, reason: '存在条件分支连线，步骤编辑器无法表达' };
    const next = byId.get(edge.target);
    if (!next) return { linear: false, reason: '存在指向未知节点的连线' };
    if (next.type === 'end') return { linear: true, reason: '' };
    if (!STEP_TYPE_SET.has(next.type)) {
      return { linear: false, reason: `节点「${next.name}」类型（${next.type}）不支持步骤编辑` };
    }
    if (edges.filter(item => item.target === next.id).length !== 1) {
      return { linear: false, reason: '存在多入边汇聚结构，步骤编辑器无法表达' };
    }
    if (visited.has(next.id)) return { linear: false, reason: '存在环状结构' };
    visited.add(next.id);
    currentId = next.id;
  }
}

function nodeToStep(node: Api.Automation.GraphNode): StepItem {
  const config = node.config ?? {};
  const step = createStep(node.type as StepType);
  step.key = node.id;
  step.name = node.name;
  step.commandVersionId = node.commandVersionId ?? null;
  step.commandId = node.commandVersion?.commandId ?? null;
  step.resourceId = node.resourceId ?? null;
  step.hostStrategy = (config.hostStrategy as StepItem['hostStrategy']) ?? 'parallel';
  step.forks = (config.forks as number) ?? null;
  step.serialBatch = (config.serialBatch as number) ?? null;
  step.checkMode = Boolean(config.checkMode);
  step.inputMappingText =
    node.inputMapping && Object.keys(node.inputMapping).length ? JSON.stringify(node.inputMapping, null, 2) : '';
  step.timeoutSeconds = node.timeoutSeconds ?? 600;
  step.maxAttempts = (node.retryPolicy?.maxAttempts as number) ?? 1;
  step.failurePolicy = node.failurePolicy === 'ignore' ? 'ignore' : 'stop';
  return step;
}

function extractSteps(graph: Api.Automation.WorkflowGraph): StepItem[] {
  const nodes = graph.nodes ?? [];
  const edges = graph.edges ?? [];
  const byId = new Map(nodes.map(node => [node.id, node]));
  const start = nodes.find(node => node.type === 'start');
  if (!start) return [];
  const result: StepItem[] = [];
  let currentId = start.id;
  while (true) {
    const cur = currentId;
    const out = edges.find(edge => edge.source === cur);
    if (!out) break;
    const next = byId.get(out.target);
    if (!next || next.type === 'end') break;
    result.push(nodeToStep(next));
    currentId = next.id;
  }
  return result;
}

/** ============ 步骤编辑状态 ============ */

const steps = ref<StepItem[]>([]);
const selectedKey = ref('');
const selectedStep = computed(() => steps.value.find(step => step.key === selectedKey.value) ?? null);

const editable = computed(() => versionInfo.value?.status === 'draft' && isLinear.value);

function selectStep(key: string) {
  if (!editable.value) return;
  selectedKey.value = key;
}

function addStep() {
  if (!editable.value) return;
  const step = createStep('command');
  steps.value.push(step);
  selectedKey.value = step.key;
}

function removeStep(key: string) {
  if (!editable.value) return;
  const index = steps.value.findIndex(step => step.key === key);
  if (index < 0) return;
  steps.value.splice(index, 1);
  if (selectedKey.value === key) {
    const next = steps.value[index] ?? steps.value[index - 1];
    selectedKey.value = next?.key ?? '';
  }
}

function copyStep(key: string) {
  if (!editable.value) return;
  const index = steps.value.findIndex(step => step.key === key);
  if (index < 0) return;
  const source = steps.value[index];
  const clone: StepItem = JSON.parse(JSON.stringify(source));
  clone.key = genStepKey();
  clone.name = `${source.name} 副本`;
  steps.value.splice(index + 1, 0, clone);
  selectedKey.value = clone.key;
}

function moveStep(key: string, offset: -1 | 1) {
  if (!editable.value) return;
  const index = steps.value.findIndex(step => step.key === key);
  const target = index + offset;
  if (index < 0 || target < 0 || target >= steps.value.length) return;
  const [item] = steps.value.splice(index, 1);
  steps.value.splice(target, 0, item);
}

function onStepTypeChange() {
  const step = selectedStep.value;
  if (!step) return;
  step.commandId = null;
  step.commandVersionId = null;
  step.resourceId = null;
  step.checkMode = false;
}

/** ============ 资源数据源 ============ */

const commandOptions = shallowRef<Api.Automation.CommandRecord[]>([]);
const apiOptions = shallowRef<Api.Automation.ApiEndpointRecord[]>([]);
const jenkinsOptions = shallowRef<Api.Automation.JenkinsJobRecord[]>([]);
const notifyOptions = shallowRef<Api.Automation.NotificationTemplateRecord[]>([]);
const versionCache = shallowRef(new Map<number, Api.Automation.CommandVersionRecord[]>());

function commandVersionsOf(commandId: number | null) {
  return (commandId && versionCache.value.get(commandId)) || [];
}

async function ensureCommandVersions(commandId: number) {
  if (versionCache.value.has(commandId)) return;
  const { data, error } = await fetchGetCommandVersions(commandId);
  if (!error) {
    const next = new Map(versionCache.value);
    next.set(
      commandId,
      data.filter(item => item.status === 'published')
    );
    versionCache.value = next;
  }
}

watch(
  () => selectedStep.value?.commandId,
  commandId => {
    if (commandId) {
      ensureCommandVersions(commandId);
    }
  },
  { immediate: true }
);

async function loadResourceOptions() {
  const [cmdRes, apiRes, jenkinsRes, notifyRes] = await Promise.all([
    fetchGetCommandList({ current: 1, size: 200 }),
    fetchGetApiEndpointList({ current: 1, size: 200 }),
    fetchGetJenkinsJobList({ current: 1, size: 200 }),
    fetchGetNotificationTemplateList({ current: 1, size: 200 })
  ]);
  if (!cmdRes.error) commandOptions.value = cmdRes.data.records;
  if (!apiRes.error) apiOptions.value = apiRes.data.records.filter(item => item.is_active);
  if (!jenkinsRes.error) jenkinsOptions.value = jenkinsRes.data.records.filter(item => item.is_active);
  if (!notifyRes.error) notifyOptions.value = notifyRes.data.records.filter(item => item.is_active);

  const boundIds = new Set(steps.value.filter(step => step.commandId).map(step => step.commandId as number));
  await Promise.all([...boundIds].map(commandId => ensureCommandVersions(commandId)));
}

const resourceOptionsByType = computed<Record<string, { id: number; name: string }[]>>(() => ({
  api: apiOptions.value.map(item => ({ id: item.id, name: item.name })),
  jenkins: jenkinsOptions.value.map(item => ({ id: item.id, name: `${item.serverName} / ${item.name}` })),
  notify: notifyOptions.value.map(item => ({ id: item.id, name: item.name }))
}));

function commandText(step: StepItem) {
  if (!ANSIBLE_TYPES.has(step.type)) return '';
  const command = commandOptions.value.find(item => item.id === step.commandId);
  const version = commandVersionsOf(step.commandId).find(item => item.id === step.commandVersionId);
  if (!command) return '未绑定资源';
  return version ? `${command.name} v${version.version}` : `${command.name}（未选版本）`;
}

function resourceText(step: StepItem) {
  if (ANSIBLE_TYPES.has(step.type)) return commandText(step);
  const options = resourceOptionsByType.value[step.type] ?? [];
  const found = options.find(item => item.id === step.resourceId);
  return found?.name ?? '未绑定资源';
}

const selectedVersionSupportedCheck = computed(() => {
  const step = selectedStep.value;
  if (!step || !ANSIBLE_TYPES.has(step.type) || !step.commandVersionId) return true;
  const version = commandVersionsOf(step.commandId).find(item => item.id === step.commandVersionId);
  return version ? version.check_mode_supported : true;
});

/** ============ 全局配置 ============ */

const inputSchemaText = ref('');
const globalVarsText = ref('');

function prettyJson(value: unknown): string {
  if (!value || (typeof value === 'object' && Object.keys(value as object).length === 0)) return '';
  return JSON.stringify(value, null, 2);
}

/** ============ 图构建与保存 ============ */

function parseJsonObject(text: string): Record<string, unknown> {
  const trimmed = text.trim();
  if (!trimmed) return {};
  const parsed = JSON.parse(trimmed);
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error('not an object');
  }
  return parsed as Record<string, unknown>;
}

function stepToNode(step: StepItem, inputMapping: Record<string, unknown>): Api.Automation.GraphNode {
  const node: Api.Automation.GraphNode = {
    id: step.key,
    name: step.name || step.key,
    type: step.type,
    inputMapping,
    failurePolicy: step.failurePolicy,
    timeoutSeconds: step.timeoutSeconds > 0 ? step.timeoutSeconds : 600
  };
  if (step.maxAttempts > 1) {
    node.retryPolicy = { maxAttempts: step.maxAttempts };
  }
  if (ANSIBLE_TYPES.has(step.type)) {
    node.commandVersionId = step.commandVersionId;
    const config: Record<string, unknown> = {};
    if (step.hostStrategy) config.hostStrategy = step.hostStrategy;
    if (step.hostStrategy === 'parallel' && step.forks) config.forks = step.forks;
    if (step.hostStrategy === 'rolling' && step.serialBatch) config.serialBatch = step.serialBatch;
    if (step.checkMode) config.checkMode = true;
    if (Object.keys(config).length) node.config = config;
  } else if (step.resourceId) {
    node.resourceType = step.type;
    node.resourceId = step.resourceId;
  }
  return node;
}

function buildGraph(mappings: Record<string, Record<string, unknown>>): Api.Automation.WorkflowGraph {
  const nodes: Api.Automation.GraphNode[] = [{ id: 'start', name: '开始', type: 'start' }];
  const edges: Api.Automation.GraphEdge[] = [];
  let previous = 'start';
  for (const step of steps.value) {
    nodes.push(stepToNode(step, mappings[step.key] ?? {}));
    edges.push({ id: `e_${previous}_${step.key}`, source: previous, target: step.key });
    previous = step.key;
  }
  nodes.push({ id: 'end', name: '结束', type: 'end' });
  edges.push({ id: `e_${previous}_end`, source: previous, target: 'end' });
  return { nodes, edges };
}

const saving = ref(false);
const saveErrors = ref<string[]>([]);

function collectSavePayload() {
  let inputSchema: Record<string, unknown>;
  let globalVars: Record<string, unknown>;
  try {
    inputSchema = parseJsonObject(inputSchemaText.value);
    globalVars = parseJsonObject(globalVarsText.value);
  } catch {
    window.$message?.error('全局配置的输入参数 Schema / 全局变量不是合法 JSON 对象');
    return null;
  }
  const mappings: Record<string, Record<string, unknown>> = {};
  for (const step of steps.value) {
    try {
      mappings[step.key] = parseJsonObject(step.inputMappingText);
    } catch {
      window.$message?.error(`步骤「${step.name}」的输入参数映射不是合法 JSON 对象`);
      selectedKey.value = step.key;
      return null;
    }
  }
  return { inputSchema, globalVars, mappings };
}

async function saveDraft(publishAfter = false) {
  if (!editable.value || !versionInfo.value) return;
  if (!steps.value.length) {
    window.$message?.warning('请先添加至少一个步骤');
    return;
  }
  const payload = collectSavePayload();
  if (!payload) return;

  saving.value = true;
  try {
    const { data, error } = await fetchUpdateWorkflowGraph(versionInfo.value.id, buildGraph(payload.mappings));
    if (error || !data) return;
    if (!data.valid) {
      saveErrors.value = data.errors;
      window.$message?.error('保存失败：流程结构校验未通过');
      return;
    }
    saveErrors.value = [];
    const patch: { inputSchema?: Record<string, unknown>; globalVars?: Record<string, unknown> } = {};
    if (Object.keys(payload.inputSchema).length) patch.inputSchema = payload.inputSchema;
    if (Object.keys(payload.globalVars).length) patch.globalVars = payload.globalVars;
    if (Object.keys(patch).length) {
      const { error: patchError } = await fetchUpdateWorkflowVersion(versionInfo.value.id, patch);
      if (patchError) return;
    }
    window.$message?.success('草稿已保存');
    if (publishAfter) await publishCurrent();
  } finally {
    saving.value = false;
  }
}

async function onValidate() {
  if (!versionInfo.value) return;
  saving.value = true;
  try {
    const { data, error } = await fetchValidateWorkflowVersion(versionInfo.value.id);
    if (!error && data) {
      if (data.valid) {
        saveErrors.value = [];
        window.$message?.success('校验通过，可以发布');
      } else {
        saveErrors.value = data.errors;
      }
    }
  } finally {
    saving.value = false;
  }
}

async function publishCurrent() {
  if (!versionInfo.value) return;
  const { data, error } = await fetchPublishWorkflowVersion(versionInfo.value.id);
  if (!error && data) {
    versionInfo.value = data;
    window.$message?.success(`v${data.version} 已发布，同模板旧发布版本已自动归档`);
  }
}

async function onPublish() {
  if (!editable.value || !versionInfo.value) return;
  try {
    await ElMessageBox.confirm('发布后本版本不可再修改，同模板旧的已发布版本将自动归档。确认发布？', '发布确认', {
      type: 'warning',
      confirmButtonText: '发布',
      cancelButtonText: '取消'
    });
  } catch {
    return;
  }
  await saveDraft(true);
}

/** ============ 初始化 ============ */

async function init() {
  pageLoading.value = true;
  try {
    const { data: versions, error } = await fetchGetWorkflowVersions(templateId as number);
    if (error) return;
    const current = versions.find(item => item.id === targetVersionId);
    if (!current) {
      window.$message?.error('未找到指定的流程版本');
      return;
    }
    versionInfo.value = current;

    const { data: graphRes, error: graphError } = await fetchGetWorkflowGraph(targetVersionId as number);
    if (graphError || !graphRes) return;
    graphData.value = graphRes.graph;
    inputSchemaText.value = prettyJson(graphRes.graph.inputSchema);
    globalVarsText.value = prettyJson(graphRes.graph.globalVars);

    const analysis = analyzeGraph(graphRes.graph);
    isLinear.value = analysis.linear;
    structureReason.value = analysis.reason;
    if (!analysis.linear) return;

    steps.value = extractSteps(graphRes.graph);
    selectedKey.value = steps.value[0]?.key ?? '';
    await loadResourceOptions();
  } finally {
    pageLoading.value = false;
  }
}

if (!missingParams.value) {
  init();
}

function backToTemplates() {
  router.push('/task/templates');
}

/** ============ 非线性结构只读展示 ============ */

const structureNodes = computed(() => graphData.value?.nodes ?? []);
const structureEdges = computed(() => graphData.value?.edges ?? []);

const structureNodeTypeText: Record<string, string> = {
  start: '开始',
  end: '结束',
  parallel_gateway: '并行网关',
  parallel_join: '并行汇聚'
};

function structureNodeText(type: string) {
  return structureNodeTypeText[type] ?? STEP_TYPE_TEXT[type] ?? type;
}

function structureResourceText(node: Api.Automation.GraphNode) {
  if (node.commandVersion) return `${node.commandVersion.commandName} v${node.commandVersion.version}`;
  if (node.resourceType) return `资源 #${node.resourceId}`;
  return '-';
}
</script>

<template>
  <div class="min-h-500px flex-col-stretch gap-16px overflow-hidden lt-sm:overflow-auto">
    <!-- 缺少参数引导 -->
    <ElCard v-if="missingParams" class="card-wrapper">
      <ElEmpty description="请从「流程模板」页选择某个草稿版本进入步骤编排">
        <ElButton type="primary" @click="backToTemplates">前往流程模板</ElButton>
      </ElEmpty>
    </ElCard>

    <template v-else>
      <!-- 顶部：版本信息 + 操作 -->
      <ElCard class="card-wrapper">
        <div v-loading="pageLoading" class="flex flex-wrap items-center justify-between gap-12px">
          <div class="flex items-center gap-12px">
            <ElButton size="small" @click="backToTemplates">返回</ElButton>
            <span class="text-16px font-600">{{ versionInfo?.workflowName || '流程编排' }}</span>
            <span class="text-14px text-gray-500">v{{ versionInfo?.version }}</span>
            <ElTag size="small" :type="(versionStatusTagType[versionInfo?.status ?? ''] ?? 'info') as any">
              {{ versionStatusText[versionInfo?.status ?? ''] ?? versionInfo?.status }}
            </ElTag>
            <ElTag v-if="!isLinear" size="small" type="danger">结构不支持步骤编辑</ElTag>
            <ElTag v-else-if="!editable" size="small" type="warning">只读</ElTag>
          </div>
          <div v-if="editable" class="flex items-center gap-8px">
            <ElButton :loading="saving" @click="onValidate">校验</ElButton>
            <ElButton type="primary" :loading="saving" @click="saveDraft(false)">保存草稿</ElButton>
            <ElButton type="success" :loading="saving" @click="onPublish">发布</ElButton>
          </div>
        </div>
      </ElCard>

      <!-- 校验错误 -->
      <ElAlert v-if="saveErrors.length" type="error" :closable="true" @close="saveErrors = []">
        <template #title>以下问题需要处理：</template>
        <ul class="m-0 list-inside pl-4px">
          <li v-for="(item, index) in saveErrors" :key="index">{{ item }}</li>
        </ul>
      </ElAlert>

      <!-- 非线性结构：只读查看 -->
      <template v-if="!isLinear">
        <ElAlert
          type="warning"
          :closable="false"
          :title="`当前步骤编辑器不支持此流程结构：${structureReason}。以下为只读查看，不会修改流程。`"
        />

        <div class="grid gap-16px lg:grid-cols-2">
          <ElCard class="card-wrapper" header="流程节点（只读）">
            <ElTable :data="structureNodes" border row-key="id">
              <ElTableColumn prop="id" label="节点 Key" min-width="140" show-overflow-tooltip />
              <ElTableColumn prop="name" label="名称" min-width="120" show-overflow-tooltip />
              <ElTableColumn label="类型" width="110" align="center">
                <template #default="{ row }">{{ structureNodeText(row.type) }}</template>
              </ElTableColumn>
              <ElTableColumn label="绑定资源" min-width="160" show-overflow-tooltip>
                <template #default="{ row }">{{ structureResourceText(row) }}</template>
              </ElTableColumn>
              <ElTableColumn label="超时(秒)" width="90" align="center">
                <template #default="{ row }">{{ row.timeoutSeconds ?? '-' }}</template>
              </ElTableColumn>
            </ElTable>
          </ElCard>
          <ElCard class="card-wrapper" header="流转连线（只读）">
            <ElTable :data="structureEdges" border row-key="id">
              <ElTableColumn prop="id" label="连线" min-width="140" show-overflow-tooltip />
              <ElTableColumn label="流转路径" min-width="200">
                <template #default="{ row }">{{ row.source }} → {{ row.target }}</template>
              </ElTableColumn>
              <ElTableColumn label="条件" min-width="140" show-overflow-tooltip>
                <template #default="{ row }">{{ row.condition || (row.isDefault ? '默认' : '-') }}</template>
              </ElTableColumn>
            </ElTable>
          </ElCard>
        </div>
      </template>

      <!-- 步骤编排器 -->
      <ElRow v-else :gutter="16" class="sm:flex-1-hidden">
        <!-- 左：步骤列表 -->
        <ElCol :xl="8" :lg="24" :md="24" :sm="24" :xs="24">
          <ElCard class="card-wrapper sm:h-full sm:flex-1-hidden" header="步骤列表">
            <div class="max-h-640px flex-col gap-8px overflow-auto">
              <div
                v-for="(step, index) in steps"
                :key="step.key"
                class="cursor-pointer border rounded-6px border-solid p-12px transition-colors"
                :class="
                  step.key === selectedKey
                    ? 'border-primary bg-primary/5'
                    : 'border-gray-200 hover:border-gray-400 dark:border-gray-700'
                "
                @click="selectStep(step.key)"
              >
                <div class="flex items-center justify-between gap-8px">
                  <div class="min-w-0 flex items-center gap-8px">
                    <span
                      class="h-20px w-20px flex shrink-0 items-center justify-center rounded-full bg-primary text-12px text-white"
                    >
                      {{ index + 1 }}
                    </span>
                    <span class="truncate text-14px font-500">{{ step.name }}</span>
                    <ElTag size="small" type="info">{{ STEP_TYPE_TEXT[step.type] }}</ElTag>
                  </div>
                  <div v-if="editable" class="flex shrink-0 items-center">
                    <ElButton link size="small" :disabled="index === 0" @click.stop="moveStep(step.key, -1)">
                      上移
                    </ElButton>
                    <ElButton
                      link
                      size="small"
                      :disabled="index === steps.length - 1"
                      @click.stop="moveStep(step.key, 1)"
                    >
                      下移
                    </ElButton>
                    <ElButton link size="small" @click.stop="copyStep(step.key)">复制</ElButton>
                    <ElButton link size="small" type="danger" @click.stop="removeStep(step.key)">删除</ElButton>
                  </div>
                </div>
                <div class="mt-6px pl-28px text-12px text-gray-500">
                  <div class="truncate">{{ resourceText(step) }}</div>
                  <div>
                    超时 {{ step.timeoutSeconds }}s
                    {{ step.maxAttempts > 1 ? ` · 重试 ${step.maxAttempts} 次` : '' }}
                    · {{ step.failurePolicy === 'ignore' ? '忽略失败' : '失败终止' }}
                    <template v-if="!['api', 'jenkins', 'notify'].includes(step.type)">
                      ·
                      {{ HOST_STRATEGY_OPTIONS.find(item => item.value === step.hostStrategy)?.label?.split('（')[0] }}
                    </template>
                  </div>
                </div>
              </div>

              <ElButton v-if="editable" class="w-full" :disabled="false" @click="addStep">＋ 添加步骤</ElButton>
              <ElEmpty v-if="!steps.length && !editable" description="该版本暂无步骤" :image-size="80" />
            </div>
          </ElCard>
        </ElCol>

        <!-- 右：配置面板 -->
        <ElCol :xl="16" :lg="24" :md="24" :sm="24" :xs="24">
          <ElCard class="card-wrapper sm:h-full sm:flex-1-hidden">
            <template #header>
              <div class="flex items-center justify-between">
                <p>步骤配置</p>
                <span v-if="selectedStep" class="text-12px text-gray-400">标识：{{ selectedStep.key }}</span>
              </div>
            </template>

            <ElEmpty v-if="!selectedStep" description="选择左侧步骤进行配置，或添加新步骤" />

            <div v-else class="max-h-680px flex-col gap-16px" :class="{ 'pointer-events-none opacity-60': !editable }">
              <!-- 基础 -->
              <ElCard shadow="never" header="基础信息">
                <ElForm label-width="110px">
                  <ElFormItem label="步骤名称">
                    <ElInput v-model="selectedStep.name" :disabled="!editable" placeholder="如：前置检查" />
                  </ElFormItem>
                  <ElFormItem label="步骤类型">
                    <ElSelect
                      v-model="selectedStep.type"
                      :disabled="!editable"
                      class="w-full"
                      @change="onStepTypeChange"
                    >
                      <ElOption v-for="item in STEP_TYPES" :key="item.value" :label="item.label" :value="item.value" />
                    </ElSelect>
                  </ElFormItem>
                </ElForm>
              </ElCard>

              <!-- 资源绑定 -->
              <ElCard shadow="never" :header="ANSIBLE_TYPES.has(selectedStep.type) ? '资源与固定版本' : '引用资源'">
                <ElForm label-width="110px">
                  <template v-if="ANSIBLE_TYPES.has(selectedStep.type)">
                    <ElFormItem label="自动化资源">
                      <ElSelect
                        v-model="selectedStep.commandId"
                        :disabled="!editable"
                        filterable
                        clearable
                        placeholder="选择命令/脚本/Playbook/模块"
                        class="w-full"
                        @change="selectedStep.commandVersionId = null"
                      >
                        <ElOption
                          v-for="item in commandOptions.filter(cmd => cmd.resource_kind === selectedStep?.type)"
                          :key="item.id"
                          :label="`${item.name}（${item.code}）`"
                          :value="item.id"
                        />
                      </ElSelect>
                      <div class="w-full text-12px text-gray-400">发布时固定引用所选版本，运行时使用快照</div>
                    </ElFormItem>
                    <ElFormItem label="资源版本">
                      <ElSelect
                        v-model="selectedStep.commandVersionId"
                        :disabled="!editable || !selectedStep.commandId"
                        placeholder="选择已发布版本"
                        class="w-full"
                      >
                        <ElOption
                          v-for="item in commandVersionsOf(selectedStep.commandId)"
                          :key="item.id"
                          :label="`v${item.version}`"
                          :value="item.id"
                        />
                      </ElSelect>
                      <div
                        v-if="selectedStep.commandId && !commandVersionsOf(selectedStep.commandId).length"
                        class="w-full text-12px text-orange-500"
                      >
                        该资源暂无已发布版本，请先到自动化资源页发布
                      </div>
                    </ElFormItem>
                  </template>
                  <ElFormItem v-else label="资源">
                    <ElSelect
                      v-model="selectedStep.resourceId"
                      :disabled="!editable"
                      filterable
                      clearable
                      placeholder="选择资源"
                      class="w-full"
                    >
                      <ElOption
                        v-for="item in resourceOptionsByType[selectedStep.type] ?? []"
                        :key="item.id"
                        :label="item.name"
                        :value="item.id"
                      />
                    </ElSelect>
                  </ElFormItem>
                </ElForm>
              </ElCard>

              <!-- 执行配置（仅主机类步骤） -->
              <ElCard v-if="ANSIBLE_TYPES.has(selectedStep.type)" shadow="never" header="执行目标与方式">
                <ElForm label-width="110px">
                  <ElFormItem label="主机执行方式">
                    <ElSelect v-model="selectedStep.hostStrategy" :disabled="!editable" class="w-full">
                      <ElOption
                        v-for="item in HOST_STRATEGY_OPTIONS"
                        :key="item.value"
                        :label="item.label"
                        :value="item.value"
                      />
                    </ElSelect>
                    <div class="w-full text-12px text-gray-400">具体主机在「创建任务」时从资产选择</div>
                  </ElFormItem>
                  <ElFormItem v-if="selectedStep.hostStrategy === 'parallel'" label="并发数 forks">
                    <ElInputNumber
                      v-model="selectedStep.forks"
                      :min="1"
                      :max="100"
                      :disabled="!editable"
                      placeholder="留空使用引擎设置"
                    />
                  </ElFormItem>
                  <ElFormItem v-if="selectedStep.hostStrategy === 'rolling'" label="每批主机数">
                    <ElInputNumber
                      v-model="selectedStep.serialBatch"
                      :min="1"
                      :max="100"
                      :disabled="!editable"
                      placeholder="留空使用引擎设置"
                    />
                  </ElFormItem>
                  <ElFormItem label="演练模式">
                    <ElSwitch
                      v-model="selectedStep.checkMode"
                      :disabled="!editable || !selectedVersionSupportedCheck"
                    />
                    <span v-if="!selectedVersionSupportedCheck" class="ml-8px text-12px text-orange-500">
                      所选资源版本不支持 Check Mode
                    </span>
                  </ElFormItem>
                </ElForm>
              </ElCard>

              <!-- 策略 -->
              <ElCard shadow="never" header="超时与失败策略">
                <ElForm label-width="110px">
                  <ElFormItem label="超时（秒）">
                    <ElInputNumber v-model="selectedStep.timeoutSeconds" :min="1" :max="86400" :disabled="!editable" />
                  </ElFormItem>
                  <ElFormItem label="失败重试次数">
                    <ElInputNumber v-model="selectedStep.maxAttempts" :min="1" :max="10" :disabled="!editable" />
                    <span class="ml-8px text-12px text-gray-400">1 表示不重试</span>
                  </ElFormItem>
                  <ElFormItem label="失败策略">
                    <ElSelect v-model="selectedStep.failurePolicy" :disabled="!editable" class="w-full">
                      <ElOption
                        v-for="item in FAILURE_POLICY_OPTIONS"
                        :key="item.value"
                        :label="item.label"
                        :value="item.value"
                      />
                    </ElSelect>
                  </ElFormItem>
                </ElForm>
              </ElCard>

              <!-- 输入参数映射 -->
              <ElCard shadow="never" header="输入参数映射">
                <template #header>
                  <div class="flex items-center gap-8px">
                    <span>输入参数映射</span>
                    <ElTooltip placement="top">
                      <template #content>
                        支持 Jinja2 模板：&#123;&#123; inputs.参数名 &#125;&#125; 引用运行输入；
                        <br />
                        &#123;&#123; global.变量名 &#125;&#125; 引用全局变量；
                        <br />
                        &#123;&#123; nodes.步骤标识.outputs.输出名 &#125;&#125; 引用上游步骤输出。
                      </template>
                      <ElButton link size="small">语法说明</ElButton>
                    </ElTooltip>
                  </div>
                </template>
                <CodeEditor
                  v-model="selectedStep.inputMappingText"
                  language="plaintext"
                  :readonly="!editable"
                  height="160px"
                  placeholder='{"appName": "{{ inputs.appName }}"}'
                />
              </ElCard>

              <!-- 全局配置 -->
              <ElCard shadow="never">
                <template #header>
                  <span>全局配置（输入参数 Schema / 全局变量）</span>
                </template>
                <ElCollapse>
                  <ElCollapseItem name="schema">
                    <template #title>输入参数 Schema（创建任务时按此生成参数表单）</template>
                    <CodeEditor v-model="inputSchemaText" language="plaintext" :readonly="!editable" height="180px" />
                  </ElCollapseItem>
                  <ElCollapseItem name="vars">
                    <template #title>
                      全局变量（步骤中用
                      <span v-pre>{{ global.变量名 }}</span>
                      引用）
                    </template>
                    <CodeEditor v-model="globalVarsText" language="plaintext" :readonly="!editable" height="180px" />
                  </ElCollapseItem>
                </ElCollapse>
              </ElCard>
            </div>
          </ElCard>
        </ElCol>
      </ElRow>
    </template>
  </div>
</template>
