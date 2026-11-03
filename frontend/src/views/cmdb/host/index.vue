<script setup lang="ts">
import { ref } from 'vue';
import { fetchGetHostRelations, fetchUpdateHostRelations } from '@/service/api';
import HostList from './modules/host-list.vue';
import HostTree from './modules/host-tree.vue';

defineOptions({ name: 'CmdbHost' });

/** 主机资产工作台：左侧分组树，右侧主机列表。 */

const hostTreeRef = ref<InstanceType<typeof HostTree>>();
const hostListRef = ref<InstanceType<typeof HostList>>();

/** ============ 左树选中 → 主机查询范围 ============ */

const hostQuery = ref<Api.Cmdb.HostListQuery>({ groupId: null });

function handleTreeSelect(payload: Api.Cmdb.HostTreeSelectPayload) {
  hostQuery.value = { groupId: payload.groupId };
}

/** 左树「添加主机到分组」：打开新增主机抽屉并预填所属分组 */
function handleAddHost(node: Api.Cmdb.HostTreeRow) {
  hostListRef.value?.openAddDrawer(node.id);
}

/** 主机增删改/导入后刷新左树主机计数 */
function handleHostsChanged() {
  hostTreeRef.value?.refresh();
}

/** ============ 移动主机到分组（真移动：分组关系覆盖为目标分组，标签保留，动态分组不受影响） ============ */

async function handleMoveHosts(node: Api.Cmdb.HostTreeRow) {
  if (node.type !== 'group') return;

  const rows = hostListRef.value?.getSelectedRows() ?? [];
  if (!rows.length) {
    window.$message?.warning('请先在右侧表格勾选需要移动的主机');
    return;
  }
  try {
    await ElMessageBox.confirm(
      `确认将选中的 ${rows.length} 台主机移动到分组「${node.name}」？主机将从其他所有分组移出`,
      '移动主机',
      { type: 'warning' }
    );
  } catch {
    return;
  }

  const targetGroupId = String(node.id);
  // relations 接口为全量覆盖：先读每台主机的标签再回传，避免标签被清空
  const okFlags = await Promise.all(
    rows.map(async row => {
      const { data: relations, error: getError } = await fetchGetHostRelations(row.id);
      if (getError) return false;
      const { error } = await fetchUpdateHostRelations(row.id, {
        groupIds: [targetGroupId],
        tagIds: relations?.tagIds ?? []
      });
      return !error;
    })
  );
  const failed = okFlags.filter(ok => !ok).length;
  if (failed) {
    window.$message?.error(`移动失败 ${failed} 台，请重试`);
  } else {
    window.$notification?.success(`已将 ${rows.length} 台主机移动到「${node.name}」`);
  }
  hostListRef.value?.refresh();
  hostTreeRef.value?.refresh();
}
</script>

<template>
  <div class="min-h-500px flex-col-stretch overflow-hidden lt-sm:overflow-auto">
    <div class="min-h-0 flex flex-1 gap-12px lt-sm:flex-col">
      <ElCard class="workspace-card min-h-0 w-300px shrink-0 card-wrapper lt-sm:w-full">
        <HostTree
          ref="hostTreeRef"
          class="min-h-0 flex-1"
          @select="handleTreeSelect"
          @add-host="handleAddHost"
          @move-hosts="handleMoveHosts"
        />
      </ElCard>

      <ElCard class="workspace-card min-h-0 min-w-0 flex-1 card-wrapper">
        <HostList ref="hostListRef" :query="hostQuery" @changed="handleHostsChanged" />
      </ElCard>
    </div>
  </div>
</template>
