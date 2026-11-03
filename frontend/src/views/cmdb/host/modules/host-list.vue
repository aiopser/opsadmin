<script setup lang="tsx">
import { ref, shallowRef, watch } from 'vue';
import type { UploadFile } from 'element-plus';
import {
  fetchAddHost,
  fetchAddTag,
  fetchAssetProbe,
  fetchBatchDeleteHost,
  fetchDeleteHost,
  fetchExcelImportHosts,
  fetchGetAssetSourceList,
  fetchGetCredentialRefList,
  fetchGetHostGroupList,
  fetchGetHostList,
  fetchGetHostRelations,
  fetchGetTagList,
  fetchTestHostConnection,
  fetchUpdateHost,
  fetchUpdateHostRelations
} from '@/service/api';
import { defaultTransform, useUIPaginatedTable } from '@/hooks/common/table';
import { $t } from '@/locales';
import CloudImportDrawer from './cloud-import-drawer.vue';
import HostAddressCell from './host-address-cell.vue';
import { buildHostPayload, formatHostDiskGb, formatHostMemory } from './shared';
import type { HostForm } from './shared';

defineOptions({ name: 'CmdbHostList' });

interface Props {
  /** 主机查询范围（由左树选中派生），空表示全部主机 */
  query?: Api.Cmdb.HostListQuery;
}

const props = withDefaults(defineProps<Props>(), {
  query: () => ({})
});

interface Emits {
  (e: 'changed'): void;
}

const emit = defineEmits<Emits>();

/** ============ 枚举文案 ============ */

const hostStatusText: Record<string, string> = {
  active: $t('page.cmdb.host.status.active'),
  inactive: $t('page.cmdb.host.status.inactive'),
  retired: $t('page.cmdb.host.status.retired')
};

const hostStatusOptions = (Object.keys(hostStatusText) as Api.Cmdb.HostStatus[]).map(value => ({
  value,
  label: hostStatusText[value]
}));

const osFamilyOptions: { value: Api.Cmdb.OsFamily; label: string }[] = [
  { value: 'linux', label: 'Linux' },
  { value: 'windows', label: 'Windows' }
];

const assetTypeOptions = [
  { value: 'server', label: '物理机' },
  { value: 'virtual_machine', label: '虚拟机' },
  { value: 'cloud_instance', label: '云主机' }
];
const connectionTypeOptions = [
  { value: 'ssh', label: 'SSH' },
  { value: 'winrm', label: 'WinRM' },
  { value: 'local', label: 'Local' }
];

const hostStatusTagType: Record<string, UI.ThemeColor> = {
  active: 'success',
  inactive: 'info',
  retired: 'warning'
};

const cloudStateLabels: Record<string, string> = {
  running: '运行中',
  stopped: '已关机',
  starting: '启动中',
  stopping: '关机中',
  suspended: '已挂起',
  paused: '已暂停',
  error: '异常',
  unknown: '未知'
};

function cloudStateText(row: Api.Cmdb.HostRecord): string {
  return row.sourceType === 'cloud' ? cloudStateLabels[row.cloudState || 'unknown'] || '未知' : '不适用';
}

const osFamilyTagType: Record<string, UI.ThemeColor> = {
  linux: 'primary',
  windows: 'warning'
};

/** OS 类型显示文案（linux → Linux） */
function osFamilyText(value: string) {
  return osFamilyOptions.find(item => item.value === value)?.label ?? value;
}

/** 资产类型显示文案（server → 物理机），空值显示 - */
function assetTypeText(value: string) {
  if (!value) return '—';
  return assetTypeOptions.find(item => item.value === value)?.label ?? value;
}

/** ============ 搜索与列表 ============ */

function getInitSearchParams() {
  return {
    current: 1,
    size: 10,
    search: undefined as string | undefined,
    status: undefined as Api.Cmdb.HostStatus | undefined
  };
}

const searchParams = ref(getInitSearchParams());

/** ============ 连通性测试（Worker 池执行 probe + 轮询结果） ============ */

const probingIds = ref(new Set<number>());

/** 每 1s 轮询一次 probe 状态，终态或超时（约 20s）返回 */
async function pollProbe(probeId: number): Promise<Api.Cmdb.AssetProbeRecord | null> {
  for (let i = 0; i < 20; i += 1) {
    // eslint-disable-next-line no-await-in-loop
    await new Promise(resolve => {
      setTimeout(resolve, 1000);
    });
    // eslint-disable-next-line no-await-in-loop
    const { error, data: probeData } = await fetchAssetProbe(probeId);
    if (error || !probeData) return null;
    if (probeData.status === 'success' || probeData.status === 'failed') return probeData;
  }
  return null;
}

interface ProbeResult {
  hostname: string;
  internalIp: string;
  ok: boolean;
  detail: string;
}

