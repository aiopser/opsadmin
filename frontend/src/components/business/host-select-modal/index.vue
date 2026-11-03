<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue';
import { fetchGetHostGroupList, fetchGetHostList } from '@/service/api';

defineOptions({ name: 'HostSelectModal' });

interface Props {
  visible: boolean;
  /** 已选主机（完整对象），打开弹窗时用于回显 */
  selectedHosts?: Api.Cmdb.HostRecord[];
  /** 打开时预置的 OS 筛选（如按命令类型联动），空为不过滤 */
  defaultOsFamily?: string;
}

const props = withDefaults(defineProps<Props>(), {
  selectedHosts: () => [],
  defaultOsFamily: ''
});

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void;
  (e: 'confirm', hosts: Api.Cmdb.HostRecord[]): void;
}>();

const osFamilyOptions = [
  { label: 'Linux', value: 'linux' },
  { label: 'Windows', value: 'windows' }
];

const searchParams = reactive({
  current: 1,
  size: 10,
  search: '',
  osFamily: ''
});

const total = ref(0);

/** 跨页已选：id → host 对象 */
const selectedMap = ref(new Map<number, Api.Cmdb.HostRecord>());

/** ============ 左侧分组树 ============ */

interface GroupTreeNode {
  id: number | null;
  label: string;
  children: GroupTreeNode[];
}

const groupLoading = ref(false);
const groupTree = ref<GroupTreeNode[]>([]);
const activeGroupId = ref<number | null>(null);

function buildGroupTree(rows: Api.Cmdb.HostGroupRecord[], parentKey: string): GroupTreeNode[] {
  return rows
    .filter(row => (row.parent ? String(row.parent) : '0') === parentKey)
    .map(row => ({
      id: row.id,
      label: `${row.name}（${row.hostCount ?? 0}）`,
      children: buildGroupTree(rows, String(row.id))
    }));
}

async function loadGroups() {
  groupLoading.value = true;
  try {
    const { data, error } = await fetchGetHostGroupList({ current: 1, size: 500 });
    if (!error && data) {
      groupTree.value = buildGroupTree(data.records ?? [], '0');
    }
  } finally {
    groupLoading.value = false;
  }
}

function onTreeNodeClick(data: GroupTreeNode) {
  activeGroupId.value = data.id;
  searchParams.current = 1;
  loadHosts();
}

/** 根节点「全部主机」+ 分组树 */
const treeData = computed<GroupTreeNode[]>(() => [
  { id: null, label: `全部主机（${total.value}）`, children: groupTree.value }
]);

/** ============ 右侧主机表格 ============ */

const hosts = ref<Api.Cmdb.HostRecord[]>([]);
const hostsLoading = ref(false);

async function loadHosts() {
  hostsLoading.value = true;
  try {
    const { data, error } = await fetchGetHostList({
      current: searchParams.current,
      size: searchParams.size,
      search: searchParams.search || undefined,
      osFamily: (searchParams.osFamily || undefined) as Api.Cmdb.HostSearchParams['osFamily'],
      groupId: activeGroupId.value ?? undefined
    });
    if (!error && data) {
      hosts.value = data.records;
      total.value = data.total;
    }
  } finally {
    hostsLoading.value = false;
  }
}

function onSearch() {
  searchParams.current = 1;
  loadHosts();
}

function onOsFamilyChange() {
  searchParams.current = 1;
  loadHosts();
}

function handlePageChange(current: number) {
  searchParams.current = current;
  loadHosts();
}

function handleSizeChange(size: number) {
  searchParams.size = size;
  searchParams.current = 1;
  loadHosts();
}

/** ============ 选择管理 ============ */

function isSelected(id: number) {
  return selectedMap.value.has(id);
}

function toggleHost(host: Api.Cmdb.HostRecord) {
  const next = new Map(selectedMap.value);
  if (next.has(host.id)) {
    next.delete(host.id);
  } else {
    next.set(host.id, host);
  }
  selectedMap.value = next;
}

function clearSelection() {
  selectedMap.value = new Map();
}

const selectedCount = computed(() => selectedMap.value.size);

const selectedPreview = computed(() => [...selectedMap.value.values()].slice(0, 8));

function handleConfirm() {
  emit('confirm', [...selectedMap.value.values()]);
  emit('update:visible', false);
}

function handleClose() {
  emit('update:visible', false);
}

watch(
  () => props.visible,
  visible => {
    if (!visible) return;
    selectedMap.value = new Map(props.selectedHosts.map(host => [host.id, host]));
    searchParams.current = 1;
    searchParams.search = '';
    searchParams.osFamily = props.defaultOsFamily ?? '';
    activeGroupId.value = null;
    loadGroups();
    loadHosts();
  }
);
</script>

