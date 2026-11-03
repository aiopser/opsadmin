<script setup lang="tsx">
import { computed, onUnmounted, ref, shallowRef } from 'vue';
import {
  fetchAddNotificationTemplate,
  fetchDeleteNotificationTemplate,
  fetchGetNotificationChannels,
  fetchGetNotificationRecords,
  fetchGetNotificationTemplateList,
  fetchGetRunDetail,
  fetchTestNotificationTemplate,
  fetchUpdateNotificationTemplate
} from '@/service/api';
import { defaultTransform, useUIPaginatedTable } from '@/hooks/common/table';
import NotificationPreview from './notification-preview.vue';

defineOptions({ name: 'AutomationNotificationResource' });

const activeTab = ref<'templates' | 'records'>('templates');

/** ============ 搜索 ============ */

function getInitSearchParams() {
  return { current: 1, size: 10, search: undefined as string | undefined };
}

const searchParams = ref(getInitSearchParams());

/** ============ 列表 ============ */

const channelTypeText: Record<string, string> = {
  webhook: 'Webhook',
  wecom: '企业微信',
  dingtalk: '钉钉',
  feishu: '飞书',
  email: '邮件'
};

const recordStatusMeta: Record<string, { text: string; type: 'success' | 'danger' | 'info' }> = {
  success: { text: '成功', type: 'success' },
  failed: { text: '失败', type: 'danger' },
  sending: { text: '发送中', type: 'info' },
  pending: { text: '待发送', type: 'info' }
};

const { columns, columnChecks, data, getData, getDataByPage, loading, mobilePagination } = useUIPaginatedTable({
  paginationProps: {
    currentPage: searchParams.value.current,
    pageSize: searchParams.value.size
  },
  api: () => fetchGetNotificationTemplateList(searchParams.value),
  transform: response => defaultTransform(response),
  onPaginationParamsChange: params => {
    searchParams.value.current = params.currentPage ?? 1;
    searchParams.value.size = params.pageSize ?? 10;
  },
  columns: () => [
    { prop: 'id', label: 'ID', width: 70 },
    { prop: 'name', label: '模板名称', minWidth: 140, showOverflowTooltip: true },
    { prop: 'code', label: '编码', minWidth: 130, showOverflowTooltip: true },
    {
      prop: 'description',
      label: '描述',
      minWidth: 140,
      showOverflowTooltip: true,
      formatter: row => row.description || '-'
    },
    {
      prop: 'channel',
      label: '渠道',
      minWidth: 140,
      align: 'center',
      formatter: row =>
        row.channel && row.channelName ? (
          <ElTag type="primary" size="small">
            {row.channelName}
            {row.channelType ? `（${channelTypeText[row.channelType] ?? row.channelType}）` : ''}
          </ElTag>
        ) : (
          '-'
        )
    },
    {
      prop: 'subjectTemplate',
      label: '标题模板',
      minWidth: 180,
      showOverflowTooltip: true,
      formatter: row => row.subjectTemplate || '-'
    },
    {
      prop: 'isActive',
      label: '状态',
      width: 90,
      align: 'center',
      formatter: row => (
        <ElTag size="small" type={row.isActive ? 'success' : 'info'}>
          {row.isActive ? '启用' : '停用'}
        </ElTag>
      )
    },
    { prop: 'updatedAt', label: '更新时间', width: 170, formatter: row => row.updatedAt || '-' },
    {
      prop: 'operate',
      label: '操作',
      width: 205,
      align: 'center',
      fixed: 'right',
      formatter: row => (
        <>
          <ElButton type="primary" plain size="small" onClick={() => openOperateDrawer('edit', row)}>
            编辑
          </ElButton>
          <ElButton type="primary" plain size="small" onClick={() => openTestSend(row)}>
            测试
          </ElButton>
          <ElPopconfirm title="确认删除该通知模板？" onConfirm={() => handleDelete(row.id)}>
            {{
              reference: () => (
                <ElButton type="danger" plain size="small">
                  删除
                </ElButton>
              )
            }}
          </ElPopconfirm>
        </>
      )
    }
  ]
});

const hasFilter = computed(() => Boolean(searchParams.value.search));

