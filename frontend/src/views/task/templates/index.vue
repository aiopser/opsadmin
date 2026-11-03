<script setup lang="tsx">
import { computed, reactive, ref, shallowRef } from 'vue';
import { useRouter } from 'vue-router';
import {
  fetchAddWorkflowTemplate,
  fetchArchiveWorkflowVersion,
  fetchCreateWorkflowVersionDraft,
  fetchDeleteWorkflowTemplate,
  fetchDeleteWorkflowVersion,
  fetchGetNotificationTemplate,
  fetchGetNotificationTemplateList,
  fetchGetWorkflowGraph,
  fetchGetWorkflowTemplateList,
  fetchGetWorkflowVersions,
  fetchPublishWorkflowVersion,
  fetchUpdateWorkflowGraph,
  fetchUpdateWorkflowTemplate
} from '@/service/api';
import { defaultTransform, useUIPaginatedTable } from '@/hooks/common/table';
import { useAuth } from '@/hooks/business/auth';

defineOptions({ name: 'TaskTemplates' });

const router = useRouter();
const { hasAuth } = useAuth();

/** ============ 搜索 ============ */

/** 模板自身状态与版本的草稿/发布/归档状态分别管理。 */
const statusOptions = [
  { value: 'published', label: '启用' },
  { value: 'draft', label: '未启用' },
  { value: 'disabled', label: '停用' }
];

const statusText: Record<string, string> = {
  draft: '未启用',
  published: '启用',
  disabled: '停用'
};

const statusTagType: Record<string, UI.ThemeColor> = {
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

/** 「更多」下拉：编辑信息 / 版本管理 / 执行历史 / 删除 */
function onMoreCommand(command: string, row: Api.Automation.WorkflowTemplateRecord) {
  switch (command) {
    case 'edit':
      openEdit(row);
      break;
    case 'versions':
      openVersions(row);
      break;
    case 'history':
      router.push({
        name: 'task_execution-history',
        query: { workflowId: String(row.id), workflowName: row.name }
      });
      break;
    case 'start':
      startFromTemplate(row);
      break;
    case 'delete':
      onDelete(row);
      break;
    default:
      break;
  }
}

async function startFromTemplate(row: Api.Automation.WorkflowTemplateRecord) {
  if (row.status !== 'published') return;
  const { data: versions, error } = await fetchGetWorkflowVersions(row.id);
  if (error) return;
  const published = versions.filter(item => item.status === 'published').sort((a, b) => b.version - a.version)[0];
  if (!published) {
    window.$message?.warning('模板没有可执行的已发布版本');
    return;
  }
  router.push({ name: 'task_run-create', query: { versionId: String(published.id) } });
}

function startFromVersion(version: Api.Automation.WorkflowVersionRecord) {
  router.push({ name: 'task_run-create', query: { versionId: String(version.id) } });
}

/** ============ 行内直达编排 ============ */

/** 有草稿直接进入；没有草稿时先选择从已发布版本克隆或创建空白草稿。 */
const orchestrateLoadingId = ref<number | null>(null);

async function onQuickOrchestrate(row: Api.Automation.WorkflowTemplateRecord) {
  orchestrateLoadingId.value = row.id;
  try {
    const { data: versions, error } = await fetchGetWorkflowVersions(row.id);
    if (error) return;
    const draft = versions.filter(item => item.status === 'draft').sort((a, b) => b.version - a.version)[0];
    if (draft) {
      router.push({ name: 'task_flow-design', query: { templateId: String(row.id), versionId: String(draft.id) } });
      return;
    }
    openVersions(row, versions);
  } finally {
    orchestrateLoadingId.value = null;
  }
}

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
      label: '模板状态',
      width: 100,
      align: 'center',
      formatter: row => <ElTag type={statusTagType[row.status] ?? 'info'}>{statusText[row.status] ?? row.status}</ElTag>
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
      label: '可编辑草稿',
      width: 140,
      align: 'center',
      formatter: row =>
        row.draftVersion ? (
          <ElTag type="warning">草稿 v{row.draftVersion}</ElTag>
        ) : (
          <span class="text-gray-500">未创建</span>
        )
    },
    { prop: 'updatedAt', label: '更新时间', width: 170, formatter: row => row.updatedAt || '-' },
    {
      prop: 'operate',
      label: '操作',
      width: 170,
      align: 'center',
      fixed: 'right',
      formatter: row => (
        <div class="flex items-center justify-center gap-8px [&>.el-button+.el-button]:!ml-0">
          <ElTooltip content={row.draftVersion ? '继续编排现有草稿' : '选择版本来源后开始编排'} placement="top">
            <ElButton
              type="primary"
              plain
              size="small"
              class="!w-64px"
              loading={orchestrateLoadingId.value === row.id}
              onClick={() => onQuickOrchestrate(row)}
            >
              编排
            </ElButton>
          </ElTooltip>
          <ElDropdown onCommand={(command: string) => onMoreCommand(command, row)}>
            {{
              default: () => (
                <ElButton plain size="small" class="!w-64px">
                  更多 ∨
                </ElButton>
              ),
              dropdown: () => (
                <ElDropdownMenu>
                  <ElDropdownItem command="edit">编辑信息</ElDropdownItem>
                  <ElDropdownItem command="versions">版本管理</ElDropdownItem>
                  <ElDropdownItem
                    v-if="row.status === 'published' && row.publishedVersion && hasAuth('jobs.workflow_run:create')"
                    command="start"
                  >
                    发起执行
                  </ElDropdownItem>
                  <ElDropdownItem command="history">执行历史</ElDropdownItem>
                  <ElDropdownItem divided command="delete">
                    删除
                  </ElDropdownItem>
                </ElDropdownMenu>
              )
            }}
          </ElDropdown>
        </div>
      )
    }
  ]
});

