<script setup lang="ts">
import { computed, ref, shallowRef, watch } from 'vue';
import { useClipboard } from '@vueuse/core';
import type { TreeNodeData } from 'element-plus';
import type { ConsulConnection, ConsulKvValue } from '@/service/api/monitoring';
import { deleteConsulKv, getConsulKvKeys, getConsulKvValue, updateConsulKv } from '@/service/api/monitoring';
import { useAuth } from '@/hooks/business/auth';
import CodeEditor from '@/components/common/code-editor/index.vue';

defineOptions({ name: 'ConsulKvDrawer' });

/** 与 CodeEditor 组件的 CodeLanguage 保持一致（组件未导出该类型） */
type EditorLanguage = 'shell' | 'python' | 'powershell' | 'yaml' | 'json' | 'plaintext';

interface Props {
  visible: boolean;
  connection?: ConsulConnection;
}
const props = defineProps<Props>();
const emit = defineEmits<{ 'update:visible': [value: boolean] }>();

const { hasAuth } = useAuth();
const { copy: copyToClipboard, isSupported: clipboardSupported } = useClipboard({ copiedDuring: 1500 });
const canEdit = computed(() => Boolean(props.connection) && hasAuth('consul.connection:kv_edit'));

const open = computed({
  get: () => props.visible,
  set: value => emit('update:visible', value)
});

interface KvNode {
  label: string;
  path: string;
  leaf: boolean;
}

interface ReloadableTreeNode {
  loaded: boolean;
  expand: () => void;
}

interface KvTreeHandle {
  filter: (value: string) => void;
  getNode: (key: string) => ReloadableTreeNode | undefined;
}

const treeRef = shallowRef<KvTreeHandle>();
const treeRenderKey = ref(0);
const keyword = ref('');
const selectedPath = ref('');
const valueLoading = ref(false);
const valueError = ref(false);
const current = shallowRef<ConsulKvValue>();
const creating = ref(false);
const editing = ref(false);
const saving = ref(false);
const draft = ref('');

function kvLabel(path: string) {
  const name = path.endsWith('/') ? path.slice(0, -1) : path;
  return name.split('/').pop() || name || '/';
}

function parentFolderOf(path: string) {
  const trimmed = path.replace(/\/+$/, '');
  const index = trimmed.lastIndexOf('/');
  return index === -1 ? '' : trimmed.slice(0, index + 1);
}

async function loadNode(node: unknown, resolve: (children: KvNode[]) => void) {
  const connection = props.connection;
  if (!connection) {
    resolve([]);
    return;
  }
  const level = (node as { level: number }).level;
  const prefix = level === 0 ? '' : String((node as { data: KvNode }).data.path);
  const { data, error } = await getConsulKvKeys(connection.id, prefix);
  if (error) {
    window.$message?.error('KV 列表读取失败，请检查连接与 Key 读取权限');
    resolve([]);
    return;
  }
  resolve((data?.keys ?? []).map<KvNode>(path => ({ label: kvLabel(path), path, leaf: !path.endsWith('/') })));
}

async function onNodeClick(node: KvNode) {
  selectedPath.value = node.path;
  if (!node.leaf || !props.connection || editing.value) return;
  valueLoading.value = true;
  valueError.value = false;
  current.value = undefined;
  try {
    const { data, error } = await getConsulKvValue(props.connection.id, node.path);
    if (error) {
      valueError.value = true;
      return;
    }
    if (data) current.value = data;
  } finally {
    valueLoading.value = false;
  }
}

function filterNode(query: string, data: TreeNodeData) {
  const label = String((data as KvNode).label ?? '');
  return !query || label.toLowerCase().includes(query.toLowerCase());
}

watch(keyword, value => {
  treeRef.value?.filter(value.trim());
});

/** 删除/新建后仅刷新 Key 所在目录节点，保留其他目录的展开状态 */
function reloadKeyFolder(keyPath: string) {
  const parentPath = parentFolderOf(keyPath);
  const parent = parentPath ? treeRef.value?.getNode(parentPath) : undefined;
  if (!parent) {
    treeRenderKey.value += 1;
    return;
  }
  parent.loaded = false;
  parent.expand();
}

async function copyText(text: string, successTip: string) {
  if (!clipboardSupported.value) {
    window.$message?.warning('当前浏览器不支持一键复制');
    return;
  }
  try {
    await copyToClipboard(text);
    window.$notification?.success(successTip);
  } catch {
    window.$message?.error('复制失败，请检查浏览器剪贴板权限');
  }
}

function copyKey() {
  const key = current.value?.key;
  if (key) copyText(key, 'Key 路径已复制');
}

function copyValue() {
  const value = current.value?.value;
  if (value !== undefined) copyText(value, 'Value 内容已复制');
}

function reformatJson(text: string, space: 0 | 2) {
  try {
    return JSON.stringify(JSON.parse(text), null, space);
  } catch {
    return null;
  }
}

