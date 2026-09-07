<script setup lang="ts">
import { computed, nextTick, ref, shallowRef, watch } from 'vue';
import type { TreeInstance } from 'element-plus';
import { fetchGetRoleMenuIds, updateRoleMenus } from '@/service/api';
import { useMenuStore } from '@/store/modules/menu';
import { $t } from '@/locales';

defineOptions({ name: 'MenuAuthModal' });

interface Props {
  /** the roleId */
  roleId: number;
}

const props = defineProps<Props>();

const visible = defineModel<boolean>('visible', {
  default: false
});

function closeModal() {
  visible.value = false;
}

const title = computed(() => $t('common.edit') + $t('page.manage.role.menuAuth'));

const home = shallowRef('');

const menuStore = useMenuStore();

const pageSelectOptions = computed(() => {
  const opts: CommonType.Option[] = menuStore.allPages.map(page => ({
    label: page,
    value: page
  }));

  return opts;
});

const treeRef = shallowRef<TreeInstance>();

/** 弹窗初始化中（树缓存命中时几乎瞬时，首次打开时展示 loading 避免短暂空白） */
const initLoading = ref(false);

/** 角色已分配的按钮权限（当前弹窗无按钮勾选 UI，提交时原样回传避免被清空） */
const buttonIds = shallowRef<string[]>([]);

/** 收集树中所有叶子节点 ID（回显时只勾选叶子，父节点勾选态由级联自动计算） */
function collectLeafIds(nodes: Api.SystemManage.MenuTree[], acc: Set<number> = new Set()): Set<number> {
  nodes.forEach(node => {
    if (node.children?.length) {
      collectLeafIds(node.children, acc);
    } else {
      acc.add(node.id);
    }
  });

  return acc;
}

/** 获取角色已分配的菜单/按钮权限并回显 */
async function getRoleAuth() {
  const { error, data } = await fetchGetRoleMenuIds(props.roleId);

  if (!error && data) {
    home.value = data.homePath ?? '';
    buttonIds.value = data.buttonIds ?? [];

    const leafIds = collectLeafIds(menuStore.menuTree);
    const checkedLeafIds = (data.menuIds ?? []).map(Number).filter(id => leafIds.has(id));

    await nextTick();
    treeRef.value?.setCheckedKeys(checkedLeafIds);
  }
}

async function handleSubmit() {
  const checkedKeys = (treeRef.value?.getCheckedKeys(false) ?? []).map(Number);
  const halfCheckedKeys = (treeRef.value?.getHalfCheckedKeys() ?? []).map(Number);
  const menuIds = [...halfCheckedKeys, ...checkedKeys];

  const { error } = await updateRoleMenus(props.roleId, {
    menuIds,
    buttonIds: buttonIds.value,
    homePath: home.value
  });

  if (!error) {
    window.$message?.success?.($t('common.modifySuccess'));

    closeModal();
  }
}

async function init() {
  initLoading.value = true;

  await Promise.all([menuStore.getAllPages(), menuStore.getMenuTree()]);
  await getRoleAuth();

  initLoading.value = false;
}

watch(visible, val => {
  if (val) {
    init();
  }
});
</script>

<template>
  <ElDialog v-model="visible" :title="title" preset="card" class="w-480px">
    <div class="flex-y-center gap-16px pb-12px">
      <div>{{ $t('page.manage.menu.home') }}</div>
      <ElSelect v-model="home" :options="pageSelectOptions" size="small" class="w-160px">
        <ElOption v-for="{ value, label } in pageSelectOptions" :key="value" :value="value" :label="label"></ElOption>
      </ElSelect>
    </div>
    <ElTree
      ref="treeRef"
      v-loading="initLoading"
      :data="menuStore.menuTree"
      node-key="id"
      show-checkbox
      class="h-280px overflow-y-auto"
    />
    <template #footer>
      <ElSpace class="w-full justify-end">
        <ElButton size="small" class="mt-16px" @click="closeModal">
          {{ $t('common.cancel') }}
        </ElButton>
        <ElButton type="primary" size="small" class="mt-16px" @click="handleSubmit">
          {{ $t('common.confirm') }}
        </ElButton>
      </ElSpace>
    </template>
  </ElDialog>
</template>

<style scoped></style>
