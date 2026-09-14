<script setup lang="tsx">
import { computed, ref } from 'vue';
import {
  fetchAddJenkinsServer,
  fetchDeleteJenkinsServer,
  fetchGetJenkinsServerList,
  fetchUpdateJenkinsServer
} from '@/service/api';
import { defaultTransform, useUIPaginatedTable } from '@/hooks/common/table';

defineOptions({ name: 'AutomationJenkinsResource' });

/** ============ 搜索 ============ */

function getInitSearchParams() {
  return { current: 1, size: 10, search: undefined as string | undefined };
}

const searchParams = ref(getInitSearchParams());

/** ============ 列表 ============ */

const { columns, columnChecks, data, getData, getDataByPage, loading, mobilePagination } = useUIPaginatedTable({
  paginationProps: {
    currentPage: searchParams.value.current,
    pageSize: searchParams.value.size
  },
  api: () => fetchGetJenkinsServerList(searchParams.value),
  transform: response => defaultTransform(response),
  onPaginationParamsChange: params => {
    searchParams.value.current = params.currentPage ?? 1;
    searchParams.value.size = params.pageSize ?? 10;
  },
  columns: () => [
    { prop: 'id', label: 'ID', width: 70 },
    { prop: 'name', label: '名称', minWidth: 150, showOverflowTooltip: true },
    {
      prop: 'base_url',
      label: '服务地址',
      minWidth: 220,
      showOverflowTooltip: true,
      formatter: row => <span class="text-12px font-mono">{row.base_url}</span>
    },
    { prop: 'username', label: '用户名', width: 120, formatter: row => row.username || '-' },
    {
      prop: 'verify_ssl',
      label: 'SSL 校验',
      width: 100,
      align: 'center',
      formatter: row => <ElTag type={row.verify_ssl ? 'success' : 'info'}>{row.verify_ssl ? '校验' : '跳过'}</ElTag>
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
          <ElPopconfirm title="确认删除该 Jenkins 服务？" onConfirm={() => handleDelete(row.id)}>
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
  base_url: string;
  username: string;
  secret: string;
  verify_ssl: boolean;
  is_active: boolean;
}

function createDefaultForm(): FormModel {
  return {
    name: '',
    base_url: '',
    username: '',
    secret: '',
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
  base_url: [{ required: true, message: '请输入服务地址', trigger: 'blur' }]
};

function openOperateDrawer(type: OperateType, row?: Api.Automation.JenkinsServerRecord) {
  operateType.value = type;
  formModel.value = row
    ? {
        id: row.id,
        name: row.name,
        base_url: row.base_url,
        username: row.username,
        secret: '',
        verify_ssl: row.verify_ssl,
        is_active: row.is_active
      }
    : createDefaultForm();
  drawerVisible.value = true;
}

async function handleSubmit() {
  await formRef.value?.validate();

  submitting.value = true;
  const payload: Api.Automation.JenkinsServerPayload = {
    name: formModel.value.name,
    base_url: formModel.value.base_url,
    username: formModel.value.username,
    verify_ssl: formModel.value.verify_ssl,
    is_active: formModel.value.is_active
  };
  // secret 仅在填写时提交（编辑留空表示不修改 API Token）
  if (formModel.value.secret) {
    payload.secret = formModel.value.secret;
  }
  const { error } =
    operateType.value === 'add'
      ? await fetchAddJenkinsServer(payload)
      : await fetchUpdateJenkinsServer(formModel.value.id!, payload);
  submitting.value = false;

  if (!error) {
    window.$message?.success(operateType.value === 'add' ? '新增成功' : '修改成功');
    drawerVisible.value = false;
    getData();
  }
}

async function handleDelete(id: number) {
  const { error } = await fetchDeleteJenkinsServer(id);

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
            placeholder="名称/地址/用户名"
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
          <p>Jenkins 服务</p>
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

    <ElDrawer
      v-model="drawerVisible"
      :title="operateType === 'add' ? '新增 Jenkins 服务' : '编辑 Jenkins 服务'"
      size="440px"
    >
      <ElForm ref="formRef" :model="formModel" :rules="formRules" label-width="100px">
        <ElFormItem label="名称" prop="name">
          <ElInput v-model="formModel.name" placeholder="Jenkins 服务名称" />
        </ElFormItem>
        <ElFormItem label="服务地址" prop="base_url">
          <ElInput v-model="formModel.base_url" placeholder="https://jenkins.example.com" />
        </ElFormItem>
        <ElFormItem label="用户名">
          <ElInput v-model="formModel.username" placeholder="API 认证用户名" />
        </ElFormItem>
        <ElFormItem label="API Token">
          <ElInput
            v-model="formModel.secret"
            type="password"
            show-password
            :placeholder="operateType === 'edit' ? '留空则不修改 Token' : 'Jenkins API Token'"
          />
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
