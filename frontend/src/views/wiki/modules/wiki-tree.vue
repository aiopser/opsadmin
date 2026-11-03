<script setup lang="ts">
import { computed, onMounted, ref, shallowRef, watch } from 'vue';
import { fetchCreateWikiPage, fetchDeleteWikiPage, fetchGetWikiTree, fetchUpdateWikiPage } from '@/service/api';
import { useAuth } from '@/hooks/business/auth';

defineOptions({ name: 'WikiTree' });

interface Emits {
  (e: 'select', node: Api.Wiki.PageNode | null): void;
  /** 节点新建/重命名/删除/移动后触发，供父级同步 */
  (e: 'changed'): void;
}

const emit = defineEmits<Emits>();

const { hasAuth } = useAuth();

const canCreate = computed(() => hasAuth('wiki.page:create'));
const canUpdate = computed(() => hasAuth('wiki.page:update'));
const canDelete = computed(() => hasAuth('wiki.page:delete'));

/** ============ 扁平列表 → 树（纯函数） ============ */

/** 按父节点 id 建索引（parent 为 null/0 视为顶级） */
function groupNodesByParent(rows: Api.Wiki.PageNode[]) {
  return rows.reduce<Map<string, Api.Wiki.PageNode[]>>((map, row) => {
    const parentKey = row.parent ? String(row.parent) : '0';
    const list = map.get(parentKey) ?? [];
    list.push(row);
    map.set(parentKey, list);
    return map;
  }, new Map());
}

function buildTreeNodes(rows: Api.Wiki.PageNode[]): Api.Wiki.TreeNode[] {
  const childMap = groupNodesByParent(rows);
  const build = (row: Api.Wiki.PageNode): Api.Wiki.TreeNode => ({
    ...row,
    children: (childMap.get(String(row.id)) ?? []).map(build)
  });
  return (childMap.get('0') ?? []).map(build);
}

/** 同级节点 id（后端按 sort,id 排序返回，即当前展示顺序） */
function orderedSiblingIds(rows: Api.Wiki.PageNode[], parentId: number | null) {
  return rows.filter(row => (row.parent ?? null) === parentId).map(row => row.id);
}

function countSubtree(node: Api.Wiki.TreeNode): number {
  return 1 + node.children.reduce((sum, child) => sum + countSubtree(child), 0);
}

/** ============ 树状态 ============ */

const loading = ref(false);
const rows = shallowRef<Api.Wiki.PageNode[]>([]);
const keyword = ref('');
const selectedKey = ref('');
const treeRef = ref();

const treeData = computed<Api.Wiki.TreeNode[]>(() => buildTreeNodes(rows.value));

const hasData = computed(() => rows.value.length > 0);

async function refresh() {
  loading.value = true;
  const { data, error } = await fetchGetWikiTree();
  loading.value = false;
  if (!error) rows.value = data ?? [];
}

function handleNodeClick(data: Api.Wiki.TreeNode) {
  selectedKey.value = String(data.id);
  emit('select', data);
}

function handleFilterNode(value: string, data: Record<string, unknown>) {
  const title = typeof data.title === 'string' ? data.title : '';
  return !value || title.toLowerCase().includes(value.toLowerCase());
}

/** ============ 节点操作 ============ */

type NodeAction = 'add-folder' | 'add-doc' | 'rename' | 'delete';

interface NodeCommand {
  action: NodeAction;
  node: Api.Wiki.TreeNode;
}

function handleNodeCommand(command: NodeCommand) {
  const handlers: Record<NodeAction, (node: Api.Wiki.TreeNode) => void> = {
    'add-folder': node => createNode(node, true),
    'add-doc': node => createNode(node, false),
    rename: node => renameNode(node),
    delete: node => deleteNode(node)
  };
  handlers[command.action](command.node);
}

/** 弹窗取名称，取消或无输入时返回 null */
async function promptTitle(message: string, title: string, initial = '') {
  try {
    const { value } = await ElMessageBox.prompt(message, title, {
      inputValue: initial,
      inputPlaceholder: `请输入${message}`,
      inputValidator: (input: string) => (input?.trim() ? true : '名称不能为空'),
      confirmButtonText: '确定',
      cancelButtonText: '取消'
    });
    return value.trim();
  } catch {
    return null;
  }
}

