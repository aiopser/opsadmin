<script setup lang="ts">
import { computed, nextTick, ref, shallowRef, watch } from 'vue';
import type { TreeInstance } from 'element-plus';
import { fetchGetRoleMenuIds, updateRoleMenus } from '@/service/api';
import { useMenuStore } from '@/store/modules/menu';
import { $t } from '@/locales';

defineOptions({ name: 'ButtonAuthModal' });

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

const title = computed(() => $t('common.edit') + $t('page.manage.role.buttonAuth'));

/** 菜单→按钮树节点（key 加前缀避免菜单/按钮数字 id 冲突） */
interface ButtonTreeNode {
  id: string;
  label: string;
  children?: ButtonTreeNode[];
}

const menuStore = useMenuStore();

/** 树数据从缓存的菜单列表实时派生（缓存失效后自动重建） */
const tree = computed<ButtonTreeNode[]>(() =>
  menuStore.allMenus
    .filter(menu => (menu.buttons ?? []).length > 0)
    .map(menu => ({
      id: `m-${menu.id}`,
      label: menu.menuName,
      children: (menu.buttons ?? [])
        .filter(button => button.id !== undefined)
        .map(button => ({
          id: `b-${button.id}`,
          label: button.desc || button.code
        }))
    }))
);

const treeRef = shallowRef<TreeInstance>();

/** 弹窗初始化中（缓存命中时几乎瞬时，首次打开时展示 loading 避免短暂空白） */
const initLoading = ref(false);

/** 角色已有的菜单权限与默认首页（提交时原样回传，避免被清空） */
const menuIds = shallowRef<string[]>([]);
const homePath = shallowRef<string | null>(null);

async function getRoleAuth() {
  const { error, data } = await fetchGetRoleMenuIds(props.roleId);

  if (!error && data) {
    menuIds.value = data.menuIds ?? [];
    homePath.value = data.homePath ?? null;

    const checkedButtonKeys = (data.buttonIds ?? []).map(id => `b-${id}`);

    await nextTick();
    treeRef.value?.setCheckedKeys(checkedButtonKeys);
  }
}

async function handleSubmit() {
  const buttonIds = (treeRef.value?.getCheckedKeys(false) ?? [])
    .map(key => String(key))
    .filter(key => key.startsWith('b-'))
    .map(key => key.slice(2));

  const { error } = await updateRoleMenus(props.roleId, {
    menuIds: menuIds.value,
    buttonIds,
    homePath: homePath.value ?? undefined
  });

  if (!error) {
    window.$message?.success?.($t('common.modifySuccess'));

    closeModal();
  }
}

async function init() {
  initLoading.value = true;

  await menuStore.getAllMenus();
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
    <ElTree
      ref="treeRef"
      v-loading="initLoading"
      :data="tree"
      node-key="id"
      show-checkbox
      class="h-280px overflow-y-auto"
    />
    <template #footer>
      <ElSpace class="w-full justify-end">
        <ElButton size="small" class="mt-16px" @click="closeModal">{{ $t('common.cancel') }}</ElButton>
        <ElButton type="primary" size="small" class="mt-16px" @click="handleSubmit">
          {{ $t('common.confirm') }}
        </ElButton>
      </ElSpace>
    </template>
  </ElDialog>
</template>

<style scoped></style>