/** 对单台主机下发探测并轮询结果，返回结构化结论（单台测试与批量验证共用） */
async function runProbeOne(row: Api.Cmdb.HostRecord): Promise<ProbeResult> {
  probingIds.value.add(row.id);
  const base = { hostname: row.hostname, internalIp: row.internalIp };
  const { error, data: dispatch } = await fetchTestHostConnection(row.id);
  if (error || !dispatch) {
    probingIds.value.delete(row.id);
    return { ...base, ok: false, detail: '下发探测失败' };
  }
  const probe = await pollProbe(dispatch.probeId);
  probingIds.value.delete(row.id);
  if (!probe) return { ...base, ok: false, detail: '探测超时' };
  if (probe.status === 'success') {
    return { ...base, ok: true, detail: `执行节点：${probe.workerPoolName || '默认池'}` };
  }
  return { ...base, ok: false, detail: probe.error || '未知错误' };
}

async function handleTestConnection(row: Api.Cmdb.HostRecord) {
  const result = await runProbeOne(row);
  if (result.ok) {
    window.$notification?.success(`连通性正常（${result.detail}）`);
  } else {
    window.$message?.error(`连通性失败：${result.detail}`);
  }
}

const { columns, columnChecks, data, getData, getDataByPage, loading, mobilePagination } = useUIPaginatedTable({
  getColumnVisible: (col: UI.TableColumn<Api.Cmdb.HostRecord>) =>
    !['cloudState', 'assetSourceName'].includes(String(col.prop)),
  paginationProps: {
    currentPage: searchParams.value.current,
    pageSize: searchParams.value.size
  },
  api: () =>
    fetchGetHostList({
      ...searchParams.value,
      groupId: props.query.groupId ?? undefined
    }),
  transform: response => defaultTransform(response),
  onPaginationParamsChange: params => {
    searchParams.value.current = params.currentPage ?? 1;
    searchParams.value.size = params.pageSize ?? 10;
  },
  columns: () => [
    {
      prop: 'hostname',
      label: $t('page.cmdb.host.hostname'),
      minWidth: 180,
      showOverflowTooltip: true,
      formatter: row =>
        row.assetSourceName ? (
          <ElTooltip content={`资产来源：${row.assetSourceName}`}>
            <span>{row.hostname || '—'}</span>
          </ElTooltip>
        ) : (
          row.hostname || '—'
        )
    },
    {
      prop: 'internalIp',
      label: '内网IP',
      minWidth: 140,
      formatter: row => <HostAddressCell ip={row.internalIp} />
    },
    {
      prop: 'externalIp',
      label: '外网IP',
      minWidth: 140,
      formatter: row => <HostAddressCell ip={row.externalIp} />
    },
    {
      prop: 'assetType',
      label: $t('page.cmdb.host.assetType'),
      width: 90,
      formatter: row => assetTypeText(row.assetType)
    },
    {
      prop: 'osFamily',
      label: $t('page.cmdb.host.osFamily'),
      width: 100,
      formatter: row => (
        <ElTag size="small" type={osFamilyTagType[row.osFamily] ?? 'info'}>
          {osFamilyText(row.osFamily)}
        </ElTag>
      )
    },
    {
      prop: 'osType',
      label: $t('page.cmdb.host.osType'),
      width: 130,
      showOverflowTooltip: true,
      formatter: row => row.osType || '—'
    },
    {
      prop: 'spec',
      label: '配置',
      minWidth: 130,
      formatter: row => {
        const specText = `${row.cpuCores ? `${row.cpuCores} 核` : '—'} / ${row.memoryMb ? formatHostMemory(row.memoryMb) : '—'}`;
        // 磁盘详情收进整格悬浮提示，虚线下划线暗示可悬浮
        if (!row.systemDiskGb && !row.dataDiskGb) return specText;
        return (
          <ElTooltip placement="top" showAfter={150}>
            {{
              default: () => (
                <span class="cursor-help whitespace-nowrap border-b border-[var(--el-border-color-darker)] border-dashed tabular-nums">
                  {specText}
                </span>
              ),
              content: () => (
                <div class="flex flex-col gap-2px">
                  <span>系统盘：{row.systemDiskGb ? formatHostDiskGb(row.systemDiskGb) : '—'}</span>
                  <span>数据盘：{row.dataDiskGb ? formatHostDiskGb(row.dataDiskGb) : '—'}</span>
                </div>
              )
            }}
          </ElTooltip>
        );
      }
    },
    {
      prop: 'region',
      label: $t('page.cmdb.host.region'),
      width: 120,
      showOverflowTooltip: true,
      formatter: row => row.region || '—'
    },
    {
      prop: 'cloudState',
      label: '云运行状态',
      width: 110,
      formatter: row => cloudStateText(row)
    },
    {
      prop: 'assetSourceName',
      label: '资产来源',
      minWidth: 140,
      showOverflowTooltip: true,
      formatter: row => row.assetSourceName || '手工维护'
    },
    {
      prop: 'status',
      label: '资产状态',
      width: 90,
      formatter: row => (
        <ElTooltip
          content={
            row.sourceType === 'cloud'
              ? `云运行状态：${cloudStateText(row)}；连接是否可用请点击测试验证`
              : '人工维护的资产状态；连接是否可用请点击测试验证'
          }
        >
          <ElTag type={hostStatusTagType[row.status] ?? 'info'}>{hostStatusText[row.status] ?? row.status}</ElTag>
        </ElTooltip>
      )
    },
    {
      prop: 'operate',
      label: $t('common.operate'),
      width: 200,
      fixed: 'right',
      formatter: row => (
        <div class="flex-center">
          <ElButton
            type="success"
            plain
            size="small"
            loading={probingIds.value.has(row.id)}
            onClick={() => handleTestConnection(row)}
          >
            测试
          </ElButton>
          <ElButton type="primary" plain size="small" onClick={() => openOperateDrawer('edit', row)}>
            {$t('common.edit')}
          </ElButton>
          <ElPopconfirm title={$t('common.confirmDelete')} onConfirm={() => handleDelete(row.id)}>
            {{
              reference: () => (
                <ElButton type="danger" plain size="small">
                  {$t('common.delete')}
                </ElButton>
              )
            }}
          </ElPopconfirm>
        </div>
      )
    }
  ]
});

