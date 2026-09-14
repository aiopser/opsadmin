<script setup lang="ts">
import { computed, nextTick, onMounted, ref, shallowRef, watch } from 'vue';
import { useRouter } from 'vue-router';
import type { UploadFile } from 'element-plus';
import {
  fetchCreateModuleRun,
  fetchCreatePlaybookRun,
  fetchCreateQuickCommandRun,
  fetchGetGatewayList,
  fetchGetWorkerPools
} from '@/service/api';
import { fetchGetCommandList, fetchGetCommandVersions } from '@/service/api/automation';
import { useRunEventStream } from '@/hooks/business/run-event-stream';
import { useAuth } from '@/hooks/business/auth';
import CodeEditor from '@/components/common/code-editor/index.vue';
import HostSelectModal from '@/components/business/host-select-modal/index.vue';
import ScriptSelectModal from '@/components/business/script-select-modal/index.vue';

defineOptions({ name: 'OpsQuickExecute' });

const router = useRouter();
const { hasAuth } = useAuth();

type CommandType = 'linux_shell' | 'windows_powershell' | 'python';

const commandTypeOptions: { value: CommandType; label: string; osFamily: string }[] = [
  { value: 'linux_shell', label: 'Shell', osFamily: 'linux' },
  { value: 'python', label: 'Python', osFamily: 'linux' },
  { value: 'windows_powershell', label: 'PowerShell', osFamily: 'windows' }
];

const form = ref({
  commandType: 'linux_shell' as CommandType,
  commandContent: '',
  workerPoolId: null as number | null,
  gatewayId: null as number | null,
  sourceCommandVersionId: null as number | null
});

const submitting = ref(false);

type ExecTab = 'command' | 'playbook' | 'module';

const activeTab = ref<ExecTab>('command');

/** 当前执行类型要求的 OS family（命令页签按命令类型，Playbook/Module 固定 Linux） */
const expectedOsFamily = computed(() => {
  if (activeTab.value !== 'command') return 'linux';
  return commandTypeOptions.find(item => item.value === form.value.commandType)?.osFamily ?? 'linux';
});

/** ============ 左栏：执行配置 ============ */

const workerPools = ref<Api.Jobs.WorkerPoolOption[]>([]);
const gateways = ref<Api.Jobs.GatewayRecord[]>([]);
/** 已启用的默认池，作为执行资源的初始值与重置值 */
const defaultWorkerPoolId = ref<number | null>(null);

async function loadWorkerPools() {
  const { data, error } = await fetchGetWorkerPools();
  if (!error && data) {
    workerPools.value = data.list.filter(pool => pool.isActive);
    const defaultPool = workerPools.value.find(pool => pool.isDefault);
    if (defaultPool) {
      defaultWorkerPoolId.value = defaultPool.id;
      form.value.workerPoolId = defaultPool.id;
    }
  }
}

async function loadGateways() {
  const { data, error } = await fetchGetGatewayList({ current: 1, size: 100 });
  if (!error && data) {
    gateways.value = data.records;
  }
}

/** ============ 左栏：目标主机（弹窗选择） ============ */

const selectedHosts = ref<Api.Cmdb.HostRecord[]>([]);
const hostModalVisible = ref(false);

function openHostModal() {
  hostModalVisible.value = true;
}

function onHostsConfirm(hosts: Api.Cmdb.HostRecord[]) {
  selectedHosts.value = hosts;
}

function removeHost(id: number) {
  selectedHosts.value = selectedHosts.value.filter(host => host.id !== id);
}

function clearSelectedHosts() {
  selectedHosts.value = [];
}

/** ============ 中栏：脚本内容 ============ */

type CommandSource = 'manual' | 'library';

const commandSource = ref<CommandSource>('manual');

/** Playbook 执行表单 */
const playbookForm = ref({ name: '', content: '' });

/** ============ 中栏：编辑器语言映射 ============ */

const editorLanguage = computed(() => {
  const map: Record<CommandType, 'shell' | 'python' | 'powershell'> = {
    linux_shell: 'shell',
    python: 'python',
    windows_powershell: 'powershell'
  };
  return map[form.value.commandType];
});

/** Module 执行表单 */
const modules = ref<Api.Automation.CommandRecord[]>([]);
const moduleVersions = ref<Api.Automation.CommandVersionRecord[]>([]);
const selectedModuleId = ref<number | null>(null);
const selectedModuleVersionId = ref<number | null>(null);
const moduleArgs = ref('');

