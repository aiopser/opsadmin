<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, shallowRef, watch } from 'vue';
import { useRouter } from 'vue-router';
import type { UploadFile } from 'element-plus';
import { fetchCreateQuickCommandRun, fetchPreviewQuickCommandRun } from '@/service/api';
import { fetchGetCommandVersions } from '@/service/api/automation';
import { useAuth } from '@/hooks/business/auth';
import CodeEditor from '@/components/common/code-editor/index.vue';
import ScriptSelectModal from '@/components/business/script-select-modal/index.vue';
import RunPreviewDialog from '@/components/business/run-preview-dialog/index.vue';
import EnvSelectField from '../components/env-select-field.vue';
import ExecutionPolicyFields from '../components/execution-policy-fields.vue';
import ExtraVarsField from '../components/extra-vars-field.vue';
import HostSelectField from '../components/host-select-field.vue';

defineOptions({ name: 'OpsQuickExecuteScript' });

const router = useRouter();
const { hasAuth } = useAuth();

/** ============ 表单模型（参与提交校验的字段收口于此，rules 见 formRules） ============ */

const form = reactive({
  /** 作业名称：留空提交时由后端自动生成（脚本执行-时间戳） */
  jobName: '',
  workerPoolId: null as number | null,
  /** 脚本库来源时已选的脚本 */
  selectedCommand: null as Api.Automation.CommandRecord | null,
  commandContent: '',
  hosts: [] as Api.Cmdb.HostRecord[]
});

const formRef = ref();
const extraVarsRef = ref<InstanceType<typeof ExtraVarsField>>();

/** ============ 脚本类型与内容 ============ */

type CommandType = 'linux_shell' | 'windows_powershell' | 'python';

const commandTypeOptions: { value: CommandType; label: string; osFamily: string }[] = [
  { value: 'linux_shell', label: 'Shell', osFamily: 'linux' },
  { value: 'python', label: 'Python', osFamily: 'linux' },
  { value: 'windows_powershell', label: 'PowerShell', osFamily: 'windows' }
];

const commandType = ref<CommandType>('linux_shell');
const sourceCommandVersionId = ref<number | null>(null);

const expectedOsFamily = computed(
  () => commandTypeOptions.find(item => item.value === commandType.value)?.osFamily ?? 'linux'
);

const editorLanguage = computed(() => {
  const map: Record<CommandType, 'shell' | 'python' | 'powershell'> = {
    linux_shell: 'shell',
    python: 'python',
    windows_powershell: 'powershell'
  };
  return map[commandType.value];
});

/** ============ 脚本库来源 ============ */

type CommandSource = 'manual' | 'upload' | 'library';

const commandSource = ref<CommandSource>('manual');
const commandVersions = shallowRef<Api.Automation.CommandVersionRecord[]>([]);
const selectedVersionId = ref<number | null>(null);
const scriptModalVisible = ref(false);
const loadingCommandVersions = ref(false);
let commandRequestId = 0;

function invalidateCommandVersions() {
  commandRequestId += 1;
  loadingCommandVersions.value = false;
  selectedVersionId.value = null;
  sourceCommandVersionId.value = null;
  commandVersions.value = [];
  form.commandContent = '';
  invalidatePreview();
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
  invalidatePreview();
  sourceCommandVersionId.value = version.id;
  form.commandContent = version.content;
}

async function onScriptConfirm(command: Api.Automation.CommandRecord) {
  form.selectedCommand = command;
  // 从脚本库选择时预填作业名称，避免历史记录全部显示系统模板名
  form.jobName = command.name;
  await loadCommandVersions(command.id, true);
}

async function loadCommandVersions(commandId: number, allowTypeFallback = false) {
  invalidateCommandVersions();
  const requestId = commandRequestId;
  const requestedType = commandType.value;
  loadingCommandVersions.value = true;
  try {
    const { data, error } = await fetchGetCommandVersions(commandId);
    if (
      requestId !== commandRequestId ||
      commandSource.value !== 'library' ||
      form.selectedCommand?.id !== commandId ||
      commandType.value !== requestedType
    )
      return;
    if (error || !Array.isArray(data)) return;
    const published = data.filter(item => item.status === 'published');
    const matched = published.filter(item => item.commandType === requestedType);
    if (matched.length || !allowTypeFallback) {
      applyPublishedVersions(matched);
      return;
    }
    const supported = published.find(item => commandTypeOptions.some(option => option.value === item.commandType));
    const supportedType = commandTypeOptions.find(option => option.value === supported?.commandType);
    // 同步 watcher 会使本次请求失效，再按资源支持的类型加载。
    if (supportedType) commandType.value = supportedType.value;
  } finally {
    if (requestId === commandRequestId) loadingCommandVersions.value = false;
  }
}

