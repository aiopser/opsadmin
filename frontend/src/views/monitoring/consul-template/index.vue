<script setup lang="ts">
import { computed, onMounted, ref, shallowRef } from 'vue';
import { ElMessageBox } from 'element-plus';
import type { FormInstance, FormRules } from 'element-plus';
import type {
  ConsulRemoteRead,
  ConsulRemoteReadInput,
  ConsulTemplateFile,
  ConsulTemplateFileInput
} from '@/service/api/monitoring';
import {
  compareConsulRemoteRead,
  deleteConsulTemplate,
  deployConsulTemplate,
  getConsulTemplates,
  saveConsulTemplate
} from '@/service/api/monitoring';
import { fetchGetHostOptions } from '@/service/api/jobs';
import { useAuth } from '@/hooks/business/auth';
import CodeEditor from '@/components/common/code-editor/index.vue';
import { useRemoteRead } from './use-remote-read';

defineOptions({ name: 'MonitoringConsulTemplate' });

const { hasAuth } = useAuth();
const { reading, readRemote, cancelRead } = useRemoteRead();
const canReadRemote = computed(() => hasAuth('consul.template:read_remote') || hasAuth('consul.template:deploy'));

const keyword = ref('');
const query = ref('');
const rows = shallowRef<ConsulTemplateFile[]>([]);
const loading = ref(false);
const visibleRows = computed(() =>
  rows.value.filter(row => `${row.name} ${row.path}`.toLowerCase().includes(query.value.toLowerCase()))
);
const page = ref(1);
const pagedRows = computed(() => visibleRows.value.slice((page.value - 1) * 20, page.value * 20));

const deployStatusMeta: Record<string, { label: string; tag: 'info' | 'success' | 'danger' }> = {
  pending: { label: '未下发', tag: 'info' },
  queued: { label: '排队中', tag: 'info' },
  running: { label: '下发中', tag: 'info' },
  canceled: { label: '已取消', tag: 'info' },
  success: { label: '成功', tag: 'success' },
  failure: { label: '失败', tag: 'danger' }
};

function deployTag(status: string) {
  return deployStatusMeta[status] || { label: '未知', tag: 'info' as const };
}

function formatTime(value?: string | null) {
  return value ? value.replace('T', ' ').slice(0, 19) : '—';
}

async function load() {
  loading.value = true;
  try {
    const { data, error } = await getConsulTemplates();
    if (!error && data) rows.value = data;
  } finally {
    loading.value = false;
  }
}

function search() {
  query.value = keyword.value.trim();
  page.value = 1;
}

function reset() {
  keyword.value = '';
  search();
}

const editor = ref(false);
const editingId = ref<number>();
const saving = ref(false);
const formRef = shallowRef<FormInstance>();
const form = ref<ConsulTemplateFileInput>(emptyForm());
let editorSequence = 0;
const fileKind = computed<{ label: string; tag: 'success' | 'primary' | 'info' }>(() => {
  const path = form.value.path.trim().toLowerCase();
  if (path.endsWith('.ctmpl')) return { label: 'CTMPL 渲染模板', tag: 'success' };
  if (path.endsWith('.hcl')) return { label: 'HCL 配置文件', tag: 'primary' };
  return { label: '按路径后缀识别', tag: 'info' };
});

const PATH_PATTERN = /^\/[A-Za-z0-9_./-]{1,500}$/;
const RELOAD_TOKEN_PATTERN = /^[A-Za-z0-9_@%+=:,./-]{1,256}$/;
const RELOAD_BIN_ALLOWLIST = new Set([
  'systemctl',
  'service',
  'killall',
  'pkill',
  '/bin/systemctl',
  '/usr/bin/systemctl',
  '/sbin/service',
  '/usr/sbin/service',
  '/usr/bin/pkill',
  '/usr/bin/killall',
  '/usr/bin/consul-template',
  '/usr/local/bin/consul-template'
]);

