<script setup lang="ts">
import { computed, ref, shallowRef, watch } from 'vue';
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router';
import { useEventListener } from '@vueuse/core';
import {
  fetchGetApiEndpointList,
  fetchGetCommandList,
  fetchGetCommandVersions,
  fetchGetJenkinsJobList,
  fetchGetJenkinsJobParameters,
  fetchGetNotificationTemplateList,
  fetchGetWorkflowGraph,
  fetchGetWorkflowVersions,
  fetchPublishWorkflowVersion,
  fetchUpdateWorkflowGraph,
  fetchUpdateWorkflowVersion,
  fetchValidateWorkflowVersion
} from '@/service/api';
import CodeEditor from '@/components/common/code-editor/index.vue';
import {
  hasStepHostOverrides,
  nativeParameterConfig,
  nativeParameterError,
  nativeParameterField,
  nativeParameterText,
  stepHostConfig
} from './shared';

defineOptions({ name: 'TaskFlowDesign' });

const route = useRoute();
const router = useRouter();

/** ============ 步骤类型定义（v1 顺序编排能力边界） ============ */

type StepType = 'command' | 'script' | 'playbook' | 'module' | 'api' | 'jenkins' | 'notify';

const STEP_TYPES: { value: StepType; label: string; needHost: boolean }[] = [
  { value: 'script', label: '脚本', needHost: true },
  { value: 'playbook', label: 'Playbook', needHost: true },
  { value: 'module', label: 'Module', needHost: true },
  { value: 'api', label: 'API', needHost: false },
  { value: 'jenkins', label: 'Jenkins', needHost: false },
  { value: 'notify', label: '通知', needHost: false }
];

const STEP_TYPE_TEXT: Record<string, string> = {
  ...Object.fromEntries(STEP_TYPES.map(item => [item.value, item.label])),
  /** command 仅作旧命令类型的展示回退 */
  command: '命令'
};

const ANSIBLE_TYPES = new Set<StepType>(['command', 'script', 'playbook', 'module']);
const STEP_TYPE_SET = new Set<string>(STEP_TYPES.map(item => item.value));
/** 线性检测包含顺序执行节点类型 */
const LINEAR_ACCEPTED_TYPES = new Set<string>([...STEP_TYPE_SET, ...ANSIBLE_TYPES]);

