<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, shallowRef } from 'vue';
import { ElMessage } from 'element-plus';
import type { TableInstance } from 'element-plus';
import { fetchGetNotificationTemplateList } from '@/service/api/automation';
import {
  collectSecuritySubscription,
  getSecurityAdvisories,
  getSecurityCollections,
  getSecuritySubscriptions,
  saveSecuritySubscription
} from '@/service/api/security';
import type {
  SecurityAdvisory,
  SecurityAdvisorySortField,
  SecurityCollection,
  SecuritySubscription
} from '@/service/api/security';
import { useAuth } from '@/hooks/business/auth';

defineOptions({ name: 'MonitoringSecurity' });
const { hasAuth } = useAuth();
const subscriptions = shallowRef<SecuritySubscription[]>([]);
const advisories = shallowRef<SecurityAdvisory[]>([]);
const collections = shallowRef<SecurityCollection[]>([]);
const templates = shallowRef<Api.Automation.NotificationTemplateRecord[]>([]);
const loading = ref(false);
const saving = ref(false);
const dialog = ref(false);
const historyDrawer = ref(false);
const editId = ref<number>();
const collectingId = ref<number>();
let pollSequence = 0;
const page = ref(1);
const pageSize = ref(10);
const total = ref(0);
const advisoryTableRef = shallowRef<TableInstance>();
const sortBy = ref<SecurityAdvisorySortField>('published');
const sortOrder = ref<'asc' | 'desc'>('desc');
const keywords = ref('');
const form = ref({
  name: '',
  enabled: false,
  interval_minutes: 60,
  severities: [] as string[],
  templateId: undefined as number | undefined,
  receivers: ''
});
const severityOptions = [
  { label: '未评级', value: 'unknown' },
  { label: '严重', value: 'critical' },
  { label: '高危', value: 'high' },
  { label: '中危', value: 'medium' },
  { label: '低危', value: 'low' }
];
const latestCollections = computed(() => {
  const map: Record<number, SecurityCollection> = {};
  for (const item of collections.value) {
    if (map[item.subscription] === undefined) map[item.subscription] = item;
  }
  return map;
});
const POLL_INTERVAL = 1500;
const POLL_MAX_ATTEMPTS = 20;
const DEFAULT_ADVISORY_SORT = { prop: 'published', order: 'descending' } as const;
const ADVISORY_SORT_FIELDS: ReadonlySet<string> = new Set([
  'stable_id',
  'title',
  'category',
  'source_status',
  'published'
]);
interface AdvisorySortChange {
  prop: string;
  order: 'ascending' | 'descending' | null;
}
function isAdvisorySortField(value: string): value is SecurityAdvisorySortField {
  return ADVISORY_SORT_FIELDS.has(value);
}
function advisoryStatusLabel(value: string): string {
  const firstLine = value.split('\n')[0]?.trim() ?? '';
  const status = firstLine.replace(/^CVE-\d{4}-\d+\s*/i, '');
  return status || '—';
}
function handleAdvisorySortChange({ prop, order }: AdvisorySortChange) {
  const nextSortBy = order && isAdvisorySortField(prop) ? prop : DEFAULT_ADVISORY_SORT.prop;
  const nextSortOrder: 'asc' | 'desc' = order === 'ascending' ? 'asc' : 'desc';
  if (!order) advisoryTableRef.value?.sort(DEFAULT_ADVISORY_SORT.prop, DEFAULT_ADVISORY_SORT.order);
  if (nextSortBy === sortBy.value && nextSortOrder === sortOrder.value) return;
  sortBy.value = nextSortBy;
  sortOrder.value = nextSortOrder;
  page.value = 1;
  loadAdvisories();
}
function statusLabel(value: string): string {
  return (
    { queued: '等待采集', running: '采集中', success: '已采集', failed: '采集失败' }[
      value as 'queued' | 'running' | 'success' | 'failed'
    ] ?? value
  );
}
function statusTagType(value: SecurityCollection['status']): 'info' | 'warning' | 'success' | 'danger' {
  const tags = { queued: 'info', running: 'warning', success: 'success', failed: 'danger' } as const;
  return tags[value];
}
async function loadAdvisories() {
  const { data, error } = await getSecurityAdvisories({
    page: page.value,
    pageSize: pageSize.value,
    sortBy: sortBy.value,
    order: sortOrder.value
  });
  if (!error && data) {
    advisories.value = data.list;
    total.value = data.total;
  }
}
function handlePageChange(next: number) {
  page.value = next;
  loadAdvisories();
}
function handlePageSizeChange(size: number) {
  pageSize.value = size;
  page.value = 1;
  loadAdvisories();
}
async function refresh() {
  loading.value = true;
  try {
    const [subs, history] = await Promise.all([getSecuritySubscriptions(), getSecurityCollections(), loadAdvisories()]);
    if (subs.data) subscriptions.value = subs.data;
    if (history.data) collections.value = history.data.list;
  } finally {
    loading.value = false;
  }
}
async function openHistoryDrawer() {
  historyDrawer.value = true;
  const { data } = await getSecurityCollections();
  if (data) collections.value = data.list;
}
function openEditor(row?: SecuritySubscription) {
  editId.value = row?.id;
  keywords.value = row?.keywords.join(', ') ?? '';
  form.value = {
    name: row?.name ?? '阿里云 AVD 订阅',
    enabled: row?.enabled ?? false,
    interval_minutes: row?.interval_minutes ?? 60,
    severities: row?.severities ?? [],
    templateId: row?.notification.templateId,
    receivers: row?.notification.receivers ?? ''
  };
  dialog.value = true;
}
function createSubscription() {
  openEditor();
}
async function save() {
  if (saving.value) return;
  if (form.value.enabled && !hasAuth('security.subscription:collect')) {
    ElMessage.warning('修改已启用的订阅需要采集执行权限，请先停用再保存');
    return;
  }
  if (!form.value.name.trim() || (form.value.enabled && !form.value.templateId)) {
    ElMessage.warning('请填写名称；启用前必须选择通知模板');
    return;
  }
  saving.value = true;
  try {
    const isCreate = editId.value === undefined;
    const { data, error } = await saveSecuritySubscription(
      {
        name: form.value.name,
        enabled: form.value.enabled,
        interval_minutes: form.value.interval_minutes,
        severities: form.value.severities,
        keywords: keywords.value
          .split(',')
          .map(value => value.trim())
          .filter(Boolean),
        notification: form.value.templateId
          ? { templateId: form.value.templateId, receivers: form.value.receivers }
          : {}
      },
      editId.value
    );
    if (error || !data) return;
    dialog.value = false;
    if (isCreate && hasAuth('security.subscription:collect')) {
      await refresh();
      window.$notification?.success('订阅已创建，正在采集基线公告');
      await collect(data);
      return;
    }
    window.$notification?.success('订阅已保存');
    await refresh();
  } finally {
    saving.value = false;
  }
}
function delay(ms: number) {
  return new Promise<void>(resolve => {
    window.setTimeout(resolve, ms);
  });
}
async function pollCollection(recordId: number, sequence: number, attempt = 0): Promise<void> {
  if (attempt >= POLL_MAX_ATTEMPTS) {
    ElMessage.warning('采集任务仍在排队，请检查 Celery Worker 是否运行');
    return;
  }
  await delay(POLL_INTERVAL);
  if (sequence !== pollSequence) return;
  const { data, error } = await getSecurityCollections();
  if (sequence !== pollSequence || error || !data) return;
  collections.value = data.list;
  const record = data.list.find(item => item.id === recordId);
  if (record && record.status !== 'queued' && record.status !== 'running') {
    await loadAdvisories();
    if (record.status === 'success') {
      window.$notification?.success(`采集完成，共获取 ${record.count} 条公告`);
    } else {
      ElMessage.error(record.error || '采集失败，请查看采集记录');
    }
    return;
  }
  await pollCollection(recordId, sequence, attempt + 1);
}
async function collect(row: SecuritySubscription) {
  if (collectingId.value !== undefined) return;
  pollSequence += 1;
  const sequence = pollSequence;
  collectingId.value = row.id;
  try {
    const { data, error } = await collectSecuritySubscription(row.id);
    if (error || !data) return;
    window.$notification?.success('采集任务已提交，正在等待执行');
    await refresh();
    await pollCollection(data.id, sequence);
  } finally {
    if (sequence === pollSequence) collectingId.value = undefined;
  }
}
async function init() {
  await refresh();
  const { data } = await fetchGetNotificationTemplateList({ current: 1, size: 100 });
  if (data) templates.value = data.records;
}
onMounted(init);
onUnmounted(() => {
  pollSequence += 1;
});
</script>

