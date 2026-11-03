<script setup lang="ts">
import { onBeforeUnmount, reactive, ref, shallowRef, watch } from 'vue';
import { useRouter } from 'vue-router';
import type { UploadFile } from 'element-plus';
import { fetchCreatePlaybookRun, fetchPreviewPlaybookRun } from '@/service/api';
import { fetchGetCommandList, fetchGetCommandVersions } from '@/service/api/automation';
import { useAuth } from '@/hooks/business/auth';
import CodeEditor from '@/components/common/code-editor/index.vue';
import RunPreviewDialog from '@/components/business/run-preview-dialog/index.vue';
import EnvSelectField from '../components/env-select-field.vue';
import ExecutionPolicyFields from '../components/execution-policy-fields.vue';
import ExtraVarsField from '../components/extra-vars-field.vue';
import HostSelectField from '../components/host-select-field.vue';

defineOptions({ name: 'OpsQuickExecutePlaybook' });

const router = useRouter();
const { hasAuth } = useAuth();

/** Playbook 目标主机限 Linux */
const expectedOsFamily = 'linux';

/** ============ 表单模型（参与提交校验的字段收口于此，rules 见 formRules） ============ */

const form = reactive({
  /** 作业名称：留空提交时由后端自动生成（剧本执行-时间戳）；兼任 playbook_name 元数据 */
  jobName: '',
  workerPoolId: null as number | null,
  /** 内容来源为"自动化配置"时已选的 Playbook */
  selectedPlaybookId: null as number | null,
  playbookContent: '',
  hosts: [] as Api.Cmdb.HostRecord[]
});

const formRef = ref();
const extraVarsRef = ref<InstanceType<typeof ExtraVarsField>>();

/** ============ Playbook 内容与三来源（在线编写 / 本地上传 / 资源库加载） ============ */

type PlaybookSource = 'manual' | 'upload' | 'library';

const playbookSource = ref<PlaybookSource>('manual');

const playbooks = shallowRef<Api.Automation.CommandRecord[]>([]);
const playbookVersions = shallowRef<Api.Automation.CommandVersionRecord[]>([]);
const selectedPlaybookVersionId = ref<number | null>(null);

let playbookRequestId = 0;
let playbookOptionsRequestId = 0;
let fileRequestId = 0;

async function loadPlaybooks(search = '') {
  playbookOptionsRequestId += 1;
  const requestId = playbookOptionsRequestId;
  const { data, error } = await fetchGetCommandList({
    current: 1,
    size: 100,
    status: 'published',
    search,
    resourceKind: 'playbook'
  });
  if (requestId !== playbookOptionsRequestId) return;
  if (!error && data) {
    playbooks.value = data.records;
  }
}

function applyPlaybookVersion(version: Api.Automation.CommandVersionRecord) {
  selectedPlaybookVersionId.value = version.id;
  form.playbookContent = version.content;
}

