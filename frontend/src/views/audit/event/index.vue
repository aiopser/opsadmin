<script setup lang="tsx">
import { computed, ref, shallowRef } from 'vue';
import { useClipboard } from '@vueuse/core';
import { fetchGetAuditEventList } from '@/service/api';
import type { AuditEvent, AuditEventSearchParams } from '@/service/api/audit';
import { useAppStore } from '@/store/modules/app';
import { defaultTransform, useUIPaginatedTable } from '@/hooks/common/table';
import { $t } from '@/locales';
import { getAuditActionLabel, getAuditObjectLabel } from './shared';

defineOptions({ name: 'AuditEvent' });

const appStore = useAppStore();
const auditLocale = computed(() => (appStore.locale === 'zh-CN' ? 'zh' : 'en'));

/**
 * 审计领域选项（命名对齐侧边栏模块与审计中心页面，与后端 DomainAuditEvent.Domain 对应）
 * security 领域目前只写入 auth.login.* 登录事件，故显示为「登录日志」
 */
const domainOptions = [
  { value: 'ops', label: '作业系统', tag: 'primary' },
  { value: 'task', label: '任务系统', tag: 'success' },
  { value: 'automation', label: '资源配置', tag: 'warning' },
  { value: 'cmdb', label: '资产管理', tag: 'info' },
  { value: 'monitoring', label: '监控管理', tag: 'info' },
  { value: 'security', label: '登录日志', tag: 'danger' },
  { value: 'system', label: '系统管理', tag: 'info' }
] as const;

const domainRecord = Object.fromEntries(domainOptions.map(item => [item.value, item]));

function getInitSearchParams(): AuditEventSearchParams {
  return {
    current: 1,
    size: 10,
    domain: undefined,
    keywords: undefined
  };
}

const searchParams = ref<AuditEventSearchParams>(getInitSearchParams());

const { columns, columnChecks, data, getData, getDataByPage, loading, mobilePagination } = useUIPaginatedTable({
  paginationProps: {
    currentPage: searchParams.value.current,
    pageSize: searchParams.value.size
  },
  api: () => fetchGetAuditEventList(searchParams.value),
  transform: response => defaultTransform(response),
  onPaginationParamsChange: params => {
    searchParams.value.current = params.currentPage;
    searchParams.value.size = params.pageSize;
  },
  columns: () => [
    { prop: 'index', type: 'index', label: $t('common.index'), width: 64 },
    { prop: 'createdAt', label: $t('page.audit.event.time'), width: 170 },
    {
      prop: 'domain',
      label: $t('page.audit.event.domain'),
      width: 110,
      align: 'center',
      formatter: row => {
        const item = domainRecord[row.domain];

        if (!item) {
          return row.domain;
        }

        return <ElTag type={item.tag}>{item.label}</ElTag>;
      }
    },
    {
      prop: 'actorName',
      label: $t('page.audit.event.actor'),
      width: 120,
      formatter: row => row.actorName || '-'
    },
    {
      prop: 'action',
      label: $t('page.audit.event.operation'),
      minWidth: 160,
      showOverflowTooltip: true,
      formatter: row => getAuditActionLabel(row, auditLocale.value)
    },
    {
      prop: 'resourceType',
      label: $t('page.audit.event.object'),
      minWidth: 220,
      showOverflowTooltip: true,
      formatter: row => getAuditObjectLabel(row, auditLocale.value)
    },
    {
      prop: 'ipAddress',
      label: $t('page.audit.event.ipAddress'),
      width: 130,
      formatter: row => row.ipAddress || '-'
    },
    {
      prop: 'operate',
      label: $t('common.operate'),
      align: 'center',
      width: 90,
      fixed: 'right',
      formatter: row => (
        <ElButton type="primary" plain size="small" onClick={() => showDetail(row)}>
          {$t('common.detail')}
        </ElButton>
      )
    }
  ]
});

/** ============ 详情抽屉 ============ */

const detailVisible = ref(false);
const detailRow = shallowRef<AuditEvent | null>(null);

function showDetail(row: AuditEvent) {
  detailRow.value = row;
  detailVisible.value = true;
}

/** Request ID 复制：主流审计详情都提供，便于排障时关联后端日志 */
const { copy: copyToClipboard, isSupported: clipboardSupported } = useClipboard({ copiedDuring: 1500 });

async function copyRequestId() {
  const requestId = detailRow.value?.requestId;

  if (!requestId) return;

  if (!clipboardSupported.value) {
    window.$message?.warning($t('page.audit.event.copyUnsupported'));
    return;
  }

  await copyToClipboard(requestId);
  window.$notification?.success($t('page.audit.event.copied'));
}

