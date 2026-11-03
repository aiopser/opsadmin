<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, shallowRef, watch } from 'vue';
import { useRouter } from 'vue-router';
import { getModuleParamDocs, versionModuleParamDocs } from '@/constants/ansible-module-param-docs';
import { fetchCreateModuleRun, fetchPreviewModuleRun } from '@/service/api';
import { fetchGetCommandList, fetchGetCommandVersions } from '@/service/api/automation';
import { useAuth } from '@/hooks/business/auth';
import RunPreviewDialog from '@/components/business/run-preview-dialog/index.vue';
import ModuleParamDocs from '@/components/common/module-param-docs/index.vue';
import EnvSelectField from '../components/env-select-field.vue';
import ExecutionPolicyFields from '../components/execution-policy-fields.vue';
import ExtraVarsField from '../components/extra-vars-field.vue';
import HostSelectField from '../components/host-select-field.vue';

defineOptions({ name: 'OpsQuickExecuteModule' });

const router = useRouter();
const { hasAuth } = useAuth();

/** Ansible Module 目标主机限 Linux */
const expectedOsFamily = 'linux';

/** free-form 模块（按短名判断，与后端 ModuleRunCreateSerializer 一致） */
const FREE_FORM_MODULES = ['shell', 'command', 'script', 'raw'];

const RISK_LEVEL_META: Record<string, { label: string; type: 'success' | 'warning' | 'danger' }> = {
  low: { label: '低风险', type: 'success' },
  medium: { label: '中风险', type: 'warning' },
  high: { label: '高风险', type: 'danger' }
};

/** ============ 内容来源与模块 ============ */

type ContentSource = 'library' | 'custom';

const contentSourceOptions: Array<{ label: string; value: ContentSource }> = [
  { label: '资源库', value: 'library' },
  { label: '在线编写', value: 'custom' }
];

const contentSource = ref<ContentSource>('library');

const modules = shallowRef<Api.Automation.CommandRecord[]>([]);
const moduleVersions = shallowRef<Api.Automation.CommandVersionRecord[]>([]);
const selectedModuleId = ref<number | null>(null);
const selectedModuleVersionId = ref<number | null>(null);
/** 在线编写的 Module 名称（rules 见 moduleFormRules） */
const moduleForm = reactive({ customModuleName: '' });
const moduleFormRef = ref();
const moduleArgs = ref('');
const defaultArgsApplied = ref(false);

/** 在线编写模块名与后端校验一致 */
const MODULE_NAME_PATTERN = /^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z][A-Za-z0-9_]*){0,4}$/;

const selectedModule = computed(() => modules.value.find(item => item.id === selectedModuleId.value) ?? null);
const selectedModuleVersion = computed(
  () => moduleVersions.value.find(item => item.id === selectedModuleVersionId.value) ?? null
);
const moduleContent = computed(() => {
  if (contentSource.value === 'custom') return moduleForm.customModuleName.trim();
  return (selectedModuleVersion.value?.moduleName || selectedModuleVersion.value?.content || '').trim();
});
const isFreeForm = computed(() => FREE_FORM_MODULES.includes(moduleContent.value.split('.').pop() ?? ''));

const riskTagType = computed(() => RISK_LEVEL_META[selectedModule.value?.riskLevel ?? '']?.type ?? 'info');
const riskTagLabel = computed(() => RISK_LEVEL_META[selectedModule.value?.riskLevel ?? '']?.label ?? '未知风险');

/** 参数说明：优先取所选版本自身配置的参数说明，未配置时回退内置字典（在线编写无版本，仅内置字典） */
const moduleParamDocs = computed(() => {
  if (contentSource.value !== 'library') return getModuleParamDocs(moduleContent.value);
  return selectedModuleVersion.value ? versionModuleParamDocs(selectedModuleVersion.value) : null;
});

let moduleRequestId = 0;
let moduleOptionsRequestId = 0;

async function loadModules(search = '') {
  moduleOptionsRequestId += 1;
  const requestId = moduleOptionsRequestId;
  const { data, error } = await fetchGetCommandList({
    current: 1,
    size: 100,
    status: 'published',
    search,
    resourceKind: 'module'
  });
  if (requestId !== moduleOptionsRequestId) return;
  if (!error && data) {
    modules.value = data.records;
  }
}