function resetSearchParams() {
  searchParams.value = getInitSearchParams();
  getDataByPage();
}

/** ============ 新增/编辑抽屉 ============ */

const editVisible = ref(false);
const alertTemplates = shallowRef<Api.Automation.NotificationTemplateRecord[]>([]);
const editingRow = shallowRef<Api.Automation.WorkflowTemplateRecord | null>(null);
const saving = ref(false);
const editFormRef = ref();

const editForm = reactive({
  name: '',
  code: '',
  description: '',
  alertTemplateId: null as number | null,
  alertReceivers: '',
  status: 'published' as Api.Automation.AtomStatus
});

const editFormRules = {
  name: [{ required: true, message: '请输入模板名称', trigger: 'blur' }],
  code: [{ required: true, message: '请输入编码', trigger: 'blur' }]
};

function openAdd() {
  loadAlertTemplates();
  editingRow.value = null;
  editForm.name = '';
  editForm.code = '';
  editForm.description = '';
  editForm.alertTemplateId = null;
  editForm.alertReceivers = '';
  editForm.status = 'published';
  editVisible.value = true;
}

function openEdit(row: Api.Automation.WorkflowTemplateRecord) {
  loadAlertTemplates('', row.failureAlert?.templateId);
  editingRow.value = row;
  editForm.name = row.name;
  editForm.code = row.code;
  editForm.description = row.description;
  editForm.alertTemplateId = row.failureAlert?.templateId ?? null;
  editForm.alertReceivers = row.failureAlert?.receivers ?? '';
  editForm.status = (row.status as Api.Automation.AtomStatus) ?? 'published';
  editVisible.value = true;
}

async function saveEdit() {
  await editFormRef.value?.validate();

  saving.value = true;
  try {
    const payload: Api.Automation.WorkflowTemplatePayload = {
      name: editForm.name.trim(),
      code: editForm.code.trim(),
      description: editForm.description,
      failureAlert: editForm.alertTemplateId
        ? { templateId: editForm.alertTemplateId, receivers: editForm.alertReceivers.trim() }
        : {},
      status: editForm.status
    };
    const { error } = editingRow.value
      ? await fetchUpdateWorkflowTemplate(editingRow.value.id, payload)
      : await fetchAddWorkflowTemplate(payload);
    if (!error) {
      window.$notification?.success(editingRow.value ? '更新成功' : '新增成功');
      editVisible.value = false;
      getData();
    }
  } finally {
    saving.value = false;
  }
}