/** 本地上传：读取文件文本填入代码框（可继续编辑），并按扩展名联动脚本类型 */
function onScriptFileChange(uploadFile: UploadFile) {
  const raw = uploadFile.raw;
  if (!raw) return;
  if (raw.size > 1024 * 1024) {
    window.$message?.error('脚本文件不能超过 1MB');
    return;
  }
  const ext = raw.name.split('.').pop()?.toLowerCase() ?? '';
  const extTypeMap: Record<string, CommandType> = {
    sh: 'linux_shell',
    bash: 'linux_shell',
    py: 'python',
    ps1: 'windows_powershell'
  };
  const mappedType = extTypeMap[ext];
  if (mappedType && mappedType !== commandType.value) {
    commandType.value = mappedType;
  }
  invalidateCommandVersions();
  const requestId = commandRequestId;
  const reader = new FileReader();
  reader.onload = () => {
    if (requestId !== commandRequestId || commandSource.value !== 'upload') return;
    form.commandContent = String(reader.result ?? '');
  };
  reader.readAsText(raw, 'utf-8');
}

/** ============ 执行配置 ============ */

const gatewayId = ref<number | null>(null);
const executionPolicy = reactive({
  hostStrategy: 'inherit' as 'inherit' | 'parallel' | 'serial' | 'rolling',
  forks: null as number | null,
  serialBatch: null as number | null,
  maxFailPercentage: null as number | null,
  timeoutSeconds: null as number | null
});
const envFieldRef = ref<InstanceType<typeof EnvSelectField>>();
const hostFieldRef = ref<InstanceType<typeof HostSelectField>>();

/** ============ 提交与重置 ============ */

const submitting = ref(false);
const previewVisible = ref(false);
const preview = shallowRef<Api.Jobs.RunPreview | null>(null);
const pendingPayload = shallowRef<Api.Jobs.QuickCommandRunPayload | null>(null);
let previewRequestId = 0;

function invalidatePreview() {
  previewRequestId += 1;
  previewVisible.value = false;
  preview.value = null;
  pendingPayload.value = null;
}

/** 脚本库来源时必须已选择脚本 */
function validateSelectedCommand(_rule: unknown, _value: unknown, callback: (error?: Error) => void) {
  if (commandSource.value === 'library' && !form.selectedCommand) return callback(new Error('请选择脚本'));
  return callback();
}

/** 目标主机为弹窗多选，required 基础规则无法校验空数组，用自定义 validator */
function validateHosts(_rule: unknown, _value: Api.Cmdb.HostRecord[], callback: (error?: Error) => void) {
  if (!form.hosts.length) return callback(new Error('请选择目标主机'));
  return callback();
}

const formRules = {
  workerPoolId: [{ required: true, message: '请选择执行资源', trigger: 'change' }],
  selectedCommand: [{ validator: validateSelectedCommand, trigger: 'change' }],
  commandContent: [{ required: true, message: '请输入命令内容或从脚本库选择模板', trigger: 'blur' }],
  hosts: [{ validator: validateHosts, trigger: 'change' }]
};