<template>
  <ElDialog
    :model-value="visible"
    title="选择主机"
    width="1000px"
    top="7vh"
    :close-on-click-modal="false"
    append-to-body
    @update:model-value="handleClose"
  >
    <div class="flex gap-12px">
      <!-- 左：分组树 -->
      <div class="w-280px shrink-0 border border-gray-200 rounded-4px p-12px">
        <div class="mb-8px font-bold">主机分组</div>
        <ElTree
          v-loading="groupLoading"
          :data="treeData"
          node-key="id"
          :current-node-key="activeGroupId ?? undefined"
          :expand-on-click-node="false"
          default-expand-all
          :props="{ label: 'label', children: 'children' }"
          :highlight-current="true"
          class="max-h-460px overflow-auto"
          @node-click="onTreeNodeClick"
        />
      </div>
      <!-- 右：主机表格 -->
      <div class="min-w-0 flex-1">
        <div class="mb-8px flex items-center gap-8px">
          <ElInput
            v-model="searchParams.search"
            clearable
            placeholder="检索主机名 / IP"
            class="w-200px"
            @keyup.enter="onSearch"
            @clear="onSearch"
          />
          <ElSelect
            v-model="searchParams.osFamily"
            clearable
            placeholder="操作系统"
            class="w-130px"
            @change="onOsFamilyChange"
          >
            <ElOption v-for="item in osFamilyOptions" :key="item.value" :label="item.label" :value="item.value" />
          </ElSelect>
          <ElButton type="primary" plain @click="onSearch">查询</ElButton>
        </div>
        <ElTable v-loading="hostsLoading" :data="hosts" height="460px" row-key="id" border class="host-table">
          <ElTableColumn width="50" align="center">
            <template #default="{ row }">
              <ElCheckbox :model-value="isSelected(row.id)" @change="toggleHost(row)" />
            </template>
          </ElTableColumn>
          <ElTableColumn prop="hostname" label="主机名" min-width="140" align="center" show-overflow-tooltip />
          <ElTableColumn prop="internalIp" label="内网IP" min-width="130" align="center" show-overflow-tooltip />
          <ElTableColumn prop="externalIp" label="外网IP" min-width="130" align="center" show-overflow-tooltip>
            <template #default="{ row }">{{ row.externalIp || '-' }}</template>
          </ElTableColumn>
          <ElTableColumn prop="osFamily" label="系统" width="90" align="center">
            <template #default="{ row }">
              <ElTag size="small" :type="row.osFamily === 'windows' ? 'warning' : 'success'">
                {{ row.osFamily === 'windows' ? 'Windows' : 'Linux' }}
              </ElTag>
            </template>
          </ElTableColumn>
        </ElTable>
        <div class="mt-8px flex justify-end">
          <ElPagination
            layout="total, prev, pager, next, sizes"
            :total="total"
            :current-page="searchParams.current"
            :page-size="searchParams.size"
            :page-sizes="[10, 20, 50, 100]"
            @current-change="handlePageChange"
            @size-change="handleSizeChange"
          />
        </div>
      </div>
    </div>
    <template #footer>
      <div class="flex items-center justify-between">
        <div class="min-w-0 flex-1 text-left">
          <span class="font-bold">已选 {{ selectedCount }} 台</span>
          <template v-if="selectedCount">
            <ElTag
              v-for="host in selectedPreview"
              :key="host.id"
              size="small"
              closable
              class="ml-4px"
              @close="toggleHost(host)"
            >
              {{ host.hostname }}
            </ElTag>
            <span v-if="selectedCount > selectedPreview.length" class="ml-4px text-gray-500">
              +{{ selectedCount - selectedPreview.length }}
            </span>
            <ElButton link size="small" class="ml-8px" @click="clearSelection">清空</ElButton>
          </template>
        </div>
        <div class="shrink-0">
          <ElButton @click="handleClose">取消</ElButton>
          <ElButton type="primary" :disabled="!selectedCount" @click="handleConfirm">确定</ElButton>
        </div>
      </div>
    </template>
  </ElDialog>
</template>

<style scoped>
.host-table :deep(.el-table__row) {
  height: 40px;
}

.host-table :deep(th.el-table__cell) {
  background-color: var(--el-fill-color-light);
  color: var(--el-text-color-regular);
  font-weight: 600;
}

.host-table :deep(.el-table__cell) {
  padding: 4px 0;
}
</style>
