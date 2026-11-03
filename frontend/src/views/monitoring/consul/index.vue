<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, shallowRef } from 'vue';
import type { FormInstance } from 'element-plus';
import type { ConsulConnection, ConsulConnectionInput, ConsulService } from '@/service/api/monitoring';
import {
  deleteConsulConnection,
  getConsulConnections,
  getConsulServices,
  saveConsulConnection,
  testConsulConnection
} from '@/service/api/monitoring';
import { useAuth } from '@/hooks/business/auth';
import CatalogDrawer from './modules/catalog-drawer.vue';
import KvDrawer from './modules/kv-drawer.vue';

defineOptions({ name: 'MonitoringConsul' });

const { hasAuth } = useAuth();
const catalogVisible = ref(false);
const catalogConnection = shallowRef<ConsulConnection>();
const kvVisible = ref(false);
const kvConnection = shallowRef<ConsulConnection>();
let serviceSequence = 0;

const keyword = ref('');
const query = ref('');
const rows = shallowRef<ConsulConnection[]>([]);
const loading = ref(false);
const visibleRows = computed(() =>
  rows.value.filter(row => `${row.name} ${row.endpoint}`.toLowerCase().includes(query.value.toLowerCase()))
);
const page = ref(1);
const pagedRows = computed(() => visibleRows.value.slice((page.value - 1) * 20, page.value * 20));
const editor = ref(false);
const editingId = ref<number>();
const saving = ref(false);
const formRef = shallowRef<FormInstance>();
const form = ref<ConsulConnectionInput>(emptyForm());
const tokenSaved = ref(false);
const rules = {
  name: [{ required: true, message: '请输入连接名称', trigger: 'blur' }],
  endpoint: [{ required: true, message: '请输入 Consul Agent 地址', trigger: 'blur' }]
};
const testingId = ref<number>();
const servicesVisible = ref(false);
const services = shallowRef<ConsulService[]>([]);
const servicesLoading = ref(false);
const serviceError = ref(false);
const selectedName = ref('');
const detail = ref('');
const detailVisible = ref(false);

function emptyForm(): ConsulConnectionInput {
  return {
    name: '',
    endpoint: '',
    datacenter: '',
    description: '',
    token: '',
    is_active: true
  };
}
async function load() {
  loading.value = true;
  try {
    const { data, error } = await getConsulConnections();
    if (!error && data) rows.value = data;
  } finally {
    loading.value = false;
  }
}
function search() {
  query.value = keyword.value.trim();
  page.value = 1;
}
function reset() {
  keyword.value = '';
  search();
}
function add() {
  editingId.value = undefined;
  tokenSaved.value = false;
  form.value = emptyForm();
  editor.value = true;
}
function edit(row: ConsulConnection) {
  editingId.value = row.id;
  tokenSaved.value = row.has_token;
  form.value = {
    name: row.name,
    endpoint: row.endpoint,
    datacenter: row.datacenter,
    description: row.description,
    token: '',
    is_active: row.is_active
  };
  editor.value = true;
}
async function save() {
  if (!(await formRef.value?.validate().catch(() => false))) return;
  saving.value = true;
  try {
    const { error } = await saveConsulConnection(editingId.value, form.value);
    if (!error) {
      editor.value = false;
      window.$notification?.success('保存成功');
      await load();
    }
  } finally {
    saving.value = false;
  }
}
async function remove(row: ConsulConnection) {
  const { error } = await deleteConsulConnection(row.id);
  if (!error) await load();
}
async function test(row: ConsulConnection) {
  testingId.value = row.id;
  try {
    const { data, error } = await testConsulConnection(row.id);
    if (!error && data)
      window.$notification?.success(`连接成功：${data.agent || 'Agent'} · ${data.datacenter || '默认 Datacenter'}`);
  } finally {
    testingId.value = undefined;
  }
}
async function viewServices(row: ConsulConnection) {
  serviceSequence += 1;
  const sequence = serviceSequence;
  selectedName.value = row.name;
  services.value = [];
  serviceError.value = false;
  servicesVisible.value = true;
  servicesLoading.value = true;
  try {
    const { data, error } = await getConsulServices(row.id);
    if (sequence !== serviceSequence) return;
    serviceError.value = Boolean(error);
    if (!error && data) services.value = data;
  } finally {
    if (sequence === serviceSequence) servicesLoading.value = false;
  }
}
function healthText(value: string) {
  return (
    (
      {
        passing: '正常',
        warning: '警告',
        critical: '异常',
        unknown: '无检查结果'
      } as Record<string, string>
    )[value] || '未知'
  );
}
function showDetail(row: ConsulService) {
  detail.value = JSON.stringify({ tags: row.tags, meta: row.meta }, null, 2);
  detailVisible.value = true;
}
function closeEditor() {
  editor.value = false;
  form.value.token = '';
}
function viewCatalog(row: ConsulConnection) {
  catalogConnection.value = row;
  catalogVisible.value = true;
}
function viewKv(row: ConsulConnection) {
  kvConnection.value = row;
  kvVisible.value = true;
}

