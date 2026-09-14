<script setup lang="tsx">
import { ref, shallowRef, watch } from 'vue';
import type { UploadFile } from 'element-plus';
import {
  fetchAddHost,
  fetchDeleteHost,
  fetchExcelImportHosts,
  fetchGetCredentialRefList,
  fetchGetHostList,
  fetchGetServiceNodeList,
  fetchUpdateHost
} from '@/service/api';
import { defaultTransform, useUIPaginatedTable } from '@/hooks/common/table';
import { $t } from '@/locales';

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
  (e: 'openManage', key: Api.Cmdb.HostManageKey): void;
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
  if (!value) return '-';
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

const { columns, columnChecks, data, getData, getDataByPage, loading, mobilePagination } = useUIPaginatedTable({
  paginationProps: {
    currentPage: searchParams.value.current,
    pageSize: searchParams.value.size
  },
  api: () =>
    fetchGetHostList({
      ...searchParams.value,
      business: props.query.business ?? undefined,
      serviceNodeIds: props.query.serviceNodeIds ?? undefined
    }),
  transform: response => defaultTransform(response),
  onPaginationParamsChange: params => {
    searchParams.value.current = params.currentPage ?? 1;
    searchParams.value.size = params.pageSize ?? 10;
  },
  columns: () => [
    { prop: 'hostname', label: $t('page.cmdb.host.hostname'), minWidth: 140, showOverflowTooltip: true },
    { prop: 'primaryIp', label: $t('page.cmdb.host.primaryIp'), width: 140, showOverflowTooltip: true },
    {
      prop: 'assetType',
      label: $t('page.cmdb.host.assetType'),
      width: 90,
      align: 'center',
      formatter: row => assetTypeText(row.assetType)
    },
    {
      prop: 'osFamily',
      label: $t('page.cmdb.host.osFamily'),
      width: 100,
      align: 'center',
      formatter: row => (
        <ElTag size="small" type={osFamilyTagType[row.osFamily] ?? 'info'}>
          {osFamilyText(row.osFamily)}
        </ElTag>
      )
    },
    {
      prop: 'osType',
      label: $t('page.cmdb.host.osType'),
      width: 120,
      showOverflowTooltip: true,
      formatter: row => row.osType || '-'
    },
    {
      prop: 'configSummary',
      label: $t('page.cmdb.host.spec'),
      width: 140,
      align: 'center',
      formatter: row => (row.cpuCores ? row.configSummary : '-')
    },
    { prop: 'appCode', label: $t('page.cmdb.host.appCode'), width: 110, showOverflowTooltip: true },
    { prop: 'ownerTeam', label: $t('page.cmdb.host.ownerTeam'), width: 110, showOverflowTooltip: true },
    {
      prop: 'region',
      label: $t('page.cmdb.host.region'),
      width: 100,
      showOverflowTooltip: true,
      formatter: row => row.region || '-'
    },
    {
      prop: 'status',
      label: $t('page.cmdb.host.statusLabel'),
      width: 90,
      align: 'center',
      formatter: row => (
        <ElTag type={hostStatusTagType[row.status] ?? 'info'}>{hostStatusText[row.status] ?? row.status}</ElTag>
      )
    },
    {
      prop: 'operate',
      label: $t('common.operate'),
      width: 140,
      align: 'center',
      fixed: 'right',
      formatter: row => (
        <>
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
        </>
      )
    }
  ]
});

const selectedRows = shallowRef<Api.Cmdb.HostRecord[]>([]);

function handleSelectionChange(rows: Api.Cmdb.HostRecord[]) {
  selectedRows.value = rows;
}

function getSelectedRows() {
  return selectedRows.value;
}

/** 左树选中范围变化后回到第一页重新查询 */
watch(
  () => props.query,
  () => {
    searchParams.value.current = 1;
    getData();
  }
);

/** ============ 新增/编辑抽屉 ============ */

type OperateType = 'add' | 'edit';

