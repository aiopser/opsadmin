<script setup lang="tsx">
import { ref } from 'vue';
import {
  fetchAddJenkinsServer,
  fetchDeleteJenkinsServer,
  fetchGetJenkinsJobList,
  fetchGetJenkinsServerList,
  fetchSyncJenkinsJobs,
  fetchTestJenkinsServer,
  fetchUpdateJenkinsServer
} from '@/service/api';
import { defaultTransform, useUIPaginatedTable } from '@/hooks/common/table';

defineOptions({ name: 'AutomationJenkinsResource' });

/** ============ 列表 ============ */

const searchParams = ref({ current: 1, size: 10 });

const { columns, columnChecks, data, getData, loading, mobilePagination } = useUIPaginatedTable({
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
      prop: 'baseUrl',
      label: '服务地址',
      minWidth: 220,
      showOverflowTooltip: true,
      formatter: row => <span class="text-12px font-mono">{row.baseUrl}</span>
    },
    { prop: 'username', label: '用户名', width: 120, formatter: row => row.username || '-' },
    {
      prop: 'verifySsl',
      label: 'SSL 校验',
      width: 100,
      align: 'center',
      formatter: row => <ElTag type={row.verifySsl ? 'success' : 'info'}>{row.verifySsl ? '校验' : '跳过'}</ElTag>
    },
    {
      prop: 'isActive',
      label: '状态',
      width: 90,
      align: 'center',
      formatter: row => <ElTag type={row.isActive ? 'success' : 'info'}>{row.isActive ? '启用' : '停用'}</ElTag>
    },
    { prop: 'updatedAt', label: '更新时间', width: 170, formatter: row => row.updatedAt || '-' },
    {
      prop: 'operate',
      label: '操作',
      width: 190,
      align: 'center',
      fixed: 'right',
      formatter: row => (
        <>
          <ElButton type="primary" plain size="small" onClick={() => openOperateDrawer('edit', row)}>
            编辑
          </ElButton>
          <ElButton type="primary" plain size="small" onClick={() => openJobDrawer(row)}>
            Job
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

/** ============ 新增/编辑抽屉 ============ */

type OperateType = 'add' | 'edit';

interface FormModel {
  id?: number;
  name: string;
  baseUrl: string;
  username: string;
  secret: string;
  verifySsl: boolean;
  isActive: boolean;
}

function createDefaultForm(): FormModel {
  return {
    name: '',
    baseUrl: '',
    username: '',
    secret: '',
    verifySsl: true,
    isActive: true
  };
}

const drawerVisible = ref(false);
const operateType = ref<OperateType>('add');
const submitting = ref(false);
const testing = ref(false);
const formRef = ref();
const formModel = ref<FormModel>(createDefaultForm());

const formRules = {
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  baseUrl: [{ required: true, message: '请输入服务地址', trigger: 'blur' }]
};

function openOperateDrawer(type: OperateType, row?: Api.Automation.JenkinsServerRecord) {
  operateType.value = type;
  formModel.value = row
    ? {
        id: row.id,
        name: row.name,
        baseUrl: row.baseUrl,
        username: row.username,
        secret: '',
        verifySsl: row.verifySsl,
        isActive: row.isActive
      }
    : createDefaultForm();
  drawerVisible.value = true;
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false);
  if (!valid) return;

  submitting.value = true;
  const payload: Api.Automation.JenkinsServerPayload = {
    name: formModel.value.name,
    baseUrl: formModel.value.baseUrl,
    username: formModel.value.username,
    verifySsl: formModel.value.verifySsl,
    isActive: formModel.value.isActive
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
    window.$notification?.success(operateType.value === 'add' ? '新增成功' : '修改成功');
    drawerVisible.value = false;
    getData();
  }
}

async function handleTestConnection() {
  const baseUrl = formModel.value.baseUrl.trim();
  if (!baseUrl) {
    formRef.value?.validateField('baseUrl').catch(() => undefined);
    return;
  }
  testing.value = true;
  const { error } = await fetchTestJenkinsServer({
    id: formModel.value.id,
    baseUrl,
    username: formModel.value.username.trim(),
    secret: formModel.value.secret || undefined,
    verifySsl: formModel.value.verifySsl
  });
  testing.value = false;
  if (!error) {
    window.$notification?.success('Jenkins 连接成功', '服务地址可达，用户名与 API Token 认证有效');
  }
}

/** ============ Jenkins 任务抽屉 ============ */

const jobDrawerVisible = ref(false);
const jobLoading = ref(false);
const syncing = ref(false);
const jobRows = ref<Api.Automation.JenkinsJobRecord[]>([]);
const activeServer = ref<{ id: number; name: string } | null>(null);

function openJobDrawer(row: Api.Automation.JenkinsServerRecord) {
  activeServer.value = { id: row.id, name: row.name };
  jobDrawerVisible.value = true;
  loadJobs();
}

async function loadJobs() {
  if (!activeServer.value) return;
  jobLoading.value = true;
  const { data: jobData, error } = await fetchGetJenkinsJobList({
    current: 1,
    size: 200,
    server: activeServer.value.id
  });
  jobLoading.value = false;
  if (!error && jobData) {
    jobRows.value = jobData.records;
  }
}

async function handleSyncJobs() {
  if (!activeServer.value) return;
  syncing.value = true;
  const { data: syncData, error } = await fetchSyncJenkinsJobs(activeServer.value.id);
  syncing.value = false;
  if (!error) {
    window.$notification?.success('同步完成', `已同步 ${syncData?.length ?? 0} 个 Jenkins 任务`);
    await loadJobs();
  }
}

async function handleDelete(id: number) {
  const { error } = await fetchDeleteJenkinsServer(id);

  if (!error) {
    window.$notification?.success('删除成功');
    getData();
  }
}
</script>

<template>
  <div class="min-h-500px flex-col-stretch gap-16px overflow-hidden lt-sm:overflow-auto">
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
          <template #empty>
            <ElEmpty v-if="!loading" description="暂无 Jenkins 服务" :image-size="80">
              <ElButton type="primary" @click="openOperateDrawer('add')">新增 Jenkins 服务</ElButton>
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
      :title="operateType === 'add' ? '新增 Jenkins 服务' : '编辑 Jenkins 服务'"
      size="min(860px, 100%)"
    >
      <ElForm
        ref="formRef"
        :model="formModel"
        :rules="formRules"
        label-width="130px"
        label-suffix="："
        require-asterisk-position="left"
      >
        <ElFormItem label="名称" prop="name">
          <ElInput v-model="formModel.name" placeholder="Jenkins 服务名称" />
        </ElFormItem>
        <ElFormItem prop="baseUrl">
          <template #label>
            <FormLabelHelp
              label="服务地址"
              :help="['Jenkins 服务根地址，如 https://jenkins.example.com；', '用于同步 Job 列表与触发构建。']"
            />
          </template>
          <ElInput v-model="formModel.baseUrl" placeholder="https://jenkins.example.com" />
        </ElFormItem>
        <ElFormItem>
          <template #label>
            <FormLabelHelp label="用户名" :help="['调用 Jenkins API 的认证用户名，与 API Token 配合使用。']" />
          </template>
          <ElInput v-model="formModel.username" placeholder="API 认证用户名" />
        </ElFormItem>
        <ElFormItem>
          <template #label>
            <FormLabelHelp
              label="API Token"
              :help="['Jenkins API Token，加密存储；', '编辑时留空表示不修改原 Token。']"
            />
          </template>
          <ElInput
            v-model="formModel.secret"
            type="password"
            show-password
            :placeholder="operateType === 'edit' ? '留空则不修改 Token' : 'Jenkins API Token'"
          />
        </ElFormItem>
        <ElFormItem>
          <template #label>
            <FormLabelHelp label="校验 SSL" :help="['关闭后跳过 HTTPS 证书校验，仅用于内网自签证书等可信场景。']" />
          </template>
          <ElSwitch v-model="formModel.verifySsl" />
        </ElFormItem>
        <ElFormItem>
          <template #label>
            <FormLabelHelp label="启用" :help="['停用后其下 Job 的流程节点将无法通过发布校验。']" />
          </template>
          <ElSwitch v-model="formModel.isActive" />
        </ElFormItem>
        <ElFormItem>
          <template #label>
            <FormLabelHelp
              label="测试连接"
              :help="['用当前表单填写的地址与 Token 发起一次真实请求；编辑时 Token 留空则使用已保存的 Token。']"
            />
          </template>
          <ElButton :loading="testing" @click="handleTestConnection">测试连接</ElButton>
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="drawerVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="submitting" @click="handleSubmit">确定</ElButton>
      </template>
    </ElDrawer>

    <ElDrawer v-model="jobDrawerVisible" :title="`Jenkins 任务 - ${activeServer?.name ?? ''}`" size="62%">
      <div class="mb-12px flex items-center justify-between gap-12px">
        <span class="text-13px text-[var(--el-text-color-secondary)]">
          任务列表从 Jenkins 同步而来，流程编排的 Jenkins 步骤从这里选择。
        </span>
        <ElButton type="primary" :loading="syncing" @click="handleSyncJobs">同步 Job</ElButton>
      </div>
      <ElTable v-loading="jobLoading" :data="jobRows" border max-height="calc(100vh - 220px)">
        <ElTableColumn prop="name" label="任务名" min-width="240" show-overflow-tooltip />
        <ElTableColumn label="Jenkins 链接" min-width="120">
          <template #default="{ row }">
            <ElLink v-if="row.url" type="primary" :href="row.url" target="_blank" rel="noopener noreferrer">
              打开
            </ElLink>
            <span v-else>-</span>
          </template>
        </ElTableColumn>
        <ElTableColumn label="状态" width="90" align="center">
          <template #default="{ row }">
            <ElTag :type="row.isActive ? 'success' : 'info'" size="small">
              {{ row.isActive ? '启用' : '停用' }}
            </ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn prop="lastSyncedAt" label="最近同步" width="170">
          <template #default="{ row }">{{ row.lastSyncedAt || '-' }}</template>
        </ElTableColumn>
        <template #empty>
          <ElEmpty v-if="!jobLoading" description="暂无任务，点击右上角「同步 Job」从 Jenkins 拉取" :image-size="80" />
        </template>
      </ElTable>
    </ElDrawer>
  </div>
</template>