async function onSubmit() {
  if (!hasAuth('jobs.quick_command:execute') || submitting.value || loadingCommandVersions.value) return;
  submitting.value = true;
  const requestId = previewRequestId;
  try {
    await formRef.value?.validate();
    if (requestId !== previewRequestId || loadingCommandVersions.value) return;
    if (commandSource.value === 'library' && !sourceCommandVersionId.value) return;
    const extraVars = extraVarsRef.value?.getValue();
    if (!extraVars) return;

    const mismatched = form.hosts.filter(host => (host.osFamily ?? '').toLowerCase() !== expectedOsFamily.value);
    if (mismatched.length) {
      const names = mismatched
        .slice(0, 5)
        .map(host => host.hostname)
        .join('、');
      window.$message?.warning(
        `以下 ${mismatched.length} 台主机与当前脚本类型（${expectedOsFamily.value}）不符：${names}${
          mismatched.length > 5 ? ' 等' : ''
        }`
      );
      return;
    }

    const payload: Api.Jobs.QuickCommandRunPayload = {
      name: form.jobName.trim(),
      hostIds: form.hosts.map(host => host.id),
      workerPoolId: form.workerPoolId,
      gatewayId: gatewayId.value,
      extraVars,
      commandType: commandType.value,
      commandContent: form.commandContent,
      sourceCommandVersionId: sourceCommandVersionId.value,
      hostStrategy: executionPolicy.hostStrategy === 'inherit' ? null : executionPolicy.hostStrategy,
      forks: executionPolicy.forks,
      serialBatch: executionPolicy.serialBatch,
      maxFailPercentage: executionPolicy.maxFailPercentage,
      timeoutSeconds: executionPolicy.timeoutSeconds
    };
    const { data, error } = await fetchPreviewQuickCommandRun(payload);
    if (requestId !== previewRequestId || error || !data) return;
    pendingPayload.value = payload;
    preview.value = data;
    previewVisible.value = true;
  } finally {
    submitting.value = false;
  }
}

async function confirmRun() {
  if (submitting.value || loadingCommandVersions.value || !pendingPayload.value || !preview.value) return;
  submitting.value = true;
  try {
    const { data, error } = await fetchCreateQuickCommandRun({
      ...pendingPayload.value,
      expectedTargetIds: preview.value.targets.map(target => target.hostId),
      expectedTargetFingerprint: preview.value.targetFingerprint,
      expectedConfirmationFingerprint: preview.value.confirmationFingerprint,
      executionRequestId: preview.value.executionRequestId
    });
    if (!error && data) {
      previewVisible.value = false;
      window.$notification?.success('已提交执行');
      router.push({ name: 'ops_run-detail', params: { id: data.id } });
    }
  } finally {
    submitting.value = false;
  }
}

function onReset() {
  invalidateCommandVersions();
  extraVarsRef.value?.reset();
  form.jobName = '';
  form.commandContent = '';
  sourceCommandVersionId.value = null;
  form.selectedCommand = null;
  executionPolicy.hostStrategy = 'inherit';
  executionPolicy.forks = null;
  executionPolicy.serialBatch = null;
  executionPolicy.maxFailPercentage = null;
  executionPolicy.timeoutSeconds = null;
  selectedVersionId.value = null;
  commandVersions.value = [];
  envFieldRef.value?.resetSelection();
  hostFieldRef.value?.clear();
  formRef.value?.clearValidate();
}

watch(
  commandSource,
  () => {
    invalidateCommandVersions();
    form.selectedCommand = null;
  },
  { flush: 'sync' }
);

watch(
  commandType,
  () => {
    if (commandSource.value === 'library' && form.selectedCommand) {
      loadCommandVersions(form.selectedCommand.id);
      return;
    }
    commandRequestId += 1;
    sourceCommandVersionId.value = null;
    invalidatePreview();
  },
  { flush: 'sync' }
);

onBeforeUnmount(invalidateCommandVersions);
</script>