const selectedRows = shallowRef<Api.Cmdb.HostRecord[]>([]);
const tableRef = shallowRef<{ clearSelection: () => void } | null>(null);

function handleSelectionChange(rows: Api.Cmdb.HostRecord[]) {
  selectedRows.value = rows;
}

function getSelectedRows() {
  return selectedRows.value;
}

async function handleBatchDelete() {
  const ids = selectedRows.value.map(row => row.id);
  if (!ids.length) return;

  const { error, data: deletedCount } = await fetchBatchDeleteHost(ids);
  if (!error) {
    window.$notification?.success(`删除成功（${deletedCount?.deleted ?? ids.length} 条）`);
    tableRef.value?.clearSelection();
    getData();
    emit('changed');
  }
}

/** ============ 批量验证（分批并发探测，结果弹窗汇总） ============ */

const PROBE_BATCH_SIZE = 5;

const batchProbing = ref(false);
const probeResults = ref<ProbeResult[]>([]);
const batchProbeTotal = ref(0);
const probeDialogVisible = ref(false);

async function handleBatchProbe() {
  const rows = [...selectedRows.value];
  if (!rows.length || batchProbing.value) return;

  batchProbing.value = true;
  probeResults.value = [];
  batchProbeTotal.value = rows.length;
  probeDialogVisible.value = true;

  for (let i = 0; i < rows.length; i += PROBE_BATCH_SIZE) {
    // eslint-disable-next-line no-await-in-loop
    const batchResults = await Promise.all(rows.slice(i, i + PROBE_BATCH_SIZE).map(runProbeOne));
    probeResults.value = [...probeResults.value, ...batchResults];
  }

  batchProbing.value = false;
  const okCount = probeResults.value.filter(item => item.ok).length;
  window.$notification?.success(`验证完成：${okCount}/${probeResults.value.length} 台连通正常`);
}

/** 左树选中范围变化后回到第一页重新查询 */
watch(
  () => props.query,
  () => {
    getDataByPage();
  }
);

/** ============ 新增/编辑抽屉 ============ */

type OperateType = 'add' | 'edit';

function createDefaultForm(): HostForm {
  return {
    hostname: '',
    internal_ip: '',
    external_ip: '',
    asset_type: 'server',
    os_family: 'linux',
    os_type: '',
    image_name: '',
    cpu_cores: null,
    memory_gb: null,
    system_disk_gb: null,
    data_disk_gb: null,
    environment: '',
    region: '',
    status: 'active',
    owner_team: '',
    app_code: '',
    connection_type: 'ssh',
    connection_port: 22,
    credential_ref: null,
    group_ids: [],
    tag_ids: [],
    asset_source: null
  };
}

const drawerVisible = ref(false);
const operateType = ref<OperateType>('add');
const submitting = ref(false);
const relationsReady = ref(false);
const formRef = ref();
const formModel = ref<HostForm>(createDefaultForm());

/** 抽屉折叠分组：默认仅展开基本属性，每次打开抽屉时重置 */
const openSections = ref<string[]>(['basic']);

const IPV4_PATTERN = /^(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}$/;

const formRules = {
  hostname: [{ required: true, message: '请输入主机名', trigger: 'blur' }],
  internal_ip: [
    { required: true, message: '请输入内网IP', trigger: 'blur' },
    { pattern: IPV4_PATTERN, message: '内网IP 地址格式不正确', trigger: 'blur' }
  ],
  external_ip: [
    {
      // 外网IP 可选，填写了才校验格式
      validator: (_rule: unknown, value: string, callback: (error?: Error) => void) => {
        if (!value) {
          callback();
          return;
        }
        callback(IPV4_PATTERN.test(value) ? undefined : new Error('外网IP 地址格式不正确'));
      },
      trigger: 'blur'
    }
  ],
  os_family: [{ required: true, message: '请选择 OS 类型', trigger: 'change' }]
};

/** 凭据/分组/标签/资产来源下拉选项（首次打开抽屉时懒加载） */
const credentialOptions = ref<{ value: number; label: string }[]>([]);
const groupOptions = ref<{ value: string; label: string }[]>([]);
const tagOptions = ref<{ value: string; label: string }[]>([]);
const assetSourceOptions = ref<{ value: number; label: string }[]>([]);
let optionsLoaded = false;