async function loadModules() {
  const { data, error } = await fetchGetCommandList({
    current: 1,
    size: 100,
    status: 'published',
    resourceKind: 'module'
  });
  if (!error && data) {
    modules.value = data.records;
  }
}

async function onModuleSelected(moduleId: number) {
  selectedModuleVersionId.value = null;
  moduleVersions.value = [];
  const { data, error } = await fetchGetCommandVersions(moduleId);
  if (!error && data) {
    moduleVersions.value = data.filter(item => item.status === 'published');
    if (moduleVersions.value.length) {
      selectedModuleVersionId.value = moduleVersions.value[0].id;
    }
  }
}

/** ============ Playbook 三来源（在线编写 / 本地上传 / 资源库加载） ============ */

type PlaybookSource = 'manual' | 'upload' | 'library';

const playbookSource = ref<PlaybookSource>('manual');
const playbooks = ref<Api.Automation.CommandRecord[]>([]);
const playbookVersions = ref<Api.Automation.CommandVersionRecord[]>([]);
const selectedPlaybookId = ref<number | null>(null);
const selectedPlaybookVersionId = ref<number | null>(null);

async function loadPlaybooks() {
  const { data, error } = await fetchGetCommandList({
    current: 1,
    size: 100,
    status: 'published',
    resourceKind: 'playbook'
  });
  if (!error && data) {
    playbooks.value = data.records;
  }
}

function applyPlaybookVersion(version: Api.Automation.CommandVersionRecord) {
  selectedPlaybookVersionId.value = version.id;
  playbookForm.value.content = version.content;
  if (!playbookForm.value.name) {
    playbookForm.value.name = `Playbook v${version.version}`;
  }
}

async function onPlaybookSelected(playbookId: number) {
  selectedPlaybookVersionId.value = null;
  playbookVersions.value = [];
  const { data, error } = await fetchGetCommandVersions(playbookId);
  if (!error && Array.isArray(data)) {
    playbookVersions.value = data.filter(item => item.status === 'published');
    if (playbookVersions.value.length) {
      applyPlaybookVersion(playbookVersions.value[0]);
    }
  }
}

function onPlaybookVersionChange(versionId: number) {
  const version = playbookVersions.value.find(item => item.id === versionId);
  if (version) {
    applyPlaybookVersion(version);
  }
}

/** 本地上传：读取文件文本填入代码框（可继续编辑） */
function onPlaybookFileChange(uploadFile: UploadFile) {
  const raw = uploadFile.raw;
  if (!raw) return;
  const reader = new FileReader();
  reader.onload = () => {
    playbookForm.value.content = String(reader.result ?? '');
  };
  reader.readAsText(raw, 'utf-8');
}

/** 脚本库（弹窗选择执行资源中已发布脚本，版本由本页按脚本类型过滤加载） */
const commandVersions = ref<Api.Automation.CommandVersionRecord[]>([]);
const selectedCommand = shallowRef<Api.Automation.CommandRecord | null>(null);
const selectedVersionId = ref<number | null>(null);
const scriptModalVisible = ref(false);

function openScriptModal() {
  scriptModalVisible.value = true;
}

async function onScriptConfirm(command: Api.Automation.CommandRecord) {
  selectedCommand.value = command;
  // 选择脚本后自动加载版本；若该脚本没有与当前脚本类型匹配的已发布版本，自动切换为脚本自身的类型
  const { data, error } = await fetchGetCommandVersions(command.id);
  if (error || !Array.isArray(data)) return;
  const published = data.filter(item => item.status === 'published');
  const matched = published.filter(item => (item.command_type as string) === form.value.commandType);
  if (matched.length) {
    applyPublishedVersions(matched);
    return;
  }
  const supported = published.find(item => commandTypeOptions.some(option => option.value === item.command_type));
  if (supported) {
    // 切换脚本类型后由 watch 按新类型重新加载版本
    form.value.commandType = supported.command_type as CommandType;
  } else {
    applyPublishedVersions([]);
  }
}

async function loadCommandVersions(commandId: number) {
  selectedVersionId.value = null;
  form.value.sourceCommandVersionId = null;
  commandVersions.value = [];
  const { data, error } = await fetchGetCommandVersions(commandId);
  if (!error && Array.isArray(data)) {
    const matched = data.filter(
      item => item.status === 'published' && (item.command_type as string) === form.value.commandType
    );
    applyPublishedVersions(matched);
  }
}