function resetSearchParams() {
  searchParams.value = getInitSearchParams();
  getDataByPage();
}

/** ============ 渠道下拉数据源 ============ */

const channelOptions = ref<Api.Automation.NotificationChannelRecord[]>([]);
const records = ref<Api.Automation.NotificationRecord[]>([]);
const recordsLoading = ref(false);
const recordsPage = ref(1);
const recordsTotal = ref(0);
let testRefreshTimer: ReturnType<typeof setTimeout> | undefined;

function stopTestRefresh() {
  if (testRefreshTimer) clearTimeout(testRefreshTimer);
  testRefreshTimer = undefined;
}

async function loadRecords() {
  recordsLoading.value = true;
  const { data: result, error } = await fetchGetNotificationRecords({ current: recordsPage.value, size: 10 });
  recordsLoading.value = false;
  if (error || !result) return;
  records.value = result.records;
  recordsTotal.value = result.total;
}

function changeRecordsPage(page: number) {
  recordsPage.value = page;
  loadRecords();
}

function handleTabChange(tab: string | number) {
  if (tab === 'records') {
    recordsPage.value = 1;
    loadRecords();
  }
}

async function loadChannels() {
  const { data: channels, error } = await fetchGetNotificationChannels();
  if (!error) {
    channelOptions.value = channels ?? [];
  }
}

loadChannels();
loadRecords();

/** ============ 新增/编辑抽屉 ============ */

type OperateType = 'add' | 'edit';

interface FormModel {
  id?: number;
  name: string;
  code: string;
  description: string;
  channel: number | null;
  subjectTemplate: string;
  bodyTemplate: string;
  receiverTemplate: string;
  isActive: boolean;
}

function createDefaultForm(): FormModel {
  return {
    name: '',
    code: '',
    description: '',
    channel: null,
    subjectTemplate: '',
    bodyTemplate: '',
    receiverTemplate: '',
    isActive: true
  };
}

const drawerVisible = ref(false);
const operateType = ref<OperateType>('add');
const submitting = ref(false);
const formRef = ref();
const formModel = ref<FormModel>(createDefaultForm());
const testDialogVisible = ref(false);
const testSending = ref(false);
const testTemplate = shallowRef<Api.Automation.NotificationTemplateRecord | null>(null);
const validatedSample = shallowRef<Api.Automation.NotificationSample | null>(null);
const templateToolsVisible = ref(false);
const selectedChannelType = computed(
  () => channelOptions.value.find(channel => channel.id === formModel.value.channel)?.channelType
);
const selectableChannels = computed(() =>
  channelOptions.value.filter(channel => channel.isActive || channel.id === formModel.value.channel)
);

const formRules = {
  name: [{ required: true, message: '请输入模板名称', trigger: 'blur' }],
  code: [{ required: true, message: '请输入编码', trigger: 'blur' }],
  channel: [{ required: true, message: '请选择通知渠道', trigger: 'change' }],
  bodyTemplate: [{ required: true, whitespace: true, message: '请输入内容模板', trigger: 'blur' }]
};

function openOperateDrawer(type: OperateType, row?: Api.Automation.NotificationTemplateRecord) {
  operateType.value = type;
  formModel.value = row
    ? {
        id: row.id,
        name: row.name,
        code: row.code,
        description: row.description,
        channel: row.channel,
        subjectTemplate: row.subjectTemplate,
        bodyTemplate: row.bodyTemplate,
        receiverTemplate: row.receiverTemplate,
        isActive: row.isActive
      }
    : createDefaultForm();
  drawerVisible.value = true;
  templateToolsVisible.value = false;
}

function insertTemplateVariable(expression: string, field: 'subjectTemplate' | 'bodyTemplate' | 'receiverTemplate') {
  formModel.value[field] += expression;
}

function openTestSend(row: Api.Automation.NotificationTemplateRecord) {
  testTemplate.value = row;
  validatedSample.value = null;
  testDialogVisible.value = true;
}

function updateValidatedSample(sample: Api.Automation.NotificationSample | null) {
  validatedSample.value = sample;
}

