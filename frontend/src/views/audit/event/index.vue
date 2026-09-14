<script setup lang="tsx">
import { computed, ref } from 'vue';
import { fetchGetAuditEventList } from '@/service/api';
import type { AuditEvent, AuditEventSearchParams } from '@/service/api/audit';
import { defaultTransform, useUIPaginatedTable } from '@/hooks/common/table';
import { $t } from '@/locales';

defineOptions({ name: 'AuditEvent' });

/** 审计领域选项（与后端 DomainAuditEvent.Domain 对应） */
const domainOptions = [
  { value: 'ops', label: '运维操作', tag: 'primary' },
  { value: 'task', label: '任务系统', tag: 'success' },
  { value: 'automation', label: '自动化配置', tag: 'warning' },
  { value: 'cmdb', label: '资产管理', tag: 'info' },
  { value: 'security', label: '安全', tag: 'danger' },
  { value: 'system', label: '系统', tag: 'info' }
] as const;

const domainRecord = Object.fromEntries(domainOptions.map(item => [item.value, item]));

function getInitSearchParams(): AuditEventSearchParams {
  return {
    current: 1,
    size: 10,
    domain: undefined,
    action: undefined,
    resourceType: undefined,
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
    { prop: 'action', label: $t('page.audit.event.action'), minWidth: 170, showOverflowTooltip: true },
    {
      prop: 'resourceType',
      label: $t('page.audit.event.resourceType'),
      width: 120,
      formatter: row => row.resourceType || '-'
    },
    {
      prop: 'resourceId',
      label: $t('page.audit.event.resourceId'),
      width: 100,
      formatter: row => row.resourceId || '-'
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
const detailRow = ref<AuditEvent | null>(null);

function showDetail(row: AuditEvent) {
  detailRow.value = row;
  detailVisible.value = true;
}

/** before/after 快照的并集键（用于变更对比展示） */
const diffKeys = computed<string[]>(() => {
  const row = detailRow.value;

  if (!row) return [];

  return Array.from(new Set([...Object.keys(row.before ?? {}), ...Object.keys(row.after ?? {})]));
});

function diffValue(key: string, source: 'before' | 'after') {
  const snapshot = detailRow.value?.[source] ?? {};
  const value = snapshot[key];

  return value === undefined ? '-' : JSON.stringify(value);
}

function isChanged(key: string) {
  return diffValue(key, 'before') !== diffValue(key, 'after');
}

function resetSearchParams() {
  searchParams.value = getInitSearchParams();
  getDataByPage();
}
</script>

<template>
  <div class="min-h-500px flex-col-stretch gap-16px overflow-hidden lt-sm:overflow-auto">
    <ElCard class="card-wrapper">
      <ElForm :model="searchParams" label-width="80px" inline>
        <ElFormItem :label="$t('page.audit.event.domain')">
          <ElSelect v-model="searchParams.domain" clearable :placeholder="$t('page.audit.event.form.domain')">
            <ElOption v-for="item in domainOptions" :key="item.value" :label="item.label" :value="item.value" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem :label="$t('page.audit.event.action')">
          <ElInput v-model="searchParams.action" clearable :placeholder="$t('page.audit.event.form.action')" />
        </ElFormItem>
        <ElFormItem :label="$t('page.audit.event.resourceType')">
          <ElInput
            v-model="searchParams.resourceType"
            clearable
            :placeholder="$t('page.audit.event.form.resourceType')"
          />
        </ElFormItem>
        <ElFormItem :label="$t('page.audit.event.keywords')">
          <ElInput
            v-model="searchParams.keywords"
            clearable
            :placeholder="$t('page.audit.event.form.keywords')"
            @keyup.enter="getDataByPage()"
          />
        </ElFormItem>
        <ElFormItem>
          <ElButton type="primary" @click="getDataByPage()">
            {{ $t('common.search') }}
          </ElButton>
          <ElButton @click="resetSearchParams">
            {{ $t('common.reset') }}
          </ElButton>
        </ElFormItem>
      </ElForm>
    </ElCard>

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

      <ElDrawer v-model="detailVisible" :title="$t('page.audit.event.detail')" size="560px">
        <template v-if="detailRow">
          <ElDescriptions :column="2" border size="small">
            <ElDescriptionsItem :label="$t('page.audit.event.time')" :span="2">
              {{ detailRow.createdAt }}
            </ElDescriptionsItem>
            <ElDescriptionsItem :label="$t('page.audit.event.domain')">
              <ElTag v-if="domainRecord[detailRow.domain]" :type="domainRecord[detailRow.domain].tag">
                {{ domainRecord[detailRow.domain].label }}
              </ElTag>
              <span v-else>{{ detailRow.domain }}</span>
            </ElDescriptionsItem>
            <ElDescriptionsItem :label="$t('page.audit.event.actor')">
              {{ detailRow.actorName || '-' }}
            </ElDescriptionsItem>
            <ElDescriptionsItem :label="$t('page.audit.event.action')" :span="2">
              {{ detailRow.action }}
            </ElDescriptionsItem>
            <ElDescriptionsItem :label="$t('page.audit.event.resourceType')">
              {{ detailRow.resourceType || '-' }}
            </ElDescriptionsItem>
            <ElDescriptionsItem :label="$t('page.audit.event.resourceId')">
              {{ detailRow.resourceId || '-' }}
            </ElDescriptionsItem>
            <ElDescriptionsItem :label="$t('page.audit.event.ipAddress')">
              {{ detailRow.ipAddress || '-' }}
            </ElDescriptionsItem>
            <ElDescriptionsItem label="Request ID">
              {{ detailRow.requestId || '-' }}
            </ElDescriptionsItem>
          </ElDescriptions>

          <p class="mb-8px mt-16px font-bold">{{ $t('page.audit.event.changes') }}</p>
          <ElEmpty v-if="!diffKeys.length" :description="$t('page.audit.event.noChanges')" :image-size="60" />
          <ElTable
            v-else
            :data="diffKeys.map(key => ({ key }))"
            border
            size="small"
            :row-class-name="({ row }) => (isChanged(row.key) ? 'audit-changed-row' : '')"
          >
            <ElTableColumn prop="key" :label="$t('page.audit.event.field')" min-width="120" show-overflow-tooltip />
            <ElTableColumn :label="$t('page.audit.event.before')" min-width="140">
              <template #default="{ row }">
                <span class="break-all text-12px font-mono">{{ diffValue(row.key, 'before') }}</span>
              </template>
            </ElTableColumn>
            <ElTableColumn :label="$t('page.audit.event.after')" min-width="140">
              <template #default="{ row }">
                <span class="break-all text-12px font-mono">{{ diffValue(row.key, 'after') }}</span>
              </template>
            </ElTableColumn>
          </ElTable>

          <p class="mb-8px mt-16px font-bold">User Agent</p>
          <p class="break-all text-12px text-gray-500 font-mono">{{ detailRow.userAgent || '-' }}</p>
        </template>
      </ElDrawer>
    </ElCard>
  </div>
</template>

<style lang="scss" scoped>
:deep(.audit-changed-row) {
  background-color: var(--el-color-warning-light-9);
}
</style>
