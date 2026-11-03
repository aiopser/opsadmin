<script setup lang="ts">
import { computed, reactive, ref, shallowRef, watch } from 'vue';
import {
  fetchAddTaskTicket,
  fetchGetGatewayList,
  fetchGetHostList,
  fetchGetNotificationTemplate,
  fetchGetNotificationTemplateList,
  fetchGetWorkerPools,
  fetchPublishedWorkflowVersions,
  fetchUpdateTaskTicket
} from '@/service/api';
import { buildDefaultVars, getSchemaFields, missingRequiredFields, optLabel, optValue } from '@/views/task/schema-form';
import ExecutionSettingsFields from '@/components/business/execution-settings-fields/index.vue';
import HostSelectModal from '@/components/business/host-select-modal/index.vue';
import TargetSelectorFields from '@/components/business/target-selector-fields/index.vue';

defineOptions({ name: 'TicketCreateDrawer' });

interface Props {
  visible: boolean;
  /** 编辑目标；null 表示新增 */
  editTicket?: Api.Jobs.TaskTicketRecord | null;
}

const props = withDefaults(defineProps<Props>(), {
  editTicket: null
});

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void;
  (e: 'saved', ticket: Api.Jobs.TaskTicketRecord): void;
}>();

/** ============ 选项数据 ============ */

const versions = shallowRef<Api.Jobs.WorkflowVersionOption[]>([]);
const pools = shallowRef<Api.Jobs.WorkerPoolOption[]>([]);
const gateways = shallowRef<Api.Jobs.GatewayRecord[]>([]);
const alertTemplates = shallowRef<Api.Automation.NotificationTemplateRecord[]>([]);

/** ============ 表单 ============ */

type HostStrategy = 'inherit' | 'parallel' | 'serial' | 'rolling';

