<script setup lang="ts">
import { onMounted, onUnmounted, reactive, ref, shallowRef } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import {
  confirmJumpServer,
  deleteJumpServer,
  fetchJumpServerRecords,
  fetchJumpServers,
  previewJumpServer,
  saveJumpServer,
  testJumpServer
} from '@/service/api/integrations';
import type { JumpServerConnection, JumpServerInput, JumpServerRun } from '@/service/api/integrations';
import { useAuth } from '@/hooks/business/auth';
import HostSelectModal from '@/components/business/host-select-modal/index.vue';

defineOptions({ name: 'MonitoringIntegrations' });
const { hasAuth } = useAuth();

const rows = shallowRef<JumpServerConnection[]>([]);
const records = shallowRef<JumpServerRun[]>([]);
const selectedHosts = shallowRef<Api.Cmdb.HostRecord[]>([]);
const selected = shallowRef<JumpServerConnection>();
const selectedRecord = shallowRef<JumpServerConnection>();
const confirming = ref(false);
let recordSequence = 0;
let previewSequence = 0;
const preview = shallowRef<JumpServerRun>();
const search = ref('');
const busy = ref(false);
const editorVisible = ref(false);
const hostVisible = ref(false);
const syncVisible = ref(false);
const recordVisible = ref(false);
const editId = ref<number>();
const defaults = (): JumpServerInput => ({
  name: '',
  endpoint: '',
  key_id: '',
  secret: '',
  org_id: '',
  node_id: '',
  linux_platform: 1,
  windows_platform: 5,
  is_active: true,
  verify_tls: true,
  sync_interval_minutes: 0
});
const form = reactive<JumpServerInput>(defaults());

async function load() {
  busy.value = true;
  try {
    const { data, error } = await fetchJumpServers(search.value);
    if (!error && data) rows.value = data;
  } finally {
    busy.value = false;
  }
}
function edit(row?: JumpServerConnection) {
  editId.value = row?.id;
  Object.assign(form, defaults(), row, { secret: '' });
  editorVisible.value = true;
}
function create() {
  edit();
}
async function save() {
  if (!form.name || !form.endpoint || !form.key_id || !form.node_id || (!editId.value && !form.secret)) {
    ElMessage.warning('请填写名称、地址、Key ID、节点 UUID 和首次 Secret');
    return;
  }
  const { error } = await saveJumpServer(form, editId.value);
  if (!error) {
    editorVisible.value = false;
    await load();
  }
}
async function remove(row: JumpServerConnection) {
  await ElMessageBox.confirm(`删除连接「${row.name}」？存在纳管映射或记录时会被保护。`, '删除连接');
  const { error } = await deleteJumpServer(row.id);
  if (!error) await load();
}
async function test(row: JumpServerConnection) {
  const { error } = await testJumpServer(row.id);
  if (!error) window.$notification?.success('节点访问正常');
}
function selectHosts(row: JumpServerConnection) {
  previewSequence += 1;
  selected.value = row;
  selectedHosts.value = [];
  preview.value = undefined;
  hostVisible.value = true;
}
async function hostsConfirmed(hosts: Api.Cmdb.HostRecord[]) {
  if (!selected.value) return;
  const connectionId = selected.value.id;
  previewSequence += 1;
  const sequence = previewSequence;
  selectedHosts.value = hosts;
  const { data, error } = await previewJumpServer(
    connectionId,
    hosts.map(host => host.id)
  );
  if (sequence !== previewSequence || selected.value?.id !== connectionId) return;
  if (!error && data) {
    preview.value = data;
    syncVisible.value = true;
  }
}
async function confirm() {
  if (!selected.value || !preview.value || confirming.value) return;
  const connection = selected.value;
  confirming.value = true;
  try {
    const { error } = await confirmJumpServer(connection.id, preview.value.id);
    if (!error) {
      syncVisible.value = false;
      window.$notification?.success('同步任务已入队');
      await showRecords(connection);
    }
  } finally {
    confirming.value = false;
  }
}
async function showRecords(row: JumpServerConnection) {
  selectedRecord.value = row;
  recordSequence += 1;
  const sequence = recordSequence;
  records.value = [];
  recordVisible.value = true;
  const { data, error } = await fetchJumpServerRecords(row.id);
  if (sequence !== recordSequence) return;
  if (!error && data) {
    records.value = data;
    recordVisible.value = true;
  }
}
async function refreshRecords() {
  if (selectedRecord.value) await showRecords(selectedRecord.value);
}
async function resetSearch() {
  search.value = '';
  await load();
}
onMounted(load);
onUnmounted(() => {
  recordSequence += 1;
  previewSequence += 1;
});
</script>

