<script setup lang="tsx">
import { onScopeDispose, ref, watch } from 'vue';
import { fetchGetSyncRecordList } from '@/service/api';
import { defaultTransform, useUIPaginatedTable } from '@/hooks/common/table';

defineOptions({ name: 'CmdbSyncRecordDrawer' });
const emit = defineEmits<{ (event: 'updated', sourceId?: number): void }>();

/** ============ 枚举文案 ============ */

const statusOptions = [
  { value: 'queued', label: '待执行' },
  { value: 'running', label: '同步中' },
  { value: 'succeeded', label: '成功' },
  { value: 'partial', label: '部分成功' },
  { value: 'failed', label: '失败' }
];
const statusText: Record<string, string> = Object.fromEntries(statusOptions.map(item => [item.value, item.label]));

const statusTagType: Record<string, UI.ThemeColor> = {
  queued: 'info',
  running: 'warning',
  succeeded: 'success',
  partial: 'warning',
  failed: 'danger'
};

/** 耗时：结束时间 - 开始时间；未完成或无法解析时显示 - */
function formatDuration(row: Api.Cmdb.AssetSyncRecordRecord): string {
  if (!row.started_at || !row.finished_at) return '-';
  const start = new Date(row.started_at.replace(' ', 'T')).getTime();
  const end = new Date(row.finished_at.replace(' ', 'T')).getTime();
  if (Number.isNaN(start) || Number.isNaN(end) || end < start) return '-';
  const seconds = (end - start) / 1000;
  if (seconds < 0.1) return '<0.1 秒';
  if (seconds < 60) return `${seconds.toFixed(1)} 秒`;
  const roundedSeconds = Math.round(seconds);
  return `${Math.floor(roundedSeconds / 60)} 分 ${roundedSeconds % 60} 秒`;
}

/** ============ 抽屉与筛选 ============ */

const visible = ref(false);
const title = ref('同步记录');

const searchParams = ref({
  current: 1,
  size: 10,
  search: undefined as string | undefined,
  source: undefined as number | undefined,
  status: undefined as Api.Cmdb.AssetSyncStatus | undefined
});

/** ============ 列表（只读） ============ */

const { columns, data, getData, getDataByPage, loading, mobilePagination } = useUIPaginatedTable({
  paginationProps: {
    currentPage: searchParams.value.current,
    pageSize: searchParams.value.size
  },
  api: () => fetchGetSyncRecordList(searchParams.value),
  transform: response => defaultTransform(response),
  onPaginationParamsChange: params => {
    searchParams.value.current = params.currentPage ?? 1;
    searchParams.value.size = params.pageSize ?? 10;
  },
  columns: () => [
    { prop: 'sourceName', label: '资产来源', width: 130, showOverflowTooltip: true },
    {
      prop: 'trigger',
      label: '触发方式',
      width: 95,
      formatter: row => (row.trigger === 'scheduled' ? '周期触发' : '手动同步')
    },
    {
      prop: 'status',
      label: '状态',
      width: 90,
      align: 'center',
      formatter: row => <ElTag type={statusTagType[row.status] ?? 'info'}>{statusText[row.status] ?? row.status}</ElTag>
    },
    {
      prop: 'duration',
      label: '耗时',
      width: 110,
      align: 'center',
      className: 'tabular-nums',
      formatter: row => <span>{formatDuration(row)}</span>
    },
    { prop: 'total_count', label: '总数', width: 70, align: 'center', className: 'tabular-nums' },
    { prop: 'created_count', label: '新增', width: 70, align: 'center', className: 'tabular-nums' },
    { prop: 'updated_count', label: '更新', width: 70, align: 'center', className: 'tabular-nums' },
    { prop: 'skipped_count', label: '跳过', width: 70, align: 'center', className: 'tabular-nums' },
    { prop: 'started_at', label: '开始时间', width: 170, formatter: row => row.started_at || '-' },
    {
      prop: 'error_message',
      label: '错误信息',
      minWidth: 160,
      showOverflowTooltip: true,
      formatter: row => row.error_message || '-'
    }
  ]
});

let pollTimer: ReturnType<typeof setTimeout> | undefined;
let pendingIds = new Set<number>();

function stopPolling() {
  if (pollTimer) clearTimeout(pollTimer);
  pollTimer = undefined;
}

function schedulePolling() {
  stopPolling();
  if (!visible.value) return;
  const pending = data.value.filter(row => row.status === 'queued' || row.status === 'running');
  const completed = data.value.some(
    row => pendingIds.has(row.id) && row.status !== 'queued' && row.status !== 'running'
  );
  if (completed) emit('updated', searchParams.value.source);
  pendingIds = new Set(pending.map(row => row.id));
  if (pending.length) pollTimer = setTimeout(refreshCurrentPage, 3000);
}