type ValidateCallback = (error?: Error) => void;

function validatePath(_rule: unknown, value: string, callback: ValidateCallback) {
  const path = (value || '').trim();
  if (!path) {
    callback();
    return;
  }
  if (!PATH_PATTERN.test(path)) {
    callback(new Error('路径必须是以 / 开头的绝对路径，仅支持字母、数字与 _ - . / 字符'));
    return;
  }
  if (path.includes('..') || path.endsWith('/')) {
    callback(new Error('路径不允许包含 .. 或以 / 结尾'));
    return;
  }
  callback();
}

function validateReloadCommand(_rule: unknown, value: string, callback: ValidateCallback) {
  const command = (value || '').trim().split(/\s+/).filter(Boolean).join(' ');
  if (!command) {
    callback();
    return;
  }
  const tokens = command.split(' ');
  if (tokens.some(token => !RELOAD_TOKEN_PATTERN.test(token))) {
    callback(new Error('命令包含不允许的字符（禁止引号、$、; | & > < 等）'));
    return;
  }
  const binary = tokens[0].split('/').pop() || '';
  const allowed =
    (binary === 'systemctl' &&
      tokens.length === 3 &&
      ['reload', 'restart'].includes(tokens[1]) &&
      ['consul-template', 'consul-template.service'].includes(tokens[2])) ||
    (binary === 'service' &&
      tokens.length === 3 &&
      ['reload', 'restart'].includes(tokens[1]) &&
      tokens[2] === 'consul-template') ||
    (binary === 'pkill' && tokens.slice(1).join(' ') === '-HUP -x consul-template') ||
    (binary === 'killall' && tokens.slice(1).join(' ') === '-HUP consul-template');
  if (!RELOAD_BIN_ALLOWLIST.has(tokens[0]) || !allowed) {
    callback(new Error('仅允许重载或重启 consul-template，或发送 HUP'));
    return;
  }
  callback();
}

const rules: FormRules = {
  name: [{ required: true, message: '请输入模板名称', trigger: 'blur' }],
  host: [{ required: true, message: '请选择目标主机', trigger: 'change' }],
  path: [
    { required: true, message: '请输入远端文件路径', trigger: 'blur' },
    { validator: validatePath, trigger: 'blur' }
  ],
  reload_command: [{ validator: validateReloadCommand, trigger: 'blur' }]
};

const baseline = ref('');
const dirty = computed(() => editor.value && baseline.value !== formSnapshot(form.value));

function formSnapshot(value: ConsulTemplateFileInput) {
  return JSON.stringify([value.name, value.host ?? null, value.path, value.content, value.reload_command]);
}

function emptyForm(): ConsulTemplateFileInput {
  return { name: '', host: undefined, path: '', content: '', reload_command: 'systemctl reload consul-template' };
}

function confirmDiscard() {
  return ElMessageBox.confirm('当前草稿尚未保存，关闭后将丢失修改。', '放弃修改？', {
    type: 'warning',
    confirmButtonText: '放弃修改',
    cancelButtonText: '继续编辑'
  })
    .then(() => true)
    .catch(() => false);
}

function handleBeforeClose(done: () => void) {
  if (!dirty.value) {
    done();
    return;
  }
  confirmDiscard().then(confirm => {
    if (confirm) done();
  });
}

async function requestClose() {
  if (dirty.value && !(await confirmDiscard())) return;
  editor.value = false;
}

const hostOptions = shallowRef<Api.Jobs.HostOption[]>([]);
const hostLoading = ref(false);

async function searchHosts(keywordValue: string) {
  hostLoading.value = true;
  try {
    const { data, error } = await fetchGetHostOptions(keywordValue.trim() || undefined, {
      os_family: 'linux',
      status: 'active'
    });
    if (!error && data) hostOptions.value = data.list;
  } finally {
    hostLoading.value = false;
  }
}

