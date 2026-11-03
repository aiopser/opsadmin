<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, shallowRef } from 'vue';
import type { FormInstance } from 'element-plus';
import { fetchGetHostList } from '@/service/api/cmdb';
import type {
  ConsulConnection,
  MonitoringSyncRecord,
  MonitoringTarget,
  MonitoringTargetInput,
  TargetKind
} from '@/service/api/monitoring';
import {
  deleteMonitoringTarget,
  getConsulConnections,
  getMonitoringAlertRules,
  getMonitoringRecords,
  getMonitoringTargets,
  getPrometheusConfig,
  previewMonitoringTarget,
  saveMonitoringTarget,
  syncMonitoringTarget
} from '@/service/api/monitoring';
import { useAuth } from '@/hooks/business/auth';
import HostImportDrawer from './modules/host-import-drawer.vue';

defineOptions({ name: 'MonitoringTargets' });

const { hasAuth } = useAuth();
const importVisible = ref(false);
const hostOptions = shallowRef<Api.Cmdb.HostRecord[]>([]);
const hostLoading = ref(false);
let hostSequence = 0;
let recordSequence = 0;

const keyword = ref('');
const query = ref('');
const page = ref(1);
const total = ref(0);
const rows = shallowRef<MonitoringTarget[]>([]);
const connections = shallowRef<ConsulConnection[]>([]);
const loading = ref(false);
const editor = ref(false);
const editingId = ref<number>();
const saving = ref(false);
const formRef = shallowRef<FormInstance>();
const form = ref<MonitoringTargetInput>(emptyForm());
const missingSelectedHost = computed(
  () => form.value.host && !hostOptions.value.some(item => item.id === form.value.host)
);
const metaText = ref('{}');
const metaError = ref('');
const rules = {
  name: [{ required: true, message: '请输入目标名称', trigger: 'blur' }],
  connection: [{ required: true, message: '请选择 Consul 连接', trigger: 'change' }],
  address: [{ required: true, message: '请输入 Exporter 地址', trigger: 'blur' }],
  probe_target: [{ required: true, message: '请输入探测地址', trigger: 'blur' }]
};
const kinds: { value: TargetKind; label: string }[] = [
  { value: 'host', label: '主机' },
  { value: 'mysql', label: 'MySQL' },
  { value: 'redis', label: 'Redis' },
  { value: 'blackbox', label: '站点探测' }
];
const busyId = ref<number>();
const previewVisible = ref(false);
const previewTitle = ref('注册预览');
const previewContent = ref('');
const previewNote = ref('');
const recordsVisible = ref(false);
const records = shallowRef<MonitoringSyncRecord[]>([]);
const recordsTotal = ref(0);
const recordsPage = ref(1);
const selectedTarget = shallowRef<MonitoringTarget>();
const recordsLoading = ref(false);
let timer: ReturnType<typeof setTimeout> | undefined;
let loadSequence = 0;
let disposed = false;

