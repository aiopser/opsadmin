<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, shallowRef } from 'vue';
import type { FormInstance } from 'element-plus';
import { fetchGetHostGroupList } from '@/service/api/cmdb';
import { getConsulConnections } from '@/service/api/monitoring';
import type { ConsulConnection } from '@/service/api/monitoring';
import type {
  EnrollmentPolicy,
  EnrollmentPolicyInput,
  EnrollmentPreview,
  EnrollmentRun
} from '@/service/api/enrollment';
import {
  confirmEnrollmentPolicy,
  deleteEnrollmentPolicy,
  getEnrollmentPolicies,
  getEnrollmentRuns,
  pauseEnrollmentPolicy,
  previewEnrollmentPolicy,
  saveEnrollmentPolicy
} from '@/service/api/enrollment';
import { useAuth } from '@/hooks/business/auth';

defineOptions({ name: 'MonitoringPolicies' });

const { hasAuth } = useAuth();
const keyword = ref('');
const query = ref('');
const page = ref(1);
const total = ref(0);
const rows = shallowRef<EnrollmentPolicy[]>([]);
const connections = shallowRef<ConsulConnection[]>([]);
const groups = shallowRef<Api.Cmdb.HostGroupRecord[]>([]);
const loading = ref(false);
const editor = ref(false);
const saving = ref(false);
const editingId = ref<number>();
const formRef = shallowRef<FormInstance>();
const form = ref<EnrollmentPolicyInput>(emptyForm());
const ruleJson = ref('{"os_family":"linux"}');
const ruleError = ref('');
const rules = {
  name: [{ required: true, message: '请输入策略名称', trigger: 'blur' }],
  connection: [{ required: true, message: '请选择 Consul 连接', trigger: 'change' }]
};
const preview = shallowRef<EnrollmentPreview>();
const selected = shallowRef<EnrollmentPolicy>();
const previewVisible = ref(false);
const previewLoading = ref(false);
const confirming = ref(false);
const previewPage = ref(1);
const previewRows = computed(
  () => preview.value?.rows.slice((previewPage.value - 1) * 20, previewPage.value * 20) || []
);
const historyVisible = ref(false);
const history = shallowRef<EnrollmentRun[]>([]);
const historyPage = ref(1);
const historyTotal = ref(0);
let requestSequence = 0;
let historySequence = 0;
let listSequence = 0;

