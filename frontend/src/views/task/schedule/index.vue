<script setup lang="tsx">
import { computed, onMounted, reactive, ref, shallowRef } from 'vue';
import { useRouter } from 'vue-router';
import {
  fetchAddScheduledJob,
  fetchDeleteScheduledJob,
  fetchGetGatewayList,
  fetchGetHostOptions,
  fetchGetScheduledJobList,
  fetchGetWorkerPools,
  fetchPreviewScheduledJob,
  fetchPreviewWorkflowRun,
  fetchPublishedWorkflowVersions,
  fetchRunScheduledJobNow,
  fetchUpdateScheduledJob
} from '@/service/api';
import { defaultTransform, useUIPaginatedTable } from '@/hooks/common/table';
import { useAuth } from '@/hooks/business/auth';
import ExecutionSettingsFields from '@/components/business/execution-settings-fields/index.vue';
import TargetSelectorFields from '@/components/business/target-selector-fields/index.vue';
import RunPreviewDialog from '@/components/business/run-preview-dialog/index.vue';
import { SYSTEM_TIMEZONE_LABEL, cronFieldSpecs, cronSegmentIndex, humanizeCron } from './shared';

defineOptions({ name: 'TaskSchedule' });

const router = useRouter();
const { hasAuth } = useAuth();

/** ============ 搜索 ============ */

const enabledOptions = [
  { value: true, label: '启用' },
  { value: false, label: '停用' }
];

function getInitSearchParams() {
  return {
    current: 1,
    size: 10,
    search: undefined as string | undefined,
    enabled: undefined as boolean | null | undefined
  };
}

const searchParams = ref(getInitSearchParams());

/** ============ 列表 ============ */

const overlapPolicyText: Record<string, string> = {
  skip: '跳过本次',
  allow: '允许并行',
  queue: '结束后补跑一次'
};

const misfirePolicyText: Record<string, string> = {
  fire: '立即补跑',
  skip: '跳过错过的次数'
};

const lastOutcomeText: Record<string, string> = {
  dispatched: '已投递',
  overlap_skipped: '重叠跳过',
  overlap_queued: '重叠排队补跑',
  misfire_skipped: '错过跳过',
  expired: '已过期',
  invalid: '配置或权限失效'
};

const scheduleTypeText: Record<Api.Jobs.ScheduleType, string> = {
  periodic: '周期性',
  once: '一次性'
};

const togglingId = ref<number | null>(null);
const runningId = ref<number | null>(null);
const previewVisible = ref(false);
const preview = shallowRef<Api.Jobs.RunPreview | null>(null);
const previewScheduleId = ref<number | null>(null);
const savePreviewVisible = ref(false);
const savePreview = shallowRef<Api.Jobs.RunPreview | null>(null);
const pendingSavePayload = shallowRef<Api.Jobs.ScheduledJobPayload | null>(null);