/** 应用匹配类型的已发布版本，默认选中最新版本并回填编辑器 */
function applyPublishedVersions(versions: Api.Automation.CommandVersionRecord[]) {
  commandVersions.value = versions;
  if (versions.length) {
    // 后端按版本号倒序返回，首个即最新
    const latest = versions[0];
    selectedVersionId.value = latest.id;
    applySelectedVersion(latest.id);
  }
}

function applySelectedVersion(versionId: number) {
  const version = commandVersions.value.find(item => item.id === versionId);
  if (!version) return;
  form.value.sourceCommandVersionId = version.id;
  form.value.commandContent = version.content;
}

// 脚本库模式下切换脚本类型后，按新类型重新筛选已发布版本
watch(
  () => form.value.commandType,
  () => {
    if (commandSource.value === 'library' && selectedCommand.value) {
      loadCommandVersions(selectedCommand.value.id);
    }
  }
);

/** ============ 右栏：实时输出 ============ */

const runId = ref<number | null>(null);
const runDomain = ref<Api.Jobs.RunDomain>('ops');
const { events, terminal, connected, transportError } = useRunEventStream(runId, runDomain);
const outputRef = ref<HTMLDivElement>();
const clearedCount = ref(0);

const hostNameMap = computed(() => {
  const map = new Map<number, string>();
  selectedHosts.value.forEach(host => map.set(host.id, host.hostname));
  return map;
});

interface OutputLine {
  key: string;
  time: string;
  source: string;
  text: string;
  level: 'info' | 'success' | 'error' | 'muted';
}

const outputLines = computed<OutputLine[]>(() =>
  events.value
    .filter(event => event.sequence > clearedCount.value)
    .map(event => {
      const time = (event.createdAt || '').slice(11, 19);
      const isHostEvent = event.hostId !== null;
      const source = isHostEvent ? (hostNameMap.value.get(event.hostId!) ?? `#${event.hostId}`) : '调度';
      const type = event.normalizedEventType || event.eventType || '';
      let level: OutputLine['level'] = 'info';
      if (!isHostEvent) level = 'muted';
      if (/fail|error|fatal/i.test(type)) level = 'error';
      else if (/success|complete|finish|ok/i.test(type)) level = 'success';
      return { key: `${event.sequence}`, time, source, text: event.message || '', level };
    })
);

const outputStatus = computed(() => {
  if (!runId.value) return { text: '待机', type: 'info' as const };
  if (terminal.value) return { text: '已结束', type: 'success' as const };
  if (connected.value) return { text: '实时连接', type: 'success' as const };
  if (transportError.value) return { text: '同步重试中', type: 'warning' as const };
  return { text: '轮询中', type: 'info' as const };
});

watch(
  () => outputLines.value.length,
  () => {
    nextTick(() => {
      if (outputRef.value) {
        outputRef.value.scrollTop = outputRef.value.scrollHeight;
      }
    });
  }
);

function clearOutput() {
  const last = events.value[events.value.length - 1];
  if (last) {
    clearedCount.value = last.sequence;
  }
}

function gotoRunDetail() {
  if (runId.value) {
    router.push({ name: 'task_run-detail', params: { id: runId.value }, query: { domain: 'ops' } });
  }
}

/** ============ 提交 ============ */

const tabEmptyMessages: Record<ExecTab, string> = {
  command: '请输入命令内容或从脚本库选择模板',
  playbook: '请输入 Playbook YAML 内容',
  module: '请选择 Module 及版本'
};

function validateByTab() {
  if (activeTab.value === 'playbook') {
    return Boolean(playbookForm.value.content.trim());
  }
  if (activeTab.value === 'module') {
    return Boolean(selectedModuleVersionId.value);
  }
  return Boolean(form.value.commandContent.trim());
}

async function submitByTab(base: { hostIds: number[]; workerPoolId: number | null; gatewayId: number | null }) {
  let result: Awaited<ReturnType<typeof fetchCreateQuickCommandRun>>;
  if (activeTab.value === 'playbook') {
    result = await fetchCreatePlaybookRun({
      ...base,
      playbookContent: playbookForm.value.content,
      playbookName: playbookForm.value.name.trim() || 'Playbook'
    });
  } else if (activeTab.value === 'module') {
    result = await fetchCreateModuleRun({
      ...base,
      moduleVersionId: selectedModuleVersionId.value!,
      moduleArgs: moduleArgs.value
    });
  } else {
    result = await fetchCreateQuickCommandRun({
      ...base,
      commandType: form.value.commandType,
      commandContent: form.value.commandContent,
      sourceCommandVersionId: form.value.sourceCommandVersionId
    });
  }
  return result;
}