async function onPlaybookSelected(playbookId: number) {
  playbookRequestId += 1;
  const requestId = playbookRequestId;
  selectedPlaybookVersionId.value = null;
  playbookVersions.value = [];
  form.playbookContent = '';
  // 从资源库选择时预填作业名称为 Playbook 名
  const playbook = playbooks.value.find(item => item.id === playbookId);
  if (playbook) form.jobName = playbook.name;
  const { data, error } = await fetchGetCommandVersions(playbookId);
  if (requestId !== playbookRequestId || playbookSource.value !== 'library' || form.selectedPlaybookId !== playbookId)
    return;
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
  fileRequestId += 1;
  const requestId = fileRequestId;
  const reader = new FileReader();
  reader.onload = () => {
    if (requestId !== fileRequestId || playbookSource.value !== 'upload') return;
    form.playbookContent = String(reader.result ?? '');
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
let previewRequestId = 0;
const pendingPayload = shallowRef<Api.Jobs.PlaybookRunPayload | null>(null);

/** 内容来源为"自动化配置"时必须已选择 Playbook */
function validateSelectedPlaybook(_rule: unknown, _value: unknown, callback: (error?: Error) => void) {
  if (
    playbookSource.value === 'library' &&
    (form.selectedPlaybookId === null || selectedPlaybookVersionId.value === null)
  ) {
    return callback(new Error('请选择已发布的 Playbook 版本'));
  }
  return callback();
}

/** 目标主机为弹窗多选，required 基础规则无法校验空数组，用自定义 validator */
function validateHosts(_rule: unknown, _value: Api.Cmdb.HostRecord[], callback: (error?: Error) => void) {
  if (!form.hosts.length) return callback(new Error('请选择目标主机'));
  return callback();
}

const formRules = {
  workerPoolId: [{ required: true, message: '请选择执行资源', trigger: 'change' }],
  selectedPlaybookId: [{ validator: validateSelectedPlaybook, trigger: 'change' }],
  playbookContent: [{ required: true, message: '请输入 Playbook YAML 内容', trigger: 'blur' }],
  hosts: [{ validator: validateHosts, trigger: 'change' }]
};

async function onSubmit() {
  if (!hasAuth('jobs.playbook_run:execute')) return;
  if (submitting.value) return;
  submitting.value = true;
  const requestId = previewRequestId;
  try {
    const valid = await formRef.value?.validate().catch(() => false);
    if (!valid || requestId !== previewRequestId) return;
    const extraVars = extraVarsRef.value?.getValue();
    if (!extraVars) return;

    const mismatched = form.hosts.filter(host => (host.osFamily ?? '').toLowerCase() !== expectedOsFamily);
    if (mismatched.length) {
      const names = mismatched
        .slice(0, 5)
        .map(host => host.hostname)
        .join('、');
      window.$message?.warning(
        `以下 ${mismatched.length} 台主机与 Playbook 要求（linux）不符：${names}${mismatched.length > 5 ? ' 等' : ''}`
      );
      return;
    }

    const jobName = form.jobName.trim();
    const payload: Api.Jobs.PlaybookRunPayload = {
      name: jobName,
      hostIds: form.hosts.map(host => host.id),
      workerPoolId: form.workerPoolId,
      gatewayId: gatewayId.value,
      extraVars,
      playbookContent: form.playbookContent,
      playbookVersionId: playbookSource.value === 'library' ? selectedPlaybookVersionId.value : null,
      playbookName: jobName || 'Playbook',
      hostStrategy: executionPolicy.hostStrategy === 'inherit' ? null : executionPolicy.hostStrategy,
      forks: executionPolicy.forks,
      serialBatch: executionPolicy.serialBatch,
      maxFailPercentage: executionPolicy.maxFailPercentage,
      timeoutSeconds: executionPolicy.timeoutSeconds
    };
    const { data, error } = await fetchPreviewPlaybookRun(payload);
    if (error || !data || requestId !== previewRequestId) return;
    pendingPayload.value = payload;
    preview.value = data;
    previewVisible.value = true;
  } finally {
    submitting.value = false;
  }
}

function invalidatePreview() {
  previewRequestId += 1;
  previewVisible.value = false;
  preview.value = null;
  pendingPayload.value = null;
}

async function confirmRun() {
  if (submitting.value || !pendingPayload.value || !preview.value) return;
  const confirmedPayload = pendingPayload.value;
  const requestId = previewRequestId;
  submitting.value = true;
  try {
    const { data, error } = await fetchCreatePlaybookRun({
      ...confirmedPayload,
      expectedTargetIds: preview.value.targets.map(target => target.hostId),
      expectedTargetFingerprint: preview.value.targetFingerprint,
      expectedConfirmationFingerprint: preview.value.confirmationFingerprint,
      executionRequestId: preview.value.executionRequestId
    });
    if (!error && data && requestId === previewRequestId) {
      previewVisible.value = false;
      window.$notification?.success('已提交执行');
      router.push({ name: 'ops_run-detail', params: { id: data.id } });
    }
  } finally {
    submitting.value = false;
  }
}

function onReset() {
  playbookRequestId += 1;
  fileRequestId += 1;
  previewVisible.value = false;
  preview.value = null;
  pendingPayload.value = null;
  extraVarsRef.value?.reset();
  form.jobName = '';
  form.playbookContent = '';
  executionPolicy.hostStrategy = 'inherit';
  executionPolicy.forks = null;
  executionPolicy.serialBatch = null;
  executionPolicy.maxFailPercentage = null;
  executionPolicy.timeoutSeconds = null;
  playbookSource.value = 'manual';
  form.selectedPlaybookId = null;
  selectedPlaybookVersionId.value = null;
  playbookVersions.value = [];
  envFieldRef.value?.resetSelection();
  hostFieldRef.value?.clear();
  formRef.value?.clearValidate();
}

watch(
  playbookSource,
  () => {
    playbookRequestId += 1;
    fileRequestId += 1;
    selectedPlaybookVersionId.value = null;
    playbookVersions.value = [];
    form.selectedPlaybookId = null;
    form.playbookContent = '';
  },
  { flush: 'sync' }
);

watch([form, executionPolicy, gatewayId], invalidatePreview, { deep: true, flush: 'sync' });

onBeforeUnmount(() => {
  invalidatePreview();
  playbookRequestId += 1;
  playbookOptionsRequestId += 1;
  fileRequestId += 1;
});

loadPlaybooks();
</script>

<template>
  <div class="min-h-500px flex-col-stretch gap-16px overflow-hidden lt-sm:overflow-auto">
    <ElCard class="card-wrapper">
      <ElAlert type="info" :closable="false" class="mb-16px">
        通过 ansible-playbook 在目标主机（Linux）上批量执行 Playbook
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
            placeholder="留空自动生成，如：剧本执行-20260923-150042"
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
                'Playbook 仅支持 Linux 主机，弹窗已按 Linux 预过滤（可手动更改）；',
                '支持按分组、关键词筛选，可跨页累计选择。'
              ]"
            />
          </template>
          <HostSelectField ref="hostFieldRef" v-model:hosts="form.hosts" :expected-os-family="expectedOsFamily" />
        </ElFormItem>
        <ExtraVarsField ref="extraVarsRef" />
        <ExecutionPolicyFields v-model="executionPolicy" />
        <ElFormItem label="内容来源" required>
          <ElRadioGroup v-model="playbookSource">
            <ElRadio value="manual">在线编写</ElRadio>
            <ElRadio value="upload">本地上传</ElRadio>
            <ElRadio value="library">自动化配置</ElRadio>
          </ElRadioGroup>
        </ElFormItem>
        <ElFormItem v-if="playbookSource === 'upload'" label="上传 Playbook" required>
          <ElUpload :auto-upload="false" :show-file-list="false" accept=".yml,.yaml" :on-change="onPlaybookFileChange">
            <ElButton type="primary" plain>选择 YAML 文件</ElButton>
          </ElUpload>
        </ElFormItem>
        <ElFormItem v-if="playbookSource === 'library'" label="选择 Playbook" prop="selectedPlaybookId">
          <div class="w-full flex flex-wrap items-center gap-8px">
            <ElSelect
              v-model="form.selectedPlaybookId"
              filterable
              remote
              :remote-method="loadPlaybooks"
              class="w-260px"
              placeholder="输入名称搜索 Playbook"
              @change="onPlaybookSelected"
            >
              <ElOption v-for="pb in playbooks" :key="pb.id" :label="pb.name" :value="pb.id" />
            </ElSelect>
            <ElSelect
              v-model="selectedPlaybookVersionId"
              class="w-120px"
              placeholder="版本"
              :disabled="!playbookVersions.length"
              @change="onPlaybookVersionChange"
            >
              <ElOption v-for="ver in playbookVersions" :key="ver.id" :label="`v${ver.version}`" :value="ver.id" />
            </ElSelect>
          </div>
        </ElFormItem>
        <ElFormItem prop="playbookContent">
          <template #label>
            <FormLabelHelp
              label="Playbook 内容"
              :help="[
                '粘贴完整 Playbook YAML（可包含多个 play），由 ansible-playbook 执行；',
                'YAML 中的 hosts 会被强制为本次选择的目标主机。'
              ]"
            />
          </template>
          <div class="min-w-480px w-3/4">
            <CodeEditor
              v-model="form.playbookContent"
              language="yaml"
              :readonly="playbookSource === 'library'"
              height="380px"
              placeholder="粘贴 Ansible Playbook YAML 内容，或从上方切换内容来源"
            />
          </div>
        </ElFormItem>
      </ElForm>

      <div class="ml-40px w-3/4 flex justify-end gap-8px">
        <ElButton @click="onReset">重置</ElButton>
        <ElButton type="primary" :loading="submitting" @click="onSubmit">执行Playbook</ElButton>
      </div>
    </ElCard>

    <RunPreviewDialog v-model:visible="previewVisible" :preview="preview" :loading="submitting" @confirm="confirmRun" />
  </div>
</template>

<style scoped>
:deep(.el-form-item__label) {
  white-space: nowrap;
}
</style>
