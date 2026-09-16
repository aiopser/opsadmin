<script setup lang="tsx">
import { computed, ref } from 'vue';
import {
  fetchAddCredentialRef,
  fetchDeleteCredentialRef,
  fetchGetCredentialRefList,
  fetchUpdateCredentialRef
} from '@/service/api';
import { defaultTransform, useUIPaginatedTable } from '@/hooks/common/table';

defineOptions({ name: 'CmdbCredential' });

/** ============ 搜索 ============ */

const typeOptions = [
  { value: 'ssh_key', label: 'SSH 密钥' },
  { value: 'password', label: '密码' }
  // vault_ref 不可选：当前部署未配置 Vault Provider，后端会拒绝该类型
];

const scopeOptions = [
  { value: 'global', label: '全局' },
  { value: 'environment', label: '环境' },
  { value: 'host_group', label: '主机组' },
  { value: 'host', label: '主机' }
];

const typeText: Record<string, string> = Object.fromEntries(typeOptions.map(item => [item.value, item.label]));
const scopeText: Record<string, string> = Object.fromEntries(scopeOptions.map(item => [item.value, item.label]));

function getInitSearchParams() {
  return {
    current: 1,
    size: 10,
    search: undefined as string | undefined,
    type: undefined as Api.Cmdb.CredentialType | undefined,
    scope: undefined as Api.Cmdb.CredentialScope | undefined
  };
}

const searchParams = ref(getInitSearchParams());

/** ============ 列表 ============ */

