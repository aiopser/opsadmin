<script setup lang="tsx">
import { computed, ref } from 'vue';
import { fetchAddTag, fetchDeleteTag, fetchGetTagList, fetchUpdateTag } from '@/service/api';
import { defaultTransform, useUIPaginatedTable } from '@/hooks/common/table';

defineOptions({ name: 'CmdbTagTab' });

/** ============ 搜索 ============ */

function getInitSearchParams() {
  return {
    current: 1,
    size: 10,
    key: undefined as string | undefined,
    value: undefined as string | undefined
  };
}

const searchParams = ref(getInitSearchParams());

/** ============ 列表 ============ */

const { columns, columnChecks, data, getData, getDataByPage, loading, mobilePagination } = useUIPaginatedTable({
  paginationProps: {
    currentPage: searchParams.value.current,
    pageSize: searchParams.value.size
  },
  api: () => fetchGetTagList(searchParams.value),
  transform: response => defaultTransform(response),
  onPaginationParamsChange: params => {
    searchParams.value.current = params.currentPage ?? 1;
    searchParams.value.size = params.pageSize ?? 10;
  },
  columns: () => [
    { prop: 'id', label: 'ID', width: 70 },
    {
      prop: 'key',
      label: '标签键',
      width: 160,
      formatter: row => <span class="font-mono">{row.key}</span>
    },
    {
      prop: 'value',
      label: '标签值',
      minWidth: 180,
      showOverflowTooltip: true,
      formatter: row => <span class="font-mono">{row.value}</span>
    },
    { prop: 'created_at', label: '创建时间', width: 170, formatter: row => row.created_at || '-' },
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
          <ElPopconfirm title="确认删除该标签？" onConfirm={() => handleDelete(row.id)}>
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

const hasFilter = computed(() => Boolean(searchParams.value.key || searchParams.value.value));

function resetSearchParams() {
  searchParams.value = getInitSearchParams();
  getDataByPage();
}

/** ============ 新增/编辑抽屉 ============ */

type OperateType = 'add' | 'edit';

interface TagForm {
  id?: number;
  key: string;
  value: string;
}

const drawerVisible = ref(false);
const operateType = ref<OperateType>('add');
const submitting = ref(false);
const formRef = ref();
const formModel = ref<TagForm>({ key: '', value: '' });

const formRules = {
  key: [{ required: true, message: '请输入标签键', trigger: 'blur' }],
  value: [{ required: true, message: '请输入标签值', trigger: 'blur' }]
};

function openOperateDrawer(type: OperateType, row?: Api.Cmdb.HostTagRecord) {
  operateType.value = type;
  formModel.value = row ? { id: row.id, key: row.key, value: row.value } : { key: '', value: '' };
  drawerVisible.value = true;
}

async function handleSubmit() {
  await formRef.value?.validate();

  submitting.value = true;
  const { error } =
    operateType.value === 'add'
      ? await fetchAddTag(formModel.value)
      : await fetchUpdateTag(formModel.value.id!, formModel.value);
  submitting.value = false;

  if (!error) {
    window.$message?.success(operateType.value === 'add' ? '新增成功' : '修改成功');
    drawerVisible.value = false;
    getData();
  }
}

async function handleDelete(id: number) {
  const { error } = await fetchDeleteTag(id);

  if (!error) {
    window.$message?.success('删除成功');
    getData();
  }
}
</script>

<template>
  <div class="flex-col-stretch gap-12px">
    <ElForm :model="searchParams" label-width="60px" inline @submit.prevent>
      <ElFormItem label="键">
        <ElInput
          v-model="searchParams.key"
          clearable
          placeholder="标签键"
          class="w-180px"
          @keyup.enter="getDataByPage()"
        />
      </ElFormItem>
      <ElFormItem label="值">
        <ElInput
          v-model="searchParams.value"
          clearable
          placeholder="标签值"
          class="w-180px"
          @keyup.enter="getDataByPage()"
        />
      </ElFormItem>
      <ElFormItem>
        <ElButton type="primary" @click="getDataByPage()">查询</ElButton>
        <ElButton :disabled="!hasFilter" @click="resetSearchParams">重置</ElButton>
      </ElFormItem>
    </ElForm>

    <div class="flex items-center justify-between">
      <p class="font-medium">主机标签</p>
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

    <ElTable v-loading="loading" height="520px" border :data="data" row-key="id">
      <ElTableColumn v-for="col in columns" :key="col.prop" v-bind="col" />
    </ElTable>

    <div class="flex justify-end">
      <ElPagination
        v-if="mobilePagination.total"
        layout="total,prev,pager,next,sizes"
        v-bind="mobilePagination"
        @current-change="mobilePagination['current-change']"
        @size-change="mobilePagination['size-change']"
      />
    </div>

    <ElDrawer v-model="drawerVisible" :title="operateType === 'add' ? '新增标签' : '编辑标签'" size="400px">
      <ElForm ref="formRef" :model="formModel" :rules="formRules" label-width="70px">
        <ElFormItem label="标签键" prop="key">
          <ElInput v-model="formModel.key" placeholder="如 env / role / app" />
        </ElFormItem>
        <ElFormItem label="标签值" prop="value">
          <ElInput v-model="formModel.value" placeholder="如 prod / web / order" />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="drawerVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="submitting" @click="handleSubmit">确认</ElButton>
      </template>
    </ElDrawer>
  </div>
</template>

<style scoped></style>
