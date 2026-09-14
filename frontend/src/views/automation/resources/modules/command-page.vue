<script setup lang="tsx">
import { computed, ref } from 'vue';
import {
  fetchAddCommand,
  fetchAddCommandVersion,
  fetchArchiveCommandVersion,
  fetchDeleteCommand,
  fetchGetCommandList,
  fetchGetCommandVersions,
  fetchPublishCommandVersion,
  fetchUpdateCommand,
  fetchUpdateCommandVersion
} from '@/service/api';
import { defaultTransform, useUIPaginatedTable } from '@/hooks/common/table';
import CodeEditor from '@/components/common/code-editor/index.vue';

defineOptions({ name: 'AutomationCommandResourcePage' });

const props = defineProps<{
  /** 固定的资源类型（command/script/playbook/module） */
  resourceKind: Api.Automation.ResourceKind;
  /** 页面标题 */
  title: string;
}>();

/** ============ 枚举文案 ============ */

const statusOptions = [
  { value: 'draft', label: '草稿' },
  { value: 'published', label: '已发布' },
  { value: 'disabled', label: '已停用' }
];

const riskLevelOptions = [
  { value: 'low', label: '低风险' },
  { value: 'medium', label: '中风险' },
  { value: 'high', label: '高风险' }
];

const commandTypeOptions = [
  { value: 'linux_shell', label: 'Linux Shell' },
  { value: 'windows_powershell', label: 'PowerShell' },
  { value: 'python', label: 'Python' },
  { value: 'http_request', label: 'HTTP 请求' },
  { value: 'ansible_module', label: 'Ansible Module' },
  { value: 'playbook', label: 'Playbook' }
];

const statusText: Record<string, string> = Object.fromEntries(statusOptions.map(item => [item.value, item.label]));
const riskLevelText: Record<string, string> = Object.fromEntries(
  riskLevelOptions.map(item => [item.value, item.label])
);
const commandTypeText: Record<string, string> = Object.fromEntries(
  commandTypeOptions.map(item => [item.value, item.label])
);
const versionStatusText: Record<string, string> = { ...statusText, archived: '已归档' };

function getStatusTagType(status: string) {
  if (status === 'published') return 'success' as const;
  if (status === 'disabled') return 'danger' as const;
  return 'info' as const;
}

function getRiskTagType(riskLevel: string) {
  if (riskLevel === 'high') return 'danger' as const;
  if (riskLevel === 'medium') return 'warning' as const;
  return 'success' as const;
}

/** ============ 搜索 ============ */

function getInitSearchParams(): Api.Automation.CommandSearchParams {
  return {
    current: 1,
    size: 10,
    search: null,
    status: null,
    riskLevel: null
  };
}

const searchParams = ref<Api.Automation.CommandSearchParams>(getInitSearchParams());

/** ============ 列表 ============ */

const { columns, columnChecks, data, getData, getDataByPage, loading, mobilePagination } = useUIPaginatedTable({
  paginationProps: {
    currentPage: searchParams.value.current,
    pageSize: searchParams.value.size
  },
  api: () => fetchGetCommandList(searchParams.value),
  transform: response => defaultTransform(response),
  onPaginationParamsChange: params => {
    searchParams.value.current = params.currentPage ?? 1;
    searchParams.value.size = params.pageSize ?? 10;
  },
  columns: () => [
    { prop: 'id', label: 'ID', width: 70 },
    { prop: 'name', label: '名称', minWidth: 150, showOverflowTooltip: true },
    { prop: 'code', label: '编码', minWidth: 130, showOverflowTooltip: true },
    { prop: 'category', label: '分类', width: 110, formatter: row => row.category || '-' },
    {
      prop: 'risk_level',
      label: '风险等级',
      width: 100,
      align: 'center',
      formatter: row => (
        <ElTag type={getRiskTagType(row.risk_level)}>{riskLevelText[row.risk_level] ?? row.risk_level}</ElTag>
      )
    },
    {
      prop: 'status',
      label: '状态',
      width: 90,
      align: 'center',
      formatter: row => <ElTag type={getStatusTagType(row.status)}>{statusText[row.status] ?? row.status}</ElTag>
    },
    {
      prop: 'versionInfo',
      label: '版本信息',
      minWidth: 200,
      formatter: row =>
        row.publishedVersion !== null
          ? `已发布 v${row.publishedVersion} · 最新 v${row.latestVersion ?? '-'} · 共 ${row.versionCount} 版`
          : `未发布 · 最新 v${row.latestVersion ?? '-'} · 共 ${row.versionCount} 版`
    },
    { prop: 'updated_at', label: '更新时间', width: 170, formatter: row => row.updated_at || '-' },
    {
      prop: 'operate',
      label: '操作',
      width: 200,
      align: 'center',
      fixed: 'right',
      formatter: row => (
        <>
          <ElButton type="primary" plain size="small" onClick={() => openOperateDrawer('edit', row)}>
            编辑
          </ElButton>
          <ElButton type="warning" plain size="small" onClick={() => openVersionDrawer(row)}>
            版本
          </ElButton>
          <ElButton type="danger" plain size="small" onClick={() => handleDelete(row)}>
            删除
          </ElButton>
        </>
      )
    }
  ]
});

