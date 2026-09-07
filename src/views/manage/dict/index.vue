<script setup lang="tsx">
import { ref } from 'vue';
import { enableStatusRecord } from '@/constants/business';
import { deleteDict, fetchGetDictList } from '@/service/api';
import { defaultTransform, useTableOperate, useUIPaginatedTable } from '@/hooks/common/table';
import { $t } from '@/locales';
import DictOperateDrawer from './modules/dict-operate-drawer.vue';
import DictItemModal from './modules/dict-item-modal.vue';
import DictSearch from './modules/dict-search.vue';

defineOptions({ name: 'DictManage' });

const searchParams = ref(getInitSearchParams());

function getInitSearchParams(): Api.SystemManage.DictTypeSearchParams {
  return {
    current: 1,
    size: 10,
    dictName: undefined,
    status: undefined
  };
}

const { columns, columnChecks, data, getData, getDataByPage, loading, mobilePagination } = useUIPaginatedTable({
  paginationProps: {
    currentPage: searchParams.value.current,
    pageSize: searchParams.value.size
  },
  api: () => fetchGetDictList(searchParams.value),
  transform: response => defaultTransform(response),
  onPaginationParamsChange: params => {
    searchParams.value.current = params.currentPage;
    searchParams.value.size = params.pageSize;
  },
  columns: () => [
    { prop: 'selection', type: 'selection', width: 48 },
    { prop: 'index', type: 'index', label: $t('common.index'), width: 64 },
    { prop: 'dictName', label: $t('page.manage.dict.dictName'), minWidth: 140 },
    { prop: 'dictCode', label: $t('page.manage.dict.dictCode'), minWidth: 140 },
    {
      prop: 'status',
      label: $t('page.manage.dict.dictStatus'),
      width: 100,
      align: 'center',
      formatter: row => {
        if (row.status === undefined) {
          return '';
        }

        const tagMap: Record<Api.Common.EnableStatus, UI.ThemeColor> = {
          1: 'success',
          2: 'warning'
        };

        return <ElTag type={tagMap[row.status]}>{$t(enableStatusRecord[row.status])}</ElTag>;
      }
    },
    { prop: 'remark', label: $t('page.manage.dict.remark'), minWidth: 160 },
    {
      prop: 'operate',
      label: $t('common.operate'),
      align: 'center',
      width: 200,
      fixed: 'right',
      formatter: row => (
        <div class="flex-center">
          <ElButton type="primary" plain size="small" onClick={() => handleShowItems(row)}>
            {$t('page.manage.dict.dictItems')}
          </ElButton>
          <ElButton type="primary" plain size="small" onClick={() => edit(row.id)}>
            {$t('common.edit')}
          </ElButton>
          <ElPopconfirm title={$t('common.confirmDelete')} onConfirm={() => handleDelete(row.id)}>
            {{
              reference: () => (
                <ElButton type="danger" plain size="small">
                  {$t('common.delete')}
                </ElButton>
              )
            }}
          </ElPopconfirm>
        </div>
      )
    }
  ]
});

const { drawerVisible, operateType, editingData, handleAdd, handleEdit, checkedRowKeys, onDeleted } = useTableOperate(
  data,
  'id',
  getData
);

const itemModalVisible = ref(false);

/** 当前查看字典项的字典类型 */
const currentItem = ref<Api.SystemManage.DictType | null>(null);

function handleShowItems(row: Api.SystemManage.DictType) {
  currentItem.value = row;
  itemModalVisible.value = true;
}

async function handleDelete(id: number) {
  const { error } = await deleteDict(id);

  if (!error) {
    onDeleted();
  }
}

function edit(id: number) {
  handleEdit(id);
}

function resetSearchParams() {
  searchParams.value = getInitSearchParams();
}
</script>

<template>
  <div class="min-h-500px flex-col-stretch gap-16px overflow-hidden lt-sm:overflow-auto">
    <DictSearch v-model:model="searchParams" @reset="resetSearchParams" @search="getDataByPage" />
    <ElCard class="card-wrapper sm:flex-1-hidden">
      <template #header>
        <div class="flex items-center justify-between">
          <p>{{ $t('page.manage.dict.title') }}</p>
          <TableHeaderOperation v-model:columns="columnChecks" :loading="loading" @add="handleAdd" @refresh="getData" />
        </div>
      </template>
      <div class="h-[calc(100%-52px)]">
        <ElTable
          v-loading="loading"
          height="100%"
          border
          class="sm:h-full"
          :data="data"
          row-key="id"
          @selection-change="checkedRowKeys = ($event as Array<{ id: number }>).map(row => String(row.id))"
        >
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
      <DictOperateDrawer
        v-model:visible="drawerVisible"
        :operate-type="operateType"
        :row-data="editingData"
        @submitted="getDataByPage"
      />
      <DictItemModal v-model:visible="itemModalVisible" :row-data="currentItem" @submitted="getDataByPage" />
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
