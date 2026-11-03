<script setup lang="ts">
import { computed, onMounted, ref, shallowRef, watch } from 'vue';
import {
  fetchAddHostGroup,
  fetchDeleteHostGroup,
  fetchGetHostGroupList,
  fetchGetHostList,
  fetchUpdateHostGroup
} from '@/service/api';

defineOptions({ name: 'CmdbHostTree' });

interface Emits {
  (e: 'select', payload: Api.Cmdb.HostTreeSelectPayload): void;
  (e: 'addHost', node: Api.Cmdb.HostTreeRow): void;
  (e: 'moveHosts', node: Api.Cmdb.HostTreeRow): void;
}

const emit = defineEmits<Emits>();

/** ============ 树数据构建（纯函数） ============ */

/** 按上级分组 ID 建索引（parentId 为 null/0 视为顶级） */
function groupRowsByParent(rows: Api.Cmdb.HostGroupRecord[]) {
  return rows.reduce<Map<string, Api.Cmdb.HostGroupRecord[]>>((map, row) => {
    const parentKey = row.parent ? String(row.parent) : '0';
    const list = map.get(parentKey) ?? [];
    list.push(row);
    map.set(parentKey, list);
    return map;
  }, new Map());
}

function buildGroupRow(
  row: Api.Cmdb.HostGroupRecord,
  childMap: Map<string, Api.Cmdb.HostGroupRecord[]>
): Api.Cmdb.HostTreeRow {
  const children = (childMap.get(String(row.id)) ?? []).map(item => buildGroupRow(item, childMap));
  const childTotal = children.reduce((sum, child) => sum + child.hostCount, 0);
  return {
    key: `group-${row.id}`,
    type: 'group',
    id: row.id,
    name: row.name,
    description: row.description,
    groupType: row.group_type,
    isActive: row.is_active,
    hostCount: row.hostCount + childTotal,
    children
  };
}

function buildTreeData(rows: Api.Cmdb.HostGroupRecord[]): Api.Cmdb.HostTreeRow[] {
  const childMap = groupRowsByParent(rows);
  return (childMap.get('0') ?? []).map(row => buildGroupRow(row, childMap));
}

/** ============ 树数据与选中 ============ */

const loading = ref(false);
const groups = shallowRef<Api.Cmdb.HostGroupRecord[]>([]);
/** 全部主机数（含未分组主机，来自主机列表接口 total） */
const totalHosts = shallowRef(0);
const filterKeyword = ref('');
const selectedKey = ref('');
const treeRef = ref();

const ROOT_KEY = 'all';

const treeData = computed<Api.Cmdb.HostTreeRow[]>(() => [
  {
    key: ROOT_KEY,
    type: 'all',
    id: 0,
    name: '全部主机',
    description: '',
    groupType: '',
    isActive: true,
    // 根节点计数取主机总数而非各分组计数之和，避免漏掉未分组主机
    hostCount: totalHosts.value,
    children: buildTreeData(groups.value)
  }
]);

const allRow: Api.Cmdb.HostTreeRow = {
  key: ROOT_KEY,
  type: 'all',
  id: 0,
  name: '全部主机',
  description: '',
  groupType: '',
  isActive: true,
  hostCount: 0,
  children: []
};

async function refresh() {
  loading.value = true;
  // 并行请求分组列表与主机总数（size=1 仅取 total，用于根节点计数）
  const [groupRes, hostRes] = await Promise.all([
    fetchGetHostGroupList({ current: 1, size: 500 }),
    fetchGetHostList({ current: 1, size: 1 })
  ]);
  loading.value = false;
  if (!groupRes.error) {
    groups.value = groupRes.data.records ?? [];
  }
  if (!hostRes.error) {
    totalHosts.value = hostRes.data.total ?? 0;
  }
}

function handleNodeClick(data: Api.Cmdb.HostTreeRow) {
  selectedKey.value = data.key;
  emit('select', {
    groupId: data.type === 'group' ? data.id : null,
    node: data
  });
}

function handleFilterNode(keyword: string, data: Record<string, unknown>) {
  const name = typeof data.name === 'string' ? data.name : '';
  return !keyword || name.toLowerCase().includes(keyword.toLowerCase());
}

