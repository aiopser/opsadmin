<script setup lang="tsx">
import { ref } from 'vue';
import { enableStatusRecord } from '@/constants/business';
import { batchDeleteDept, deleteDept, fetchGetDeptList } from '@/service/api';
import { useTableOperate } from '@/hooks/common/table';
import { $t } from '@/locales';
import DeptOperateDrawer from './modules/dept-operate-drawer.vue';
import DeptSearch from './modules/dept-search.vue';

defineOptions({ name: 'DeptManage' });

const searchParams = ref<Api.SystemManage.DepartmentSearchParams>(getInitSearchParams());

function getInitSearchParams(): Api.SystemManage.DepartmentSearchParams {
  return {
    deptName: undefined,
    status: undefined
  };
}

/** 部门为树形列表（后端不分页） */
const data = ref<Api.SystemManage.Department[]>([]);
const loading = ref(false);

async function getData() {
  loading.value = true;

  const { error, data: tree } = await fetchGetDeptList(searchParams.value);

  if (!error) {
    data.value = tree;
  }

  loading.value = false;
}

const { operateType, editingData, checkedRowKeys, onBatchDeleted, onDeleted } = useTableOperate(data, 'id', getData);

const operateDrawerVisible = ref(false);

function handleAdd() {
  editingData.value = null;
  operateType.value = 'add';
  operateDrawerVisible.value = true;
}

function handleEdit(row: Api.SystemManage.Department) {
  editingData.value = row;
  operateType.value = 'edit';
  operateDrawerVisible.value = true;
}

const deleteConfirmVisible = ref(false);

async function handleBatchDelete() {
  const ids = checkedRowKeys.value.map(Number);

  const { error } = await batchDeleteDept(ids);

  if (!error) {
    deleteConfirmVisible.value = false;
    onBatchDeleted();
  }
}

async function handleDelete(id: number) {
  const { error } = await deleteDept(id);

  if (!error) {
    onDeleted();
  }
}

function resetSearchParams() {
  searchParams.value = getInitSearchParams();
}

function handleSubmit() {
  getData();
}

getData();

const columns = () => [
  { prop: 'selection', type: 'selection', width: 48 },
  { prop: 'deptName', label: $t('page.manage.dept.deptName'), minWidth: 200 },
  { prop: 'deptCode', label: $t('page.manage.dept.deptCode'), minWidth: 140 },
  { prop: 'sort', label: $t('page.manage.dept.sort'), width: 90, align: 'center' as const },
  {
    prop: 'status',
    label: $t('page.manage.dept.deptStatus'),
    align: 'center' as const,
    width: 110,
    formatter: (row: Api.SystemManage.Department) => {
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
  {
    prop: 'operate',
    label: $t('common.operate'),
    align: 'center' as const,
    width: 140,
    formatter: (row: Api.SystemManage.Department) => (
      <div class="flex-center">
        <ElButton type="primary" plain size="small" onClick={() => handleEdit(row)}>
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
];
</script>

<template>
  <div class="min-h-500px flex-col-stretch gap-16px overflow-hidden lt-sm:overflow-auto">
    <DeptSearch v-model:model="searchParams" @reset="resetSearchParams" @search="getData" />
    <ElCard class="card-wrapper sm:flex-1-hidden">
      <template #header>
        <div class="flex items-center justify-between">
          <p>{{ $t('page.manage.dept.title') }}</p>
          <ElSpace>
            <ElPopconfirm
              v-model:visible="deleteConfirmVisible"
              title="确认删除选中的部门吗？"
              @confirm="handleBatchDelete"
            >
              <template #reference>
                <ElButton type="danger" plain :disabled="checkedRowKeys.length === 0">
                  {{ $t('common.batchDelete') }}
                </ElButton>
              </template>
            </ElPopconfirm>
            <ElButton type="primary" @click="handleAdd">{{ $t('common.add') }}</ElButton>
            <ElButton @click="getData">{{ $t('common.refresh') }}</ElButton>
          </ElSpace>
        </div>
      </template>
      <div class="h-[calc(100%-52px)]">
        <ElTable
          v-loading="loading"
          height="100%"
          border
          row-key="id"
          default-expand-all
          class="sm:h-full"
          :data="data"
          :tree-props="{ children: 'children' }"
          @selection-change="checkedRowKeys = ($event as Array<{ id: number }>).map(row => String(row.id))"
        >
          <ElTableColumn v-for="col in columns()" :key="col.prop" v-bind="col" />
        </ElTable>
      </div>
      <DeptOperateDrawer
        v-model:visible="operateDrawerVisible"
        :operate-type="operateType"
        :row-data="editingData"
        @submitted="handleSubmit"
      />
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