async function refreshCurrentPage() {
  if (loading.value) {
    if (visible.value) pollTimer = setTimeout(refreshCurrentPage, 3000);
    return;
  }
  await getData();
  schedulePolling();
}

function resetFilter() {
  searchParams.value.search = undefined;
  searchParams.value.status = undefined;
  getDataByPage();
}

function formatScope(row: Api.Cmdb.AssetSyncRecordRecord): string {
  const scope = row.collection_scope;
  if (!scope) return '历史记录未保存范围';
  const regions = scope.regions?.join('、') || '账号可见范围';
  return scope.selectedCount === undefined
    ? regions
    : `${regions}；读取 ${scope.readCount ?? row.total_count} 台，选中 ${scope.selectedCount} 台`;
}

function formatChanges(fields: NonNullable<Api.Cmdb.AssetSyncRecordRecord['changes']>[number]['fields']): string {
  return fields
    .map(field => `${field.label}：${formatChangeValue(field.before)} → ${formatChangeValue(field.after)}`)
    .join('；');
}

function formatChangeValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—';
  return typeof value === 'object' ? JSON.stringify(value) : String(value);
}

/** 打开抽屉：传入账号则按该账号过滤，不传则展示全部 */
function open(sourceId?: number, sourceName?: string) {
  title.value = sourceName ? `同步记录：${sourceName}` : '同步记录';
  pendingIds = new Set();
  searchParams.value = {
    current: 1,
    size: 10,
    search: undefined,
    source: sourceId,
    status: undefined
  };
  visible.value = true;
  getDataByPage();
}

watch([visible, data], schedulePolling);
onScopeDispose(stopPolling);

defineExpose({ open });
</script>

<template>
  <ElDrawer v-model="visible" :title="title" size="min(1080px, 100vw)">
    <div class="flex-col-stretch gap-12px">
      <ElForm :model="searchParams" class="flex flex-wrap items-center gap-x-24px gap-y-12px" @submit.prevent>
        <ElFormItem label="状态" class="!mb-0">
          <ElSelect v-model="searchParams.status" clearable placeholder="全部" class="w-120px">
            <ElOption v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="关键词" class="!mb-0">
          <ElInput
            v-model="searchParams.search"
            clearable
            placeholder="任务 ID/错误信息"
            class="w-200px"
            @keyup.enter="getDataByPage()"
            @clear="getDataByPage()"
          />
        </ElFormItem>
        <ElFormItem class="!mb-0">
          <ElButton type="primary" @click="getDataByPage()">查询</ElButton>
          <ElButton @click="resetFilter">重置</ElButton>
          <ElButton :loading="loading" @click="refreshCurrentPage">刷新</ElButton>
        </ElFormItem>
      </ElForm>

      <ElTable v-loading="loading" border :data="data" row-key="id" max-height="480" class="w-full">
        <ElTableColumn type="expand" width="40">
          <template #default="{ row }">
            <div class="flex flex-col gap-12px p-16px">
              <ElDescriptions :column="1" border size="small">
                <ElDescriptionsItem label="采集范围">{{ formatScope(row) }}</ElDescriptionsItem>
                <ElDescriptionsItem label="采集时间">{{ row.observed_at || '历史记录未保存' }}</ElDescriptionsItem>
                <ElDescriptionsItem label="范围读取">
                  {{
                    row.collection_scope?.complete ? '配置范围已读取完成' : '未完成或历史记录未保存'
                  }}；不代表整个云账号的全部资产
                </ElDescriptionsItem>
              </ElDescriptions>
              <ElTable v-if="row.changes?.length" :data="row.changes" border size="small">
                <ElTableColumn prop="hostname" label="主机" min-width="140" align="center" show-overflow-tooltip />
                <ElTableColumn prop="sourceId" label="实例 ID" min-width="150" align="center" show-overflow-tooltip />
                <ElTableColumn label="变化" min-width="240" align="center">
                  <template #default="{ row: change }">
                    {{ change.action === 'create' ? '新增资产' : formatChanges(change.fields) }}
                  </template>
                </ElTableColumn>
              </ElTable>
              <span v-else class="text-regular text-sm">本次没有资产字段变化或历史记录未保存明细。</span>
            </div>
          </template>
        </ElTableColumn>
        <ElTableColumn v-for="col in columns" :key="col.prop" v-bind="col" align="center" header-align="center" />
      </ElTable>

      <div class="flex justify-end">
        <ElPagination
          v-if="mobilePagination.total"
          layout="total,prev,pager,next,sizes"
          v-bind="mobilePagination"
          @current-change="mobilePagination['current-change']"
          @size-change="mobilePagination['size-change']"
        />
      </div>
    </div>
  </ElDrawer>
</template>