const { columns, columnChecks, data, getData, getDataByPage, loading, mobilePagination } = useUIPaginatedTable({
  paginationProps: {
    currentPage: searchParams.value.current,
    pageSize: searchParams.value.size
  },
  api: () => fetchGetCredentialRefList(searchParams.value),
  transform: response => defaultTransform(response),
  onPaginationParamsChange: params => {
    searchParams.value.current = params.currentPage ?? 1;
    searchParams.value.size = params.pageSize ?? 10;
  },
  columns: () => [
    { prop: 'id', label: 'ID', width: 70 },
    { prop: 'name', label: '名称', minWidth: 150, showOverflowTooltip: true },
    {
      prop: 'type',
      label: '类型',
      width: 110,
      align: 'center',
      formatter: row => <ElTag type="primary">{typeText[row.type] ?? row.type}</ElTag>
    },
    {
      prop: 'scope',
      label: '作用域',
      width: 100,
      align: 'center',
      formatter: row => scopeText[row.scope] ?? row.scope
    },
    { prop: 'connection_type', label: '协议', width: 90, align: 'center' },
    { prop: 'username', label: '用户名', width: 110, formatter: row => row.username || '-' },
    {
      prop: 'effectivePort',
      label: '端口',
      width: 80,
      align: 'center',
      formatter: row => String(row.effectivePort ?? '-')
    },
    {
      prop: 'secret_ref',
      label: '外部引用',
      minWidth: 140,
      showOverflowTooltip: true,
      formatter: row => row.secret_ref || '-'
    },
    {
      prop: 'encrypted_secret',
      label: '密钥',
      width: 110,
      formatter: row => <span class="text-12px font-mono">{row.encrypted_secret || '-'}</span>
    },
    { prop: 'hostCount', label: '关联主机', width: 90, align: 'center' },
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
      width: 160,
      align: 'center',
      fixed: 'right',
      formatter: row => (
        <>
          <ElButton type="primary" plain size="small" onClick={() => openOperateDrawer('edit', row)}>
            编辑
          </ElButton>
          <ElPopconfirm title="确认删除该凭据？" onConfirm={() => handleDelete(row.id)}>
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

const hasFilter = computed(() =>
  Boolean(searchParams.value.search || searchParams.value.type || searchParams.value.scope)
);

function resetSearchParams() {
  searchParams.value = getInitSearchParams();
  getDataByPage();
}

/** ============ 新增/编辑抽屉 ============ */

type OperateType = 'add' | 'edit';

interface FormModel {
  id?: number;
  name: string;
  type: Api.Cmdb.CredentialType;
  scope: Api.Cmdb.CredentialScope;
  connection_type: Api.Cmdb.CredentialConnectionType;
  username: string;
  default_port: number | null;
  secret_ref: string;
  secret: string;
  is_active: boolean;
}

function createDefaultForm(): FormModel {
  return {
    name: '',
    type: 'ssh_key',
    scope: 'global',
    connection_type: 'ssh',
    username: 'root',
    default_port: null,
    secret_ref: '',
    secret: '',
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
  type: [{ required: true, message: '请选择类型', trigger: 'change' }],
  scope: [{ required: true, message: '请选择作用域', trigger: 'change' }]
};

function openOperateDrawer(type: OperateType, row?: Api.Cmdb.CredentialRefRecord) {
  operateType.value = type;
  formModel.value = row
    ? {
        id: row.id,
        name: row.name,
        type: row.type as Api.Cmdb.CredentialType,
        scope: row.scope as Api.Cmdb.CredentialScope,
        connection_type: row.connection_type as Api.Cmdb.CredentialConnectionType,
        username: row.username,
        default_port: row.default_port,
        secret_ref: row.secret_ref,
        secret: '',
        is_active: row.is_active
      }
    : createDefaultForm();
  drawerVisible.value = true;
}

async function handleSubmit() {
  await formRef.value?.validate();

  submitting.value = true;
  const payload: Api.Cmdb.CredentialRefPayload = {
    name: formModel.value.name,
    type: formModel.value.type,
    scope: formModel.value.scope,
    connection_type: formModel.value.connection_type,
    username: formModel.value.username,
    default_port: formModel.value.default_port,
    secret_ref: formModel.value.secret_ref,
    is_active: formModel.value.is_active
  };
  // secret 仅在填写时提交（编辑留空表示不修改密钥）
  if (formModel.value.secret) {
    payload.secret = formModel.value.secret;
  }
  const { error } =
    operateType.value === 'add'
      ? await fetchAddCredentialRef(payload)
      : await fetchUpdateCredentialRef(formModel.value.id!, payload);
  submitting.value = false;

  if (!error) {
    window.$message?.success(operateType.value === 'add' ? '新增成功' : '修改成功');
    drawerVisible.value = false;
    getData();
  }
}

async function handleDelete(id: number) {
  const { error } = await fetchDeleteCredentialRef(id);

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
        <ElFormItem label="类型">
          <ElSelect v-model="searchParams.type" clearable placeholder="全部" class="w-140px">
            <ElOption v-for="item in typeOptions" :key="item.value" :label="item.label" :value="item.value" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="作用域">
          <ElSelect v-model="searchParams.scope" clearable placeholder="全部" class="w-130px">
            <ElOption v-for="item in scopeOptions" :key="item.value" :label="item.label" :value="item.value" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="关键词">
          <ElInput
            v-model="searchParams.search"
            clearable
            placeholder="名称/用户名/引用"
            class="w-200px"
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
          <p>凭据引用</p>
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
          <ElTableColumn v-for="col in columns" :key="col.prop" v-bind="(col as any)" />
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

    <ElDrawer v-model="drawerVisible" :title="operateType === 'add' ? '新增凭据' : '编辑凭据'" size="440px">
      <ElForm ref="formRef" :model="formModel" :rules="formRules" label-width="90px">
        <ElFormItem label="名称" prop="name">
          <ElInput v-model="formModel.name" placeholder="凭据名称" />
        </ElFormItem>
        <ElFormItem label="类型" prop="type">
          <ElSelect v-model="formModel.type" class="w-full">
            <ElOption v-for="item in typeOptions" :key="item.value" :label="item.label" :value="item.value" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="作用域" prop="scope">
          <ElSelect v-model="formModel.scope" class="w-full">
            <ElOption v-for="item in scopeOptions" :key="item.value" :label="item.label" :value="item.value" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="协议">
          <ElSelect v-model="formModel.connection_type" class="w-full">
            <ElOption label="SSH" value="ssh" />
            <ElOption label="WinRM" value="winrm" />
            <ElOption label="Local" value="local" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="用户名">
          <ElInput v-model="formModel.username" placeholder="连接用户名" />
        </ElFormItem>
        <ElFormItem label="默认端口">
          <ElInputNumber
            v-model="formModel.default_port"
            :min="1"
            :max="65535"
            class="w-full"
            placeholder="留空自动推断"
          />
        </ElFormItem>
        <ElFormItem label="外部引用">
          <ElInput v-model="formModel.secret_ref" placeholder="env:/file: 引用，需在环境白名单或凭据目录内" />
        </ElFormItem>
        <ElFormItem label="密钥明文">
          <ElInput
            v-model="formModel.secret"
            type="password"
            show-password
            :placeholder="operateType === 'edit' ? '留空则不修改密钥' : '密码或 SSH 私钥'"
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