function emptyForm(): MonitoringTargetInput {
  return {
    name: '',
    connection: undefined,
    kind: 'host',
    address: '',
    port: 9100,
    tags: [],
    meta: {},
    check_enabled: false,
    probe_target: '',
    probe_module: 'http_2xx',
    sync_interval_minutes: 0,
    follow_host_address: false,
    address_source: 'internal'
  };
}
async function load() {
  loadSequence += 1;
  const sequence = loadSequence;
  loading.value = true;
  if (timer) clearTimeout(timer);
  try {
    const { data, error } = await getMonitoringTargets(page.value, query.value);
    if (disposed || sequence !== loadSequence) return;
    if (!error && data) {
      rows.value = data.list;
      total.value = data.total;
      if (rows.value.some(row => ['queued', 'running'].includes(row.sync_state))) timer = setTimeout(load, 5000);
    }
  } finally {
    if (sequence === loadSequence) loading.value = false;
  }
}
async function init() {
  const { data, error } = await getConsulConnections();
  if (!error && data) connections.value = data;
  await load();
}
async function search() {
  page.value = 1;
  query.value = keyword.value.trim();
  await load();
}
function reset() {
  keyword.value = '';
  search();
}
function kindLabel(value: string) {
  return kinds.find(item => item.value === value)?.label || value;
}
function stateLabel(value: string) {
  return (
    (
      {
        queued: '排队中',
        running: '同步中',
        succeeded: '成功',
        failed: '失败',
        synced: '已同步',
        pending: '有修改待同步',
        unregistered: '未注册'
      } as Record<string, string>
    )[value] || value
  );
}
function stateType(value: string): 'success' | 'danger' | 'warning' | 'info' {
  if (value === 'synced' || value === 'succeeded') return 'success';
  if (value === 'failed') return 'danger';
  if (value === 'pending' || value === 'running' || value === 'queued') return 'warning';
  return 'info';
}
function isBusy(row: MonitoringTarget) {
  return ['queued', 'running'].includes(row.sync_state) || busyId.value === row.id;
}
function add() {
  editingId.value = undefined;
  form.value = emptyForm();
  metaText.value = '{}';
  metaError.value = '';
  editor.value = true;
  hostOptions.value = [];
}
function edit(row: MonitoringTarget) {
  editingId.value = row.id;
  form.value = {
    name: row.name,
    connection: row.connection,
    host: row.host,
    kind: row.kind,
    address: row.address,
    port: row.port,
    tags: [...row.tags],
    meta: { ...row.meta },
    check_enabled: row.check_enabled,
    probe_target: row.probe_target,
    probe_module: row.probe_module,
    sync_interval_minutes: row.sync_interval_minutes,
    follow_host_address: row.follow_host_address,
    address_source: row.address_source
  };
  metaText.value = JSON.stringify(row.meta, null, 2);
  metaError.value = '';
  editor.value = true;
  hostOptions.value = [];
}
function changeKind() {
  const ports: Record<TargetKind, number> = {
    host: 9100,
    mysql: 9104,
    redis: 9121,
    blackbox: 9115
  };
  form.value.port = ports[form.value.kind];
}
function parseMeta(): Record<string, string> | undefined {
  try {
    const parsed: unknown = JSON.parse(metaText.value || '{}');
    if (
      !parsed ||
      typeof parsed !== 'object' ||
      Array.isArray(parsed) ||
      Object.values(parsed).some(value => typeof value !== 'string')
    )
      throw new Error('invalid');
    return Object.fromEntries(Object.entries(parsed).map(([key, value]) => [key, String(value)]));
  } catch {
    metaError.value = 'Meta 必须是键值均为字符串的 JSON 对象';
    return undefined;
  }
}
async function save() {
  metaError.value = '';
  const meta = parseMeta();
  if (!meta || !(await formRef.value?.validate().catch(() => false))) return;
  saving.value = true;
  try {
    const { error } = await saveMonitoringTarget(editingId.value, {
      ...form.value,
      meta
    });
    if (!error) {
      editor.value = false;
      window.$notification?.success('保存成功，请同步以更新 Consul');
      await load();
    }
  } finally {
    saving.value = false;
  }
}
async function preview(row: MonitoringTarget) {
  const { data, error } = await previewMonitoringTarget(row.id);
  if (!error && data) {
    previewTitle.value = '注册预览';
    previewContent.value = JSON.stringify(data, null, 2);
    previewNote.value = '预览不会写入 Consul。';
    previewVisible.value = true;
  }
}
async function config(row: MonitoringTarget) {
  const { data, error } = await getPrometheusConfig(row.connection);
  if (!error && data) {
    previewTitle.value = 'Prometheus 配置';
    previewContent.value = data.config;
    previewNote.value = data.note;
    previewVisible.value = true;
  }
}
async function showRules(row: MonitoringTarget) {
  const { data, error } = await getMonitoringAlertRules(row.connection);
  if (!error && data) {
    previewTitle.value = '基础告警规则';
    previewContent.value = data.config;
    previewNote.value = data.note;
    previewVisible.value = true;
  }
}
async function operate(row: MonitoringTarget, operation: 'sync' | 'deregister') {
  busyId.value = row.id;
  try {
    const { error } = await syncMonitoringTarget(row.id, operation);
    if (!error) {
      window.$notification?.success('已提交，请查看同步状态与记录');
      await load();
    }
  } finally {
    busyId.value = undefined;
  }
}
async function register(row: MonitoringTarget) {
  await operate(row, 'sync');
}
async function deregister(row: MonitoringTarget) {
  await operate(row, 'deregister');
}
async function remove(row: MonitoringTarget) {
  const { error } = await deleteMonitoringTarget(row.id);
  if (!error) await load();
}
async function loadRecords() {
  const target = selectedTarget.value;
  if (!target) return;
  recordSequence += 1;
  const sequence = recordSequence;
  recordsLoading.value = true;
  try {
    const { data, error } = await getMonitoringRecords(target.id, recordsPage.value);
    if (disposed || sequence !== recordSequence) return;
    if (!error && data) {
      records.value = data.list;
      recordsTotal.value = data.total;
    }
  } finally {
    if (sequence === recordSequence) recordsLoading.value = false;
  }
}
async function showRecords(row: MonitoringTarget) {
  selectedTarget.value = row;
  records.value = [];
  recordsTotal.value = 0;
  recordsPage.value = 1;
  recordsVisible.value = true;
  await loadRecords();
}
function closeEditor() {
  editor.value = false;
}
async function openImport() {
  const { data, error } = await getConsulConnections();
  if (!error && data) {
    connections.value = data;
    importVisible.value = true;
  }
}
function triggerLabel(value: string) {
  return ({ manual: '手动', batch: '批量接入', automatic: '定时同步' } as Record<string, string>)[value] || value;
}

