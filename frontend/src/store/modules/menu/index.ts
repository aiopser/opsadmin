import { shallowRef } from 'vue';
import { defineStore } from 'pinia';
import { fetchGetAllMenus, fetchGetAllPages, fetchGetMenuTree } from '@/service/api';
import { SetupStoreId } from '@/enum';

/**
 * 菜单共享数据缓存
 *
 * 菜单树 / 页面列表 / 菜单+按钮列表属于所有角色共用的参照数据，
 * 角色授权弹窗每次打开都重复拉取会造成不必要的请求与短暂空白，
 * 这里做会话级缓存：首次加载后复用，菜单管理发生变更时通过 invalidate 失效。
 *
 * 角色已分配的 menuIds/buttonIds 属于角色私有数据，不做缓存，每次打开弹窗实时查询。
 */
export const useMenuStore = defineStore(SetupStoreId.Menu, () => {
  /** 菜单勾选树（菜单权限弹窗） */
  const menuTree = shallowRef<Api.SystemManage.MenuTree[]>([]);

  /** 页面组件名列表（首页路径下拉） */
  const allPages = shallowRef<string[]>([]);

  /** 菜单列表（含按钮定义，按钮权限弹窗） */
  const allMenus = shallowRef<Api.SystemManage.Menu[]>([]);

  async function getMenuTree() {
    if (menuTree.value.length) {
      return;
    }

    const { error, data } = await fetchGetMenuTree();

    if (!error) {
      menuTree.value = data;
    }
  }

  async function getAllPages() {
    if (allPages.value.length) {
      return;
    }

    const { error, data } = await fetchGetAllPages();

    if (!error) {
      allPages.value = data;
    }
  }

  async function getAllMenus() {
    if (allMenus.value.length) {
      return;
    }

    const { error, data } = await fetchGetAllMenus();

    if (!error) {
      allMenus.value = data;
    }
  }

  /** 菜单数据发生变更（新增/编辑/删除）后调用，下次访问将重新拉取 */
  function invalidate() {
    menuTree.value = [];
    allPages.value = [];
    allMenus.value = [];
  }

  return {
    menuTree,
    allPages,
    allMenus,
    getMenuTree,
    getAllPages,
    getAllMenus,
    invalidate
  };
});