const { columns, columnChecks, data, getData, getDataByPage, loading, mobilePagination } = useUIPaginatedTable({
  paginationProps: {
    currentPage: searchParams.value.current,
    pageSize: searchParams.value.size
  },
  api: () =>
    fetchGetScheduledJobList({
      current: searchParams.value.current,
      size: searchParams.value.size,
      search: searchParams.value.search || null,
      enabled: typeof searchParams.value.enabled === 'boolean' ? searchParams.value.enabled : null
    }),
  transform: response => defaultTransform(response),
  onPaginationParamsChange: params => {
    searchParams.value.current = params.currentPage ?? 1;
    searchParams.value.size = params.pageSize ?? 10;
  },
  columns: () => [
    { prop: 'id', label: 'ID', width: 80, align: 'center', className: 'tabular-nums' },
    { prop: 'name', label: '名称', minWidth: 150, showOverflowTooltip: true },
    {
      prop: 'schedule_type',
      label: '调度类型',
      width: 100,
      align: 'center',
      formatter: row => (
        <ElTag size="small" type={row.schedule_type === 'once' ? 'warning' : 'primary'} disable-transitions>
          {scheduleTypeText[row.schedule_type] ?? '-'}
        </ElTag>
      )
    },
    {
      prop: 'cron_expression',
      label: '触发规则',
      minWidth: 190,
      showOverflowTooltip: true,
      formatter: row => (row.schedule_type === 'once' ? row.run_at || '-' : row.cron_expression || '-')
    },
    {
      prop: 'timezone',
      label: '时区',
      width: 210,
      formatter: row => (row.schedule_type === 'once' ? SYSTEM_TIMEZONE_LABEL : row.timezone || '-')
    },
    {
      prop: 'enabled',
      label: '启用',
      width: 90,
      align: 'center',
      formatter: row => (
        <ElSwitch
          modelValue={row.enabled}
          loading={togglingId.value === row.id}
          onChange={(val: string | number | boolean) => onToggleEnabled(row, Boolean(val))}
        />
      )
    },
    { prop: 'next_run_at', label: '下次执行时间', width: 170, formatter: row => row.next_run_at || '-' },
    { prop: 'expires_at', label: '过期时间', width: 170, formatter: row => row.expires_at || '-' },
    {
      prop: 'remark',
      label: '备注',
      minWidth: 140,
      showOverflowTooltip: true,
      formatter: row => row.remark || '-'
    },
    {
      prop: 'lastOutcome',
      label: '最近调度结果',
      minWidth: 180,
      showOverflowTooltip: true,
      formatter: row =>
        row.lastOutcome
          ? `${lastOutcomeText[row.lastOutcome.outcome] ?? row.lastOutcome.outcome}${row.lastOutcome.reason ? ` ${row.lastOutcome.reason}` : ''}`
          : '-'
    },
    {
      prop: 'operate',
      label: '操作',
      width: 300,
      align: 'center',
      fixed: 'right',
      formatter: row => (
        <>
          {hasAuth('jobs.scheduled_job:run_now') ? (
            <ElButton
              type="primary"
              plain
              size="small"
              loading={runningId.value === row.id}
              onClick={() => onPreviewRun(row)}
            >
              立即执行
            </ElButton>
          ) : null}
          <ElButton type="primary" plain size="small" onClick={() => openEdit(row)}>
            编辑
          </ElButton>
          <ElButton type="primary" plain size="small" onClick={() => viewExecutionHistory(row)}>
            执行历史
          </ElButton>
          <ElButton type="danger" plain size="small" onClick={() => onDelete(row)}>
            删除
          </ElButton>
        </>
      )
    }
  ]
});

function viewExecutionHistory(row: Api.Jobs.ScheduledJobRecord) {
  router.push({
    name: 'task_execution-history',
    query: { scheduledJobId: String(row.id), scheduledJobName: row.name }
  });
}

function resetSearchParams() {
  searchParams.value = getInitSearchParams();
  getDataByPage();
}

async function onToggleEnabled(row: Api.Jobs.ScheduledJobRecord, enabled: boolean) {
  togglingId.value = row.id;
  try {
    const { error } = await fetchUpdateScheduledJob(row.id, { enabled });
    if (!error) {
      window.$notification?.success(enabled ? '已启用' : '已停用');
      getData();
    }
  } finally {
    togglingId.value = null;
  }
}

async function onDelete(row: Api.Jobs.ScheduledJobRecord) {
  try {
    await ElMessageBox.confirm(`确认删除定时任务「${row.name}」？`, '删除确认', {
      type: 'warning',
      confirmButtonText: '确定',
      cancelButtonText: '取消'
    });
  } catch {
    return;
  }

  const { error } = await fetchDeleteScheduledJob(row.id);
  if (!error) {
    window.$notification?.success('删除成功');
    getData();
  }
}

async function onPreviewRun(row: Api.Jobs.ScheduledJobRecord) {
  runningId.value = row.id;
  try {
    const { data: result, error } = await fetchPreviewScheduledJob(row.id);
    if (error || !result) return;
    preview.value = result;
    previewScheduleId.value = row.id;
    previewVisible.value = true;
  } finally {
    runningId.value = null;
  }
}