onMounted(load);
onUnmounted(() => {
  serviceSequence += 1;
});
</script>

<template>
  <div class="flex-col-stretch gap-16px">
    <SearchPanel @search="search" @reset="reset">
      <ElForm label-width="80px" @submit.prevent="search">
        <ElFormItem label="关键词">
          <ElInput v-model="keyword" clearable placeholder="连接名称 / 地址" @keyup.enter="search" />
        </ElFormItem>
      </ElForm>
    </SearchPanel>
    <ElCard class="card-wrapper">
      <template #header>
        <div class="flex items-center justify-between gap-12px">
          <span>Consul 连接</span>
          <div class="flex gap-8px">
            <ElButton v-if="hasAuth('consul.connection:create')" type="primary" @click="add">新增连接</ElButton>
            <ElButton :loading="loading" @click="load">刷新</ElButton>
          </div>
        </div>
      </template>
      <ElTable v-loading="loading" :data="pagedRows" border>
        <ElTableColumn prop="name" label="名称" min-width="140" align="center" show-overflow-tooltip />
        <ElTableColumn prop="endpoint" label="Agent 地址" min-width="220" align="center" show-overflow-tooltip />
        <ElTableColumn prop="datacenter" label="Datacenter" min-width="120" align="center">
          <template #default="{ row }">{{ row.datacenter || '默认' }}</template>
        </ElTableColumn>
        <ElTableColumn label="Token" width="100" align="center">
          <template #default="{ row }">{{ row.has_token ? '已配置' : '未配置' }}</template>
        </ElTableColumn>
        <ElTableColumn label="状态" width="90" align="center">
          <template #default="{ row }">
            <ElTag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '启用' : '停用' }}</ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn label="操作" width="430" align="center" fixed="right">
          <template #default="{ row }">
            <ElButton
              v-if="hasAuth('consul.connection:test')"
              link
              type="primary"
              :disabled="!row.is_active || testingId !== undefined"
              :loading="testingId === row.id"
              @click="test(row)"
            >
              测试
            </ElButton>
            <ElButton link type="primary" :disabled="!row.is_active" @click="viewServices(row)">
              Agent Services
            </ElButton>
            <ElButton link type="primary" :disabled="!row.is_active" @click="viewCatalog(row)">Catalog</ElButton>
            <ElButton
              v-if="hasAuth('consul.connection:kv')"
              link
              type="primary"
              :disabled="!row.is_active"
              @click="viewKv(row)"
            >
              KV
            </ElButton>
            <ElButton v-if="hasAuth('consul.connection:update')" link type="primary" @click="edit(row)">编辑</ElButton>
            <ElPopconfirm
              v-if="hasAuth('consul.connection:delete')"
              title="确认删除该连接？有关联目标时无法删除。"
              @confirm="remove(row)"
            >
              <template #reference><ElButton link type="danger">删除</ElButton></template>
            </ElPopconfirm>
          </template>
        </ElTableColumn>
        <template #empty>
          <ElEmpty description="暂无 Consul 连接">
            <ElButton v-if="hasAuth('consul.connection:create')" @click="add">新增连接</ElButton>
          </ElEmpty>
        </template>
      </ElTable>
      <ElPagination
        v-model:current-page="page"
        class="mt-16px justify-end"
        :page-size="20"
        :total="visibleRows.length"
        layout="total, prev, pager, next"
      />
    </ElCard>
    <ElDrawer
      v-model="editor"
      :title="editingId ? '编辑 Consul 连接' : '新增 Consul 连接'"
      size="560px"
      :close-on-click-modal="false"
      @closed="closeEditor"
    >
      <ElForm
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="120px"
        label-suffix="："
        require-asterisk-position="left"
      >
        <ElFormItem prop="name">
          <template #label>
            <FormLabelHelp
              label="连接名称"
              :help="['用于区分环境或集群，建议使用「环境-用途」命名，如 prod-monitoring。']"
            />
          </template>
          <ElInput v-model="form.name" maxlength="128" placeholder="如 prod-monitoring" />
        </ElFormItem>
        <ElFormItem prop="endpoint">
          <template #label>
            <FormLabelHelp
              label="Agent 地址"
              :help="[
                'Agent 的 HTTP API 地址，如 http://10.0.0.10:8500。',
                '服务注册、注销与 KV、Catalog 操作均通过该地址，请保持稳定。'
              ]"
            />
          </template>
          <ElInput v-model="form.endpoint" placeholder="http://consul.example.com:8500" maxlength="512" />
        </ElFormItem>
        <ElFormItem>
          <template #label>
            <FormLabelHelp
              label="Datacenter"
              :help="['留空使用 Agent 的默认 Datacenter；跨 Datacenter 的 Catalog 浏览仍受 Agent 权限限制。']"
            />
          </template>
          <ElInput v-model="form.datacenter" placeholder="留空使用默认 Datacenter" maxlength="128" />
        </ElFormItem>
        <ElFormItem>
          <template #label>
            <FormLabelHelp
              label="ACL Token"
              :help="[
                'Token 加密保存且不回显，编辑时留空表示保留原 Token。',
                '建议授予 Agent 注册、Catalog 读取与 KV 读写的所需权限。'
              ]"
            />
          </template>
          <ElInput
            v-model="form.token"
            type="password"
            show-password
            autocomplete="new-password"
            :placeholder="tokenSaved ? '已配置，留空保留原 Token' : '未启用 ACL 时可留空'"
          />
        </ElFormItem>
        <ElFormItem>
          <template #label>
            <FormLabelHelp
              label="状态"
              :help="['停用后不再参与自动同步与纳管策略，已注册到 Agent 的实例不会自动注销。']"
            />
          </template>
          <ElRadioGroup v-model="form.is_active">
            <ElRadio :value="true">启用</ElRadio>
            <ElRadio :value="false">停用</ElRadio>
          </ElRadioGroup>
        </ElFormItem>
        <ElFormItem label="备注">
          <ElInput v-model="form.description" type="textarea" :rows="3" maxlength="512" />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton :disabled="saving" @click="closeEditor">取消</ElButton>
        <ElButton type="primary" :loading="saving" @click="save">保存</ElButton>
      </template>
    </ElDrawer>
    <ElDrawer v-model="servicesVisible" :title="`Agent Services · ${selectedName}`" size="80%">
      <p class="mb-16px text-12px text-[var(--el-text-color-secondary)]">
        Agent 注册的服务，每个 instance 一行；外部实例只读，平台纳管实例请在监控目标中操作。
      </p>
      <ElAlert
        v-if="serviceError"
        title="Services 读取失败，请检查连接后重新打开；未将失败视为空清单。"
        type="error"
        :closable="false"
        class="mb-16px"
      />
      <ElTable v-loading="servicesLoading" :data="services" border>
        <ElTableColumn prop="name" label="Services" min-width="130" align="center" show-overflow-tooltip />
        <ElTableColumn prop="id" label="Instance ID" min-width="180" align="center" show-overflow-tooltip />
        <ElTableColumn prop="address" label="地址" min-width="140" align="center" show-overflow-tooltip />
        <ElTableColumn prop="port" label="端口" width="80" align="center" />
        <ElTableColumn label="Health" width="130" align="center">
          <template #default="{ row }">{{ healthText(row.health) }}</template>
        </ElTableColumn>
        <ElTableColumn label="管理方式" width="110" align="center">
          <template #default="{ row }">{{ row.managed ? '平台纳管' : '外部实例' }}</template>
        </ElTableColumn>
        <ElTableColumn label="操作" width="100" align="center">
          <template #default="{ row }">
            <ElButton link type="primary" @click="showDetail(row)">标签与 Meta</ElButton>
          </template>
        </ElTableColumn>
      </ElTable>
    </ElDrawer>
    <CatalogDrawer v-model:visible="catalogVisible" :connection="catalogConnection" />
    <KvDrawer v-model:visible="kvVisible" :connection="kvConnection" />
    <ElDialog v-model="detailVisible" title="标签与 Meta" width="640px">
      <ElInput :model-value="detail" type="textarea" :rows="15" readonly />
    </ElDialog>
  </div>
</template>