interface HostForm {
  id?: number;
  hostname: string;
  primary_ip: string;
  asset_type: string;
  os_family: Api.Cmdb.OsFamily;
  os_type: string;
  image_name: string;
  cpu_cores: number | null;
  memory_mb: number | null;
  system_disk_gb: number | null;
  data_disk_gb: number | null;
  environment: string;
  region: string;
  status: Api.Cmdb.HostStatus;
  owner_team: string;
  app_code: string;
  connection_type: Api.Cmdb.CredentialConnectionType;
  connection_port: number | null;
  credential_ref: number | null;
  service_node: number | null;
}

function createDefaultForm(): HostForm {
  return {
    hostname: '',
    primary_ip: '',
    asset_type: 'server',
    os_family: 'linux',
    os_type: '',
    image_name: '',
    cpu_cores: null,
    memory_mb: null,
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
    service_node: null
  };
}

const drawerVisible = ref(false);
const operateType = ref<OperateType>('add');
const submitting = ref(false);
const formRef = ref();
const formModel = ref<HostForm>(createDefaultForm());

const formRules = {
  hostname: [{ required: true, message: '请输入主机名', trigger: 'blur' }],
  primary_ip: [
    { required: true, message: '请输入主 IP', trigger: 'blur' },
    {
      pattern: /^(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}$/,
      message: 'IP 地址格式不正确',
      trigger: 'blur'
    }
  ],
  os_family: [{ required: true, message: '请选择 OS 类型', trigger: 'change' }]
};

/** 凭据/服务树下拉选项（首次打开抽屉时懒加载） */
const credentialOptions = ref<{ value: number; label: string }[]>([]);
const serviceNodeOptions = ref<{ value: number; label: string }[]>([]);
let optionsLoaded = false;

async function loadFormOptions() {
  if (optionsLoaded) return;
  optionsLoaded = true;
  const [credRes, nodeRes] = await Promise.all([
    fetchGetCredentialRefList({ current: 1, size: 100, isActive: true }),
    fetchGetServiceNodeList({ current: 1, size: 100, isActive: true })
  ]);
  if (!credRes.error) {
    credentialOptions.value = (credRes.data.records ?? []).map(item => ({ value: item.id, label: item.name }));
  }
  if (!nodeRes.error) {
    serviceNodeOptions.value = (nodeRes.data.records ?? []).map(item => ({
      value: item.id,
      label: `${item.name}（${item.businessName}）`
    }));
  }
}

function buildFormFromRow(row: Api.Cmdb.HostRecord): HostForm {
  return {
    id: row.id,
    hostname: row.hostname,
    primary_ip: row.primaryIp,
    asset_type: row.assetType || 'server',
    os_family: row.osFamily === 'windows' ? 'windows' : 'linux',
    os_type: row.osType,
    image_name: row.imageName,
    cpu_cores: row.cpuCores || null,
    memory_mb: row.memoryMb || null,
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
    service_node: row.serviceNode
  };
}

async function openOperateDrawer(type: OperateType, row?: Api.Cmdb.HostRecord, presetServiceNode?: number) {
  operateType.value = type;
  await loadFormOptions();
  formModel.value = row ? buildFormFromRow(row) : { ...createDefaultForm(), service_node: presetServiceNode ?? null };
  drawerVisible.value = true;
}

/** 供父组件调用：左树「添加主机」时预填服务树节点 */
function openAddDrawer(serviceNodeId?: number) {
  openOperateDrawer('add', undefined, serviceNodeId);
}

async function handleSubmit() {
  await formRef.value?.validate();

  submitting.value = true;
  const form = formModel.value;
  const payload: Api.Cmdb.HostPayload = {
    hostname: form.hostname,
    primary_ip: form.primary_ip,
    asset_type: form.asset_type,
    os_family: form.os_family,
    os_type: form.os_type,
    image_name: form.image_name,
    cpu_cores: form.cpu_cores ?? 0,
    memory_mb: form.memory_mb ?? 0,
    system_disk_gb: form.system_disk_gb ?? 0,
    data_disk_gb: form.data_disk_gb ?? 0,
    environment: form.environment,
    region: form.region,
    status: form.status,
    owner_team: form.owner_team,
    app_code: form.app_code,
    connection_type: form.connection_type,
    connection_port: form.connection_port ?? 22,
    credential_ref: form.credential_ref || null,
    service_node: form.service_node || null
  };
  const { error } =
    operateType.value === 'add' ? await fetchAddHost(payload) : await fetchUpdateHost(form.id!, payload);
  submitting.value = false;

  if (!error) {
    window.$message?.success(operateType.value === 'add' ? '新增成功' : '修改成功');
    drawerVisible.value = false;
    getData();
    emit('changed');
  }
}