<template>
  <div class="min-h-500px flex-col-stretch gap-16px overflow-hidden lt-sm:overflow-auto">
    <ElCard class="card-wrapper">
      <ElAlert type="info" :closable="false" class="mb-16px">
        适用于一次性快速批量执行脚本场景，可以直接使用脚本库中的脚本
      </ElAlert>

      <ElForm
        ref="formRef"
        :model="form"
        :rules="formRules"
        label-width="170px"
        label-position="right"
        label-suffix="："
        require-asterisk-position="left"
      >
        <ElFormItem label="作业名称" prop="jobName">
          <ElInput
            v-model="form.jobName"
            placeholder="留空自动生成，如：脚本执行-20260923-150042"
            maxlength="128"
            class="w-3/4"
          />
        </ElFormItem>
        <ElFormItem prop="workerPoolId">
          <template #label>
            <FormLabelHelp
              label="执行资源"
              :help="[
                '作业由所选执行节点池处理，默认池由管理员配置；',
                '下方网关用于经跳板机连接私有网络主机，不选则直连。'
              ]"
            />
          </template>
          <EnvSelectField ref="envFieldRef" v-model:worker-pool-id="form.workerPoolId" v-model:gateway-id="gatewayId" />
        </ElFormItem>
        <ElFormItem prop="hosts">
          <template #label>
            <FormLabelHelp
              label="目标主机"
              :help="[
                '弹窗内多选主机，支持按分组、系统与关键词筛选，可跨页累计选择；',
                '弹窗已按脚本类型对应的系统预过滤，系统不匹配将阻止执行。'
              ]"
            />
          </template>
          <HostSelectField ref="hostFieldRef" v-model:hosts="form.hosts" :expected-os-family="expectedOsFamily" />
        </ElFormItem>
        <ExtraVarsField ref="extraVarsRef" />
        <ExecutionPolicyFields v-model="executionPolicy" />
        <ElFormItem label="脚本来源" required>
          <ElRadioGroup v-model="commandSource">
            <ElRadio value="manual">手工录入</ElRadio>
            <ElRadio value="upload">本地上传</ElRadio>
            <ElRadio value="library">脚本库</ElRadio>
          </ElRadioGroup>
        </ElFormItem>
        <ElFormItem v-if="commandSource === 'upload'" label="上传脚本" required>
          <ElUpload
            :auto-upload="false"
            :show-file-list="false"
            accept=".sh,.bash,.py,.ps1,.txt"
            :on-change="onScriptFileChange"
          >
            <ElButton type="primary" plain>选择脚本文件</ElButton>
          </ElUpload>
        </ElFormItem>
        <ElFormItem v-if="commandSource === 'library'" label="选择脚本" prop="selectedCommand">
          <div class="w-full flex flex-wrap items-center gap-8px">
            <ElButton type="primary" plain @click="scriptModalVisible = true">
              {{ form.selectedCommand ? `已选：${form.selectedCommand.name}` : '请选择脚本' }}
            </ElButton>
            <ElSelect
              v-model="selectedVersionId"
              placeholder="版本"
              class="w-140px"
              :disabled="loadingCommandVersions || !commandVersions.length"
              :loading="loadingCommandVersions"
              @change="applySelectedVersion"
            >
              <ElOption v-for="ver in commandVersions" :key="ver.id" :label="`v${ver.version}`" :value="ver.id" />
            </ElSelect>
          </div>
        </ElFormItem>
        <ElFormItem required>
          <template #label>
            <FormLabelHelp
              label="脚本类型"
              :help="[
                '决定脚本解释器与目标主机系统：Shell / Python 对应 Linux，PowerShell 对应 Windows；',
                '主机系统与脚本类型不匹配时将阻止执行。'
              ]"
            />
          </template>
          <ElRadioGroup v-model="commandType">
            <ElRadio v-for="item in commandTypeOptions" :key="item.value" :value="item.value">
              {{ item.label }}
            </ElRadio>
          </ElRadioGroup>
        </ElFormItem>
        <ElFormItem label="脚本内容" prop="commandContent">
          <div class="min-w-480px w-3/4">
            <CodeEditor
              v-model="form.commandContent"
              :language="editorLanguage"
              :readonly="commandSource === 'library'"
              height="380px"
              :placeholder="
                commandSource === 'upload'
                  ? '本地上传：选择脚本文件后内容自动填充，可继续编辑'
                  : '手工录入：输入要在目标主机上执行的命令，支持多行，逐行依次执行'
              "
            />
          </div>
        </ElFormItem>
      </ElForm>

      <div class="ml-40px w-3/4 flex justify-end gap-8px">
        <ElButton @click="onReset">重置</ElButton>
        <ElButton type="primary" :loading="submitting" :disabled="loadingCommandVersions" @click="onSubmit">
          执行脚本
        </ElButton>
      </div>
    </ElCard>

    <RunPreviewDialog v-model:visible="previewVisible" :preview="preview" :loading="submitting" @confirm="confirmRun" />
    <ScriptSelectModal
      v-model:visible="scriptModalVisible"
      :selected="form.selectedCommand"
      @confirm="onScriptConfirm"
    />
  </div>
</template>

<style scoped>
:deep(.el-form-item__label) {
  white-space: nowrap;
}
</style>