function emptyForm(): EnrollmentPolicyInput {
  return {
    name: '',
    connection: undefined,
    scope: 'group',
    group: null,
    include_descendants: true,
    match_rule: {},
    address_source: 'internal',
    port: 9100,
    interval_minutes: 5,
    target_sync_interval_minutes: 5,
    follow_host_address: true
  };
}
async function load() {
  listSequence += 1;
  const sequence = listSequence;
  loading.value = true;
  try {
    const { data, error } = await getEnrollmentPolicies(page.value, query.value);
    if (sequence === listSequence && !error && data) {
      rows.value = data.list;
      total.value = data.total;
    }
  } finally {
    if (sequence === listSequence) loading.value = false;
  }
}
async function search() {
  query.value = keyword.value.trim();
  page.value = 1;
  await load();
}
async function reset() {
  keyword.value = '';
  await search();
}
async function choices() {
  const results = await Promise.all([getConsulConnections(), fetchGetHostGroupList({ current: 1, size: 1000 })]);
  if (!results[0].error && results[0].data) connections.value = results[0].data;
  if (!results[1].error && results[1].data) groups.value = results[1].data.records;
}
async function add() {
  await choices();
  editingId.value = undefined;
  form.value = emptyForm();
  ruleJson.value = '{"os_family":"linux"}';
  ruleError.value = '';
  editor.value = true;
}
async function edit(row: EnrollmentPolicy) {
  await choices();
  editingId.value = row.id;
  form.value = {
    name: row.name,
    connection: row.connection,
    scope: row.scope,
    group: row.group,
    include_descendants: row.include_descendants,
    match_rule: row.match_rule,
    address_source: row.address_source,
    port: row.port,
    interval_minutes: row.interval_minutes,
    target_sync_interval_minutes: row.target_sync_interval_minutes,
    follow_host_address: row.follow_host_address
  };
  ruleJson.value = JSON.stringify(row.match_rule, null, 2);
  ruleError.value = '';
  editor.value = true;
}
function parseRules(): EnrollmentPolicyInput['match_rule'] | undefined {
  try {
    const data: unknown = JSON.parse(ruleJson.value);
    if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('invalid');
    const entries = Object.entries(data);
    if (
      entries.some(
        ([, value]) =>
          !(
            typeof value === 'string' ||
            typeof value === 'number' ||
            (Array.isArray(value) && value.every(item => typeof item === 'string' || typeof item === 'number'))
          )
      )
    )
      throw new Error('invalid');
    return Object.fromEntries(entries) as EnrollmentPolicyInput['match_rule'];
  } catch {
    ruleError.value = '请填写有效的规则 JSON 对象';
    return undefined;
  }
}
async function save() {
  ruleError.value = '';
  if (!(await formRef.value?.validate().catch(() => false))) return;
  if (form.value.scope === 'group' && !form.value.group) {
    window.$message?.warning('请选择主机分组');
    return;
  }
  const matchRule = form.value.scope === 'rule' ? parseRules() : {};
  if (!matchRule) return;
  saving.value = true;
  try {
    const { error } = await saveEnrollmentPolicy(editingId.value, { ...form.value, match_rule: matchRule });
    if (!error) {
      editor.value = false;
      window.$notification?.success('已保存为暂停状态，请预览后启用');
      await load();
    }
  } finally {
    saving.value = false;
  }
}
async function showPreview(row: EnrollmentPolicy) {
  requestSequence += 1;
  const sequence = requestSequence;
  selected.value = row;
  preview.value = undefined;
  previewVisible.value = true;
  previewLoading.value = true;
  previewPage.value = 1;
  try {
    const { data, error } = await previewEnrollmentPolicy(row.id);
    if (sequence === requestSequence && previewVisible.value && !error && data) preview.value = data;
  } finally {
    if (sequence === requestSequence) previewLoading.value = false;
  }
}
async function confirm(operation: 'run' | 'enable') {
  if (!selected.value || !preview.value || confirming.value) return;
  confirming.value = true;
  try {
    const { error } = await confirmEnrollmentPolicy(selected.value.id, {
      preview_token: preview.value.preview_token,
      operation
    });
    if (!error) {
      previewVisible.value = false;
      window.$notification?.success('策略任务已提交，请查看执行记录及目标同步状态');
      await load();
    } else preview.value = undefined;
  } finally {
    confirming.value = false;
  }
}
async function runOnce() {
  await confirm('run');
}
async function enable() {
  await confirm('enable');
}
async function pause(row: EnrollmentPolicy) {
  const { error } = await pauseEnrollmentPolicy(row.id);
  if (!error) await load();
}
async function remove(row: EnrollmentPolicy) {
  const { error } = await deleteEnrollmentPolicy(row.id);
  if (!error) await load();
}
async function loadHistory() {
  if (!selected.value) return;
  historySequence += 1;
  const sequence = historySequence;
  const { data, error } = await getEnrollmentRuns(selected.value.id, historyPage.value);
  if (sequence === historySequence && historyVisible.value && !error && data) {
    history.value = data.list;
    historyTotal.value = data.total;
  }
}
async function showHistory(row: EnrollmentPolicy) {
  selected.value = row;
  historyPage.value = 1;
  history.value = [];
  historyVisible.value = true;
  await loadHistory();
}
function statusLabel(value: string) {
  return (
    ({ queued: '排队中', running: '执行中', succeeded: '已处理', failed: '失败' } as Record<string, string>)[value] ||
    value
  );
}
function closeEditor() {
  editor.value = false;
}

onMounted(load);
onUnmounted(() => {
  requestSequence += 1;
  historySequence += 1;
  listSequence += 1;
});
</script>