/** 读取版本默认模块参数（defaultVars.module_args，与后端序列化逻辑一致） */
function versionDefaultArgs(version: Api.Automation.CommandVersionRecord) {
  if ((version.moduleName && !version.content) || 'x-module-parameter-docs' in (version.argumentSchema ?? {}))
    return '';
  const raw = (version.defaultVars ?? {}).module_args;
  if (typeof raw === 'string') return raw;
  if (raw && typeof raw === 'object') return JSON.stringify(raw, null, 2);
  return '';
}

/** 选中模块：加载已发布版本并默认选中第一个（带入默认参数） */
async function onModuleSelected(moduleId: number) {
  moduleRequestId += 1;
  const requestId = moduleRequestId;
  selectedModuleVersionId.value = null;
  moduleVersions.value = [];
  moduleArgs.value = '';
  defaultArgsApplied.value = false;
  const { data, error } = await fetchGetCommandVersions(moduleId);
  if (
    requestId !== moduleRequestId ||
    contentSource.value !== 'library' ||
    error ||
    !data ||
    selectedModuleId.value !== moduleId
  )
    return;
  moduleVersions.value = data.filter(item => item.status === 'published');
  const first = moduleVersions.value[0];
  if (first) {
    selectedModuleVersionId.value = first.id;
    applyVersionDefault(first);
  }
}

/** 切换版本：带入默认参数 */
function onVersionSelected(versionId: number) {
  const version = moduleVersions.value.find(item => item.id === versionId);
  if (version) {
    applyVersionDefault(version);
  }
}

function applyVersionDefault(version: Api.Automation.CommandVersionRecord) {
  moduleArgs.value = versionDefaultArgs(version);
  defaultArgsApplied.value = Boolean(moduleArgs.value);
}

/** 切换内容来源：清空模块与参数 */
function onSourceChanged() {
  invalidatePreview();
  moduleRequestId += 1;
  moduleVersions.value = [];
  selectedModuleVersionId.value = null;
  selectedModuleId.value = null;
  moduleForm.customModuleName = '';
  moduleArgs.value = '';
  defaultArgsApplied.value = false;
}

/** ============ 执行配置 ============ */

/** 左栏表单模型（执行资源与目标主机，rules 见 formRules） */
const form = reactive({
  /** 作业名称：留空提交时由后端自动生成（模块执行-时间戳） */
  jobName: '',
  workerPoolId: null as number | null,
  hosts: [] as Api.Cmdb.HostRecord[]
});

const formRef = ref();
const extraVarsRef = ref<InstanceType<typeof ExtraVarsField>>();

const executionPolicy = reactive({
  hostStrategy: 'inherit' as 'inherit' | 'parallel' | 'serial' | 'rolling',
  forks: null as number | null,
  serialBatch: null as number | null,
  maxFailPercentage: null as number | null,
  timeoutSeconds: null as number | null
});
const gatewayId = ref<number | null>(null);

// 从资源库选择 Module 时预填作业名称为 Module 名
watch(selectedModuleId, moduleId => {
  const module = modules.value.find(item => item.id === moduleId);
  if (module) form.jobName = module.name;
});

/** ============ 命令预览 ============ */

const commandPreview = computed(() => {
  if (!moduleContent.value) return '';
  const args = moduleArgs.value.trim();
  if (isFreeForm.value) {
    return `${moduleContent.value} ${args}`;
  }
  return `ansible all -m ${moduleContent.value} -a "${args}"`;
});

async function copyCommand() {
  if (!commandPreview.value) return;
  try {
    await navigator.clipboard.writeText(commandPreview.value);
    window.$notification?.success('已复制');
  } catch {
    window.$message?.error('复制失败，请手动复制');
  }
}

/** ============ 提交 ============ */

const submitting = ref(false);
const previewVisible = ref(false);
const preview = shallowRef<Api.Jobs.RunPreview | null>(null);
let previewRequestId = 0;
const pendingPayload = shallowRef<Api.Jobs.ModuleRunPayload | null>(null);

