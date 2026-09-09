<script setup lang="ts">
import { computed, reactive, ref, shallowRef, watch } from 'vue';
import {
  fetchCreateWorkflowRun,
  fetchGetHostOptions,
  fetchGetWorkerPools,
  fetchPublishedWorkflowVersions
} from '@/service/api';

defineOptions({ name: 'WorkflowRunCreateDrawer' });
const visible = defineModel<boolean>('visible', { required: true });
const emit = defineEmits<{ created: [run: Api.Jobs.RunRecord] }>();
const versions = shallowRef<Api.Jobs.WorkflowVersionOption[]>([]);
const hosts = shallowRef<Api.Jobs.HostOption[]>([]);
const pools = shallowRef<Api.Jobs.WorkerPoolOption[]>([]);
const saving = ref(false);
const form = reactive({ version: null as number | null, hosts: [] as number[], pool: null as number | null });
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
  if (!form.version || !form.pool || !form.hosts.length) {
    window.$message?.warning('请选择已发布流程、执行池和目标资产');
    return;
  }
  const missing = fields.value.find(
    field => field.required && (values.value[field.name] === undefined || values.value[field.name] === '')
  );
  if (missing) {
    window.$message?.warning(`请填写${missing.label || missing.name}`);
    return;
  }
  saving.value = true;
  try {
    const inputVars = Object.fromEntries(fields.value.map(field => [field.name, values.value[field.name]]));
    const { data, error } = await fetchCreateWorkflowRun({
      workflowVersionId: form.version,
      workerPoolId: form.pool,
      hostIds: form.hosts,
      inputVars
    });
    if (!error) {
      visible.value = false;
      emit('created', data);
    }
  } finally {
    saving.value = false;
  }
}

watch(selected, () => {
  values.value = {};
  fields.value.forEach(field => {
    if (field.default !== undefined) values.value[field.name] = field.default;
  });
});
watch(visible, open => {
  if (open) load();
});
</script>

<template>
  <ElDrawer v-model="visible" title="发起任务" size="520px">
    <ElForm label-position="top">
      <ElFormItem label="已发布流程" required>
        <ElSelect v-model="form.version" filterable class="w-full" placeholder="选择流程版本">
          <ElOption
            v-for="version in versions"
            :key="version.id"
            :value="version.id"
            :label="`${version.workflowName} · v${version.version}`"
          />
        </ElSelect>
      </ElFormItem>
      <ElFormItem label="目标资产" required>
        <ElSelect v-model="form.hosts" multiple filterable remote :remote-method="searchHosts" class="w-full">
          <ElOption
            v-for="host in hosts"
            :key="host.id"
            :value="host.id"
            :label="`${host.hostname} · ${host.primaryIp}`"
          />
        </ElSelect>
      </ElFormItem>
      <ElFormItem label="执行池" required>
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
    <template #footer><ElButton type="primary" :loading="saving" @click="submit">发起任务</ElButton></template>
  </ElDrawer>
</template>
