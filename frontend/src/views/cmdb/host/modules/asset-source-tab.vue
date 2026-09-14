<script setup lang="tsx">
import { computed, ref } from 'vue';
import {
  fetchAddAssetSource,
  fetchDeleteAssetSource,
  fetchGetAssetSourceList,
  fetchSyncAssetSource,
  fetchUpdateAssetSource
} from '@/service/api';
import { defaultTransform, useUIPaginatedTable } from '@/hooks/common/table';

defineOptions({ name: 'CmdbAssetSourceTab' });

/** ============ 枚举文案 ============ */

const sourceTypeOptions = [
  { value: 'manual', label: '手工维护' },
  { value: 'cloud', label: '云平台' },
  { value: 'external_cmdb', label: '外部 CMDB' }
];
const sourceTypeText: Record<string, string> = Object.fromEntries(
  sourceTypeOptions.map(item => [item.value, item.label])
);

const sourceTypeTagType: Record<string, UI.ThemeColor> = {
  manual: 'info',
  cloud: 'primary',
  external_cmdb: 'warning'
};

/** ============ 搜索 ============ */

function getInitSearchParams() {
  return {
    current: 1,
    size: 10,
    search: undefined as string | undefined,
    sourceType: undefined as Api.Cmdb.AssetSourceType | undefined
  };
}

const searchParams = ref(getInitSearchParams());

/** ============ 列表 ============ */

