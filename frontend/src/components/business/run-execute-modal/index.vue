<script setup lang="ts">
import { computed, reactive, ref, shallowRef, watch } from 'vue';
import { useRouter } from 'vue-router';
import {
  fetchCreateWorkflowRun,
  fetchGetGatewayList,
  fetchGetWorkerPools,
  fetchGetWorkflowVersions,
  fetchPreviewWorkflowRun
} from '@/service/api';
import ExecutionSettingsFields from '@/components/business/execution-settings-fields/index.vue';
import HostSelectModal from '@/components/business/host-select-modal/index.vue';
import RunPreviewDialog from '@/components/business/run-preview-dialog/index.vue';

defineOptions({ name: 'RunExecuteModal' });

interface Props {
  visible: boolean;
  /** 工作流模板 id，弹窗打开时加载其已发布版本 */
  templateId: number | null;
  templateName?: string;
}

const props = withDefaults(defineProps<Props>(), {
  templateName: ''
});

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void;
  (e: 'submitted', runId: number): void;
}>();

const router = useRouter();

/** ============ 选项数据 ============ */

const versions = shallowRef<Api.Automation.WorkflowVersionRecord[]>([]);
const pools = shallowRef<Api.Jobs.WorkerPoolOption[]>([]);
const gateways = shallowRef<Api.Jobs.GatewayRecord[]>([]);

/** ============ 表单 ============ */

type HostStrategy = 'inherit' | 'parallel' | 'serial' | 'rolling';

function getInitForm() {
  return {
    version: null as number | null,
    pool: null as number | null,
    gateway: null as number | null,
    hostStrategy: 'inherit' as HostStrategy,
    forks: null as number | null,
    serialBatch: null as number | null,
    maxFailPercentage: null as number | null,
    timeoutSeconds: null as number | null
  };
}

const form = reactive(getInitForm());

/** 运行参数（按流程 inputSchema 动态渲染，整体替换以保持响应性） */
const inputVars = ref<Record<string, unknown>>({});

async function loadOptions() {
  const [versionResult, poolResult, gatewayResult] = await Promise.all([
    fetchGetWorkflowVersions(props.templateId as number),
    fetchGetWorkerPools(),
    fetchGetGatewayList({ current: 1, size: 100 })
  ]);
  if (!versionResult.error) {
    const published = versionResult.data
      .filter(item => item.status === 'published')
      .sort((a, b) => b.version - a.version);
    versions.value = published;
    form.version = published[0]?.id ?? null;
  }
  if (!poolResult.error) {
    pools.value = poolResult.data.list.filter(
      item => item.isActive && (!item.executionKinds.length || item.executionKinds.includes('workflow'))
    );
    form.pool = pools.value.find(item => item.isDefault)?.id ?? pools.value[0]?.id ?? null;
  }
  if (!gatewayResult.error && gatewayResult.data) {
    gateways.value = gatewayResult.data.records;
  }
}

/** ============ 流程版本与动态参数 ============ */

const selectedVersion = computed(() => versions.value.find(item => item.id === form.version));

function getSchemaFields(
  version: Api.Automation.WorkflowVersionRecord | null | undefined
): Api.Jobs.WorkflowInputField[] {
  const schema = version?.inputSchema;
  if (Array.isArray(schema)) return schema as Api.Jobs.WorkflowInputField[];
  if (schema && typeof schema === 'object' && Array.isArray((schema as { fields?: unknown }).fields)) {
    return (schema as { fields: Api.Jobs.WorkflowInputField[] }).fields;
  }
  return [];
}

const schemaFields = computed(() => getSchemaFields(selectedVersion.value));

watch(selectedVersion, version => {
  const next: Record<string, unknown> = {};
  getSchemaFields(version).forEach(field => {
    if (field.default !== undefined) next[field.name] = field.default;
  });
  inputVars.value = next;
});

/** select / multiselect 选项取值 */
type FieldOption = NonNullable<Api.Jobs.WorkflowInputField['options']>[number];

function optValue(opt: FieldOption) {
  return typeof opt === 'object' ? opt.value : opt;
}

function optLabel(opt: FieldOption) {
  return typeof opt === 'object' ? (opt.label ?? String(opt.value)) : String(opt);
}

/** ============ 目标主机（共享选择弹窗） ============ */

const selectedHosts = ref<Api.Cmdb.HostRecord[]>([]);
const hostModalVisible = ref(false);

function onHostsConfirm(hosts: Api.Cmdb.HostRecord[]) {
  selectedHosts.value = hosts;
}

function removeHost(id: number) {
  selectedHosts.value = selectedHosts.value.filter(host => host.id !== id);
}

function clearHosts() {
  selectedHosts.value = [];
}

/** ============ 高级设置（默认折叠，预填默认值） ============ */

