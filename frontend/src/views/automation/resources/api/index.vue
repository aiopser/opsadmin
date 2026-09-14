<script setup lang="tsx">
import { computed, ref } from 'vue';
import {
  fetchAddApiEndpoint,
  fetchDeleteApiEndpoint,
  fetchGetApiEndpointList,
  fetchUpdateApiEndpoint
} from '@/service/api';
import { defaultTransform, useUIPaginatedTable } from '@/hooks/common/table';

defineOptions({ name: 'AutomationApiResource' });

/** ============ 搜索 ============ */

function getInitSearchParams() {
  return { current: 1, size: 10, search: undefined as string | undefined };
}

const searchParams = ref(getInitSearchParams());

/** ============ 列表 ============ */

const methodOptions = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'];

const methodTagType: Record<string, 'primary' | 'success' | 'warning' | 'info' | 'danger'> = {
  GET: 'success',
  POST: 'warning',
  PUT: 'info',
  PATCH: 'primary',
  DELETE: 'danger'
};

const authTypeOptions = [
  { value: 'none', label: '无认证' },
  { value: 'basic', label: 'Basic' },
  { value: 'bearer', label: 'Bearer' },
  { value: 'api_key', label: 'API Key' }
];

const authTypeText: Record<string, string> = Object.fromEntries(authTypeOptions.map(item => [item.value, item.label]));