const hasFilter = computed(() =>
  Boolean(searchParams.value.search || searchParams.value.status || searchParams.value.riskLevel)
);

function resetSearchParams() {
  searchParams.value = getInitSearchParams();
  getDataByPage();
}

/** ============ 删除 ============ */

/** 从后端错误响应中提取可读原因（DRF: detail / 字段错误数组） */
function getBackendErrorMsg(error: unknown): string {
  const errorData = (error as { response?: { data?: unknown } } | null | undefined)?.response?.data;

  if (typeof errorData === 'string' && errorData) return errorData;

  if (errorData && typeof errorData === 'object') {
    for (const value of Object.values(errorData as Record<string, unknown>)) {
      if (typeof value === 'string' && value) return value;
      if (Array.isArray(value)) {
        const first = value.find(item => typeof item === 'string' && item);
        if (first) return first;
      }
    }
  }

  return '操作失败';
}

async function handleDelete(row: Api.Automation.CommandRecord) {
  try {
    await ElMessageBox.confirm(`确认删除「${row.name}」？被流程节点引用的${props.title}将被拒绝删除`, '删除确认', {
      type: 'warning',
      confirmButtonText: '确定',
      cancelButtonText: '取消'
    });
  } catch {
    return;
  }

  const { error } = await fetchDeleteCommand(row.id);

  if (error) {
    window.$message?.error(getBackendErrorMsg(error));
    return;
  }

  window.$message?.success('删除成功');
  getData();
}

/** ============ 新增/编辑抽屉 ============ */

type OperateType = 'add' | 'edit';

interface FormModel {
  id?: number;
  name: string;
  code: string;
  category: string;
  description: string;
  status: Api.Automation.AtomStatus;
  risk_level: Api.Automation.RiskLevel;
}

function createDefaultForm(): FormModel {
  return {
    name: '',
    code: '',
    category: '',
    description: '',
    status: 'draft',
    risk_level: 'low'
  };
}

const drawerVisible = ref(false);
const operateType = ref<OperateType>('add');
const submitting = ref(false);
const formRef = ref();
const formModel = ref<FormModel>(createDefaultForm());

const formRules = {
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  code: [{ required: true, message: '请输入编码', trigger: 'blur' }]
};

function openOperateDrawer(type: OperateType, row?: Api.Automation.CommandRecord) {
  operateType.value = type;
  formModel.value = row
    ? {
        id: row.id,
        name: row.name,
        code: row.code,
        category: row.category,
        description: row.description,
        status: row.status as Api.Automation.AtomStatus,
        risk_level: row.risk_level as Api.Automation.RiskLevel
      }
    : createDefaultForm();
  drawerVisible.value = true;
}