async function confirmRunNow() {
  if (!previewScheduleId.value || !preview.value) return;
  runningId.value = previewScheduleId.value;
  try {
    const { data: run, error } = await fetchRunScheduledJobNow(previewScheduleId.value, preview.value);
    if (error || !run) return;
    previewVisible.value = false;
    window.$notification?.success('定时任务已发起运行');
    getData();
    router.push({ name: 'task_run-detail', params: { id: run.id }, query: { domain: 'task' } });
  } finally {
    runningId.value = null;
  }
}

/** ============ 抽屉选项数据 ============ */

const versions = shallowRef<Api.Jobs.WorkflowVersionOption[]>([]);
const pools = shallowRef<Api.Jobs.WorkerPoolOption[]>([]);
const gateways = shallowRef<Api.Jobs.GatewayRecord[]>([]);
const hosts = shallowRef<Api.Jobs.HostOption[]>([]);

async function searchHosts(keyword = '') {
  const { data: hostList, error } = await fetchGetHostOptions(keyword);
  if (!error) hosts.value = hostList.list;
}

async function loadOptions() {
  const [versionResult, poolResult, gatewayResult] = await Promise.all([
    fetchPublishedWorkflowVersions(),
    fetchGetWorkerPools(),
    fetchGetGatewayList({ current: 1, size: 100 }),
    searchHosts()
  ]);
  if (!versionResult.error) {
    versions.value = versionResult.data.list.filter(item => !item.workflowCode.startsWith('__quick_'));
  }
  if (!poolResult.error) {
    pools.value = poolResult.data.list.filter(item => item.isActive);
  }
  if (!gatewayResult.error) {
    gateways.value = gatewayResult.data.records.filter(item => item.status === 'normal');
  }
}

onMounted(loadOptions);

/** ============ 新增/编辑抽屉 ============ */

type HostStrategy = 'inherit' | 'parallel' | 'serial' | 'rolling';

const scheduleTypeOptions = [
  { value: 'periodic', label: '周期性任务' },
  { value: 'once', label: '一次性任务' }
] as const;

/** 后端 datetime 为 ISO（含 T），DatePicker 需要空格分隔的本地格式 */
function normalizeDateTimeInput(value: string | null | undefined): string {
  return value ? value.replace('T', ' ').slice(0, 19) : '';
}

function getInitForm() {
  return {
    name: '',
    workflow_version: null as number | null,
    worker_pool: null as number | null,
    gateway: null as number | null,
    schedule_type: 'periodic' as Api.Jobs.ScheduleType,
    cron_expression: '',
    run_at: '',
    timezone: 'Asia/Shanghai',
    expires_at: '',
    remark: '',
    host_ids: [] as number[],
    group_ids: [] as number[],
    tag_ids: [] as number[],
    host_strategy: 'inherit' as HostStrategy,
    forks: null as number | null,
    serial_batch: null as number | null,
    max_fail_percentage: null as number | null,
    timeout_seconds: null as number | null,
    queue_timeout_seconds: 3600,
    enabled: true,
    overlap_policy: 'skip' as Api.Jobs.ScheduleOverlapPolicy,
    misfire_policy: 'fire' as Api.Jobs.ScheduleMisfirePolicy,
    misfire_grace_seconds: 3600,
    input_vars_text: '{}'
  };
}

const editVisible = ref(false);
const editingRow = shallowRef<Api.Jobs.ScheduledJobRecord | null>(null);
const saving = ref(false);
const formRef = ref();
const form = reactive(getInitForm());
const advancedOpen = ref<string[]>([]);
const targetOpen = ref<string[]>(['target']);

/** 折叠态下的目标摘要，收起后仍能看到已选范围 */
const targetSummaryText = computed(() => {
  const parts: string[] = [];
  if (form.host_ids.length) parts.push(`${form.host_ids.length} 台主机`);
  if (form.group_ids.length) parts.push(`${form.group_ids.length} 个分组`);
  if (form.tag_ids.length) parts.push(`${form.tag_ids.length} 个标签`);
  return parts.length ? parts.join(' / ') : '未选择目标';
});

