<script setup lang="tsx">
import { computed, ref } from 'vue';
import {
  fetchAddNotificationTemplate,
  fetchDeleteNotificationTemplate,
  fetchGetNotificationChannels,
  fetchGetNotificationTemplateList,
  fetchUpdateNotificationTemplate
} from '@/service/api';
import { defaultTransform, useUIPaginatedTable } from '@/hooks/common/table';

defineOptions({ name: 'AutomationNotificationResource' });

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
  email: '邮件'
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
      prop: 'channel',
      label: '渠道',
      width: 130,
      align: 'center',
      formatter: row =>
        row.channel && row.channelName ? (
          <ElTag type="primary">
            {row.channelName}
            {row.channelType ? `（${channelTypeText[row.channelType] ?? row.channelType}）` : ''}
          </ElTag>
        ) : (
          '-'
        )
    },
    {
      prop: 'subject_template',
      label: '标题模板',
      minWidth: 180,
      showOverflowTooltip: true,
      formatter: row => row.subject_template || '-'
    },
    {
      prop: 'is_active',
      label: '状态',
      width: 90,
      align: 'center',
      formatter: row => <ElTag type={row.is_active ? 'success' : 'info'}>{row.is_active ? '启用' : '停用'}</ElTag>
    },
    { prop: 'updated_at', label: '更新时间', width: 170, formatter: row => row.updated_at || '-' },
    {
      prop: 'operate',
      label: '操作',
      width: 150,
      align: 'center',
      fixed: 'right',
      formatter: row => (
        <>
          <ElButton type="primary" plain size="small" onClick={() => openOperateDrawer('edit', row)}>
            编辑
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

async function loadChannels() {
  const { data: channels, error } = await fetchGetNotificationChannels();
  if (!error) {
    channelOptions.value = channels ?? [];
  }
}

loadChannels();

/** ============ 新增/编辑抽屉 ============ */

type OperateType = 'add' | 'edit';

interface FormModel {
  id?: number;
  name: string;
  code: string;
  description: string;
  channel: number | null;
  subject_template: string;
  body_template: string;
  receiver_template: string;
  is_active: boolean;
}

function createDefaultForm(): FormModel {
  return {
    name: '',
    code: '',
    description: '',
    channel: null,
    subject_template: '',
    body_template: '',
    receiver_template: '',
    is_active: true
  };
}

const drawerVisible = ref(false);
const operateType = ref<OperateType>('add');
const submitting = ref(false);
const formRef = ref();
const formModel = ref<FormModel>(createDefaultForm());

const formRules = {
  name: [{ required: true, message: '请输入模板名称', trigger: 'blur' }],
  code: [{ required: true, message: '请输入编码', trigger: 'blur' }]
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
        subject_template: row.subject_template,
        body_template: row.body_template,
        receiver_template: row.receiver_template,
        is_active: row.is_active
      }
    : createDefaultForm();
  drawerVisible.value = true;
}

async function handleSubmit() {
  await formRef.value?.validate();

  submitting.value = true;
  const payload: Api.Automation.NotificationTemplatePayload = {
    name: formModel.value.name,
    code: formModel.value.code,
    description: formModel.value.description,
    channel: formModel.value.channel ?? null,
    subject_template: formModel.value.subject_template,
    body_template: formModel.value.body_template,
    receiver_template: formModel.value.receiver_template,
    is_active: formModel.value.is_active
  };
  const { error } =
    operateType.value === 'add'
      ? await fetchAddNotificationTemplate(payload)
      : await fetchUpdateNotificationTemplate(formModel.value.id!, payload);
  submitting.value = false;

  if (!error) {
    window.$message?.success(operateType.value === 'add' ? '新增成功' : '修改成功');
    drawerVisible.value = false;
    getData();
  }
}

async function handleDelete(id: number) {
  const { error } = await fetchDeleteNotificationTemplate(id);

  if (!error) {
    window.$message?.success('删除成功');
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
            placeholder="名称/编码/标题"
            class="w-240px"
            @keyup.enter="getDataByPage()"
          />
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
          <p>通知模板</p>
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

    <ElDrawer v-model="drawerVisible" :title="operateType === 'add' ? '新增通知模板' : '编辑通知模板'" size="480px">
      <ElForm ref="formRef" :model="formModel" :rules="formRules" label-width="100px">
        <ElFormItem label="模板名称" prop="name">
          <ElInput v-model="formModel.name" placeholder="模板名称" />
        </ElFormItem>
        <ElFormItem label="编码" prop="code">
          <ElInput v-model="formModel.code" :disabled="operateType === 'edit'" placeholder="如 deploy_success" />
        </ElFormItem>
        <ElFormItem label="描述">
          <ElInput v-model="formModel.description" placeholder="模板用途说明" />
        </ElFormItem>
        <ElFormItem label="通知渠道">
          <ElSelect v-model="formModel.channel" clearable class="w-full" placeholder="请选择渠道">
            <ElOption
              v-for="item in channelOptions"
              :key="item.id"
              :label="`${item.name}（${channelTypeText[item.channel_type] ?? item.channel_type}）`"
              :value="item.id"
            />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="标题模板">
          <ElInput v-model="formModel.subject_template" placeholder="如 {{ title }}" />
        </ElFormItem>
        <ElFormItem label="内容模板">
          <ElInput v-model="formModel.body_template" type="textarea" :rows="6" placeholder="支持 {{ var }} 变量占位" />
        </ElFormItem>
        <ElFormItem label="接收人模板">
          <ElInput
            v-model="formModel.receiver_template"
            type="textarea"
            :rows="3"
            placeholder="接收人/群/机器人配置模板"
          />
        </ElFormItem>
        <ElFormItem label="启用">
          <ElSwitch v-model="formModel.is_active" />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="drawerVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="submitting" @click="handleSubmit">确定</ElButton>
      </template>
    </ElDrawer>
  </div>
</template>
