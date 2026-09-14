<script setup lang="tsx">
import { computed, reactive, ref, shallowRef } from 'vue';
import { useRouter } from 'vue-router';
import {
  fetchAddWorkflowTemplate,
  fetchArchiveWorkflowVersion,
  fetchCreateWorkflowVersionDraft,
  fetchDeleteWorkflowTemplate,
  fetchGetWorkflowEdges,
  fetchGetWorkflowGraph,
  fetchGetWorkflowNodes,
  fetchGetWorkflowTemplateList,
  fetchGetWorkflowVersions,
  fetchPublishWorkflowVersion,
  fetchUpdateWorkflowGraph,
  fetchUpdateWorkflowTemplate
} from '@/service/api';
import { defaultTransform, useUIPaginatedTable } from '@/hooks/common/table';
import CodeEditor from '@/components/common/code-editor/index.vue';

defineOptions({ name: 'TaskTemplates' });

const router = useRouter();

/** ============ 搜索 ============ */

/** 模板启用/停用与版本草稿/发布/归档是两套独立状态：模板只关心是否启用 */
const statusOptions = [
  { value: 'published', label: '启用' },
  { value: 'disabled', label: '停用' }
];

const statusText: Record<string, string> = {
  draft: '草稿',
  published: '启用',
  disabled: '停用'
};

const statusTagType: Record<string, string> = {
  draft: 'info',
  published: 'success',
  disabled: 'danger'
};

function getInitSearchParams() {
  return {
    current: 1,
    size: 10,
    status: undefined as string | undefined,
    search: undefined as string | undefined
  };
}

const searchParams = ref(getInitSearchParams());

/** ============ 列表 ============ */

const { columns, columnChecks, data, getData, getDataByPage, loading, mobilePagination } = useUIPaginatedTable({
  paginationProps: {
    currentPage: searchParams.value.current,
    pageSize: searchParams.value.size
  },
  api: () =>
    fetchGetWorkflowTemplateList({
      current: searchParams.value.current,
      size: searchParams.value.size,
      status: searchParams.value.status || null,
      search: searchParams.value.search
    }),
  transform: response => defaultTransform(response),
  onPaginationParamsChange: params => {
    searchParams.value.current = params.currentPage ?? 1;
    searchParams.value.size = params.pageSize ?? 10;
  },
  columns: () => [
    { prop: 'id', label: 'ID', width: 80 },
    { prop: 'name', label: '名称', minWidth: 150, showOverflowTooltip: true },
    { prop: 'code', label: '编码', minWidth: 150, showOverflowTooltip: true },
    {
      prop: 'description',
      label: '描述',
      minWidth: 180,
      showOverflowTooltip: true,
      formatter: row => row.description || '-'
    },
    {
      prop: 'status',
      label: '启用状态',
      width: 100,
      align: 'center',
      formatter: row => (
        <ElTag type={(statusTagType[row.status] ?? 'info') as any}>{statusText[row.status] ?? row.status}</ElTag>
      )
    },
    {
      prop: 'publishedVersion',
      label: '当前发布版本',
      width: 120,
      align: 'center',
      formatter: row => (row.publishedVersion ? `v${row.publishedVersion}` : '-')
    },
    {
      prop: 'draftVersion',
      label: '草稿版本',
      width: 100,
      align: 'center',
      formatter: row => (row.draftVersion ? `v${row.draftVersion}` : '-')
    },
    { prop: 'updated_at', label: '更新时间', width: 170, formatter: row => row.updated_at || '-' },
    {
      prop: 'operate',
      label: '操作',
      width: 180,
      align: 'center',
      fixed: 'right',
      formatter: row => (
        <>
          <ElButton type="primary" plain size="small" onClick={() => openEdit(row)}>
            编辑
          </ElButton>
          <ElButton type="warning" plain size="small" onClick={() => openVersions(row)}>
            版本
          </ElButton>
          <ElButton type="danger" plain size="small" onClick={() => onDelete(row)}>
            删除
          </ElButton>
        </>
      )
    }
  ]
});

const hasFilter = computed(() => Boolean(searchParams.value.status || searchParams.value.search));

function resetSearchParams() {
  searchParams.value = getInitSearchParams();
  getDataByPage();
}

/** ============ 新增/编辑抽屉 ============ */

const editVisible = ref(false);
const editingRow = shallowRef<Api.Automation.WorkflowTemplateRecord | null>(null);
const saving = ref(false);

const editForm = reactive({
  name: '',
  code: '',
  description: '',
  status: 'published' as Api.Automation.AtomStatus
});