async function loadFormOptions() {
  if (optionsLoaded) return;
  const [credRes, groupRes, tagRes, sourceRes] = await Promise.all([
    fetchGetCredentialRefList({ current: 1, size: 100, isActive: true }),
    // 动态分组按规则自动匹配成员，手动勾选无意义，仅列静态分组
    fetchGetHostGroupList({ current: 1, size: 500, isActive: true, groupType: 'static' }),
    fetchGetTagList({ current: 1, size: 500 }),
    fetchGetAssetSourceList({ current: 1, size: 100, isActive: true })
  ]);
  if (!credRes.error) {
    credentialOptions.value = (credRes.data.records ?? []).map(item => ({ value: item.id, label: item.name }));
  }
  if (!groupRes.error) {
    groupOptions.value = (groupRes.data.records ?? []).map(item => ({ value: String(item.id), label: item.name }));
  }
  if (!tagRes.error) {
    tagOptions.value = (tagRes.data.records ?? []).map(item => ({ value: String(item.id), label: item.label }));
  }
  if (!sourceRes.error) {
    assetSourceOptions.value = (sourceRes.data.records ?? []).map(item => ({ value: item.id, label: item.name }));
  }
  optionsLoaded = !credRes.error && !groupRes.error && !tagRes.error && !sourceRes.error;
}

function buildFormFromRow(row: Api.Cmdb.HostRecord): HostForm {
  return {
    id: row.id,
    hostname: row.hostname,
    internal_ip: row.internalIp,
    external_ip: row.externalIp ?? '',
    asset_type: row.assetType || 'server',
    os_family: row.osFamily === 'windows' ? 'windows' : 'linux',
    os_type: row.osType,
    image_name: row.imageName,
    cpu_cores: row.cpuCores || null,
    memory_gb: row.memoryMb ? row.memoryMb / 1024 : null,
    system_disk_gb: row.systemDiskGb || null,
    data_disk_gb: row.dataDiskGb || null,
    environment: row.environment,
    region: row.region ?? '',
    status: (row.status as Api.Cmdb.HostStatus) || 'active',
    owner_team: row.ownerTeam,
    app_code: row.appCode,
    connection_type: (row.connectionType as Api.Cmdb.CredentialConnectionType) || 'ssh',
    connection_port: row.connectionPort || 22,
    credential_ref: row.credentialRef,
    group_ids: row.groupIds ?? [],
    tag_ids: [],
    asset_source: row.assetSource ?? null
  };
}

async function openOperateDrawer(type: OperateType, row?: Api.Cmdb.HostRecord, presetGroupIds?: string[]) {
  drawerVisible.value = false;
  relationsReady.value = false;
  operateType.value = type;
  openSections.value = ['basic'];
  await loadFormOptions();
  const nextForm = row ? buildFormFromRow(row) : { ...createDefaultForm(), group_ids: presetGroupIds ?? [] };
  if (row) {
    // 标签关联不在列表输出中，编辑时通过 relations 接口回填（顺带校准分组）
    const { data: relations, error } = await fetchGetHostRelations(row.id);
    if (error || !relations) {
      window.$message?.error('读取主机分组和标签失败，请重新打开编辑');
      return;
    }
    nextForm.group_ids = relations.groupIds ?? [];
    nextForm.tag_ids = relations.tagIds ?? [];
  }
  formModel.value = nextForm;
  relationsReady.value = true;
  drawerVisible.value = true;
}

/** 供父组件调用：左树「添加主机」时预填所属分组 */
function openAddDrawer(groupId?: number) {
  openOperateDrawer('add', undefined, groupId ? [String(groupId)] : []);
}

/** 解析「键:值」文本为标签创建参数，非法格式返回 null */
function parseTagDraft(text: string): { key: string; value: string } | null {
  const separatorIndex = text.indexOf(':');
  if (separatorIndex <= 0) return null;
  const key = text.slice(0, separatorIndex).trim();
  const value = text.slice(separatorIndex + 1).trim();
  if (!key || !value) return null;
  return { key, value };
}

/** 创建新标签并注册进下拉选项，返回新标签 ID；失败返回 null */
async function createTag(key: string, value: string): Promise<string | null> {
  const { data: created, error } = await fetchAddTag({ key, value });
  if (error || !created) return null;
  const newId = String(created.id);
  tagOptions.value.push({ value: newId, label: created.label || `${key}:${value}` });
  return newId;
}

/**
 * 解析主机标签选择值：已有标签 ID 原样保留；
 * 「键:值」格式的新建文本先按 label 查重复用，再调用创建接口，返回最终 tagIds。
 * 任一标签非法或创建失败时返回 null，中断主机提交。
 */
async function resolveTagIds(tagIds: string[]): Promise<string[] | null> {
  const knownIds = new Set(tagOptions.value.map(item => item.value));
  const resolutions = tagIds.map(item => {
    if (knownIds.has(item)) return { id: item };
    const existed = tagOptions.value.find(option => option.label === item);
    if (existed) return { id: existed.value };
    const draft = parseTagDraft(item);
    return draft ? { draft } : null;
  });
  const invalidIndex = resolutions.findIndex(item => item === null);
  if (invalidIndex >= 0) {
    window.$message?.warning(`标签「${tagIds[invalidIndex]}」需按「键:值」格式输入`);
    return null;
  }
  const finalIds = await Promise.all(
    resolutions.map(item => {
      if (!item) return null;
      return 'id' in item ? item.id : createTag(item.draft.key, item.draft.value);
    })
  );
  if (finalIds.includes(null)) return null;
  return finalIds.filter((id): id is string => id !== null);
}

