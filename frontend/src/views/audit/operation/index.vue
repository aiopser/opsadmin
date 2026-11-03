<script setup lang="tsx">
import { ref } from 'vue';
import { fetchGetLogList } from '@/service/api';
import { defaultTransform, useUIPaginatedTable } from '@/hooks/common/table';
import { $t } from '@/locales';
import LogSearch from './modules/log-search.vue';

defineOptions({ name: 'AuditOperation' });

const searchParams = ref(getInitSearchParams());

function getInitSearchParams(): Api.SystemManage.OperationLogSearchParams {
  return {
    current: 1,
    size: 10,
    keywords: undefined,
    createTime: null
  };
}

const methodTagMap: Record<string, UI.ThemeColor> = {
  get: 'primary',
  post: 'success',
  put: 'warning',
  delete: 'danger'
};

const { columns, columnChecks, data, getData, getDataByPage, loading, mobilePagination } = useUIPaginatedTable({
  paginationProps: {
    currentPage: searchParams.value.current,
    pageSize: searchParams.value.size
  },
  api: () => fetchGetLogList(searchParams.value),
  transform: response => defaultTransform(response),
  onPaginationParamsChange: params => {
    searchParams.value.current = params.currentPage;
    searchParams.value.size = params.pageSize;
  },
  columns: () => [
    { prop: 'index', type: 'index', label: $t('common.index'), width: 64 },
    { prop: 'module', label: $t('page.manage.log.module'), width: 110 },
    { prop: 'title', label: $t('page.manage.log.logTitle'), minWidth: 160 },
    { prop: 'operatorName', label: $t('page.manage.log.operator'), width: 110 },
    {
      prop: 'requestMethod',
      label: $t('page.manage.log.requestMethod'),
      width: 90,
      align: 'center',
      formatter: row => {
        const method = row.requestMethod?.toLowerCase() ?? '';

        return <ElTag type={methodTagMap[method] ?? 'info'}>{row.requestMethod}</ElTag>;
      }
    },
    { prop: 'requestUri', label: $t('page.manage.log.requestUri'), minWidth: 200, showOverflowTooltip: true },
    { prop: 'ip', label: $t('page.manage.log.ip'), width: 130 },
    {
      prop: 'status',
      label: $t('page.manage.log.logStatus'),
      width: 90,
      align: 'center',
      formatter: row => {
        const isSuccess = row.status === '1';

        return <ElTag type={isSuccess ? 'success' : 'danger'}>{isSuccess ? '成功' : '失败'}</ElTag>;
      }
    },
    { prop: 'executionTime', label: $t('page.manage.log.executionTime'), width: 90, align: 'center' },
    { prop: 'createTime', label: $t('page.manage.log.createTime'), width: 170, fixed: 'right' }
  ]
});

function resetSearchParams() {
  searchParams.value = getInitSearchParams();
}
</script>

<template>
  <div class="min-h-500px flex-col-stretch gap-16px overflow-hidden lt-sm:overflow-auto">
    <LogSearch v-model:model="searchParams" @reset="resetSearchParams" @search="getDataByPage" />
    <ElCard class="card-wrapper sm:flex-1-hidden">
      <template #header>
        <div class="flex items-center justify-between">
          <p>{{ $t('page.manage.log.title') }}</p>
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

<style lang="scss" scoped>
:deep(.el-card) {
  .ht50 {
    height: calc(100% - 50px);
  }
}
</style>