/** 目标主机为多选数组，required 基础规则无法校验空数组，用自定义 validator */
function validateHostIds(_rule: unknown, value: number[], callback: (error?: Error) => void) {
  if (!value.length && !form.group_ids.length && !form.tag_ids.length) return callback(new Error('请选择目标主机'));
  return callback();
}

/** 周期性校验 Cron，一次性校验执行时间 */
const formRules = computed(() => ({
  name: [{ required: true, message: '请填写任务名称', trigger: 'blur' }],
  workflow_version: [{ required: true, message: '请选择流程版本', trigger: 'change' }],
  ...(form.schedule_type === 'once'
    ? { run_at: [{ required: true, message: '请选择执行时间', trigger: 'change' }] }
    : { cron_expression: [{ required: true, message: '请填写 Cron 表达式', trigger: 'blur' }] }),
  host_ids: [{ required: true, validator: validateHostIds, trigger: 'change' }]
}));

/** ============ Cron 人话预览 + 字段说明图高亮 ============ */

const cronPreviewText = computed(() => humanizeCron(form.cron_expression));
const cronActiveSegment = ref(-1);

/** 输入/点击/聚焦时按插入符位置高亮对应 Cron 段 */
function onCronCaret(event: Event) {
  const target = event.target as HTMLInputElement | null;
  const caret = target?.selectionStart ?? form.cron_expression.length;
  cronActiveSegment.value = cronSegmentIndex(form.cron_expression, caret);
}

function openAdd() {
  editingRow.value = null;
  Object.assign(form, getInitForm());
  const defaultPool = pools.value.find(item => item.isDefault) ?? pools.value[0];
  form.worker_pool = defaultPool?.id ?? null;
  advancedOpen.value = [];
  targetOpen.value = ['target'];
  cronActiveSegment.value = -1;
  editVisible.value = true;
}

function openEdit(row: Api.Jobs.ScheduledJobRecord) {
  editingRow.value = row;
  Object.assign(form, getInitForm(), {
    name: row.name,
    workflow_version: row.workflow_version,
    worker_pool: row.worker_pool,
    gateway: row.gateway,
    schedule_type: row.schedule_type ?? 'periodic',
    cron_expression: row.cron_expression ?? '',
    run_at: normalizeDateTimeInput(row.run_at),
    expires_at: normalizeDateTimeInput(row.expires_at),
    remark: row.remark ?? '',
    timezone: row.timezone,
    host_ids: [...row.host_ids],
    group_ids: [...row.group_ids],
    tag_ids: [...row.tag_ids],
    host_strategy: row.host_strategy ?? 'inherit',
    forks: row.forks,
    serial_batch: row.serial_batch,
    max_fail_percentage: row.max_fail_percentage,
    timeout_seconds: row.timeout_seconds,
    queue_timeout_seconds: row.queue_timeout_seconds,
    enabled: row.enabled,
    overlap_policy: (row.overlap_policy as Api.Jobs.ScheduleOverlapPolicy) || 'skip',
    misfire_policy: (row.misfire_policy as Api.Jobs.ScheduleMisfirePolicy) || 'fire',
    misfire_grace_seconds: row.misfire_grace_seconds ?? 3600,
    input_vars_text: JSON.stringify(row.input_vars ?? {}, null, 2)
  });
  advancedOpen.value = [];
  targetOpen.value = ['target'];
  cronActiveSegment.value = -1;
  editVisible.value = true;
}