function hostLabel(option: Api.Jobs.HostOption) {
  return `${option.hostname} (${option.internalIp})`;
}

function ensureHostOption(row: ConsulTemplateFile) {
  if (!hostOptions.value.some(item => item.id === row.host)) {
    hostOptions.value = [
      { id: row.host, hostname: row.host_name, internalIp: row.host_ip, osFamily: 'linux' },
      ...hostOptions.value
    ];
  }
}

function add() {
  editorSequence += 1;
  editingId.value = undefined;
  form.value = emptyForm();
  baseline.value = formSnapshot(form.value);
  editor.value = true;
  if (!hostOptions.value.length) searchHosts('');
}

function edit(row: ConsulTemplateFile) {
  editorSequence += 1;
  editingId.value = row.id;
  form.value = {
    name: row.name,
    host: row.host,
    path: row.path,
    content: row.content,
    reload_command: row.reload_command
  };
  baseline.value = formSnapshot(form.value);
  editor.value = true;
  ensureHostOption(row);
}

function closeEditor() {
  editorSequence += 1;
  cancelRead();
  editor.value = false;
}

function isCurrentDraft(snapshot: { host: number; path: string; content: string; sequence: number }): boolean {
  return (
    editor.value &&
    editorSequence === snapshot.sequence &&
    form.value.host === snapshot.host &&
    form.value.path === snapshot.path &&
    form.value.content === snapshot.content
  );
}

async function readFromHost() {
  const { host, path, content } = form.value;
  if (!host || !path.trim()) {
    window.$message?.warning('请先选择主机并填写文件路径');
    return;
  }
  const sequence = editorSequence;
  const snapshot = { host, path, content, sequence };
  const result = await readRemote({ host, path });
  if (!result || sequence !== editorSequence || !editor.value) return;
  if (!isCurrentDraft(snapshot)) {
    window.$message?.warning('主机、路径或编辑内容已变化，未替换当前草稿');
    return;
  }
  if (!result.exists || result.content === null) {
    window.$message?.warning('远端文件不存在，当前草稿保持不变');
    return;
  }
  if (content && content !== result.content) {
    try {
      await ElMessageBox.confirm('用远端文件内容替换当前编辑器草稿？此操作不会保存或下发。', '读取到草稿', {
        type: 'warning'
      });
    } catch {
      return;
    }
  }
  if (isCurrentDraft(snapshot)) {
    form.value.content = result.content;
    window.$notification?.success('已读取到草稿，尚未保存或下发');
  }
}

async function save() {
  if (saving.value) return;
  form.value.path = form.value.path.trim();
  form.value.reload_command = form.value.reload_command.trim().split(/\s+/).filter(Boolean).join(' ');
  if (!(await formRef.value?.validate().catch(() => false))) return;
  saving.value = true;
  try {
    const { error } = await saveConsulTemplate(editingId.value, form.value);
    if (!error) {
      editor.value = false;
      window.$notification?.success('保存成功');
      await load();
    }
  } finally {
    saving.value = false;
  }
}

async function remove(row: ConsulTemplateFile) {
  const { error } = await deleteConsulTemplate(row.id);
  if (!error) {
    window.$notification?.success('已删除');
    await load();
  }
}

const deployingId = ref<number>();
const comparisonVisible = ref(false);
const comparisonRead = shallowRef<ConsulRemoteRead>();
const comparisonRow = shallowRef<ConsulTemplateFile>();
const comparisonContent = ref('');
const comparisonDiff = ref('');
const comparisonError = ref('');
const comparisonPath = ref('');
const comparisonHost = ref('');
const comparing = ref(false);
let comparisonSequence = 0;

