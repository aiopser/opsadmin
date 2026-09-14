<script setup lang="tsx">
import { computed, onMounted, reactive, ref, shallowRef } from 'vue';
import {
  fetchAddScheduledJob,
  fetchDeleteScheduledJob,
  fetchGetHostOptions,
  fetchGetScheduledJobList,
  fetchGetWorkerPools,
  fetchPublishedWorkflowVersions,
  fetchUpdateScheduledJob
} from '@/service/api';
import { defaultTransform, useUIPaginatedTable } from '@/hooks/common/table';

defineOptions({ name: 'TaskSchedule' });

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

const hostStrategyText: Record<string, string> = {
  parallel: '并行',
  serial: '串行',
  rolling: '滚动'
};

const togglingId = ref<number | null>(null);

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
    { prop: 'id', label: 'ID', width: 80 },
    { prop: 'name', label: '名称', minWidth: 150, showOverflowTooltip: true },
    { prop: 'cron_expression', label: 'Cron 表达式', minWidth: 140, showOverflowTooltip: true },
    { prop: 'timezone', label: '时区', width: 140 },
    {
      prop: 'host_strategy',
      label: '执行策略',
      width: 100,
      align: 'center',
      formatter: row => hostStrategyText[row.host_strategy] ?? row.host_strategy
    },
    { prop: 'forks', label: 'forks', width: 80, align: 'center' },
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
    {
      prop: 'operate',
      label: '操作',
      width: 150,
      align: 'center',
      fixed: 'right',
      formatter: row => (
        <>
          <ElButton type="primary" plain size="small" onClick={() => openEdit(row)}>
            编辑
          </ElButton>
          <ElButton type="danger" plain size="small" onClick={() => onDelete(row)}>
            删除
          </ElButton>
        </>
      )
    }
  ]
});

const hasFilter = computed(() => Boolean(searchParams.value.search || searchParams.value.enabled !== undefined));

function resetSearchParams() {
  searchParams.value = getInitSearchParams();
  getDataByPage();
}