watch(filterKeyword, value => {
  treeRef.value?.filter(value);
});

/** ============ 节点操作入口 ============ */

type NodeAction = 'add-child' | 'add-host' | 'move-hosts' | 'edit' | 'delete';

interface NodeCommand {
  action: NodeAction;
  row: Api.Cmdb.HostTreeRow;
}

function handleNodeCommand(command: NodeCommand) {
  const handlers: Record<NodeAction, (row: Api.Cmdb.HostTreeRow) => void> = {
    'add-child': row => openGroupDialog(row),
    'add-host': row => emit('addHost', row),
    'move-hosts': row => emit('moveHosts', row),
    edit: row => openGroupDialog(null, row),
    delete: row => handleDeleteRow(row)
  };
  handlers[command.action](command.row);
}

async function handleDeleteRow(row: Api.Cmdb.HostTreeRow) {
  try {
    await ElMessageBox.confirm(`确认删除分组「${row.name}」？分组下存在子分组或成员主机时将被拒绝删除`, '删除确认', {
      type: 'warning'
    });
  } catch {
    return;
  }
  const { error } = await fetchDeleteHostGroup(row.id);
  if (!error) {
    window.$notification?.success('删除成功');
    if (selectedKey.value === row.key) {
      selectedKey.value = ROOT_KEY;
      emit('select', { groupId: null, node: allRow });
    }
    refresh();
  }
}

/** ============ 分组 新建/编辑 对话框 ============ */

interface GroupForm {
  id?: number;
  name: string;
  description: string;
  is_active: boolean;
  /** 编辑时回传，保持类型与匹配规则不变 */
  group_type?: string;
  match_rule?: Record<string, unknown>;
}

function createDefaultGroupForm(): GroupForm {
  return { name: '', description: '', is_active: true };
}

const groupVisible = ref(false);
const groupSubmitting = ref(false);
const groupFormRef = ref();
const groupForm = ref<GroupForm>(createDefaultGroupForm());
const groupFormTitle = computed(() => (groupForm.value.id ? '编辑分组' : '新建分组'));

const groupFormRules = {
  name: [{ required: true, message: '请输入分组名称', trigger: 'blur' }]
};

/** 新建子分组时携带的父节点行 */
const parentRow = shallowRef<Api.Cmdb.HostTreeRow | null>(null);

const parentLabel = computed(() => parentRow.value?.name ?? '');

function openGroupDialog(parent: Api.Cmdb.HostTreeRow | null, row?: Api.Cmdb.HostTreeRow) {
  parentRow.value = row ? null : parent;
  const record = row ? groups.value.find(item => item.id === row.id) : null;
  groupForm.value = row
    ? {
        id: row.id,
        name: row.name,
        description: row.description,
        is_active: row.isActive,
        group_type: record?.group_type,
        match_rule: record?.match_rule
      }
    : createDefaultGroupForm();
  groupVisible.value = true;
}

async function handleGroupSubmit() {
  await groupFormRef.value?.validate();

  groupSubmitting.value = true;
  const form = groupForm.value;
  // 新建时按所选父节点挂载；编辑时不传 parent，保持原层级不变
  const parentId = parentRow.value?.type === 'group' ? parentRow.value.id : null;
  const payload: Api.Cmdb.HostGroupPayload = {
    name: form.name,
    parent: form.id ? undefined : parentId,
    description: form.description,
    is_active: form.is_active,
    group_type: (form.group_type as Api.Cmdb.HostGroupType) ?? 'static',
    match_rule: form.match_rule ?? {}
  };
  const { error } = form.id ? await fetchUpdateHostGroup(form.id, payload) : await fetchAddHostGroup(payload);
  groupSubmitting.value = false;

  if (!error) {
    window.$notification?.success(form.id ? '修改成功' : '新建成功');
    groupVisible.value = false;
    refresh();
  }
}

/** ============ 生命周期 ============ */

onMounted(() => {
  refresh();
});

defineExpose({ refresh });
</script>

