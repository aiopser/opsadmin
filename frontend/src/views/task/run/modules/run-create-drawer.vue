<script setup lang="ts">
import { computed, reactive, ref, shallowRef, watch } from 'vue';
import {
  fetchCreateWorkflowRun,
  fetchGetHostOptions,
  fetchGetWorkerPools,
  fetchPreviewWorkflowRun,
  fetchPublishedWorkflowVersions
} from '@/service/api';
import RunPreviewDialog from '@/components/business/run-preview-dialog/index.vue';
import TargetSelectorFields from '@/components/business/target-selector-fields/index.vue';

defineOptions({ name: 'WorkflowRunCreateDrawer' });
const visible = defineModel<boolean>('visible', { required: true });
const emit = defineEmits<{ created: [run: Api.Jobs.RunRecord] }>();
const versions = shallowRef<Api.Jobs.WorkflowVersionOption[]>([]);
const hosts = shallowRef<Api.Jobs.HostOption[]>([]);
const pools = shallowRef<Api.Jobs.WorkerPoolOption[]>([]);
const saving = ref(false);
const previewVisible = ref(false);
const preview = shallowRef<Api.Jobs.RunPreview | null>(null);
const pendingPayload = shallowRef<Api.Jobs.WorkflowRunPayload | null>(null);
let previewRequestId = 0;
const form = reactive({
  version: null as number | null,
  hosts: [] as number[],
  groups: [] as number[],
  tags: [] as number[],
  pool: null as number | null
});
const formRef = ref();

/** 目标资产为多选数组，required 基础规则无法校验空数组，用自定义 validator */
function validateHosts(_rule: unknown, _value: number[], callback: (error?: Error) => void) {
  if (!form.hosts.length && !form.groups.length && !form.tags.length) return callback(new Error('请选择目标资产'));
  return callback();
}

const formRules = {
  version: [{ required: true, message: '请选择流程版本', trigger: 'change' }],
  hosts: [{ validator: validateHosts, trigger: 'change' }],
  pool: [{ required: true, message: '请选择执行池', trigger: 'change' }]
};

const values = ref<Record<string, string | number | boolean>>({});
const selected = computed(() => versions.value.find(item => item.id === form.version));
const fields = computed(() => {
  const schema = selected.value?.inputSchema;
  return Array.isArray(schema) ? schema : (schema?.fields ?? []);
});

function numberValue(name: string): number | undefined {
  const value = values.value[name];
  return typeof value === 'number' ? value : undefined;
}
function textValue(name: string): string {
  const value = values.value[name];
  return typeof value === 'string' ? value : '';
}
function setNumber(name: string, value: number | undefined) {
  if (value === undefined)
    values.value = Object.fromEntries(Object.entries(values.value).filter(([key]) => key !== name));
  else values.value[name] = value;
}
function setText(name: string, value: string) {
  values.value[name] = value;
}

async function searchHosts(keyword = '') {
  const { data, error } = await fetchGetHostOptions(keyword);
  if (!error) hosts.value = data.list;
}

async function load() {
  const [versionResult, poolResult] = await Promise.all([
    fetchPublishedWorkflowVersions(),
    fetchGetWorkerPools(),
    searchHosts()
  ]);
  if (!versionResult.error)
    versions.value = versionResult.data.list.filter(item => !item.workflowCode.startsWith('__quick_'));
  if (!poolResult.error) {
    pools.value = poolResult.data.list.filter(
      item => item.isActive && (!item.executionKinds.length || item.executionKinds.includes('workflow'))
    );
    form.pool = pools.value.find(item => item.isDefault)?.id ?? pools.value[0]?.id ?? null;
  }
}

