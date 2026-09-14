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
      prop: 'network',
      label: '网段 (CIDR)',
      minWidth: 220,
      formatter: row =>
        String(row.network || '')
          .split(',')
          .filter((item: string) => item.trim()).length ? (
          <>
            {String(row.network)
              .split(',')
              .filter((item: string) => item.trim())
              .map((item: string) => (
                <ElTag key={item} size="small" class="mr-4px">
                  {item.trim()}
                </ElTag>
              ))}
          </>
        ) : (
          '-'
        )
    },
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
  network: string;
  auth_type: 'password' | 'key';
  username: string;
  secret: string;
}

function createDefaultForm(): FormModel {
  return {
    name: '',
    address: '',
    cloud: '',
    network: '',
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
        network: row.network || '',
        auth_type: row.auth_type,
        username: row.username || '',
        secret: ''
      }
    : createDefaultForm();
  drawerVisible.value = true;
}

async function handleSubmit() {
  await formRef.value?.validate();

  submitting.value = true;
  const payload: Api.Jobs.GatewayPayload = {
    name: formModel.value.name,
    address: formModel.value.address,
    cloud: formModel.value.cloud,
    network: formModel.value.network.trim(),
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
    window.$message?.success(operateType.value === 'add' ? '新增成功' : '修改成功');
    drawerVisible.value = false;
    getData();
  }
}

async function handleTest(row: Api.Jobs.GatewayRecord) {
  testingId.value = row.id;
  const { error } = await fetchTestGateway(row.id);
  testingId.value = null;

  if (!error) {
    window.$message?.success(`网关「${row.name}」连接正常`);
    getData();
  }
}

async function handleDelete(id: number) {
  const { error } = await fetchDeleteGateway(id);

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
            placeholder="名称/地址/网段"
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

    <ElDrawer v-model="drawerVisible" :title="operateType === 'add' ? '新增网关' : '编辑网关'" size="440px">
      <ElForm ref="formRef" :model="formModel" :rules="formRules" label-width="90px">
        <ElFormItem label="名称" prop="name">
          <ElInput v-model="formModel.name" placeholder="网关名称" />
        </ElFormItem>
        <ElFormItem label="地址" prop="address">
          <ElInput v-model="formModel.address" placeholder="host:port，端口默认 22" />
        </ElFormItem>
        <ElFormItem label="云厂商">
          <ElInput v-model="formModel.cloud" placeholder="如 aliyun / aws，可留空" />
        </ElFormItem>
        <ElFormItem label="网段">
          <ElInput
            v-model="formModel.network"
            type="textarea"
            :rows="2"
            placeholder="逗号分隔的 CIDR，如 10.0.0.0/8,172.16.0.0/12；目标主机 IP 命中时自动经此网关代理"
          />
        </ElFormItem>
        <ElFormItem label="认证方式">
          <ElSelect v-model="formModel.auth_type" class="w-full">
            <ElOption label="密码" value="password" />
            <ElOption label="密钥" value="key" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="用户名">
          <ElInput v-model="formModel.username" placeholder="SSH 用户名" />
        </ElFormItem>
        <ElFormItem label="密钥/密码">
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