async function onToggleEnabled(row: Api.Jobs.ScheduledJobRecord, enabled: boolean) {
  togglingId.value = row.id;
  try {
    const { error } = await fetchUpdateScheduledJob(row.id, { enabled });
    if (!error) {
      window.$message?.success(enabled ? '已启用' : '已停用');
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
    window.$message?.success('删除成功');
    getData();
  }
}

/** ============ 抽屉选项数据 ============ */

const versions = shallowRef<Api.Jobs.WorkflowVersionOption[]>([]);
const pools = shallowRef<Api.Jobs.WorkerPoolOption[]>([]);
const hosts = shallowRef<Api.Jobs.HostOption[]>([]);

async function searchHosts(keyword = '') {
  const { data: hostList, error } = await fetchGetHostOptions(keyword);
  if (!error) hosts.value = hostList.list;
}

async function loadOptions() {
  const [versionResult, poolResult] = await Promise.all([
    fetchPublishedWorkflowVersions(),
    fetchGetWorkerPools(),
    searchHosts()
  ]);
  if (!versionResult.error) {
    versions.value = versionResult.data.list.filter(item => !item.workflowCode.startsWith('__quick_'));
  }
  if (!poolResult.error) {
    pools.value = poolResult.data.list.filter(item => item.isActive);
  }
}

onMounted(loadOptions);

/** ============ 新增/编辑抽屉 ============ */

type HostStrategy = 'parallel' | 'serial' | 'rolling';

const hostStrategyOptions = [
  { value: 'parallel', label: '并行' },
  { value: 'serial', label: '串行' },
  { value: 'rolling', label: '滚动' }
] as const;

function getInitForm() {
  return {
    name: '',
    workflow_version: null as number | null,
    worker_pool: null as number | null,
    cron_expression: '',
    timezone: 'Asia/Shanghai',
    host_ids: [] as number[],
    host_strategy: 'parallel' as HostStrategy,
    forks: 5,
    serial_batch: 0,
    max_fail_percentage: 0,
    timeout_seconds: 3600,
    queue_timeout_seconds: 3600,
    bypass_host_gateway: false,
    enabled: true,
    input_vars_text: '{}'
  };
}

const editVisible = ref(false);
const editingRow = shallowRef<Api.Jobs.ScheduledJobRecord | null>(null);
const saving = ref(false);
const form = reactive(getInitForm());

function openAdd() {
  editingRow.value = null;
  Object.assign(form, getInitForm());
  const defaultPool = pools.value.find(item => item.isDefault) ?? pools.value[0];
  form.worker_pool = defaultPool?.id ?? null;
  editVisible.value = true;
}

function openEdit(row: Api.Jobs.ScheduledJobRecord) {
  editingRow.value = row;
  Object.assign(form, getInitForm(), {
    name: row.name,
    workflow_version: row.workflow_version,
    worker_pool: row.worker_pool,
    cron_expression: row.cron_expression,
    timezone: row.timezone,
    host_ids: [...row.host_ids],
    host_strategy: row.host_strategy as HostStrategy,
    forks: row.forks,
    serial_batch: row.serial_batch,
    max_fail_percentage: row.max_fail_percentage,
    timeout_seconds: row.timeout_seconds,
    queue_timeout_seconds: row.queue_timeout_seconds,
    bypass_host_gateway: row.bypass_host_gateway,
    enabled: row.enabled,
    input_vars_text: JSON.stringify(row.input_vars ?? {}, null, 2)
  });
  editVisible.value = true;
}

async function saveEdit() {
  if (!form.name.trim()) {
    window.$message?.warning('请填写任务名称');
    return;
  }
  if (!form.workflow_version) {
    window.$message?.warning('请选择工作流版本');
    return;
  }
  if (!form.cron_expression.trim()) {
    window.$message?.warning('请填写 Cron 表达式');
    return;
  }
  if (!form.host_ids.length) {
    window.$message?.warning('请选择目标主机');
    return;
  }
  let inputVars: Record<string, unknown>;
  try {
    inputVars = JSON.parse(form.input_vars_text || '{}');
  } catch {
    window.$message?.error('输入变量不是合法的 JSON');
    return;
  }
  if (typeof inputVars !== 'object' || Array.isArray(inputVars) || inputVars === null) {
    window.$message?.error('输入变量必须是 JSON 对象');
    return;
  }

  saving.value = true;
  try {
    const payload: Api.Jobs.ScheduledJobPayload = {
      name: form.name.trim(),
      workflow_version: form.workflow_version,
      worker_pool: form.worker_pool,
      host_ids: form.host_ids,
      cron_expression: form.cron_expression.trim(),
      timezone: form.timezone,
      input_vars: inputVars,
      host_strategy: form.host_strategy,
      forks: form.forks,
      serial_batch: form.serial_batch,
      max_fail_percentage: form.max_fail_percentage,
      timeout_seconds: form.timeout_seconds,
      queue_timeout_seconds: form.queue_timeout_seconds,
      bypass_host_gateway: form.bypass_host_gateway,
      enabled: form.enabled
    };
    const { error } = editingRow.value
      ? await fetchUpdateScheduledJob(editingRow.value.id, payload)
      : await fetchAddScheduledJob(payload);
    if (!error) {
      window.$message?.success(editingRow.value ? '更新成功' : '新增成功');
      editVisible.value = false;
      getData();
    }
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <div class="min-h-500px flex-col-stretch gap-16px overflow-hidden lt-sm:overflow-auto">
    <ElCard class="card-wrapper">
      <ElForm :model="searchParams" label-width="90px" inline @submit.prevent>
        <ElFormItem label="启用状态">
          <ElSelect v-model="searchParams.enabled" clearable placeholder="全部" class="w-120px">
            <ElOption
              v-for="item in enabledOptions"
              :key="String(item.value)"
              :label="item.label"
              :value="item.value"
            />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="关键词">
          <ElInput
            v-model="searchParams.search"
            clearable
            placeholder="任务名称"
            class="w-200px"
            @keyup.enter="getDataByPage()"
          />
        </ElFormItem>
        <ElFormItem>
          <ElButton type="primary" @click="getDataByPage()">查询</ElButton>
          <ElButton :disabled="!hasFilter" @click="resetSearchParams">重置</ElButton>
        </ElFormItem>
      </ElForm>
    </ElCard>

    <ElCard class="card-wrapper sm:flex-1-hidden">
      <template #header>
        <div class="flex items-center justify-between">
          <p>定时任务</p>
          <div class="flex items-center gap-8px">
            <ElButton type="primary" @click="openAdd">新增任务</ElButton>
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

    <ElDrawer v-model="editVisible" :title="editingRow ? '编辑定时任务' : '新增定时任务'" size="600px">
      <ElForm :model="form" label-width="150px">
        <ElFormItem label="任务名称" required>
          <ElInput v-model="form.name" placeholder="请输入任务名称" />
        </ElFormItem>
        <ElFormItem label="工作流版本" required>
          <ElSelect v-model="form.workflow_version" filterable class="w-full" placeholder="选择已发布的工作流版本">
            <ElOption
              v-for="version in versions"
              :key="version.id"
              :value="version.id"
              :label="`${version.workflowName} · v${version.version}`"
            />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="Worker 池">
          <ElSelect v-model="form.worker_pool" clearable class="w-full" placeholder="留空使用默认池">
            <ElOption v-for="pool in pools" :key="pool.id" :value="pool.id" :label="pool.name" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="Cron 表达式" required>
          <ElInput v-model="form.cron_expression" placeholder="如：0 2 * * *" />
          <p class="mt-4px w-full text-12px text-gray-400">5 段式：分 时 日 月 周，如每天 2 点执行为 0 2 * * *</p>
        </ElFormItem>
        <ElFormItem label="时区">
          <ElInput v-model="form.timezone" placeholder="如 Asia/Shanghai" />
        </ElFormItem>
        <ElFormItem label="目标主机" required>
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
              :label="`${host.hostname} · ${host.primaryIp}`"
            />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="执行策略">
          <ElRadioGroup v-model="form.host_strategy">
            <ElRadio v-for="item in hostStrategyOptions" :key="item.value" :value="item.value">
              {{ item.label }}
            </ElRadio>
          </ElRadioGroup>
        </ElFormItem>
        <ElFormItem label="并发数（forks）">
          <ElInputNumber v-model="form.forks" :min="1" :max="100" />
        </ElFormItem>
        <ElFormItem label="串行批次大小">
          <ElInputNumber v-model="form.serial_batch" :min="0" />
        </ElFormItem>
        <ElFormItem label="最大失败百分比">
          <ElInputNumber v-model="form.max_fail_percentage" :min="0" :max="100" />
        </ElFormItem>
        <ElFormItem label="执行超时（秒）">
          <ElInputNumber v-model="form.timeout_seconds" :min="1" :step="60" />
        </ElFormItem>
        <ElFormItem label="排队超时（秒）">
          <ElInputNumber v-model="form.queue_timeout_seconds" :min="1" :step="60" />
        </ElFormItem>
        <ElFormItem label="绕过主机网关">
          <ElSwitch v-model="form.bypass_host_gateway" />
        </ElFormItem>
        <ElFormItem label="是否启用">
          <ElSwitch v-model="form.enabled" />
        </ElFormItem>
        <ElFormItem label="输入变量 JSON">
          <ElInput
            v-model="form.input_vars_text"
            type="textarea"
            :rows="6"
            placeholder='JSON 对象，如 {"key": "value"}'
          />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="editVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="saving" @click="saveEdit">保存</ElButton>
      </template>
    </ElDrawer>
  </div>
</template>