async function createNode(parent: Api.Wiki.TreeNode | null, isFolder: boolean) {
  const label = isFolder ? '目录名' : '文档名';
  const title = await promptTitle(label, isFolder ? '新建目录' : '新建文档');
  if (!title) return;

  const { data, error } = await fetchCreateWikiPage({
    title,
    parent: parent?.id ?? null,
    is_folder: isFolder
  });
  if (error || !data) return;

  window.$notification?.success('新建成功');
  await refresh();
  selectedKey.value = String(data.id);
  emit('select', data);
  emit('changed');
}

async function renameNode(node: Api.Wiki.TreeNode) {
  const title = await promptTitle('节点名', '重命名', node.title);
  if (!title || title === node.title) return;

  const { error } = await fetchUpdateWikiPage(node.id, { title });
  if (error) return;

  window.$notification?.success('已重命名');
  await refresh();
  emit('changed');
}

async function deleteNode(node: Api.Wiki.TreeNode) {
  const childCount = countSubtree(node) - 1;
  const tips = childCount
    ? `确认删除「${node.title}」及其下 ${childCount} 个子节点？删除后不可恢复`
    : `确认删除「${node.title}」？删除后不可恢复`;
  try {
    await ElMessageBox.confirm(tips, '删除确认', { type: 'warning' });
  } catch {
    return;
  }

  const { error } = await fetchDeleteWikiPage(node.id);
  if (error) return;

  window.$notification?.success('删除成功');
  if (selectedKey.value === String(node.id)) {
    selectedKey.value = '';
    emit('select', null);
  }
  await refresh();
  emit('changed');
}

/** ============ 拖拽移动 / 排序 ============ */

type DropType = 'before' | 'after' | 'inner';

/** allow-drop 的落点类型（Element Plus 用 prev/next 表示同级前后） */
type AllowDropType = 'prev' | 'inner' | 'next';

/** ElTree 拖拽事件载荷：data 为传入的节点对象，结构由运行时还原 */
interface DropNodeLike {
  data: Record<string, unknown>;
}

/** 从 ElTree 事件载荷还原业务节点 */
function readTreeNode(data: Record<string, unknown>): Api.Wiki.TreeNode | null {
  const { id, title, parent, is_folder, sort, is_active } = data;
  if (typeof id !== 'number' || typeof title !== 'string') return null;
  return {
    id,
    title,
    parent: typeof parent === 'number' ? parent : null,
    is_folder: is_folder === true,
    sort: typeof sort === 'number' ? sort : 0,
    is_active: is_active !== false,
    children: []
  };
}

/** 只允许拖到目录内部，同级前后排序不受限 */
function handleAllowDrop(_draggingNode: DropNodeLike, dropNode: DropNodeLike, type: AllowDropType) {
  return type !== 'inner' || readTreeNode(dropNode.data)?.is_folder === true;
}

/** 拖拽后按「新父节点 + 落点位置」重算同级顺序，仅提交变化的 sort */
async function handleNodeDrop(draggingNode: DropNodeLike, dropNode: DropNodeLike, dropType: DropType) {
  const dragging = readTreeNode(draggingNode.data);
  const drop = readTreeNode(dropNode.data);
  if (!dragging || !drop) return;

  const targetParent = dropType === 'inner' ? drop.id : drop.parent;
  const siblings = orderedSiblingIds(rows.value, targetParent).filter(id => id !== dragging.id);
  const anchorIndex = dropType === 'inner' ? siblings.length : siblings.indexOf(drop.id);
  const insertIndex = dropType === 'after' ? anchorIndex + 1 : anchorIndex;
  const orderedIds = [...siblings.slice(0, insertIndex), dragging.id, ...siblings.slice(insertIndex)];

  const { error } = await fetchUpdateWikiPage(dragging.id, { parent: targetParent });
  if (error) return;

  // sort 以 10 递增，避免与同级其它节点取同值导致顺序抖动
  await Promise.all(
    orderedIds.map(async (id, index) => {
      const sort = index * 10;
      if (rows.value.find(row => row.id === id)?.sort === sort) return;
      await fetchUpdateWikiPage(id, { sort });
    })
  );

  await refresh();
  window.$notification?.success('已移动');
  emit('changed');
}