<template>
  <div class="flex-col-stretch gap-8px overflow-hidden">
    <div class="flex items-center justify-between">
      <p class="font-medium">主机分组</p>
      <div class="flex items-center gap-4px">
        <ElTooltip content="新建根分组" placement="top">
          <ElButton size="small" circle @click="openGroupDialog(null)">
            <template #icon>
              <icon-ic-round-plus class="text-icon" />
            </template>
          </ElButton>
        </ElTooltip>
        <ElTooltip content="刷新" placement="top">
          <ElButton size="small" circle @click="refresh()">
            <template #icon>
              <icon-ic-round-refresh class="text-icon" />
            </template>
          </ElButton>
        </ElTooltip>
      </div>
    </div>

    <ElInput v-model="filterKeyword" clearable placeholder="搜索分组" size="small" />

    <div v-loading="loading" class="flex-1 overflow-auto">
      <ElTree
        ref="treeRef"
        :data="treeData"
        node-key="key"
        :current-node-key="selectedKey"
        :expand-on-click-node="false"
        default-expand-all
        highlight-current
        :filter-node-method="handleFilterNode"
        @node-click="handleNodeClick"
      >
        <template #default="{ data }">
          <div class="group flex flex-1 items-center gap-4px overflow-hidden pr-4px">
            <span class="truncate" :class="{ 'font-medium': data.type === 'all' }">{{ data.name }}</span>
            <span v-if="data.groupType === 'dynamic'" class="shrink-0 text-12px text-warning">（动态）</span>
            <span v-if="!data.isActive" class="shrink-0 text-12px text-warning">（停用）</span>
            <span class="ml-auto shrink-0 text-12px text-[var(--el-text-color-secondary)]">{{ data.hostCount }}</span>
            <span v-if="data.type === 'group'" class="shrink-0" @click.stop>
              <!-- ElTooltip 必须包在 ElDropdown 外层：嵌在触发按钮外会丢失 dropdown 的 click 绑定导致点击无响应 -->
              <ElTooltip content="更多操作" placement="top">
                <ElDropdown trigger="click" @command="handleNodeCommand">
                  <ElButton size="small" text circle class="opacity-0 group-hover:opacity-100">
                    <template #icon>
                      <icon-ic-round-more-vert class="text-icon" />
                    </template>
                  </ElButton>
                  <template #dropdown>
                    <ElDropdownMenu>
                      <ElDropdownItem :command="{ action: 'add-child', row: data }">新建子分组</ElDropdownItem>
                      <ElDropdownItem v-if="data.groupType === 'static'" :command="{ action: 'add-host', row: data }">
                        添加主机
                      </ElDropdownItem>
                      <ElDropdownItem v-if="data.groupType === 'static'" :command="{ action: 'move-hosts', row: data }">
                        移动主机到此分组
                      </ElDropdownItem>
                      <ElDropdownItem divided :command="{ action: 'edit', row: data }">编辑</ElDropdownItem>
                      <ElDropdownItem :command="{ action: 'delete', row: data }">
                        <span class="text-danger">删除</span>
                      </ElDropdownItem>
                    </ElDropdownMenu>
                  </template>
                </ElDropdown>
              </ElTooltip>
            </span>
          </div>
        </template>
      </ElTree>
      <ElEmpty v-if="!loading && !groups.length" description="暂无分组">
        <ElButton type="primary" size="small" @click="openGroupDialog(null)">新建根分组</ElButton>
      </ElEmpty>
    </div>

    <ElDialog v-model="groupVisible" :title="groupFormTitle" width="440px" :close-on-click-modal="false">
      <ElForm
        ref="groupFormRef"
        :model="groupForm"
        :rules="groupFormRules"
        label-width="80px"
        label-suffix="："
        require-asterisk-position="left"
      >
        <ElFormItem v-if="parentRow" label="上级分组">
          <span>{{ parentLabel }}</span>
        </ElFormItem>
        <ElFormItem label="分组名称" prop="name">
          <ElInput v-model="groupForm.name" placeholder="如 生产环境 / 华东区" />
        </ElFormItem>
        <ElFormItem label="描述">
          <ElInput v-model="groupForm.description" type="textarea" :rows="3" placeholder="分组描述" />
        </ElFormItem>
        <ElFormItem label="启用">
          <ElSwitch v-model="groupForm.is_active" />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="groupVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="groupSubmitting" @click="handleGroupSubmit">确认</ElButton>
      </template>
    </ElDialog>
  </div>
</template>

<style scoped></style>