const advancedOpen = ref<string[]>([]);

/** ============ 提交 ============ */

const submitting = ref(false);
const previewVisible = ref(false);
const preview = shallowRef<Api.Jobs.RunPreview | null>(null);
const pendingPayload = shallowRef<Api.Jobs.WorkflowRunPayload | null>(null);
let previewRequestId = 0;

function validateRequiredParams() {
  const missing = schemaFields.value.filter(
    field => field.required && (inputVars.value[field.name] === undefined || inputVars.value[field.name] === '')
  );
  if (missing.length) {
    window.$message?.warning(`请填写必填参数：${missing.map(field => field.label || field.name).join('、')}`);
    return false;
  }
  return true;
}

function buildPayload(): Api.Jobs.WorkflowRunPayload | null {
  if (!form.version) return null;
  const supportsBatch = ['serial', 'rolling', 'inherit'].includes(form.hostStrategy);
  return {
    workflowVersionId: form.version,
    hostIds: selectedHosts.value.map(host => host.id),
    workerPoolId: form.pool,
    gatewayId: form.gateway,
    inputVars: { ...inputVars.value },
    hostStrategy: form.hostStrategy === 'inherit' ? null : form.hostStrategy,
    forks: form.forks,
    timeoutSeconds: form.timeoutSeconds,
    ...(supportsBatch && form.serialBatch !== null ? { serialBatch: form.serialBatch } : {}),
    ...(form.maxFailPercentage !== null ? { maxFailPercentage: form.maxFailPercentage } : {})
  };
}

async function submit() {
  if (submitting.value) return;
  if (!form.version || !form.pool) {
    window.$message?.warning('请选择已发布版本和 Worker 池');
    return;
  }
  if (!validateRequiredParams()) return;
  submitting.value = true;
  const requestId = previewRequestId;
  try {
    if (!selectedHosts.value.length) {
      // 仅含 API / Jenkins / 通知步骤的流程可无主机；含命令/脚本类步骤则必须指定目标
      try {
        await window.$messageBox?.confirm(
          '未选择目标主机。若流程包含命令/脚本/Playbook/模块步骤，将无法执行。确认继续提交？',
          '目标资产确认',
          { type: 'warning', confirmButtonText: '继续', cancelButtonText: '取消' }
        );
      } catch {
        return;
      }
    }

    if (requestId !== previewRequestId || !props.visible) return;
    const payload = buildPayload();
    if (!payload) return;
    const { data, error } = await fetchPreviewWorkflowRun(payload);
    if (requestId !== previewRequestId || !props.visible || error || !data) return;
    pendingPayload.value = payload;
    preview.value = data;
    previewVisible.value = true;
  } finally {
    submitting.value = false;
  }
}

async function confirmRun() {
  if (submitting.value || !pendingPayload.value || !preview.value) return;
  submitting.value = true;
  try {
    const { data, error } = await fetchCreateWorkflowRun({
      ...pendingPayload.value,
      expectedTargetIds: preview.value.targets.map(target => target.hostId),
      expectedTargetFingerprint: preview.value.targetFingerprint,
      expectedConfirmationFingerprint: preview.value.confirmationFingerprint,
      executionRequestId: preview.value.executionRequestId
    });
    if (!error && data) {
      previewVisible.value = false;
      window.$notification?.success('任务已发起');
      emit('update:visible', false);
      emit('submitted', data.id);
      router.push({ name: 'task_run-detail', params: { id: data.id } });
    }
  } finally {
    submitting.value = false;
  }
}

function handleClose() {
  invalidatePreview();
  emit('update:visible', false);
}

function invalidatePreview() {
  previewRequestId += 1;
  previewVisible.value = false;
  preview.value = null;
  pendingPayload.value = null;
}

/** 打开弹窗：重置表单并加载选项 */
watch(
  () => props.visible,
  visible => {
    invalidatePreview();
    if (!visible) return;
    Object.assign(form, getInitForm());
    selectedHosts.value = [];
    inputVars.value = {};
    versions.value = [];
    advancedOpen.value = [];
    loadOptions();
  },
  { flush: 'sync' }
);
</script>

