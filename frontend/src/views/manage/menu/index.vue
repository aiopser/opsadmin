<script setup lang="tsx">
import { ref } from 'vue';
import type { Ref } from 'vue';
import { useBoolean } from '@sa/hooks';
import { yesOrNoRecord } from '@/constants/common';
import { enableStatusRecord, menuTypeRecord } from '@/constants/business';
import { deleteMenu, fetchGetAllPages, fetchGetMenuTableTree } from '@/service/api';
import { useMenuStore } from '@/store/modules/menu';
import { defaultTransform, useTableOperate, useUIPaginatedTable } from '@/hooks/common/table';
import { $t } from '@/locales';
import SvgIcon from '@/components/custom/svg-icon.vue';
import MenuOperateModal, { type OperateType } from './modules/menu-operate-modal.vue';

const { bool: visible, setTrue: openModal } = useBoolean();

const wrapperRef = ref<HTMLElement | null>(null);

const { columns, columnChecks, data, loading, getData } = useUIPaginatedTable({
  api: () => fetchGetMenuTableTree(),
  transform: response => defaultTransform(response),
  columns: () => [
    { prop: 'selection', type: 'selection', width: 48 },
    { prop: 'id', label: $t('page.manage.menu.id') },
    {
      prop: 'menuType',
      label: $t('page.manage.menu.menuType'),
      width: 90,
      formatter: row => {
        const tagMap: Record<Api.SystemManage.MenuType, UI.ThemeColor> = {
          1: 'info',
          2: 'primary'
        };

        const label = $t(menuTypeRecord[row.menuType]);

        return <ElTag type={tagMap[row.menuType]}>{label}</ElTag>;
      }
    },
    {
      prop: 'menuName',
      label: $t('page.manage.menu.menuName'),
      minWidth: 120,
      formatter: row => {
        const { i18nKey, menuName } = row;

        const label = i18nKey ? $t(i18nKey) : menuName;

        return <span>{label}</span>;
      }
    },
    {
      prop: 'icon',
      label: $t('page.manage.menu.icon'),
      width: 100,
      formatter: row => {
        const icon = row.iconType === '1' ? row.icon : undefined;

        const localIcon = row.iconType === '2' ? row.icon : undefined;

        return (
          <div class="flex-center">
            <SvgIcon icon={icon} localIcon={localIcon} class="text-icon" />
          </div>
        );
      }
    },
    { prop: 'routeName', label: $t('page.manage.menu.routeName'), minWidth: 120 },
    { prop: 'routePath', label: $t('page.manage.menu.routePath'), minWidth: 120 },
    {
      prop: 'status',
      label: $t('page.manage.menu.menuStatus'),
      width: 80,
      formatter: row => {
        if (row.status === undefined) {
          return '';
        }

        const tagMap: Record<Api.Common.EnableStatus, UI.ThemeColor> = {
          1: 'success',
          2: 'warning'
        };

        const label = $t(enableStatusRecord[row.status]);

        return <ElTag type={tagMap[row.status]}>{label}</ElTag>;
      }
    },
    {
      prop: 'hideInMenu',
      label: $t('page.manage.menu.hideInMenu'),
      width: 80,
      formatter: row => {
        const hide: CommonType.YesOrNo = row.hideInMenu ? 'Y' : 'N';

        const tagMap: Record<CommonType.YesOrNo, UI.ThemeColor> = {
          Y: 'danger',
          N: 'info'
        };

        const label = $t(yesOrNoRecord[hide]);

        return <ElTag type={tagMap[hide]}>{label}</ElTag>;
      }
    },
    { prop: 'order', label: $t('page.manage.menu.order'), width: 60 },
    {
      prop: 'operate',
      label: $t('common.operate'),
      width: 270,
      formatter: row => (
        <div class="flex-center justify-end pr-10px">
          {row.menuType === '1' && (
            <ElButton type="primary" plain size="small" onClick={() => handleAddChildMenu(row)}>
              {$t('page.manage.menu.addChildMenu')}
            </ElButton>
          )}
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
  ]
});

const { checkedRowKeys, onBatchDeleted, onDeleted } = useTableOperate(data, 'id', getData);

const operateType = ref<OperateType>('add');

function handleAdd() {
  operateType.value = 'add';
  openModal();
}

async function handleBatchDelete() {
  const results = await Promise.all(checkedRowKeys.value.map(id => deleteMenu(Number(id))));

  if (results.every(result => !result.error)) {
    useMenuStore().invalidate();
    onBatchDeleted();
  }
}

async function handleDelete(id: number) {
  const { error } = await deleteMenu(id);

  if (!error) {
    useMenuStore().invalidate();
    onDeleted();
  }
}

/** the edit menu data or the parent menu data when adding a child menu */
const editingData: Ref<Api.SystemManage.Menu | null> = ref(null);

function handleEdit(item: Api.SystemManage.Menu) {
  operateType.value = 'edit';
  editingData.value = { ...item };

  openModal();
}

function handleAddChildMenu(item: Api.SystemManage.Menu) {
  operateType.value = 'addChild';

  editingData.value = { ...item };

  openModal();
}

const allPages = ref<string[]>([]);

async function getAllPages() {
  const { data: pages } = await fetchGetAllPages();
  allPages.value = pages || [];
}

function init() {
  getAllPages();
}

// init
init();
</script>

<template>
  <div ref="wrapperRef" class="flex-col-stretch gap-16px overflow-hidden lt-sm:overflow-auto">
    <ElCard class="card-wrapper sm:flex-1-hidden">
      <template #header>
        <div class="flex items-center justify-between">
          <p>{{ $t('page.manage.menu.title') }}</p>
          <TableHeaderOperation
            v-model:columns="columnChecks"
            :disabled-delete="checkedRowKeys.length === 0"
            :loading="loading"
            @add="handleAdd"
            @delete="handleBatchDelete"
            @refresh="getData"
          />
        </div>
      </template>
      <div class="h-full">
        <ElTable
          v-loading="loading"
          height="100%"
          border
          row-key="id"
          :data="data"
          :tree-props="{ children: 'children' }"
          @selection-change="checkedRowKeys = ($event as Array<{ id: number }>).map(row => String(row.id))"
        >
          <ElTableColumn v-for="col in columns" :key="col.prop" v-bind="col" />
        </ElTable>
      </div>
      <MenuOperateModal
        v-model:visible="visible"
        :operate-type="operateType"
        :row-data="editingData"
        :all-pages="allPages"
        @submitted="getData"
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