/** 主机保存成功后，全量覆盖分组/标签关联（新增时用创建返回的 id） */
async function saveHostRelations(hostId: number, form: HostForm) {
  const { error } = await fetchUpdateHostRelations(hostId, {
    groupIds: form.group_ids,
    tagIds: form.tag_ids
  });
  if (error) {
    window.$message?.warning('主机属性已保存，但分组和标签保存失败；修改已保留，请重试保存');
  }
  return !error;
}

async function handleSubmit() {
  if (!relationsReady.value) {
    window.$message?.error('主机分组和标签尚未加载成功，请重新打开编辑');
    return;
  }
  await formRef.value?.validate();

  submitting.value = true;
  try {
    const form = formModel.value;
    // 先将「键:值」新建文本落库为真实标签，再保存主机与关联
    const finalTagIds = await resolveTagIds(form.tag_ids);
    if (finalTagIds === null) {
      return;
    }
    form.tag_ids = finalTagIds;
    const payload = buildHostPayload(form);
    const { error, data: saved } =
      operateType.value === 'add' ? await fetchAddHost(payload) : await fetchUpdateHost(form.id!, payload);
    if (error) return;
    const hostId = saved?.id ?? form.id;
    if (!hostId) {
      window.$message?.error('未收到主机保存结果，请刷新列表确认');
      return;
    }
    form.id = hostId;
    const relationsSaved = await saveHostRelations(hostId, form);
    if (!relationsSaved) {
      operateType.value = 'edit';
      getData();
      emit('changed');
      return;
    }
    window.$notification?.success(operateType.value === 'add' ? '新增成功' : '修改成功');
    drawerVisible.value = false;
    getData();
    emit('changed');
  } finally {
    submitting.value = false;
  }
}

async function handleDelete(id: number) {
  const { error } = await fetchDeleteHost(id);

  if (!error) {
    window.$notification?.success('删除成功');
    getData();
    emit('changed');
  }
}

/** ============ Excel 导入 ============ */

const importVisible = ref(false);
const importing = ref(false);
const importFile = ref<File | null>(null);
const importSummary = ref<Api.Cmdb.HostImportSummary | null>(null);
const cloudImportRef = ref<InstanceType<typeof CloudImportDrawer>>();

function openImportDialog() {
  importFile.value = null;
  importSummary.value = null;
  importVisible.value = true;
}

/** 「新建」下拉入口分发 */
function handleCreateCommand(command: string) {
  if (command === 'host') {
    openOperateDrawer('add');
    return;
  }
  if (command === 'excel') {
    openImportDialog();
    return;
  }
  if (command === 'cloud') cloudImportRef.value?.open();
}

function handleImportFileChange(file: UploadFile) {
  importFile.value = (file.raw as File | undefined) ?? null;
}

function handleImportFileRemove() {
  importFile.value = null;
}

async function handleImport() {
  if (!importFile.value) {
    window.$message?.warning('请先选择 .xlsx 文件');
    return;
  }

  importing.value = true;
  const { error, data: summary } = await fetchExcelImportHosts(importFile.value);
  importing.value = false;

  if (!error) {
    importSummary.value = summary;
    window.$notification?.success(`导入完成：共 ${summary.total} 行，新增 ${summary.created} 条`);
    getData();
    emit('changed');
  }
}

/** ============ 管理抽屉入口（分组/标签/资产来源已内嵌到主机表单基本属性） ============ */

defineExpose({ openAddDrawer, getSelectedRows, refresh: getData });
</script>

