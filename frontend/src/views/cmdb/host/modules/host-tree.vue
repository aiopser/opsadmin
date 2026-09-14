<script setup lang="ts">
import { computed, onMounted, ref, shallowRef, watch } from 'vue';
import {
  fetchAddBusiness,
  fetchAddServiceNode,
  fetchDeleteBusiness,
  fetchDeleteServiceNode,
  fetchGetBusinessList,
  fetchGetServiceNodeList,
  fetchUpdateBusiness,
  fetchUpdateServiceNode
} from '@/service/api';

defineOptions({ name: 'CmdbHostTree' });

interface Emits {
  (e: 'select', payload: Api.Cmdb.HostTreeSelectPayload): void;
  (e: 'addHost', node: Api.Cmdb.HostTreeRow): void;
  (e: 'moveHosts', node: Api.Cmdb.HostTreeRow): void;
}

const emit = defineEmits<Emits>();

/** ============ 枚举文案与层级约束 ============ */

const nodeTypeText: Record<string, string> = {
  environment: '环境',
  region: '区域',
  module: '模块'
};

const nodeTypeTagType: Record<string, UI.ThemeColor> = {
  environment: 'primary',
  region: 'warning',
  module: 'success'
};

/** 子节点类型约束：业务下挂环境，环境挂区域，区域挂模块，模块不可再挂子节点 */
const childNodeType: Record<string, Api.Cmdb.ServiceNodeType | null> = {
  business: 'environment',
  environment: 'region',
  region: 'module',
  module: null
};

/** ============ 树数据构建（纯函数） ============ */

function bySortOrder<T extends Pick<Api.Cmdb.ServiceTreeNodeRecord, 'sort_order' | 'id'>>(a: T, b: T) {
  return a.sort_order - b.sort_order || a.id - b.id;
}

function collectNodeIds(row: Api.Cmdb.HostTreeRow): number[] {
  return row.children.flatMap(child => [child.id, ...collectNodeIds(child)]);
}

function groupNodesByParent(nodes: Api.Cmdb.ServiceTreeNodeRecord[]) {
  return nodes.reduce<Map<number, Api.Cmdb.ServiceTreeNodeRecord[]>>((map, node) => {
    const parentKey = node.parent ?? 0;
    const list = map.get(parentKey) ?? [];
    list.push(node);
    map.set(parentKey, list);
    return map;
  }, new Map());
}

function buildNodeRow(
  node: Api.Cmdb.ServiceTreeNodeRecord,
  childMap: Map<number, Api.Cmdb.ServiceTreeNodeRecord[]>
): Api.Cmdb.HostTreeRow {
  const children = (childMap.get(node.id) ?? [])
    .slice()
    .sort(bySortOrder)
    .map(item => buildNodeRow(item, childMap));
  const childTotal = children.reduce((sum, child) => sum + child.hostCount, 0);
  return {
    key: `node-${node.id}`,
    type: 'node',
    id: node.id,
    name: node.name,
    code: node.code,
    nodeType: node.node_type,
    description: node.description,
    sortOrder: node.sort_order,
    hostCount: node.hostCount + childTotal,
    businessId: node.business,
    isActive: node.is_active,
    children
  };
}

function buildTreeData(
  businesses: Api.Cmdb.BusinessRecord[],
  nodes: Api.Cmdb.ServiceTreeNodeRecord[]
): Api.Cmdb.HostTreeRow[] {
  return businesses.map(business => {
    const childMap = groupNodesByParent(nodes.filter(node => node.business === business.id));
    const children = (childMap.get(0) ?? [])
      .slice()
      .sort(bySortOrder)
      .map(node => buildNodeRow(node, childMap));
    return {
      key: `business-${business.id}`,
      type: 'business',
      id: business.id,
      name: business.name,
      code: business.code,
      nodeType: '',
      description: business.description,
      sortOrder: 0,
      hostCount: business.hostCount,
      businessId: business.id,
      isActive: business.is_active,
      children
    };
  });
}