<template>
  <div class="flex-col-stretch gap-16px">
    <SearchPanel @search="load" @reset="resetSearch">
      <ElForm label-width="80px" @submit.prevent="load">
        <ElFormItem label="关键词">
          <ElInput v-model="search" placeholder="连接名称" clearable @keyup.enter="load" />
        </ElFormItem>
      </ElForm>
    </SearchPanel>
    <ElCard class="card-wrapper">
      <template #header>
        <div class="flex items-center justify-between gap-12px">
          <span>JumpServer 集成</span>
          <div class="flex gap-8px">
            <ElButton v-if="hasAuth('integrations.jumpserver:manage')" type="primary" @click="create">
              新建连接
            </ElButton>
            <ElButton @click="load">刷新</ElButton>
          </div>
        </div>
      </template>
      <p class="text-sm">
        将明确选择的 CMDB 主机同步到 JumpServer v3/v4。仅更新本地映射拥有的资产；不按同名接管，不删除远端资产。
      </p>
      <ElSkeleton v-if="busy" :rows="5" animated />
      <ElTable v-else :data="rows" border class="w-full">
        <ElTableColumn align="center" prop="name" label="连接" min-width="150" show-overflow-tooltip />
        <ElTableColumn align="center" prop="endpoint" label="地址" min-width="220" show-overflow-tooltip />
        <ElTableColumn align="center" label="状态" width="100">
          <template #default="scope">
            <ElTag>{{ scope.row.is_active ? '启用' : '停用' }}</ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn
          prop="sync_interval_minutes"
          label="周期 / 分钟"
          width="120"
          align="center"
          class-name="font-mono"
        />
        <ElTableColumn align="center" label="操作" width="360">
          <template #default="scope">
            <ElButton v-if="hasAuth('integrations.jumpserver:manage')" link @click="edit(scope.row)">编辑</ElButton>
            <ElButton
              v-if="hasAuth('integrations.jumpserver:sync')"
              link
              :disabled="!scope.row.is_active"
              @click="test(scope.row)"
            >
              测试
            </ElButton>
            <ElButton
              v-if="hasAuth('integrations.jumpserver:sync')"
              link
              :disabled="!scope.row.is_active"
              @click="selectHosts(scope.row)"
            >
              选择主机同步
            </ElButton>
            <ElButton link @click="showRecords(scope.row)">记录</ElButton>
            <ElButton v-if="hasAuth('integrations.jumpserver:manage')" link @click="remove(scope.row)">删除</ElButton>
          </template>
        </ElTableColumn>
      </ElTable>
    </ElCard>
    <ElDrawer v-model="editorVisible" :title="editId ? '编辑 JumpServer 连接' : '新增 JumpServer 连接'" size="560px">
      <ElForm label-width="150px" label-suffix="：" require-asterisk-position="left">
        <ElFormItem label="名称" required><ElInput v-model="form.name" maxlength="128" /></ElFormItem>
        <ElFormItem required>
          <template #label>
            <FormLabelHelp
              label="服务地址"
              :help="['JumpServer API 根地址，如 https://jumpserver.example.com；需平台可访问。']"
            />
          </template>
          <ElInput v-model="form.endpoint" placeholder="https://jumpserver.example.com" />
        </ElFormItem>
        <ElFormItem required>
          <template #label>
            <FormLabelHelp label="Key ID" :help="['JumpServer 开放 API 的 Access Key ID。']" />
          </template>
          <ElInput v-model="form.key_id" maxlength="128" autocomplete="off" />
        </ElFormItem>
        <ElFormItem :required="!editId">
          <template #label>
            <FormLabelHelp label="Secret" :help="['加密保存且不回显；编辑时留空表示保留已有凭据。']" />
          </template>
          <ElInput
            v-model="form.secret"
            type="password"
            show-password
            autocomplete="new-password"
            :placeholder="editId ? '留空保留已有凭据' : '请输入 API Key Secret'"
          />
        </ElFormItem>
        <ElFormItem>
          <template #label>
            <FormLabelHelp label="组织 UUID" :help="['可选；留空使用默认组织。']" />
          </template>
          <ElInput v-model="form.org_id" />
        </ElFormItem>
        <ElFormItem required>
          <template #label>
            <FormLabelHelp
              label="目标节点 UUID"
              :help="['同步主机默认挂载的节点 UUID，可在 JumpServer 节点页获取。']"
            />
          </template>
          <ElInput v-model="form.node_id" />
        </ElFormItem>
        <ElFormItem>
          <template #label>
            <FormLabelHelp
              label="Linux 平台 ID"
              :help="['JumpServer 平台 ID，以目标实例为准；目前同步 SSH，WinRM 主机需先调整 CMDB 协议。']"
            />
          </template>
          <ElInputNumber v-model="form.linux_platform" :min="1" />
        </ElFormItem>
        <ElFormItem>
          <template #label>
            <FormLabelHelp
              label="Windows 平台 ID"
              :help="['JumpServer 平台 ID，以目标实例为准；目前同步 SSH，WinRM 主机需先调整 CMDB 协议。']"
            />
          </template>
          <ElInputNumber v-model="form.windows_platform" :min="1" />
        </ElFormItem>
        <ElFormItem>
          <template #label>
            <FormLabelHelp label="TLS 验证" :help="['内网自签证书可关闭；关闭后将跳过证书校验。']" />
          </template>
          <ElSwitch v-model="form.verify_tls" />
        </ElFormItem>
        <ElFormItem>
          <template #label>
            <FormLabelHelp label="启用" :help="['停用后该连接不参与周期同步，已同步资产不会自动删除。']" />
          </template>
          <ElSwitch v-model="form.is_active" />
        </ElFormItem>
        <ElFormItem>
          <template #label>
            <FormLabelHelp
              label="周期（分钟）"
              :help="['0 表示仅手工同步；', '周期同步使用最近一次确认的主机范围及确认账号，每次重新检查账号权限。']"
            />
          </template>
          <ElInputNumber v-model="form.sync_interval_minutes" :min="0" :max="10080" />
        </ElFormItem>
        <ElButton type="primary" @click="save">保存</ElButton>
      </ElForm>
    </ElDrawer>
    <HostSelectModal v-model:visible="hostVisible" :selected-hosts="selectedHosts" @confirm="hostsConfirmed" />
    <ElDrawer v-model="syncVisible" title="确认同步预览（10 分钟有效）" size="720px">
      <p>以下为即将发送的资产快照。首次同步分配独立 UUID；后续只更新同一 UUID 且所有权标记一致的资产。</p>
      <ElTable :data="preview?.snapshot ?? []" border>
        <ElTableColumn prop="host_id" label="CMDB ID" width="100" align="center" />
        <ElTableColumn align="center" prop="payload.name" label="主机名" min-width="150" />
        <ElTableColumn align="center" prop="payload.address" label="地址" min-width="140" />
        <ElTableColumn prop="payload.platform" label="平台 ID" width="100" align="center" />
      </ElTable>
      <ElButton type="primary" class="mt-4" :loading="confirming" @click="confirm">确认并执行同步</ElButton>
    </ElDrawer>
    <ElDrawer v-model="recordVisible" title="最近 100 次同步记录" size="800px">
      <ElButton class="mb-4" @click="refreshRecords">刷新状态</ElButton>
      <ElTable :data="records" border>
        <ElTableColumn prop="id" label="记录" width="80" align="center" />
        <ElTableColumn align="center" prop="status" label="状态" width="110" />
        <ElTableColumn align="center" prop="created_at" label="时间" min-width="180" />
        <ElTableColumn align="center" prop="error" label="错误详情" min-width="220" show-overflow-tooltip />
      </ElTable>
    </ElDrawer>
  </div>
</template>