async function searchHosts(hostQuery: string) {
  hostSequence += 1;
  const sequence = hostSequence;
  hostLoading.value = true;
  try {
    const { data, error } = await fetchGetHostList({
      current: 1,
      size: 20,
      search: hostQuery
    });
    if (!disposed && sequence === hostSequence && !error && data) hostOptions.value = data.records;
  } finally {
    if (sequence === hostSequence) hostLoading.value = false;
  }
}
function selectHost(id: number | null | undefined) {
  form.value.host = id || null;
  if (!id) form.value.follow_host_address = false;
  const host = hostOptions.value.find(item => item.id === id);
  if (host && !form.value.address) form.value.address = host.internalIp || host.externalIp || '';
}

onMounted(init);
onUnmounted(() => {
  disposed = true;
  recordSequence += 1;
  hostSequence += 1;
  loadSequence += 1;
  if (timer) clearTimeout(timer);
});
</script>

<template>
  <div class="flex-col-stretch gap-16px">
    <SearchPanel @search="search" @reset="reset">
      <ElForm label-width="80px" @submit.prevent="search">
        <ElFormItem label="关键词">
          <ElInput v-model="keyword" clearable placeholder="目标名称 / 地址 / 实例 ID" @keyup.enter="search" />
        </ElFormItem>
      </ElForm>
    </SearchPanel>
    <ElCard class="card-wrapper">
      <template #header>
        <div class="flex items-center justify-between gap-12px">
          <span>监控目标</span>
          <div class="flex gap-8px">
            <ElButton v-if="hasAuth('monitoring.target:create')" type="primary" @click="add">新增目标</ElButton>
            <ElButton v-if="hasAuth('monitoring.target:host_import')" @click="openImport">从资产接入</ElButton>
            <ElButton :loading="loading" @click="load">刷新</ElButton>
          </div>
        </div>
      </template>
      <ElTable v-loading="loading" :data="rows" border>
        <ElTableColumn prop="name" label="名称" min-width="130" align="center" show-overflow-tooltip />
        <ElTableColumn label="类型" width="100" align="center">
          <template #default="{ row }">{{ kindLabel(row.kind) }}</template>
        </ElTableColumn>
        <ElTableColumn
          prop="connection_name"
          label="Consul 连接"
          min-width="130"
          align="center"
          show-overflow-tooltip
        />
        <ElTableColumn label="Exporter 地址" min-width="180" align="center" show-overflow-tooltip>
          <template #default="{ row }">{{ row.address }}:{{ row.port }}</template>
        </ElTableColumn>
        <ElTableColumn prop="probe_target" label="探测目标" min-width="170" align="center" show-overflow-tooltip>
          <template #default="{ row }">{{ row.kind === 'blackbox' ? row.probe_target : '—' }}</template>
        </ElTableColumn>
        <ElTableColumn label="同步状态" width="140" align="center">
          <template #default="{ row }">
            <ElTag :type="stateType(row.sync_state)">{{ stateLabel(row.sync_state) }}</ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn label="定时同步" width="130" align="center">
          <template #default="{ row }">
            {{ row.sync_interval_minutes ? `每 ${row.sync_interval_minutes} 分钟` : '关闭' }}
          </template>
        </ElTableColumn>
        <ElTableColumn label="操作" width="360" align="center" fixed="right">
          <template #default="{ row }">
            <ElButton
              v-if="hasAuth('monitoring.target:update')"
              link
              type="primary"
              :disabled="isBusy(row)"
              @click="edit(row)"
            >
              编辑
            </ElButton>
            <ElButton link type="primary" @click="preview(row)">预览</ElButton>
            <ElButton
              v-if="hasAuth('monitoring.target:sync')"
              link
              type="primary"
              :disabled="isBusy(row)"
              @click="register(row)"
            >
              同步
            </ElButton>
            <ElButton link type="primary" @click="showRecords(row)">记录</ElButton>
            <ElDropdown trigger="click">
              <ElButton link type="primary" class="ml-12px">更多</ElButton>
              <template #dropdown>
                <ElDropdownMenu>
                  <ElDropdownItem @click="config(row)">Prometheus 配置</ElDropdownItem>
                  <ElDropdownItem @click="showRules(row)">基础告警规则</ElDropdownItem>
                  <ElDropdownItem v-if="hasAuth('monitoring.target:deregister')" :disabled="isBusy(row)">
                    <ElPopconfirm
                      title="确认注销？将暂停定时同步，并从当前 Agent 移除此目标的注册。"
                      @confirm="deregister(row)"
                    >
                      <template #reference><span>注销服务</span></template>
                    </ElPopconfirm>
                  </ElDropdownItem>
                  <ElDropdownItem
                    v-if="hasAuth('monitoring.target:delete')"
                    :disabled="row.registered || row.registration_uncertain || isBusy(row)"
                  >
                    <ElPopconfirm title="确认删除目标？历史同步记录仍会保留。" @confirm="remove(row)">
                      <template #reference><span>删除目标</span></template>
                    </ElPopconfirm>
                  </ElDropdownItem>
                </ElDropdownMenu>
              </template>
            </ElDropdown>
          </template>
        </ElTableColumn>
        <template #empty>
          <ElEmpty description="暂无监控目标">
            <ElButton v-if="hasAuth('monitoring.target:create')" @click="add">新增目标</ElButton>
          </ElEmpty>
        </template>
      </ElTable>
      <ElPagination
        v-model:current-page="page"
        class="mt-16px justify-end"
        :page-size="20"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="load"
      />
    </ElCard>
    <ElDrawer
      v-model="editor"
      :title="editingId ? '编辑监控目标' : '新增监控目标'"
      size="640px"
      :close-on-click-modal="false"
    >
      <ElForm
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="132px"
        label-suffix="："
        require-asterisk-position="left"
      >
        <ElFormItem label="目标名称" prop="name"><ElInput v-model="form.name" maxlength="128" /></ElFormItem>
        <ElFormItem>
          <template #label>
            <FormLabelHelp label="关联主机" :help="['可选；关联 CMDB 主机后，可在定时同步时跟随资产 IP。']" />
          </template>
          <ElSelect
            v-model="form.host"
            filterable
            remote
            clearable
            :remote-method="searchHosts"
            :loading="hostLoading"
            class="w-full"
            placeholder="可选，输入主机名或 IP 搜索"
            @change="selectHost"
          >
            <ElOption v-if="form.host && missingSelectedHost" :value="form.host" :label="`已关联主机 #${form.host}`" />
            <ElOption
              v-for="host in hostOptions"
              :key="host.id"
              :value="host.id"
              :label="`${host.hostname} · ${host.internalIp || host.externalIp || '无 IP'}`"
            />
          </ElSelect>
        </ElFormItem>
        <ElFormItem prop="connection">
          <template #label>
            <FormLabelHelp label="Consul 连接" :help="['服务注册到该 Agent；停用的连接不可选择。']" />
          </template>
          <ElSelect v-model="form.connection" class="w-full" placeholder="请选择已配置连接">
            <ElOption
              v-for="item in connections"
              :key="item.id"
              :value="item.id"
              :label="item.name"
              :disabled="!item.is_active"
            />
          </ElSelect>
        </ElFormItem>
        <ElFormItem>
          <template #label>
            <FormLabelHelp
              label="目标类型"
              :help="[
                'host / mysql / redis：按固定 Exporter 地址注册；',
                'blackbox：填写 Blackbox Exporter 地址，并单独配置探测地址与探测模块。'
              ]"
            />
          </template>
          <ElRadioGroup v-model="form.kind" @change="changeKind">
            <ElRadio v-for="kind in kinds" :key="kind.value" :value="kind.value">{{ kind.label }}</ElRadio>
          </ElRadioGroup>
        </ElFormItem>
        <ElFormItem label="Exporter 地址" prop="address">
          <div class="w-full">
            <ElInput v-model="form.address" placeholder="IP 或主机名，不包含协议和路径" maxlength="255" />
            <p class="mt-6px text-12px text-[var(--el-text-color-secondary)]">
              {{
                form.kind === 'blackbox'
                  ? '填写 Blackbox Exporter 地址，探测 URL 单独填写。'
                  : '填写已部署的 Exporter 地址；保存目标不会安装 Exporter。'
              }}
            </p>
          </div>
        </ElFormItem>
        <ElFormItem>
          <template #label>
            <FormLabelHelp
              label="Exporter 端口"
              :help="['Exporter 监听端口；node_exporter 常用 9100，blackbox_exporter 常用 9115。']"
            />
          </template>
          <ElInputNumber v-model="form.port" :min="1" :max="65535" controls-position="right" />
        </ElFormItem>
        <template v-if="form.kind === 'blackbox'">
          <ElFormItem label="探测地址" prop="probe_target">
            <ElInput v-model="form.probe_target" placeholder="https://example.com/health" maxlength="2048" />
          </ElFormItem>
          <ElFormItem label="探测模块">
            <ElInput v-model="form.probe_module" placeholder="http_2xx" maxlength="128" />
          </ElFormItem>
        </template>
        <ElFormItem label="健康检查">
          <div>
            <ElRadioGroup v-model="form.check_enabled">
              <ElRadio :value="false">不配置</ElRadio>
              <ElRadio :value="true">TCP 检查</ElRadio>
            </ElRadioGroup>
            <p class="mt-6px text-12px text-[var(--el-text-color-secondary)]">
              TCP 检查仅反映 Exporter 端口连通性，不代表业务或探测 URL 健康。
            </p>
          </div>
        </ElFormItem>
        <ElFormItem>
          <template #label>
            <FormLabelHelp
              label="标签"
              :help="['写入 Consul 服务 Tags，可用于 Prometheus relabel 或 Catalog 过滤。']"
            />
          </template>
          <ElSelect
            v-model="form.tags"
            multiple
            filterable
            allow-create
            default-first-option
            class="w-full"
            placeholder="输入标签后回车"
          />
        </ElFormItem>
        <ElFormItem :error="metaError">
          <template #label>
            <FormLabelHelp
              label="Meta"
              :help="[
                'JSON 对象，写入 Consul 服务 Meta；平台托管标记由系统维护，请勿覆盖。',
                '如 {&quot;environment&quot;: &quot;production&quot;}'
              ]"
            />
          </template>
          <ElInput v-model="metaText" type="textarea" :rows="4" placeholder='{"environment": "production"}' />
        </ElFormItem>
        <ElFormItem label="定时同步">
          <div>
            <ElInputNumber v-model="form.sync_interval_minutes" :min="0" :max="10080" controls-position="right" />
            <span class="ml-8px">分钟</span>
            <p class="mt-6px text-12px text-[var(--el-text-color-secondary)]">
              0 为关闭；启用后由当前账号授权执行，权限失效会暂停任务。
            </p>
          </div>
        </ElFormItem>
        <ElFormItem label="跟随资产 IP">
          <div>
            <ElRadioGroup v-model="form.follow_host_address">
              <ElRadio :value="false">保持当前地址</ElRadio>
              <ElRadio :value="true" :disabled="!form.host">跟随关联主机</ElRadio>
            </ElRadioGroup>
            <p class="mt-6px text-12px text-[var(--el-text-color-secondary)]">
              仅在定时同步时更新 Exporter 地址，其他配置保持不变。
            </p>
          </div>
        </ElFormItem>
        <ElFormItem v-if="form.follow_host_address">
          <template #label>
            <FormLabelHelp label="地址来源" :help="['跟随资产 IP 时，选择使用主机的内网或外网地址。']" />
          </template>
          <ElRadioGroup v-model="form.address_source">
            <ElRadio value="internal">内网 IP</ElRadio>
            <ElRadio value="external">外网 IP</ElRadio>
          </ElRadioGroup>
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton :disabled="saving" @click="closeEditor">取消</ElButton>
        <ElButton type="primary" :loading="saving" @click="save">保存</ElButton>
      </template>
    </ElDrawer>
    <ElDialog v-model="previewVisible" :title="previewTitle" width="760px">
      <p class="mb-12px text-12px text-[var(--el-text-color-secondary)]">
        {{ previewNote }}
      </p>
      <ElInput :model-value="previewContent" type="textarea" :rows="22" readonly />
    </ElDialog>
    <ElDrawer v-model="recordsVisible" :title="`同步记录 · ${selectedTarget?.name || ''}`" size="80%">
      <div class="mb-16px flex justify-end">
        <ElButton :loading="recordsLoading" @click="loadRecords">刷新</ElButton>
      </div>
      <ElTable v-loading="recordsLoading" :data="records" border>
        <ElTableColumn prop="id" label="ID" width="80" align="center" />
        <ElTableColumn label="触发来源" width="110" align="center">
          <template #default="{ row }">{{ triggerLabel(row.trigger) }}</template>
        </ElTableColumn>
        <ElTableColumn label="操作" width="100" align="center">
          <template #default="{ row }">{{ row.operation === 'register' ? '注册 / 更新' : '注销' }}</template>
        </ElTableColumn>
        <ElTableColumn label="状态" width="100" align="center">
          <template #default="{ row }">
            <ElTag :type="stateType(row.status)">{{ stateLabel(row.status) }}</ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn prop="created_at" label="提交时间" min-width="170" align="center" show-overflow-tooltip />
        <ElTableColumn prop="error" label="错误信息" min-width="260" align="center" show-overflow-tooltip>
          <template #default="{ row }">{{ row.error || '—' }}</template>
        </ElTableColumn>
      </ElTable>
      <ElPagination
        v-model:current-page="recordsPage"
        class="mt-16px justify-end"
        :page-size="20"
        :total="recordsTotal"
        layout="total, prev, pager, next"
        @current-change="loadRecords"
      />
    </ElDrawer>
    <HostImportDrawer v-model:visible="importVisible" :connections="connections" @completed="load" />
  </div>
</template>