async function submitTestSend() {
  if (!testTemplate.value || !validatedSample.value || testSending.value) return;
  testSending.value = true;
  try {
    await handleTestSend(testTemplate.value.id, validatedSample.value);
  } finally {
    testSending.value = false;
  }
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false);
  if (!valid) return;

  submitting.value = true;
  const payload: Api.Automation.NotificationTemplatePayload = {
    name: formModel.value.name,
    code: formModel.value.code,
    description: formModel.value.description,
    channel: formModel.value.channel ?? null,
    subjectTemplate: formModel.value.subjectTemplate,
    bodyTemplate: formModel.value.bodyTemplate,
    receiverTemplate: formModel.value.receiverTemplate,
    isActive: formModel.value.isActive
  };
  const { error } =
    operateType.value === 'add'
      ? await fetchAddNotificationTemplate(payload)
      : await fetchUpdateNotificationTemplate(formModel.value.id!, payload);
  submitting.value = false;

  if (!error) {
    window.$notification?.success(operateType.value === 'add' ? '新增成功' : '修改成功');
    drawerVisible.value = false;
    getData();
  }
}

async function handleDelete(id: number) {
  const { error } = await fetchDeleteNotificationTemplate(id);

  if (!error) {
    window.$notification?.success('删除成功');
    getData();
  }
}

async function handleTestSend(id: number, sample: Api.Automation.NotificationSample) {
  const { data: result, error } = await fetchTestNotificationTemplate(id, sample);
  const runId = result?.workflowRunId;
  if (error || !runId) return;
  testDialogVisible.value = false;
  const confirmedRunId: number = runId;
  stopTestRefresh();
  window.$notification?.success(`测试运行已发起（#${runId}），正在等待发送结果`);
  activeTab.value = 'records';
  async function refreshTestResult(attempt: number) {
    await loadRecords();
    if (records.value.some(record => record.workflowRunId === confirmedRunId)) return;

    const { data: run, error: runError } = await fetchGetRunDetail(confirmedRunId);
    if (!runError && run && ['failed', 'timeout', 'canceled'].includes(run.status)) {
      window.$message?.error(`测试运行失败：${run.failureReason || '请查看运行详情'}`);
      return;
    }
    if (attempt >= 15) {
      window.$message?.warning('暂未生成发送记录，请检查测试运行状态和 Worker 服务');
      return;
    }
    testRefreshTimer = setTimeout(() => refreshTestResult(attempt + 1), 2000);
  }
  await refreshTestResult(1);
}

onUnmounted(stopTestRefresh);
</script>