/** 登录失败原因（后端写入 after.reason） */
const failureReason = computed(() => {
  const row = detailRow.value;

  if (!row || row.result !== 'failure') return '';

  const reason = row.after?.reason;

  return typeof reason === 'string' ? reason : '';
});

/** 实际发生变化的字段；登录事件只记录结果原因，不参与数据变更展示 */
const changedKeys = computed<string[]>(() => {
  const row = detailRow.value;

  if (!row || row.resourceType === 'login') return [];

  const keys = new Set([...Object.keys(row.before ?? {}), ...Object.keys(row.after ?? {})]);

  return Array.from(keys).filter(key => isChanged(key));
});

function snapshotValue(key: string, source: 'before' | 'after') {
  const snapshot = detailRow.value?.[source] ?? {};

  return snapshot[key];
}

/** 快照值展示文本：字符串去引号，对象转 JSON，空值统一为占位符 */
function formatSnapshotValue(value: unknown) {
  if (value === undefined || value === null || value === '') return '-';
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);

  return JSON.stringify(value) ?? '-';
}

function snapshotText(key: string, source: 'before' | 'after') {
  return formatSnapshotValue(snapshotValue(key, source));
}

function isMissing(key: string, source: 'before' | 'after') {
  return snapshotText(key, source) === '-';
}

function isChanged(key: string) {
  return snapshotText(key, 'before') !== snapshotText(key, 'after');
}

/** 变更表格行数据：只展示发生变化的字段 */
const diffRows = computed(() => changedKeys.value.map(key => ({ key })));

function resetSearchParams() {
  searchParams.value = getInitSearchParams();
  getDataByPage();
}
</script>