/** ============ 树数据与选中 ============ */

const loading = ref(false);
const businesses = shallowRef<Api.Cmdb.BusinessRecord[]>([]);
const nodes = shallowRef<Api.Cmdb.ServiceTreeNodeRecord[]>([]);
const filterKeyword = ref('');
const selectedKey = ref('');
const treeRef = ref();

const treeData = computed(() => buildTreeData(businesses.value, nodes.value));

async function refresh() {
  loading.value = true;
  const [businessRes, nodeRes] = await Promise.all([
    fetchGetBusinessList({ current: 1, size: 100 }),
    fetchGetServiceNodeList({ current: 1, size: 100 })
  ]);
  loading.value = false;
  if (!businessRes.error) {
    businesses.value = businessRes.data.records ?? [];
  }
  if (!nodeRes.error) {
    nodes.value = nodeRes.data.records ?? [];
  }
}

function handleNodeClick(data: Api.Cmdb.HostTreeRow) {
  selectedKey.value = data.key;
  emit('select', {
    business: data.type === 'business' ? data.id : null,
    serviceNodeIds: data.type === 'node' ? [data.id, ...collectNodeIds(data)] : null,
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
    'add-child': row => openNodeDialog(row),
    'add-host': row => emit('addHost', row),
    'move-hosts': row => emit('moveHosts', row),
    edit: row => (row.type === 'business' ? openBusinessDialog(row) : openNodeDialog(null, row)),
    delete: row => handleDeleteRow(row)
  };
  handlers[command.action](command.row);
}

async function handleDeleteRow(row: Api.Cmdb.HostTreeRow) {
  const isBusiness = row.type === 'business';
  const tip = isBusiness
    ? `确认删除业务「${row.name}」？业务下存在服务树节点时将被拒绝删除`
    : `确认删除节点「${row.name}」？节点下存在子节点或主机时将被拒绝删除`;
  try {
    await ElMessageBox.confirm(tip, '删除确认', { type: 'warning' });
  } catch {
    return;
  }
  const { error } = isBusiness ? await fetchDeleteBusiness(row.id) : await fetchDeleteServiceNode(row.id);
  if (!error) {
    window.$message?.success('删除成功');
    if (selectedKey.value === row.key) {
      selectedKey.value = '';
      emit('select', { business: null, serviceNodeIds: null, node: null });
    }
    refresh();
  }
}

/** ============ 业务 新建/编辑 对话框 ============ */

interface BusinessForm {
  id?: number;
  code: string;
  name: string;
  description: string;
  is_active: boolean;
}

const businessVisible = ref(false);
const businessSubmitting = ref(false);
const businessFormRef = ref();
const businessForm = ref<BusinessForm>({ code: '', name: '', description: '', is_active: true });

const businessFormTitle = computed(() => (businessForm.value.id ? '编辑业务' : '新建业务'));

const businessFormRules = {
  code: [{ required: true, message: '请输入业务编码', trigger: 'blur' }],
  name: [{ required: true, message: '请输入业务名称', trigger: 'blur' }]
};

function openBusinessDialog(row?: Api.Cmdb.HostTreeRow) {
  businessForm.value = row
    ? { id: row.id, code: row.code, name: row.name, description: row.description, is_active: row.isActive }
    : { code: '', name: '', description: '', is_active: true };
  businessVisible.value = true;
}

async function handleBusinessSubmit() {
  await businessFormRef.value?.validate();

  businessSubmitting.value = true;
  const form = businessForm.value;
  const payload: Api.Cmdb.BusinessPayload = {
    code: form.code,
    name: form.name,
    description: form.description,
    is_active: form.is_active
  };
  const { error } = form.id ? await fetchUpdateBusiness(form.id, payload) : await fetchAddBusiness(payload);
  businessSubmitting.value = false;

  if (!error) {
    window.$message?.success(form.id ? '修改成功' : '新建成功');
    businessVisible.value = false;
    refresh();
  }
}

/** ============ 服务树节点 新建/编辑 对话框 ============ */

interface NodeForm {
  id?: number;
  business: number | null;
  parent: number | null;
  node_type: Api.Cmdb.ServiceNodeType;
  code: string;
  name: string;
  sort_order: number;
  description: string;
  is_active: boolean;
}

function createDefaultNodeForm(): NodeForm {
  return {
    business: null,
    parent: null,
    node_type: 'environment',
    code: '',
    name: '',
    sort_order: 0,
    description: '',
    is_active: true
  };
}

const nodeVisible = ref(false);
const nodeSubmitting = ref(false);
const nodeFormRef = ref();
const nodeForm = ref<NodeForm>(createDefaultNodeForm());
const nodeFormTitle = computed(() => (nodeForm.value.id ? '编辑节点' : '新建子节点'));

const nodeFormRules = {
  code: [{ required: true, message: '请输入节点编码', trigger: 'blur' }],
  name: [{ required: true, message: '请输入节点名称', trigger: 'blur' }]
};

/** 新增子节点时携带的父节点行 */
const nodeParentRow = shallowRef<Api.Cmdb.HostTreeRow | null>(null);

const nodeParentLabel = computed(() => {
  const parent = nodeParentRow.value;
  return parent ? `${parent.name}（${nodeTypeText[parent.nodeType] ?? parent.nodeType}）` : '';
});

function openNodeDialog(parent: Api.Cmdb.HostTreeRow | null, row?: Api.Cmdb.HostTreeRow) {
  nodeParentRow.value = row ? null : parent;
  nodeForm.value = row
    ? {
        id: row.id,
        business: row.businessId,
        parent: null,
        node_type: row.nodeType as Api.Cmdb.ServiceNodeType,
        code: row.code,
        name: row.name,
        sort_order: row.sortOrder,
        description: row.description,
        is_active: row.isActive
      }
    : {
        ...createDefaultNodeForm(),
        business: parent?.businessId ?? null,
        parent: parent?.type === 'node' ? parent.id : null,
        node_type: (parent && childNodeType[parent.nodeType]) || 'environment'
      };
  nodeVisible.value = true;
}

async function handleNodeSubmit() {
  await nodeFormRef.value?.validate();

  nodeSubmitting.value = true;
  const form = nodeForm.value;
  // 编辑时不传 parent，保持原层级不变
  const payload: Api.Cmdb.ServiceTreeNodePayload = {
    business: form.business!,
    parent: form.parent ?? null,
    node_type: form.node_type,
    code: form.code,
    name: form.name,
    sort_order: form.sort_order,
    description: form.description,
    is_active: form.is_active
  };
  const { error } = form.id ? await fetchUpdateServiceNode(form.id, payload) : await fetchAddServiceNode(payload);
  nodeSubmitting.value = false;

  if (!error) {
    window.$message?.success(form.id ? '修改成功' : '新建成功');
    nodeVisible.value = false;
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
      <p class="font-medium">业务 / 服务树</p>
      <div class="flex items-center gap-4px">
        <ElTooltip content="新建业务" placement="top">
          <ElButton size="small" circle @click="openBusinessDialog()">
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

    <ElInput v-model="filterKeyword" clearable placeholder="搜索节点" size="small" />

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
            <ElTag v-if="data.type === 'node'" size="small" :type="nodeTypeTagType[data.nodeType] ?? 'info'">
              {{ nodeTypeText[data.nodeType] ?? data.nodeType }}
            </ElTag>
            <span class="truncate" :class="{ 'font-medium': data.type === 'business' }">{{ data.name }}</span>
            <span v-if="!data.isActive" class="shrink-0 text-12px text-warning">（停用）</span>
            <span class="ml-auto shrink-0 text-12px text-#909399">{{ data.hostCount }}</span>
            <span class="shrink-0" @click.stop>
              <ElDropdown trigger="click" @command="handleNodeCommand">
                <ElButton size="small" text circle class="opacity-0 group-hover:opacity-100">
                  <template #icon>
                    <icon-ic-round-more-vert class="text-icon" />
                  </template>
                </ElButton>
                <template #dropdown>
                  <ElDropdownMenu>
                    <ElDropdownItem
                      v-if="data.type === 'business' || childNodeType[data.nodeType]"
                      :command="{ action: 'add-child', row: data }"
                    >
                      新建子节点
                    </ElDropdownItem>
                    <ElDropdownItem v-if="data.type === 'node'" :command="{ action: 'add-host', row: data }">
                      添加主机
                    </ElDropdownItem>
                    <ElDropdownItem v-if="data.type === 'node'" :command="{ action: 'move-hosts', row: data }">
                      移动主机到此节点
                    </ElDropdownItem>
                    <ElDropdownItem divided :command="{ action: 'edit', row: data }">编辑</ElDropdownItem>
                    <ElDropdownItem :command="{ action: 'delete', row: data }">
                      <span class="text-danger">删除</span>
                    </ElDropdownItem>
                  </ElDropdownMenu>
                </template>
              </ElDropdown>
            </span>
          </div>
        </template>
      </ElTree>
      <ElEmpty v-if="!loading && !treeData.length" description="暂无业务，点击右上角 + 新建" />
    </div>

    <ElDialog v-model="businessVisible" :title="businessFormTitle" width="440px" :close-on-click-modal="false">
      <ElForm ref="businessFormRef" :model="businessForm" :rules="businessFormRules" label-width="80px">
        <ElFormItem label="业务编码" prop="code">
          <ElInput v-model="businessForm.code" placeholder="业务内唯一，如 order" />
        </ElFormItem>
        <ElFormItem label="业务名称" prop="name">
          <ElInput v-model="businessForm.name" placeholder="如 订单业务" />
        </ElFormItem>
        <ElFormItem label="描述">
          <ElInput v-model="businessForm.description" type="textarea" :rows="3" placeholder="业务描述" />
        </ElFormItem>
        <ElFormItem label="启用">
          <ElSwitch v-model="businessForm.is_active" />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="businessVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="businessSubmitting" @click="handleBusinessSubmit">确认</ElButton>
      </template>
    </ElDialog>

    <ElDialog v-model="nodeVisible" :title="nodeFormTitle" width="440px" :close-on-click-modal="false">
      <ElForm ref="nodeFormRef" :model="nodeForm" :rules="nodeFormRules" label-width="80px">
        <ElFormItem v-if="nodeForm.id" label="节点类型">
          <ElTag :type="nodeTypeTagType[nodeForm.node_type] ?? 'info'">
            {{ nodeTypeText[nodeForm.node_type] ?? nodeForm.node_type }}
          </ElTag>
        </ElFormItem>
        <ElFormItem v-else-if="nodeParentRow" label="父节点">
          <span>{{ nodeParentLabel }}</span>
        </ElFormItem>
        <ElFormItem label="节点编码" prop="code">
          <ElInput v-model="nodeForm.code" placeholder="业务内唯一，如 prod / cn-north / order" />
        </ElFormItem>
        <ElFormItem label="节点名称" prop="name">
          <ElInput v-model="nodeForm.name" placeholder="如 生产环境" />
        </ElFormItem>
        <ElFormItem label="排序">
          <ElInputNumber v-model="nodeForm.sort_order" :min="0" class="w-full" />
        </ElFormItem>
        <ElFormItem label="描述">
          <ElInput v-model="nodeForm.description" type="textarea" :rows="3" placeholder="节点描述" />
        </ElFormItem>
        <ElFormItem label="启用">
          <ElSwitch v-model="nodeForm.is_active" />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="nodeVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="nodeSubmitting" @click="handleNodeSubmit">确认</ElButton>
      </template>
    </ElDialog>
  </div>
</template>

<style scoped></style>