async function onSubmit() {
  if (!hasAuth('jobs.quick_command:execute')) return;
  if (form.value.workerPoolId === null) {
    window.$message?.warning('请选择执行资源');
    return;
  }
  if (!form.value.commandContent.trim()) {
    window.$message?.warning('请输入命令内容或从脚本库选择模板');
    return;
  }
  if (!selectedHosts.value.length) {
    window.$message?.warning('请选择目标主机');
    return;
  }
  const mismatched = selectedHosts.value.filter(host => (host.osFamily ?? '').toLowerCase() !== expectedOsFamily.value);
  if (mismatched.length) {
    const names = mismatched
      .slice(0, 5)
      .map(host => host.hostname)
      .join('、');
    window.$message?.warning(
      `以下 ${mismatched.length} 台主机与当前命令类型（${expectedOsFamily.value}）不符：${names}${
        mismatched.length > 5 ? ' 等' : ''
      }`
    );
    return;
  }

  if (!validateByTab()) {
    window.$message?.warning(tabEmptyMessages[activeTab.value]);
    return;
  }

  submitting.value = true;
  try {
    const { data, error } = await submitByTab({
      hostIds: selectedHosts.value.map(host => host.id),
      workerPoolId: form.value.workerPoolId,
      gatewayId: form.value.gatewayId
    });
    if (!error && data) {
      window.$message?.success('已提交执行');
      clearedCount.value = 0;
      runId.value = data.id;
    }
  } finally {
    submitting.value = false;
  }
}

function onReset() {
  form.value.commandContent = '';
  form.value.sourceCommandVersionId = null;
  form.value.gatewayId = null;
  form.value.workerPoolId = defaultWorkerPoolId.value;
  clearSelectedHosts();
  selectedCommand.value = null;
  selectedVersionId.value = null;
  commandVersions.value = [];
  playbookForm.value = { name: '', content: '' };
  playbookSource.value = 'manual';
  selectedPlaybookId.value = null;
  selectedPlaybookVersionId.value = null;
  playbookVersions.value = [];
  selectedModuleId.value = null;
  selectedModuleVersionId.value = null;
  moduleVersions.value = [];
  moduleArgs.value = '';
}

onMounted(() => {
  loadWorkerPools();
  loadGateways();
  loadModules();
  loadPlaybooks();
});
</script>