<template>
  <div class="min-h-0 flex flex-col flex-1 gap-12px">
    <CloudImportDrawer ref="cloudImportRef" @submitted="getData" />
    <div class="flex flex-wrap items-center justify-between gap-8px">
      <div class="flex flex-wrap items-center gap-8px">
        <ElInput
          v-model="searchParams.search"
          clearable
          placeholder="输入主机名称或 IP 地址"
          aria-label="主机名称或 IP 地址"
          class="w-220px lt-sm:w-full"
          @clear="getDataByPage()"
          @keyup.enter="getDataByPage()"
        />
        <ElSelect
          v-model="searchParams.status"
          clearable
          placeholder="全部状态"
          aria-label="主机状态"
          class="w-120px"
          @change="getDataByPage()"
          @clear="getDataByPage()"
        >
          <ElOption v-for="item in hostStatusOptions" :key="item.value" :label="item.label" :value="item.value" />
        </ElSelect>
      </div>

      <TableHeaderOperation v-model:columns="columnChecks" :loading="loading" @refresh="getData">
        <template #default>
          <ElPopconfirm title="确认删除选中的主机？" @confirm="handleBatchDelete">
            <template #reference>
              <ElButton type="danger" plain :disabled="!selectedRows.length">批量删除</ElButton>
            </template>
          </ElPopconfirm>
          <ElButton plain :loading="batchProbing" :disabled="!selectedRows.length" @click="handleBatchProbe">
            批量验证
          </ElButton>
          <ElDropdown trigger="click" @command="handleCreateCommand">
            <ElButton type="primary">
              <template #icon>
                <icon-ic-round-plus class="text-icon" />
              </template>
              新建
              <icon-mdi-chevron-down class="ml-2px text-icon" />
            </ElButton>
            <template #dropdown>
              <ElDropdownMenu>
                <ElDropdownItem command="host">
                  <icon-ic-round-edit class="mr-8px text-icon" />
                  新建主机
                </ElDropdownItem>
                <ElDropdownItem command="excel">
                  <icon-mdi-microsoft-excel class="mr-8px text-icon text-success" />
                  Excel
                </ElDropdownItem>
                <ElDropdownItem divided command="cloud">
                  <icon-mdi-cloud class="mr-8px text-icon text-primary" />
                  导入云主机
                </ElDropdownItem>
              </ElDropdownMenu>
            </template>
          </ElDropdown>
        </template>
      </TableHeaderOperation>
    </div>

    <div class="min-h-240px flex-1 lt-sm:h-400px lt-sm:flex-none">
      <ElTable
        ref="tableRef"
        v-loading="loading"
        height="100%"
        border
        :data="data"
        row-key="id"
        :cell-style="{ verticalAlign: 'top' }"
        @selection-change="handleSelectionChange"
      >
        <ElTableColumn type="selection" width="42" align="center" header-align="center" />
        <ElTableColumn v-for="col in columns" :key="col.prop" v-bind="col" align="center" header-align="center" />
      </ElTable>
    </div>

    <div class="flex shrink-0 justify-end overflow-x-auto">
      <ElPagination
        v-if="mobilePagination.total"
        layout="total,prev,pager,next,sizes"
        v-bind="mobilePagination"
        @current-change="mobilePagination['current-change']"
        @size-change="mobilePagination['size-change']"
      />
    </div>

    <ElDialog v-model="probeDialogVisible" title="批量连通性验证" width="640px">
      <div class="mb-12px flex items-center justify-between">
        <span class="text-13px">
          进度：{{ probeResults.length }} / {{ batchProbeTotal }}
          <span v-if="batchProbing" class="text-primary">探测中…</span>
        </span>
        <span class="text-13px">
          连通正常
          <span class="text-success font-bold">{{ probeResults.filter(item => item.ok).length }}</span>
          / 失败
          <span class="text-danger font-bold">{{ probeResults.filter(item => !item.ok).length }}</span>
        </span>
      </div>
      <ElTable :data="probeResults" height="360px" border size="small">
        <ElTableColumn prop="hostname" label="主机名" min-width="140" align="center" show-overflow-tooltip />
        <ElTableColumn prop="internalIp" label="内网IP" width="140" align="center" />
        <ElTableColumn label="结果" width="90" align="center">
          <template #default="{ row }">
            <ElTag size="small" :type="row.ok ? 'success' : 'danger'">{{ row.ok ? '连通' : '失败' }}</ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn prop="detail" label="详情" min-width="180" align="center" show-overflow-tooltip />
      </ElTable>
      <template #footer>
        <ElButton :disabled="batchProbing" @click="probeDialogVisible = false">关闭</ElButton>
      </template>
    </ElDialog>

    <ElDrawer v-model="drawerVisible" :title="operateType === 'add' ? '新增主机' : '编辑主机'" size="720px">
      <ElForm
        ref="formRef"
        :model="formModel"
        :rules="formRules"
        label-position="top"
        require-asterisk-position="left"
        label-suffix="："
      >
        <ElCollapse v-model="openSections" class="advanced-collapse">
          <ElCollapseItem title="基本属性" name="basic">
            <ElRow :gutter="16">
              <ElCol :xs="24" :sm="12">
                <ElFormItem label="主机名" prop="hostname">
                  <ElInput v-model="formModel.hostname" placeholder="主机名" />
                </ElFormItem>
              </ElCol>
              <ElCol :xs="24" :sm="12">
                <ElFormItem prop="internal_ip">
                  <template #label>
                    <FormLabelHelp
                      label="内网IP"
                      :help="[
                        '必填，仅支持 IPv4 格式，如 10.0.0.11',
                        '与主机名共同构成同步匹配键，同步时据此判断新增或更新'
                      ]"
                    />
                  </template>
                  <ElInput v-model="formModel.internal_ip" placeholder="IPv4 地址" />
                </ElFormItem>
              </ElCol>
              <ElCol :xs="24" :sm="12">
                <ElFormItem label="外网IP" prop="external_ip">
                  <ElInput v-model="formModel.external_ip" placeholder="可选，IPv4 地址" />
                </ElFormItem>
              </ElCol>
              <ElCol :xs="24" :sm="12">
                <ElFormItem label="资产类型">
                  <ElSelect v-model="formModel.asset_type" class="w-full">
                    <ElOption
                      v-for="item in assetTypeOptions"
                      :key="item.value"
                      :label="item.label"
                      :value="item.value"
                    />
                  </ElSelect>
                </ElFormItem>
              </ElCol>
              <ElCol :xs="24" :sm="12">
                <ElFormItem prop="os_family">
                  <template #label>
                    <FormLabelHelp
                      label="操作系统"
                      :help="['按目标系统选择 Linux / Windows', 'Windows 主机需搭配 WinRM 连接协议与凭据使用']"
                    />
                  </template>
                  <ElSelect v-model="formModel.os_family" class="w-full">
                    <ElOption
                      v-for="item in osFamilyOptions"
                      :key="item.value"
                      :label="item.label"
                      :value="item.value"
                    />
                  </ElSelect>
                </ElFormItem>
              </ElCol>
              <ElCol :xs="24" :sm="12">
                <ElFormItem label="系统版本">
                  <ElInput v-model="formModel.os_type" placeholder="如 CentOS 7.9 / Ubuntu 22.04" />
                </ElFormItem>
              </ElCol>
              <ElCol :xs="24" :sm="12">
                <ElFormItem label="环境">
                  <ElInput v-model="formModel.environment" placeholder="如 prod / staging" />
                </ElFormItem>
              </ElCol>
              <ElCol :xs="24" :sm="12">
                <ElFormItem>
                  <template #label>
                    <FormLabelHelp
                      label="主机状态"
                      :help="['仅「在用」状态的主机可作为任务执行与连通性测试的目标', '停用、退役的主机不参与执行调度']"
                    />
                  </template>
                  <ElSelect v-model="formModel.status" class="w-full">
                    <ElOption
                      v-for="item in hostStatusOptions"
                      :key="item.value"
                      :label="item.label"
                      :value="item.value"
                    />
                  </ElSelect>
                </ElFormItem>
              </ElCol>
              <ElCol :xs="24" :sm="12">
                <ElFormItem>
                  <template #label>
                    <FormLabelHelp
                      label="主机分组"
                      :help="[
                        '可多选，保存后全量覆盖该主机的分组关联',
                        '动态分组按规则自动匹配成员，无需手动勾选；此处仅列出静态分组'
                      ]"
                    />
                  </template>
                  <ElSelect
                    v-model="formModel.group_ids"
                    multiple
                    filterable
                    collapse-tags
                    collapse-tags-tooltip
                    placeholder="选择所属静态分组"
                    class="w-full"
                  >
                    <ElOption v-for="item in groupOptions" :key="item.value" :label="item.label" :value="item.value" />
                  </ElSelect>
                </ElFormItem>
              </ElCol>
              <ElCol :xs="24" :sm="12">
                <ElFormItem>
                  <template #label>
                    <FormLabelHelp
                      label="主机标签"
                      :help="[
                        '可多选，用于按维度筛选主机',
                        '下拉选择已有标签，输入「键:值」回车即新建标签',
                        '保存后全量覆盖该主机的标签关联'
                      ]"
                    />
                  </template>
                  <ElSelect
                    v-model="formModel.tag_ids"
                    multiple
                    filterable
                    allow-create
                    :reserve-keyword="false"
                    collapse-tags
                    collapse-tags-tooltip
                    placeholder="选择已有标签，或输入 键:值 新建"
                    class="w-full"
                  >
                    <ElOption v-for="item in tagOptions" :key="item.value" :label="item.label" :value="item.value" />
                  </ElSelect>
                </ElFormItem>
              </ElCol>
              <ElCol :xs="24" :sm="12">
                <ElFormItem>
                  <template #label>
                    <FormLabelHelp
                      label="资产来源"
                      :help="[
                        '标识该主机的资产登记途径：手工维护、云平台或外部 CMDB',
                        '由「资产来源-同步」写入的主机会自动标记对应来源'
                      ]"
                    />
                  </template>
                  <ElSelect v-model="formModel.asset_source" clearable placeholder="选择资产来源" class="w-full">
                    <ElOption
                      v-for="item in assetSourceOptions"
                      :key="item.value"
                      :label="item.label"
                      :value="item.value"
                    />
                  </ElSelect>
                </ElFormItem>
              </ElCol>
            </ElRow>
          </ElCollapseItem>

          <ElCollapseItem title="系统属性" name="system">
            <ElRow :gutter="16">
              <ElCol :xs="24" :sm="12">
                <ElFormItem label="镜像名称">
                  <ElInput v-model="formModel.image_name" placeholder="镜像/模板名称" />
                </ElFormItem>
              </ElCol>
              <ElCol :xs="24" :sm="12">
                <ElFormItem>
                  <template #label>
                    <FormLabelHelp
                      label="地域"
                      :help="['任务执行时优先路由到同地域的执行节点池', '留空表示不参与地域路由']"
                    />
                  </template>
                  <ElInput v-model="formModel.region" placeholder="如 cn-east-1，调度时匹配同地域执行节点池" />
                </ElFormItem>
              </ElCol>
              <ElCol :xs="24" :sm="12">
                <ElFormItem>
                  <template #label>
                    <FormLabelHelp label="CPU" :help="['单位：核，如 8 表示 8 核', '可通过主机探测自动采集回填']" />
                  </template>
                  <ElInputNumber v-model="formModel.cpu_cores" :min="0" class="w-full" placeholder="0" />
                </ElFormItem>
              </ElCol>
              <ElCol :xs="24" :sm="12">
                <ElFormItem label="内存（GB）">
                  <ElInputNumber v-model="formModel.memory_gb" :min="0" :step="1" class="w-full" placeholder="0" />
                </ElFormItem>
              </ElCol>
              <ElCol :xs="24" :sm="12">
                <ElFormItem label="系统盘（GB）">
                  <ElInputNumber v-model="formModel.system_disk_gb" :min="0" class="w-full" placeholder="0" />
                </ElFormItem>
              </ElCol>
              <ElCol :xs="24" :sm="12">
                <ElFormItem label="数据盘（GB）">
                  <ElInputNumber v-model="formModel.data_disk_gb" :min="0" class="w-full" placeholder="0" />
                </ElFormItem>
              </ElCol>
            </ElRow>
          </ElCollapseItem>

          <ElCollapseItem title="设备属性" name="device">
            <ElRow :gutter="16">
              <ElCol :xs="24" :sm="12">
                <ElFormItem label="归属团队">
                  <ElInput v-model="formModel.owner_team" placeholder="如 运维部" />
                </ElFormItem>
              </ElCol>
              <ElCol :xs="24" :sm="12">
                <ElFormItem label="应用编码">
                  <ElInput v-model="formModel.app_code" placeholder="应用系统编码" />
                </ElFormItem>
              </ElCol>
              <ElCol :xs="24" :sm="12">
                <ElFormItem>
                  <template #label>
                    <FormLabelHelp
                      label="连接协议"
                      :help="['Linux 主机使用 SSH，Windows 主机使用 WinRM', '连通性测试与任务下发时按该协议连接目标机']"
                    />
                  </template>
                  <ElSelect v-model="formModel.connection_type" class="w-full">
                    <ElOption
                      v-for="item in connectionTypeOptions"
                      :key="item.value"
                      :label="item.label"
                      :value="item.value"
                    />
                  </ElSelect>
                </ElFormItem>
              </ElCol>
              <ElCol :xs="24" :sm="12">
                <ElFormItem>
                  <template #label>
                    <FormLabelHelp
                      label="连接端口"
                      :help="['目标主机的实际监听端口，范围 1-65535', 'SSH 默认 22，WinRM 一般为 5985']"
                    />
                  </template>
                  <ElInputNumber v-model="formModel.connection_port" :min="1" :max="65535" class="w-full" />
                </ElFormItem>
              </ElCol>
              <ElCol :xs="24" :sm="12">
                <ElFormItem>
                  <template #label>
                    <FormLabelHelp
                      label="凭据"
                      :help="[
                        '登录目标主机的账号与密钥，连通性测试、任务下发均使用该凭据',
                        '未配置凭据的主机无法正常执行测试与任务'
                      ]"
                    />
                  </template>
                  <ElSelect v-model="formModel.credential_ref" clearable placeholder="选择登录凭据" class="w-full">
                    <ElOption
                      v-for="item in credentialOptions"
                      :key="item.value"
                      :label="item.label"
                      :value="item.value"
                    />
                  </ElSelect>
                </ElFormItem>
              </ElCol>
            </ElRow>
          </ElCollapseItem>
        </ElCollapse>
      </ElForm>
      <template #footer>
        <ElButton @click="drawerVisible = false">
          {{ $t('common.cancel') }}
        </ElButton>
        <ElButton type="primary" :loading="submitting" @click="handleSubmit">
          {{ $t('common.confirm') }}
        </ElButton>
      </template>
    </ElDrawer>

    <ElDialog v-model="importVisible" title="Excel 批量导入主机" width="560px" :close-on-click-modal="false">
      <ElUpload
        drag
        accept=".xlsx"
        :auto-upload="false"
        :limit="1"
        :on-change="handleImportFileChange"
        :on-remove="handleImportFileRemove"
      >
        <div class="py-16px text-13px">
          <p>将 .xlsx 文件拖到此处，或点击选择文件</p>
          <p class="mt-4px text-12px text-[var(--el-text-color-secondary)]">
            表头支持：hostname、internal_ip（兼容旧字段
            ip/primary_ip）、external_ip（可选）、os_family、environment、status、owner_team、app_code、
            group_names（按分组名追加，多个用英文逗号分隔，需为已有静态分组）等
          </p>
        </div>
      </ElUpload>
      <div v-if="importSummary" class="mt-12px rounded-4px bg-[var(--el-fill-color-light)] p-12px text-13px">
        <p>
          共 {{ importSummary.total }} 行：新增 {{ importSummary.created }}，跳过 {{ importSummary.skipped }}， 无效
          {{ importSummary.invalid.length }}，失败 {{ importSummary.errors.length }}
        </p>
        <p v-if="importSummary.invalid.length" class="mt-6px break-all text-red-500">
          无效行：{{ JSON.stringify(importSummary.invalid) }}
        </p>
        <p v-if="importSummary.errors.length" class="mt-6px break-all text-red-500">
          错误：{{ JSON.stringify(importSummary.errors) }}
        </p>
      </div>
      <template #footer>
        <ElButton @click="importVisible = false">关闭</ElButton>
        <ElButton type="primary" :loading="importing" @click="handleImport">开始导入</ElButton>
      </template>
    </ElDialog>
  </div>
</template>
