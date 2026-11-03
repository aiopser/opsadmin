<script setup lang="tsx">
import { computed, ref } from 'vue';
import {
  fetchAddGitRepository,
  fetchDeleteGitRepository,
  fetchGetGitRepositoryList,
  fetchUpdateGitRepository
} from '@/service/api';
import { defaultTransform, useUIPaginatedTable } from '@/hooks/common/table';

defineOptions({ name: 'AutomationGitResource' });

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
  api: () => fetchGetGitRepositoryList(searchParams.value),
  transform: response => defaultTransform(response),
  onPaginationParamsChange: params => {
    searchParams.value.current = params.currentPage ?? 1;
    searchParams.value.size = params.pageSize ?? 10;
  },
  columns: () => [
    { prop: 'id', label: 'ID', width: 70 },
    { prop: 'name', label: '名称', minWidth: 140, showOverflowTooltip: true },
    {
      prop: 'repoUrl',
      label: '仓库地址',
      minWidth: 260,
      showOverflowTooltip: true,
      formatter: row => <span class="text-12px font-mono">{row.repoUrl}</span>
    },
    { prop: 'branch', label: '默认分支', width: 110, formatter: row => row.branch || '-' },
    { prop: 'username', label: '令牌用户名', width: 110, formatter: row => row.username || '-' },
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
      width: 150,
      align: 'center',
      fixed: 'right',
      formatter: row => (
        <>
          <ElButton type="primary" plain size="small" onClick={() => openOperateDrawer('edit', row)}>
            编辑
          </ElButton>
          <ElPopconfirm title="确认删除该 Git 仓库？" onConfirm={() => handleDelete(row.id)}>
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
  repoUrl: string;
  username: string;
  branch: string;
  secret: string;
  verifySsl: boolean;
  isActive: boolean;
}

function createDefaultForm(): FormModel {
  return {
    name: '',
    repoUrl: '',
    username: '',
    branch: 'main',
    secret: '',
    verifySsl: true,
    isActive: true
  };
}

const drawerVisible = ref(false);
const operateType = ref<OperateType>('add');
const submitting = ref(false);
const formRef = ref();
const formModel = ref<FormModel>(createDefaultForm());

const formRules = {
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  repoUrl: [{ required: true, message: '请输入仓库地址', trigger: 'blur' }]
};

function openOperateDrawer(type: OperateType, row?: Api.Automation.GitRepositoryRecord) {
  operateType.value = type;
  formModel.value = row
    ? {
        id: row.id,
        name: row.name,
        repoUrl: row.repoUrl,
        username: row.username,
        branch: row.branch,
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
  const payload: Api.Automation.GitRepositoryPayload = {
    name: formModel.value.name,
    repoUrl: formModel.value.repoUrl,
    username: formModel.value.username,
    branch: formModel.value.branch,
    verifySsl: formModel.value.verifySsl,
    isActive: formModel.value.isActive
  };
  // secret 仅在填写时提交（编辑留空表示不修改访问令牌）
  if (formModel.value.secret) {
    payload.secret = formModel.value.secret;
  }
  const { error } =
    operateType.value === 'add'
      ? await fetchAddGitRepository(payload)
      : await fetchUpdateGitRepository(formModel.value.id!, payload);
  submitting.value = false;

  if (!error) {
    window.$notification?.success(operateType.value === 'add' ? '新增成功' : '修改成功');
    drawerVisible.value = false;
    getData();
  }
}

async function handleDelete(id: number) {
  const { error } = await fetchDeleteGitRepository(id);

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
            placeholder="名称/地址/用户名"
            @keyup.enter="getDataByPage()"
          />
        </ElFormItem>
      </ElForm>
    </SearchPanel>

    <ElCard class="card-wrapper sm:flex-1-hidden">
      <template #header>
        <div class="flex items-center justify-between">
          <p>Git 仓库</p>
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
              :description="hasFilter ? '没有符合条件的 Git 仓库' : '暂无 Git 仓库'"
              :image-size="80"
            >
              <ElButton v-if="!hasFilter" type="primary" @click="openOperateDrawer('add')">新增 Git 仓库</ElButton>
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
      :title="operateType === 'add' ? '新增 Git 仓库' : '编辑 Git 仓库'"
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
          <ElInput v-model="formModel.name" placeholder="Git 仓库名称" />
        </ElFormItem>
        <ElFormItem prop="repoUrl">
          <template #label>
            <FormLabelHelp
              label="仓库地址"
              :help="['Git 仓库完整地址，仅支持 http(s) 协议；', '用于在新建脚本 / Playbook 时加载仓库文件。']"
            />
          </template>
          <ElInput v-model="formModel.repoUrl" placeholder="https://gitlab.example.com/group/repo.git" />
        </ElFormItem>
        <ElFormItem>
          <template #label>
            <FormLabelHelp
              label="令牌用户名"
              :help="['私有令牌的用户名，GitLab 常用 oauth2；', '留空则令牌直接作为用户名嵌入地址。']"
            />
          </template>
          <ElInput v-model="formModel.username" placeholder="GitLab 常用 oauth2，GitHub 可留空" />
        </ElFormItem>
        <ElFormItem>
          <template #label>
            <FormLabelHelp
              label="默认分支"
              :help="['加载仓库文件时默认使用的分支或标签；', '加载时可按需切换到其他分支 / 标签。']"
            />
          </template>
          <ElInput v-model="formModel.branch" placeholder="main" />
        </ElFormItem>
        <ElFormItem>
          <template #label>
            <FormLabelHelp
              label="访问令牌"
              :help="['私有仓库的访问令牌，加密存储；', '编辑时留空表示不修改原有令牌。']"
            />
          </template>
          <ElInput
            v-model="formModel.secret"
            type="password"
            show-password
            :placeholder="operateType === 'edit' ? '留空则不修改令牌' : '私有仓库访问令牌'"
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
            <FormLabelHelp label="启用" :help="['停用后将不能作为脚本 / Playbook 的内容来源。']" />
          </template>
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