/** ============ 生命周期 ============ */

watch(keyword, value => {
  treeRef.value?.filter(value);
});

onMounted(() => {
  refresh();
});

defineExpose({
  refresh,
  /** 供父级在放弃切换时回滚高亮 */
  selectNode(node: Api.Wiki.PageNode) {
    selectedKey.value = String(node.id);
    treeRef.value?.setCurrentKey(String(node.id));
  }
});
</script>

<template>
  <div class="flex-col-stretch gap-8px overflow-hidden">
    <div class="flex items-center justify-between">
      <p class="font-medium">知识库目录</p>
      <div class="flex items-center gap-4px">
        <template v-if="canCreate">
          <ElTooltip content="新建目录" placement="top">
            <ElButton size="small" circle aria-label="新建目录" @click="createNode(null, true)">
              <template #icon>
                <icon-ic-round-create-new-folder class="text-icon" />
              </template>
            </ElButton>
          </ElTooltip>
          <ElTooltip content="新建文档" placement="top">
            <ElButton size="small" circle aria-label="新建文档" @click="createNode(null, false)">
              <template #icon>
                <icon-ic-round-note-add class="text-icon" />
              </template>
            </ElButton>
          </ElTooltip>
        </template>
        <ElTooltip content="刷新" placement="top">
          <ElButton size="small" circle aria-label="刷新" @click="refresh()">
            <template #icon>
              <icon-ic-round-refresh class="text-icon" />
            </template>
          </ElButton>
        </ElTooltip>
      </div>
    </div>

    <ElInput v-model="keyword" clearable placeholder="搜索节点" size="small" />

    <div v-loading="loading" class="min-h-0 flex-1 overflow-auto">
      <ElTree
        ref="treeRef"
        :data="treeData"
        node-key="id"
        :current-node-key="selectedKey"
        :expand-on-click-node="false"
        default-expand-all
        highlight-current
        draggable
        :allow-drop="handleAllowDrop"
        :filter-node-method="handleFilterNode"
        :props="{ label: 'title' }"
        @node-click="handleNodeClick"
        @node-drop="handleNodeDrop"
      >
        <template #default="{ data }">
          <div class="node group flex flex-1 items-center gap-4px overflow-hidden pr-4px">
            <icon-ic-round-folder v-if="data.is_folder" class="shrink-0 text-icon" />
            <icon-ic-round-description v-else class="shrink-0 text-icon" />
            <span class="truncate">{{ data.title }}</span>
            <span v-if="!data.is_active" class="shrink-0 text-12px text-warning">（停用）</span>
            <span v-if="canCreate || canUpdate || canDelete" class="shrink-0" @click.stop>
              <!-- ElTooltip 必须包在 ElDropdown 外层：嵌在触发按钮外会丢失 dropdown 的 click 绑定 -->
              <ElTooltip content="更多操作" placement="top">
                <ElDropdown trigger="click" @command="handleNodeCommand">
                  <ElButton size="small" text circle class="opacity-0 group-hover:opacity-100" aria-label="更多操作">
                    <template #icon>
                      <icon-ic-round-more-vert class="text-icon" />
                    </template>
                  </ElButton>
                  <template #dropdown>
                    <ElDropdownMenu>
                      <ElDropdownItem v-if="canCreate" :command="{ action: 'add-folder', node: data }">
                        新建子目录
                      </ElDropdownItem>
                      <ElDropdownItem v-if="canCreate" :command="{ action: 'add-doc', node: data }">
                        新建子文档
                      </ElDropdownItem>
                      <ElDropdownItem v-if="canUpdate" divided :command="{ action: 'rename', node: data }">
                        重命名
                      </ElDropdownItem>
                      <ElDropdownItem v-if="canDelete" :command="{ action: 'delete', node: data }">
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

      <ElEmpty v-if="!loading && !hasData" description="暂无文档，先建一个目录吧">
        <ElButton v-if="canCreate" type="primary" size="small" @click="createNode(null, true)">新建目录</ElButton>
      </ElEmpty>
    </div>
  </div>
</template>

<style scoped></style>