async function submit() {
  if (saving.value) return;
  saving.value = true;
  const requestId = previewRequestId;
  try {
    await formRef.value?.validate();
    if (requestId !== previewRequestId || !visible.value || !form.version) return;
    const missing = fields.value.find(
      field => field.required && (values.value[field.name] === undefined || values.value[field.name] === '')
    );
    if (missing) {
      window.$message?.warning(`请填写${missing.label || missing.name}`);
      return;
    }
    const inputVars = Object.fromEntries(fields.value.map(field => [field.name, values.value[field.name]]));
    const payload: Api.Jobs.WorkflowRunPayload = {
      workflowVersionId: form.version,
      workerPoolId: form.pool,
      hostIds: [...form.hosts],
      groupIds: [...form.groups],
      tagIds: [...form.tags],
      inputVars
    };
    const { data, error } = await fetchPreviewWorkflowRun(payload);
    if (requestId !== previewRequestId || !visible.value || error || !data) return;
    pendingPayload.value = payload;
    preview.value = data;
    previewVisible.value = true;
  } finally {
    saving.value = false;
  }
}

async function confirmRun() {
  if (saving.value || !pendingPayload.value || !preview.value) return;
  saving.value = true;
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
      visible.value = false;
      emit('created', data);
    }
  } finally {
    saving.value = false;
  }
}

function invalidatePreview() {
  previewRequestId += 1;
  previewVisible.value = false;
  preview.value = null;
  pendingPayload.value = null;
}

watch(selected, () => {
  values.value = {};
  fields.value.forEach(field => {
    // multiselect 的数组默认值在此抽屉无对应控件，跳过
    if (field.default !== undefined && typeof field.default !== 'object') {
      values.value[field.name] = field.default;
    }
  });
});
watch(
  visible,
  open => {
    invalidatePreview();
    if (open) load();
  },
  { flush: 'sync' }
);
</script>

<template>
  <ElDrawer v-model="visible" title="发起执行" size="520px">
    <ElForm
      ref="formRef"
      :model="form"
      :rules="formRules"
      :disabled="saving"
      label-position="top"
      label-suffix="："
      require-asterisk-position="left"
    >
      <ElFormItem prop="version">
        <template #label>
          <FormLabelHelp label="已发布流程" :help="['只能选择已发布版本；运行创建后固定引用该版本的流程快照。']" />
        </template>
        <ElSelect v-model="form.version" filterable class="w-full" placeholder="选择流程版本">
          <ElOption
            v-for="version in versions"
            :key="version.id"
            :value="version.id"
            :label="`${version.workflowName} · v${version.version}`"
          />
        </ElSelect>
      </ElFormItem>
      <ElFormItem label="目标资产" prop="hosts">
        <ElSelect v-model="form.hosts" multiple filterable remote :remote-method="searchHosts" class="w-full">
          <ElOption
            v-for="host in hosts"
            :key="host.id"
            :value="host.id"
            :label="`${host.hostname} · ${host.internalIp}`"
          />
        </ElSelect>
      </ElFormItem>
      <TargetSelectorFields v-model:group-ids="form.groups" v-model:tag-ids="form.tags" />
      <ElFormItem prop="pool">
        <template #label>
          <FormLabelHelp label="执行池" :help="['运行被投递到该池对应队列执行；池可限制并发数量与支持的执行类型。']" />
        </template>
        <ElSelect v-model="form.pool" class="w-full">
          <ElOption v-for="pool in pools" :key="pool.id" :value="pool.id" :label="pool.name" />
        </ElSelect>
      </ElFormItem>
      <ElFormItem
        v-for="field in fields"
        :key="field.name"
        :label="field.label || field.name"
        :required="field.required"
      >
        <ElSwitch v-if="field.type === 'boolean'" v-model="values[field.name]" />
        <ElInputNumber
          v-else-if="field.type === 'number' || field.type === 'integer'"
          :model-value="numberValue(field.name)"
          @update:model-value="setNumber(field.name, $event)"
        />
        <ElInput
          v-else
          :model-value="textValue(field.name)"
          :show-password="field.type === 'secret'"
          autocomplete="off"
          @update:model-value="setText(field.name, $event)"
        />
      </ElFormItem>
    </ElForm>
    <template #footer><ElButton type="primary" :loading="saving" @click="submit">发起执行</ElButton></template>
    <RunPreviewDialog
      v-model:visible="previewVisible"
      :preview="preview"
      :loading="saving"
      append-to-body
      @confirm="confirmRun"
    />
  </ElDrawer>
</template>
