<script setup lang="tsx">
import { computed, ref, watch } from 'vue';
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
  { value: 'ssh_key', label: '密钥' },
  { value: 'password', label: '密码' }
  // vault_ref 不可选：当前部署未配置 Vault Provider，后端会拒绝该类型
];

const typeText: Record<string, string> = Object.fromEntries(typeOptions.map(item => [item.value, item.label]));

function getInitSearchParams() {
  return {
    current: 1,
    size: 10,
    search: undefined as string | undefined,
    type: undefined as Api.Cmdb.CredentialType | undefined
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
      prop: 'connection_type',
      label: '协议',
      width: 90,
      align: 'center'
    },
    { prop: 'username', label: '用户名', width: 110, formatter: row => row.username || '-' },
    {
      prop: 'effectivePort',
      label: '端口',
      width: 80,
      align: 'center',
      className: 'tabular-nums',
      formatter: row => String(row.effectivePort ?? '-')
    },
    {
      prop: 'secret_source',
      label: '密钥来源',
      minWidth: 150,
      showOverflowTooltip: true,
      formatter: formatSecretSource
    },
    { prop: 'hostCount', label: '关联主机', width: 90, align: 'center', className: 'tabular-nums' },
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

/** 列表「密钥来源」：外部引用原样展示（env:/file:），加密存储的显示固定文案 */
function formatSecretSource(row: Api.Cmdb.CredentialRefRecord) {
  if (row.secret_ref) return <span class="text-12px font-mono">{row.secret_ref}</span>;
  return row.encrypted_secret ? '加密存储' : '-';
}

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
  connection_type: Api.Cmdb.CredentialConnectionType;
  username: string;
  default_port: number | null;
  /** 密钥来源：inline=平台加密存储（默认）；external=引用服务器已有密钥（不落库） */
  secretSource: 'inline' | 'external';
  /** external 模式的引用方式：env=环境变量，file=密钥文件（提交时拼为 env:xxx / file:xxx） */
  refScheme: 'env' | 'file';
  refValue: string;
  secret: string;
  is_active: boolean;
}

function createDefaultForm(): FormModel {
  return {
    name: '',
    type: 'ssh_key',
    connection_type: 'ssh',
    username: 'root',
    default_port: null,
    secretSource: 'inline',
    refScheme: 'env',
    refValue: '',
    secret: '',
    is_active: true
  };
}

const drawerVisible = ref(false);
const operateType = ref<OperateType>('add');
const submitting = ref(false);
const formRef = ref();
const formModel = ref<FormModel>(createDefaultForm());

const isSshKey = computed(() => formModel.value.type === 'ssh_key');

/** 密钥必填：inline 来源时新增必填（编辑留空 = 不修改）；external 来源不校验 */
function validateSecret(_rule: unknown, value: string, callback: (error?: Error) => void) {
  if (formModel.value.secretSource !== 'inline') return callback();
  if (operateType.value === 'edit' && !value) return callback();
  if (!value.trim()) return callback(new Error(isSshKey.value ? '请粘贴私钥内容' : '请输入登录密码'));
  return callback();
}

/** 引用值必填：仅 external 来源校验，文案随引用方式联动 */
function validateRefValue(_rule: unknown, value: string, callback: (error?: Error) => void) {
  if (formModel.value.secretSource !== 'external') return callback();
  if (!value.trim()) {
    return callback(new Error(formModel.value.refScheme === 'env' ? '请输入环境变量名' : '请输入密钥文件路径'));
  }
  return callback();
}

const formRules = {
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  type: [{ required: true, message: '请选择类型', trigger: 'change' }],
  secret: [{ validator: validateSecret, trigger: 'blur' }],
  refValue: [{ validator: validateRefValue, trigger: 'blur' }]
};

/** ============ 字段联动 ============ */

/** 密钥类型不支持 WinRM（WinRM 用密码/证书），此时协议锁定为 SSH */
const protocolLockedToSsh = computed(() => formModel.value.type === 'ssh_key');
const protocolOptions = computed(() =>
  protocolLockedToSsh.value
    ? [{ value: 'ssh', label: 'SSH' }]
    : [
        { value: 'ssh', label: 'SSH' },
        { value: 'winrm', label: 'WinRM' }
      ]
);

