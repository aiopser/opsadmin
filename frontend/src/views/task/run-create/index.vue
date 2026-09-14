<script setup lang="ts">
import { computed, onMounted, reactive, ref, shallowRef, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import {
  fetchCreateWorkflowRun,
  fetchGetHostGroupList,
  fetchGetHostList,
  fetchGetTagList,
  fetchGetWorkerPools,
  fetchPublishedWorkflowVersions
} from '@/service/api';
import HostSelectModal from '@/components/business/host-select-modal/index.vue';

defineOptions({ name: 'TaskRunCreate' });

const route = useRoute();
const router = useRouter();

/** ============ 选项数据 ============ */

const versions = shallowRef<Api.Jobs.WorkflowVersionOption[]>([]);
const pools = shallowRef<Api.Jobs.WorkerPoolOption[]>([]);
const hostGroups = shallowRef<Api.Cmdb.HostGroupRecord[]>([]);
const hostTags = shallowRef<Api.Cmdb.HostTagRecord[]>([]);

/** ============ 表单 ============ */

type HostStrategy = 'parallel' | 'serial' | 'rolling';

const hostStrategyOptions = [
  { value: 'parallel', label: '并行', tip: '所有主机同时执行' },
  { value: 'serial', label: '串行', tip: '主机按批次逐台执行' },
  { value: 'rolling', label: '滚动', tip: '按批次滚动执行' }
] as const;

function getInitForm() {
  return {
    version: null as number | null,
    pool: null as number | null,
    hosts: [] as number[],
    groups: [] as number[],
    tags: [] as number[],
    hostStrategy: 'parallel' as HostStrategy,
    forks: 5,
    serialBatch: null as number | null,
    maxFailPercentage: null as number | null,
    timeoutSeconds: 3600
  };
}

const form = reactive(getInitForm());

/** 运行参数（按流程 inputSchema 动态渲染，整体替换以保持响应性） */
const inputVars = ref<Record<string, unknown>>({});
/** 「再次执行」预填：{来源版本 id, 参数值}，仅切到该版本时覆盖默认值 */
const prefillVars = ref<{ versionId: number; values: Record<string, unknown> } | null>(null);

/** ============ 主机选择（共享弹窗） ============ */

const selectedHosts = ref<Api.Cmdb.HostRecord[]>([]);
const hostModalVisible = ref(false);

function onHostsConfirm(hosts: Api.Cmdb.HostRecord[]) {
  selectedHosts.value = hosts;
  form.hosts = hosts.map(host => host.id);
}

function removeHost(id: number) {
  selectedHosts.value = selectedHosts.value.filter(host => host.id !== id);
  form.hosts = selectedHosts.value.map(host => host.id);
}

function clearHosts() {
  selectedHosts.value = [];
  form.hosts = [];
}

async function loadOptions() {
  const [versionResult, poolResult, groupResult, tagResult] = await Promise.all([
    fetchPublishedWorkflowVersions(),
    fetchGetWorkerPools(),
    fetchGetHostGroupList(),
    fetchGetTagList()
  ]);
  if (!versionResult.error) {
    versions.value = versionResult.data.list.filter(item => !item.workflowCode.startsWith('__quick_'));
  }
  if (!poolResult.error) {
    pools.value = poolResult.data.list.filter(
      item => item.isActive && (!item.executionKinds.length || item.executionKinds.includes('workflow'))
    );
    form.pool = pools.value.find(item => item.isDefault)?.id ?? pools.value[0]?.id ?? null;
  }
  if (!groupResult.error) {
    hostGroups.value = groupResult.data.records.filter(item => item.is_active);
  }
  if (!tagResult.error) {
    hostTags.value = tagResult.data.records;
  }
  applyQueryPrefill();
}

/** ============ 流程选择 ============ */

const selectedVersion = computed(() => versions.value.find(item => item.id === form.version));

function getSchemaFields(version?: Api.Jobs.WorkflowVersionOption) {
  const schema = version?.inputSchema;
  return Array.isArray(schema) ? schema : (schema?.fields ?? []);
}

const schemaFields = computed(() => getSchemaFields(selectedVersion.value));

watch(selectedVersion, version => {
  const next: Record<string, unknown> = {};
  getSchemaFields(version).forEach(field => {
    if (field.default !== undefined) next[field.name] = field.default;
  });
  // 再次执行：切到来源版本时预填值覆盖默认值
  if (version && prefillVars.value && prefillVars.value.versionId === version.id) {
    Object.assign(next, prefillVars.value.values);
  }
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

/** ============ query 预填（模板页执行入口 / 任务列表再次执行 / 资产页带主机） ============ */

function applyQueryPrefill() {
  const query = route.query;
  if (query.versionId) {
    const id = Number(query.versionId);
    if (versions.value.some(item => item.id === id)) {
      form.version = id;
    } else {
      window.$message?.warning('指定的流程版本不存在或未发布');
    }
  }
  if (query.inputVars) {
    try {
      const values = JSON.parse(String(query.inputVars));
      if (values && typeof values === 'object' && !Array.isArray(values)) {
        const versionId = query.versionId ? Number(query.versionId) : (form.version ?? 0);
        prefillVars.value = { versionId, values };
        // 同步应用到当前选中版本
        inputVars.value = { ...values };
      }
    } catch {
      // 无效预填参数，忽略
    }
  }
  if (query.hostIds) {
    const ids = String(query.hostIds)
      .split(',')
      .map(item => Number(item))
      .filter(item => Number.isInteger(item) && item > 0);
    if (ids.length) prefillHosts(ids);
  }
}

async function prefillHosts(ids: number[]) {
  const { data, error } = await fetchGetHostList({ current: 1, size: 200 });
  if (error || !data) return;
  const matched = data.records.filter(host => ids.includes(host.id));
  selectedHosts.value = matched;
  form.hosts = matched.map(host => host.id);
  if (matched.length < ids.length) {
    window.$message?.warning('部分预选主机已不存在，请重新确认目标资产');
  }
}

/** ============ 提交 ============ */

const submitting = ref(false);

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

async function submit() {
  if (!form.version || !form.pool) {
    window.$message?.warning('请选择已发布流程和 Worker 池');
    return;
  }
  if (!validateRequiredParams()) return;
  if (!form.hosts.length) {
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

  submitting.value = true;
  try {
    const payload: Api.Jobs.WorkflowRunPayload = {
      workflowVersionId: form.version,
      hostIds: form.hosts,
      groupIds: form.groups,
      tagIds: form.tags,
      workerPoolId: form.pool,
      inputVars: { ...inputVars.value },
      hostStrategy: form.hostStrategy,
      forks: form.forks,
      timeoutSeconds: form.timeoutSeconds
    };
    if (form.hostStrategy === 'serial' && form.serialBatch) {
      payload.serialBatch = form.serialBatch;
    }
    if (form.maxFailPercentage !== null) {
      payload.maxFailPercentage = form.maxFailPercentage;
    }
    const { data, error } = await fetchCreateWorkflowRun(payload);
    if (!error && data) {
      window.$message?.success('任务已发起');
      router.push(`/task/run-detail/${data.id}`);
    }
  } finally {
    submitting.value = false;
  }
}

onMounted(loadOptions);
</script>

<template>
  <div class="min-h-500px flex-col-stretch gap-16px overflow-hidden lt-sm:overflow-auto">
    <ElCard class="card-wrapper sm:flex-1-hidden">
      <template #header>
        <div class="flex items-center justify-between">
          <p>创建任务</p>
          <ElButton text type="primary" @click="loadOptions">刷新选项</ElButton>
        </div>
      </template>

      <ElForm :model="form" label-width="120px">
        <ElRow :gutter="16">
          <!-- ① 流程选择 -->
          <ElCol :xl="12" :lg="24" :md="24" :sm="24" :xs="24">
            <ElCard shadow="never" header="流程选择" class="mb-16px">
              <ElFormItem label="已发布流程" required>
                <ElSelect v-model="form.version" filterable clearable class="w-full" placeholder="选择已发布的流程版本">
                  <ElOption
                    v-for="version in versions"
                    :key="version.id"
                    :value="version.id"
                    :label="`${version.workflowName} · v${version.version}`"
                  />
                </ElSelect>
              </ElFormItem>
              <div v-if="selectedVersion" class="w-full text-12px text-gray-400">
                编码：{{ selectedVersion.workflowCode }} · 发布后固定引用资源版本，运行时使用快照
              </div>
            </ElCard>
          </ElCol>

          <!-- ② 运行参数 -->
          <ElCol :xl="12" :lg="24" :md="24" :sm="24" :xs="24">
            <ElCard shadow="never" header="运行参数" class="mb-16px">
              <template v-if="schemaFields.length">
                <ElFormItem
                  v-for="field in schemaFields"
                  :key="field.name"
                  :label="field.label || field.name"
                  :required="field.required"
                >
                  <ElInput
                    v-if="field.type === 'string' || field.type === 'host'"
                    v-model="inputVars[field.name] as string"
                    :placeholder="
                      field.type === 'host' ? '主机名 / IP，或从目标资产选择' : `请输入 ${field.label || field.name}`
                    "
                  />
                  <ElInput
                    v-else-if="field.type === 'text'"
                    v-model="inputVars[field.name] as string"
                    type="textarea"
                    :rows="3"
                  />
                  <ElInput
                    v-else-if="field.type === 'secret'"
                    v-model="inputVars[field.name] as string"
                    show-password
                  />
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
                  <ElInput
                    v-else
                    v-model="inputVars[field.name] as string"
                    placeholder="请输入，多个值用英文逗号分隔"
                  />
                </ElFormItem>
              </template>
              <ElEmpty v-else description="该流程未定义输入参数" :image-size="60" />
            </ElCard>
          </ElCol>

          <!-- ③ 目标资产 -->
          <ElCol :xl="12" :lg="24" :md="24" :sm="24" :xs="24">
            <ElCard shadow="never" header="目标资产" class="mb-16px">
              <ElFormItem label="目标主机">
                <div class="w-full">
                  <div class="flex items-center gap-8px">
                    <ElButton type="primary" plain @click="hostModalVisible = true">选择主机</ElButton>
                    <ElTag v-if="selectedHosts.length" size="small" type="success">
                      已选 {{ selectedHosts.length }} 台
                    </ElTag>
                    <ElButton v-if="selectedHosts.length" link size="small" @click="clearHosts">清空</ElButton>
                  </div>
                  <div v-if="selectedHosts.length" class="mt-8px max-h-160px flex flex-wrap gap-4px overflow-auto">
                    <ElTag
                      v-for="host in selectedHosts"
                      :key="host.id"
                      size="small"
                      closable
                      @close="removeHost(host.id)"
                    >
                      {{ host.hostname }} · {{ host.primaryIp }}
                    </ElTag>
                  </div>
                  <div v-else class="mt-8px text-12px text-gray-400">
                    命令/脚本/Playbook/模块步骤在所选主机上执行；API、Jenkins、通知步骤使用自身资源配置，不需要主机
                  </div>
                </div>
              </ElFormItem>
              <ElFormItem label="主机组">
                <ElSelect
                  v-model="form.groups"
                  multiple
                  filterable
                  clearable
                  collapse-tags
                  collapse-tags-tooltip
                  class="w-full"
                  placeholder="选择主机组，展开为组内全部主机"
                >
                  <ElOption v-for="group in hostGroups" :key="group.id" :value="group.id" :label="group.name" />
                </ElSelect>
              </ElFormItem>
              <ElFormItem label="标签">
                <ElSelect
                  v-model="form.tags"
                  multiple
                  filterable
                  clearable
                  collapse-tags
                  collapse-tags-tooltip
                  class="w-full"
                  placeholder="选择标签，展开为绑定该标签的全部主机"
                >
                  <ElOption v-for="tag in hostTags" :key="tag.id" :value="tag.id" :label="tag.label" />
                </ElSelect>
              </ElFormItem>
              <div class="text-12px text-gray-400">主机、主机组、标签三类目标会合并去重后作为最终执行范围</div>
            </ElCard>
          </ElCol>

          <!-- ④ 执行设置 -->
          <ElCol :xl="12" :lg="24" :md="24" :sm="24" :xs="24">
            <ElCard shadow="never" header="执行设置" class="mb-16px">
              <ElFormItem label="Worker 池" required>
                <ElSelect v-model="form.pool" class="w-full" placeholder="选择执行池">
                  <ElOption v-for="pool in pools" :key="pool.id" :value="pool.id" :label="pool.name" />
                </ElSelect>
              </ElFormItem>
              <ElFormItem label="执行策略">
                <ElRadioGroup v-model="form.hostStrategy">
                  <ElTooltip v-for="item in hostStrategyOptions" :key="item.value" :content="item.tip" placement="top">
                    <ElRadio :value="item.value">{{ item.label }}</ElRadio>
                  </ElTooltip>
                </ElRadioGroup>
              </ElFormItem>
              <ElFormItem v-if="form.hostStrategy === 'serial'" label="每批主机数">
                <ElInputNumber v-model="form.serialBatch" :min="1" placeholder="默认 1 台/批" />
              </ElFormItem>
              <ElFormItem label="并发数（forks）">
                <ElInputNumber v-model="form.forks" :min="1" :max="100" :disabled="form.hostStrategy === 'serial'" />
                <span v-if="form.hostStrategy === 'serial'" class="ml-8px text-12px text-gray-400">
                  串行策略强制逐台执行
                </span>
              </ElFormItem>
              <ElFormItem label="超时秒数">
                <ElInputNumber v-model="form.timeoutSeconds" :min="1" :max="86400" :step="60" />
              </ElFormItem>
              <ElFormItem label="最大失败比例">
                <ElInputNumber v-model="form.maxFailPercentage" :min="0" :max="100" placeholder="不限制" />
                <span class="ml-8px text-12px text-gray-400">失败主机占比超过该值时终止剩余执行</span>
              </ElFormItem>

              <ElFormItem>
                <ElButton type="primary" :loading="submitting" @click="submit">提交任务</ElButton>
              </ElFormItem>
            </ElCard>
          </ElCol>
        </ElRow>
      </ElForm>
    </ElCard>

    <HostSelectModal v-model:visible="hostModalVisible" :selected-hosts="selectedHosts" @confirm="onHostsConfirm" />
  </div>
</template>