async function saveEdit() {
  await formRef.value?.validate();

  let inputVars: Record<string, unknown>;
  try {
    inputVars = JSON.parse(form.input_vars_text || '{}');
  } catch {
    window.$message?.error('任务单参数不是合法的 JSON');
    return;
  }
  if (typeof inputVars !== 'object' || Array.isArray(inputVars) || inputVars === null) {
    window.$message?.error('任务单参数必须是 JSON 对象');
    return;
  }

  saving.value = true;
  try {
    const payload: Api.Jobs.ScheduledJobPayload = {
      name: form.name.trim(),
      workflow_version: form.workflow_version!,
      worker_pool: form.worker_pool,
      gateway: form.gateway,
      schedule_type: form.schedule_type,
      run_at: form.schedule_type === 'once' ? form.run_at || null : null,
      expires_at: form.expires_at || null,
      remark: form.remark.trim(),
      host_ids: form.host_ids,
      group_ids: form.group_ids,
      tag_ids: form.tag_ids,
      input_vars: inputVars,
      host_strategy: form.host_strategy === 'inherit' ? null : form.host_strategy,
      forks: form.forks ?? null,
      serial_batch: form.serial_batch ?? null,
      max_fail_percentage: form.max_fail_percentage ?? null,
      timeout_seconds: form.timeout_seconds ?? null,
      queue_timeout_seconds: form.queue_timeout_seconds,
      enabled: form.enabled,
      overlap_policy: form.overlap_policy,
      misfire_policy: form.misfire_policy,
      misfire_grace_seconds: form.misfire_grace_seconds
    };
    if (form.schedule_type === 'periodic') {
      payload.cron_expression = form.cron_expression.trim();
      payload.timezone = form.timezone;
    }
    const { data: previewData, error } = await fetchPreviewWorkflowRun({
      workflowVersionId: payload.workflow_version,
      workerPoolId: payload.worker_pool,
      hostIds: payload.host_ids,
      groupIds: payload.group_ids,
      tagIds: payload.tag_ids,
      inputVars: payload.input_vars,
      hostStrategy: payload.host_strategy,
      forks: payload.forks,
      serialBatch: payload.serial_batch,
      maxFailPercentage: payload.max_fail_percentage,
      timeoutSeconds: payload.timeout_seconds,
      gatewayId: payload.gateway
    });
    if (error || !previewData) return;
    pendingSavePayload.value = payload;
    savePreview.value = previewData;
    savePreviewVisible.value = true;
  } finally {
    saving.value = false;
  }
}