/** 在线编写的 Module 名称必填，格式与后端 ModuleRunCreateSerializer 校验一致 */
function validateCustomModuleName(_rule: unknown, value: string, callback: (error?: Error) => void) {
  const name = value.trim();
  if (!name) return callback(new Error('请填写 Module 名称'));
  if (!MODULE_NAME_PATTERN.test(name)) {
    return callback(new Error('Module 名称格式不合法，示例：shell 或 ansible.builtin.yum'));
  }
  return callback();
}

const moduleFormRules = {
  customModuleName: [{ validator: validateCustomModuleName, trigger: 'blur' }]
};

/** 目标主机为弹窗多选，required 基础规则无法校验空数组，用自定义 validator */
function validateHosts(_rule: unknown, _value: Api.Cmdb.HostRecord[], callback: (error?: Error) => void) {
  if (!form.hosts.length) return callback(new Error('请选择目标主机'));
  return callback();
}

const formRules = {
  workerPoolId: [{ required: true, message: '请选择执行资源', trigger: 'change' }],
  hosts: [{ validator: validateHosts, trigger: 'change' }]
};

function validateModuleHosts(): boolean {
  const mismatched = form.hosts.filter(host => (host.osFamily ?? '').toLowerCase() !== expectedOsFamily);
  if (mismatched.length) {
    const names = mismatched
      .slice(0, 5)
      .map(host => host.hostname)
      .join('、');
    window.$message?.warning(
      `以下 ${mismatched.length} 台主机与 Module 要求（linux）不符：${names}${mismatched.length > 5 ? ' 等' : ''}`
    );
    return false;
  }

  return true;
}

async function submitRun(checkMode: boolean) {
  if (!hasAuth('jobs.module_run:execute')) return;
  if (submitting.value) return;
  submitting.value = true;
  const requestId = previewRequestId;
  try {
    const valid = await formRef.value?.validate().catch(() => false);
    if (!valid || requestId !== previewRequestId) return;
    const extraVars = extraVarsRef.value?.getValue();
    if (!extraVars) return;

    if (contentSource.value === 'custom') {
      await moduleFormRef.value?.validate();
    } else if (!selectedModuleVersionId.value) {
      // Module 与版本为两个联动字段（选中 Module 后版本自动带出），保留聚合提示
      window.$message?.warning('请选择 Module 及版本');
      return;
    }

    if (!validateModuleHosts()) return;

    const moduleVersionId = selectedModuleVersionId.value;
    const payload: Api.Jobs.ModuleRunPayload = {
      name: form.jobName.trim(),
      hostIds: form.hosts.map(host => host.id),
      workerPoolId: form.workerPoolId,
      gatewayId: gatewayId.value,
      extraVars,
      moduleArgs: moduleArgs.value,
      hostStrategy: executionPolicy.hostStrategy === 'inherit' ? null : executionPolicy.hostStrategy,
      forks: executionPolicy.forks,
      serialBatch: executionPolicy.serialBatch,
      maxFailPercentage: executionPolicy.maxFailPercentage,
      timeoutSeconds: executionPolicy.timeoutSeconds,
      ...(checkMode ? { checkMode: true } : {})
    };
    if (contentSource.value === 'custom') {
      payload.moduleName = moduleForm.customModuleName.trim();
    } else if (moduleVersionId !== null) {
      payload.moduleVersionId = moduleVersionId;
    }
    const { data, error } = await fetchPreviewModuleRun(payload);
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
    const { data, error } = await fetchCreateModuleRun({
      ...confirmedPayload,
      expectedTargetIds: preview.value.targets.map(target => target.hostId),
      expectedTargetFingerprint: preview.value.targetFingerprint,
      expectedConfirmationFingerprint: preview.value.confirmationFingerprint,
      executionRequestId: preview.value.executionRequestId
    });
    if (!error && data && requestId === previewRequestId) {
      previewVisible.value = false;
      window.$notification?.success(confirmedPayload.checkMode ? '已提交检查模式执行' : '已提交执行');
      router.push({ name: 'ops_run-detail', params: { id: data.id } });
    }
  } finally {
    submitting.value = false;
  }
}

watch([form, executionPolicy, gatewayId, moduleArgs, contentSource, selectedModuleVersionId], invalidatePreview, {
  deep: true,
  flush: 'sync'
});