function getInitForm() {
  return {
    groupIds: [] as number[],
    tagIds: [] as number[],
    name: '',
    remark: '',
    alertMode: 'inherit' as 'inherit' | 'off' | 'custom',
    alertTemplateId: null as number | null,
    alertReceivers: '',
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

let alertSearchSequence = 0;

async function loadAlertTemplates(search = '', selectedId = form.alertTemplateId ?? undefined) {
  alertSearchSequence += 1;
  const sequence = alertSearchSequence;
  const [listResult, selectedResult] = await Promise.all([
    fetchGetNotificationTemplateList({ current: 1, size: 20, search: search.trim() || null }),
    selectedId ? fetchGetNotificationTemplate(selectedId) : Promise.resolve(null)
  ]);
  if (sequence !== alertSearchSequence || listResult.error || !listResult.data) return;
  const selected = selectedResult && !selectedResult.error ? selectedResult.data : null;
  const options = listResult.data.records.filter(item => item.isActive);
  alertTemplates.value = selected && !options.some(item => item.id === selected.id) ? [selected, ...options] : options;
}

const formRef = ref();

const formRules = {
  name: [{ required: true, message: '请输入任务名称', trigger: 'blur' }],
  version: [{ required: true, message: '请选择流程版本', trigger: 'change' }]
};

/** 运行参数（按流程 inputSchema 动态渲染，整体替换以保持响应性） */
const inputVars = ref<Record<string, unknown>>({});

/** ============ 流程版本与动态参数 ============ */

const selectedVersion = computed(() => versions.value.find(item => item.id === form.version));

const schemaFields = computed(() => getSchemaFields(selectedVersion.value));

/** 回填期间跳过「版本切换 → 重置参数」，避免覆盖任务单已存参数 */
let restoring = false;

watch(selectedVersion, version => {
  if (restoring) return;
  inputVars.value = buildDefaultVars(getSchemaFields(version));
});

/** ============ 目标主机（共享选择弹窗） ============ */

const selectedHosts = shallowRef<Api.Cmdb.HostRecord[]>([]);
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

/** 桩记录：查询失败时的兜底渲染（仅展示用，提交只依赖 id） */
function stubHostsByIds(ids: number[]): Api.Cmdb.HostRecord[] {
  return ids.map(id => ({ id, hostname: `主机 #${id}`, internalIp: '' }) as unknown as Api.Cmdb.HostRecord);
}

/** 编辑回填时仅有 hostIds：按 id 拉取真实主机信息渲染 chips；查询失败或主机缺失时回退桩记录 */
async function fillSelectedHosts(ids: number[]) {
  if (!ids.length) {
    selectedHosts.value = [];
    return;
  }
  const { data, error } = await fetchGetHostList({ current: 1, size: ids.length, ids: ids.join(',') });
  if (!error && data && data.records.length === ids.length) {
    selectedHosts.value = data.records;
  } else {
    selectedHosts.value = stubHostsByIds(ids);
  }
}

/** ============ 高级设置（默认折叠） ============ */

const advancedOpen = ref<string[]>([]);

/** ============ 加载与回填 ============ */

function defaultPoolId() {
  return pools.value.find(item => item.isDefault)?.id ?? pools.value[0]?.id ?? null;
}

function ticketAlertMode(alert: Api.Jobs.TaskTicketRecord['failureAlert']): 'inherit' | 'off' | 'custom' {
  if (alert === null) return 'inherit';
  return alert.templateId ? 'custom' : 'off';
}

function ticketFailureAlert(): Api.Jobs.TaskTicketPayload['failureAlert'] {
  if (form.alertMode === 'inherit') return null;
  if (form.alertMode === 'off') return {};
  return { templateId: form.alertTemplateId!, receivers: form.alertReceivers.trim() };
}

async function restoreTicket(ticket: Api.Jobs.TaskTicketRecord) {
  form.groupIds = [...ticket.groupIds];
  form.tagIds = [...ticket.tagIds];
  form.name = ticket.name;
  form.remark = ticket.remark ?? '';
  form.alertMode = ticketAlertMode(ticket.failureAlert);
  form.alertTemplateId = ticket.failureAlert?.templateId ?? null;
  form.alertReceivers = ticket.failureAlert?.receivers ?? '';
  form.version = ticket.workflowVersionId;
  form.hostStrategy = ticket.hostStrategy ?? 'inherit';
  form.forks = ticket.forks;
  form.serialBatch = ticket.serialBatch;
  form.maxFailPercentage = ticket.maxFailPercentage;
  form.timeoutSeconds = ticket.timeoutSeconds;
  form.pool = ticket.workerPoolId ?? defaultPoolId();
  form.gateway = ticket.gatewayId;
  inputVars.value = { ...(ticket.inputVars ?? {}) };
  await fillSelectedHosts(ticket.hostIds ?? []);
}

async function loadOptions(ticket: Api.Jobs.TaskTicketRecord | null) {
  restoring = true;
  const [versionResult, poolResult, gatewayResult] = await Promise.all([
    fetchPublishedWorkflowVersions(),
    fetchGetWorkerPools(),
    fetchGetGatewayList({ current: 1, size: 100 })
  ]);
  await loadAlertTemplates('', ticket?.failureAlert?.templateId);
  if (!versionResult.error) {
    versions.value = versionResult.data.list;
  }
  if (!poolResult.error) {
    pools.value = poolResult.data.list.filter(
      item => item.isActive && (!item.executionKinds.length || item.executionKinds.includes('workflow'))
    );
  }
  if (!gatewayResult.error && gatewayResult.data) {
    gateways.value = gatewayResult.data.records;
  }

  if (ticket) {
    await restoreTicket(ticket);
  } else {
    form.version = versions.value[0]?.id ?? null;
    form.pool = defaultPoolId();
    form.gateway = null;
    inputVars.value = {};
    selectedHosts.value = [];
  }
  advancedOpen.value = [];
  restoring = false;
}

/** ============ 提交 ============ */

const submitting = ref(false);

function validateRequiredParams() {
  const missing = missingRequiredFields(schemaFields.value, inputVars.value);
  if (missing.length) {
    window.$message?.warning(`请填写必填参数：${missing.map(field => field.label || field.name).join('、')}`);
    return false;
  }
  return true;
}

async function submit() {
  await formRef.value?.validate();

  if (!validateRequiredParams()) return;
  if (form.alertMode === 'custom' && !form.alertTemplateId) {
    window.$message?.warning('请选择失败告警模板');
    return;
  }

  submitting.value = true;
  try {
    const payload: Api.Jobs.TaskTicketPayload = {
      name: form.name.trim(),
      remark: form.remark.trim(),
      failureAlert: ticketFailureAlert(),
      workflowVersionId: form.version!,
      hostIds: selectedHosts.value.map(host => host.id),
      groupIds: form.groupIds,
      tagIds: form.tagIds,
      workerPoolId: form.pool,
      gatewayId: form.gateway,
      inputVars: { ...inputVars.value },
      hostStrategy: form.hostStrategy === 'inherit' ? null : form.hostStrategy,
      serialBatch: form.serialBatch ?? null,
      maxFailPercentage: form.maxFailPercentage ?? null,
      forks: form.forks ?? null,
      timeoutSeconds: form.timeoutSeconds ?? null
    };
    if ((form.hostStrategy === 'serial' || form.hostStrategy === 'rolling') && form.serialBatch) {
      payload.serialBatch = form.serialBatch;
    }
    if (form.maxFailPercentage !== null) {
      payload.maxFailPercentage = form.maxFailPercentage;
    }

    const result = props.editTicket
      ? await fetchUpdateTaskTicket(props.editTicket.id, payload)
      : await fetchAddTaskTicket(payload);
    const { data, error } = result;
    if (!error && data) {
      window.$notification?.success(props.editTicket ? '任务已更新' : '任务已创建，可在列表中运行');
      emit('saved', data);
      handleClose();
    }
  } finally {
    submitting.value = false;
  }
}

function handleClose() {
  emit('update:visible', false);
}

/** 打开抽屉：重置表单、加载选项并按需回填 */
watch(
  () => props.visible,
  visible => {
    if (!visible) return;
    Object.assign(form, getInitForm());
    selectedHosts.value = [];
    versions.value = [];
    loadOptions(props.editTicket);
  }
);
</script>

<template>
  <ElDrawer
    :model-value="visible"
    :title="editTicket ? '编辑任务单' : '新增任务单'"
    size="640px"
    :close-on-click-modal="false"
    @update:model-value="handleClose"
  >
    <div v-loading="submitting" class="flex flex-col gap-16px">
      <!-- 基本信息（卡片风格与编排页一致） -->
      <ElCard class="card-wrapper" shadow="never">
        <template #header>
          <span>基本信息</span>
        </template>
        <ElForm
          ref="formRef"
          class="responsive-form"
          :model="form"
          :rules="formRules"
          label-width="110px"
          label-suffix="："
          require-asterisk-position="left"
        >
          <ElFormItem label="任务名称" prop="name">
            <ElInput v-model="form.name" placeholder="请输入任务名称" maxlength="128" />
          </ElFormItem>
          <ElFormItem prop="version">
            <template #label>
              <FormLabelHelp
                label="流程版本"
                :help="['只能选择已发布版本；任务单固定引用该版本，模板发布新版本后不会自动切换。']"
              />
            </template>
            <ElSelect v-model="form.version" filterable class="w-full" placeholder="选择已发布的流程版本">
              <ElOption
                v-for="version in versions"
                :key="version.id"
                :value="version.id"
                :label="`${version.workflowName} · v${version.version}`"
              />
            </ElSelect>
          </ElFormItem>
          <ElFormItem label="备注">
            <ElInput v-model="form.remark" type="textarea" :rows="2" placeholder="选填" maxlength="255" />
          </ElFormItem>
        </ElForm>
      </ElCard>

      <ElCard class="card-wrapper" shadow="never">
        <template #header><span>失败告警</span></template>
        <ElForm class="responsive-form" label-width="110px" label-suffix="：" require-asterisk-position="left">
          <ElFormItem label="告警规则">
            <ElRadioGroup v-model="form.alertMode">
              <ElRadio value="inherit">继承流程</ElRadio>
              <ElRadio value="off">不发送</ElRadio>
              <ElRadio value="custom">任务单指定</ElRadio>
            </ElRadioGroup>
          </ElFormItem>
          <ElFormItem v-if="form.alertMode === 'custom'" label="通知模板" required>
            <ElSelect
              v-model="form.alertTemplateId"
              filterable
              remote
              :remote-method="loadAlertTemplates"
              class="w-full"
              placeholder="搜索失败通知模板"
            >
              <ElOption
                v-for="item in alertTemplates"
                :key="item.id"
                :label="item.isActive ? item.name : `${item.name}（已停用）`"
                :value="item.id"
                :disabled="!item.isActive"
              />
            </ElSelect>
          </ElFormItem>
          <ElFormItem v-if="form.alertMode === 'custom'" label="接收人">
            <ElInput
              v-model="form.alertReceivers"
              maxlength="1024"
              placeholder="可选；逗号分隔，留空使用通知模板配置"
            />
          </ElFormItem>
          <div class="ml-110px text-12px text-gray-500">
            运行失败或超时后发送；通知结果单独记录，不会改变步骤执行结果。
          </div>
        </ElForm>
      </ElCard>

      <!-- 任务单参数 -->
      <ElCard v-if="schemaFields.length" class="card-wrapper" shadow="never">
        <template #header>
          <span>任务单参数 extra_vars</span>
        </template>
        <ElForm class="responsive-form" label-width="110px" label-suffix="：" require-asterisk-position="left">
          <ElFormItem
            v-for="field in schemaFields"
            :key="field.name"
            :label="field.label || field.name"
            :required="field.required"
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
        </ElForm>
      </ElCard>

      <!-- 执行配置（目标主机 + 高级设置） -->
      <ElCard class="card-wrapper" shadow="never">
        <template #header>
          <span>执行配置</span>
        </template>
        <ElForm class="responsive-form" label-width="110px" label-suffix="：" require-asterisk-position="left">
          <ElFormItem label="目标主机">
            <div class="w-full">
              <div class="flex items-center gap-8px">
                <ElButton type="primary" plain @click="hostModalVisible = true">选择主机</ElButton>
                <ElTag v-if="selectedHosts.length" size="small" type="success">
                  已选 {{ selectedHosts.length }} 台
                </ElTag>
                <ElButton v-if="selectedHosts.length" link size="small" @click="clearHosts">清空</ElButton>
              </div>
              <div v-if="selectedHosts.length" class="mt-8px max-h-120px flex flex-wrap gap-4px overflow-auto">
                <ElTag v-for="host in selectedHosts" :key="host.id" size="small" closable @close="removeHost(host.id)">
                  {{ host.internalIp ? `${host.hostname} · ${host.internalIp}` : host.hostname }}
                </ElTag>
              </div>
              <div v-else class="mt-4px text-12px text-gray-500">仅含 API / Jenkins / 通知步骤的流程可不选主机</div>
            </div>
          </ElFormItem>
          <TargetSelectorFields v-model:group-ids="form.groupIds" v-model:tag-ids="form.tagIds" />
        </ElForm>

        <ElCollapse v-model="advancedOpen" class="advanced-collapse mt-12px">
          <ElCollapseItem name="advanced" title="高级设置">
            <ElForm class="responsive-form" label-width="180px" label-suffix="：" require-asterisk-position="left">
              <ElFormItem>
                <template #label>
                  <FormLabelHelp
                    label="执行节点池"
                    :help="['运行被投递到该池对应队列执行；池可限制并发数量与支持的执行类型。']"
                  />
                </template>
                <ElSelect v-model="form.pool" class="w-full" placeholder="选择执行池">
                  <ElOption v-for="pool in pools" :key="pool.id" :value="pool.id" :label="pool.name" />
                </ElSelect>
              </ElFormItem>
              <ElFormItem>
                <template #label>
                  <FormLabelHelp
                    label="连接网关"
                    :help="['指定后所有 SSH 主机统一经该网关代理；仅影响命令 / 脚本 / Playbook / 模块步骤。']"
                  />
                </template>
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
      </ElCard>
    </div>

    <template #footer>
      <ElButton @click="handleClose">取消</ElButton>
      <ElButton type="primary" :loading="submitting" @click="submit">
        {{ editTicket ? '保存' : '创建任务单' }}
      </ElButton>
    </template>

    <HostSelectModal v-model:visible="hostModalVisible" :selected-hosts="selectedHosts" @confirm="onHostsConfirm" />
  </ElDrawer>
</template>