async function handleDelete(id: number) {
  const { error } = await fetchDeleteHost(id);

  if (!error) {
    window.$message?.success('删除成功');
    getData();
    emit('changed');
  }
}

/** ============ Excel 导入 ============ */

const importVisible = ref(false);
const importing = ref(false);
const importFile = ref<File | null>(null);
const importSummary = ref<Api.Cmdb.HostImportSummary | null>(null);

function openImportDialog() {
  importFile.value = null;
  importSummary.value = null;
  importVisible.value = true;
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
    window.$message?.success(`导入完成：共 ${summary.total} 行，新增 ${summary.created} 条`);
    getData();
    emit('changed');
  }
}

/** ============ 管理抽屉入口 ============ */

const manageOptions: { key: Api.Cmdb.HostManageKey; label: string }[] = [
  { key: 'host-group', label: '主机分组' },
  { key: 'tag', label: '主机标签' },
  { key: 'asset-source', label: '资产来源' },
  { key: 'sync-record', label: '同步记录' }
];

function handleManageCommand(key: Api.Cmdb.HostManageKey) {
  emit('openManage', key);
}

defineExpose({ openAddDrawer, getSelectedRows, refresh: getData });
</script>

<template>
  <div class="flex-col-stretch gap-12px">
    <div class="flex items-center justify-between gap-8px">
      <div class="flex items-center gap-8px">
        <ElInput
          v-model="searchParams.search"
          clearable
          placeholder="输入名称/IP检索"
          class="w-220px"
          @keyup.enter="getDataByPage()"
        />
        <ElSelect v-model="searchParams.status" clearable placeholder="全部状态" class="w-120px">
          <ElOption v-for="item in hostStatusOptions" :key="item.value" :label="item.label" :value="item.value" />
        </ElSelect>
        <ElButton type="primary" plain @click="getDataByPage()">
          {{ $t('common.search') }}
        </ElButton>
      </div>

      <TableHeaderOperation
        v-model:columns="columnChecks"
        :loading="loading"
        :show-batch-delete="false"
        @refresh="getData"
      >
        <template #default>
          <ElDropdown trigger="click" @command="handleManageCommand">
            <ElButton>
              管理
              <template #icon>
                <icon-ic-round-arrow-drop-down class="text-icon" />
              </template>
            </ElButton>
            <template #dropdown>
              <ElDropdownMenu>
                <ElDropdownItem v-for="item in manageOptions" :key="item.key" :command="item.key">
                  {{ item.label }}
                </ElDropdownItem>
              </ElDropdownMenu>
            </template>
          </ElDropdown>
          <ElButton @click="openImportDialog()">
            <template #icon>
              <icon-ic-round-upload class="text-icon" />
            </template>
            Excel 导入
          </ElButton>
          <ElButton type="primary" @click="openOperateDrawer('add')">
            <template #icon>
              <icon-ic-round-plus class="text-icon" />
            </template>
            新建主机
          </ElButton>
        </template>
      </TableHeaderOperation>
    </div>

    <ElTable
      v-loading="loading"
      height="520px"
      border
      :data="data"
      row-key="id"
      @selection-change="handleSelectionChange"
    >
      <ElTableColumn type="selection" width="42" />
      <ElTableColumn v-for="col in columns" :key="col.prop" v-bind="col" />
    </ElTable>

    <div class="flex justify-end">
      <ElPagination
        v-if="mobilePagination.total"
        layout="total,prev,pager,next,sizes"
        v-bind="mobilePagination"
        @current-change="mobilePagination['current-change']"
        @size-change="mobilePagination['size-change']"
      />
    </div>

    <ElDrawer v-model="drawerVisible" :title="operateType === 'add' ? '新增主机' : '编辑主机'" size="480px">
      <ElForm ref="formRef" :model="formModel" :rules="formRules" label-width="90px">
        <ElFormItem label="主机名" prop="hostname">
          <ElInput v-model="formModel.hostname" placeholder="主机名" />
        </ElFormItem>
        <ElFormItem label="主 IP" prop="primary_ip">
          <ElInput v-model="formModel.primary_ip" placeholder="IPv4 地址" />
        </ElFormItem>
        <ElFormItem label="资产类型">
          <ElSelect v-model="formModel.asset_type" class="w-full">
            <ElOption v-for="item in assetTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="OS 类型" prop="os_family">
          <ElSelect v-model="formModel.os_family" class="w-full">
            <ElOption v-for="item in osFamilyOptions" :key="item.value" :label="item.label" :value="item.value" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="系统版本">
          <ElInput v-model="formModel.os_type" placeholder="如 CentOS 7.9 / Ubuntu 22.04" />
        </ElFormItem>
        <ElFormItem label="镜像名称">
          <ElInput v-model="formModel.image_name" placeholder="镜像/模板名称" />
        </ElFormItem>
        <ElFormItem label="CPU 核数">
          <ElInputNumber v-model="formModel.cpu_cores" :min="0" class="w-full" placeholder="0" />
        </ElFormItem>
        <ElFormItem label="内存(MB)">
          <ElInputNumber v-model="formModel.memory_mb" :min="0" :step="1024" class="w-full" placeholder="0" />
        </ElFormItem>
        <ElFormItem label="系统盘(GB)">
          <ElInputNumber v-model="formModel.system_disk_gb" :min="0" class="w-full" placeholder="0" />
        </ElFormItem>
        <ElFormItem label="数据盘(GB)">
          <ElInputNumber v-model="formModel.data_disk_gb" :min="0" class="w-full" placeholder="0" />
        </ElFormItem>
        <ElFormItem label="环境">
          <ElInput v-model="formModel.environment" placeholder="如 prod / staging" />
        </ElFormItem>
        <ElFormItem label="地域">
          <ElInput v-model="formModel.region" placeholder="如 cn-east-1，调度时匹配同地域 Worker 池" />
        </ElFormItem>
        <ElFormItem label="主机状态">
          <ElSelect v-model="formModel.status" class="w-full">
            <ElOption v-for="item in hostStatusOptions" :key="item.value" :label="item.label" :value="item.value" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="归属团队">
          <ElInput v-model="formModel.owner_team" placeholder="如 运维部" />
        </ElFormItem>
        <ElFormItem label="应用编码">
          <ElInput v-model="formModel.app_code" placeholder="应用系统编码" />
        </ElFormItem>
        <ElFormItem label="连接协议">
          <ElSelect v-model="formModel.connection_type" class="w-full">
            <ElOption v-for="item in connectionTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="连接端口">
          <ElInputNumber v-model="formModel.connection_port" :min="1" :max="65535" class="w-full" />
        </ElFormItem>
        <ElFormItem label="凭据">
          <ElSelect v-model="formModel.credential_ref" clearable placeholder="选择登录凭据" class="w-full">
            <ElOption v-for="item in credentialOptions" :key="item.value" :label="item.label" :value="item.value" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="服务树节点">
          <ElSelect v-model="formModel.service_node" clearable filterable placeholder="选择服务树节点" class="w-full">
            <ElOption v-for="item in serviceNodeOptions" :key="item.value" :label="item.label" :value="item.value" />
          </ElSelect>
        </ElFormItem>
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
          <p class="mt-4px text-12px text-#909399">
            表头支持：hostname、primary_ip、os_family、environment、status、owner_team、app_code 等
          </p>
        </div>
      </ElUpload>
      <div v-if="importSummary" class="mt-12px rounded-4px bg-#f5f7fa p-12px text-13px dark:bg-#262727">
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

<style scoped></style>