const { columns, columnChecks, data, getData, getDataByPage, loading, mobilePagination } = useUIPaginatedTable({
  paginationProps: {
    currentPage: searchParams.value.current,
    pageSize: searchParams.value.size
  },
  api: () => fetchGetApiEndpointList(searchParams.value),
  transform: response => defaultTransform(response),
  onPaginationParamsChange: params => {
    searchParams.value.current = params.currentPage ?? 1;
    searchParams.value.size = params.pageSize ?? 10;
  },
  columns: () => [
    { prop: 'id', label: 'ID', width: 70 },
    { prop: 'name', label: '名称', minWidth: 140, showOverflowTooltip: true },
    {
      prop: 'description',
      label: '描述',
      minWidth: 140,
      showOverflowTooltip: true,
      formatter: row => row.description || '-'
    },
    {
      prop: 'method',
      label: '请求方法',
      width: 100,
      align: 'center',
      formatter: row => <ElTag type={methodTagType[row.method] ?? 'info'}>{row.method}</ElTag>
    },
    {
      prop: 'url',
      label: 'URL',
      minWidth: 200,
      showOverflowTooltip: true,
      formatter: row => <span class="text-12px font-mono">{row.url}</span>
    },
    {
      prop: 'auth_type',
      label: '认证',
      width: 90,
      align: 'center',
      formatter: row => authTypeText[row.auth_type] ?? row.auth_type
    },
    { prop: 'timeout_seconds', label: '超时(s)', width: 90, align: 'center' },
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
          <ElPopconfirm title="确认删除该 API 端点？" onConfirm={() => handleDelete(row.id)}>
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

/** ============ 新增/编辑抽屉 ============ */

type OperateType = 'add' | 'edit';

interface FormModel {
  id?: number;
  name: string;
  description: string;
  method: string;
  url: string;
  auth_type: 'none' | 'basic' | 'bearer' | 'api_key';
  username: string;
  secret: string;
  headersText: string;
  timeout_seconds: number;
  verify_ssl: boolean;
  is_active: boolean;
}

function createDefaultForm(): FormModel {
  return {
    name: '',
    description: '',
    method: 'GET',
    url: '',
    auth_type: 'none',
    username: '',
    secret: '',
    headersText: '{}',
    timeout_seconds: 30,
    verify_ssl: true,
    is_active: true
  };
}

const drawerVisible = ref(false);
const operateType = ref<OperateType>('add');
const submitting = ref(false);
const formRef = ref();
const formModel = ref<FormModel>(createDefaultForm());

const formRules = {
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  url: [{ required: true, message: '请输入请求 URL', trigger: 'blur' }]
};

function openOperateDrawer(type: OperateType, row?: Api.Automation.ApiEndpointRecord) {
  operateType.value = type;
  formModel.value = row
    ? {
        id: row.id,
        name: row.name,
        description: row.description,
        method: row.method,
        url: row.url,
        auth_type: (row.auth_type || 'none') as FormModel['auth_type'],
        username: row.username,
        secret: '',
        headersText: JSON.stringify(row.headers ?? {}, null, 2),
        timeout_seconds: row.timeout_seconds,
        verify_ssl: row.verify_ssl,
        is_active: row.is_active
      }
    : createDefaultForm();
  drawerVisible.value = true;
}

async function handleSubmit() {
  await formRef.value?.validate();

  let headers: Record<string, unknown> | undefined;
  if (formModel.value.headersText.trim()) {
    try {
      const parsed = JSON.parse(formModel.value.headersText);
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
        window.$message?.error('Headers 必须是 JSON 对象');
        return;
      }
      headers = parsed as Record<string, unknown>;
    } catch {
      window.$message?.error('Headers JSON 格式不正确');
      return;
    }
  }

  submitting.value = true;
  const payload: Api.Automation.ApiEndpointPayload = {
    name: formModel.value.name,
    description: formModel.value.description,
    method: formModel.value.method,
    url: formModel.value.url,
    auth_type: formModel.value.auth_type,
    username: formModel.value.username,
    timeout_seconds: formModel.value.timeout_seconds,
    verify_ssl: formModel.value.verify_ssl,
    is_active: formModel.value.is_active
  };
  if (headers) {
    payload.headers = headers;
  }
  // secret 仅在填写时提交（编辑留空表示不修改密钥）
  if (formModel.value.secret) {
    payload.secret = formModel.value.secret;
  }
  const { error } =
    operateType.value === 'add'
      ? await fetchAddApiEndpoint(payload)
      : await fetchUpdateApiEndpoint(formModel.value.id!, payload);
  submitting.value = false;

  if (!error) {
    window.$message?.success(operateType.value === 'add' ? '新增成功' : '修改成功');
    drawerVisible.value = false;
    getData();
  }
}

async function handleDelete(id: number) {
  const { error } = await fetchDeleteApiEndpoint(id);

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
            placeholder="名称/URL/描述"
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
          <p>API 端点</p>
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

    <ElDrawer v-model="drawerVisible" :title="operateType === 'add' ? '新增 API 端点' : '编辑 API 端点'" size="480px">
      <ElForm ref="formRef" :model="formModel" :rules="formRules" label-width="100px">
        <ElFormItem label="名称" prop="name">
          <ElInput v-model="formModel.name" placeholder="端点名称" />
        </ElFormItem>
        <ElFormItem label="请求 URL" prop="url">
          <ElInput v-model="formModel.url" placeholder="https://example.com/api" />
        </ElFormItem>
        <ElFormItem label="请求方法">
          <ElSelect v-model="formModel.method" class="w-full">
            <ElOption v-for="item in methodOptions" :key="item" :label="item" :value="item" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="描述">
          <ElInput v-model="formModel.description" placeholder="端点用途说明" />
        </ElFormItem>
        <ElFormItem label="认证方式">
          <ElSelect v-model="formModel.auth_type" class="w-full">
            <ElOption v-for="item in authTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="用户名">
          <ElInput v-model="formModel.username" placeholder="Basic 认证用户名" />
        </ElFormItem>
        <ElFormItem label="密钥">
          <ElInput
            v-model="formModel.secret"
            type="password"
            show-password
            :placeholder="operateType === 'edit' ? '留空则不修改密钥' : 'Token / 密码 / API Key'"
          />
        </ElFormItem>
        <ElFormItem label="Headers">
          <ElInput
            v-model="formModel.headersText"
            type="textarea"
            :rows="4"
            class="font-mono"
            placeholder='{"Content-Type": "application/json"}'
          />
        </ElFormItem>
        <ElFormItem label="超时(秒)">
          <ElInputNumber v-model="formModel.timeout_seconds" :min="1" :max="600" class="w-full" />
        </ElFormItem>
        <ElFormItem label="校验 SSL">
          <ElSwitch v-model="formModel.verify_ssl" />
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
