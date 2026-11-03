<script setup lang="tsx">
import { computed, onBeforeUnmount, ref, shallowRef, watch } from 'vue';
import type { UploadFile } from 'element-plus';
import type { ModuleParamNote } from '@/constants/ansible-module-param-docs';
import {
  buildParameterDocs,
  readVersionModuleNotes,
  versionModuleParamDocs
} from '@/constants/ansible-module-param-docs';
import {
  fetchAddCommand,
  fetchAddCommandVersion,
  fetchArchiveCommandVersion,
  fetchDeleteCommand,
  fetchDeleteCommandVersion,
  fetchGetCommandList,
  fetchGetCommandVersions,
  fetchGetGitRepositoryFiles,
  fetchGetGitRepositoryList,
  fetchLoadGitRepositoryFile,
  fetchPublishCommandVersion,
  fetchUpdateCommand,
  fetchUpdateCommandVersion
} from '@/service/api';
import { defaultTransform, useUIPaginatedTable } from '@/hooks/common/table';
import CodeEditor from '@/components/common/code-editor/index.vue';
import ModuleParamDocs from '@/components/common/module-param-docs/index.vue';
import VersionFormFields from './version-form-fields.vue';

defineOptions({ name: 'AutomationCommandResourcePage' });

const props = defineProps<{
  /** 固定的资源类型（command/script/playbook/module） */
  resourceKind: Api.Automation.ResourceKind;
  /** 页面标题 */
  title: string;
  /** 页面说明文字（标题行展示） */
  description?: string;
}>();

/** ============ 枚举文案 ============ */