<template>
  <ElDialog
    :model-value="visible"
    :title="`执行${templateName ? `「${templateName}」` : ''}`"
    width="720px"
    :close-on-click-modal="false"
    append-to-body
    @update:model-value="handleClose"
  >
    <div v-loading="submitting" class="flex flex-col gap-16px">
      <!-- ① 已发布版本 -->
      <ElFormItem label="已发布版本" required label-width="110px">
        <ElSelect
          v-model="form.version"
          filterable
          class="w-full"
          placeholder="选择模板的已发布版本"
          :loading="submitting"
        >
          <ElOption
            v-for="version in versions"
            :key="version.id"
            :value="version.id"
            :label="`v${version.version}（发布于 ${version.publishedAt || '-'}）`"
          />
        </ElSelect>
      </ElFormItem>

      <!-- ② 任务单参数 -->
      <template v-if="schemaFields.length">
        <div class="text-14px font-600">任务单参数</div>
        <ElFormItem
          v-for="field in schemaFields"
          :key="field.name"
          :label="field.label || field.name"
          :required="field.required"
          label-width="110px"
        >
          <ElInput
            v-if="field.type === 'string' || field.type === 'host'"
            v-model="inputVars[field.name] as string"
            :placeholder="field.type === 'host' ? '主机名 / IP' : `请输入 ${field.label || field.name}`"
          />
          <ElInput
            v-else-if="field.type === 'text'"
            v-model="inputVars[field.name] as string"
            type="textarea"
            :rows="3"
          />
          <ElInput v-else-if="field.type === 'secret'" v-model="inputVars[field.name] as string" show-password />
          <ElInputNumber
            v-else-if="field.type === 'number' || field.type === 'integer'"
            v-model="inputVars[field.name] as number"
            class="w-full"
            :step="field.type === 'integer' ? 1 : 0.1"
          />
          <ElSwitch v-else-if="field.type === 'boolean'" v-model="inputVars[field.name] as boolean" />
          <ElSelect
            v-else-if="(field.type === 'select' || field.type === 'multiselect') && field.options?.length"
            v-model="inputVars[field.name] as string | number | Array<string | number>"
            class="w-full"
            :multiple="field.type === 'multiselect'"
            clearable
            placeholder="请选择"
          >
            <ElOption
              v-for="opt in field.options"
              :key="String(optValue(opt))"
              :label="optLabel(opt)"
              :value="optValue(opt)"
            />
          </ElSelect>
          <ElInput v-else v-model="inputVars[field.name] as string" placeholder="请输入" />
        </ElFormItem>
      </template>

      <!-- ③ 目标主机 -->
      <ElFormItem label="目标主机" label-width="110px">
        <div class="w-full">
          <div class="flex items-center gap-8px">
            <ElButton type="primary" plain @click="hostModalVisible = true">选择主机</ElButton>
            <ElTag v-if="selectedHosts.length" size="small" type="success">已选 {{ selectedHosts.length }} 台</ElTag>
            <ElButton v-if="selectedHosts.length" link size="small" @click="clearHosts">清空</ElButton>
          </div>
          <div v-if="selectedHosts.length" class="mt-8px max-h-120px flex flex-wrap gap-4px overflow-auto">
            <ElTag v-for="host in selectedHosts" :key="host.id" size="small" closable @close="removeHost(host.id)">
              {{ host.hostname }} · {{ host.internalIp }}
            </ElTag>
          </div>
          <div v-else class="mt-4px text-12px text-gray-500">仅含 API / Jenkins / 通知步骤的流程可不选主机</div>
        </div>
      </ElFormItem>

      <!-- ④ 高级设置（默认折叠） -->
      <ElCollapse v-model="advancedOpen">
        <ElCollapseItem name="advanced" title="高级设置">
          <ElForm label-width="170px" label-suffix="：" require-asterisk-position="left">
            <ElFormItem label="执行节点池" required>
              <ElSelect v-model="form.pool" class="w-full" placeholder="选择执行池">
                <ElOption v-for="pool in pools" :key="pool.id" :value="pool.id" :label="pool.name" />
              </ElSelect>
            </ElFormItem>
            <ElFormItem label="连接网关">
              <ElSelect v-model="form.gateway" class="w-full" clearable placeholder="不指定则全部直连">
                <ElOption
                  v-for="gateway in gateways"
                  :key="gateway.id"
                  :value="gateway.id"
                  :label="`${gateway.name}（${gateway.address}）`"
                />
              </ElSelect>
            </ElFormItem>
            <ExecutionSettingsFields
              v-model:host-strategy="form.hostStrategy"
              v-model:forks="form.forks"
              v-model:serial-batch="form.serialBatch"
              v-model:max-fail-percentage="form.maxFailPercentage"
              v-model:timeout-seconds="form.timeoutSeconds"
            />
          </ElForm>
        </ElCollapseItem>
      </ElCollapse>
    </div>

    <template #footer>
      <ElButton @click="handleClose">取消</ElButton>
      <ElButton type="primary" :loading="submitting" @click="submit">立即执行</ElButton>
    </template>

    <HostSelectModal v-model:visible="hostModalVisible" :selected-hosts="selectedHosts" @confirm="onHostsConfirm" />
    <RunPreviewDialog
      v-model:visible="previewVisible"
      :preview="preview"
      :loading="submitting"
      append-to-body
      @confirm="confirmRun"
    />
  </ElDialog>
</template>