<template>
  <div class="min-h-500px flex-col-stretch gap-16px overflow-hidden lt-sm:overflow-auto">
    <SearchPanel @reset="resetSearchParams" @search="getDataByPage">
      <ElForm :model="searchParams" label-width="80px" @submit.prevent="getDataByPage">
        <ElFormItem :label="$t('page.audit.event.domain')">
          <ElSelect v-model="searchParams.domain" clearable :placeholder="$t('page.audit.event.form.domain')">
            <ElOption v-for="item in domainOptions" :key="item.value" :label="item.label" :value="item.value" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem :label="$t('page.audit.event.keywords')">
          <ElInput v-model="searchParams.keywords" clearable :placeholder="$t('page.audit.event.form.keywords')" />
        </ElFormItem>
      </ElForm>
    </SearchPanel>

    <ElCard class="card-wrapper sm:flex-1-hidden">
      <template #header>
        <div class="flex items-center justify-between">
          <p>{{ $t('page.audit.event.title') }}</p>
          <!-- 审计事件为只读数据，隐藏新增/批量删除按钮 -->
          <TableHeaderOperation
            v-model:columns="columnChecks"
            :loading="loading"
            :show-add="false"
            :show-batch-delete="false"
            @refresh="getData"
          />
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

      <ElDrawer v-model="detailVisible" :title="$t('page.audit.event.detail')" size="min(960px, 100%)">
        <template v-if="detailRow">
          <ElDescriptions class="detail-descriptions" :column="2" border size="small" :label-width="110">
            <ElDescriptionsItem :label="$t('page.audit.event.time')" :span="2">
              <span class="tabular-nums">{{ detailRow.createdAt }}</span>
            </ElDescriptionsItem>
            <ElDescriptionsItem :label="$t('page.audit.event.domain')">
              <ElTag v-if="domainRecord[detailRow.domain]" :type="domainRecord[detailRow.domain].tag">
                {{ domainRecord[detailRow.domain].label }}
              </ElTag>
              <span v-else>{{ detailRow.domain }}</span>
            </ElDescriptionsItem>
            <ElDescriptionsItem :label="$t('page.audit.event.result')">
              <ElTag :type="detailRow.result === 'success' ? 'success' : 'danger'">
                {{ $t(detailRow.result === 'success' ? 'page.audit.event.success' : 'page.audit.event.failure') }}
              </ElTag>
            </ElDescriptionsItem>
            <ElDescriptionsItem :label="$t('page.audit.event.actor')">
              {{ detailRow.actorName || '-' }}
            </ElDescriptionsItem>
            <ElDescriptionsItem :label="$t('page.audit.event.ipAddress')">
              <span class="text-12px font-mono tabular-nums">{{ detailRow.ipAddress || '-' }}</span>
            </ElDescriptionsItem>
            <ElDescriptionsItem :label="$t('page.audit.event.operation')">
              {{ getAuditActionLabel(detailRow, auditLocale) }}
            </ElDescriptionsItem>
            <ElDescriptionsItem :label="$t('page.audit.event.object')">
              {{ getAuditObjectLabel(detailRow, auditLocale) }}
            </ElDescriptionsItem>
            <ElDescriptionsItem v-if="failureReason" :label="$t('page.audit.event.failReason')" :span="2">
              <div class="detail-text-block detail-failure-block">{{ failureReason }}</div>
            </ElDescriptionsItem>
            <ElDescriptionsItem :label="$t('page.audit.event.actionCode')" :span="2">
              <span class="break-all text-12px font-mono">{{ detailRow.action }}</span>
            </ElDescriptionsItem>
            <ElDescriptionsItem :label="$t('page.audit.event.resourceTypeCode')">
              <span class="break-all text-12px font-mono">{{ detailRow.resourceType || '-' }}</span>
            </ElDescriptionsItem>
            <ElDescriptionsItem :label="$t('page.audit.event.resourceId')">
              <span class="break-all text-12px font-mono">{{ detailRow.resourceId || '-' }}</span>
            </ElDescriptionsItem>
            <ElDescriptionsItem label="Request ID" :span="2">
              <div class="flex items-center gap-8px">
                <span class="min-w-0 break-all text-12px font-mono">{{ detailRow.requestId || '-' }}</span>
                <ElButton v-if="detailRow.requestId" class="shrink-0" link size="small" @click="copyRequestId">
                  {{ $t('page.audit.event.copy') }}
                </ElButton>
              </div>
            </ElDescriptionsItem>
          </ElDescriptions>

          <template v-if="diffRows.length">
            <div class="detail-section-header">
              <p class="detail-section-title">{{ $t('page.audit.event.changes') }}</p>
              <span class="detail-section-hint">
                {{ $t('page.audit.event.changedHint', { count: diffRows.length }) }}
              </span>
            </div>
            <ElTable :data="diffRows" border size="small" :max-height="320" class="detail-data-table">
              <ElTableColumn prop="key" :label="$t('page.audit.event.field')" min-width="110">
                <template #default="{ row }">
                  <span class="break-all text-12px font-mono">{{ row.key }}</span>
                </template>
              </ElTableColumn>
              <ElTableColumn :label="$t('page.audit.event.before')" min-width="150">
                <template #default="{ row }">
                  <span
                    class="break-all text-12px font-mono"
                    :class="isMissing(row.key, 'before') ? 'diff-empty' : 'diff-value'"
                  >
                    {{ snapshotText(row.key, 'before') }}
                  </span>
                </template>
              </ElTableColumn>
              <ElTableColumn :label="$t('page.audit.event.after')" min-width="150">
                <template #default="{ row }">
                  <span
                    class="break-all text-12px font-mono"
                    :class="isMissing(row.key, 'after') ? 'diff-empty' : 'diff-value'"
                  >
                    {{ snapshotText(row.key, 'after') }}
                  </span>
                </template>
              </ElTableColumn>
            </ElTable>
          </template>

          <div class="detail-section-header">
            <p class="detail-section-title">{{ $t('page.audit.event.userAgent') }}</p>
          </div>
          <div class="detail-text-block">{{ detailRow.userAgent || '-' }}</div>
        </template>
      </ElDrawer>
    </ElCard>
  </div>
</template>

<style lang="scss" scoped>
/** 详情描述表：去掉标签列灰底，仅靠文字色区分标签与内容，降低表格重量 */
.detail-descriptions {
  :deep(.el-descriptions__label.is-bordered-label) {
    background: transparent;
    color: var(--el-text-color-regular);
    font-weight: 400;
  }
}

/** 详情数据表：全局表格 .cell padding 为 0，恢复内边距并压缩行高 */
.detail-data-table {
  :deep(.el-table__cell .cell) {
    padding: 0 12px;
  }

  :deep(td.el-table__cell) {
    padding: 6px 0;
  }
}

.detail-section-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  margin: 20px 0 8px;
}

.detail-section-title {
  color: var(--el-text-color-primary);
  font-size: 14px;
  font-weight: 500;
  line-height: 1.5;
  text-wrap: balance;
}

.detail-section-hint {
  color: var(--el-text-color-regular);
  font-size: 12px;
  line-height: 1.5;
}

.diff-value {
  color: var(--el-text-color-regular);
}

.diff-empty {
  color: var(--el-text-color-placeholder);
}

.detail-text-block {
  padding: 10px 12px;
  border: 1px solid var(--el-border-color-lighter);
  background: var(--el-fill-color-lighter);
  color: var(--el-text-color-regular);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.6;
  word-break: break-all;
}

/* 失败原因：语义上属于异常信息，用浅红底与普通文本块区分 */
.detail-failure-block {
  border-color: var(--el-color-danger-light-7);
  background: var(--el-color-danger-light-9);
  color: var(--el-text-color-primary);
}
</style>