<template>
  <div class="min-h-500px flex-col-stretch gap-16px overflow-auto">
    <ElTabs v-model="activeTab" @tab-change="handleTabChange">
      <ElTabPane label="通知模板" name="templates" />
      <ElTabPane label="发送记录" name="records" />
    </ElTabs>
    <SearchPanel v-if="activeTab === 'templates'" @reset="resetSearchParams" @search="getDataByPage">
      <ElForm :model="searchParams" label-width="80px" @submit.prevent="getDataByPage">
        <ElFormItem label="关键词">
          <ElInput
            v-model="searchParams.search"
            clearable
            placeholder="名称/编码/标题"
            @keyup.enter="getDataByPage()"
            @clear="getDataByPage()"
          />
        </ElFormItem>
      </ElForm>
    </SearchPanel>

    <ElCard v-if="activeTab === 'templates'" class="card-wrapper sm:flex-1-hidden">
      <template #header>
        <div class="flex flex-wrap items-center justify-between gap-8px">
          <div class="min-w-0 flex flex-wrap items-baseline gap-8px">
            <p>通知模板</p>
            <span class="text-13px text-gray-500">
              供流程通知节点与失败告警引用，先在「变量说明与预览」中验证再发布
            </span>
          </div>
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
          <template #empty>
            <ElEmpty
              v-if="!loading"
              :description="hasFilter ? '没有符合条件的通知模板' : '暂无通知模板'"
              :image-size="80"
            >
              <ElButton v-if="!hasFilter" type="primary" @click="openOperateDrawer('add')">新增通知模板</ElButton>
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
      class="notification-template-drawer"
      :title="operateType === 'add' ? '新增通知模板' : '编辑通知模板'"
      size="min(760px, 100vw)"
    >
      <section
        class="notification-template-help mb-20px border border-[var(--el-color-primary-light-7)] bg-[var(--el-color-primary-light-9)]"
      >
        <div class="min-h-44px flex items-center justify-between gap-12px px-16px py-8px">
          <span class="inline-flex items-center gap-8px">
            <icon-ep-info-filled class="text-16px text-[var(--el-color-primary)]" aria-hidden="true" />
            <span class="text-13px">变量说明与预览</span>
          </span>
          <ElSwitch
            v-model="templateToolsVisible"
            inline-prompt
            active-text="显示"
            inactive-text="隐藏"
            :width="58"
            aria-label="显示变量说明与预览"
            aria-controls="notification-template-tools"
          />
        </div>
        <ElCollapseTransition>
          <div v-show="templateToolsVisible" id="notification-template-tools" class="px-16px pb-16px pt-4px">
            <NotificationPreview
              v-if="drawerVisible"
              :subject-template="formModel.subjectTemplate"
              :body-template="formModel.bodyTemplate"
              :receiver-template="formModel.receiverTemplate"
              :channel-type="selectedChannelType"
              insertable
              @insert="insertTemplateVariable"
            />
          </div>
        </ElCollapseTransition>
      </section>
      <ElForm
        ref="formRef"
        :model="formModel"
        :rules="formRules"
        label-width="120px"
        label-suffix="："
        require-asterisk-position="left"
      >
        <ElFormItem label="模板名称" prop="name">
          <ElInput v-model="formModel.name" placeholder="如：部署成功通知" />
        </ElFormItem>
        <ElFormItem prop="code">
          <template #label>
            <FormLabelHelp label="编码" :help="['模板唯一编码，供流程节点引用；', '创建后不可修改。']" />
          </template>
          <ElInput v-model="formModel.code" :disabled="operateType === 'edit'" placeholder="如 deploy_success" />
        </ElFormItem>
        <ElFormItem label="描述">
          <ElInput v-model="formModel.description" placeholder="模板用途说明" />
        </ElFormItem>
        <ElFormItem prop="channel">
          <template #label>
            <FormLabelHelp
              label="通知渠道"
              :help="[
                '决定发送方式（Webhook / 企业微信 / 钉钉 / 飞书 / 邮件）；',
                '渠道的地址、密钥等配置在「通知渠道」中维护。'
              ]"
            />
          </template>
          <ElSelect v-model="formModel.channel" clearable class="w-full" placeholder="请选择渠道">
            <ElOption
              v-for="item in selectableChannels"
              :key="item.id"
              :label="`${item.name}（${channelTypeText[item.channelType] ?? item.channelType}）`"
              :value="item.id"
            />
          </ElSelect>
        </ElFormItem>
        <ElFormItem>
          <template #label>
            <FormLabelHelp
              label="标题模板"
              :help="[
                '可在顶部「变量说明与预览」查看并插入变量。',
                '钉钉、飞书、企微文本消息只发送正文，标题仍需通过模板校验。'
              ]"
            />
          </template>
          <ElInput v-model="formModel.subjectTemplate" placeholder="示例：{{ title }}" />
        </ElFormItem>
        <ElFormItem prop="bodyTemplate">
          <template #label>
            <FormLabelHelp
              label="内容模板"
              :help="[
                '支持 {{ 变量 }} 占位；不同通知场景提供的变量不同。',
                '可在顶部「变量说明与预览」选择场景，编辑测试数据并查看渲染结果。'
              ]"
            />
          </template>
          <ElInput v-model="formModel.bodyTemplate" type="textarea" :rows="6" placeholder="支持 {{ var }} 变量占位" />
        </ElFormItem>
        <ElFormItem>
          <template #label>
            <FormLabelHelp
              label="接收人模板"
              :help="['渠道未配置接收人时使用本模板，支持 {{ 变量 }} 占位；', '渲染结果按逗号分隔或 JSON 数组解析。']"
            />
          </template>
          <ElInput
            v-model="formModel.receiverTemplate"
            type="textarea"
            :rows="3"
            placeholder="接收人/群/机器人配置模板"
          />
        </ElFormItem>
        <ElFormItem>
          <template #label>
            <FormLabelHelp label="启用" :help="['停用后引用该模板的通知节点将无法通过发布校验。']" />
          </template>
          <ElSwitch v-model="formModel.isActive" />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="drawerVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="submitting" @click="handleSubmit">保存</ElButton>
      </template>
    </ElDrawer>
    <ElDialog v-model="testDialogVisible" title="测试通知模板" width="min(860px, 94vw)" destroy-on-close>
      <div v-if="testTemplate" class="max-h-65vh flex flex-col gap-16px overflow-auto">
        <div class="flex flex-wrap items-center gap-8px">
          <span class="text-15px font-medium">{{ testTemplate.name }}</span>
          <ElTag v-if="testTemplate.channelName" size="small" type="primary">
            {{
              testTemplate.channelName +
              (testTemplate.channelType
                ? `（${channelTypeText[testTemplate.channelType] ?? testTemplate.channelType}）`
                : '')
            }}
          </ElTag>
          <ElTag v-else size="small" type="info">未配置渠道</ElTag>
        </div>
        <NotificationPreview
          :subject-template="testTemplate.subjectTemplate"
          :body-template="testTemplate.bodyTemplate"
          :receiver-template="testTemplate.receiverTemplate"
          :channel-type="testTemplate.channelType"
          @validated="updateValidatedSample"
        />
      </div>
      <template #footer>
        <ElButton :disabled="testSending" @click="testDialogVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="testSending" :disabled="!validatedSample" @click="submitTestSend">
          发送测试
        </ElButton>
      </template>
    </ElDialog>
    <ElCard v-if="activeTab === 'records'" class="card-wrapper">
      <template #header>
        <div class="flex flex-wrap items-center justify-between gap-8px">
          <div class="min-w-0 flex flex-wrap items-baseline gap-8px">
            <p>发送记录</p>
            <span class="text-13px text-gray-500">模板测试与流程通知的实际投递结果</span>
          </div>
          <ElButton :loading="recordsLoading" @click="loadRecords">刷新</ElButton>
        </div>
      </template>
      <ElTable v-loading="recordsLoading" :data="records" border class="w-full" row-key="id">
        <ElTableColumn prop="sentAt" label="发送时间" width="175" align="center" header-align="center" />
        <ElTableColumn
          prop="templateName"
          label="模板"
          min-width="140"
          align="center"
          header-align="center"
          show-overflow-tooltip
        />
        <ElTableColumn
          prop="channelName"
          label="渠道"
          min-width="140"
          align="center"
          header-align="center"
          show-overflow-tooltip
        />
        <ElTableColumn label="状态" width="90" align="center" header-align="center">
          <template #default="{ row }">
            <ElTag size="small" :type="recordStatusMeta[row.status]?.type ?? 'info'">
              {{ recordStatusMeta[row.status]?.text ?? row.status }}
            </ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn label="尝试次数" width="95" align="center" header-align="center" class-name="tabular-nums">
          <template #default="{ row }">{{ row.attemptCount ?? 0 }}</template>
        </ElTableColumn>
        <ElTableColumn prop="nextRetryAt" label="下次重试" width="175" align="center" header-align="center">
          <template #default="{ row }">{{ row.nextRetryAt || '-' }}</template>
        </ElTableColumn>
        <ElTableColumn
          prop="failureReason"
          label="失败原因"
          min-width="200"
          align="left"
          header-align="center"
          show-overflow-tooltip
        />
        <template #empty>
          <ElEmpty description="暂无发送记录" :image-size="80">
            <span class="text-12px text-[var(--el-text-color-regular)]">
              发送测试或触发流程通知后，投递结果将显示在这里
            </span>
          </ElEmpty>
        </template>
      </ElTable>
      <div class="mt-16px flex justify-end">
        <ElPagination
          v-if="recordsTotal"
          :current-page="recordsPage"
          :page-size="10"
          :total="recordsTotal"
          layout="total,prev,pager,next"
          @current-change="changeRecordsPage"
        />
      </div>
    </ElCard>
  </div>
</template>
