<script setup lang="tsx">
import { computed, ref } from 'vue';
import {
  fetchAddGateway,
  fetchDeleteGateway,
  fetchGetGatewayList,
  fetchTestGateway,
  fetchUpdateGateway
} from '@/service/api';
import { defaultTransform, useUIPaginatedTable } from '@/hooks/common/table';

defineOptions({ name: 'AutomationResourcesGateway' });

/** ============ 搜索 ============ */

function getInitSearchParams() {
  return { current: 1, size: 10, search: undefined as string | undefined };
}

const searchParams = ref(getInitSearchParams());

/** ============ 列表 ============ */

const authTypeText: Record<string, string> = {
  password: '密码',
  key: '密钥'
};

const testingId = ref<number | null>(null);

const { columns, columnChecks, data, getData, getDataByPage, loading, mobilePagination } = useUIPaginatedTable({
  paginationProps: {
    currentPage: searchParams.value.current,
    pageSize: searchParams.value.size
  },
  api: () =>
    fetchGetGatewayList({
      current: searchParams.value.current,
      size: searchParams.value.size,
      search: searchParams.value.search
    }),
  transform: response => defaultTransform(response),
  onPaginationParamsChange: params => {
    searchParams.value.current = params.currentPage ?? 1;
    searchParams.value.size = params.pageSize ?? 10;
  },
  columns: () => [
    { prop: 'id', label: 'ID', width: 70 },
    { prop: 'name', label: '名称', minWidth: 140, showOverflowTooltip: true },
    { prop: 'address', label: '地址', minWidth: 170, showOverflowTooltip: true },
    { prop: 'cloud', label: '云厂商', width: 100, formatter: row => row.cloud || '-' },
    {
      prop: 'auth_type',
      label: '认证方式',
      width: 100,
      align: 'center',
      formatter: row => authTypeText[row.auth_type] ?? row.auth_type
    },
    { prop: 'username', label: '用户名', width: 120, formatter: row => row.username || '-' },
    {
      prop: 'status',
      label: '状态',
      width: 90,
      align: 'center',
      formatter: row => (
        <ElTag type={row.status === 'normal' ? 'success' : 'danger'}>{row.status === 'normal' ? '正常' : '异常'}</ElTag>
      )
    },
    { prop: 'last_tested_at', label: '最近检测', width: 170, formatter: row => row.last_tested_at || '-' },
    {
      prop: 'operate',
      label: '操作',
      width: 210,
      align: 'center',
      fixed: 'right',
      formatter: row => (
        <>
          <ElButton
            type="success"
            plain
            size="small"
            loading={testingId.value === row.id}
            onClick={() => handleTest(row)}
          >
            测试
          </ElButton>
          <ElButton type="primary" plain size="small" onClick={() => openOperateDrawer('edit', row)}>
            编辑
          </ElButton>
          <ElPopconfirm title="确认删除该网关？" onConfirm={() => handleDelete(row.id)}>
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
  address: string;
  cloud: string;
  auth_type: 'password' | 'key';
  username: string;
  secret: string;
}

function createDefaultForm(): FormModel {
  return {
    name: '',
    address: '',
    cloud: '',
    auth_type: 'password',
    username: '',
    secret: ''
  };
}

const drawerVisible = ref(false);
const operateType = ref<OperateType>('add');
const submitting = ref(false);
const formRef = ref();
const formModel = ref<FormModel>(createDefaultForm());

const formRules = {
  name: [{ required: true, message: '请输入网关名称', trigger: 'blur' }],
  address: [{ required: true, message: '请输入网关地址', trigger: 'blur' }]
};

function openOperateDrawer(type: OperateType, row?: Api.Jobs.GatewayRecord) {
  operateType.value = type;
  formModel.value = row
    ? {
        id: row.id,
        name: row.name,
        address: row.address,
        cloud: row.cloud || '',
        auth_type: row.auth_type,
        username: row.username || '',
        secret: ''
      }
    : createDefaultForm();
  drawerVisible.value = true;
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false);
  if (!valid) return;

  submitting.value = true;
  const payload: Api.Jobs.GatewayPayload = {
    name: formModel.value.name,
    address: formModel.value.address,
    cloud: formModel.value.cloud,
    auth_type: formModel.value.auth_type,
    username: formModel.value.username
  };
  // 密钥/密码留空表示不修改（后端 secret 非必填，空串会覆盖为空，因此仅在填写时提交）
  if (formModel.value.secret) {
    payload.secret = formModel.value.secret;
  }
  const { error } =
    operateType.value === 'add'
      ? await fetchAddGateway(payload)
      : await fetchUpdateGateway(formModel.value.id!, payload);
  submitting.value = false;

  if (!error) {
    window.$notification?.success(operateType.value === 'add' ? '新增成功' : '修改成功');
    drawerVisible.value = false;
    getData();
  }
}

async function handleTest(row: Api.Jobs.GatewayRecord) {
  testingId.value = row.id;
  const { error } = await fetchTestGateway(row.id);
  testingId.value = null;

  if (!error) {
    window.$notification?.success(`网关「${row.name}」连接正常`);
    getData();
  }
}

async function handleDelete(id: number) {
  const { error } = await fetchDeleteGateway(id);

  if (!error) {
    window.$notification?.success('删除成功');
    getData();
  }
}
</script>

<template>
  <div class="min-h-500px flex-col-stretch gap-16px overflow-hidden lt-sm:overflow-auto">
    <SearchPanel @reset="resetSearchParams" @search="getDataByPage">
      <ElForm :model="searchParams" label-width="80px" @submit.prevent="getDataByPage">
        <ElFormItem label="关键词">
          <ElInput v-model="searchParams.search" clearable placeholder="名称或地址" @keyup.enter="getDataByPage()" />
        </ElFormItem>
      </ElForm>
    </SearchPanel>

    <ElCard class="card-wrapper sm:flex-1-hidden">
      <template #header>
        <div class="flex items-center justify-between">
          <p>网关代理</p>
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
              :description="hasFilter ? '没有符合条件的网关代理' : '暂无网关代理'"
              :image-size="80"
            >
              <ElButton v-if="!hasFilter" type="primary" @click="openOperateDrawer('add')">新增网关</ElButton>
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

    <ElDrawer v-model="drawerVisible" :title="operateType === 'add' ? '新增网关' : '编辑网关'" size="440px">
      <ElForm
        ref="formRef"
        :model="formModel"
        :rules="formRules"
        label-width="120px"
        label-suffix="："
        require-asterisk-position="left"
      >
        <ElFormItem label="名称" prop="name">
          <ElInput v-model="formModel.name" placeholder="网关名称" />
        </ElFormItem>
        <ElFormItem prop="address">
          <template #label>
            <FormLabelHelp label="地址" :help="['网关机的 SSH 地址，格式 host:port；', '端口缺省为 22。']" />
          </template>
          <ElInput v-model="formModel.address" placeholder="host:port，端口默认 22" />
        </ElFormItem>
        <ElFormItem>
          <template #label>
            <FormLabelHelp
              label="云厂商"
              :help="['仅作分组与筛选标注，如 aliyun / aws；', '可留空，不影响代理逻辑。']"
            />
          </template>
          <ElInput v-model="formModel.cloud" placeholder="如 aliyun / aws，可留空" />
        </ElFormItem>
        <ElFormItem>
          <template #label>
            <FormLabelHelp
              label="认证方式"
              :help="['密码：下方「密钥/密码」填写 SSH 登录密码；', '密钥：填写对应私钥内容。']"
            />
          </template>
          <ElSelect v-model="formModel.auth_type" class="w-full">
            <ElOption label="密码" value="password" />
            <ElOption label="密钥" value="key" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem>
          <template #label>
            <FormLabelHelp label="用户名" :help="['登录网关机的 SSH 用户名；', '留空默认使用 root。']" />
          </template>
          <ElInput v-model="formModel.username" placeholder="SSH 用户名" />
        </ElFormItem>
        <ElFormItem>
          <template #label>
            <FormLabelHelp
              label="密钥/密码"
              :help="['按认证方式填写 SSH 密码或私钥内容，加密存储；', '编辑时留空表示不修改。']"
            />
          </template>
          <ElInput
            v-model="formModel.secret"
            type="password"
            show-password
            :placeholder="operateType === 'edit' ? '留空表示不修改' : 'SSH 密码或私钥'"
          />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="drawerVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="submitting" @click="handleSubmit">确定</ElButton>
      </template>
    </ElDrawer>
  </div>
</template>