async function compareFile(input: ConsulRemoteReadInput, content: string, row?: ConsulTemplateFile) {
  comparisonSequence += 1;
  const sequence = comparisonSequence;
  comparisonRow.value = row;
  comparisonPath.value = input.path;
  comparisonHost.value = row ? `${row.host_name} (${row.host_ip})` : `主机 #${input.host}`;
  comparisonRead.value = undefined;
  comparisonContent.value = content;
  comparisonDiff.value = '';
  comparisonError.value = '';
  comparisonVisible.value = true;
  comparing.value = true;
  try {
    const remote = await readRemote(input);
    if (sequence !== comparisonSequence || !comparisonVisible.value) return;
    if (!remote) {
      comparisonError.value = '读取未完成，原配置未改动，请重试';
      return;
    }
    const { data, error } = await compareConsulRemoteRead(remote.id, content);
    if (sequence !== comparisonSequence || !comparisonVisible.value) return;
    if (error || !data) {
      comparisonError.value = '差异比较失败，请重新读取';
      return;
    }
    comparisonRead.value = remote;
    comparisonDiff.value = data.diff || (data.changed ? '将新建空文件' : '文件内容一致');
  } finally {
    if (sequence === comparisonSequence) comparing.value = false;
  }
}

function showDraftDiff() {
  if (!form.value.host || !form.value.path.trim()) {
    window.$message?.warning('请先选择主机并填写文件路径');
    return;
  }
  compareFile({ host: form.value.host, path: form.value.path }, form.value.content);
}

function closeComparison() {
  comparisonSequence += 1;
  cancelRead();
  comparisonRead.value = undefined;
  comparing.value = false;
}

function deploy(row: ConsulTemplateFile) {
  compareFile({ host: row.host, path: row.path, template_id: row.id, revision: row.revision }, row.content, row);
}

async function confirmDeploy() {
  const row = comparisonRow.value;
  const remote = comparisonRead.value;
  if (!row || !remote || deployingId.value !== undefined) return;
  deployingId.value = row.id;
  try {
    await ElMessageBox.confirm(
      `确认将「${row.name}」下发到主机 ${row.host_name}？将覆盖远端文件 ${row.path} 并执行 reload 命令。`,
      '下发确认',
      { type: 'warning', confirmButtonText: '下发', cancelButtonText: '取消' }
    );
  } catch {
    deployingId.value = undefined;
    return;
  }
  deployingId.value = row.id;
  try {
    const { data, error } = await deployConsulTemplate(row.id, remote.id);
    if (!error && data) {
      window.$notification?.success('下发任务已提交');
      comparisonVisible.value = false;
      await load();
    } else comparisonRead.value = undefined;
  } finally {
    deployingId.value = undefined;
  }
}

onMounted(load);
</script>