<template>
  <div class="flex-col-stretch gap-16px">
    <SearchPanel @search="search" @reset="reset">
      <ElForm label-width="80px" @submit.prevent="search">
        <ElFormItem label="关键词">
          <ElInput v-model="keyword" placeholder="策略名称" clearable @keyup.enter="search" />
        </ElFormItem>
      </ElForm>
    </SearchPanel>
    <ElCard class="card-wrapper">
      <template #header>
        <div class="flex items-center justify-between gap-12px">
          <span>动态纳管策略</span>
          <div class="flex gap-8px">
            <ElButton v-if="hasAuth('monitoring.enrollment:create')" type="primary" @click="add">新增策略</ElButton>
            <ElButton :loading="loading" @click="load">刷新</ElButton>
          </div>
        </div>
      </template>
      <ElTable v-loading="loading" :data="rows" border>
        <ElTableColumn prop="name" label="名称" min-width="140" align="center" show-overflow-tooltip />
        <ElTableColumn
          prop="connection_name"
          label="Consul 连接"
          min-width="140"
          align="center"
          show-overflow-tooltip
        />
        <ElTableColumn label="范围" min-width="140" align="center" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.scope === 'group' ? row.group_name || '分组失效' : '匹配规则' }}
          </template>
        </ElTableColumn>
        <ElTableColumn label="状态" width="100" align="center">
          <template #default="{ row }">
            <ElTag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '启用' : '暂停' }}</ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn label="发现间隔" width="120" align="center">
          <template #default="{ row }">{{ row.interval_minutes }} 分钟</template>
        </ElTableColumn>
        <ElTableColumn prop="actor_name" label="执行账号" min-width="120" align="center" />
        <ElTableColumn label="操作" width="320" align="center" fixed="right">
          <template #default="{ row }">
            <ElButton v-if="hasAuth('monitoring.enrollment:update')" link type="primary" @click="edit(row)">
              编辑
            </ElButton>
            <ElButton v-if="hasAuth('monitoring.enrollment:run')" link type="primary" @click="showPreview(row)">
              预览
            </ElButton>
            <ElButton link type="primary" @click="showHistory(row)">记录</ElButton>
            <ElButton
              v-if="hasAuth('monitoring.enrollment:run') && row.is_active"
              link
              type="primary"
              @click="pause(row)"
            >
              暂停
            </ElButton>
            <ElPopconfirm
              v-if="hasAuth('monitoring.enrollment:delete')"
              title="删除策略会保留已有目标和执行历史，确认删除？"
              @confirm="remove(row)"
            >
              <template #reference><ElButton link type="danger" :disabled="row.is_active">删除</ElButton></template>
            </ElPopconfirm>
          </template>
        </ElTableColumn>
      </ElTable>
      <ElPagination
        v-model:current-page="page"
        class="mt-16px justify-end"
        :total="total"
        :page-size="20"
        layout="total, prev, pager, next"
        @current-change="load"
      />
    </ElCard>
    <ElDrawer
      v-model="editor"
      :title="editingId ? '编辑纳管策略' : '新增纳管策略'"
      size="660px"
      :close-on-click-modal="false"
    >
      <ElForm
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="168px"
        label-suffix="："
        require-asterisk-position="left"
      >
        <ElFormItem label="策略名称" prop="name"><ElInput v-model="form.name" maxlength="128" /></ElFormItem>
        <ElFormItem prop="connection">
          <template #label>
            <FormLabelHelp
              label="Consul 连接"
              :help="['从该 Agent 的 Catalog 发现服务，纳管后的目标也注册到该 Agent。']"
            />
          </template>
          <ElSelect v-model="form.connection" class="w-full">
            <ElOption
              v-for="item in connections"
              :key="item.id"
              :label="item.name"
              :value="item.id"
              :disabled="!item.is_active"
            />
          </ElSelect>
        </ElFormItem>
        <ElFormItem>
          <template #label>
            <FormLabelHelp
              label="纳管范围"
              :help="['主机分组：按 CMDB 分组批量纳管；', '匹配规则：按主机字段动态匹配，适合按环境、应用等维度纳管。']"
            />
          </template>
          <ElRadioGroup v-model="form.scope">
            <ElRadio value="group">主机分组</ElRadio>
            <ElRadio value="rule">匹配规则</ElRadio>
          </ElRadioGroup>
        </ElFormItem>
        <template v-if="form.scope === 'group'">
          <ElFormItem label="主机分组" required>
            <ElSelect v-model="form.group" filterable class="w-full">
              <ElOption
                v-for="group in groups"
                :key="group.id"
                :value="group.id"
                :label="`${group.name} #${group.id}`"
                :disabled="!group.is_active"
              />
            </ElSelect>
          </ElFormItem>
          <ElFormItem>
            <template #label>
              <FormLabelHelp
                label="包含子分组"
                :help="['递归包含子分组主机；之后加入子分组的主机在下次发现时纳入。']"
              />
            </template>
            <ElSwitch v-model="form.include_descendants" />
          </ElFormItem>
        </template>
        <ElFormItem v-else label="匹配规则" required :error="ruleError">
          <div class="w-full">
            <ElInput v-model="ruleJson" type="textarea" :rows="5" />
            <p class="mt-6px text-12px text-[var(--el-text-color-secondary)]">
              支持 os_family、environment、app_code、asset_source；多个字段同时匹配，数组值匹配任一项。
            </p>
          </div>
        </ElFormItem>
        <ElFormItem>
          <template #label>
            <FormLabelHelp
              label="发现间隔"
              :help="['按该间隔读取 Catalog 并匹配主机；新目标分批创建，每批最多 200 个。']"
            />
          </template>
          <ElInputNumber v-model="form.interval_minutes" :min="1" :max="10080" controls-position="right" />
          <span class="ml-8px">分钟</span>
        </ElFormItem>
        <ElFormItem>
          <template #label>
            <FormLabelHelp label="新目标地址" :help="['新发现目标注册服务时使用的地址来源：CMDB 内网或外网 IP。']" />
          </template>
          <ElRadioGroup v-model="form.address_source">
            <ElRadio value="internal">内网 IP</ElRadio>
            <ElRadio value="external">外网 IP</ElRadio>
          </ElRadioGroup>
        </ElFormItem>
        <ElFormItem>
          <template #label>
            <FormLabelHelp
              label="新目标 Exporter 端口"
              :help="['新发现目标统一使用该 Exporter 端口；不同端口请拆分为多个策略。']"
            />
          </template>
          <ElInputNumber v-model="form.port" :min="1" :max="65535" controls-position="right" />
        </ElFormItem>
        <ElFormItem>
          <template #label>
            <FormLabelHelp label="新目标同步间隔" :help="['只作用于策略新建的目标；0 为关闭定时同步。']" />
          </template>
          <ElInputNumber v-model="form.target_sync_interval_minutes" :min="0" :max="10080" controls-position="right" />
          <span class="ml-8px">分钟，0 为关闭</span>
        </ElFormItem>
        <ElFormItem>
          <template #label>
            <FormLabelHelp label="新目标跟随 IP" :help="['开启后，新建目标在定时同步时跟随关联主机的资产 IP。']" />
          </template>
          <ElSwitch v-model="form.follow_host_address" />
        </ElFormItem>
      </ElForm>
      <p class="text-12px text-[var(--el-text-color-secondary)]">
        只新增目标，不覆盖已有配置；退出范围的主机不自动注销。修改策略后会暂停，需重新预览并启用。
      </p>
      <template #footer>
        <ElButton :disabled="saving" @click="closeEditor">取消</ElButton>
        <ElButton type="primary" :loading="saving" @click="save">保存</ElButton>
      </template>
    </ElDrawer>
    <ElDrawer
      v-model="previewVisible"
      :title="`范围预览 · ${selected?.name || ''}`"
      size="75%"
      :close-on-click-modal="false"
      :show-close="!confirming"
    >
      <div v-loading="previewLoading" class="flex-col gap-16px">
        <p>
          匹配 {{ preview?.matched_count || 0 }} 台，已有 {{ preview?.existing_count || 0 }} 台，本次新增
          {{ preview?.create_count || 0 }} 台，无效 {{ preview?.invalid_count || 0 }} 台，后续待处理
          {{ preview?.remaining_count || 0 }} 台。
        </p>
        <p class="text-12px text-[var(--el-text-color-secondary)]">
          每批最多新增 200
          个目标；执行记录“已处理”表示配置处理完毕，实际注册结果请查看目标同步记录。暂停策略不会注销已有目标或关闭其定时同步。
        </p>
        <ElTable :data="previewRows" border>
          <ElTableColumn prop="name" label="主机" min-width="160" align="center" show-overflow-tooltip />
          <ElTableColumn prop="address" label="监控地址" min-width="160" align="center" />
        </ElTable>
        <ElPagination
          v-model:current-page="previewPage"
          class="justify-end"
          :total="preview?.rows.length || 0"
          :page-size="20"
          layout="total, prev, pager, next"
        />
      </div>
      <template #footer>
        <ElButton v-if="hasAuth('monitoring.enrollment:run')" :disabled="!preview || confirming" @click="runOnce">
          仅执行一次
        </ElButton>
        <ElButton
          v-if="hasAuth('monitoring.enrollment:run')"
          type="primary"
          :disabled="!preview"
          :loading="confirming"
          @click="enable"
        >
          启用并执行
        </ElButton>
      </template>
    </ElDrawer>
    <ElDrawer v-model="historyVisible" title="纳管执行记录" size="80%">
      <ElTable :data="history" border>
        <ElTableColumn prop="policy_name" label="策略" min-width="130" align="center" />
        <ElTableColumn label="状态" width="100" align="center">
          <template #default="{ row }">{{ statusLabel(row.status) }}</template>
        </ElTableColumn>
        <ElTableColumn label="已创建目标" width="120" align="center">
          <template #default="{ row }">{{ row.summary.created ?? '—' }}</template>
        </ElTableColumn>
        <ElTableColumn prop="error" label="错误信息" min-width="240" align="center" show-overflow-tooltip />
        <ElTableColumn prop="created_at" label="时间" min-width="170" align="center" />
      </ElTable>
      <ElPagination
        v-model:current-page="historyPage"
        class="mt-16px justify-end"
        :total="historyTotal"
        :page-size="20"
        layout="total, prev, pager, next"
        @current-change="loadHistory"
      />
    </ElDrawer>
  </div>
</template>