function formatDraft(space: 0 | 2) {
  if (!draft.value.trim()) return;
  const formatted = reformatJson(draft.value, space);
  if (formatted === null) {
    window.$message?.error('内容不是合法 JSON，无法格式化');
    return;
  }
  draft.value = formatted;
}

const draftJsonState = computed<'valid' | 'invalid' | 'none'>(() => {
  const text = draft.value.trim();
  if (!text || !/^[{[]/.test(text)) return 'none';
  return reformatJson(text, 2) === null ? 'invalid' : 'valid';
});

const languageOptions: { label: string; value: EditorLanguage }[] = [
  { label: 'YAML', value: 'yaml' },
  { label: 'JSON', value: 'json' },
  { label: 'Shell', value: 'shell' },
  { label: 'Python', value: 'python' },
  { label: 'PowerShell', value: 'powershell' },
  { label: '纯文本', value: 'plaintext' }
];

function isEditorLanguage(value: string): value is EditorLanguage {
  return languageOptions.some(item => item.value === value);
}

/** 强信号识别：Key 后缀优先，JSON 内容兜底 */
function strongDetectLanguage(key: string, looksLikeJson: boolean): EditorLanguage | null {
  const lower = key.toLowerCase();
  if (lower.endsWith('.json')) return 'json';
  if (/\.(ya?ml)$/.test(lower)) return 'yaml';
  if (lower.endsWith('.sh')) return 'shell';
  if (lower.endsWith('.py')) return 'python';
  if (lower.endsWith('.ps1')) return 'powershell';
  return looksLikeJson ? 'json' : null;
}

/** 用户手动选择的高亮语言，在本次抽屉会话内跨 Key 生效 */
const languageOverride = shallowRef<EditorLanguage | null>(null);

const editorLanguage = computed(
  () =>
    strongDetectLanguage(current.value?.key ?? '', draftJsonState.value === 'valid') ??
    languageOverride.value ??
    // Consul KV 值以 YAML 配置为主（prometheus 规则 / consul-template 配置等），默认按 YAML 高亮
    'yaml'
);

function onLanguageChange(value: string) {
  if (isEditorLanguage(value)) languageOverride.value = value;
}

function onUpdateDraft(value: string) {
  draft.value = value;
}

function startEdit() {
  if (!current.value) return;
  draft.value = current.value.value;
  editing.value = true;
}

function cancelEdit() {
  if (creating.value) {
    creating.value = false;
    current.value = undefined;
  }
  editing.value = false;
  draft.value = '';
}

async function saveEdit() {
  const connection = props.connection;
  const target = current.value;
  if (!connection || !target || saving.value) return;
  saving.value = true;
  try {
    const { error } = await updateConsulKv(connection.id, target.key, draft.value);
    if (error) return;
    editing.value = false;
    if (creating.value) {
      creating.value = false;
      current.value = {
        key: target.key,
        value: draft.value,
        create_index: 0,
        modify_index: 0,
        lock_index: 0,
        flags: 0
      };
      reloadKeyFolder(target.key);
      window.$notification?.success('Key 已创建，consul-template 会自动渲染并热加载关联服务');
    } else {
      const { data } = await getConsulKvValue(connection.id, target.key);
      if (data) current.value = data;
      window.$notification?.success('已保存，consul-template 会自动渲染并热加载关联服务');
    }
  } finally {
    saving.value = false;
  }
}

async function deleteCurrent() {
  const connection = props.connection;
  const key = current.value?.key;
  if (!connection || !key) return;
  try {
    await window.$messageBox?.confirm(
      `确认删除 Key「${key}」？该操作不可恢复，依赖此配置的服务可能受影响。`,
      '删除确认',
      {
        type: 'warning',
        confirmButtonText: '删除',
        cancelButtonText: '取消'
      }
    );
  } catch {
    return;
  }
  const { error } = await deleteConsulKv(connection.id, key);
  if (error) return;
  window.$notification?.success('Key 已删除');
  current.value = undefined;
  editing.value = false;
  reloadKeyFolder(key);
}

function defaultCreatePrefix() {
  const path = selectedPath.value;
  if (!path) return '';
  return path.endsWith('/') ? path : parentFolderOf(path);
}

async function createKey() {
  if (!props.connection) return;
  try {
    const promptResult = (await window.$messageBox?.prompt(
      '输入新 Key 的完整路径，如 IDC/app/config.yaml',
      '新建 Key',
      {
        confirmButtonText: '下一步',
        cancelButtonText: '取消',
        inputValue: defaultCreatePrefix(),
        inputPattern: /^[A-Za-z0-9_./-]{1,512}$/,
        inputErrorMessage: '仅支持字母、数字与 _ - . / 字符，长度不超过 512'
      }
    )) as { value?: string } | undefined;
    const newKey = promptResult?.value ?? '';
    if (!newKey) return;
    creating.value = true;
    current.value = {
      key: newKey.replace(/\/+$/, ''),
      value: '',
      create_index: 0,
      modify_index: 0,
      lock_index: 0,
      flags: 0
    };
    draft.value = '';
    editing.value = true;
  } catch {
    // 用户取消
  }
}

function resetView() {
  keyword.value = '';
  selectedPath.value = '';
  current.value = undefined;
  valueError.value = false;
  creating.value = false;
  editing.value = false;
  draft.value = '';
  languageOverride.value = null;
  treeRenderKey.value += 1;
}

watch(
  () => props.visible,
  visible => {
    if (visible) resetView();
  }
);

const displayValue = computed(() => {
  const raw = current.value?.value ?? '';
  if (raw.length > 100_000) return `${raw.slice(0, 100_000)}\n\n…（内容过长，已截断展示）`;
  if (!raw) return '';
  try {
    return JSON.stringify(JSON.parse(raw), null, 2);
  } catch {
    return raw;
  }
});

const charCount = computed(() => (editing.value ? draft.value.length : (current.value?.value.length ?? 0)));
</script>

<template>
  <ElDrawer v-model="open" :title="`KV 管理 · ${connection?.name ?? ''}`" size="72%">
    <div class="h-full flex gap-16px">
      <div class="w-340px flex-col-stretch shrink-0 gap-8px">
        <div class="flex items-center gap-8px">
          <ElInput v-model="keyword" class="min-w-0 flex-1" clearable placeholder="过滤已加载的 Key" />
          <ElButton v-if="canEdit" type="primary" plain @click="createKey">新建</ElButton>
        </div>
        <ElTree
          :key="treeRenderKey"
          ref="treeRef"
          class="min-h-0 flex-1 overflow-auto"
          lazy
          :load="loadNode"
          :props="{ label: 'label', isLeaf: 'leaf' }"
          node-key="path"
          highlight-current
          :filter-node-method="filterNode"
          @node-click="onNodeClick"
        />
      </div>
      <div class="min-w-0 flex-col-stretch flex-1 gap-8px">
        <template v-if="current">
          <div class="flex flex-wrap items-center justify-between gap-8px">
            <div class="min-w-0 flex flex-1 items-center gap-4px">
              <p class="min-w-0 truncate text-13px font-mono">{{ current.key }}</p>
              <ElTooltip content="复制 Key 路径" placement="top" :show-after="200">
                <ElButton link size="small" class="shrink-0" aria-label="复制 Key 路径" @click="copyKey">
                  <ElIcon aria-hidden="true"><icon-mdi-content-copy /></ElIcon>
                </ElButton>
              </ElTooltip>
              <ElSelect
                :model-value="editorLanguage"
                size="small"
                class="ml-auto w-108px shrink-0"
                @update:model-value="onLanguageChange"
              >
                <ElOption v-for="item in languageOptions" :key="item.value" :label="item.label" :value="item.value" />
              </ElSelect>
            </div>
            <div v-if="!editing" class="flex flex-wrap items-center gap-8px">
              <ElTag size="small" type="info" class="font-mono">{{ charCount }} 字符</ElTag>
              <ElButton size="small" @click="copyValue">复制值</ElButton>
              <ElButton v-if="canEdit" type="primary" plain size="small" @click="startEdit">编辑</ElButton>
              <ElButton v-if="canEdit" type="danger" plain size="small" @click="deleteCurrent">删除</ElButton>
            </div>
            <div v-else class="flex flex-wrap items-center gap-8px">
              <template v-if="draftJsonState !== 'none'">
                <ElButton size="small" @click="formatDraft(2)">格式化</ElButton>
                <ElButton size="small" @click="formatDraft(0)">压缩</ElButton>
                <ElTag v-if="draftJsonState === 'valid'" size="small" type="success">JSON 有效</ElTag>
                <ElTag v-else size="small" type="danger">JSON 无效</ElTag>
              </template>
              <div class="flex-1"></div>
              <ElButton size="small" @click="cancelEdit">取消</ElButton>
              <ElButton type="primary" size="small" :loading="saving" @click="saveEdit">保存</ElButton>
            </div>
          </div>
          <div class="min-h-0 flex flex-1">
            <CodeEditor
              :model-value="editing ? draft : displayValue"
              :language="editorLanguage"
              :readonly="!editing"
              height="100%"
              :placeholder="editing ? '输入 Key 内容（支持 JSON / YAML / Shell 等）' : ''"
              @update:model-value="onUpdateDraft"
            />
          </div>
          <p v-if="editing" class="text-12px text-gray-500">
            保存即写入 Consul（PUT 覆盖原值）；consul-template 监听到变更后会自动渲染模板并热加载服务。
          </p>
        </template>
        <ElAlert
          v-else-if="valueError"
          title="KV 值读取失败，请重试或检查 Key 读取权限。"
          type="error"
          :closable="false"
        />
        <ElEmpty v-else-if="!valueLoading" description="点击左侧 Key 查看值（仅支持 UTF-8 文本）" />
        <div v-if="valueLoading" v-loading="valueLoading" class="min-h-200px" />
      </div>
    </div>
  </ElDrawer>
</template>
