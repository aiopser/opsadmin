<script setup lang="tsx">
import { ref } from 'vue';
import { fetchGetLoginEventList } from '@/service/api/audit';
import type { LoginEventSearchParams } from '@/service/api/audit';
import { defaultTransform, useUIPaginatedTable } from '@/hooks/common/table';
import { $t } from '@/locales';

defineOptions({ name: 'AuditLogin' });

function getInitSearchParams(): LoginEventSearchParams {
  return { current: 1, size: 10, username: undefined, result: undefined, ipAddress: undefined, dateRange: null };
}

const searchParams = ref<LoginEventSearchParams>(getInitSearchParams());

const { columns, columnChecks, data, getData, getDataByPage, loading, mobilePagination } = useUIPaginatedTable({
  paginationProps: { currentPage: searchParams.value.current, pageSize: searchParams.value.size },
  api: () => fetchGetLoginEventList(searchParams.value),
  transform: response => defaultTransform(response),
  onPaginationParamsChange: params => {
    searchParams.value.current = params.currentPage ?? 1;
    searchParams.value.size = params.pageSize ?? 10;
  },
  columns: () => [
    { prop: 'index', type: 'index', label: $t('common.index'), width: 64 },
    { prop: 'createdAt', label: $t('page.audit.login.time'), width: 180 },
    { prop: 'username', label: $t('page.audit.login.username'), minWidth: 150, showOverflowTooltip: true },
    {
      prop: 'result',
      label: $t('page.audit.login.result'),
      width: 110,
      align: 'center',
      formatter: row => (
        <ElTag type={row.result === 'success' ? 'success' : 'danger'}>
          {$t(row.result === 'success' ? 'page.audit.login.success' : 'page.audit.login.failure')}
        </ElTag>
      )
    },
    {
      prop: 'reason',
      label: $t('page.audit.login.reason'),
      minWidth: 150,
      formatter: row => {
        if (row.result === 'success') return '-';
        if (row.reason === 'invalid_request') return $t('page.audit.login.invalidRequest');
        if (row.reason === 'internal_error') return $t('page.audit.login.internalError');
        return $t('page.audit.login.authFailed');
      }
    },
    { prop: 'ipAddress', label: $t('page.audit.login.ipAddress'), width: 150, formatter: row => row.ipAddress || '-' },
    { prop: 'userAgent', label: $t('page.audit.login.userAgent'), minWidth: 220, showOverflowTooltip: true }
  ]
});

function resetSearchParams() {
  searchParams.value = getInitSearchParams();
  getDataByPage();
}
</script>

<template>
  <div class="min-h-500px flex-col-stretch gap-16px overflow-hidden lt-sm:overflow-auto">
    <SearchPanel @reset="resetSearchParams" @search="getDataByPage">
      <ElForm :model="searchParams" label-width="80px" @submit.prevent="getDataByPage">
        <ElFormItem :label="$t('page.audit.login.username')">
          <ElInput v-model="searchParams.username" clearable :placeholder="$t('page.audit.login.username')" />
        </ElFormItem>
        <ElFormItem :label="$t('page.audit.login.result')">
          <ElSelect v-model="searchParams.result" clearable :placeholder="$t('page.audit.login.result')">
            <ElOption value="success" :label="$t('page.audit.login.success')" />
            <ElOption value="failure" :label="$t('page.audit.login.failure')" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem :label="$t('page.audit.login.ipAddress')">
          <ElInput v-model="searchParams.ipAddress" clearable :placeholder="$t('page.audit.login.ipAddress')" />
        </ElFormItem>
        <ElFormItem :label="$t('page.audit.login.time')">
          <ElDatePicker
            v-model="searchParams.dateRange"
            class="w-full"
            type="daterange"
            value-format="YYYY-MM-DD"
            start-placeholder="YYYY-MM-DD"
            end-placeholder="YYYY-MM-DD"
          />
        </ElFormItem>
      </ElForm>
    </SearchPanel>

    <ElCard class="card-wrapper sm:flex-1-hidden">
      <template #header>
        <div class="flex items-center justify-between">
          <p>{{ $t('page.audit.login.title') }}</p>
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
    </ElCard>
  </div>
</template>