let alertSearchSequence = 0;
const alertLoading = ref(false);

async function loadAlertTemplates(search = '', selectedId = editForm.alertTemplateId ?? undefined) {
  alertSearchSequence += 1;
  const sequence = alertSearchSequence;
  alertLoading.value = true;
  try {
    const [listResult, selectedResult] = await Promise.all([
      fetchGetNotificationTemplateList({ current: 1, size: 20, search: search.trim() || null }),
      selectedId ? fetchGetNotificationTemplate(selectedId) : Promise.resolve(null)
    ]);
    if (sequence !== alertSearchSequence || listResult.error || !listResult.data) return;
    const selected = selectedResult && !selectedResult.error ? selectedResult.data : null;
    const options = listResult.data.records.filter(item => item.isActive);
    alertTemplates.value =
      selected && !options.some(item => item.id === selected.id) ? [selected, ...options] : options;
  } finally {
    if (sequence === alertSearchSequence) alertLoading.value = false;
  }
}

async function onDelete(row: Api.Automation.WorkflowTemplateRecord) {
  try {
    await ElMessageBox.confirm(`确认删除流程模板「${row.name}」？`, '删除确认', {
      type: 'warning',
      confirmButtonText: '确定',
      cancelButtonText: '取消'
    });
  } catch {
    return;
  }

  const { error } = await fetchDeleteWorkflowTemplate(row.id);
  if (!error) {
    window.$notification?.success('删除成功');
    getData();
  }
}

/** ============ 版本管理抽屉 ============ */

const versionVisible = ref(false);
const versionTemplate = shallowRef<Api.Automation.WorkflowTemplateRecord | null>(null);
const versionRows = shallowRef<Api.Automation.WorkflowVersionRecord[]>([]);
const versionLoading = ref(false);
const versionOperatingId = ref<number | null>(null);
let versionRequestId = 0;
const hasPublishedVersion = computed(() => versionRows.value.some(row => row.status === 'published'));

const versionStatusText: Record<string, string> = {
  draft: '草稿',
  published: '已发布',
  archived: '已归档'
};

const versionStatusTagType: Record<string, UI.ThemeColor> = {
  draft: 'info',
  published: 'success',
  archived: 'warning'
};

async function loadVersions() {
  if (!versionTemplate.value) return;
  const templateId = versionTemplate.value.id;
  versionRequestId += 1;
  const requestId = versionRequestId;
  versionLoading.value = true;
  try {
    const { data: versions, error } = await fetchGetWorkflowVersions(templateId);
    if (requestId === versionRequestId && versionTemplate.value?.id === templateId && !error) {
      versionRows.value = [...versions].sort((a, b) => b.version - a.version);
    }
  } finally {
    if (requestId === versionRequestId) versionLoading.value = false;
  }
}

function openVersions(row: Api.Automation.WorkflowTemplateRecord, versions?: Api.Automation.WorkflowVersionRecord[]) {
  versionRequestId += 1;
  versionTemplate.value = row;
  versionRows.value = versions ? [...versions].sort((a, b) => b.version - a.version) : [];
  versionVisible.value = true;
  if (!versions) loadVersions();
}

function editVersionTemplate() {
  if (!versionTemplate.value) return;
  const template = versionTemplate.value;
  versionVisible.value = false;
  openEdit(template);
}

async function onPublishVersion(row: Api.Automation.WorkflowVersionRecord) {
  try {
    await ElMessageBox.confirm(
      `确认发布草稿 v${row.version}？发布后该版本不可再修改，原发布版本将自动归档。`,
      '发布确认',
      {
        type: 'warning',
        confirmButtonText: '发布',
        cancelButtonText: '取消'
      }
    );
  } catch {
    return;
  }
  versionOperatingId.value = row.id;
  try {
    const { error } = await fetchPublishWorkflowVersion(row.id);
    if (!error) {
      window.$notification?.success(`v${row.version} 已发布`);
      loadVersions();
      getData();
    }
  } finally {
    versionOperatingId.value = null;
  }
}