function openAdd() {
  editingRow.value = null;
  editForm.name = '';
  editForm.code = '';
  editForm.description = '';
  editForm.status = 'published';
  editVisible.value = true;
}

function openEdit(row: Api.Automation.WorkflowTemplateRecord) {
  editingRow.value = row;
  editForm.name = row.name;
  editForm.code = row.code;
  editForm.description = row.description;
  editForm.status = (row.status as Api.Automation.AtomStatus) ?? 'published';
  editVisible.value = true;
}

async function saveEdit() {
  if (!editForm.name.trim() || !editForm.code.trim()) {
    window.$message?.warning('请填写名称和编码');
    return;
  }
  saving.value = true;
  try {
    const payload: Api.Automation.WorkflowTemplatePayload = {
      name: editForm.name.trim(),
      code: editForm.code.trim(),
      description: editForm.description,
      status: editForm.status
    };
    const { error } = editingRow.value
      ? await fetchUpdateWorkflowTemplate(editingRow.value.id, payload)
      : await fetchAddWorkflowTemplate(payload);
    if (!error) {
      window.$message?.success(editingRow.value ? '更新成功' : '新增成功');
      editVisible.value = false;
      getData();
    }
  } finally {
    saving.value = false;
  }
}

async function onDelete(row: Api.Automation.WorkflowTemplateRecord) {
  try {
    await ElMessageBox.confirm(`确认删除工作流模板「${row.name}」？`, '删除确认', {
      type: 'warning',
      confirmButtonText: '确定',
      cancelButtonText: '取消'
    });
  } catch {
    return;
  }

  const { error } = await fetchDeleteWorkflowTemplate(row.id);
  if (!error) {
    window.$message?.success('删除成功');
    getData();
  }
}

/** ============ 版本管理抽屉 ============ */

const versionVisible = ref(false);
const versionTemplate = shallowRef<Api.Automation.WorkflowTemplateRecord | null>(null);
const versionRows = shallowRef<Api.Automation.WorkflowVersionRecord[]>([]);
const versionLoading = ref(false);
const versionOperatingId = ref<number | null>(null);

const versionStatusText: Record<string, string> = {
  draft: '草稿',
  published: '已发布',
  archived: '已归档'
};

const versionStatusTagType: Record<string, string> = {
  draft: 'info',
  published: 'success',
  archived: 'warning'
};

async function loadVersions() {
  if (!versionTemplate.value) return;
  versionLoading.value = true;
  const { data: versions, error } = await fetchGetWorkflowVersions(versionTemplate.value.id);
  if (!error) versionRows.value = [...versions].sort((a, b) => b.version - a.version);
  versionLoading.value = false;
}

function openVersions(row: Api.Automation.WorkflowTemplateRecord) {
  versionTemplate.value = row;
  versionRows.value = [];
  versionVisible.value = true;
  loadVersions();
}

async function onPublishVersion(row: Api.Automation.WorkflowVersionRecord) {
  versionOperatingId.value = row.id;
  try {
    const { error } = await fetchPublishWorkflowVersion(row.id);
    if (!error) {
      window.$message?.success(`v${row.version} 已发布`);
      loadVersions();
    }
  } finally {
    versionOperatingId.value = null;
  }
}

async function onArchiveVersion(row: Api.Automation.WorkflowVersionRecord) {
  versionOperatingId.value = row.id;
  try {
    const { error } = await fetchArchiveWorkflowVersion(row.id);
    if (!error) {
      window.$message?.success(`v${row.version} 已归档`);
      loadVersions();
    }
  } finally {
    versionOperatingId.value = null;
  }
}

/** 创建草稿版本并直接进入步骤编排（版本号由后端自动自增） */
async function onCreateDraft() {
  if (!versionTemplate.value) return;
  versionOperatingId.value = -1;
  try {
    const { data: draft, error } = await fetchCreateWorkflowVersionDraft(versionTemplate.value.id);
    if (!error && draft) {
      window.$message?.success(`已创建草稿 v${draft.version}`);
      versionVisible.value = false;
      goFlowEditor(draft);
    }
  } finally {
    versionOperatingId.value = null;
  }
}

function goFlowEditor(row: Api.Automation.WorkflowVersionRecord) {
  if (!versionTemplate.value) return;
  router.push({
    path: '/task/flow-design',
    query: { templateId: String(versionTemplate.value.id), versionId: String(row.id) }
  });
}

function goRunCreate(row: Api.Automation.WorkflowVersionRecord) {
  router.push({ path: '/task/run-create', query: { versionId: String(row.id) } });
}