const portPlaceholder = computed(() => (formModel.value.connection_type === 'winrm' ? '留空默认 5985' : '留空默认 22'));

/** ============ 密钥来源联动 ============ */

/** 编辑时打开抽屉前保存的原 secret_ref（inline 模式留空明文 = 不修改已存密钥时原样回传） */
const originalSecretRef = ref('');

/** inline 模式输入框标签随类型联动 */
const inlineSecretLabel = computed(() => (isSshKey.value ? '私钥内容' : '登录密码'));

const inlineSecretPlaceholder = computed(() => {
  if (operateType.value === 'edit' && !formModel.value.secret) return '留空则不修改已存密钥';
  return isSshKey.value ? '粘贴 SSH 私钥全文（OpenSSH / PEM 格式）' : '登录密码';
});

const refValuePlaceholder = computed(() =>
  formModel.value.refScheme === 'env' ? '环境变量名，如 PROD_SSH_KEY' : '凭据目录内的绝对路径，如 /srv/creds/deploy.key'
);

/** 解析已存外部引用为 引用方式 + 引用值 */
function parseExternalRef(secretRef: string) {
  const refScheme: FormModel['refScheme'] = secretRef.startsWith('file:') ? 'file' : 'env';
  return { refScheme, refValue: secretRef.replace(/^file:/, '').replace(/^env:/, '') };
}

/** 切换来源/引用方式时清除另一字段的残留校验错误 */
watch([() => formModel.value.secretSource, () => formModel.value.refScheme], () => {
  formRef.value?.clearValidate(['secret', 'refValue']);
});

watch(
  () => formModel.value.type,
  type => {
    if (type === 'ssh_key') {
      formModel.value.connection_type = 'ssh';
    }
  }
);

function openOperateDrawer(type: OperateType, row?: Api.Cmdb.CredentialRefRecord) {
  operateType.value = type;
  originalSecretRef.value = row?.secret_ref ?? '';
  formModel.value = row
    ? {
        id: row.id,
        name: row.name,
        type: row.type as Api.Cmdb.CredentialType,
        connection_type: row.connection_type as Api.Cmdb.CredentialConnectionType,
        username: row.username,
        default_port: row.default_port,
        secretSource: row.secret_ref ? 'external' : 'inline',
        ...parseExternalRef(row.secret_ref),
        secret: '',
        is_active: row.is_active
      }
    : createDefaultForm();
  drawerVisible.value = true;
}

async function handleSubmit() {
  await formRef.value?.validate();

  const isEdit = operateType.value === 'edit';

  // inline + 编辑留空明文 = 不修改，原 secret_ref 原样回传（保持后端"留空即不变"语义）
  function resolveSubmitSecretRef() {
    if (formModel.value.secretSource === 'external') {
      return `${formModel.value.refScheme}:${formModel.value.refValue.trim()}`;
    }
    if (isEdit && !formModel.value.secret) return originalSecretRef.value;
    return '';
  }

  submitting.value = true;
  const payload: Api.Cmdb.CredentialRefPayload = {
    name: formModel.value.name,
    type: formModel.value.type,
    // 作用域对执行链路无行为差异，统一按全局创建（存量 host 值编辑时归一为 global）
    scope: 'global',
    connection_type: formModel.value.connection_type,
    username: formModel.value.username,
    default_port: formModel.value.default_port,
    secret_ref: resolveSubmitSecretRef(),
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
    window.$notification?.success(operateType.value === 'add' ? '新增成功' : '修改成功');
    drawerVisible.value = false;
    getData();
  }
}

