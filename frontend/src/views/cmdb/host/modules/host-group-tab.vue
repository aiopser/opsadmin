<script setup lang="tsx">
import { computed, onMounted, ref } from 'vue';
import {
  fetchAddHostGroup,
  fetchDeleteHostGroup,
  fetchGetHostGroupList,
  fetchGetHostGroupMembers,
  fetchGetHostList,
  fetchUpdateHostGroup,
  fetchUpdateHostGroupMembers
} from '@/service/api';
import { defaultTransform, useUIPaginatedTable } from '@/hooks/common/table';

defineOptions({ name: 'CmdbHostGroupTab' });

/** ============ 枚举文案 ============ */

const groupTypeOptions = [
  { value: 'static', label: '静态分组' },
  { value: 'dynamic', label: '动态分组' }
];
const groupTypeText: Record<string, string> = Object.fromEntries(
  groupTypeOptions.map(item => [item.value, item.label])
);

const groupTypeTagType: Record<string, UI.ThemeColor> = {
  static: 'primary',
  dynamic: 'warning'
};

/** ============ 搜索 ============ */

function getInitSearchParams() {
  return {
    current: 1,
    size: 10,
    search: undefined as string | undefined,
    groupType: undefined as Api.Cmdb.HostGroupType | undefined
  };
}

const searchParams = ref(getInitSearchParams());

/** ============ 列表 ============ */

/** 分组 ID → 名称映射（父分组列显示用） */
const groupNameMap = ref<Map<number, string>>(new Map());

