<script setup lang="tsx">
import { ref } from 'vue';
import {
  fetchAddWorkerPool,
  fetchDeleteWorkerPool,
  fetchGetWorkerPoolList,
  fetchUpdateWorkerPool
} from '@/service/api';
import { defaultTransform, useUIPaginatedTable } from '@/hooks/common/table';

defineOptions({ name: 'CmdbExecution' });

/** ============ 搜索 ============ */

function getInitSearchParams() {
  return { current: 1, size: 10, search: undefined as string | undefined };
}

const searchParams = ref(getInitSearchParams());

/** ============ 列表 ============ */

const executionKindOptions = ['workflow', 'quick_command', 'playbook', 'module'];

const executionKindText: Record<string, string> = {
  workflow: '流程',
  quick_command: '脚本命令',
  playbook: 'Playbook',
  module: 'Ansible 模块'
};

const { columns, columnChecks, data, getData, getDataByPage, loading, mobilePagination } = useUIPaginatedTable({
  paginationProps: {
    currentPage: searchParams.value.current,
    pageSize: searchParams.value.size
  },
  api: () =>
    fetchGetWorkerPoolList({
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
    { prop: 'code', label: '编码', minWidth: 130, showOverflowTooltip: true },
    { prop: 'name', label: '名称', minWidth: 140, showOverflowTooltip: true },
    { prop: 'queueName', label: '队列', minWidth: 150, showOverflowTooltip: true },
    { prop: 'region', label: '地域', width: 110, formatter: row => row.region || '-' },
    {
      prop: 'isDefault',
      label: '默认池',
      width: 90,
      align: 'center',
      formatter: row => (row.isDefault ? <ElTag type="success">默认</ElTag> : '-')
    },
    {
      prop: 'isActive',
      label: '状态',
      width: 90,
      align: 'center',
      formatter: row => <ElTag type={row.isActive ? 'success' : 'info'}>{row.isActive ? '启用' : '停用'}</ElTag>
    },
    { prop: 'concurrencyLimit', label: '并发限制', width: 100, align: 'center', className: 'tabular-nums' },
    {
      prop: 'executionKinds',
      label: '执行类型',
      minWidth: 200,
      formatter: row =>
        (row.executionKinds ?? []).length ? (
          <>
            {(row.executionKinds as string[]).map(kind => (
              <ElTag key={kind} size="small" class="mr-4px">
                {executionKindText[kind] ?? kind}
              </ElTag>
            ))}
          </>
        ) : (
          '-'
        )
    },
    { prop: 'updatedAt', label: '更新时间', width: 170, formatter: row => row.updatedAt || '-' },
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
          <ElPopconfirm title="确认删除该执行节点池？" onConfirm={() => handleDelete(row.id)}>
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

function resetSearchParams() {
  searchParams.value = getInitSearchParams();
  getDataByPage();
}

/** ============ 新增/编辑抽屉 ============ */

type OperateType = 'add' | 'edit';

interface FormModel {
  id?: number;
  code: string;
  name: string;
  queueName: string;
  region: string;
  concurrencyLimit: number;
  executionKinds: string[];
  isDefault: boolean;
  isActive: boolean;
}

function createDefaultForm(): FormModel {
  return {
    code: '',
    name: '',
    queueName: '',
    region: '',
    concurrencyLimit: 10,
    executionKinds: ['workflow'],
    isDefault: false,
    isActive: true
  };
}

const drawerVisible = ref(false);
const operateType = ref<OperateType>('add');
const submitting = ref(false);
const formRef = ref();
const formModel = ref<FormModel>(createDefaultForm());

const formRules = {
  code: [{ required: true, message: '请输入编码', trigger: 'blur' }],
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  queueName: [{ required: true, message: '请输入队列名称', trigger: 'blur' }],
  concurrencyLimit: [{ required: true, message: '并发限制必须大于 0', trigger: 'blur' }]
};

function openOperateDrawer(type: OperateType, row?: Api.Jobs.WorkerPoolRecord) {
  operateType.value = type;
  formModel.value = row
    ? {
        id: row.id,
        code: row.code,
        name: row.name,
        queueName: row.queueName,
        region: row.region ?? '',
        concurrencyLimit: row.concurrencyLimit,
        executionKinds: [...(row.executionKinds ?? [])],
        isDefault: row.isDefault,
        isActive: row.isActive
      }
    : createDefaultForm();
  drawerVisible.value = true;
}

async function handleSubmit() {
  await formRef.value?.validate();

  submitting.value = true;
  const payload: Api.Jobs.WorkerPoolPayload = {
    code: formModel.value.code,
    name: formModel.value.name,
    queueName: formModel.value.queueName,
    region: formModel.value.region.trim(),
    concurrencyLimit: formModel.value.concurrencyLimit,
    executionKinds: formModel.value.executionKinds,
    isDefault: formModel.value.isDefault,
    isActive: formModel.value.isActive
  };
  const { error } =
    operateType.value === 'add'
      ? await fetchAddWorkerPool(payload)
      : await fetchUpdateWorkerPool(formModel.value.id!, payload);
  submitting.value = false;

  if (!error) {
    window.$notification?.success(operateType.value === 'add' ? '新增成功' : '修改成功');
    drawerVisible.value = false;
    getData();
  }
}

async function handleDelete(id: number) {
  const { error } = await fetchDeleteWorkerPool(id);

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
          <ElInput
            v-model="searchParams.search"
            clearable
            placeholder="编码/名称/队列"
            @keyup.enter="getDataByPage()"
          />
        </ElFormItem>
      </ElForm>
    </SearchPanel>

    <ElCard class="card-wrapper sm:flex-1-hidden">
      <template #header>
        <div class="flex flex-wrap items-center justify-between gap-8px">
          <p>执行节点池</p>
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
      <div class="h-[calc(100%-52px)] min-w-0 overflow-x-auto">
        <ElTable v-loading="loading" height="100%" border class="min-w-900px sm:h-full" :data="data" row-key="id">
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
      :title="operateType === 'add' ? '新增执行节点池' : '编辑执行节点池'"
      size="min(680px, 100%)"
    >
      <ElForm
        ref="formRef"
        :model="formModel"
        :rules="formRules"
        label-position="top"
        label-suffix="："
        require-asterisk-position="left"
      >
        <ElFormItem label="编码" prop="code">
          <ElInput v-model="formModel.code" :disabled="operateType === 'edit'" placeholder="如 default" />
        </ElFormItem>
        <ElFormItem label="名称" prop="name">
          <ElInput v-model="formModel.name" placeholder="执行节点池名称" />
        </ElFormItem>
        <ElFormItem prop="queueName">
          <template #label>
            <FormLabelHelp
              label="队列"
              :help="['Celery 队列名，需与 Worker 节点订阅的队列一致', '仅支持字母、数字、点、下划线、连字符']"
            />
          </template>
          <ElInput v-model="formModel.queueName" placeholder="Celery 队列名" />
        </ElFormItem>
        <ElFormItem>
          <template #label>
            <FormLabelHelp
              label="地域"
              :help="['目标主机地域与该池一致时，任务优先路由到此池执行', '留空表示不参与地域就近路由']"
            />
          </template>
          <ElInput v-model="formModel.region" placeholder="如 cn-east-1，留空不参与地域路由" />
        </ElFormItem>
        <ElFormItem prop="concurrencyLimit">
          <template #label>
            <FormLabelHelp label="并发限制" :help="['该池同时执行的任务数上限，超出后任务排队等待']" />
          </template>
          <ElInputNumber v-model="formModel.concurrencyLimit" :min="1" class="w-full" />
        </ElFormItem>
        <ElFormItem>
          <template #label>
            <FormLabelHelp label="执行类型" :help="['该池可承接的任务类型，未勾选的类型不会路由到此池']" />
          </template>
          <ElSelect v-model="formModel.executionKinds" multiple class="w-full">
            <ElOption
              v-for="item in executionKindOptions"
              :key="item"
              :label="executionKindText[item] ?? item"
              :value="item"
            />
          </ElSelect>
        </ElFormItem>
        <ElFormItem>
          <template #label>
            <FormLabelHelp label="默认池" :help="['未指定执行池且无同地域可用池时，任务回退到默认池执行']" />
          </template>
          <ElSwitch v-model="formModel.isDefault" />
        </ElFormItem>
        <ElFormItem label="启用">
          <ElSwitch v-model="formModel.isActive" />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="drawerVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="submitting" @click="handleSubmit">确定</ElButton>
      </template>
    </ElDrawer>
  </div>
</template>