async function handleDelete(id: number) {
  const { error } = await fetchDeleteCredentialRef(id);

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
        <ElFormItem label="类型">
          <ElSelect v-model="searchParams.type" clearable placeholder="全部">
            <ElOption v-for="item in typeOptions" :key="item.value" :label="item.label" :value="item.value" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="关键词">
          <ElInput
            v-model="searchParams.search"
            clearable
            placeholder="名称/用户名/引用"
            @keyup.enter="getDataByPage()"
          />
        </ElFormItem>
      </ElForm>
    </SearchPanel>

    <ElCard class="card-wrapper sm:flex-1-hidden">
      <template #header>
        <div class="flex flex-wrap items-center justify-between gap-8px">
          <p>凭据管理</p>
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

    <ElDrawer v-model="drawerVisible" :title="operateType === 'add' ? '新增凭据' : '编辑凭据'" size="min(560px, 100%)">
      <ElForm
        ref="formRef"
        :model="formModel"
        :rules="formRules"
        label-position="top"
        label-suffix="："
        require-asterisk-position="left"
      >
        <ElFormItem label="名称" prop="name">
          <ElInput v-model="formModel.name" placeholder="凭据名称" />
        </ElFormItem>
        <ElFormItem label="类型" prop="type">
          <ElSelect v-model="formModel.type" class="w-full">
            <ElOption v-for="item in typeOptions" :key="item.value" :label="item.label" :value="item.value" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="协议">
          <ElSelect v-model="formModel.connection_type" class="w-full" :disabled="protocolLockedToSsh">
            <ElOption v-for="item in protocolOptions" :key="item.value" :label="item.label" :value="item.value" />
          </ElSelect>
          <p v-if="protocolLockedToSsh" class="mt-4px text-12px text-[var(--el-text-color-secondary)]">
            密钥类型仅支持 SSH
          </p>
        </ElFormItem>
        <ElFormItem>
          <template #label>
            <FormLabelHelp
              label="用户名"
              :help="['连接目标主机时使用的登录账号，如 root', '执行时对应 Ansible 的 ansible_user 变量']"
            />
          </template>
          <ElInput v-model="formModel.username" placeholder="连接用户名" />
        </ElFormItem>
        <ElFormItem>
          <template #label>
            <FormLabelHelp label="默认端口" :help="['留空时按协议推断：SSH 为 22，WinRM 为 5985']" />
          </template>
          <ElInputNumber
            v-model="formModel.default_port"
            :min="1"
            :max="65535"
            class="w-full"
            :placeholder="portPlaceholder"
          />
        </ElFormItem>
        <ElFormItem>
          <template #label>
            <FormLabelHelp
              label="密钥来源"
              :help="[
                '平台加密存储：密钥加密后保存到平台数据库，仅执行时解密使用',
                '服务器已有密钥：平台只保存引用，密钥不落库，需服务器预先配置环境变量或凭据目录'
              ]"
            />
          </template>
          <ElRadioGroup v-model="formModel.secretSource">
            <ElRadio value="inline">平台加密存储</ElRadio>
            <ElRadio value="external">服务器已有密钥</ElRadio>
          </ElRadioGroup>
        </ElFormItem>
        <ElFormItem v-if="formModel.secretSource === 'inline'" prop="secret">
          <template #label>
            <FormLabelHelp
              :label="inlineSecretLabel"
              :help="['平台加密存储该密钥，仅在任务执行时解密使用', '编辑时留空表示不修改已保存的密钥']"
            />
          </template>
          <ElInput
            v-if="isSshKey"
            v-model="formModel.secret"
            type="textarea"
            :rows="6"
            :placeholder="inlineSecretPlaceholder"
          />
          <ElInput
            v-else
            v-model="formModel.secret"
            type="password"
            show-password
            :placeholder="inlineSecretPlaceholder"
          />
        </ElFormItem>
        <template v-else>
          <ElFormItem>
            <template #label>
              <FormLabelHelp
                label="引用方式"
                :help="[
                  '环境变量：从执行服务器的环境变量读取密钥（需在部署白名单内）',
                  '密钥文件：从部署配置的凭据目录读取密钥文件'
                ]"
              />
            </template>
            <ElRadioGroup v-model="formModel.refScheme">
              <ElRadio value="env">环境变量</ElRadio>
              <ElRadio value="file">密钥文件</ElRadio>
            </ElRadioGroup>
          </ElFormItem>
          <ElFormItem label="引用值" prop="refValue">
            <ElInput v-model="formModel.refValue" class="w-full" :placeholder="refValuePlaceholder" />
            <p class="w-full text-12px text-[var(--el-text-color-secondary)] leading-relaxed">
              密钥保存在服务器上，平台仅存引用不落库；需预先配置环境变量白名单或凭据目录，未配置时保存会被拒绝
            </p>
          </ElFormItem>
        </template>
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