async function onArchiveVersion(row: Api.Automation.WorkflowVersionRecord) {
  try {
    await ElMessageBox.confirm(`确认归档流程版本 v${row.version}？归档后将不能用于新执行。`, '归档确认', {
      type: 'warning',
      confirmButtonText: '归档',
      cancelButtonText: '取消'
    });
  } catch {
    return;
  }
  versionOperatingId.value = row.id;
  try {
    const { error } = await fetchArchiveWorkflowVersion(row.id);
    if (!error) {
      window.$notification?.success(`v${row.version} 已归档`);
      loadVersions();
      getData();
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
    if (error) return;
    if (!draft) {
      window.$message?.error('创建草稿版本失败');
      return;
    }
    window.$notification?.success(`已创建草稿 v${draft.version}`);
    versionVisible.value = false;
    goFlowEditor(draft);
    getData();
  } finally {
    versionOperatingId.value = null;
  }
}

function goFlowEditor(row: Api.Automation.WorkflowVersionRecord) {
  if (!versionTemplate.value) return;
  router.push({
    name: 'task_flow-design',
    query: { templateId: String(versionTemplate.value.id), versionId: String(row.id) }
  });
}

/** 先读取原版本，再创建草稿，避免读取失败后留下空白版本。 */
async function onCopyAsDraft(row: Api.Automation.WorkflowVersionRecord) {
  if (!versionTemplate.value) return;
  versionOperatingId.value = row.id;
  try {
    const { data: graphRes, error: graphError } = await fetchGetWorkflowGraph(row.id);
    if (graphError) return; // 请求失败由全局错误处理提示
    if (!graphRes?.graph) {
      window.$message?.error('原版本没有可克隆的流程图');
      return;
    }
    const { data: draft, error } = await fetchCreateWorkflowVersionDraft(versionTemplate.value.id);
    if (error) return;
    if (!draft) {
      window.$message?.error('创建草稿版本失败');
      return;
    }
    const { error: saveError } = await fetchUpdateWorkflowGraph(draft.id, graphRes.graph);
    if (!saveError) {
      window.$notification?.success(`已克隆为草稿 v${draft.version}`);
    } else {
      window.$message?.warning(`草稿 v${draft.version} 已创建，但复制内容失败；请在版本管理中处理该空白草稿`);
    }
    loadVersions();
    getData();
  } finally {
    versionOperatingId.value = null;
  }
}

function onVersionCommand(command: string, row: Api.Automation.WorkflowVersionRecord) {
  switch (command) {
    case 'publish':
      onPublishVersion(row);
      break;
    case 'start':
      startFromVersion(row);
      break;
    case 'clone':
      onCopyAsDraft(row);
      break;
    case 'archive':
      onArchiveVersion(row);
      break;
    case 'delete':
      onDeleteVersion(row);
      break;
    default:
      break;
  }
}

/** 删除草稿版本（仅草稿可删，删除前二次确认） */
async function onDeleteVersion(row: Api.Automation.WorkflowVersionRecord) {
  try {
    await ElMessageBox.confirm(`确认删除草稿 v${row.version}？删除后不可恢复`, '删除确认', {
      type: 'warning',
      confirmButtonText: '确定',
      cancelButtonText: '取消'
    });
  } catch {
    return;
  }

  versionOperatingId.value = row.id;
  try {
    const { error } = await fetchDeleteWorkflowVersion(row.id);
    if (!error) {
      window.$notification?.success(`v${row.version} 已删除`);
      loadVersions();
      getData();
    }
  } finally {
    versionOperatingId.value = null;
  }
}
</script>

<template>
  <div class="min-h-500px flex-col-stretch gap-16px overflow-hidden lt-sm:overflow-auto">
    <SearchPanel @reset="resetSearchParams" @search="getDataByPage">
      <ElForm :model="searchParams" label-width="80px" @submit.prevent="getDataByPage">
        <ElFormItem label="状态">
          <ElSelect v-model="searchParams.status" clearable placeholder="全部">
            <ElOption v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="关键词">
          <ElInput v-model="searchParams.search" clearable placeholder="名称/编码" @keyup.enter="getDataByPage()" />
        </ElFormItem>
      </ElForm>
    </SearchPanel>

    <ElCard class="card-wrapper sm:flex-1-hidden">
      <template #header>
        <div class="flex items-center justify-between">
          <div class="flex items-baseline gap-8px">
            <p>流程模板</p>
            <span class="text-13px text-gray-500">模板维护流程元信息，版本承载可执行的步骤编排</span>
          </div>
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
      <ElForm
        ref="editFormRef"
        :model="editForm"
        :rules="editFormRules"
        label-width="96px"
        label-suffix="："
        require-asterisk-position="left"
      >
        <ElFormItem label="名称" prop="name">
          <ElInput v-model="editForm.name" placeholder="请输入模板名称" />
        </ElFormItem>
        <ElFormItem prop="code">
          <template #label>
            <FormLabelHelp label="编码" :help="['模板唯一编码，全站不可重复，建议小写下划线命名，如 deploy_app。']" />
          </template>
          <ElInput v-model="editForm.code" placeholder="唯一编码，如 deploy_app" />
        </ElFormItem>
        <ElFormItem label="描述">
          <ElInput v-model="editForm.description" type="textarea" :rows="3" placeholder="模板用途说明" />
        </ElFormItem>
        <ElFormItem>
          <template #label>
            <FormLabelHelp
              label="模板状态"
              :help="['模板状态与版本状态分别管理。', '未启用的模板即使已有发布版本，也不会在本页提供发起执行入口。']"
            />
          </template>
          <ElSelect v-model="editForm.status" class="w-full">
            <ElOption v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem>
          <template #label>
            <FormLabelHelp label="失败告警" :help="['流程失败或超时时发送通知；任务单可单独覆盖。']" />
          </template>
          <ElSelect
            v-model="editForm.alertTemplateId"
            clearable
            filterable
            remote
            :remote-method="loadAlertTemplates"
            :loading="alertLoading"
            class="w-full"
            placeholder="搜索通知模板；留空不发送"
          >
            <ElOption
              v-for="item in alertTemplates"
              :key="item.id"
              :label="item.isActive ? item.name : `${item.name}（已停用）`"
              :value="item.id"
              :disabled="!item.isActive"
            />
          </ElSelect>
        </ElFormItem>
        <ElFormItem v-if="editForm.alertTemplateId">
          <template #label>
            <FormLabelHelp label="接收人" :help="['可选；多个用逗号分隔，留空使用通知模板配置的接收人。']" />
          </template>
          <ElInput
            v-model="editForm.alertReceivers"
            maxlength="1024"
            placeholder="可选；逗号分隔，留空使用通知模板配置"
          />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="editVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="saving" @click="saveEdit">确定</ElButton>
      </template>
    </ElDrawer>

    <ElDrawer v-model="versionVisible" :title="`版本管理 · ${versionTemplate?.name ?? ''}`" size="min(840px, 100%)">
      <div class="mb-20px flex flex-wrap items-center justify-between gap-12px">
        <div class="min-w-0 flex-1">
          <div class="flex items-center gap-8px">
            <span class="text-14px">模板状态</span>
            <ElTag size="small" :type="statusTagType[versionTemplate?.status ?? ''] ?? 'info'">
              {{ statusText[versionTemplate?.status ?? ''] ?? versionTemplate?.status }}
            </ElTag>
          </div>
          <p class="mt-4px text-12px text-gray-500">模板的启用状态与版本的发布状态分别管理。</p>
        </div>
        <ElButton
          type="primary"
          plain
          size="small"
          class="!h-32px"
          :disabled="versionOperatingId !== null"
          @click="editVersionTemplate"
        >
          编辑状态
        </ElButton>
      </div>

      <div class="mb-12px flex flex-wrap items-center justify-between gap-12px">
        <div class="min-w-0 flex-1">
          <div class="flex items-baseline gap-8px">
            <span class="text-14px">流程版本</span>
            <span class="text-12px text-gray-500 tabular-nums">
              {{ versionLoading ? '加载中' : `${versionRows.length} 个版本` }}
            </span>
          </div>
          <p class="mt-4px text-12px text-gray-500">
            {{
              hasPublishedVersion
                ? '沿用现有流程可从已发布版本克隆；全新流程可创建空白草稿。'
                : '创建草稿并完成步骤编排后，再发布可执行版本。'
            }}
          </p>
        </div>
        <div class="flex shrink-0 items-center gap-8px">
          <ElButton
            size="small"
            class="!h-32px"
            :loading="versionLoading"
            :disabled="versionOperatingId !== null"
            @click="loadVersions"
          >
            刷新
          </ElButton>
          <ElButton
            type="primary"
            size="small"
            class="!h-32px"
            :loading="versionOperatingId === -1"
            :disabled="versionOperatingId !== null && versionOperatingId !== -1"
            @click="onCreateDraft"
          >
            新建空白草稿
          </ElButton>
        </div>
      </div>
      <ElTable v-loading="versionLoading" :data="versionRows" border row-key="id">
        <ElTableColumn label="版本号" width="90" align="center">
          <template #default="{ row }">
            <span class="tabular-nums">v{{ row.version }}</span>
          </template>
        </ElTableColumn>
        <ElTableColumn label="状态" width="100" align="center">
          <template #default="{ row }">
            <ElTag :type="versionStatusTagType[row.status] ?? 'info'">
              {{ versionStatusText[row.status] ?? row.status }}
            </ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn label="创建时间" min-width="170">
          <template #default="{ row }">
            <span class="tabular-nums">{{ row.createdAt || '-' }}</span>
          </template>
        </ElTableColumn>
        <ElTableColumn label="发布时间" min-width="170">
          <template #default="{ row }">
            <span class="tabular-nums">{{ row.publishedAt || '-' }}</span>
          </template>
        </ElTableColumn>
        <ElTableColumn label="操作" width="128" align="center" fixed="right">
          <template #default="{ row }">
            <div class="flex items-center justify-center gap-4px">
              <ElButton
                type="primary"
                link
                size="small"
                class="!h-32px !w-44px"
                :disabled="versionOperatingId !== null"
                @click="goFlowEditor(row)"
              >
                {{ row.status === 'draft' ? '编排' : '查看' }}
              </ElButton>
              <ElDropdown
                v-if="row.status !== 'archived'"
                :disabled="versionOperatingId !== null"
                @command="onVersionCommand($event, row)"
              >
                <ElButton link size="small" class="!h-32px !w-52px">更多 ∨</ElButton>
                <template #dropdown>
                  <ElDropdownMenu>
                    <template v-if="row.status === 'draft'">
                      <ElDropdownItem command="publish">发布版本</ElDropdownItem>
                      <ElDropdownItem divided command="delete">删除草稿</ElDropdownItem>
                    </template>
                    <template v-else>
                      <ElDropdownItem
                        v-if="versionTemplate?.status === 'published' && hasAuth('jobs.workflow_run:create')"
                        command="start"
                      >
                        发起执行
                      </ElDropdownItem>
                      <ElDropdownItem command="clone">克隆为草稿</ElDropdownItem>
                      <ElDropdownItem divided command="archive">归档版本</ElDropdownItem>
                    </template>
                  </ElDropdownMenu>
                </template>
              </ElDropdown>
            </div>
          </template>
        </ElTableColumn>
        <template #empty>
          <ElEmpty v-if="!versionLoading" description="暂无流程版本" :image-size="80">
            <ElButton type="primary" :disabled="versionLoading || versionOperatingId !== null" @click="onCreateDraft">
              新建空白草稿
            </ElButton>
          </ElEmpty>
        </template>
      </ElTable>
    </ElDrawer>
  </div>
</template>