const { columns, columnChecks, data, getData, getDataByPage, loading, mobilePagination } = useUIPaginatedTable({
  paginationProps: {
    currentPage: searchParams.value.current,
    pageSize: searchParams.value.size
  },
  api: () => fetchGetHostGroupList(searchParams.value),
  transform: response => defaultTransform(response),
  onPaginationParamsChange: params => {
    searchParams.value.current = params.currentPage ?? 1;
    searchParams.value.size = params.pageSize ?? 10;
  },
  columns: () => [
    { prop: 'id', label: 'ID', width: 70 },
    { prop: 'name', label: '分组名称', minWidth: 150, showOverflowTooltip: true },
    {
      prop: 'parent',
      label: '上级分组',
      width: 130,
      showOverflowTooltip: true,
      formatter: row => (row.parent ? (groupNameMap.value.get(row.parent) ?? `#${row.parent}`) : '-')
    },
    { prop: 'hostCount', label: '主机数', width: 90, align: 'center' },
    {
      prop: 'group_type',
      label: '分组类型',
      width: 100,
      align: 'center',
      formatter: row => (
        <ElTag type={groupTypeTagType[row.group_type] ?? 'info'}>
          {groupTypeText[row.group_type] ?? row.group_type}
        </ElTag>
      )
    },
    {
      prop: 'is_active',
      label: '状态',
      width: 80,
      align: 'center',
      formatter: row => <ElTag type={row.is_active ? 'success' : 'info'}>{row.is_active ? '启用' : '停用'}</ElTag>
    },
    {
      prop: 'description',
      label: '描述',
      minWidth: 160,
      showOverflowTooltip: true,
      formatter: row => row.description || '-'
    },
    { prop: 'updated_at', label: '更新时间', width: 170, formatter: row => row.updated_at || '-' },
    {
      prop: 'operate',
      label: '操作',
      width: 220,
      align: 'center',
      fixed: 'right',
      formatter: row => (
        <>
          {row.group_type === 'static' ? (
            <ElButton type="success" plain size="small" onClick={() => openMembersDialog(row)}>
              成员
            </ElButton>
          ) : null}
          <ElButton type="primary" plain size="small" onClick={() => openOperateDrawer('edit', row)}>
            编辑
          </ElButton>
          <ElPopconfirm title="确认删除该分组？" onConfirm={() => handleDelete(row.id)}>
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

const hasFilter = computed(() => Boolean(searchParams.value.search || searchParams.value.groupType));

function resetSearchParams() {
  searchParams.value = getInitSearchParams();
  getDataByPage();
}

/** 父分组选项（挂载时静默加载，供表格映射与抽屉选择） */
const parentOptions = ref<{ value: number; label: string }[]>([]);

onMounted(async () => {
  const { error, data: resData } = await fetchGetHostGroupList({ current: 1, size: 100 });
  if (!error) {
    const records = resData.records ?? [];
    parentOptions.value = records.map(item => ({ value: item.id, label: item.name }));
    groupNameMap.value = new Map(records.map(item => [item.id, item.name]));
  }
});

/** ============ 新增/编辑抽屉 ============ */

type OperateType = 'add' | 'edit';

interface GroupForm {
  id?: number;
  name: string;
  parent: number | null;
  group_type: Api.Cmdb.HostGroupType;
  match_rule_text: string;
  description: string;
  is_active: boolean;
}

function createDefaultForm(): GroupForm {
  return {
    name: '',
    parent: null,
    group_type: 'static',
    match_rule_text: '',
    description: '',
    is_active: true
  };
}

const drawerVisible = ref(false);
const operateType = ref<OperateType>('add');
const submitting = ref(false);
const formRef = ref();
const formModel = ref<GroupForm>(createDefaultForm());

const formRules = {
  name: [{ required: true, message: '请输入分组名称', trigger: 'blur' }]
};

/** 动态分组需提供非空 JSON 对象匹配规则 */
function validateMatchRule(_rule: unknown, value: string, callback: (error?: Error) => void) {
  if (formModel.value.group_type !== 'dynamic') {
    callback();
    return;
  }
  try {
    const parsed = JSON.parse(value);
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed) || !Object.keys(parsed).length) {
      callback(new Error('动态分组需要非空的 JSON 对象匹配规则'));
      return;
    }
    callback();
  } catch {
    callback(new Error('匹配规则必须是合法 JSON'));
  }
}

function openOperateDrawer(type: OperateType, row?: Api.Cmdb.HostGroupRecord) {
  operateType.value = type;
  formModel.value = row
    ? {
        id: row.id,
        name: row.name,
        parent: row.parent,
        group_type: (row.group_type as Api.Cmdb.HostGroupType) || 'static',
        match_rule_text:
          row.match_rule && Object.keys(row.match_rule).length ? JSON.stringify(row.match_rule, null, 2) : '',
        description: row.description,
        is_active: row.is_active
      }
    : createDefaultForm();
  drawerVisible.value = true;
}

async function handleSubmit() {
  await formRef.value?.validate();

  submitting.value = true;
  const form = formModel.value;
  const payload: Api.Cmdb.HostGroupPayload = {
    name: form.name,
    parent: form.parent || null,
    group_type: form.group_type,
    match_rule: form.group_type === 'dynamic' ? JSON.parse(form.match_rule_text) : {},
    description: form.description,
    is_active: form.is_active
  };
  const { error } =
    operateType.value === 'add' ? await fetchAddHostGroup(payload) : await fetchUpdateHostGroup(form.id!, payload);
  submitting.value = false;

  if (!error) {
    window.$message?.success(operateType.value === 'add' ? '新增成功' : '修改成功');
    drawerVisible.value = false;
    getData();
  }
}

async function handleDelete(id: number) {
  const { error } = await fetchDeleteHostGroup(id);

  if (!error) {
    window.$message?.success('删除成功');
    getData();
  }
}

/** ============ 成员维护 ============ */

const membersVisible = ref(false);
const memberGroup = ref<Api.Cmdb.HostGroupRecord | null>(null);
const memberIds = ref<string[]>([]);
const memberLoading = ref(false);
const memberSaving = ref(false);
const hostOptions = ref<{ value: string; label: string }[]>([]);

async function openMembersDialog(row: Api.Cmdb.HostGroupRecord) {
  memberGroup.value = row;
  memberIds.value = [];
  membersVisible.value = true;
  memberLoading.value = true;

  const [membersRes, hostsRes] = await Promise.all([
    fetchGetHostGroupMembers(row.id),
    fetchGetHostList({ current: 1, size: 100 })
  ]);
  if (!membersRes.error) {
    memberIds.value = membersRes.data?.hostIds ?? [];
  }
  if (!hostsRes.error) {
    hostOptions.value = (hostsRes.data.records ?? []).map(host => ({
      value: String(host.id),
      label: `${host.hostname}（${host.primaryIp}）`
    }));
  }
  memberLoading.value = false;
}

async function handleSaveMembers() {
  if (!memberGroup.value) return;

  memberSaving.value = true;
  const { error } = await fetchUpdateHostGroupMembers(memberGroup.value.id, memberIds.value);
  memberSaving.value = false;

  if (!error) {
    window.$message?.success('成员更新成功');
    membersVisible.value = false;
    getData();
  }
}
</script>

<template>
  <div class="flex-col-stretch gap-12px">
    <ElForm :model="searchParams" label-width="70px" inline @submit.prevent>
      <ElFormItem label="分组类型">
        <ElSelect v-model="searchParams.groupType" clearable placeholder="全部" class="w-140px">
          <ElOption v-for="item in groupTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
        </ElSelect>
      </ElFormItem>
      <ElFormItem label="关键词">
        <ElInput
          v-model="searchParams.search"
          clearable
          placeholder="分组名称/描述"
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
      <p class="font-medium">主机分组</p>
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

    <ElDrawer v-model="drawerVisible" :title="operateType === 'add' ? '新增分组' : '编辑分组'" size="440px">
      <ElForm ref="formRef" :model="formModel" :rules="formRules" label-width="90px">
        <ElFormItem label="分组名称" prop="name">
          <ElInput v-model="formModel.name" placeholder="分组名称" />
        </ElFormItem>
        <ElFormItem label="上级分组">
          <ElSelect v-model="formModel.parent" clearable filterable placeholder="不选则为顶级分组" class="w-full">
            <ElOption
              v-for="item in parentOptions.filter(option => option.value !== formModel.id)"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="分组类型">
          <ElRadioGroup v-model="formModel.group_type">
            <ElRadio v-for="item in groupTypeOptions" :key="item.value" :value="item.value">
              {{ item.label }}
            </ElRadio>
          </ElRadioGroup>
        </ElFormItem>
        <ElFormItem
          v-if="formModel.group_type === 'dynamic'"
          label="匹配规则"
          prop="match_rule_text"
          :rules="[{ validator: validateMatchRule, trigger: 'blur' }]"
        >
          <ElInput
            v-model="formModel.match_rule_text"
            type="textarea"
            :rows="5"
            placeholder='JSON 对象，如 {"environment": "prod"}'
          />
        </ElFormItem>
        <ElFormItem label="描述">
          <ElInput v-model="formModel.description" type="textarea" :rows="3" placeholder="分组用途描述" />
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
      v-model="membersVisible"
      :title="`维护成员：${memberGroup?.name ?? ''}`"
      width="520px"
      :close-on-click-modal="false"
    >
      <div v-loading="memberLoading">
        <ElSelect
          v-model="memberIds"
          multiple
          filterable
          placeholder="选择主机（可搜索）"
          class="w-full"
          :multiple-limit="0"
        >
          <ElOption v-for="item in hostOptions" :key="item.value" :label="item.label" :value="item.value" />
        </ElSelect>
        <p class="mt-8px text-12px text-#909399">
          保存将全量覆盖该分组的主机成员（共 {{ hostOptions.length }} 台主机可选）
        </p>
      </div>
      <template #footer>
        <ElButton @click="membersVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="memberSaving" @click="handleSaveMembers">保存</ElButton>
      </template>
    </ElDialog>
  </div>
</template>

<style scoped></style>