async function handleSubmit() {
  await formRef.value?.validate();

  submitting.value = true;
  const payload: Api.Automation.CommandPayload = {
    name: formModel.value.name,
    code: formModel.value.code,
    category: formModel.value.category,
    description: formModel.value.description,
    status: formModel.value.status,
    risk_level: formModel.value.risk_level
  };
  if (operateType.value === 'add') {
    payload.resource_kind = props.resourceKind;
  }
  const { error } =
    operateType.value === 'add'
      ? await fetchAddCommand(payload)
      : await fetchUpdateCommand(formModel.value.id!, payload);
  submitting.value = false;

  if (!error) {
    window.$message?.success(operateType.value === 'add' ? '新增成功' : '修改成功');
    drawerVisible.value = false;
    getData();
  }
}

/** ============ 版本抽屉 ============ */

const versionDrawerVisible = ref(false);
const versionLoading = ref(false);
const versionSubmitting = ref(false);
const versionList = ref<Api.Automation.CommandVersionRecord[]>([]);
const currentCommand = ref<Api.Automation.CommandRecord | null>(null);

const versionFormVisible = ref(false);
const versionFormRef = ref();
/** 正在编辑的草稿版本 ID（null 表示新增） */
const editingVersionId = ref<number | null>(null);

/** ============ 版本只读详情抽屉 ============ */

const versionDetailVisible = ref(false);
const versionDetail = ref<Api.Automation.CommandVersionRecord | null>(null);

/** 版本内容对应的编辑器语言 */
function getVersionEditorLanguage(commandType: string) {
  const map: Record<string, 'shell' | 'python' | 'powershell' | 'yaml' | 'plaintext'> = {
    linux_shell: 'shell',
    python: 'python',
    windows_powershell: 'powershell',
    playbook: 'yaml',
    http_request: 'plaintext',
    ansible_module: 'plaintext'
  };
  return map[commandType] ?? 'plaintext';
}

/** JSON 字段美化展示（空对象/数组返回空串，解析失败时原样返回） */
function prettyJson(value: unknown): string {
  const text = typeof value === 'string' ? value : JSON.stringify(value ?? null);
  if (!text || text === 'null') return '';
  try {
    const parsed: unknown = JSON.parse(text);
    if (Array.isArray(parsed) && parsed.length === 0) return '';
    if (parsed && typeof parsed === 'object' && Object.keys(parsed).length === 0) return '';
    return JSON.stringify(parsed, null, 2);
  } catch {
    return text;
  }
}

function openVersionDetail(row: Api.Automation.CommandVersionRecord) {
  versionDetail.value = row;
  versionDetailVisible.value = true;
}

interface VersionFormModel {
  command_type: Api.Automation.CommandType;
  content: string;
  timeout_seconds: number;
  argument_schema: string;
  default_vars: string;
  output_extractors: string;
}

function createDefaultVersionForm(): VersionFormModel {
  return {
    command_type: 'linux_shell',
    content: '',
    timeout_seconds: 60,
    argument_schema: '',
    default_vars: '',
    output_extractors: ''
  };
}

const versionForm = ref<VersionFormModel>(createDefaultVersionForm());

const versionFormRules = {
  command_type: [{ required: true, message: '请选择执行类型', trigger: 'change' }],
  content: [{ required: true, message: '请输入内容', trigger: 'blur' }]
};

function openVersionDrawer(row: Api.Automation.CommandRecord) {
  currentCommand.value = row;
  versionForm.value = createDefaultVersionForm();
  editingVersionId.value = null;
  versionFormVisible.value = false;
  versionList.value = [];
  versionDrawerVisible.value = true;
  loadVersions();
}

async function loadVersions() {
  if (!currentCommand.value) return;

  versionLoading.value = true;
  const { error, data: versions } = await fetchGetCommandVersions(currentCommand.value.id);
  versionLoading.value = false;

  if (!error) {
    versionList.value = versions ?? [];
  }
}

function resetVersionForm() {
  versionForm.value = createDefaultVersionForm();
  editingVersionId.value = null;
  versionFormVisible.value = false;
}