/** 已发布版本复制为新草稿：建草稿版本后整体拷贝图协议 */
async function onCopyAsDraft(row: Api.Automation.WorkflowVersionRecord) {
  if (!versionTemplate.value) return;
  versionOperatingId.value = row.id;
  try {
    const { data: draft, error } = await fetchCreateWorkflowVersionDraft(versionTemplate.value.id);
    if (error || !draft) return;
    const { data: graphRes, error: graphError } = await fetchGetWorkflowGraph(row.id);
    if (graphError || !graphRes?.graph) {
      window.$message?.warning(`草稿 v${draft.version} 已创建，但读取 v${row.version} 图内容失败`);
      loadVersions();
      return;
    }
    const { error: saveError } = await fetchUpdateWorkflowGraph(draft.id, graphRes.graph);
    if (!saveError) {
      window.$message?.success(`已复制为草稿 v${draft.version}`);
      loadVersions();
    }
  } finally {
    versionOperatingId.value = null;
  }
}

/** ============ 版本详情抽屉（只读） ============ */

const detailVisible = ref(false);
const detailVersion = shallowRef<Api.Automation.WorkflowVersionRecord | null>(null);
const detailNodes = shallowRef<Api.Automation.WorkflowNodeRecord[]>([]);
const detailEdges = shallowRef<Api.Automation.WorkflowEdgeRecord[]>([]);
const detailLoading = ref(false);

const nodeTypeText: Record<string, string> = {
  start: '开始',
  end: '结束',
  command: '命令',
  script: '脚本',
  playbook: 'Playbook',
  module: '模块',
  api: 'API',
  jenkins: 'Jenkins',
  notify: '通知',
  parallel_gateway: '并行网关',
  parallel_join: '并行汇聚'
};

const failurePolicyText: Record<string, string> = {
  stop: '失败终止',
  ignore: '忽略错误',
  retry: '重试'
};

const editorModeText: Record<string, string> = {
  graph: '图形化设计'
};

const detailNodeMap = computed(() => new Map(detailNodes.value.map(node => [node.id, node])));

function detailNodeLabel(id: number) {
  const node = detailNodeMap.value.get(id);
  return node ? `${node.name || node.node_key}（${node.node_key}）` : `#${id}`;
}

function detailCommandText(row: Api.Automation.WorkflowNodeRecord) {
  if (!row.commandName) return '-';
  return row.command_version ? `${row.commandName}（v${row.command_version}）` : row.commandName;
}

function detailConditionText(row: Api.Automation.WorkflowEdgeRecord) {
  if (row.is_default) return '默认';
  return row.condition_expression || '-';
}

/** JSON 对象转美化的格式化文本，空对象/空值返回空串 */
function prettyJson(value: unknown): string {
  if (!value || (typeof value === 'object' && Object.keys(value as object).length === 0)) return '';
  return JSON.stringify(value, null, 2);
}

async function openVersionDetail(row: Api.Automation.WorkflowVersionRecord) {
  detailVersion.value = row;
  detailNodes.value = [];
  detailEdges.value = [];
  detailVisible.value = true;
  detailLoading.value = true;
  const [nodeRes, edgeRes] = await Promise.all([fetchGetWorkflowNodes(row.id), fetchGetWorkflowEdges(row.id)]);
  if (!nodeRes.error) detailNodes.value = [...nodeRes.data].sort((a, b) => a.order_index - b.order_index);
  if (!edgeRes.error) detailEdges.value = [...edgeRes.data].sort((a, b) => a.order_index - b.order_index);
  detailLoading.value = false;
}
</script>