<template>
  <div class="flex flex-col gap-16px">
    <ElAlert
      title="订阅阿里云 AVD 官方漏洞公告。首次采集仅建立基线，后续匹配的新公告和重要变更进入通知队列。此功能不扫描资产。"
      type="info"
      :closable="false"
    />
    <ElCard v-loading="loading" class="card-wrapper">
      <div class="mb-16px flex items-center justify-between gap-12px">
        <span>漏洞公告订阅</span>
        <div>
          <ElButton @click="refresh">刷新</ElButton>
          <ElButton v-if="hasAuth('security.subscription:manage')" type="primary" @click="createSubscription">
            新建订阅
          </ElButton>
        </div>
      </div>
      <ElTable :data="subscriptions" border>
        <ElTableColumn align="center" prop="name" label="订阅名称" min-width="180" />
        <ElTableColumn align="center" label="启用状态" width="100">
          <template #default="{ row }">
            <ElTag>{{ row.enabled ? '已启用' : '已停用' }}</ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn align="center" label="采集基线" width="140">
          <template #default="{ row }">{{ row.initialized_at ? '已建立' : '尚未采集' }}</template>
        </ElTableColumn>
        <ElTableColumn prop="interval_minutes" label="间隔（分钟）" width="130" align="center" />
        <ElTableColumn align="center" label="最近采集" min-width="200">
          <template #default="{ row }">
            <div v-if="latestCollections[row.id]" class="flex items-center justify-center gap-8px">
              <ElTag :type="statusTagType(latestCollections[row.id].status)" size="small">
                {{ statusLabel(latestCollections[row.id].status) }}
              </ElTag>
              <span class="text-12px text-[var(--el-text-color-secondary)]">{{ row.last_attempt_at }}</span>
            </div>
            <span v-else>未采集</span>
          </template>
        </ElTableColumn>
        <ElTableColumn align="center" label="操作" width="180">
          <template #default="{ row }">
            <ElButton v-if="hasAuth('security.subscription:manage')" link @click="openEditor(row)">配置</ElButton>
            <ElButton
              v-if="hasAuth('security.subscription:collect')"
              link
              :loading="collectingId === row.id"
              :disabled="collectingId !== undefined && collectingId !== row.id"
              @click="collect(row)"
            >
              手动采集
            </ElButton>
          </template>
        </ElTableColumn>
      </ElTable>
    </ElCard>
    <ElCard class="card-wrapper">
      <template #header>
        <div class="flex items-center justify-between gap-12px">
          <span>漏洞公告</span>
          <ElButton @click="openHistoryDrawer">采集记录</ElButton>
        </div>
      </template>
      <ElTable
        ref="advisoryTableRef"
        :data="advisories"
        border
        :default-sort="DEFAULT_ADVISORY_SORT"
        @sort-change="handleAdvisorySortChange"
      >
        <ElTableColumn align="center" prop="stable_id" label="AVD编号" width="180" sortable="custom" />
        <ElTableColumn align="center" prop="title" label="漏洞名称" min-width="320" sortable="custom">
          <template #default="{ row }">
            <ElTooltip :content="row.title" placement="top" :show-after="200">
              <ElLink class="max-w-full" type="primary" :href="row.url" target="_blank" rel="noopener noreferrer">
                <span class="block min-w-0 truncate">{{ row.title }}</span>
              </ElLink>
            </ElTooltip>
          </template>
        </ElTableColumn>
        <ElTableColumn align="center" prop="category" label="漏洞类型" min-width="220" sortable="custom">
          <template #default="{ row }">
            <ElTooltip :content="row.category" placement="top" :show-after="200">
              <span class="block truncate">{{ row.category }}</span>
            </ElTooltip>
          </template>
        </ElTableColumn>
        <ElTableColumn align="center" prop="source_status" label="漏洞状态" min-width="160" sortable="custom">
          <template #default="{ row }">
            <ElTooltip :content="advisoryStatusLabel(row.source_status)" placement="top" :show-after="200">
              <span class="block truncate">{{ advisoryStatusLabel(row.source_status) }}</span>
            </ElTooltip>
          </template>
        </ElTableColumn>
        <ElTableColumn align="center" prop="published" label="披露时间" width="140" sortable="custom" />
      </ElTable>
      <ElPagination
        v-if="total"
        :current-page="page"
        :page-size="pageSize"
        :total="total"
        :page-sizes="[10, 15, 20, 25, 30]"
        class="mt-16px justify-end"
        layout="total, sizes, prev, pager, next"
        @current-change="handlePageChange"
        @size-change="handlePageSizeChange"
      />
    </ElCard>
    <ElDrawer v-model="historyDrawer" title="最近 30 次采集记录" size="70%" direction="rtl">
      <ElTable :data="collections" border>
        <ElTableColumn prop="id" label="记录" width="90" align="center" />
        <ElTableColumn prop="subscription" label="订阅 ID" width="100" align="center" />
        <ElTableColumn align="center" label="采集状态" width="130">
          <template #default="{ row }">{{ statusLabel(row.status) }}</template>
        </ElTableColumn>
        <ElTableColumn prop="count" label="采集公告数" width="130" align="center" />
        <ElTableColumn prop="notifications" label="进入通知队列数" width="160" align="center" />
        <ElTableColumn align="center" prop="error" label="失败原因" min-width="220" show-overflow-tooltip />
        <ElTableColumn align="center" prop="created_at" label="提交时间" min-width="200" />
      </ElTable>
      <p class="mt-12px">进入通知队列不等于发送成功；实际发送及重试结果请在通知发送记录中查看。</p>
    </ElDrawer>
    <ElDialog v-model="dialog" :title="editId ? '编辑漏洞订阅' : '新增漏洞订阅'" width="600px">
      <ElForm label-width="130px" label-suffix="：" require-asterisk-position="left">
        <ElFormItem label="名称" required><ElInput v-model="form.name" maxlength="128" /></ElFormItem>
        <ElFormItem label="固定官方来源">阿里云 AVD（https://avd.aliyun.com/）</ElFormItem>
        <ElFormItem label="启用周期订阅">
          <ElSwitch v-model="form.enabled" :disabled="!hasAuth('security.subscription:collect') && !form.enabled" />
        </ElFormItem>
        <ElFormItem label="采集间隔">
          <ElInputNumber v-model="form.interval_minutes" :min="5" :max="10080" />
          <span class="ml-8px">分钟</span>
        </ElFormItem>
        <ElFormItem label="关键词">
          <ElInput v-model="keywords" placeholder="逗号分隔；留空匹配全部，多个词任一匹配" />
        </ElFormItem>
        <ElFormItem label="严重程度">
          <ElSelect v-model="form.severities" multiple placeholder="留空匹配全部">
            <ElOption v-for="item in severityOptions" :key="item.value" :label="item.label" :value="item.value" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="通知模板" :required="form.enabled">
          <ElSelect v-model="form.templateId" clearable placeholder="选择已有通知模板">
            <ElOption v-for="item in templates" :key="item.id" :label="item.name" :value="item.id" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="接收人">
          <ElInput v-model="form.receivers" placeholder="留空使用模板接收人" maxlength="1024" />
        </ElFormItem>
      </ElForm>
      <p
        v-if="!editId && hasAuth('security.subscription:collect')"
        class="text-12px text-[var(--el-text-color-secondary)]"
      >
        新增订阅保存后会立即采集一次基线公告；启用周期订阅后按采集间隔自动检查新公告。
      </p>
      <template #footer>
        <ElButton @click="dialog = false">取消</ElButton>
        <ElButton type="primary" :loading="saving" @click="save">保存</ElButton>
      </template>
    </ElDialog>
  </div>
</template>