/** 编辑草稿版本：回填表单（JSON 字段序列化为表单字符串） */
function openVersionEdit(row: Api.Automation.CommandVersionRecord) {
  editingVersionId.value = row.id;
  versionForm.value = {
    command_type: row.command_type as Api.Automation.CommandType,
    content: row.content,
    timeout_seconds: row.timeout_seconds,
    argument_schema: Object.keys(row.argument_schema ?? {}).length ? JSON.stringify(row.argument_schema) : '',
    default_vars: Object.keys(row.default_vars ?? {}).length ? JSON.stringify(row.default_vars) : '',
    output_extractors: (row.output_extractors ?? []).length ? JSON.stringify(row.output_extractors) : ''
  };
  versionFormVisible.value = true;
}

function parseJsonObject(text: string): Record<string, unknown> | null {
  if (!text.trim()) return {};
  try {
    const parsed: unknown = JSON.parse(text);
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? (parsed as Record<string, unknown>) : null;
  } catch {
    return null;
  }
}

function parseJsonArray(text: string): unknown[] | null {
  if (!text.trim()) return [];
  try {
    const parsed: unknown = JSON.parse(text);
    return Array.isArray(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

async function handleSaveVersion() {
  await versionFormRef.value?.validate();

  const argumentSchema = parseJsonObject(versionForm.value.argument_schema);
  if (argumentSchema === null) {
    window.$message?.error('参数模式必须是合法的 JSON 对象');
    return;
  }
  const defaultVars = parseJsonObject(versionForm.value.default_vars);
  if (defaultVars === null) {
    window.$message?.error('默认变量必须是合法的 JSON 对象');
    return;
  }
  const outputExtractors = parseJsonArray(versionForm.value.output_extractors);
  if (outputExtractors === null) {
    window.$message?.error('输出提取器必须是合法的 JSON 数组');
    return;
  }
  if (!currentCommand.value) return;

  versionSubmitting.value = true;
  const payload: Omit<Api.Automation.CommandVersionPayload, 'command'> = {
    command_type: versionForm.value.command_type,
    content: versionForm.value.content,
    timeout_seconds: versionForm.value.timeout_seconds,
    argument_schema: argumentSchema,
    default_vars: defaultVars,
    output_extractors: outputExtractors
  };
  const editingId = editingVersionId.value;
  const { error } =
    editingId !== null
      ? await fetchUpdateCommandVersion(editingId, payload)
      : await fetchAddCommandVersion(currentCommand.value.id, payload);
  versionSubmitting.value = false;

  if (!error) {
    window.$message?.success(editingId !== null ? '版本已保存' : '版本创建成功');
    resetVersionForm();
    loadVersions();
    getData();
  }
}

async function handlePublishVersion(row: Api.Automation.CommandVersionRecord) {
  const { error } = await fetchPublishCommandVersion(row.id);

  if (!error) {
    window.$message?.success(`v${row.version} 已发布`);
    loadVersions();
    getData();
  }
}

async function handleArchiveVersion(row: Api.Automation.CommandVersionRecord) {
  const { error } = await fetchArchiveCommandVersion(row.id);

  if (!error) {
    window.$message?.success(`v${row.version} 已归档`);
    loadVersions();
    getData();
  }
}
</script>

<template>
  <div class="min-h-500px flex-col-stretch gap-16px overflow-hidden lt-sm:overflow-auto">
    <ElCard class="card-wrapper">
      <ElForm :model="searchParams" label-width="70px" inline @submit.prevent>
        <ElFormItem label="关键词">
          <ElInput
            v-model="searchParams.search"
            clearable
            placeholder="名称/编码/分类"
            class="w-200px"
            @keyup.enter="getDataByPage()"
          />
        </ElFormItem>
        <ElFormItem label="状态">
          <ElSelect v-model="searchParams.status" clearable placeholder="全部" class="w-120px">
            <ElOption v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="风险等级">
          <ElSelect v-model="searchParams.riskLevel" clearable placeholder="全部" class="w-120px">
            <ElOption v-for="item in riskLevelOptions" :key="item.value" :label="item.label" :value="item.value" />
          </ElSelect>
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
          <p>{{ title }}</p>
          <TableHeaderOperation
            v-model:columns="columnChecks"
            :loading="loading"
            :show-batch-delete="false"
            @refresh="getData"
          >
            <template #default>
              <ElButton type="primary" @click="openOperateDrawer('add')">
                <template #icon>
                  <icon-ic-round-plus class="text-icon" />
                </template>
                新增
              </ElButton>
            </template>
          </TableHeaderOperation>
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

    <ElDrawer v-model="drawerVisible" :title="operateType === 'add' ? `新增${title}` : `编辑${title}`" size="440px">
      <ElForm ref="formRef" :model="formModel" :rules="formRules" label-width="90px">
        <ElFormItem label="资源类型">
          <ElInput :model-value="resourceKind" disabled />
        </ElFormItem>
        <ElFormItem label="名称" prop="name">
          <ElInput v-model="formModel.name" :placeholder="`${title}名称`" />
        </ElFormItem>
        <ElFormItem label="编码" prop="code">
          <ElInput v-model="formModel.code" placeholder="唯一编码，如 disk_check" />
        </ElFormItem>
        <ElFormItem label="分类">
          <ElInput v-model="formModel.category" placeholder="分类标识，如 inspection" />
        </ElFormItem>
        <ElFormItem label="风险等级">
          <ElSelect v-model="formModel.risk_level" class="w-full">
            <ElOption v-for="item in riskLevelOptions" :key="item.value" :label="item.label" :value="item.value" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="状态">
          <ElSelect v-model="formModel.status" class="w-full">
            <ElOption v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="描述">
          <ElInput v-model="formModel.description" type="textarea" :rows="3" placeholder="用途说明" />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="drawerVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="submitting" @click="handleSubmit">确定</ElButton>
      </template>
    </ElDrawer>

    <ElDrawer v-model="versionDrawerVisible" :title="`版本管理 - ${currentCommand?.name ?? ''}`" size="720px">
      <div class="flex flex-col gap-12px">
        <div class="flex items-center justify-between">
          <p class="font-500">版本列表（共 {{ versionList.length }} 个）</p>
          <ElButton type="primary" size="small" @click="versionFormVisible = !versionFormVisible">
            {{ versionFormVisible ? '收起表单' : editingVersionId ? '编辑草稿版本' : '新增版本' }}
          </ElButton>
        </div>

        <ElCard v-if="versionFormVisible" shadow="never">
          <ElForm ref="versionFormRef" :model="versionForm" :rules="versionFormRules" label-width="90px">
            <ElFormItem label="执行类型" prop="command_type">
              <ElSelect v-model="versionForm.command_type" class="w-full">
                <ElOption
                  v-for="item in commandTypeOptions"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
                />
              </ElSelect>
            </ElFormItem>
            <ElFormItem label="内容" prop="content">
              <CodeEditor
                v-model="versionForm.content"
                :language="getVersionEditorLanguage(versionForm.command_type)"
                height="220px"
                placeholder="命令 / 脚本 / Playbook 内容"
              />
            </ElFormItem>
            <ElFormItem label="超时秒数">
              <ElInputNumber v-model="versionForm.timeout_seconds" :min="1" class="w-full" />
            </ElFormItem>
            <ElFormItem label="参数模式">
              <ElInput
                v-model="versionForm.argument_schema"
                type="textarea"
                :rows="2"
                placeholder='JSON 对象，如 {"count": {"type": "number"}}'
              />
            </ElFormItem>
            <ElFormItem label="默认变量">
              <ElInput
                v-model="versionForm.default_vars"
                type="textarea"
                :rows="2"
                placeholder='JSON 对象，如 {"count": 1}'
              />
            </ElFormItem>
            <ElFormItem label="输出提取器">
              <ElInput
                v-model="versionForm.output_extractors"
                type="textarea"
                :rows="2"
                placeholder="JSON 数组，如 []"
              />
            </ElFormItem>
            <ElFormItem>
              <ElButton type="primary" :loading="versionSubmitting" @click="handleSaveVersion">保存版本</ElButton>
              <ElButton @click="resetVersionForm">取消</ElButton>
            </ElFormItem>
          </ElForm>
        </ElCard>

        <ElTable v-loading="versionLoading" :data="versionList" border row-key="id">
          <ElTableColumn prop="version" label="版本号" width="80" align="center">
            <template #default="{ row }">v{{ row.version }}</template>
          </ElTableColumn>
          <ElTableColumn prop="command_type" label="执行类型" width="130" align="center">
            <template #default="{ row }">{{ commandTypeText[row.command_type] ?? row.command_type }}</template>
          </ElTableColumn>
          <ElTableColumn prop="content" label="内容" min-width="180" show-overflow-tooltip />
          <ElTableColumn prop="status" label="状态" width="90" align="center">
            <template #default="{ row }">
              <ElTag :type="getStatusTagType(row.status)">{{ versionStatusText[row.status] ?? row.status }}</ElTag>
            </template>
          </ElTableColumn>
          <ElTableColumn prop="timeout_seconds" label="超时(秒)" width="90" align="center" />
          <ElTableColumn prop="published_at" label="发布时间" width="170">
            <template #default="{ row }">{{ row.published_at || '-' }}</template>
          </ElTableColumn>
          <ElTableColumn prop="created_at" label="创建时间" width="170">
            <template #default="{ row }">{{ row.created_at || '-' }}</template>
          </ElTableColumn>
          <ElTableColumn label="操作" width="200" align="center" fixed="right">
            <template #default="{ row }">
              <ElButton type="primary" plain size="small" @click="openVersionDetail(row)">查看</ElButton>
              <ElButton
                v-if="row.status === 'draft'"
                type="success"
                plain
                size="small"
                @click="handlePublishVersion(row)"
              >
                发布
              </ElButton>
              <ElButton
                v-else-if="row.status === 'published'"
                type="warning"
                plain
                size="small"
                @click="handleArchiveVersion(row)"
              >
                归档
              </ElButton>
              <ElButton v-if="row.status === 'draft'" size="small" @click="openVersionEdit(row)">编辑</ElButton>
            </template>
          </ElTableColumn>
        </ElTable>
      </div>
    </ElDrawer>

    <ElDrawer v-model="versionDetailVisible" title="版本详情" size="680px">
      <template v-if="versionDetail">
        <ElDescriptions :column="2" border size="small">
          <ElDescriptionsItem label="版本号">v{{ versionDetail.version }}</ElDescriptionsItem>
          <ElDescriptionsItem label="状态">
            <ElTag :type="getStatusTagType(versionDetail.status)">
              {{ versionStatusText[versionDetail.status] ?? versionDetail.status }}
            </ElTag>
          </ElDescriptionsItem>
          <ElDescriptionsItem label="执行类型">
            {{ commandTypeText[versionDetail.command_type] ?? versionDetail.command_type }}
          </ElDescriptionsItem>
          <ElDescriptionsItem label="超时(秒)">{{ versionDetail.timeout_seconds }}</ElDescriptionsItem>
          <ElDescriptionsItem label="发布时间">{{ versionDetail.published_at || '-' }}</ElDescriptionsItem>
          <ElDescriptionsItem label="创建时间">{{ versionDetail.created_at || '-' }}</ElDescriptionsItem>
        </ElDescriptions>
        <p class="mb-4px mt-12px font-500">内容</p>
        <CodeEditor
          :model-value="versionDetail.content"
          :language="getVersionEditorLanguage(versionDetail.command_type)"
          readonly
          height="260px"
        />
        <p class="mb-4px mt-12px font-500">参数模式</p>
        <CodeEditor
          :model-value="prettyJson(versionDetail.argument_schema)"
          language="plaintext"
          readonly
          height="120px"
        />
        <p class="mb-4px mt-12px font-500">默认变量</p>
        <CodeEditor
          :model-value="prettyJson(versionDetail.default_vars)"
          language="plaintext"
          readonly
          height="120px"
        />
        <p class="mb-4px mt-12px font-500">输出提取器</p>
        <CodeEditor
          :model-value="prettyJson(versionDetail.output_extractors)"
          language="plaintext"
          readonly
          height="120px"
        />
      </template>
    </ElDrawer>
  </div>
</template>