const statusOptions = [
  { value: 'draft', label: '未发布' },
  { value: 'published', label: '已启用' },
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
const versionStatusText: Record<string, string> = { draft: '草稿', published: '已发布', archived: '已归档' };

/** 各资源类型允许的执行类型（与后端 CommandVersionSerializer 校验规则一致） */
const allowedCommandTypes: Record<string, string[]> = {
  command: ['linux_shell', 'windows_powershell'],
  script: ['linux_shell', 'windows_powershell', 'python'],
  playbook: ['playbook'],
  module: ['ansible_module']
};

/** 当前页面资源类型可选的执行类型 */
const commandTypeOptionsForKind = computed(() =>
  commandTypeOptions.filter(item => allowedCommandTypes[props.resourceKind]?.includes(item.value))
);

/** 执行类型字段标签（脚本资源展示为"脚本类型"） */
const commandTypeLabel = computed(() => (props.resourceKind === 'script' ? '脚本类型' : '执行类型'));

/** 蓝鲸式内置脚本模板（linux_shell/windows_powershell/python/playbook） */
const SHELL_TEMPLATE = `#!/bin/bash
#------ 内置脚本方法，可以直接调用 ------
anyowntimes=$(date '+%Y-%m-%d %H:%M:%S')
NOW="echo [\${anyowntimes}][PID:$$]"

#可在脚本开始执行时调用，打印当时的时间戳及PID。
job_start(){
    echo "$(eval $NOW) job_start"
}

#可在脚本执行成功的逻辑分支处调用，打印当时的时间戳及PID。
job_success(){
    MSG="$1"
    echo "$(eval $NOW) job_success:[$MSG]"
    exit 0
}

#可在脚本执行失败的逻辑分支处调用，打印当时的时间戳及PID。
job_fail(){
    MSG="$1"
    echo "$(eval $NOW) job_fail:[$MSG]"
    exit 1
}

job_start
#------ 可在此处下面开始编写您的脚本逻辑代码 ------`;

const POWERSHELL_TEMPLATE = `#------ 可在此处开始编写您的脚本逻辑代码 ------
Write-Output "hello"`;

const PYTHON_TEMPLATE = `#------ 可在此处开始编写您的脚本逻辑代码 ------
print("hello")`;

const PLAYBOOK_TEMPLATE = `- name: 示例任务
  hosts: all
  tasks:
    - name: 输出主机名
      ansible.builtin.command: hostname
      register: result
    - name: 显示结果
      ansible.builtin.debug:
        var: result.stdout`;

function getScriptTemplate(commandType: string): string {
  if (commandType === 'playbook') return PLAYBOOK_TEMPLATE;
  if (commandType === 'windows_powershell') return POWERSHELL_TEMPLATE;
  if (commandType === 'python') return PYTHON_TEMPLATE;
  if (commandType === 'linux_shell') return SHELL_TEMPLATE;
  return '';
}

/** 记录当前预填的模板，用于切换类型时判断内容是否仍是未编辑的模板 */
let currentTemplate = '';

function getStatusTagType(status: string) {
  if (status === 'published') return 'success' as const;
  if (status === 'disabled') return 'danger' as const;
  if (status === 'archived') return 'warning' as const;
  if (status === 'draft') return 'primary' as const;
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
    riskLevel: null,
    resourceKind: props.resourceKind
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
    { prop: 'name', label: '名称', minWidth: 160, showOverflowTooltip: true },
    { prop: 'code', label: '编码', minWidth: 130, showOverflowTooltip: true },
    ...(props.resourceKind === 'module'
      ? [
          {
            prop: 'publishedModuleName',
            label: 'Ansible 模块名',
            width: 150,
            showOverflowTooltip: true,
            formatter: (row: Api.Automation.CommandRecord) => row.publishedModuleName || row.publishedContent || '-'
          }
        ]
      : []),
    {
      prop: 'status',
      label: '资源状态',
      width: 90,
      align: 'center',
      formatter: row => <ElTag type={getStatusTagType(row.status)}>{statusText[row.status] ?? row.status}</ElTag>
    },
    {
      prop: 'riskLevel',
      label: '风险等级',
      width: 100,
      align: 'center',
      formatter: row => (
        <ElTag type={getRiskTagType(row.riskLevel)}>{riskLevelText[row.riskLevel] ?? row.riskLevel}</ElTag>
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
      label: '可编辑草稿',
      width: 120,
      align: 'center',
      formatter: row =>
        row.draftVersion ? (
          <ElTag type="warning">草稿 v{row.draftVersion}</ElTag>
        ) : (
          <span class="text-gray-500">未创建</span>
        )
    },
    { prop: 'createdByName', label: '创建人', width: 110, formatter: row => row.createdByName || '-' },
    { prop: 'updatedAt', label: '更新时间', width: 170, formatter: row => row.updatedAt || '-' },
    {
      prop: 'operate',
      label: '操作',
      width: 230,
      align: 'center',
      fixed: 'right',
      formatter: row => (
        <div class="flex items-center justify-center gap-8px [&>.el-button+.el-button]:!ml-0">
          <ElButton plain type="primary" size="small" class="!w-80px" onClick={() => openOperateDrawer('edit', row)}>
            编辑信息
          </ElButton>
          <ElButton link type="primary" size="small" onClick={() => openContentEditor(row)}>
            编辑内容
          </ElButton>
          <ElDropdown onCommand={(command: string) => onMoreCommand(command, row)}>
            {{
              default: () => (
                <ElButton plain size="small" class="!w-64px">
                  更多 ∨
                </ElButton>
              ),
              dropdown: () => (
                <ElDropdownMenu>
                  <ElDropdownItem command="versions">版本管理</ElDropdownItem>
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

const hasFilter = computed(() =>
  Boolean(searchParams.value.search || searchParams.value.status || searchParams.value.riskLevel)
);

function onMoreCommand(command: string, row: Api.Automation.CommandRecord) {
  if (command === 'versions') openVersionDrawer(row);
  if (command === 'delete') handleDelete(row);
}

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

  window.$notification?.success('删除成功');
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
  riskLevel: Api.Automation.RiskLevel;
  /** 一步创建：首版本信息（仅新增模式使用） */
  commandType: Api.Automation.CommandType;
  content: string;
  moduleName: string;
  remark: string;
  timeoutSeconds: number;
  becomeEnabled: boolean;
  checkModeSupported: boolean;
  argumentSchema: string;
  defaultVars: string;
  outputExtractors: string;
  /** 仅作为执行参考的参数说明 */
  moduleParamNotes: ModuleParamNote[];
}

function createDefaultForm(): FormModel {
  return {
    name: '',
    code: '',
    category: '',
    description: '',
    status: 'draft',
    riskLevel: 'low',
    commandType: (allowedCommandTypes[props.resourceKind]?.[0] ?? 'linux_shell') as Api.Automation.CommandType,
    content: '',
    moduleName: '',
    remark: '',
    timeoutSeconds: 60,
    becomeEnabled: false,
    checkModeSupported: false,
    argumentSchema: '',
    defaultVars: '',
    outputExtractors: '',
    moduleParamNotes: []
  };
}

const drawerVisible = ref(false);
const pendingCreatedId = ref<number | null>(null);

/** ============ 内容来源（新建抽屉展示；脚本为"脚本来源"，Playbook/Module 为"内容来源"） ============ */

type ScriptSource = 'manual' | 'clone' | 'local' | 'git';

const isScriptKind = computed(() => props.resourceKind === 'script');

const sourceLabel = computed(() => (isScriptKind.value ? '脚本来源' : '内容来源'));

const scriptSourceOptions = computed<{ value: ScriptSource; label: string }[]>(() => {
  if (props.resourceKind === 'module') {
    return [
      { value: 'manual', label: '手工录入' },
      { value: 'clone', label: '从已有资源复制' }
    ];
  }
  if (isScriptKind.value) {
    return [
      { value: 'manual', label: '手工录入' },
      { value: 'clone', label: '脚本克隆' },
      { value: 'local', label: '本地脚本' }
    ];
  }
  return [
    { value: 'manual', label: '手工录入' },
    { value: 'clone', label: '从已有资源复制' },
    { value: 'local', label: '本地上传' },
    { value: 'git', label: 'Git 单文件导入' }
  ];
});

/** 克隆/上传行 label（跟随资源标题） */
const cloneLabel = computed(() => `选择${props.title}`);
const uploadLabel = computed(() => (isScriptKind.value ? '上传脚本' : '上传文件'));

/** 本地上传接受的文件扩展名（跟随资源类型） */
const uploadAccept = computed(() => (isScriptKind.value ? '.sh,.py,.ps1,.txt' : '.yml,.yaml,.txt'));

const scriptSource = ref<ScriptSource>('manual');
/** "克隆"候选：同类型已发布资源 */
const cloneScriptOptions = shallowRef<Api.Automation.CommandRecord[]>([]);
const cloneScriptId = ref<number | null>(null);
let cloneOptionsRequestId = 0;
let cloneRequestId = 0;
/** "本地上传"已选文件名（仅展示，内容读入内容框后可继续编辑） */
const localFileName = ref('');

/** "Git 仓库加载"状态 */
const gitRepoOptions = shallowRef<Api.Automation.GitRepositoryRecord[]>([]);
const gitRepoId = ref<number | null>(null);
/** 分支/标签（留空使用仓库配置的默认分支） */
const gitRef = ref('');
const gitFileOptions = shallowRef<string[]>([]);
const gitFilePath = ref<string | null>(null);
const gitLoadingFiles = ref(false);
const gitLoadingContent = ref(false);
let gitFilesRequestId = 0;
let gitContentRequestId = 0;

const operateType = ref<OperateType>('add');
const submitting = ref(false);
const formRef = ref();

const formModel = ref<FormModel>(createDefaultForm());
const formBaseline = ref('');
/** 编辑模式下该资源是否已发布（已发布后编码锁定） */
const editingPublished = ref(false);
const hasPublishedVersion = ref(false);
const editableStatusOptions = computed(() =>
  statusOptions.filter(
    item =>
      item.value === 'disabled' ||
      (editingPublished.value ? hasPublishedVersion.value && item.value === 'published' : item.value === 'draft')
  )
);

/** JSON 字段校验工厂：空值放行（提交时按空对象/空数组处理），非空必须可解析为对应结构 */
function createJsonValidator(kind: 'object' | 'array', message: string) {
  return (_rule: unknown, value: string, callback: (error?: Error) => void) => {
    if (!value.trim()) return callback();
    const parsed = kind === 'object' ? parseJsonObject(value) : parseJsonArray(value);
    if (parsed === null) return callback(new Error(message));
    return callback();
  };
}

const formRules = {
  moduleParamNotes: [{ validator: validateModuleNotes, trigger: 'blur' }],
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  code: [{ required: true, message: '请输入编码', trigger: 'blur' }],
  content: [{ required: props.resourceKind !== 'module', message: '请输入内容', trigger: 'blur' }],
  moduleName: [{ required: props.resourceKind === 'module', message: '请输入 Ansible 模块名', trigger: 'blur' }],
  argumentSchema: [{ validator: createJsonValidator('object', '参数模式必须是合法的 JSON 对象'), trigger: 'blur' }],
  defaultVars: [{ validator: createJsonValidator('object', 'extra_vars 必须是合法的 JSON 对象'), trigger: 'blur' }],
  outputExtractors: [{ validator: createJsonValidator('array', '输出提取器必须是合法的 JSON 数组'), trigger: 'blur' }]
};

function openOperateDrawer(type: OperateType, row?: Api.Automation.CommandRecord) {
  pendingCreatedId.value = null;
  operateType.value = type;
  if (row) {
    formModel.value = {
      id: row.id,
      name: row.name,
      code: row.code,
      category: row.category,
      description: row.description,
      status: row.status as Api.Automation.AtomStatus,
      riskLevel: row.riskLevel as Api.Automation.RiskLevel,
      commandType: createDefaultForm().commandType,
      content: '',
      moduleName: '',
      remark: '',
      timeoutSeconds: 60,
      becomeEnabled: false,
      checkModeSupported: false,
      argumentSchema: '',
      defaultVars: '',
      outputExtractors: '',
      moduleParamNotes: []
    };
    currentTemplate = '';
    editingPublished.value = row.status !== 'draft';
    hasPublishedVersion.value = row.publishedVersion !== null;
  } else {
    const fresh = createDefaultForm();
    hasPublishedVersion.value = false;
    // 新建资源预填内容模板，名称由用户填写

    fresh.content = getScriptTemplate(fresh.commandType);
    currentTemplate = fresh.content;
    scriptSource.value = 'manual';
    cloneScriptId.value = null;
    localFileName.value = '';
    gitRepoId.value = null;
    gitRef.value = '';
    gitFileOptions.value = [];
    gitFilePath.value = null;
    formModel.value = fresh;
    loadCloneScriptOptions();
    loadGitRepoOptions();
  }
  formBaseline.value = JSON.stringify(formModel.value);
  drawerVisible.value = true;
}

/** 新增模式下切换执行类型：内容仍为未编辑的模板（或为空）时跟随切换 */
function onAddTypeChange(commandType: string | number | boolean | undefined) {
  if (typeof commandType !== 'string') return;
  if (!formModel.value.content || formModel.value.content === currentTemplate) {
    formModel.value.content = getScriptTemplate(commandType);
    currentTemplate = formModel.value.content;
  }
}

/** ============ 脚本来源交互（克隆导入 / 本地上传） ============ */

/** 本地脚本扩展名 → 执行类型（仅采纳当前资源类型允许的类型） */
const localFileExtTypeMap: Record<string, Api.Automation.CommandType> = {
  sh: 'linux_shell',
  ps1: 'windows_powershell',
  py: 'python'
};

/** 切换来源时清理其他来源的辅助状态（内容不重置，由用户决定去留） */
function onScriptSourceChange() {
  if (scriptSource.value !== 'clone') {
    cloneScriptId.value = null;
    cloneRequestId += 1;
  }
  if (scriptSource.value !== 'local') localFileName.value = '';
  if (scriptSource.value !== 'git') {
    invalidateGitSelection();
    gitRepoId.value = null;
    gitRef.value = '';
  }
}

/** 拉取同资源类型已发布脚本，供"克隆"选择 */
async function loadCloneScriptOptions(search = '') {
  cloneOptionsRequestId += 1;
  const requestId = cloneOptionsRequestId;
  const { data: list, error } = await fetchGetCommandList({
    current: 1,
    size: 100,
    status: 'published',
    resourceKind: props.resourceKind,
    search
  });
  if (requestId !== cloneOptionsRequestId) return;
  if (!error && list) {
    cloneScriptOptions.value = list.records;
  }
}

/** 脚本克隆：导入所选脚本最新已发布版本的内容与执行类型 */
async function handleCloneScriptChange(id?: number) {
  if (!id) return;
  cloneRequestId += 1;
  const requestId = cloneRequestId;
  const { data: versions, error } = await fetchGetCommandVersions(id);
  if (requestId !== cloneRequestId || cloneScriptId.value !== id || !drawerVisible.value) return;
  if (error || !versions) return;
  const published = versions.filter(item => item.status === 'published').sort((a, b) => b.version - a.version)[0];
  if (!published) {
    window.$message?.warning('该脚本暂无已发布版本');
    return;
  }
  formModel.value.commandType = published.commandType as Api.Automation.CommandType;
  formModel.value.content = props.resourceKind === 'module' ? '' : published.content;
  formModel.value.moduleName = published.moduleName || published.content;
  formModel.value.timeoutSeconds = published.timeoutSeconds;
  formModel.value.becomeEnabled = published.becomeEnabled;
  formModel.value.checkModeSupported = published.checkModeSupported;
  formModel.value.argumentSchema = Object.keys(published.argumentSchema ?? {}).length
    ? JSON.stringify(published.argumentSchema)
    : '';
  formModel.value.defaultVars = Object.keys(published.defaultVars ?? {}).length
    ? JSON.stringify(published.defaultVars)
    : '';
  formModel.value.outputExtractors = (published.outputExtractors ?? []).length
    ? JSON.stringify(published.outputExtractors)
    : '';
  formModel.value.moduleParamNotes = readVersionModuleNotes(published);
  currentTemplate = '';
  window.$notification?.success(`已导入 v${published.version} 的内容与参数配置`);
}

/** 本地脚本：读取文件文本填入内容框（可继续编辑），并按扩展名推断执行类型 */
function handleLocalFileChange(uploadFile: UploadFile) {
  const raw = uploadFile.raw;
  if (!raw) return;
  localFileName.value = raw.name;
  const reader = new FileReader();
  reader.onload = () => {
    if (!drawerVisible.value || scriptSource.value !== 'local' || localFileName.value !== raw.name) return;
    formModel.value.content = String(reader.result ?? '');
    currentTemplate = '';
    const ext = raw.name.split('.').pop()?.toLowerCase() ?? '';
    const inferred = localFileExtTypeMap[ext];
    if (inferred && allowedCommandTypes[props.resourceKind]?.includes(inferred)) {
      formModel.value.commandType = inferred;
    }
  };
  reader.onerror = () => window.$message?.error('文件读取失败，请重新选择');
  reader.readAsText(raw, 'utf-8');
}

/** ============ Git 仓库加载 ============ */

async function loadGitRepoOptions() {
  const { data: list, error } = await fetchGetGitRepositoryList({ current: 1, size: 100 });
  if (!error && list) {
    gitRepoOptions.value = list.records.filter(item => item.isActive);
  }
}

/** 仓库、分支和抽屉生命周期变化时，选中文件及正文必须同时失效。 */
function invalidateGitSelection() {
  gitFilesRequestId += 1;
  gitContentRequestId += 1;
  gitLoadingFiles.value = false;
  gitLoadingContent.value = false;
  gitFilePath.value = null;
  gitFileOptions.value = [];
  if (scriptSource.value === 'git') {
    formModel.value.content = '';
    currentTemplate = '';
  }
}

/** 切换仓库：带出默认分支并拉取文件列表 */
function handleGitRepoChange(id?: number) {
  invalidateGitSelection();
  const repo = gitRepoOptions.value.find(item => item.id === id);
  gitRef.value = repo?.branch || '';
  if (id) {
    searchGitFiles('');
  }
}

/** 远程搜索仓库文件（修改分支后重新拉取） */
async function searchGitFiles(query: string) {
  if (!gitRepoId.value || scriptSource.value !== 'git' || !drawerVisible.value) return;
  const repoId = gitRepoId.value;
  const requestedRef = gitRef.value;
  gitFilesRequestId += 1;
  const requestId = gitFilesRequestId;
  gitLoadingFiles.value = true;
  try {
    const { data: files, error } = await fetchGetGitRepositoryFiles(repoId, {
      ref: requestedRef || undefined,
      search: query || undefined,
      limit: 100
    });
    if (
      requestId !== gitFilesRequestId ||
      gitRepoId.value !== repoId ||
      gitRef.value !== requestedRef ||
      scriptSource.value !== 'git' ||
      !drawerVisible.value
    )
      return;
    if (!error && files) gitFileOptions.value = files.files ?? [];
  } finally {
    if (requestId === gitFilesRequestId) gitLoadingFiles.value = false;
  }
}

/** 选中文件后加载内容填入内容框（可继续编辑） */
async function handleGitFileChange(path: string | null) {
  gitContentRequestId += 1;
  gitLoadingContent.value = false;
  formModel.value.content = '';
  currentTemplate = '';
  if (!path || !gitRepoId.value || scriptSource.value !== 'git' || !drawerVisible.value) return;
  const repoId = gitRepoId.value;
  const requestedRef = gitRef.value;
  const requestId = gitContentRequestId;
  gitLoadingContent.value = true;
  try {
    const { data: result, error } = await fetchLoadGitRepositoryFile(repoId, {
      path,
      ref: requestedRef || undefined
    });
    if (
      requestId !== gitContentRequestId ||
      gitRepoId.value !== repoId ||
      gitRef.value !== requestedRef ||
      gitFilePath.value !== path ||
      scriptSource.value !== 'git' ||
      !drawerVisible.value
    )
      return;
    if (!error && result) {
      formModel.value.content = result.content;
      window.$notification?.success(`已加载 ${path}`);
    }
  } finally {
    if (requestId === gitContentRequestId) gitLoadingContent.value = false;
  }
}

function validateModuleNotes(_rule: unknown, value: ModuleParamNote[], callback: (error?: Error) => void) {
  if (props.resourceKind !== 'module') return callback();
  try {
    buildParameterDocs(value);
    return callback();
  } catch (error) {
    return callback(error instanceof Error ? error : new Error('参数说明填写不正确'));
  }
}

/** 从表单构建版本载荷（新增首版本 / 编辑草稿版本共用），JSON 合法性已由表单 rules 校验 */
function buildVersionPayload(
  model: VersionFormModel = formModel.value
): Omit<Api.Automation.CommandVersionPayload, 'command'> | null {
  let argumentSchema: Record<string, unknown>;
  let defaultVars: Record<string, unknown>;

  if (props.resourceKind === 'module') {
    // Module resources describe arguments; actual values belong to each execution.
    try {
      buildParameterDocs(model.moduleParamNotes);
      argumentSchema = {};
    } catch (error) {
      window.$message?.error(error instanceof Error ? error.message : '参数说明填写不正确');
      return null;
    }
    defaultVars = {};
  } else {
    // 空串由 parseJsonObject/parseJsonArray 按空对象/空数组处理
    argumentSchema = parseJsonObject(model.argumentSchema) ?? {};
    defaultVars = parseJsonObject(model.defaultVars) ?? {};
  }

  const outputExtractors = parseJsonArray(model.outputExtractors) ?? [];
  return {
    commandType: model.commandType,
    content: props.resourceKind === 'module' ? '' : model.content,
    ...(props.resourceKind === 'module'
      ? { moduleName: model.moduleName, parameterDocs: buildParameterDocs(model.moduleParamNotes) }
      : {}),
    timeoutSeconds: props.resourceKind === 'module' ? 60 : model.timeoutSeconds,
    becomeEnabled: props.resourceKind !== 'module' && model.becomeEnabled,
    checkModeSupported: props.resourceKind !== 'module' && model.checkModeSupported,
    remark: model.remark,
    argumentSchema,
    defaultVars,
    outputExtractors: props.resourceKind === 'module' ? [] : outputExtractors
  };
}

async function ensureCreatedCommand(payload: Api.Automation.CommandPayload): Promise<number | null> {
  if (pendingCreatedId.value !== null) {
    const { error } = await fetchUpdateCommand(pendingCreatedId.value, payload);
    return error ? null : pendingCreatedId.value;
  }
  const { error, data: created } = await fetchAddCommand(payload);
  if (error || !created) return null;
  pendingCreatedId.value = created.id;
  return created.id;
}

async function handleSubmit() {
  if (submitting.value || gitLoadingContent.value) return;
  const contentRequestId = gitContentRequestId;
  const valid = await formRef.value?.validate().catch(() => false);
  if (!valid || submitting.value || gitLoadingContent.value || contentRequestId !== gitContentRequestId) return;

  const versionPayload = operateType.value === 'add' ? buildVersionPayload() : null;
  if (operateType.value === 'add' && !versionPayload) return;

  submitting.value = true;
  try {
    if (operateType.value === 'add') {
      if (!versionPayload) return;
      // 蓝鲸式一步创建：先建资源，再用返回 id 创建首版本
      const payload: Api.Automation.CommandPayload = {
        name: formModel.value.name,
        code: formModel.value.code,
        category: formModel.value.category,
        description: formModel.value.description,
        riskLevel: formModel.value.riskLevel,
        resourceKind: props.resourceKind
      };
      const createdId = await ensureCreatedCommand(payload);
      if (createdId === null) return;
      const { error: versionError } = await fetchAddCommandVersion(createdId, versionPayload);
      if (versionError) {
        window.$message?.warning('资源信息已保存，首版本保存失败。请修正后重试，当前内容已保留。');
        getData();
        return;
      }
      window.$notification?.success('新增成功');
    } else {
      const payload: Api.Automation.CommandPayload = {
        name: formModel.value.name,
        code: formModel.value.code,
        category: formModel.value.category,
        description: formModel.value.description,
        status: formModel.value.status,
        riskLevel: formModel.value.riskLevel
      };
      const { error } = await fetchUpdateCommand(formModel.value.id!, payload);
      if (error) return;
      window.$notification?.success('修改成功');
    }
    drawerVisible.value = false;
    getData();
  } finally {
    submitting.value = false;
  }
}

/** ============ 版本抽屉 ============ */

const versionDrawerVisible = ref(false);
const versionLoading = ref(false);
const versionSubmitting = ref(false);
const versionList = ref<Api.Automation.CommandVersionRecord[]>([]);
const currentCommand = ref<Api.Automation.CommandRecord | null>(null);
let versionRequestId = 0;
let versionEditorId = 0;
const versionActionBusy = ref(false);

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
  versionDrawerVisible.value = false;
  versionDetailVisible.value = true;
}

/** 版本详情的参数说明（仅 Module 资源）：优先取版本自身配置，未配置时回退内置字典 */
const versionDetailParamDocs = computed(() => {
  const detail = versionDetail.value;
  if (!detail || props.resourceKind !== 'module') return null;
  return versionModuleParamDocs(detail);
});

const versionDetailExtraVars = computed(() => {
  return versionDetail.value?.defaultVars ?? {};
});

interface VersionFormModel {
  commandType: Api.Automation.CommandType;
  content: string;
  moduleName: string;
  timeoutSeconds: number;
  becomeEnabled: boolean;
  checkModeSupported: boolean;
  remark: string;
  argumentSchema: string;
  defaultVars: string;
  outputExtractors: string;
  /** 仅作为执行参考的参数说明 */
  moduleParamNotes: ModuleParamNote[];
}

function createDefaultVersionForm(): VersionFormModel {
  return {
    commandType: (allowedCommandTypes[props.resourceKind]?.[0] ?? 'linux_shell') as Api.Automation.CommandType,
    content: '',
    moduleName: '',
    timeoutSeconds: 60,
    becomeEnabled: false,
    checkModeSupported: false,
    remark: '',
    argumentSchema: '',
    defaultVars: '',
    outputExtractors: '',
    moduleParamNotes: []
  };
}

const versionForm = ref<VersionFormModel>(createDefaultVersionForm());
const versionFormBaseline = ref('');

async function confirmDiscard(changed: boolean): Promise<boolean> {
  if (!changed) return true;
  try {
    await ElMessageBox.confirm('有尚未保存的修改，确认放弃？', '关闭确认', {
      type: 'warning',
      confirmButtonText: '放弃修改',
      cancelButtonText: '继续编辑'
    });
    return true;
  } catch {
    return false;
  }
}

async function beforeVersionClose(done: () => void) {
  if (versionSubmitting.value) return;
  if (await confirmDiscard(JSON.stringify(versionForm.value) !== versionFormBaseline.value)) done();
}

async function beforeResourceClose(done: () => void) {
  if (submitting.value) return;
  if (await confirmDiscard(JSON.stringify(formModel.value) !== formBaseline.value)) done();
}

function cancelResourceEdit() {
  beforeResourceClose(() => {
    drawerVisible.value = false;
  });
}

const versionFormRules = computed(() => ({
  moduleParamNotes: [{ validator: validateModuleNotes, trigger: 'blur' }],
  commandType: [{ required: true, message: `请选择${commandTypeLabel.value}`, trigger: 'change' }],
  content: [{ required: props.resourceKind !== 'module', message: '请输入内容', trigger: 'blur' }],
  moduleName: [{ required: props.resourceKind === 'module', message: '请输入 Ansible 模块名', trigger: 'blur' }],
  argumentSchema: [{ validator: createJsonValidator('object', '参数模式必须是合法的 JSON 对象'), trigger: 'blur' }],
  defaultVars: [{ validator: createJsonValidator('object', 'extra_vars 必须是合法的 JSON 对象'), trigger: 'blur' }],
  outputExtractors: [{ validator: createJsonValidator('array', '输出提取器必须是合法的 JSON 数组'), trigger: 'blur' }]
}));

function openVersionDrawer(row: Api.Automation.CommandRecord) {
  versionEditorId += 1;
  versionRequestId += 1;
  currentCommand.value = row;
  versionForm.value = createDefaultVersionForm();
  editingVersionId.value = null;
  versionFormVisible.value = false;
  versionList.value = [];
  versionDrawerVisible.value = true;
  return loadVersions();
}

async function openContentEditor(row: Api.Automation.CommandRecord) {
  const loaded = await openVersionDrawer(row);
  if (loaded && versionDrawerVisible.value && currentCommand.value?.id === row.id) openNewVersionForm();
}

async function loadVersions(): Promise<boolean> {
  if (!currentCommand.value) return false;
  const commandId = currentCommand.value.id;
  versionRequestId += 1;
  const requestId = versionRequestId;
  versionLoading.value = true;
  const { error, data: versions } = await fetchGetCommandVersions(commandId);
  if (requestId !== versionRequestId || currentCommand.value?.id !== commandId) return false;
  versionLoading.value = false;

  if (!error) {
    versionList.value = versions ?? [];
    return true;
  }
  return false;
}

function resetVersionForm() {
  beforeVersionClose(() => {
    versionFormVisible.value = false;
  });
}

function onVersionFormClosed() {
  if (versionFormVisible.value) return;
  versionEditorId += 1;
  if (currentCommand.value && !drawerVisible.value && !versionDetailVisible.value) versionDrawerVisible.value = true;
}

function onVersionDetailClosed() {
  if (versionDetailVisible.value) return;
  versionDetail.value = null;
  if (currentCommand.value) versionDrawerVisible.value = true;
}

function editCurrentCommand() {
  if (!currentCommand.value) return;
  const command = currentCommand.value;
  versionDrawerVisible.value = false;
  openOperateDrawer('edit', command);
}

function openNewVersionForm() {
  const draft = versionList.value.find(item => item.status === 'draft');
  if (draft) {
    openVersionEdit(draft);
    return;
  }
  const published = versionList.value.find(item => item.status === 'published');
  if (published) {
    cloneVersionAsDraft(published);
    return;
  }
  versionForm.value = createDefaultVersionForm();
  versionFormBaseline.value = JSON.stringify(versionForm.value);
  editingVersionId.value = null;
  versionDrawerVisible.value = false;
  versionFormVisible.value = true;
}

function openVersionPrimary(row: Api.Automation.CommandVersionRecord) {
  if (row.status === 'draft') openVersionEdit(row);
  else openVersionDetail(row);
}

/** 编辑草稿版本：回填表单（JSON 字段序列化为表单字符串） */
function openVersionEdit(row: Api.Automation.CommandVersionRecord) {
  versionEditorId += 1;
  editingVersionId.value = row.id;
  versionForm.value = {
    commandType: row.commandType as Api.Automation.CommandType,
    content: props.resourceKind === 'module' ? '' : row.content,
    moduleName: row.moduleName || row.content,
    timeoutSeconds: row.timeoutSeconds,
    becomeEnabled: row.becomeEnabled,
    checkModeSupported: row.checkModeSupported,
    remark: row.remark ?? '',
    argumentSchema: Object.keys(row.argumentSchema ?? {}).length ? JSON.stringify(row.argumentSchema) : '',
    defaultVars: Object.keys(row.defaultVars ?? {}).length ? JSON.stringify(row.defaultVars) : '',
    outputExtractors: (row.outputExtractors ?? []).length ? JSON.stringify(row.outputExtractors) : '',
    moduleParamNotes: readVersionModuleNotes(row)
  };
  versionFormBaseline.value = JSON.stringify(versionForm.value);
  versionDrawerVisible.value = false;
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
  if (versionSubmitting.value || !currentCommand.value) return;
  versionSubmitting.value = true;
  const commandId = currentCommand.value.id;
  const editorId = versionEditorId;
  const editingId = editingVersionId.value;
  try {
    const valid = await versionFormRef.value?.validate().catch(() => false);
    if (!valid || editorId !== versionEditorId || currentCommand.value?.id !== commandId) return;
    const payload = buildVersionPayload(versionForm.value);
    if (!payload) return;
    const { error } =
      editingId !== null
        ? await fetchUpdateCommandVersion(editingId, payload)
        : await fetchAddCommandVersion(commandId, payload);
    if (error) return;
    getData();
    if (editorId !== versionEditorId || currentCommand.value?.id !== commandId) return;
    window.$notification?.success('草稿已保存');
    versionFormBaseline.value = JSON.stringify(versionForm.value);
    versionFormVisible.value = false;
    loadVersions();
  } finally {
    versionSubmitting.value = false;
  }
}

async function handlePublishVersion(row: Api.Automation.CommandVersionRecord) {
  if (versionActionBusy.value || !currentCommand.value) return;
  const commandId = currentCommand.value.id;
  const contextId = versionEditorId;
  versionActionBusy.value = true;
  try {
    await ElMessageBox.confirm(`确认发布草稿 v${row.version}？发布后内容不可修改，原发布版本将归档。`, '发布确认', {
      type: 'warning'
    });
    if (currentCommand.value?.id !== commandId || contextId !== versionEditorId) return;
    const { error } = await fetchPublishCommandVersion(row.id);
    if (error) return;
    getData();
    if (currentCommand.value?.id !== commandId || contextId !== versionEditorId) return;
    currentCommand.value = {
      ...currentCommand.value,
      status: currentCommand.value.status === 'draft' ? 'published' : currentCommand.value.status,
      publishedVersion: row.version,
      draftVersion: null
    };
    window.$notification?.success(`v${row.version} 已发布`);
    loadVersions();
  } catch {
    // Confirmation dismissed; request errors are displayed by the API client.
  } finally {
    versionActionBusy.value = false;
  }
}

async function handleArchiveVersion(row: Api.Automation.CommandVersionRecord) {
  if (versionActionBusy.value || !currentCommand.value) return;
  const commandId = currentCommand.value.id;
  const contextId = versionEditorId;
  versionActionBusy.value = true;
  try {
    await ElMessageBox.confirm(`确认归档版本 v${row.version}？归档后不能用于新执行。`, '归档确认', { type: 'warning' });
    if (currentCommand.value?.id !== commandId || contextId !== versionEditorId) return;
    const { error } = await fetchArchiveCommandVersion(row.id);
    if (error) return;
    getData();
    if (currentCommand.value?.id !== commandId || contextId !== versionEditorId) return;
    if (currentCommand.value.publishedVersion === row.version) {
      currentCommand.value = { ...currentCommand.value, publishedVersion: null };
    }
    window.$notification?.success(`v${row.version} 已归档`);
    loadVersions();
  } catch {
    // Confirmation dismissed.
  } finally {
    versionActionBusy.value = false;
  }
}

function cloneVersionAsDraft(row: Api.Automation.CommandVersionRecord) {
  if (versionList.value.some(item => item.status === 'draft')) {
    window.$message?.warning('已有可编辑草稿，请先完成或处理该草稿');
    return;
  }
  openVersionEdit(row);
  editingVersionId.value = null;
  versionForm.value.remark = '';
  versionFormBaseline.value = JSON.stringify(versionForm.value);
}

/** 删除草稿版本（仅草稿可删；被流程节点引用的版本后端会拒绝并提示改用归档） */
async function handleDeleteVersion(row: Api.Automation.CommandVersionRecord) {
  if (row.status !== 'draft') return;
  try {
    await ElMessageBox.confirm(`确认删除草稿 v${row.version}？删除后不可恢复`, '删除确认', {
      type: 'warning',
      confirmButtonText: '确定',
      cancelButtonText: '取消'
    });
  } catch {
    return;
  }
  const { error } = await fetchDeleteCommandVersion(row.id);

  if (!error) {
    if (versionDetail.value?.id === row.id) {
      versionDetail.value = null;
    }
    window.$notification?.success(`v${row.version} 已删除`);
    loadVersions();
    getData();
  }
}

function onVersionCommand(command: string, row: Api.Automation.CommandVersionRecord) {
  if (command === 'publish') handlePublishVersion(row);
  if (command === 'archive') handleArchiveVersion(row);
  if (command === 'clone') cloneVersionAsDraft(row);
  if (command === 'delete') handleDeleteVersion(row);
}

watch([gitRepoId, gitRef], invalidateGitSelection, { flush: 'sync' });

watch(
  drawerVisible,
  visible => {
    if (visible) return;
    invalidateGitSelection();
    cloneRequestId += 1;
  },
  { flush: 'sync' }
);

onBeforeUnmount(() => {
  invalidateGitSelection();
  cloneRequestId += 1;
});
</script>

<template>
  <div class="min-h-500px flex-col-stretch gap-16px overflow-hidden lt-sm:overflow-auto">
    <SearchPanel @reset="resetSearchParams" @search="getDataByPage">
      <ElForm :model="searchParams" label-width="80px" @submit.prevent="getDataByPage">
        <ElFormItem label="关键词">
          <ElInput
            v-model="searchParams.search"
            clearable
            placeholder="名称 / 编码"
            @keyup.enter="getDataByPage()"
            @clear="getDataByPage()"
          />
        </ElFormItem>
        <ElFormItem label="状态">
          <ElSelect v-model="searchParams.status" clearable placeholder="全部状态">
            <ElOption v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="风险">
          <ElSelect v-model="searchParams.riskLevel" clearable placeholder="全部风险">
            <ElOption v-for="item in riskLevelOptions" :key="item.value" :label="item.label" :value="item.value" />
          </ElSelect>
        </ElFormItem>
      </ElForm>
    </SearchPanel>

    <ElCard class="card-wrapper sm:flex-1-hidden">
      <template #header>
        <div class="flex flex-wrap items-center justify-between gap-12px">
          <div class="min-w-0 flex flex-wrap items-baseline gap-8px">
            <p>{{ title }}</p>
            <span v-if="description" class="text-13px text-gray-500">{{ description }}</span>
          </div>
          <TableHeaderOperation
            v-model:columns="columnChecks"
            :loading="loading"
            :show-add="false"
            :show-batch-delete="false"
            @refresh="getData"
          >
            <template #default>
              <ElButton type="primary" @click="openOperateDrawer('add')">
                <template #icon>
                  <icon-ic-round-plus class="text-icon" />
                </template>
                新建
              </ElButton>
            </template>
          </TableHeaderOperation>
        </div>
      </template>

      <div class="h-[calc(100%-52px)]">
        <ElTable v-loading="loading" :data="data" row-key="id" height="100%" border class="sm:h-full">
          <ElTableColumn v-for="col in columns" :key="col.prop" v-bind="col" />
          <template #empty>
            <ElEmpty
              v-if="!loading"
              :description="hasFilter ? '没有符合条件的资源' : `暂无${title}资源`"
              :image-size="80"
            >
              <ElButton v-if="!hasFilter" type="primary" @click="openOperateDrawer('add')">新建{{ title }}</ElButton>
            </ElEmpty>
          </template>
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

    <ElDrawer
      v-model="drawerVisible"
      :before-close="beforeResourceClose"
      :title="operateType === 'add' ? `新建${title}` : `编辑${title}信息`"
      size="min(860px, 100%)"
    >
      <ElForm
        ref="formRef"
        :disabled="submitting"
        :model="formModel"
        :rules="formRules"
        label-position="top"
        class="el-form--light"
        label-suffix="："
        require-asterisk-position="left"
      >
        <ElRow :gutter="16">
          <ElCol :xs="24" :sm="12">
            <ElFormItem label="名称" prop="name">
              <ElInput v-model="formModel.name" :placeholder="`${title}名称`" />
            </ElFormItem>
          </ElCol>
          <ElCol :xs="24" :sm="12">
            <ElFormItem prop="code">
              <template #label>
                <FormLabelHelp label="编码" :help="['资源唯一编码，供流程节点引用；', '资源发布后不可修改。']" />
              </template>
              <ElInput
                v-model="formModel.code"
                placeholder="唯一编码，如 disk_check"
                :disabled="operateType === 'edit' && editingPublished"
              />
            </ElFormItem>
          </ElCol>
          <ElCol :xs="24" :sm="12">
            <ElFormItem label="分类">
              <ElInput v-model="formModel.category" placeholder="如 inspection（可选）" />
            </ElFormItem>
          </ElCol>
          <ElCol :xs="24" :sm="12">
            <ElFormItem>
              <template #label>
                <FormLabelHelp
                  label="风险等级"
                  :help="['标识资源的执行风险程度；', '展示在资源选择与执行确认信息中。']"
                />
              </template>
              <ElRadioGroup v-model="formModel.riskLevel">
                <ElRadio v-for="item in riskLevelOptions" :key="item.value" :value="item.value">
                  {{ item.label }}
                </ElRadio>
              </ElRadioGroup>
            </ElFormItem>
          </ElCol>
        </ElRow>
        <ElFormItem label="描述">
          <ElInput v-model="formModel.description" type="textarea" :rows="2" placeholder="用途说明（可选）" />
        </ElFormItem>
        <ElFormItem v-if="operateType === 'edit'" label="资源状态">
          <ElRadioGroup v-model="formModel.status">
            <ElRadio v-for="item in editableStatusOptions" :key="item.value" :value="item.value">
              {{ item.label }}
            </ElRadio>
          </ElRadioGroup>
          <div class="w-full text-12px text-gray-500">
            资源状态控制能否用于新执行；内容和发布状态请在版本管理中调整。
          </div>
        </ElFormItem>

        <template v-if="operateType === 'add'">
          <template v-if="operateType === 'add'">
            <ElFormItem :label="sourceLabel">
              <ElRadioGroup v-model="scriptSource" @change="onScriptSourceChange">
                <ElRadio v-for="item in scriptSourceOptions" :key="item.value" :value="item.value">
                  {{ item.label }}
                </ElRadio>
              </ElRadioGroup>
            </ElFormItem>
            <ElFormItem v-if="scriptSource === 'clone'" :label="cloneLabel">
              <ElSelect
                v-model="cloneScriptId"
                filterable
                remote
                :remote-method="loadCloneScriptOptions"
                clearable
                placeholder="选择已发布资源，自动导入最新已发布版本内容"
                class="w-full"
                @change="handleCloneScriptChange"
              >
                <ElOption v-for="item in cloneScriptOptions" :key="item.id" :label="item.name" :value="item.id">
                  <span>{{ item.name }}</span>
                  <span class="ml-8px text-12px text-gray-500">{{ item.code }}</span>
                </ElOption>
              </ElSelect>
            </ElFormItem>
            <ElFormItem v-if="scriptSource === 'local'" :label="uploadLabel">
              <div class="w-full flex items-center gap-12px">
                <ElUpload
                  :auto-upload="false"
                  :show-file-list="false"
                  :accept="uploadAccept"
                  :on-change="handleLocalFileChange"
                >
                  <ElButton>选择文件</ElButton>
                </ElUpload>
                <span v-if="localFileName" class="text-13px text-gray-500">{{ localFileName }}</span>
              </div>
            </ElFormItem>
            <template v-if="scriptSource === 'git'">
              <ElRow :gutter="16">
                <ElCol :xs="24" :sm="12">
                  <ElFormItem label="Git 仓库">
                    <ElSelect
                      v-model="gitRepoId"
                      filterable
                      clearable
                      placeholder="选择已配置的 Git 仓库"
                      class="w-full"
                      @change="handleGitRepoChange"
                    >
                      <ElOption v-for="item in gitRepoOptions" :key="item.id" :label="item.name" :value="item.id">
                        <span>{{ item.name }}</span>
                        <span class="ml-8px text-12px text-gray-500">{{ item.repoUrl }}</span>
                      </ElOption>
                    </ElSelect>
                  </ElFormItem>
                </ElCol>
                <ElCol :xs="24" :sm="12">
                  <ElFormItem label="分支 / 标签">
                    <ElInput v-model="gitRef" placeholder="留空使用仓库默认分支" @change="searchGitFiles('')" />
                  </ElFormItem>
                </ElCol>
              </ElRow>
              <ElFormItem label="选择文件">
                <ElSelect
                  v-model="gitFilePath"
                  filterable
                  remote
                  clearable
                  :remote-method="searchGitFiles"
                  :loading="gitLoadingFiles || gitLoadingContent"
                  :disabled="!gitRepoId"
                  placeholder="先选择仓库，输入关键字搜索文件"
                  class="w-full"
                  @change="handleGitFileChange"
                >
                  <ElOption v-for="file in gitFileOptions" :key="file" :label="file" :value="file" />
                </ElSelect>
              </ElFormItem>
            </template>
          </template>
          <VersionFormFields
            v-model="formModel"
            :command-type-options="commandTypeOptionsForKind"
            :command-type-label="commandTypeLabel"
            :is-module="resourceKind === 'module'"
            @type-change="onAddTypeChange"
          />
        </template>
      </ElForm>
      <template #footer>
        <ElButton text @click="cancelResourceEdit">取消</ElButton>
        <ElButton type="primary" :loading="submitting" :disabled="gitLoadingContent" @click="handleSubmit">
          确定
        </ElButton>
      </template>
    </ElDrawer>

    <ElDrawer
      v-model="versionDrawerVisible"
      :title="`版本管理 · ${currentCommand?.name ?? ''}`"
      size="min(840px, 100%)"
    >
      <div class="flex flex-col gap-12px">
        <div class="flex items-center justify-between gap-12px">
          <div>
            <div class="flex items-center gap-8px">
              <span class="text-14px">资源状态</span>
              <ElTag size="small" :type="getStatusTagType(currentCommand?.status ?? '')">
                {{ statusText[currentCommand?.status ?? ''] ?? currentCommand?.status }}
              </ElTag>
            </div>
            <p class="mt-4px text-12px text-gray-500">资源状态控制新执行是否可用；版本发布状态单独管理。</p>
          </div>
          <ElButton size="small" @click="editCurrentCommand">编辑状态</ElButton>
        </div>
        <div class="flex items-center justify-between gap-12px">
          <div>
            <span class="text-14px">资源版本</span>
            <span class="ml-8px text-12px text-gray-500 tabular-nums">{{ versionList.length }} 个版本</span>
          </div>
          <ElButton type="primary" size="small" @click="openNewVersionForm">
            {{
              versionList.some(item => item.status === 'draft')
                ? '编辑草稿'
                : versionList.some(item => item.status === 'published')
                  ? '基于已发布版本创建草稿'
                  : '新建草稿'
            }}
          </ElButton>
        </div>

        <ElTable v-loading="versionLoading" :data="versionList" border row-key="id">
          <ElTableColumn prop="version" label="版本号" width="80" align="center">
            <template #default="{ row }">v{{ row.version }}</template>
          </ElTableColumn>
          <ElTableColumn
            v-if="resourceKind === 'command' || resourceKind === 'script'"
            prop="commandType"
            :label="commandTypeLabel"
            width="130"
            align="center"
          >
            <template #default="{ row }">{{ commandTypeText[row.commandType] ?? row.commandType }}</template>
          </ElTableColumn>
          <ElTableColumn prop="status" label="状态" width="90" align="center">
            <template #default="{ row }">
              <ElTag :type="getStatusTagType(row.status)">{{ versionStatusText[row.status] ?? row.status }}</ElTag>
            </template>
          </ElTableColumn>
          <ElTableColumn prop="remark" label="版本说明" min-width="150" show-overflow-tooltip align="center" />
          <ElTableColumn prop="publishedAt" label="发布时间" min-width="170" align="center">
            <template #default="{ row }">
              <span class="tabular-nums">{{ row.publishedAt || '-' }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn prop="createdAt" label="创建时间" min-width="170" align="center">
            <template #default="{ row }">
              <span class="tabular-nums">{{ row.createdAt || '-' }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn label="操作" width="128" align="center" fixed="right">
            <template #default="{ row }">
              <div class="flex items-center justify-center gap-4px">
                <ElButton link type="primary" size="small" class="!h-32px !w-44px" @click="openVersionPrimary(row)">
                  {{ row.status === 'draft' ? '编辑' : '查看' }}
                </ElButton>
                <ElDropdown :disabled="versionActionBusy" @command="onVersionCommand($event, row)">
                  <ElButton link size="small" class="!h-32px !w-52px">更多 ∨</ElButton>
                  <template #dropdown>
                    <ElDropdownMenu>
                      <ElDropdownItem v-if="row.status === 'draft'" command="publish">发布版本</ElDropdownItem>
                      <ElDropdownItem v-if="row.status === 'draft'" divided command="delete">删除草稿</ElDropdownItem>
                      <template v-else>
                        <ElDropdownItem command="clone">基于此版本创建草稿</ElDropdownItem>
                        <ElDropdownItem v-if="row.status === 'published'" divided command="archive">
                          归档版本
                        </ElDropdownItem>
                      </template>
                    </ElDropdownMenu>
                  </template>
                </ElDropdown>
              </div>
            </template>
          </ElTableColumn>
          <template #empty>
            <ElEmpty v-if="!versionLoading" description="暂无资源版本" :image-size="80">
              <ElButton type="primary" @click="openNewVersionForm">新建草稿</ElButton>
            </ElEmpty>
          </template>
        </ElTable>
      </div>
    </ElDrawer>

    <ElDrawer
      v-model="versionFormVisible"
      :title="`${currentCommand?.name ?? ''} · ${editingVersionId ? '编辑草稿' : '新建草稿'}`"
      size="min(860px, 100%)"
      :before-close="beforeVersionClose"
      @closed="onVersionFormClosed"
    >
      <ElForm
        ref="versionFormRef"
        :disabled="versionSubmitting"
        :model="versionForm"
        :rules="versionFormRules"
        label-position="top"
        class="el-form--light"
        label-suffix="："
        require-asterisk-position="left"
      >
        <VersionFormFields
          v-model="versionForm"
          :command-type-options="commandTypeOptionsForKind"
          :command-type-label="commandTypeLabel"
          :is-module="resourceKind === 'module'"
        />
      </ElForm>
      <template #footer>
        <ElButton @click="resetVersionForm">取消</ElButton>
        <ElButton type="primary" :loading="versionSubmitting" @click="handleSaveVersion">保存草稿</ElButton>
      </template>
    </ElDrawer>

    <ElDrawer
      v-model="versionDetailVisible"
      :title="`${currentCommand?.name ?? ''} · v${versionDetail?.version ?? ''} 版本详情`"
      size="min(860px, 100%)"
      @closed="onVersionDetailClosed"
    >
      <template v-if="versionDetail">
        <ElDescriptions :column="2" border size="small">
          <ElDescriptionsItem label="版本号">v{{ versionDetail.version }}</ElDescriptionsItem>
          <ElDescriptionsItem label="状态">
            <ElTag :type="getStatusTagType(versionDetail.status)">
              {{ versionStatusText[versionDetail.status] ?? versionDetail.status }}
            </ElTag>
          </ElDescriptionsItem>
          <ElDescriptionsItem :label="commandTypeLabel">
            {{ commandTypeText[versionDetail.commandType] ?? versionDetail.commandType }}
          </ElDescriptionsItem>
          <ElDescriptionsItem label="版本备注" :span="2">{{ versionDetail.remark || '-' }}</ElDescriptionsItem>
          <ElDescriptionsItem label="发布时间">{{ versionDetail.publishedAt || '-' }}</ElDescriptionsItem>
          <ElDescriptionsItem label="创建时间">{{ versionDetail.createdAt || '-' }}</ElDescriptionsItem>
          <ElDescriptionsItem v-if="resourceKind !== 'module'" label="默认步骤超时">
            {{ versionDetail.timeoutSeconds }} 秒
          </ElDescriptionsItem>
          <ElDescriptionsItem v-if="resourceKind !== 'module'" label="提权执行">
            {{ versionDetail.becomeEnabled ? '开启' : '关闭' }}
          </ElDescriptionsItem>
          <ElDescriptionsItem v-if="resourceKind !== 'module'" label="支持检查模式">
            {{ versionDetail.checkModeSupported ? '是' : '否' }}
          </ElDescriptionsItem>
        </ElDescriptions>
        <p class="mb-8px mt-20px">{{ resourceKind === 'module' ? 'Ansible 模块名' : '执行内容' }}</p>
        <ElInput
          v-if="resourceKind === 'module'"
          :model-value="versionDetail.moduleName || versionDetail.content"
          readonly
        />
        <CodeEditor
          v-else
          :model-value="versionDetail.content"
          :language="getVersionEditorLanguage(versionDetail.commandType)"
          readonly
          height="460px"
        />
        <template v-if="resourceKind === 'module'">
          <p class="mb-4px mt-12px font-normal">参数说明</p>
          <ModuleParamDocs v-if="versionDetailParamDocs?.length" :options="versionDetailParamDocs" />
          <p v-else class="text-13px text-gray-500">该版本未配置参数说明</p>
        </template>
        <ElCollapse v-if="resourceKind !== 'module'" class="advanced-collapse mt-12px">
          <ElCollapseItem title="高级配置" name="advanced">
            <div v-if="Object.keys(versionDetail.argumentSchema || {}).length" class="adv-field">
              <span class="adv-label">历史参数校验</span>
              <div class="min-w-0 flex-1">
                <CodeEditor
                  :model-value="prettyJson(versionDetail.argumentSchema)"
                  language="plaintext"
                  readonly
                  height="120px"
                />
              </div>
            </div>
            <div class="adv-field">
              <span class="adv-label">extra_vars</span>
              <div class="min-w-0 flex-1">
                <CodeEditor
                  :model-value="prettyJson(versionDetailExtraVars)"
                  language="plaintext"
                  readonly
                  height="120px"
                />
              </div>
            </div>
            <div v-if="versionDetail.outputExtractors?.length" class="adv-field">
              <span class="adv-label">历史输出提取</span>
              <div class="min-w-0 flex-1">
                <CodeEditor
                  :model-value="prettyJson(versionDetail.outputExtractors)"
                  language="plaintext"
                  readonly
                  height="120px"
                />
              </div>
            </div>
          </ElCollapseItem>
        </ElCollapse>
      </template>
    </ElDrawer>
  </div>
</template>

<style scoped>
/** 高级配置行式布局：label 右对齐、紧挨编辑器 */
.adv-field {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.adv-field:last-child {
  margin-bottom: 0;
}

.adv-label {
  width: 72px;
  flex-shrink: 0;
  text-align: right;
  line-height: 32px;
  font-size: 12px;
  color: var(--el-text-color-regular);
}
</style>