const { columns, columnChecks, data, getData, getDataByPage, loading, mobilePagination } = useUIPaginatedTable({
  paginationProps: {
    currentPage: searchParams.value.current,
    pageSize: searchParams.value.size
  },
  api: () => fetchGetAssetSourceList(searchParams.value),
  transform: response => defaultTransform(response),
  onPaginationParamsChange: params => {
    searchParams.value.current = params.currentPage ?? 1;
    searchParams.value.size = params.pageSize ?? 10;
  },
  columns: () => [
    { prop: 'id', label: 'ID', width: 70 },
    {
      prop: 'code',
      label: '来源编码',
      width: 150,
      formatter: row => <span class="font-mono">{row.code}</span>
    },
    { prop: 'name', label: '来源名称', minWidth: 140, showOverflowTooltip: true },
    {
      prop: 'source_type',
      label: '来源类型',
      width: 110,
      align: 'center',
      formatter: row => (
        <ElTag type={sourceTypeTagType[row.source_type] ?? 'info'}>
          {sourceTypeText[row.source_type] ?? row.source_type}
        </ElTag>
      )
    },
    {
      prop: 'endpoint',
      label: '接入端点',
      minWidth: 160,
      showOverflowTooltip: true,
      formatter: row => row.endpoint || '-'
    },
    {
      prop: 'is_active',
      label: '状态',
      width: 80,
      align: 'center',
      formatter: row => <ElTag type={row.is_active ? 'success' : 'info'}>{row.is_active ? '启用' : '停用'}</ElTag>
    },
    { prop: 'last_synced_at', label: '最近同步', width: 170, formatter: row => row.last_synced_at || '-' },
    { prop: 'updated_at', label: '更新时间', width: 170, formatter: row => row.updated_at || '-' },
    {
      prop: 'operate',
      label: '操作',
      width: 220,
      align: 'center',
      fixed: 'right',
      formatter: row => (
        <>
          <ElButton type="success" plain size="small" onClick={() => openSyncDialog(row)}>
            同步
          </ElButton>
          <ElButton type="primary" plain size="small" onClick={() => openOperateDrawer('edit', row)}>
            编辑
          </ElButton>
          <ElPopconfirm title="确认删除该来源？" onConfirm={() => handleDelete(row.id)}>
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

const hasFilter = computed(() => Boolean(searchParams.value.search || searchParams.value.sourceType));

function resetSearchParams() {
  searchParams.value = getInitSearchParams();
  getDataByPage();
}

/** ============ 新增/编辑抽屉 ============ */

type OperateType = 'add' | 'edit';

interface SourceForm {
  id?: number;
  code: string;
  name: string;
  source_type: Api.Cmdb.AssetSourceType;
  endpoint: string;
  description: string;
  is_active: boolean;
}

function createDefaultForm(): SourceForm {
  return { code: '', name: '', source_type: 'manual', endpoint: '', description: '', is_active: true };
}

const drawerVisible = ref(false);
const operateType = ref<OperateType>('add');
const submitting = ref(false);
const formRef = ref();
const formModel = ref<SourceForm>(createDefaultForm());

const formRules = {
  code: [{ required: true, message: '请输入来源编码', trigger: 'blur' }],
  name: [{ required: true, message: '请输入来源名称', trigger: 'blur' }],
  source_type: [{ required: true, message: '请选择来源类型', trigger: 'change' }]
};

function openOperateDrawer(type: OperateType, row?: Api.Cmdb.AssetSourceRecord) {
  operateType.value = type;
  formModel.value = row
    ? {
        id: row.id,
        code: row.code,
        name: row.name,
        source_type: (row.source_type as Api.Cmdb.AssetSourceType) || 'manual',
        endpoint: row.endpoint,
        description: row.description,
        is_active: row.is_active
      }
    : createDefaultForm();
  drawerVisible.value = true;
}

async function handleSubmit() {
  await formRef.value?.validate();

  submitting.value = true;
  const { error } =
    operateType.value === 'add'
      ? await fetchAddAssetSource(formModel.value)
      : await fetchUpdateAssetSource(formModel.value.id!, formModel.value);
  submitting.value = false;

  if (!error) {
    window.$message?.success(operateType.value === 'add' ? '新增成功' : '修改成功');
    drawerVisible.value = false;
    getData();
  }
}

async function handleDelete(id: number) {
  const { error } = await fetchDeleteAssetSource(id);

  if (!error) {
    window.$message?.success('删除成功');
    getData();
  }
}

/** ============ 触发同步 ============ */

const syncVisible = ref(false);
const syncSource = ref<Api.Cmdb.AssetSourceRecord | null>(null);
const syncing = ref(false);
const syncAssetsText = ref('');

const DEFAULT_SYNC_ASSETS = `[
  {
    "hostname": "web-01",
    "primary_ip": "10.0.0.11",
    "os_family": "linux",
    "environment": "prod",
    "app_code": "order",
    "owner_team": "运维部"
  }
]`;

function openSyncDialog(row: Api.Cmdb.AssetSourceRecord) {
  syncSource.value = row;
  syncAssetsText.value = DEFAULT_SYNC_ASSETS;
  syncVisible.value = true;
}

async function handleSync() {
  if (!syncSource.value) return;

  let assets: unknown;
  try {
    assets = JSON.parse(syncAssetsText.value);
  } catch {
    window.$message?.error('资产清单必须是合法 JSON');
    return;
  }
  if (!Array.isArray(assets)) {
    window.$message?.error('资产清单必须是 JSON 数组');
    return;
  }

  syncing.value = true;
  const { error, data: record } = await fetchSyncAssetSource(
    syncSource.value.id,
    assets as Array<Record<string, unknown>>
  );
  syncing.value = false;

  if (!error) {
    window.$message?.success(`同步任务已提交（记录 #${record.id}，状态：${record.status}）`);
    syncVisible.value = false;
    getData();
  }
}
</script>

<template>
  <div class="flex-col-stretch gap-12px">
    <ElForm :model="searchParams" label-width="70px" inline @submit.prevent>
      <ElFormItem label="来源类型">
        <ElSelect v-model="searchParams.sourceType" clearable placeholder="全部" class="w-140px">
          <ElOption v-for="item in sourceTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
        </ElSelect>
      </ElFormItem>
      <ElFormItem label="关键词">
        <ElInput
          v-model="searchParams.search"
          clearable
          placeholder="编码/名称/端点/描述"
          class="w-200px"
          @keyup.enter="getDataByPage()"
        />
      </ElFormItem>
      <ElFormItem>
        <ElButton type="primary" @click="getDataByPage()">查询</ElButton>
        <ElButton :disabled="!hasFilter" @click="resetSearchParams">重置</ElButton>
      </ElFormItem>
    </ElForm>

    <div class="flex items-center justify-between">
      <p class="font-medium">资产来源</p>
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

    <ElDrawer v-model="drawerVisible" :title="operateType === 'add' ? '新增来源' : '编辑来源'" size="440px">
      <ElForm ref="formRef" :model="formModel" :rules="formRules" label-width="80px">
        <ElFormItem label="来源编码" prop="code">
          <ElInput v-model="formModel.code" placeholder="如 aliyun-prod" />
        </ElFormItem>
        <ElFormItem label="来源名称" prop="name">
          <ElInput v-model="formModel.name" placeholder="如 阿里云生产环境" />
        </ElFormItem>
        <ElFormItem label="来源类型" prop="source_type">
          <ElSelect v-model="formModel.source_type" class="w-full">
            <ElOption v-for="item in sourceTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="接入端点">
          <ElInput v-model="formModel.endpoint" placeholder="API 地址（可选）" />
        </ElFormItem>
        <ElFormItem label="描述">
          <ElInput v-model="formModel.description" type="textarea" :rows="3" placeholder="来源描述" />
        </ElFormItem>
        <ElFormItem label="启用">
          <ElSwitch v-model="formModel.is_active" />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="drawerVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="submitting" @click="handleSubmit">确认</ElButton>
      </template>
    </ElDrawer>

    <ElDialog
      v-model="syncVisible"
      :title="`同步资产：${syncSource?.name ?? ''}`"
      width="560px"
      :close-on-click-modal="false"
    >
      <p class="mb-8px text-13px">
        提交资产清单（JSON 数组），后端异步任务将按 hostname + primary_ip / source_id
        增量更新主机，可在“同步记录”页签查看结果。
      </p>
      <ElInput v-model="syncAssetsText" type="textarea" :rows="12" class="font-mono" />
      <template #footer>
        <ElButton @click="syncVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="syncing" @click="handleSync">提交同步</ElButton>
      </template>
    </ElDialog>
  </div>
</template>

<style scoped></style>