onBeforeUnmount(() => {
  invalidatePreview();
  moduleRequestId += 1;
  moduleOptionsRequestId += 1;
});

loadModules();
</script>

<template>
  <div class="h-full min-h-500px flex gap-12px overflow-hidden lt-sm:h-auto lt-sm:flex-col lt-sm:overflow-auto">
    <!-- 左栏：执行前置 -->
    <ElCard
      class="w-520px flex flex-col flex-shrink-0 card-wrapper lt-sm:w-full"
      :body-style="{ flex: '1 1 auto', display: 'flex', flexDirection: 'column' }"
    >
      <ElForm
        ref="formRef"
        :model="form"
        :rules="formRules"
        label-position="top"
        label-suffix="："
        require-asterisk-position="left"
      >
        <ElFormItem label="作业名称" prop="jobName">
          <ElInput
            v-model="form.jobName"
            placeholder="留空自动生成，如：模块执行-20260923-150042"
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
          <EnvSelectField v-model:worker-pool-id="form.workerPoolId" v-model:gateway-id="gatewayId" />
        </ElFormItem>
        <ElFormItem prop="hosts">
          <template #label>
            <FormLabelHelp
              label="目标主机"
              :help="[
                'Module 仅支持 Linux 主机，弹窗已按 Linux 预过滤（可手动更改）；',
                '支持按分组、关键词筛选，可跨页累计选择。'
              ]"
            />
          </template>
          <HostSelectField v-model:hosts="form.hosts" :expected-os-family="expectedOsFamily" />
        </ElFormItem>
        <ExtraVarsField ref="extraVarsRef" />
        <ExecutionPolicyFields v-model="executionPolicy" />
      </ElForm>
      <div class="mt-auto flex justify-end gap-8px pt-12px">
        <ElButton type="primary" :loading="submitting" @click="submitRun(false)">运行</ElButton>
        <ElButton type="primary" plain :disabled="submitting" @click="submitRun(true)">试运行</ElButton>
      </div>
    </ElCard>

    <!-- 右栏：Module 执行（约占 2/3 宽，不铺满） -->
    <ElCard class="w-2/3 flex-shrink-0 overflow-y-auto card-wrapper lt-sm:w-full">
      <div class="flex flex-col gap-20px">
        <ElForm
          ref="moduleFormRef"
          :model="moduleForm"
          :rules="moduleFormRules"
          label-position="top"
          class="module-form-row"
          label-suffix="："
          require-asterisk-position="left"
        >
          <ElFormItem label="内容来源" class="w-full">
            <ElRadioGroup v-model="contentSource" @change="onSourceChanged">
              <ElRadio v-for="option in contentSourceOptions" :key="option.value" :value="option.value">
                {{ option.label }}
              </ElRadio>
            </ElRadioGroup>
          </ElFormItem>
          <ElFormItem v-if="contentSource === 'library'" label="Module" required class="w-260px">
            <ElSelect
              v-model="selectedModuleId"
              filterable
              remote
              :remote-method="loadModules"
              placeholder="输入名称搜索 Module"
              @change="onModuleSelected"
            >
              <ElOption v-for="mod in modules" :key="mod.id" :label="mod.name" :value="mod.id" />
            </ElSelect>
          </ElFormItem>
          <ElFormItem v-else label="Module 名称" prop="customModuleName" class="w-410px">
            <ElInput
              v-model="moduleForm.customModuleName"
              class="font-mono"
              placeholder="如 shell 或 ansible.builtin.yum"
            />
          </ElFormItem>
          <ElFormItem v-if="contentSource === 'library'" class="w-130px flex-shrink-0">
            <template #label>
              <FormLabelHelp
                label="版本"
                :help="['参数说明来自执行资源中该已发布版本的配置。切换版本后请重新核对本次参数。']"
              />
            </template>
            <ElSelect
              v-model="selectedModuleVersionId"
              placeholder="版本"
              :disabled="!moduleVersions.length"
              @change="onVersionSelected"
            >
              <ElOption v-for="ver in moduleVersions" :key="ver.id" :label="`v${ver.version}`" :value="ver.id" />
            </ElSelect>
          </ElFormItem>
          <ElFormItem class="w-full">
            <template #label>
              <FormLabelHelp
                label="模块参数"
                :help="[
                  '支持 JSON 对象或 key=value，如 name=httpd state=present；',
                  'shell / command / script / raw 等 free-form 模块直接填写命令内容；',
                  '参数会经过命令过滤规则校验，命中规则的命令将被拦截。'
                ]"
              />
            </template>
            <ElInput
              v-model="moduleArgs"
              class="w-410px font-mono"
              placeholder="free-form 参数，如：name=httpd state=present"
            />
            <div v-if="defaultArgsApplied" class="mt-4px w-full text-12px text-gray-500">
              已带入版本默认参数，可直接修改
            </div>
          </ElFormItem>
        </ElForm>

        <div class="section">
          <div class="section-title">模块说明</div>
          <template v-if="contentSource === 'custom'">
            <p class="section-desc">
              在线编写模式：直接执行上方填写的 Module，不依赖资源库版本。模块风险未知，请自行确认来源与参数。
            </p>
          </template>
          <template v-else-if="selectedModule">
            <p class="section-desc">{{ selectedModule.description || '暂无说明' }}</p>
            <div class="mt-8px flex flex-wrap gap-8px">
              <ElTag size="small" type="info">ansible_module</ElTag>
              <ElTag v-if="selectedModuleVersion" size="small" type="success">
                已发布 v{{ selectedModuleVersion.version }}
              </ElTag>
              <ElTag size="small" :type="riskTagType">{{ riskTagLabel }}</ElTag>
            </div>
          </template>
          <p v-else class="section-desc">请先选择 Module</p>
        </div>

        <div class="section">
          <div class="section-title">参数说明</div>
          <ModuleParamDocs v-if="moduleParamDocs?.length" :options="moduleParamDocs" />
          <p v-else-if="contentSource === 'custom' && !moduleContent" class="section-desc">
            填写 Module 名称后展示参数说明
          </p>
          <p v-else-if="contentSource === 'library' && selectedModuleVersion" class="section-desc">
            该版本未配置参数说明，可在执行资源的 Module 版本中补充。
          </p>
          <p v-else-if="moduleParamDocs" class="section-desc">该模块无需参数，直接运行即可</p>
          <p v-else-if="contentSource === 'custom' || selectedModuleVersion" class="section-desc">
            该模块暂无内置参数说明，请按需填写参数
          </p>
          <p v-else class="section-desc">选择 Module 后展示参数说明</p>
        </div>

        <div class="section">
          <div class="section-title">命令预览</div>
          <div v-if="commandPreview" class="preview-box">
            <code class="min-w-0 flex-1 break-all">{{ commandPreview }}</code>
            <ElButton link type="primary" size="small" @click="copyCommand">复制</ElButton>
          </div>
          <p v-else class="section-desc">
            {{ contentSource === 'custom' ? '填写 Module 名称后生成命令预览' : '选择 Module 后生成命令预览' }}
          </p>
          <p class="mt-8px text-12px text-gray-500">
            实际执行由服务端 ansible-runner 以单任务 playbook 模式发起，此预览仅用于确认语义
          </p>
        </div>
      </div>
    </ElCard>

    <RunPreviewDialog v-model:visible="previewVisible" :preview="preview" :loading="submitting" @confirm="confirmRun" />
  </div>
</template>

<style scoped>
.module-form-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 16px;
}

/* 行间距交给 gap 控制，避免与 form-item 自带 margin 叠加 */
.module-form-row :deep(.el-form-item) {
  margin-bottom: 0;
}

.section-title {
  margin-bottom: 12px;
  padding-left: 8px;
  border-left: 3px solid var(--el-color-primary);
  font-size: 14px;
  font-weight: 600;
  line-height: 1.3;
}

.section-desc {
  margin: 0;
  color: var(--el-text-color-regular);
  font-size: 13px;
  line-height: 1.7;
}

.preview-box {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--el-fill-color-light);
  border: 1px solid var(--el-border-color-lighter);
  font-size: 13px;
}

:deep(.el-form-item__label) {
  white-space: nowrap;
}
</style>