<template>
  <div class="min-h-500px flex-col-stretch gap-16px overflow-hidden lt-sm:overflow-auto">
    <ElCard class="card-wrapper">
      <ElForm :model="searchParams" label-width="70px" inline @submit.prevent>
        <ElFormItem label="状态">
          <ElSelect v-model="searchParams.status" clearable placeholder="全部" class="w-140px">
            <ElOption v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="关键词">
          <ElInput
            v-model="searchParams.search"
            clearable
            placeholder="名称/编码"
            class="w-200px"
            @keyup.enter="getDataByPage()"
          />
        </ElFormItem>
        <ElFormItem>
          <ElButton type="primary" @click="getDataByPage()">查询</ElButton>
          <ElButton :disabled="!hasFilter" @click="resetSearchParams">重置</ElButton>
        </ElFormItem>
      </ElForm>
    </ElCard>

    <ElCard class="card-wrapper sm:flex-1-hidden">
      <template #header>
        <div class="flex items-center justify-between">
          <p>工作流模板</p>
          <div class="flex items-center gap-8px">
            <ElButton type="primary" @click="openAdd">新增模板</ElButton>
            <TableHeaderOperation
              v-model:columns="columnChecks"
              :loading="loading"
              :show-add="false"
              :show-batch-delete="false"
              @refresh="getData"
            />
          </div>
        </div>
      </template>
      <div class="h-[calc(100%-52px)]">
        <ElTable v-loading="loading" height="100%" border class="sm:h-full" :data="data" row-key="id">
          <ElTableColumn v-for="col in columns" :key="col.prop" v-bind="col" />
        </ElTable>
      </div>
      <div class="mt-20px flex justify-end">
        <ElPagination
          v-if="mobilePagination.total"
          layout="total,prev,pager,next,sizes"
          v-bind="mobilePagination"
          @current-change="mobilePagination['current-change']"
          @size-change="mobilePagination['size-change']"
        />
      </div>
    </ElCard>

    <ElDrawer v-model="editVisible" :title="editingRow ? '编辑模板' : '新增模板'" size="480px">
      <ElForm :model="editForm" label-width="80px">
        <ElFormItem label="名称" required>
          <ElInput v-model="editForm.name" placeholder="请输入模板名称" />
        </ElFormItem>
        <ElFormItem label="编码" required>
          <ElInput v-model="editForm.code" placeholder="唯一编码，如 deploy_app" />
        </ElFormItem>
        <ElFormItem label="描述">
          <ElInput v-model="editForm.description" type="textarea" :rows="3" placeholder="模板用途说明" />
        </ElFormItem>
        <ElFormItem label="状态">
          <ElSelect v-model="editForm.status" class="w-full">
            <ElOption v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
          </ElSelect>
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="editVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="saving" @click="saveEdit">保存</ElButton>
      </template>
    </ElDrawer>

    <ElDrawer v-model="versionVisible" :title="`版本管理 - ${versionTemplate?.name ?? ''}`" size="840px">
      <div class="mb-12px flex justify-end gap-8px">
        <ElButton type="primary" :loading="versionOperatingId === -1" @click="onCreateDraft">创建草稿版本</ElButton>
        <ElButton :loading="versionLoading" @click="loadVersions">刷新</ElButton>
      </div>
      <ElTable v-loading="versionLoading" :data="versionRows" border row-key="id">
        <ElTableColumn label="版本号" width="90" align="center">
          <template #default="{ row }">v{{ row.version }}</template>
        </ElTableColumn>
        <ElTableColumn label="状态" width="100" align="center">
          <template #default="{ row }">
            <ElTag :type="(versionStatusTagType[row.status] ?? 'info') as any">
              {{ versionStatusText[row.status] ?? row.status }}
            </ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn label="发布时间" min-width="170">
          <template #default="{ row }">{{ row.publishedAt || '-' }}</template>
        </ElTableColumn>
        <ElTableColumn label="创建时间" min-width="170">
          <template #default="{ row }">{{ row.createdAt || '-' }}</template>
        </ElTableColumn>
        <ElTableColumn label="操作" width="300" align="center" fixed="right">
          <template #default="{ row }">
            <ElButton type="primary" plain size="small" @click="openVersionDetail(row)">查看</ElButton>
            <ElButton v-if="row.status === 'draft'" type="primary" size="small" @click="goFlowEditor(row)">
              编排
            </ElButton>
            <ElButton
              v-if="row.status === 'draft'"
              type="success"
              plain
              size="small"
              :loading="versionOperatingId === row.id"
              @click="onPublishVersion(row)"
            >
              发布
            </ElButton>
            <ElButton v-if="row.status === 'published'" type="success" size="small" @click="goRunCreate(row)">
              执行
            </ElButton>
            <ElButton
              v-if="row.status === 'published'"
              type="warning"
              plain
              size="small"
              :loading="versionOperatingId === row.id"
              @click="onCopyAsDraft(row)"
            >
              复制为新草稿
            </ElButton>
            <ElButton
              v-if="row.status === 'published'"
              type="danger"
              plain
              size="small"
              :loading="versionOperatingId === row.id"
              @click="onArchiveVersion(row)"
            >
              归档
            </ElButton>
          </template>
        </ElTableColumn>
      </ElTable>
    </ElDrawer>

    <ElDrawer v-model="detailVisible" :title="`版本详情 - v${detailVersion?.version ?? ''}`" size="760px">
      <div v-loading="detailLoading" class="flex-col-stretch gap-12px overflow-hidden">
        <ElDescriptions :column="2" border>
          <ElDescriptionsItem label="版本号">v{{ detailVersion?.version }}</ElDescriptionsItem>
          <ElDescriptionsItem label="状态">
            <ElTag :type="(versionStatusTagType[detailVersion?.status ?? ''] ?? 'info') as any">
              {{ versionStatusText[detailVersion?.status ?? ''] ?? detailVersion?.status }}
            </ElTag>
          </ElDescriptionsItem>
          <ElDescriptionsItem label="编辑模式">
            {{ editorModeText[detailVersion?.editorMode ?? ''] ?? detailVersion?.editorMode }}
          </ElDescriptionsItem>
          <ElDescriptionsItem label="节点数量">{{ detailNodes.length }}</ElDescriptionsItem>
          <ElDescriptionsItem label="发布时间">{{ detailVersion?.publishedAt || '-' }}</ElDescriptionsItem>
          <ElDescriptionsItem label="创建时间">{{ detailVersion?.createdAt || '-' }}</ElDescriptionsItem>
        </ElDescriptions>

        <ElCard shadow="never" class="card-wrapper">
          <template #header>
            <span>输入参数 Schema</span>
          </template>
          <CodeEditor
            :model-value="prettyJson(detailVersion?.inputSchema)"
            language="plaintext"
            readonly
            height="140px"
          />
        </ElCard>

        <ElCard v-if="prettyJson(detailVersion?.globalVars)" shadow="never" class="card-wrapper">
          <template #header>
            <span>全局变量</span>
          </template>
          <CodeEditor
            :model-value="prettyJson(detailVersion?.globalVars)"
            language="plaintext"
            readonly
            height="140px"
          />
        </ElCard>

        <ElCard v-if="prettyJson(detailVersion?.targetSelectorSchema)" shadow="never" class="card-wrapper">
          <template #header>
            <span>目标选择器 Schema</span>
          </template>
          <CodeEditor
            :model-value="prettyJson(detailVersion?.targetSelectorSchema)"
            language="plaintext"
            readonly
            height="140px"
          />
        </ElCard>

        <ElCard shadow="never" class="card-wrapper">
          <template #header>
            <span>流程节点</span>
          </template>
          <ElTable :data="detailNodes" border max-height="320" row-key="id">
            <ElTableColumn prop="order_index" label="顺序" width="70" align="center" />
            <ElTableColumn prop="node_key" label="节点 Key" min-width="140" show-overflow-tooltip />
            <ElTableColumn prop="name" label="名称" min-width="120" show-overflow-tooltip />
            <ElTableColumn label="类型" width="90" align="center">
              <template #default="{ row }">{{ nodeTypeText[row.node_type] ?? row.node_type }}</template>
            </ElTableColumn>
            <ElTableColumn label="命令版本" min-width="160" show-overflow-tooltip>
              <template #default="{ row }">{{ detailCommandText(row) }}</template>
            </ElTableColumn>
            <ElTableColumn label="失败策略" width="100" align="center">
              <template #default="{ row }">{{ failurePolicyText[row.failure_policy] ?? row.failure_policy }}</template>
            </ElTableColumn>
            <ElTableColumn label="超时(秒)" width="90" align="center">
              <template #default="{ row }">{{ row.timeout_seconds ?? '-' }}</template>
            </ElTableColumn>
          </ElTable>
        </ElCard>

        <ElCard v-if="detailEdges.length" shadow="never" class="card-wrapper">
          <template #header>
            <span>流转连线</span>
          </template>
          <ElTable :data="detailEdges" border max-height="260" row-key="id">
            <ElTableColumn label="流转路径" min-width="220" show-overflow-tooltip>
              <template #default="{ row }">
                {{ detailNodeLabel(row.source_node) }} → {{ detailNodeLabel(row.target_node) }}
              </template>
            </ElTableColumn>
            <ElTableColumn label="条件" min-width="140" show-overflow-tooltip>
              <template #default="{ row }">{{ detailConditionText(row) }}</template>
            </ElTableColumn>
            <ElTableColumn label="默认连线" width="90" align="center">
              <template #default="{ row }">
                <ElTag size="small" :type="(row.is_default ? 'success' : 'info') as any">
                  {{ row.is_default ? '是' : '否' }}
                </ElTag>
              </template>
            </ElTableColumn>
          </ElTable>
        </ElCard>
      </div>
    </ElDrawer>
  </div>
</template>