async function confirmSave() {
  if (!pendingSavePayload.value || !savePreview.value) return;
  saving.value = true;
  try {
    const payload: Api.Jobs.ScheduledJobPayload = {
      ...pendingSavePayload.value,
      expectedTargetIds: savePreview.value.targets.map(target => target.hostId),
      expectedTargetFingerprint: savePreview.value.targetFingerprint
    };
    const { error } = editingRow.value
      ? await fetchUpdateScheduledJob(editingRow.value.id, payload)
      : await fetchAddScheduledJob(payload);
    if (error) return;
    window.$notification?.success(editingRow.value ? '更新成功' : '新增成功');
    savePreviewVisible.value = false;
    editVisible.value = false;
    getData();
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <div class="min-h-500px flex-col-stretch gap-16px overflow-hidden lt-sm:overflow-auto">
    <SearchPanel @reset="resetSearchParams" @search="getDataByPage">
      <ElForm :model="searchParams" label-width="80px" @submit.prevent="getDataByPage">
        <ElFormItem label="启用状态">
          <ElSelect v-model="searchParams.enabled" clearable placeholder="全部">
            <ElOption
              v-for="item in enabledOptions"
              :key="String(item.value)"
              :label="item.label"
              :value="item.value"
            />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="关键词">
          <ElInput v-model="searchParams.search" clearable placeholder="任务名称" @keyup.enter="getDataByPage()" />
        </ElFormItem>
      </ElForm>
    </SearchPanel>

    <ElCard class="card-wrapper sm:flex-1-hidden">
      <template #header>
        <div class="flex flex-wrap items-center justify-between gap-12px">
          <p>定时任务</p>
          <div class="flex items-center gap-8px">
            <ElButton type="primary" @click="openAdd">新增定时任务</ElButton>
            <TableHeaderOperation
              v-model:columns="columnChecks"
              :loading="loading"
              :show-add="false"
              :show-batch-delete="false"
              @refresh="getData"
            />
          </div>
        </div>
      </template>
      <div class="h-[calc(100%-52px)]">
        <ElTable v-loading="loading" height="100%" border class="sm:h-full" :data="data" row-key="id">
          <ElTableColumn v-for="col in columns" :key="col.prop" v-bind="col" />
        </ElTable>
      </div>
      <div class="mt-20px flex justify-end">
        <ElPagination
          v-if="mobilePagination.total"
          layout="total,prev,pager,next,sizes"
          v-bind="mobilePagination"
          @current-change="mobilePagination['current-change']"
          @size-change="mobilePagination['size-change']"
        />
      </div>
    </ElCard>

    <ElDrawer v-model="editVisible" :title="editingRow ? '编辑定时任务' : '新增定时任务'" size="min(720px, 100%)">
      <ElForm
        ref="formRef"
        :model="form"
        :rules="formRules"
        label-width="170px"
        label-suffix="："
        require-asterisk-position="left"
        class="responsive-form"
      >
        <ElFormItem label="任务名称" prop="name">
          <ElInput v-model="form.name" placeholder="请输入任务名称" />
        </ElFormItem>
        <ElFormItem prop="workflow_version">
          <template #label>
            <FormLabelHelp
              label="流程版本"
              :help="['只能选择已发布版本；定时任务按版本固定执行，模板发布新版本后不会自动切换。']"
            />
          </template>
          <ElSelect v-model="form.workflow_version" filterable class="w-full" placeholder="选择已发布的流程版本">
            <ElOption
              v-for="version in versions"
              :key="version.id"
              :value="version.id"
              :label="`${version.workflowName} · v${version.version}`"
            />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="定时规则" prop="schedule_type">
          <ElRadioGroup v-model="form.schedule_type">
            <ElRadio v-for="item in scheduleTypeOptions" :key="item.value" :value="item.value">
              {{ item.label }}
            </ElRadio>
          </ElRadioGroup>
        </ElFormItem>
        <ElFormItem v-if="form.schedule_type === 'periodic'" prop="cron_expression">
          <template #label>
            <FormLabelHelp
              label="表达式"
              :help="[
                '5 段式：分 时 日 月 周，支持 * 、逗号列举、- 范围、/ 步长。',
                '如 0 2 * * * 表示每天 2 点执行。'
              ]"
            />
          </template>
          <div class="cron-guide">
            <p class="cron-guide__desc">{{ cronPreviewText }}</p>
            <ElInput
              v-model="form.cron_expression"
              placeholder="请输入表达式，请注意空格分隔"
              @keyup="onCronCaret"
              @click="onCronCaret"
              @focus="onCronCaret"
            />
            <div class="cron-guide__specs">
              <div
                v-for="(spec, index) in cronFieldSpecs"
                :key="spec.key"
                class="cron-spec"
                :class="{ 'is-active': cronActiveSegment === index }"
              >
                <p class="cron-spec__name">{{ spec.label }}</p>
                <p class="cron-spec__meta">允许值：{{ spec.range }}</p>
                <p class="cron-spec__meta">特殊字符：{{ spec.chars }}</p>
              </div>
            </div>
          </div>
        </ElFormItem>
        <ElFormItem v-else prop="run_at">
          <template #label>
            <FormLabelHelp
              label="执行时间"
              :help="['按 Asia/Shanghai 时区在指定时间发起一次运行；发起后自动停用，结果可在执行历史查看。']"
            />
          </template>
          <ElDatePicker
            v-model="form.run_at"
            type="datetime"
            value-format="YYYY-MM-DD HH:mm:ss"
            placeholder="请选择执行时间"
            class="w-full"
          />
          <p class="mt-4px w-full text-12px text-[var(--el-text-color-regular)]">时区：{{ SYSTEM_TIMEZONE_LABEL }}</p>
        </ElFormItem>
        <ElFormItem>
          <template #label>
            <FormLabelHelp label="过期时间" :help="['超过该时间后不再发起新的运行；留空表示长期有效。']" />
          </template>
          <ElDatePicker
            v-model="form.expires_at"
            type="datetime"
            value-format="YYYY-MM-DD HH:mm:ss"
            placeholder="请选择过期时间（留空不过期）"
            class="w-full"
          />
          <p class="mt-4px w-full text-12px text-[var(--el-text-color-regular)]">
            时区：{{ SYSTEM_TIMEZONE_LABEL }}，留空表示不过期。
          </p>
        </ElFormItem>
        <ElFormItem label="是否启用">
          <ElSwitch v-model="form.enabled" />
        </ElFormItem>
        <ElFormItem label="备注">
          <ElInput v-model="form.remark" type="textarea" :rows="3" placeholder="请填写备注" />
        </ElFormItem>
        <ElCollapse v-model="targetOpen" class="advanced-collapse form-section">
          <ElCollapseItem name="target">
            <template #title>
              <span class="flex items-center gap-8px">
                <span>执行目标</span>
                <span class="text-12px text-gray-500 font-normal">{{ targetSummaryText }}</span>
              </span>
            </template>
            <ElFormItem label="目标主机" prop="host_ids">
              <ElSelect
                v-model="form.host_ids"
                multiple
                filterable
                remote
                clearable
                :remote-method="searchHosts"
                class="w-full"
                placeholder="输入关键字搜索主机（主机名/IP）"
              >
                <ElOption
                  v-for="host in hosts"
                  :key="host.id"
                  :value="host.id"
                  :label="`${host.hostname} · ${host.internalIp}`"
                />
              </ElSelect>
            </ElFormItem>
            <TargetSelectorFields v-model:group-ids="form.group_ids" v-model:tag-ids="form.tag_ids" />
          </ElCollapseItem>
        </ElCollapse>
        <ElCollapse v-model="advancedOpen" class="advanced-collapse form-section">
          <ElCollapseItem name="advanced" title="高级配置">
            <ElFormItem label="执行节点池">
              <ElSelect v-model="form.worker_pool" clearable class="w-full" placeholder="留空使用默认池">
                <ElOption v-for="pool in pools" :key="pool.id" :value="pool.id" :label="pool.name" />
              </ElSelect>
            </ElFormItem>
            <ElFormItem>
              <template #label>
                <FormLabelHelp
                  label="连接网关"
                  :help="['显式选择后，本次定时运行的 SSH 主机经该网关连接；留空则直连。']"
                />
              </template>
              <ElSelect v-model="form.gateway" clearable class="w-full" placeholder="不指定则直连">
                <ElOption v-for="gateway in gateways" :key="gateway.id" :value="gateway.id" :label="gateway.name" />
              </ElSelect>
            </ElFormItem>
            <ElFormItem v-if="form.schedule_type === 'periodic'">
              <template #label>
                <FormLabelHelp
                  label="时区"
                  :help="['按该时区解析 Cron 表达式并计算下次执行时间，如 Asia/Shanghai。']"
                />
              </template>
              <ElInput v-model="form.timezone" placeholder="如 Asia/Shanghai" />
            </ElFormItem>
            <ExecutionSettingsFields
              v-model:host-strategy="form.host_strategy"
              v-model:forks="form.forks"
              v-model:serial-batch="form.serial_batch"
              v-model:max-fail-percentage="form.max_fail_percentage"
              v-model:timeout-seconds="form.timeout_seconds"
            />
            <ElFormItem>
              <template #label>
                <FormLabelHelp
                  label="排队超时（秒）"
                  :help="['运行等待执行节点池分配资源的最长时间；超时仍未开始执行则放弃本次运行。']"
                />
              </template>
              <ElInputNumber v-model="form.queue_timeout_seconds" :min="1" :step="60" />
            </ElFormItem>
            <ElFormItem label="重叠策略">
              <ElSelect v-model="form.overlap_policy" class="w-full">
                <ElOption v-for="(label, value) in overlapPolicyText" :key="value" :value="value" :label="label" />
              </ElSelect>
              <p class="mt-4px w-full text-12px text-gray-500">
                上次运行未结束时：跳过本次 / 仍并行派发 / 结束后补跑一次
              </p>
            </ElFormItem>
            <ElFormItem v-if="form.schedule_type === 'periodic'">
              <template #label>
                <FormLabelHelp
                  label="错过策略"
                  :help="[
                    '立即补跑：错过触发时间也会延迟执行这一次；',
                    '跳过错过的次数：错过且超过宽限期则跳过，等待下一次触发。'
                  ]"
                />
              </template>
              <ElSelect v-model="form.misfire_policy" class="w-full">
                <ElOption v-for="(label, value) in misfirePolicyText" :key="value" :value="value" :label="label" />
              </ElSelect>
              <p class="mt-4px w-full text-12px text-gray-500">调度停机等原因错过触发时间且超过宽限期后的处理方式</p>
            </ElFormItem>
            <ElFormItem v-if="form.schedule_type === 'periodic'">
              <template #label>
                <FormLabelHelp
                  label="错过宽限期（秒）"
                  :help="['触发时间被错过多久之内仍允许补跑；超过该时间则按错过策略处理。']"
                />
              </template>
              <ElInputNumber v-model="form.misfire_grace_seconds" :min="0" :step="60" />
            </ElFormItem>
            <ElFormItem>
              <template #label>
                <FormLabelHelp
                  label="任务单参数 JSON"
                  :help="[
                    '每次触发时作为任务单参数传入，键名需与流程定义的任务单参数一致，必填参数不能为空。',
                    '示例：{&quot;branch&quot;: &quot;main&quot;}'
                  ]"
                />
              </template>
              <ElInput
                v-model="form.input_vars_text"
                type="textarea"
                :rows="6"
                placeholder='JSON 对象，如 {"key": "value"}'
              />
            </ElFormItem>
          </ElCollapseItem>
        </ElCollapse>
      </ElForm>
      <template #footer>
        <ElButton @click="editVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="saving" @click="saveEdit">保存</ElButton>
      </template>
    </ElDrawer>
    <RunPreviewDialog
      v-model:visible="previewVisible"
      :preview="preview"
      :loading="runningId !== null"
      @confirm="confirmRunNow"
    />
    <RunPreviewDialog
      v-model:visible="savePreviewVisible"
      :preview="savePreview"
      :loading="saving"
      title="确认定时任务配置"
      confirm-text="确认并保存"
      note="这是当前解析出的目标主机；未来每次触发会重新解析选择规则，并为该次运行冻结实际目标。"
      @confirm="confirmSave"
    />
  </div>
</template>

<style scoped>
/** 折叠分区与相邻字段之间加分隔线，区分基础字段与执行相关配置 */
.form-section {
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid var(--el-border-color-lighter);
}

.cron-guide {
  width: 100%;
  padding: 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  background-color: var(--el-fill-color-light);
}

.cron-guide__desc {
  margin: 0 0 8px;
  text-align: center;
  font-size: 13px;
  font-weight: 600;
  color: var(--el-color-primary);
}

.cron-guide__specs {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 8px;
  margin-top: 8px;
}

.cron-spec {
  padding: 6px 8px;
  border: 1px solid var(--el-border-color);
  border-radius: 4px;
  background-color: var(--el-bg-color);
  transition:
    border-color 0.2s,
    box-shadow 0.2s;
}

.cron-spec.is-active {
  border-color: var(--el-color-primary);
  box-shadow: 0 0 0 2px var(--el-color-primary-light-8);
}

.cron-spec__name {
  margin: 0;
  font-size: 12px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.cron-spec__meta {
  margin: 2px 0 0;
  font-size: 11px;
  line-height: 1.4;
  color: var(--el-text-color-secondary);
  word-break: break-all;
}

@media (max-width: 639px) {
  .cron-guide__specs {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