<template>
  <div class="h-full min-h-560px flex flex-col gap-16px overflow-hidden lt-sm:overflow-auto">
    <div class="min-h-0 flex flex-1 gap-16px overflow-hidden lt-lg:flex-col lt-lg:overflow-auto">
      <!-- 左栏：执行配置 -->
      <ElCard class="layout-card w-300px shrink-0 lt-lg:w-full" shadow="never">
        <template #header>
          <div class="flex items-center justify-between">
            <span class="font-bold">执行配置</span>
            <ElTag size="small" type="success">已选 {{ selectedHosts.length }}</ElTag>
          </div>
        </template>
        <ElForm label-position="top" size="small">
          <ElFormItem label="连接网关">
            <ElSelect v-model="form.gatewayId" clearable placeholder="自动路由（主机默认网关 / 网段匹配）">
              <ElOption
                v-for="gateway in gateways"
                :key="gateway.id"
                :label="`${gateway.name}（${gateway.address}）`"
                :value="gateway.id"
              />
            </ElSelect>
          </ElFormItem>
          <ElFormItem label="执行资源" required>
            <ElSelect v-model="form.workerPoolId" placeholder="请选择执行资源">
              <ElOption
                v-for="pool in workerPools"
                :key="pool.id"
                :label="`${pool.name}${pool.isDefault ? '（默认）' : ''}`"
                :value="pool.id"
              />
            </ElSelect>
          </ElFormItem>
        </ElForm>
        <ElDivider class="my-8px" />
        <div class="mb-8px flex items-center justify-between">
          <span class="font-bold">目标主机</span>
          <ElButton type="primary" size="small" @click="openHostModal">选择主机</ElButton>
        </div>
        <div v-if="selectedHosts.length" class="max-h-200px overflow-auto">
          <ElTag
            v-for="host in selectedHosts"
            :key="host.id"
            size="small"
            closable
            class="mb-4px mr-4px"
            @close="removeHost(host.id)"
          >
            {{ host.hostname }}（{{ host.primaryIp }}）
          </ElTag>
        </div>
        <ElEmpty v-else description="未选择主机" :image-size="60" />
        <div class="mt-8px text-12px text-gray-400">已选 {{ selectedHosts.length }} 台主机，经所选执行资源下发</div>
      </ElCard>

      <!-- 中栏：脚本内容 -->
      <ElCard class="layout-card min-w-0 flex-1" shadow="never">
        <template #header>
          <ElTabs v-model="activeTab" class="header-tabs">
            <ElTabPane label="脚本" name="command" />
            <ElTabPane label="Playbook" name="playbook" />
            <ElTabPane label="Module" name="module" />
          </ElTabs>
        </template>

        <!-- 脚本页签 -->
        <div v-if="activeTab === 'command'" class="min-h-0 flex flex-col flex-1">
          <div class="mb-8px flex items-center gap-12px">
            <span class="text-13px text-gray-500">脚本类型</span>
            <ElRadioGroup v-model="form.commandType" size="small">
              <ElRadioButton v-for="item in commandTypeOptions" :key="item.value" :value="item.value">
                {{ item.label }}
              </ElRadioButton>
            </ElRadioGroup>
          </div>
          <div class="mb-8px flex items-center gap-12px">
            <span class="text-13px text-gray-500">脚本来源</span>
            <ElRadioGroup v-model="commandSource" size="small">
              <ElRadioButton value="manual">手工录入</ElRadioButton>
              <ElRadioButton value="library">脚本库</ElRadioButton>
            </ElRadioGroup>
            <template v-if="commandSource === 'library'">
              <ElButton size="small" type="primary" plain @click="openScriptModal">
                {{ selectedCommand ? `已选：${selectedCommand.name}` : '从脚本库选择' }}
              </ElButton>
              <ElSelect
                v-model="selectedVersionId"
                size="small"
                placeholder="版本"
                class="w-140px"
                :disabled="!commandVersions.length"
                @change="applySelectedVersion"
              >
                <ElOption v-for="ver in commandVersions" :key="ver.id" :label="`v${ver.version}`" :value="ver.id" />
              </ElSelect>
            </template>
          </div>
          <CodeEditor
            v-model="form.commandContent"
            :language="editorLanguage"
            :readonly="commandSource === 'library'"
            height="100%"
            class="min-h-120px flex-1"
            placeholder="手工录入：输入要在目标主机上执行的命令，支持多行，逐行依次执行"
          />
        </div>

        <!-- Playbook 页签 -->
        <div v-else-if="activeTab === 'playbook'" class="min-h-0 flex flex-col flex-1">
          <div class="mb-8px flex items-center gap-12px">
            <span class="shrink-0 text-13px text-gray-500">任务名称</span>
            <ElInput v-model="playbookForm.name" size="small" class="w-180px" placeholder="Playbook 名称（可选）" />
            <span class="text-12px text-gray-400">目标主机限 Linux，内容经 ansible-playbook 下发执行</span>
          </div>
          <div class="mb-8px flex items-center gap-12px">
            <span class="shrink-0 text-13px text-gray-500">内容来源</span>
            <ElRadioGroup v-model="playbookSource" size="small">
              <ElRadioButton value="manual">在线编写</ElRadioButton>
              <ElRadioButton value="upload">本地上传</ElRadioButton>
              <ElRadioButton value="library">自动化配置</ElRadioButton>
            </ElRadioGroup>
            <ElUpload
              v-if="playbookSource === 'upload'"
              :auto-upload="false"
              :show-file-list="false"
              accept=".yml,.yaml"
              :on-change="onPlaybookFileChange"
            >
              <ElButton size="small" type="primary" plain>选择 YAML 文件</ElButton>
            </ElUpload>
            <template v-if="playbookSource === 'library'">
              <ElSelect
                v-model="selectedPlaybookId"
                filterable
                size="small"
                class="w-200px"
                placeholder="选择已发布 Playbook"
                @change="onPlaybookSelected"
              >
                <ElOption v-for="pb in playbooks" :key="pb.id" :label="pb.name" :value="pb.id" />
              </ElSelect>
              <ElSelect
                v-model="selectedPlaybookVersionId"
                size="small"
                class="w-110px"
                placeholder="版本"
                :disabled="!playbookVersions.length"
                @change="onPlaybookVersionChange"
              >
                <ElOption v-for="ver in playbookVersions" :key="ver.id" :label="`v${ver.version}`" :value="ver.id" />
              </ElSelect>
            </template>
          </div>
          <CodeEditor
            v-model="playbookForm.content"
            language="yaml"
            height="100%"
            class="min-h-120px flex-1"
            placeholder="粘贴 Ansible Playbook YAML 内容，或从上方切换内容来源"
          />
        </div>

        <!-- Module 页签 -->
        <div v-else class="min-h-0 flex flex-col flex-1">
          <div class="mb-8px flex items-center gap-8px">
            <span class="shrink-0 text-13px text-gray-500">Module</span>
            <ElSelect
              v-model="selectedModuleId"
              filterable
              size="small"
              class="min-w-200px flex-1"
              placeholder="选择已发布 Module"
              @change="onModuleSelected"
            >
              <ElOption v-for="mod in modules" :key="mod.id" :label="mod.name" :value="mod.id" />
            </ElSelect>
            <ElSelect
              v-model="selectedModuleVersionId"
              size="small"
              class="w-110px shrink-0"
              placeholder="版本"
              :disabled="!moduleVersions.length"
            >
              <ElOption v-for="ver in moduleVersions" :key="ver.id" :label="`v${ver.version}`" :value="ver.id" />
            </ElSelect>
          </div>
          <div class="min-h-0 flex flex-col flex-1">
            <span class="text-13px text-gray-500">模块参数</span>
            <ElInput
              v-model="moduleArgs"
              type="textarea"
              :rows="6"
              resize="none"
              class="module-args mt-4px min-h-0 flex-1 font-mono"
              placeholder="free-form 参数，如：name=httpd state=present"
            />
          </div>
          <div class="mt-8px text-12px text-gray-400">在目标主机上执行单个 Ansible Module，目标主机限 Linux</div>
        </div>

        <div class="mt-12px flex items-center gap-8px">
          <ElButton type="primary" :loading="submitting" @click="onSubmit">快速执行</ElButton>
          <ElButton @click="onReset">重置</ElButton>
          <ElButton v-if="runId" link type="primary" @click="gotoRunDetail">查看执行详情</ElButton>
        </div>
      </ElCard>

      <!-- 右栏：实时输出 -->
      <ElCard class="layout-card min-w-0 flex-1" shadow="never">
        <template #header>
          <div class="flex items-center justify-between">
            <span class="font-bold">实时输出</span>
            <div class="flex items-center gap-8px">
              <ElTag size="small" :type="outputStatus.type">{{ outputStatus.text }}</ElTag>
              <ElButton size="small" :disabled="!outputLines.length" @click="clearOutput">清屏</ElButton>
            </div>
          </div>
        </template>
        <div
          ref="outputRef"
          class="min-h-0 flex-1 overflow-auto border border-gray-200 rounded-4px bg-white p-12px text-12px leading-20px font-mono"
        >
          <template v-if="outputLines.length">
            <div v-for="line in outputLines" :key="line.key" class="whitespace-pre-wrap break-all">
              <span class="text-#909399">{{ line.time }}</span>
              <span class="ml-8px" :class="{ 'text-#909399': line.level === 'muted' }">[{{ line.source }}]</span>
              <span
                class="ml-4px"
                :class="{
                  'text-#303133': line.level === 'info',
                  'text-#67c23a': line.level === 'success',
                  'text-#f56c6c': line.level === 'error',
                  'text-#909399': line.level === 'muted'
                }"
              >
                {{ line.text }}
              </span>
            </div>
          </template>
          <div v-else class="h-full flex-col-center gap-12px text-#909399">
            <span class="text-32px">🖥</span>
            <span>{{ runId ? '等待执行输出…' : '选择主机并执行命令后，这里将实时输出每台主机的执行结果' }}</span>
          </div>
        </div>
      </ElCard>
    </div>

    <HostSelectModal
      v-model:visible="hostModalVisible"
      :selected-hosts="selectedHosts"
      :default-os-family="expectedOsFamily"
      @confirm="onHostsConfirm"
    />

    <ScriptSelectModal v-model:visible="scriptModalVisible" :selected="selectedCommand" @confirm="onScriptConfirm" />
  </div>
</template>

<style scoped>
.header-tabs :deep(.el-tabs__header) {
  margin-bottom: 0;
}

/* Module 参数多行输入框：随容器高度铺满 */
.module-args :deep(.el-textarea__inner) {
  height: 100%;
}

/* 三栏卡片等高铺满：header 固定，body 占满剩余空间 */
.layout-card {
  display: flex;
  flex-direction: column;
}

.layout-card :deep(.el-card__body) {
  display: flex;
  flex: 1;
  min-height: 0;
  flex-direction: column;
  overflow: auto;
}
</style>