const HOST_STRATEGY_OPTIONS = [
  { value: 'inherit', label: '继承任务设置' },
  { value: 'parallel', label: '并行' },
  { value: 'rolling', label: '滚动' },
  { value: 'serial', label: '串行' }
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
  hostPolicy: 'native' | 'platform';
  overrideHostSettings: boolean;
  maxFailPercentage: number | null;
  hostStrategy: 'inherit' | 'parallel' | 'rolling' | 'serial';
  forks: number | null;
  serialBatch: number | null;
  checkMode: boolean | 'inherit';
  /** 输入参数映射：值通常是字符串（含 Jinja2 表达式），也可能是历史数据中的对象/数组 */
  inputMapping: Record<string, unknown>;
  sourceConfig: Record<string, unknown>;
  nativeParametersText: string;
  outputExtractorsText: string;
  timeoutSeconds: number | null;
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
    hostPolicy: type === 'playbook' ? 'native' : 'platform',
    overrideHostSettings: false,
    maxFailPercentage: null,
    hostStrategy: 'inherit',
    forks: null,
    serialBatch: null,
    checkMode: 'inherit',
    inputMapping: {},
    sourceConfig: {},
    nativeParametersText: '',
    outputExtractorsText: '',
    timeoutSeconds: null,
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

const versionStatusTagType: Record<string, UI.ThemeColor> = {
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
    if (!LINEAR_ACCEPTED_TYPES.has(next.type)) {
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
  step.hostPolicy = config.hostPolicy === 'platform' ? 'platform' : 'native';
  step.overrideHostSettings = hasStepHostOverrides(config);
  step.maxFailPercentage = typeof config.maxFailPercentage === 'number' ? config.maxFailPercentage : null;
  step.hostStrategy = (config.hostStrategy as StepItem['hostStrategy']) ?? 'inherit';
  step.forks = (config.forks as number) ?? null;
  step.serialBatch = (config.serialBatch as number) ?? null;
  step.checkMode = typeof config.checkMode === 'boolean' ? config.checkMode : 'inherit';
  step.sourceConfig = { ...config };
  step.nativeParametersText = nativeParameterText(step.type, config);
  step.inputMapping = step.type === 'jenkins' ? { ...node.inputMapping } : {};
  step.outputExtractorsText =
    config.outputExtractors === undefined ? '' : JSON.stringify(config.outputExtractors, null, 2);
  step.timeoutSeconds = node.timeoutSeconds ?? null;
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
const activeConfigTab = ref<'step' | 'workflow'>('step');
const saving = ref(false);

const editable = computed(() => versionInfo.value?.status === 'draft' && isLinear.value);

/** 高级设置折叠面板：默认收起 */
const advancedOpen = ref<string[]>([]);

function selectStep(key: string) {
  selectedKey.value = key;
  activeConfigTab.value = 'step';
}

function addStep() {
  if (!editable.value || saving.value) return;
  const step = createStep('script');
  steps.value.push(step);
  selectedKey.value = step.key;
}

function removeStep(key: string) {
  if (!editable.value || saving.value) return;
  const index = steps.value.findIndex(step => step.key === key);
  if (index < 0) return;
  steps.value.splice(index, 1);
  if (selectedKey.value === key) {
    const next = steps.value[index] ?? steps.value[index - 1];
    selectedKey.value = next?.key ?? '';
  }
}

function copyStep(key: string) {
  if (!editable.value || saving.value) return;
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
  if (!editable.value || saving.value) return;
  const index = steps.value.findIndex(step => step.key === key);
  const target = index + offset;
  if (index < 0 || target < 0 || target >= steps.value.length) return;
  const [item] = steps.value.splice(index, 1);
  steps.value.splice(target, 0, item);
}

function onStepCommand(command: string, key: string) {
  switch (command) {
    case 'up':
      moveStep(key, -1);
      break;
    case 'down':
      moveStep(key, 1);
      break;
    case 'copy':
      copyStep(key);
      break;
    case 'delete':
      removeStep(key);
      break;
    default:
      break;
  }
}

/** ============ 参数映射（key-value 行编辑器） ============ */

interface MappingRow {
  key: string;
  value: string;
}

/** 映射对象 → 行数据：非字符串值转 JSON 文本以便编辑 */
function mappingToRows(mapping: Record<string, unknown> | undefined): MappingRow[] {
  if (!mapping) return [];
  return Object.entries(mapping).map(([key, value]) => ({
    key,
    value: typeof value === 'string' ? value : JSON.stringify(value)
  }));
}

/** 是否疑似 JSON 文本：排除 Jinja2 模板 {{ ... }} / {% ... %} 等以花括号开头但并非 JSON 的写法 */
function looksLikeJsonText(value: string): boolean {
  const text = value.trim();
  if (text.startsWith('{{') || text.startsWith('{%')) return false;
  return text.startsWith('{') || text.startsWith('[');
}

/** 行值解析：以 { / [ 开头的合法 JSON 还原为对象，其余一律存字符串 */
function parseRowValue(value: string): unknown {
  const text = value.trim();
  if (looksLikeJsonText(text)) {
    try {
      return JSON.parse(text);
    } catch {
      // 非法 JSON 保留字符串，由校验项提示
    }
  }
  return value;
}

/** 行数据 → 映射对象：空变量名行跳过 */
function rowsToMapping(rows: MappingRow[]): Record<string, unknown> {
  const result: Record<string, unknown> = {};
  for (const row of rows) {
    const key = row.key.trim();
    if (key) {
      result[key] = parseRowValue(row.value);
    }
  }
  return result;
}

/** 值形如 JSON 对象/数组但解析失败 */
function rowValueIsBrokenJson(value: string): boolean {
  const text = value.trim();
  if (!looksLikeJsonText(text)) return false;
  try {
    JSON.parse(text);
    return false;
  } catch {
    return true;
  }
}

function mappingHasBrokenJson(mapping: Record<string, unknown> | undefined): boolean {
  return Object.values(mapping ?? {}).some(value => typeof value === 'string' && rowValueIsBrokenJson(value));
}

/** 行数据即选中步骤映射的编辑视图，双向同步 */
const mappingRows = ref<MappingRow[]>([]);
const syncingMappingRows = ref(false);

watch(
  () => selectedStep.value?.key,
  () => {
    syncingMappingRows.value = true;
    mappingRows.value = mappingToRows(selectedStep.value?.inputMapping);
    syncingMappingRows.value = false;
  },
  { immediate: true }
);

watch(
  mappingRows,
  rows => {
    if (syncingMappingRows.value || selectedStep.value?.type !== 'jenkins') return;
    selectedStep.value.inputMapping = rowsToMapping(rows);
  },
  { deep: true }
);

function onStepTypeChange() {
  if (!editable.value || saving.value) return;
  const step = selectedStep.value;
  if (!step) return;
  step.commandId = null;
  step.commandVersionId = null;
  step.resourceId = null;
  step.hostPolicy = step.type === 'playbook' ? 'native' : 'platform';
  step.overrideHostSettings = false;
  step.hostStrategy = 'inherit';
  step.forks = null;
  step.serialBatch = null;
  step.maxFailPercentage = null;
  step.checkMode = 'inherit';
  step.sourceConfig = {};
  step.nativeParametersText = '';
  step.inputMapping = {};
  mappingRows.value = [];
}

function addMappingRow() {
  if (!editable.value || saving.value) return;
  mappingRows.value.push({ key: '', value: '' });
}

function removeMappingRow(index: number) {
  if (!editable.value || saving.value) return;
  mappingRows.value.splice(index, 1);
}

const mappingRowsError = computed(() => mappingRows.value.some(row => rowValueIsBrokenJson(row.value)));

/** ============ Jenkins 参数自动带出（探测资源定义的构建参数） ============ */

const jenkinsParamCache = shallowRef(new Map<number, Api.Automation.JenkinsJobParameter[]>());
const jenkinsParamLoading = ref(false);

/** 当前任务无映射行时，按该任务参数自动带出参数名并预填 Jenkins 默认值 */
function applyJenkinsParamDefaults(resourceId: number) {
  const data = jenkinsParamCache.value.get(resourceId);
  if (!data?.length) return;
  if (
    editable.value &&
    selectedStep.value?.type === 'jenkins' &&
    selectedStep.value.resourceId === resourceId &&
    !mappingRows.value.length
  ) {
    mappingRows.value = data.map(param => ({
      key: param.name,
      value: param.default === null ? '' : String(param.default)
    }));
  }
}

async function loadJenkinsParameters(resourceId: number, force = false) {
  if (!force && jenkinsParamCache.value.has(resourceId)) {
    applyJenkinsParamDefaults(resourceId);
    return;
  }
  jenkinsParamLoading.value = true;
  const { data, error } = await fetchGetJenkinsJobParameters(resourceId);
  jenkinsParamLoading.value = false;
  if (!error && data) {
    const next = new Map(jenkinsParamCache.value);
    next.set(resourceId, data);
    jenkinsParamCache.value = next;
    applyJenkinsParamDefaults(resourceId);
  }
}

/** 强制重新探测当前 Jenkins 任务的参数定义（不覆盖已填的映射行） */
function reloadJenkinsParams() {
  if (selectedStep.value?.type !== 'jenkins' || typeof selectedStep.value.resourceId !== 'number') return;
  loadJenkinsParameters(selectedStep.value.resourceId, true);
}

watch(
  () => [selectedStep.value?.type, selectedStep.value?.resourceId] as const,
  ([type, resourceId], [prevType, prevResourceId]) => {
    if (type === 'jenkins' && typeof resourceId === 'number') {
      // 切换到不同 Jenkins 任务时清空上一任务的参数映射，避免残留旧参数
      if (editable.value && resourceId !== prevResourceId && prevType === 'jenkins') {
        mappingRows.value = [];
      }
      loadJenkinsParameters(resourceId);
    }
  }
);

const jenkinsParamDefinitions = computed(() => {
  if (selectedStep.value?.type !== 'jenkins' || typeof selectedStep.value.resourceId !== 'number') return [];
  return jenkinsParamCache.value.get(selectedStep.value.resourceId) ?? [];
});

const jenkinsParamNames = computed(() => jenkinsParamDefinitions.value.map(param => param.name));

const jenkinsMissingParams = computed(() => {
  const filled = new Set(mappingRows.value.map(row => row.key.trim()).filter(Boolean));
  return jenkinsParamNames.value.filter(name => !filled.has(name));
});

/** 当前映射行对应 Jenkins 参数的选项列表；choice 类型参数值列渲染为下拉 */
function rowChoices(rowIndex: number): string[] {
  const row = mappingRows.value[rowIndex];
  if (selectedStep.value?.type !== 'jenkins' || !row) return [];
  const definition = jenkinsParamDefinitions.value.find(param => param.name === row.key.trim());
  return definition?.choices ?? [];
}

/** 按 Jenkins 参数定义补齐缺失的参数名，值默认填 Jenkins 侧默认值 */
function fillMissingJenkinsParams() {
  if (!editable.value || saving.value || !jenkinsMissingParams.value.length) return;
  const definitions = jenkinsParamDefinitions.value;
  const rows = [...mappingRows.value];
  for (const name of jenkinsMissingParams.value) {
    const definition = definitions.find(param => param.name === name);
    const fallback = definition?.default ?? null;
    rows.push({ key: name, value: fallback === null ? '' : String(fallback) });
  }
  mappingRows.value = rows;
}

/** 变量名自动补全候选：Jenkins 类型来自参数探测，其他类型无候选 */
function queryMappingKeySuggestions(query: string, cb: (items: { value: string }[]) => void) {
  const keyword = query.trim().toLowerCase();
  cb(
    jenkinsParamNames.value
      .filter(name => !keyword || name.toLowerCase().includes(keyword))
      .map(name => ({ value: name }))
  );
}

/** 步骤缺失项检测：列表小红点提示，保存前即可发现 */
function stepIssues(step: StepItem): string[] {
  const issues: string[] = [];
  if (ANSIBLE_TYPES.has(step.type)) {
    if (!step.commandId) {
      issues.push('未绑定自动化资源');
    } else if (!step.commandVersionId) {
      issues.push('未选择资源版本');
    }
  } else if (!step.resourceId) {
    issues.push('未选择引用资源');
  }
  if (mappingHasBrokenJson(step.inputMapping)) {
    issues.push('步骤参数存在非法 JSON 值');
  }
  if (nativeParameterError(step.type, step.nativeParametersText)) issues.push('原生参数格式无效');
  return issues;
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
  if (!apiRes.error) apiOptions.value = apiRes.data.records.filter(item => item.isActive);
  if (!jenkinsRes.error) jenkinsOptions.value = jenkinsRes.data.records.filter(item => item.isActive);
  if (!notifyRes.error) notifyOptions.value = notifyRes.data.records.filter(item => item.isActive);

  const boundIds = new Set(steps.value.filter(step => step.commandId).map(step => step.commandId as number));
  await Promise.all([...boundIds].map(commandId => ensureCommandVersions(commandId)));
}

const resourceOptionsByType = computed<Record<string, { id: number; name: string }[]>>(() => ({
  api: apiOptions.value.map(item => ({ id: item.id, name: item.name })),
  jenkins: jenkinsOptions.value.map(item => ({ id: item.id, name: `${item.serverName} / ${item.name}` })),
  notify: notifyOptions.value.map(item => ({ id: item.id, name: item.name }))
}));

function onStepResourceChange() {
  if (!selectedStep.value) return;
  selectedStep.value.commandVersionId = null;
  selectedStep.value.checkMode = 'inherit';
}

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

const selectedResourceVersion = computed(() => {
  const step = selectedStep.value;
  return step ? commandVersionsOf(step.commandId).find(item => item.id === step.commandVersionId) : undefined;
});

const selectedVersionSupportedCheck = computed(() => {
  const step = selectedStep.value;
  if (!step || !ANSIBLE_TYPES.has(step.type) || !step.commandVersionId) return true;
  const version = commandVersionsOf(step.commandId).find(item => item.id === step.commandVersionId);
  return version ? version.checkModeSupported : true;
});

/** 参数映射仅对执行器真正消费 inputMapping 的步骤展示：ansible 类（注入 extra_vars）与 jenkins（构建参数） */
const mappingSupported = computed(() => {
  const step = selectedStep.value;
  return step?.type === 'jenkins';
});

/** ============ 全局配置（版本级，内联在基本信息卡的高级配置折叠中） ============ */

const inputSchemaText = ref('');

/** ============ 变量选择器（inputs.xxx 占位符插入） ============ */

/** 解析任务单参数 Schema fields 数组中的字段名；非法 JSON 返回空（不阻塞输入） */
function schemaKeys(text: string): string[] {
  try {
    const parsed = JSON.parse(text || '{}') as { fields?: unknown };
    if (!Array.isArray(parsed.fields)) return [];
    return parsed.fields
      .map(field =>
        field && typeof field === 'object' && typeof (field as { name?: unknown }).name === 'string'
          ? (field as { name: string }).name
          : ''
      )
      .filter(Boolean);
  } catch {
    return [];
  }
}

const variableCandidates = computed(() =>
  schemaKeys(inputSchemaText.value).map(key => ({ label: `inputs.${key}`, value: `{{ inputs.${key} }}` }))
);

/** 已声明的任务单参数字段数（header 入口徽标用） */
const declaredFieldCount = computed(() => schemaKeys(inputSchemaText.value).length);

function insertVariable(rowIndex: number, snippet: string) {
  if (!editable.value || saving.value) return;
  const row = mappingRows.value[rowIndex];
  if (!row) return;
  row.value = row.value ? `${row.value}${snippet}` : snippet;
}

function prettyJson(value: unknown): string {
  if (!value || (typeof value === 'object' && Object.keys(value as object).length === 0)) return '';
  return JSON.stringify(value, null, 2);
}

/** ============ 未保存变更检测 ============ */

const stepsSnapshot = ref('');
const textsSnapshot = ref('');

const stepsDirty = computed(() => JSON.stringify(steps.value) !== stepsSnapshot.value);
const textsDirty = computed(() => inputSchemaText.value !== textsSnapshot.value);
const isDirty = computed(() => editable.value && (stepsDirty.value || textsDirty.value));

function syncStepsSnapshot() {
  stepsSnapshot.value = JSON.stringify(steps.value);
}

function syncTextsSnapshot() {
  textsSnapshot.value = inputSchemaText.value;
}

onBeforeRouteLeave(async () => {
  if (!isDirty.value) return true;
  try {
    await ElMessageBox.confirm('步骤编排有未保存的修改，离开将丢失这些修改。', '未保存提醒', {
      type: 'warning',
      confirmButtonText: '放弃修改并离开',
      cancelButtonText: '留在本页'
    });
    return true;
  } catch {
    return false;
  }
});

useEventListener(window, 'beforeunload', event => {
  if (!isDirty.value) return;
  event.preventDefault();
  event.returnValue = '';
});

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

/** JSON 编辑即时校验：返回错误文案，空串表示合法/为空 */
function jsonErrorText(text: string | undefined): string {
  const trimmed = (text ?? '').trim();
  if (!trimmed) return '';
  try {
    parseJsonObject(trimmed);
    return '';
  } catch {
    return '不是合法的 JSON 对象';
  }
}

const inputSchemaError = computed(() => jsonErrorText(inputSchemaText.value));

function stepToNode(step: StepItem, inputMapping: Record<string, unknown>): Api.Automation.GraphNode {
  const node: Api.Automation.GraphNode = {
    id: step.key,
    name: step.name || step.key,
    type: step.type,
    inputMapping: step.type === 'jenkins' ? inputMapping : {},
    failurePolicy: step.failurePolicy,
    timeoutSeconds: step.timeoutSeconds ?? null
  };
  if (step.maxAttempts > 1) {
    node.retryPolicy = { maxAttempts: step.maxAttempts };
  }
  if (ANSIBLE_TYPES.has(step.type)) {
    node.commandVersionId = step.commandVersionId;
    const managedKeys = new Set([
      'outputExtractors',
      'hostPolicy',
      'maxFailPercentage',
      'hostStrategy',
      'forks',
      'serialBatch',
      'checkMode',
      'environment',
      'extraVars',
      'args',
      'moduleArgs'
    ]);
    const config: Record<string, unknown> = {
      ...Object.fromEntries(Object.entries(step.sourceConfig).filter(([key]) => !managedKeys.has(key))),
      ...nativeParameterConfig(step.type, step.nativeParametersText),
      ...stepHostConfig(step.type, step)
    };
    if (step.outputExtractorsText.trim()) config.outputExtractors = JSON.parse(step.outputExtractorsText);
    if (step.checkMode !== 'inherit') config.checkMode = step.checkMode;
    if (Object.keys(config).length) node.config = config;
  } else if (step.resourceId) {
    if (Object.keys(step.sourceConfig).length) node.config = { ...step.sourceConfig };
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

const saveErrors = ref<string[]>([]);
const validationIssues = computed(() =>
  saveErrors.value.map(message => {
    const normalizedMessage = message.toLocaleLowerCase();
    const step = steps.value.find(
      item =>
        normalizedMessage.includes(item.key.toLocaleLowerCase()) ||
        normalizedMessage.includes(item.name.toLocaleLowerCase())
    );
    return { message, stepKey: step?.key ?? null };
  })
);

function focusValidationStep(stepKey: string | null) {
  if (!stepKey) return;
  selectedKey.value = stepKey;
  activeConfigTab.value = 'step';
}

function collectSavePayload() {
  let inputSchema: Record<string, unknown>;
  try {
    inputSchema = parseJsonObject(inputSchemaText.value);
  } catch {
    window.$message?.error('任务单参数 Schema 不是合法 JSON 对象');
    return null;
  }
  const mappings: Record<string, Record<string, unknown>> = {};
  for (const step of steps.value) {
    if (mappingHasBrokenJson(step.inputMapping)) {
      window.$message?.error(`步骤「${step.name}」的步骤参数存在非法 JSON 值`);
      selectedKey.value = step.key;
      return null;
    }
    try {
      nativeParameterConfig(step.type, step.nativeParametersText);
    } catch {
      window.$message?.error(`步骤「${step.name}」的原生参数格式无效，请填写 JSON 对象`);
      selectedKey.value = step.key;
      advancedOpen.value = ['advanced'];
      return null;
    }
    if (step.outputExtractorsText.trim()) {
      try {
        const rules: unknown = JSON.parse(step.outputExtractorsText);
        if (!Array.isArray(rules)) throw new Error('输出提取规则必须为数组');
      } catch {
        window.$message?.error(`步骤「${step.name}」的输出提取规则必须为有效 JSON 数组`);
        selectedKey.value = step.key;
        return null;
      }
    }
    mappings[step.key] = step.inputMapping ?? {};
  }
  return { inputSchema, mappings };
}

async function saveDraft(publishAfter = false): Promise<boolean> {
  if (!editable.value || !versionInfo.value || saving.value) return false;
  if (!steps.value.length) {
    window.$message?.warning('请先添加至少一个步骤');
    return false;
  }
  const payload = collectSavePayload();
  if (!payload) return false;
  const versionId = versionInfo.value.id;
  const submittedStepsSnapshot = JSON.stringify(steps.value);
  const submittedTextsSnapshot = inputSchemaText.value;
  // 参数映射可能含响应式嵌套对象，提交载荷必须拥有独立快照。
  const graph: Api.Automation.WorkflowGraph = JSON.parse(JSON.stringify(buildGraph(payload.mappings)));

  saving.value = true;
  try {
    const { data, error } = await fetchUpdateWorkflowGraph(versionId, graph);
    if (error || !data) return false;
    if (!data.valid) {
      saveErrors.value = data.errors;
      window.$message?.error('保存失败：流程结构校验未通过');
      return false;
    }
    saveErrors.value = [];
    const { error: patchError } = await fetchUpdateWorkflowVersion(versionId, {
      inputSchema: payload.inputSchema
    });
    if (patchError) return false;
    stepsSnapshot.value = submittedStepsSnapshot;
    textsSnapshot.value = submittedTextsSnapshot;
    window.$notification?.success('草稿已保存');
    if (publishAfter) {
      if (isDirty.value) {
        window.$message?.warning('保存期间内容发生变化，请重新保存后再发布');
        return false;
      }
      return await publishCurrent();
    }
    return true;
  } finally {
    saving.value = false;
  }
}

/** 任务单参数没有独立保存入口：随「保存草稿」统一提交（saveDraft 内含 inputSchema） */

async function onValidate() {
  if (!versionInfo.value || saving.value) return;
  if (editable.value && isDirty.value) {
    const saved = await saveDraft(false);
    if (!saved || isDirty.value) return;
  }
  saving.value = true;
  try {
    const { data, error } = await fetchValidateWorkflowVersion(versionInfo.value.id);
    if (!error && data) {
      if (data.valid) {
        saveErrors.value = [];
        window.$notification?.success('校验通过，可以发布');
      } else {
        saveErrors.value = data.errors;
      }
    }
  } finally {
    saving.value = false;
  }
}

async function publishCurrent() {
  if (!versionInfo.value) return false;
  const { data, error } = await fetchPublishWorkflowVersion(versionInfo.value.id);
  if (!error && data) {
    versionInfo.value = data;
    window.$notification?.success(`v${data.version} 已发布，同模板旧发布版本已自动归档`);
    return true;
  }
  return false;
}

async function onPublish() {
  if (!editable.value || !versionInfo.value || saving.value) return;
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
    // 版本信息与流程图并行请求，全部返回后在同一 tick 统一应用，避免基本信息先渲染、步骤后渲染的闪动
    const [versionsRes, graphRes] = await Promise.all([
      fetchGetWorkflowVersions(templateId as number),
      fetchGetWorkflowGraph(targetVersionId as number)
    ]);
    if (versionsRes.error || !versionsRes.data) return;
    const current = versionsRes.data.find(item => item.id === targetVersionId);
    if (!current) {
      window.$message?.error('未找到指定的流程版本');
      return;
    }
    if (graphRes.error || !graphRes.data) return;
    const graph = graphRes.data.graph;

    versionInfo.value = current;
    graphData.value = graph;
    inputSchemaText.value = prettyJson(graph.inputSchema);
    syncTextsSnapshot();

    const analysis = analyzeGraph(graph);
    isLinear.value = analysis.linear;
    structureReason.value = analysis.reason;
    if (!analysis.linear) return;

    steps.value = extractSteps(graph);
    selectedKey.value = steps.value[0]?.key ?? '';
    syncStepsSnapshot();
    await loadResourceOptions();
  } finally {
    pageLoading.value = false;
  }
}

if (!missingParams.value) {
  init();
}

function backToTemplates() {
  router.push({ name: 'task_templates' });
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
  <div class="h-full min-h-560px flex flex-col gap-12px overflow-y-auto">
    <!-- 缺少参数引导 -->
    <ElCard v-if="missingParams" class="shrink-0 card-wrapper">
      <ElEmpty description="请从「流程模板」页选择某个草稿版本进入步骤编排">
        <ElButton type="primary" @click="backToTemplates">前往流程模板</ElButton>
      </ElEmpty>
    </ElCard>

    <template v-else>
      <!-- 紧凑版本栏：身份、状态与主操作同处一行 -->
      <ElCard class="shrink-0 card-wrapper">
        <template #header>
          <div class="flex flex-wrap items-center justify-between gap-12px">
            <div class="min-w-0 flex flex-wrap items-center gap-12px">
              <div class="min-w-0">
                <div class="truncate text-16px font-600">{{ versionInfo?.workflowName || '流程编排' }}</div>
                <div class="mt-4px text-12px text-gray-500">流程模板 · 版本 v{{ versionInfo?.version }}</div>
              </div>
              <ElTag size="small" :type="versionStatusTagType[versionInfo?.status ?? ''] ?? 'info'">
                {{ versionStatusText[versionInfo?.status ?? ''] ?? versionInfo?.status }}
              </ElTag>
              <ElTag v-if="!isLinear" size="small" type="danger">结构不支持步骤编辑</ElTag>
              <ElTag v-else-if="!editable" size="small" type="warning">只读版本</ElTag>
            </div>
            <div class="flex items-center gap-8px">
              <ElButton @click="backToTemplates">返回模板</ElButton>
              <ElButton v-if="editable" type="primary" plain :loading="saving" @click="onPublish">发布版本</ElButton>
            </div>
          </div>
        </template>
        <div v-loading="pageLoading" class="flex flex-wrap items-center justify-between gap-8px text-13px">
          <span class="text-gray-500">按顺序配置流程步骤；运行目标在发起执行时从资产中确定。</span>
          <span v-if="editable" class="text-gray-500">资源版本在发布时固定，运行时使用版本快照。</span>
        </div>
      </ElCard>

      <!-- 校验错误 -->
      <ElAlert v-if="saveErrors.length" class="shrink-0" type="error" :closable="true" @close="saveErrors = []">
        <template #title>以下问题需要处理：</template>
        <ul class="m-0 list-inside pl-4px">
          <li v-for="(item, index) in validationIssues" :key="index" class="mb-4px">
            <span>{{ item.message }}</span>
            <ElButton
              v-if="item.stepKey"
              link
              type="primary"
              size="small"
              class="ml-8px"
              @click="focusValidationStep(item.stepKey)"
            >
              定位步骤
            </ElButton>
          </li>
        </ul>
      </ElAlert>

      <!-- 非线性结构：只读查看 -->
      <template v-if="!isLinear">
        <ElAlert
          class="shrink-0"
          type="warning"
          :closable="false"
          :title="`当前步骤编辑器不支持此流程结构：${structureReason}。以下为只读查看，不会修改流程。`"
        />

        <div class="grid shrink-0 gap-16px lg:grid-cols-2">
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
                <template #default="{ row }">{{ row.timeoutSeconds ?? '继承资源' }}</template>
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

      <!-- 步骤编排器：左步骤列表 + 右分组配置 -->
      <div v-else class="flex shrink-0 items-stretch gap-16px lt-lg:flex-col">
        <!-- 左：步骤列表 -->
        <ElCard class="w-360px shrink-0 card-wrapper lt-lg:w-full" shadow="never">
          <template #header>
            <div class="flex items-center justify-between">
              <p>步骤列表</p>
              <ElTag size="small" type="info">{{ steps.length }} 个步骤</ElTag>
            </div>
          </template>
          <div class="flex flex-col gap-8px">
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
                  <ElTooltip v-if="editable && stepIssues(step).length" placement="top">
                    <template #content>
                      <div v-for="issue in stepIssues(step)" :key="issue">{{ issue }}</div>
                    </template>
                    <ElTag size="small" type="warning">待完善 {{ stepIssues(step).length }} 项</ElTag>
                  </ElTooltip>
                </div>
                <ElDropdown
                  v-if="editable"
                  :disabled="saving"
                  trigger="click"
                  @command="onStepCommand($event, step.key)"
                >
                  <ElButton link size="small" class="!h-32px !min-w-48px" @click.stop>更多 ∨</ElButton>
                  <template #dropdown>
                    <ElDropdownMenu>
                      <ElDropdownItem command="up" :disabled="index === 0">上移步骤</ElDropdownItem>
                      <ElDropdownItem command="down" :disabled="index === steps.length - 1">下移步骤</ElDropdownItem>
                      <ElDropdownItem command="copy">复制步骤</ElDropdownItem>
                      <ElDropdownItem divided command="delete">删除步骤</ElDropdownItem>
                    </ElDropdownMenu>
                  </template>
                </ElDropdown>
              </div>
              <div class="mt-6px pl-28px text-12px text-gray-500">
                <div class="truncate">{{ resourceText(step) }}</div>
                <div v-if="ANSIBLE_TYPES.has(step.type)" class="truncate">执行目标：发起时确定</div>
              </div>
            </div>

            <ElButton v-if="editable && steps.length" :disabled="saving" class="w-full" @click="addStep">
              添加步骤
            </ElButton>
            <ElEmpty v-if="!steps.length" description="该版本暂无步骤" :image-size="80">
              <ElButton v-if="editable" type="primary" :disabled="saving" @click="addStep">添加第一个步骤</ElButton>
            </ElEmpty>
          </div>
        </ElCard>

        <!-- 右：步骤配置（分组页签 + 吸底保存） -->
        <ElCard class="min-w-0 flex-1 card-wrapper" shadow="never">
          <template #header>
            <div class="flex flex-wrap items-center justify-between gap-8px">
              <div class="flex items-center gap-8px">
                <span class="text-15px font-600">
                  {{ activeConfigTab === 'workflow' ? '任务单参数' : '步骤配置' }}
                </span>
                <span v-if="activeConfigTab === 'step' && selectedStep" class="text-12px text-gray-500">
                  标识：{{ selectedStep.key }}
                </span>
                <span v-else-if="activeConfigTab === 'workflow'" class="text-12px text-gray-500">
                  仅「每次运行取值不同」的变量需要声明，值固定的写在资源默认变量即可
                </span>
              </div>
              <ElButton
                v-if="activeConfigTab === 'step'"
                link
                type="primary"
                :disabled="saving"
                @click="activeConfigTab = 'workflow'"
              >
                任务单参数{{ declaredFieldCount ? `（${declaredFieldCount}）` : '' }}
              </ElButton>
              <ElButton v-else link type="primary" :disabled="saving" @click="activeConfigTab = 'step'">
                返回步骤配置
              </ElButton>
            </div>
          </template>

          <template v-if="activeConfigTab === 'step'">
            <ElEmpty v-if="!selectedStep" description="选择左侧步骤进行配置，或添加新步骤">
              <ElButton v-if="editable" type="primary" :disabled="saving" @click="addStep">添加步骤</ElButton>
            </ElEmpty>
            <div v-else class="min-h-0 flex flex-col overflow-auto">
              <ElForm label-width="110px" label-suffix="：" require-asterisk-position="left" class="max-w-640px py-8px">
                <ElFormItem label="步骤名称">
                  <ElInput v-model="selectedStep.name" :disabled="!editable || saving" placeholder="如：前置检查" />
                </ElFormItem>
                <ElFormItem label="步骤类型">
                  <ElRadioGroup
                    v-if="STEP_TYPE_SET.has(selectedStep.type)"
                    v-model="selectedStep.type"
                    :disabled="!editable || saving"
                    @change="onStepTypeChange"
                  >
                    <ElRadio v-for="item in STEP_TYPES" :key="item.value" :value="item.value">
                      {{ item.label }}
                    </ElRadio>
                  </ElRadioGroup>
                  <ElTag v-else size="small" type="info">
                    {{ STEP_TYPE_TEXT[selectedStep.type] ?? selectedStep.type }}
                  </ElTag>
                  <div v-if="editable" class="w-full text-12px text-gray-500">切换类型会清空已绑定的资源</div>
                </ElFormItem>

                <!-- 资源绑定 -->
                <template v-if="ANSIBLE_TYPES.has(selectedStep.type)">
                  <ElFormItem label="选择资源">
                    <ElSelect
                      v-model="selectedStep.commandId"
                      :disabled="!editable || saving"
                      filterable
                      clearable
                      placeholder="选择执行资源"
                      class="w-full"
                      @change="onStepResourceChange"
                    >
                      <ElOption
                        v-for="item in commandOptions.filter(cmd => cmd.resourceKind === selectedStep?.type)"
                        :key="item.id"
                        :label="`${item.name}（${item.code}）`"
                        :value="item.id"
                      />
                    </ElSelect>
                    <div class="w-full text-12px text-gray-500">发布时固定引用所选版本，运行时使用快照</div>
                  </ElFormItem>
                  <ElFormItem label="资源版本">
                    <ElSelect
                      v-model="selectedStep.commandVersionId"
                      :disabled="!editable || saving || !selectedStep.commandId"
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
                    :disabled="!editable || saving"
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

                <ElFormItem
                  v-if="selectedStep.type === 'module' && selectedResourceVersion?.parameterDocs?.length"
                  label="模块参数参考"
                >
                  <dl class="m-0 w-full flex flex-col gap-8px">
                    <div v-for="item in selectedResourceVersion.parameterDocs" :key="item.name" class="flex gap-12px">
                      <dt class="w-120px shrink-0 break-all font-mono">{{ item.name }}</dt>
                      <dd class="m-0 min-w-0 flex-1 break-words">{{ item.description }}</dd>
                    </div>
                  </dl>
                </ElFormItem>

                <!-- Jenkins 构建参数 -->
                <ElFormItem v-if="mappingSupported">
                  <template #label>
                    <span>构建参数</span>
                    <ElTooltip placement="top">
                      <template #content>
                        每行作为 Jenkins 构建参数提交。
                        <br />
                        值支持 Jinja2 表达式：&#123;&#123; inputs.变量名 &#125;&#125; 引用任务单参数；
                        <br />
                        &#123;&#123; nodes.步骤标识.outputs.输出名 &#125;&#125;
                        引用单主机步骤输出；多主机步骤请按主机读取 outputs.hosts 中的 outputs。
                      </template>
                      <icon-mdi-help-circle-outline class="ml-4px text-14px text-gray-500" />
                    </ElTooltip>
                  </template>
                  <div class="w-full flex flex-col gap-6px">
                    <div v-if="!mappingRows.length" class="text-12px text-gray-500">
                      {{
                        selectedStep.type === 'jenkins' && jenkinsParamLoading
                          ? '正在获取 Jenkins 参数定义…'
                          : '暂无构建参数，点击下方按钮添加'
                      }}
                    </div>
                    <div v-for="(row, index) in mappingRows" :key="index" class="flex items-center gap-6px">
                      <ElAutocomplete
                        v-model="row.key"
                        :fetch-suggestions="queryMappingKeySuggestions"
                        :trigger-on-focus="true"
                        :disabled="!editable || saving"
                        placeholder="变量名"
                        class="w-180px shrink-0"
                      />
                      <ElSelect
                        v-if="rowChoices(index).length"
                        v-model="row.value"
                        :disabled="!editable || saving"
                        filterable
                        allow-create
                        default-first-option
                        placeholder="选择值或填表达式"
                        class="flex-1"
                        :class="{ 'is-error': rowValueIsBrokenJson(row.value) }"
                      >
                        <ElOption v-for="choice in rowChoices(index)" :key="choice" :value="choice" :label="choice" />
                      </ElSelect>
                      <ElInput
                        v-else
                        v-model="row.value"
                        :disabled="!editable || saving"
                        placeholder="值或表达式"
                        class="flex-1"
                        :class="{ 'is-error': rowValueIsBrokenJson(row.value) }"
                      />
                      <ElDropdown
                        trigger="click"
                        :disabled="!editable || saving || !variableCandidates.length"
                        @command="(snippet: string) => insertVariable(index, snippet)"
                      >
                        <ElButton link :disabled="!editable || saving || !variableCandidates.length">插入变量</ElButton>
                        <template #dropdown>
                          <ElDropdownMenu>
                            <ElDropdownItem
                              v-for="candidate in variableCandidates"
                              :key="candidate.label"
                              :command="candidate.value"
                            >
                              {{ candidate.label }}
                            </ElDropdownItem>
                          </ElDropdownMenu>
                        </template>
                      </ElDropdown>
                      <ElButton link type="danger" :disabled="!editable || saving" @click="removeMappingRow(index)">
                        删除
                      </ElButton>
                    </div>
                    <div class="flex items-center gap-8px">
                      <ElButton size="small" :disabled="!editable || saving" @click="addMappingRow">
                        ＋ 添加参数
                      </ElButton>
                      <ElButton
                        v-if="selectedStep.type === 'jenkins' && jenkinsMissingParams.length"
                        size="small"
                        :loading="jenkinsParamLoading"
                        :disabled="!editable || saving"
                        @click="fillMissingJenkinsParams"
                      >
                        按 Jenkins 参数补齐（{{ jenkinsMissingParams.length }}）
                      </ElButton>
                      <ElButton
                        v-if="selectedStep.type === 'jenkins'"
                        size="small"
                        :loading="jenkinsParamLoading"
                        :disabled="!editable || saving"
                        @click="reloadJenkinsParams"
                      >
                        重新探测参数
                      </ElButton>
                    </div>
                    <div v-if="mappingRowsError" class="text-12px text-red-500">存在非法 JSON 值，保存前需修正</div>
                  </div>
                </ElFormItem>
              </ElForm>

              <!-- 高级配置（默认收起，样式与执行资源-脚本的高级配置一致） -->
              <ElCollapse v-model="advancedOpen" class="advanced-collapse max-w-640px">
                <ElCollapseItem name="advanced" title="高级配置">
                  <ElForm label-width="180px" label-suffix="：" require-asterisk-position="left">
                    <ElFormItem
                      v-if="nativeParameterField(selectedStep.type)"
                      :error="nativeParameterError(selectedStep.type, selectedStep.nativeParametersText)"
                      :label="
                        selectedStep.type === 'playbook'
                          ? 'extra_vars（可选）'
                          : selectedStep.type === 'module'
                            ? '模块参数'
                            : '环境变量（可选）'
                      "
                    >
                      <div class="w-full">
                        <ElInput
                          v-model="selectedStep.nativeParametersText"
                          type="textarea"
                          :rows="4"
                          :disabled="!editable || saving"
                          :placeholder="
                            selectedStep.type === 'module'
                              ? 'name=nginx state=started，或 JSON 对象'
                              : 'JSON 对象，例如 {&quot;version&quot;: &quot;v1&quot;}'
                          "
                        />
                        <p class="mb-0 mt-6px text-12px text-[var(--el-text-color-regular)]">
                          {{
                            selectedStep.type === 'playbook'
                              ? '直接交给 Ansible 作为 extra_vars，保留原生 Jinja 语法。任务单参数会自动传入；此处同名值将覆盖任务单参数。'
                              : selectedStep.type === 'module'
                                ? '使用 Ansible 原生模块参数写法。'
                                : '脚本通过 $变量名 读取，值支持字符串、数字和布尔值。任务单参数会自动注入；此处同名值将覆盖任务单参数。'
                          }}
                        </p>
                      </div>
                    </ElFormItem>
                    <ElFormItem v-if="ANSIBLE_TYPES.has(selectedStep.type)" label="输出提取（可选）">
                      <div class="w-full">
                        <ElInput
                          v-model="selectedStep.outputExtractorsText"
                          type="textarea"
                          :rows="3"
                          :disabled="!editable || saving"
                          placeholder='JSON 数组，例如 [{"name":"release","pattern":"RELEASE=(.*)"}]'
                        />
                        <p class="mb-0 mt-6px text-12px text-[var(--el-text-color-regular)]">
                          从本步骤的主机标准输出中提取变量，供后续步骤引用。留空兼容资源原有规则，填写 [] 则关闭提取。
                        </p>
                      </div>
                    </ElFormItem>
                    <template v-if="ANSIBLE_TYPES.has(selectedStep.type)">
                      <ElFormItem v-if="selectedStep.type === 'playbook'" label="主机策略来源">
                        <div class="w-full">
                          <ElRadioGroup v-model="selectedStep.hostPolicy" :disabled="!editable || saving">
                            <ElRadio value="native">Playbook 原生策略</ElRadio>
                            <ElRadio value="platform">平台执行策略</ElRadio>
                          </ElRadioGroup>
                          <p class="mb-0 mt-6px text-12px text-[var(--el-text-color-regular)]">
                            原生策略保留 Playbook 中的 serial、失败比例与失败处理；平台策略使用任务运行设置。
                          </p>
                        </div>
                      </ElFormItem>
                      <template v-if="selectedStep.type !== 'playbook' || selectedStep.hostPolicy === 'platform'">
                        <ElFormItem label="单独设置此步骤">
                          <div class="w-full">
                            <ElSwitch v-model="selectedStep.overrideHostSettings" :disabled="!editable || saving" />
                            <p class="mb-0 mt-6px text-12px text-[var(--el-text-color-regular)]">
                              默认继承任务运行设置；开启后，填写的配置将覆盖本次运行设置。
                            </p>
                          </div>
                        </ElFormItem>
                        <template v-if="selectedStep.overrideHostSettings">
                          <ElFormItem label="执行策略">
                            <ElRadioGroup v-model="selectedStep.hostStrategy" :disabled="!editable || saving">
                              <ElRadio v-for="item in HOST_STRATEGY_OPTIONS" :key="item.value" :value="item.value">
                                {{ item.label }}
                              </ElRadio>
                            </ElRadioGroup>
                          </ElFormItem>
                          <ElFormItem label="并发数（forks）">
                            <ElInputNumber
                              v-model="selectedStep.forks"
                              :min="1"
                              :max="100"
                              :disabled="!editable || saving || selectedStep.hostStrategy === 'serial'"
                              placeholder="留空继承运行"
                            />
                            <span
                              v-if="selectedStep.hostStrategy === 'serial'"
                              class="ml-8px text-12px text-[var(--el-text-color-regular)]"
                            >
                              串行固定为 1
                            </span>
                          </ElFormItem>
                          <ElFormItem
                            v-if="selectedStep.hostStrategy === 'rolling' || selectedStep.hostStrategy === 'inherit'"
                            label="每批主机数"
                          >
                            <ElInputNumber
                              v-model="selectedStep.serialBatch"
                              :min="1"
                              :max="100"
                              :disabled="!editable || saving"
                              placeholder="留空继承运行"
                            />
                          </ElFormItem>
                          <ElFormItem label="最大失败比例（%）">
                            <ElInputNumber
                              v-model="selectedStep.maxFailPercentage"
                              :min="0"
                              :max="100"
                              :disabled="!editable || saving"
                              placeholder="留空继承运行"
                            />
                          </ElFormItem>
                        </template>
                      </template>
                      <ElFormItem>
                        <template #label>
                          <FormLabelHelp
                            label="演练模式"
                            :help="['Ansible Check Mode；实际行为取决于模块和任务支持情况，需所选资源版本支持。']"
                          />
                        </template>
                        <ElRadioGroup v-model="selectedStep.checkMode" :disabled="!editable || saving">
                          <ElRadio value="inherit">继承运行设置</ElRadio>
                          <ElRadio :value="true" :disabled="!selectedVersionSupportedCheck">开启演练</ElRadio>
                          <ElRadio :value="false">关闭演练</ElRadio>
                        </ElRadioGroup>
                        <span v-if="!selectedVersionSupportedCheck" class="ml-8px text-12px text-orange-500">
                          所选资源版本不支持 Check Mode
                        </span>
                      </ElFormItem>
                    </template>
                    <ElFormItem>
                      <template #label>
                        <FormLabelHelp
                          label="步骤超时（秒）"
                          :help="['留空使用资源默认步骤超时；填写后覆盖资源默认值，仍受整个流程剩余时间限制。']"
                        />
                      </template>
                      <ElInputNumber
                        v-model="selectedStep.timeoutSeconds"
                        placeholder="留空继承资源"
                        :precision="0"
                        :min="1"
                        :max="86400"
                        :disabled="!editable || saving"
                      />
                      <p
                        v-if="selectedResourceVersion"
                        class="mb-0 mt-6px w-full text-12px text-[var(--el-text-color-regular)]"
                      >
                        资源默认步骤超时：{{ selectedResourceVersion.timeoutSeconds }} 秒。
                      </p>
                    </ElFormItem>
                    <ElFormItem label="最大尝试次数">
                      <ElInputNumber
                        v-model="selectedStep.maxAttempts"
                        :min="1"
                        :max="10"
                        :disabled="!editable || saving"
                      />
                      <span class="ml-8px text-12px text-gray-500">1 表示不重试</span>
                    </ElFormItem>
                    <ElFormItem>
                      <template #label>
                        <FormLabelHelp
                          label="失败策略"
                          :help="[
                            '失败终止：该步骤失败即结束整个流程。',
                            '忽略失败继续：该步骤标记为已忽略，后续步骤照常执行。'
                          ]"
                        />
                      </template>
                      <ElRadioGroup v-model="selectedStep.failurePolicy" :disabled="!editable || saving">
                        <ElRadio v-for="item in FAILURE_POLICY_OPTIONS" :key="item.value" :value="item.value">
                          {{ item.label }}
                        </ElRadio>
                      </ElRadioGroup>
                    </ElFormItem>
                  </ElForm>
                </ElCollapseItem>
              </ElCollapse>
            </div>
          </template>

          <div v-else class="max-w-900px py-8px">
            <ElForm label-width="120px" label-suffix="：" require-asterisk-position="left" class="mt-16px">
              <ElFormItem label="任务单参数">
                <div class="code-editor-wrapper w-full">
                  <div class="mb-4px text-12px text-gray-500">
                    声明发任务单时要填写的表单字段，仅「每次运行取值不同」的变量需要；执行时平铺注入 ansible-runner 的
                    extra_vars—— playbook 中用
                    <span class="font-mono">&#123;&#123; 变量名 &#125;&#125;</span>
                    引用，脚本中直接
                    <span class="font-mono">$变量名</span>
                    读取（自动注入环境变量），通知模板与 Jenkins 构建参数中用
                    <span class="font-mono">&#123;&#123; inputs.变量名 &#125;&#125;</span>
                    引用。值固定的变量写在资源默认变量即可，无需在此声明。
                  </div>
                  <CodeEditor
                    v-model="inputSchemaText"
                    language="json"
                    :readonly="!editable || saving"
                    height="220px"
                    placeholder='{"fields": [{"name": "branch", "label": "发布分支", "type": "string", "required": true}]}'
                  />
                  <div v-if="inputSchemaError" class="mt-4px text-12px text-red-500">{{ inputSchemaError }}</div>
                </div>
              </ElFormItem>
              <ElFormItem v-if="prettyJson(versionInfo?.targetSelectorSchema)" label="目标参数说明">
                <div class="w-full">
                  <div class="mb-4px text-12px text-gray-500">流程目标参数说明；发起执行时从资产管理确认具体主机。</div>
                  <CodeEditor
                    :model-value="prettyJson(versionInfo?.targetSelectorSchema)"
                    language="json"
                    readonly
                    height="160px"
                  />
                </div>
              </ElFormItem>
            </ElForm>
          </div>

          <template #footer>
            <div class="flex items-center justify-between">
              <span v-if="editable" class="text-13px" :class="isDirty ? 'text-orange-500' : 'text-gray-500'">
                {{ isDirty ? '● 有未保存的修改' : '● 已保存' }}
              </span>
              <span v-else class="text-13px text-gray-500">只读版本，仅可查看</span>
              <div class="flex items-center gap-8px">
                <ElButton :disabled="!editable || saving" :loading="saving" @click="onValidate">校验</ElButton>
                <ElButton type="primary" :disabled="!editable || saving" :loading="saving" @click="saveDraft(false)">
                  保存草稿
                </ElButton>
              </div>
            </div>
          </template>
        </ElCard>
      </div>
    </template>
  </div>
</template>