<template>
  <div class="flex-col-stretch gap-16px">
    <SearchPanel @search="search" @reset="reset">
      <ElForm label-width="80px" @submit.prevent="search">
        <ElFormItem label="关键词">
          <ElInput v-model="keyword" clearable placeholder="模板名称 / 文件路径" @keyup.enter="search" />
        </ElFormItem>
      </ElForm>
    </SearchPanel>
    <ElCard class="card-wrapper">
      <template #header>
        <div class="flex items-center justify-between gap-12px">
          <span>配置文件管理</span>
          <div class="flex gap-8px">
            <ElButton v-if="hasAuth('consul.template:create')" type="primary" @click="add">新增模板</ElButton>
            <ElButton :loading="loading" @click="load">刷新</ElButton>
          </div>
        </div>
      </template>
      <ElTable v-loading="loading" :data="pagedRows" border>
        <ElTableColumn prop="name" label="名称" min-width="140" align="center" show-overflow-tooltip />
        <ElTableColumn label="目标主机" min-width="180" align="center" show-overflow-tooltip>
          <template #default="{ row }">{{ row.host_name }} ({{ row.host_ip }})</template>
        </ElTableColumn>
        <ElTableColumn prop="path" label="远端路径" min-width="220" align="center" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="font-mono">{{ row.path }}</span>
          </template>
        </ElTableColumn>
        <ElTableColumn label="最近下发" min-width="200" align="center">
          <template #default="{ row }">
            <div class="flex items-center justify-center gap-8px">
              <ElTag :type="deployTag(row.last_deploy_status).tag">{{ deployTag(row.last_deploy_status).label }}</ElTag>
              <span class="text-12px text-[var(--el-text-color-secondary)]">{{ formatTime(row.last_deploy_at) }}</span>
            </div>
          </template>
        </ElTableColumn>
        <ElTableColumn label="下发说明" min-width="160" align="center" show-overflow-tooltip>
          <template #default="{ row }">{{ row.last_deploy_message || '—' }}</template>
        </ElTableColumn>
        <ElTableColumn label="操作" width="230" align="center" fixed="right">
          <template #default="{ row }">
            <ElButton
              v-if="canReadRemote"
              link
              type="primary"
              :loading="deployingId === row.id"
              :disabled="deployingId !== undefined"
              @click="deploy(row)"
            >
              {{ hasAuth('consul.template:deploy') ? '比较并下发' : '查看差异' }}
            </ElButton>
            <ElButton v-if="hasAuth('consul.template:update')" link type="primary" @click="edit(row)">编辑</ElButton>
            <ElPopconfirm
              v-if="hasAuth('consul.template:delete')"
              title="确认删除该模板？仅删除平台记录，不影响远端文件。"
              @confirm="remove(row)"
            >
              <template #reference><ElButton link type="danger">删除</ElButton></template>
            </ElPopconfirm>
          </template>
        </ElTableColumn>
        <template #empty>
          <ElEmpty description="暂无托管模板">
            <ElButton v-if="hasAuth('consul.template:create')" @click="add">新增模板</ElButton>
          </ElEmpty>
        </template>
      </ElTable>
      <ElPagination
        v-model:current-page="page"
        class="mt-16px justify-end"
        :page-size="20"
        :total="visibleRows.length"
        layout="total, prev, pager, next"
      />
    </ElCard>
    <ElDrawer
      v-model="editor"
      :title="editingId ? '编辑托管模板' : '新增托管模板'"
      size="min(960px, 100vw)"
      :close-on-click-modal="false"
      :before-close="handleBeforeClose"
      @close="closeEditor"
    >
      <ElForm
        ref="formRef"
        :model="form"
        :rules="rules"
        :disabled="saving"
        label-width="132px"
        label-suffix="："
        require-asterisk-position="left"
      >
        <ElFormItem prop="name">
          <template #label>
            <FormLabelHelp
              label="模板名称"
              :help="['建议按「服务-用途」命名，如 prometheus-rules、gohangout-conf。']"
            />
          </template>
          <ElInput v-model="form.name" maxlength="128" />
        </ElFormItem>
        <ElFormItem prop="host">
          <template #label>
            <FormLabelHelp
              label="目标主机"
              :help="['选择已接入 CMDB 的 Linux 主机；读取、比较和下发都通过该主机执行。']"
            />
          </template>
          <ElSelect
            v-model="form.host"
            filterable
            remote
            clearable
            :remote-method="searchHosts"
            :loading="hostLoading"
            placeholder="输入主机名或 IP 搜索 Linux 主机"
            class="w-full"
          >
            <ElOption v-for="item in hostOptions" :key="item.id" :value="item.id" :label="hostLabel(item)" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem prop="path">
          <template #label>
            <FormLabelHelp
              label="远端路径"
              :help="[
                '必须是 .hcl 或 .ctmpl 的绝对路径，仅支持字母、数字与 _ - . / 字符。',
                '读取和保存草稿不会修改主机文件。'
              ]"
            />
          </template>
          <div class="w-full">
            <ElInput v-model="form.path" placeholder="/etc/consul-template/conf.d/app.hcl" maxlength="512" />
            <div class="mt-6px flex items-center gap-8px text-12px">
              <ElTag :type="fileKind.tag" size="small" effect="plain">{{ fileKind.label }}</ElTag>
            </div>
          </div>
        </ElFormItem>
        <ElFormItem prop="reload_command">
          <template #label>
            <FormLabelHelp
              label="reload 命令"
              :help="[
                '仅允许重载/重启 consul-template，或发送 HUP；留空表示只写文件不重载。',
                '允许：systemctl reload|restart consul-template、service consul-template reload|restart、pkill -HUP -x consul-template、killall -HUP consul-template。'
              ]"
            />
          </template>
          <ElInput v-model="form.reload_command" placeholder="systemctl reload consul-template" maxlength="512" />
        </ElFormItem>
        <ElFormItem>
          <template #label>
            <FormLabelHelp
              label="文件内容"
              :help="[
                '支持 HCL 配置与 CTMPL 模板；保存草稿不会写入主机。',
                '下发时先比较远端差异，确认后备份原文件再写入。'
              ]"
            />
          </template>
          <div class="w-full">
            <div v-if="canReadRemote" class="mb-12px flex gap-8px">
              <ElButton :loading="reading" :disabled="saving" @click="readFromHost">从主机读取</ElButton>
              <ElButton :disabled="reading || saving" @click="showDraftDiff">比较远端差异</ElButton>
            </div>
            <CodeEditor
              v-model="form.content"
              language="plaintext"
              height="460px"
              placeholder="可粘贴 HCL 配置或 CTMPL 模板，也可从主机读取现有文件"
            />
          </div>
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton :disabled="saving" @click="requestClose">取消</ElButton>
        <ElButton type="primary" :loading="saving" :disabled="reading" @click="save">保存草稿</ElButton>
      </template>
    </ElDrawer>
    <ElDrawer
      v-model="comparisonVisible"
      title="远端文件差异"
      size="min(1080px, 100vw)"
      :close-on-click-modal="false"
      @close="closeComparison"
    >
      <p class="mb-16px break-all text-[var(--el-text-color-regular)]">{{ comparisonHost }} · {{ comparisonPath }}</p>
      <ElAlert v-if="comparisonError" :title="comparisonError" type="error" :closable="false" class="mb-16px" />
      <ElAlert
        v-else-if="comparisonRead?.exists === false"
        title="远端文件不存在，本次下发将新建文件"
        type="info"
        :closable="false"
        class="mb-16px"
      />
      <ElSkeleton v-if="comparing" :rows="8" animated />
      <div v-else-if="comparisonRead" class="flex flex-col gap-16px">
        <div class="grid grid-cols-1 gap-16px lg:grid-cols-2">
          <section>
            <p>远端当前文件</p>
            <CodeEditor :model-value="comparisonRead.content ?? ''" readonly language="plaintext" height="300px" />
          </section>
          <section>
            <p>{{ comparisonRow ? '已保存的待下发配置' : '当前草稿快照' }}</p>
            <CodeEditor :model-value="comparisonContent" readonly language="plaintext" height="300px" />
          </section>
        </div>
        <section>
          <p>差异（− 远端内容，+ 待下发内容）</p>
          <CodeEditor :model-value="comparisonDiff" readonly language="plaintext" height="220px" />
        </section>
        <p class="text-12px text-[var(--el-text-color-regular)]">
          读取结果10分钟有效。下发时会再次校验远端内容；已变化的文件不会覆盖。
        </p>
      </div>
      <template #footer>
        <ElButton @click="comparisonVisible = false">关闭</ElButton>
        <ElButton
          v-if="comparisonRow && hasAuth('consul.template:deploy')"
          type="primary"
          :loading="deployingId !== undefined"
          :disabled="!comparisonRead || comparing"
          @click="confirmDeploy"
        >
          确认下发并重载
        </ElButton>
      </template>
    </ElDrawer>
  </div>
</template>
