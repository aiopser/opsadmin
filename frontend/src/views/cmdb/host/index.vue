<script setup lang="ts">
import { ref } from 'vue';
import { fetchPatchHost } from '@/service/api';
import AssetSourceTab from './modules/asset-source-tab.vue';
import HostGroupTab from './modules/host-group-tab.vue';
import HostList from './modules/host-list.vue';
import HostTree from './modules/host-tree.vue';
import SyncRecordTab from './modules/sync-record-tab.vue';
import TagTab from './modules/tag-tab.vue';

defineOptions({ name: 'CmdbHost' });

/**
 * 主机资产页：左树右表布局。
 * 左侧为「业务 → 服务树节点」树（带主机计数与节点操作），
 * 右侧为主机列表（搜索 + CRUD + Excel 导入）；
 * 分组/标签/资产来源/同步记录等管理入口收纳进「管理」下拉 + 抽屉。
 */

const hostTreeRef = ref<InstanceType<typeof HostTree>>();
const hostListRef = ref<InstanceType<typeof HostList>>();

/** ============ 左树选中 → 主机查询范围 ============ */

const hostQuery = ref<Api.Cmdb.HostListQuery>({ business: null, serviceNodeIds: null });

function handleTreeSelect(payload: Api.Cmdb.HostTreeSelectPayload) {
  hostQuery.value = { business: payload.business, serviceNodeIds: payload.serviceNodeIds };
}

/** 左树「添加主机到节点」：打开新增主机抽屉并预填服务树节点 */
function handleAddHost(node: Api.Cmdb.HostTreeRow) {
  hostListRef.value?.openAddDrawer(node.id);
}

/** 主机增删改/导入后刷新左树主机计数 */
function handleHostsChanged() {
  hostTreeRef.value?.refresh();
}

/** ============ 移动主机到节点 ============ */

async function handleMoveHosts(node: Api.Cmdb.HostTreeRow) {
  if (node.type !== 'node') return;

  const rows = hostListRef.value?.getSelectedRows() ?? [];
  if (!rows.length) {
    window.$message?.warning('请先在右侧表格勾选需要移动的主机');
    return;
  }
  try {
    await ElMessageBox.confirm(`确认将选中的 ${rows.length} 台主机移动到节点「${node.name}」？`, '移动主机', {
      type: 'warning'
    });
  } catch {
    return;
  }

  const results = await Promise.all(rows.map(row => fetchPatchHost(row.id, { service_node: node.id })));
  const failedCount = results.filter(result => result.error).length;
  if (failedCount) {
    window.$message?.warning(`移动完成：${rows.length - failedCount} 台成功，${failedCount} 台失败`);
  } else {
    window.$message?.success(`已将 ${rows.length} 台主机移动到「${node.name}」`);
  }
  hostListRef.value?.refresh();
  hostTreeRef.value?.refresh();
}

/** ============ 管理抽屉（原页签组件收纳） ============ */

const drawerVisible = ref(false);
const activeDrawer = ref<Api.Cmdb.HostManageKey>('host-group');

const drawerTitleMap: Record<Api.Cmdb.HostManageKey, string> = {
  'host-group': '主机分组管理',
  tag: '主机标签管理',
  'asset-source': '资产来源管理',
  'sync-record': '资产同步记录'
};

function openManageDrawer(key: Api.Cmdb.HostManageKey) {
  activeDrawer.value = key;
  drawerVisible.value = true;
}
</script>

<template>
  <div class="min-h-500px flex gap-12px lt-sm:flex-col">
    <ElCard class="w-300px shrink-0 card-wrapper lt-sm:w-full">
      <HostTree ref="hostTreeRef" @select="handleTreeSelect" @add-host="handleAddHost" @move-hosts="handleMoveHosts" />
    </ElCard>

    <ElCard class="min-w-0 flex-1 card-wrapper">
      <HostList ref="hostListRef" :query="hostQuery" @changed="handleHostsChanged" @open-manage="openManageDrawer" />
    </ElCard>

    <ElDrawer v-model="drawerVisible" :title="drawerTitleMap[activeDrawer]" size="75%" destroy-on-close>
      <HostGroupTab v-if="activeDrawer === 'host-group'" />
      <TagTab v-else-if="activeDrawer === 'tag'" />
      <AssetSourceTab v-else-if="activeDrawer === 'asset-source'" />
      <SyncRecordTab v-else-if="activeDrawer === 'sync-record'" />
    </ElDrawer>
  </div>
</template>

<style scoped></style>
