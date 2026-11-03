<script setup lang="ts">
import { computed, ref, shallowRef, watch } from 'vue';
import {
  fetchAddAssetSource,
  fetchGetNotificationTemplate,
  fetchGetNotificationTemplateList,
  fetchTestCloudConnection,
  fetchUpdateAssetSource
} from '@/service/api';

defineOptions({ name: 'CmdbAccountOperateDrawer' });

interface Emits {
  (e: 'submitted'): void;
}

const emit = defineEmits<Emits>();

type OperateType = 'add' | 'edit';

interface AccountForm {
  id?: number;
  code: string;
  name: string;
  cloud_provider: Api.Cmdb.AssetSourceRecord['cloud_provider'];
  endpoint: string;
  projectName: string;
  userDomainName: string;
  projectDomainName: string;
  regionsText: string;
  access_key_id: string;
  access_key_secret: string;
  has_credentials: boolean;
  description: string;
  is_active: boolean;
  syncEnabled: boolean;
  syncInterval: number;
  alertTemplateId: number | null;
  alertReceivers: string;
}

function createDefaultForm(): AccountForm {
  return {
    code: '',
    name: '',
    cloud_provider: '',
    endpoint: '',
    projectName: '',
    userDomainName: 'Default',
    projectDomainName: 'Default',
    regionsText: '',
    access_key_id: '',
    access_key_secret: '',
    has_credentials: false,
    description: '',
    is_active: true,
    syncEnabled: false,
    syncInterval: 60,
    alertTemplateId: null,
    alertReceivers: ''
  };
}

const visible = ref(false);
const operateType = ref<OperateType>('add');
const submitting = ref(false);
const formRef = ref();
const formModel = ref<AccountForm>(createDefaultForm());
const originalCloudProvider = ref<AccountForm['cloud_provider']>('');
const savedCredentialId = ref('');
const testing = ref(false);
const connectionResults = shallowRef<Api.Cmdb.CloudConnectionResult[]>([]);
const selectedTestRegions = ref<string[]>([]);
const untestedRegions = ref<string[]>([]);
const alertTemplates = shallowRef<Api.Automation.NotificationTemplateRecord[]>([]);
let templateSearchSequence = 0;

async function loadAlertTemplates(search = '') {
  templateSearchSequence += 1;
  const sequence = templateSearchSequence;
  const selectedId = formModel.value.alertTemplateId;
  const [list, selected] = await Promise.all([
    fetchGetNotificationTemplateList({ current: 1, size: 20, search: search.trim() || null }),
    selectedId ? fetchGetNotificationTemplate(selectedId) : Promise.resolve(null)
  ]);
  if (sequence !== templateSearchSequence || list.error || !list.data) return;
  const selectedOption = selected && !selected.error ? selected.data : null;
  const options = list.data.records.filter(item => item.isActive);
  alertTemplates.value =
    selectedOption && !options.some(item => item.id === selectedOption.id) ? [selectedOption, ...options] : options;
}
const regionOptions = computed(() => [
  ...new Set(
    formModel.value.regionsText
      .split(',')
      .map(region => region.trim())
      .filter(Boolean)
  )
]);
let testGeneration = 0;

const formRules = {
  code: [{ required: true, message: '请输入账号编码', trigger: 'blur' }],
  name: [{ required: true, message: '请输入账号名称', trigger: 'blur' }]
};

/** 凭据必填：新增账号、从未配置过凭据、或编辑时更换了云厂商 */
const credentialsRequired = computed(
  () =>
    !formModel.value.has_credentials ||
    (operateType.value === 'edit' && formModel.value.cloud_provider !== originalCloudProvider.value)
);
const isPrivateCloud = computed(() => ['vmware', 'openstack', 'pve'].includes(formModel.value.cloud_provider));
const needsRegion = computed(() => ['aliyun', 'tencent', 'openstack'].includes(formModel.value.cloud_provider));
const credentialIdLabel = computed(() => {
  if (formModel.value.cloud_provider === 'pve') return 'API Token ID';
  if (formModel.value.cloud_provider === 'vmware' || formModel.value.cloud_provider === 'openstack')
    return '只读用户名';
  return 'AccessKey ID';
});
const credentialSecretLabel = computed(() => {
  if (formModel.value.cloud_provider === 'pve') return 'API Token Secret';
  if (formModel.value.cloud_provider === 'vmware' || formModel.value.cloud_provider === 'openstack') return '登录密码';
  return 'AccessKey Secret';
});

function open(type: OperateType, row?: Api.Cmdb.AssetSourceRecord) {
  savedCredentialId.value = row?.masked_access_key_id ?? '';
  connectionResults.value = [];
  untestedRegions.value = [];
  operateType.value = type;
  originalCloudProvider.value = row?.cloud_provider ?? '';
  formModel.value = row
    ? {
        id: row.id,
        code: row.code,
        name: row.name,
        cloud_provider: row.cloud_provider,
        endpoint: row.endpoint,
        projectName: String(row.metadata?.project_name ?? ''),
        userDomainName: String(row.metadata?.user_domain_name ?? 'Default'),
        projectDomainName: String(row.metadata?.project_domain_name ?? 'Default'),
        regionsText: row.regions.join(', '),
        access_key_id: '',
        access_key_secret: '',
        has_credentials: row.has_credentials,
        description: row.description,
        is_active: row.is_active,
        syncEnabled: Boolean(row.sync_interval_minutes),
        syncInterval: row.sync_interval_minutes || 60,
        alertTemplateId: row.sync_failure_alert?.templateId ?? null,
        alertReceivers: row.sync_failure_alert?.receivers ?? ''
      }
    : createDefaultForm();
  visible.value = true;
  loadAlertTemplates();
}

async function handleTestConnection() {
  await formRef.value?.validate();
  const message = getValidationMessage(formModel.value);
  if (message) {
    window.$message?.warning(message);
    return;
  }
  if (!selectedTestRegions.value.length) {
    window.$message?.warning('请选择 1 至 5 个测试区域');
    return;
  }
  testGeneration += 1;
  const generation = testGeneration;
  testing.value = true;
  connectionResults.value = [];
  try {
    const { data, error } = await fetchTestCloudConnection({
      ...createPayload(formModel.value),
      test_regions: selectedTestRegions.value,
      ...(operateType.value === 'edit' ? { source_id: formModel.value.id } : {})
    });
    if (!error && data && generation === testGeneration) {
      connectionResults.value = data.results;
      untestedRegions.value = data.untestedRegions ?? [];
    }
  } finally {
    testing.value = false;
  }
}

function getValidationMessage(form: AccountForm): string {
  if (
    form.syncEnabled &&
    (!Number.isInteger(form.syncInterval) || form.syncInterval < 5 || form.syncInterval > 10080)
  ) {
    return '请填写 5 至 10080 分钟的周期同步间隔';
  }
  if (!form.cloud_provider || (needsRegion.value && !form.regionsText.trim())) {
    return '请选择云平台并填写同步区域';
  }
  if (isPrivateCloud.value && !form.endpoint.trim()) {
    return '请填写私有云 HTTPS 接入地址';
  }
  if (form.cloud_provider === 'openstack' && !form.projectName.trim()) {
    return '请填写 OpenStack 项目名称';
  }
  if (credentialsRequired.value && (!form.access_key_id.trim() || !form.access_key_secret)) {
    return '新增账号或更换云平台时，请填写完整的只读凭据';
  }
  if (Boolean(form.access_key_id.trim()) !== Boolean(form.access_key_secret)) {
    return '请同时填写账号标识和凭据密钥';
  }
  return '';
}

function createPayload(form: AccountForm): Api.Cmdb.AssetSourcePayload {
  return {
    code: form.code.trim(),
    name: form.name.trim(),
    source_type: 'cloud',
    description: form.description,
    is_active: form.is_active,
    sync_interval_minutes: form.syncEnabled ? form.syncInterval : 0,
    sync_failure_alert: form.alertTemplateId
      ? { templateId: form.alertTemplateId, receivers: form.alertReceivers.trim() }
      : {},
    cloud_provider: form.cloud_provider,
    endpoint: isPrivateCloud.value ? form.endpoint.trim() : '',
    metadata:
      form.cloud_provider === 'openstack'
        ? {
            project_name: form.projectName.trim(),
            user_domain_name: form.userDomainName.trim() || 'Default',
            project_domain_name: form.projectDomainName.trim() || 'Default'
          }
        : {},
    regions: needsRegion.value
      ? form.regionsText
          .split(',')
          .map(region => region.trim())
          .filter(Boolean)
      : [],
    ...(form.access_key_id.trim()
      ? { access_key_id: form.access_key_id.trim(), access_key_secret: form.access_key_secret }
      : {})
  };
}

async function handleSubmit() {
  await formRef.value?.validate();
  const form = formModel.value;
  const validationMessage = getValidationMessage(form);
  if (validationMessage) {
    window.$message?.warning(validationMessage);
    return;
  }

  submitting.value = true;
  const { error } =
    operateType.value === 'add'
      ? await fetchAddAssetSource(createPayload(form))
      : await fetchUpdateAssetSource(form.id!, createPayload(form));
  submitting.value = false;

  if (!error) {
    window.$notification?.success(operateType.value === 'add' ? '新增成功' : '修改成功');
    visible.value = false;
    emit('submitted');
  }
}

watch(
  formModel,
  () => {
    testGeneration += 1;
    connectionResults.value = [];
    untestedRegions.value = [];
  },
  { deep: true }
);

watch(regionOptions, regions => {
  selectedTestRegions.value = regions.slice(0, 5);
});
watch(selectedTestRegions, () => {
  testGeneration += 1;
  connectionResults.value = [];
  untestedRegions.value = [];
});

defineExpose({ open });
</script>

<template>
  <ElDrawer v-model="visible" :title="operateType === 'add' ? '新增云账号' : '编辑云账号'" size="720px">
    <ElForm
      ref="formRef"
      :model="formModel"
      :rules="formRules"
      label-position="top"
      label-suffix="："
      require-asterisk-position="left"
    >
      <ElRow :gutter="16">
        <ElCol :xs="24" :sm="12">
          <ElFormItem label="账号编码" prop="code">
            <ElInput v-model="formModel.code" placeholder="如 aliyun-prod" />
          </ElFormItem>
        </ElCol>
        <ElCol :xs="24" :sm="12">
          <ElFormItem label="账号名称" prop="name">
            <ElInput v-model="formModel.name" placeholder="如 阿里云生产环境" />
          </ElFormItem>
        </ElCol>
        <ElCol :xs="24" :sm="12">
          <ElFormItem label="云厂商" required>
            <ElSelect v-model="formModel.cloud_provider" class="w-full" placeholder="选择云厂商">
              <ElOption label="阿里云 ECS" value="aliyun" />
              <ElOption label="腾讯云 CVM" value="tencent" />
              <ElOption label="VMware vSphere" value="vmware" />
              <ElOption label="OpenStack" value="openstack" />
              <ElOption label="Proxmox VE" value="pve" />
            </ElSelect>
          </ElFormItem>
        </ElCol>
        <ElCol v-if="needsRegion" :xs="24" :sm="12">
          <ElFormItem>
            <template #label>
              <FormLabelHelp
                :label="formModel.cloud_provider === 'openstack' ? 'Region 名称' : '区域 ID'"
                :help="[
                  '云厂商区域 ID，支持英文逗号分隔多个区域；',
                  '不使用接口遍历区域列表，避免部分厂商接口过慢影响同步速度。'
                ]"
              />
            </template>
            <ElInput
              v-model="formModel.regionsText"
              :placeholder="formModel.cloud_provider === 'openstack' ? '如 RegionOne' : '如 cn-hangzhou, cn-shanghai'"
            />
          </ElFormItem>
        </ElCol>
        <ElCol v-if="isPrivateCloud" :span="24">
          <ElFormItem label="HTTPS 接入地址" required>
            <ElInput
              v-model="formModel.endpoint"
              :placeholder="
                formModel.cloud_provider === 'pve'
                  ? 'https://pve.example.com:8006'
                  : formModel.cloud_provider === 'openstack'
                    ? 'https://keystone.example.com/v3'
                    : 'https://vcenter.example.com'
              "
            />
          </ElFormItem>
          <p class="mb-12px text-12px text-[var(--el-text-color-regular)]">
            使用系统信任的 TLS 证书；VMware 需可读取虚拟机 Guest 网络，PVE 虚拟机需启用 QEMU Guest Agent 才能获取 IP。
          </p>
        </ElCol>
        <template v-if="formModel.cloud_provider === 'openstack'">
          <ElCol :xs="24" :sm="12">
            <ElFormItem label="项目名称" required>
              <ElInput v-model="formModel.projectName" placeholder="如 admin" />
            </ElFormItem>
          </ElCol>
          <ElCol :xs="24" :sm="12">
            <ElFormItem label="用户域 / 项目域">
              <div class="w-full flex gap-8px">
                <ElInput v-model="formModel.userDomainName" placeholder="用户域，如 Default" />
                <ElInput v-model="formModel.projectDomainName" placeholder="项目域，如 Default" />
              </div>
            </ElFormItem>
          </ElCol>
        </template>
        <ElCol :xs="24" :sm="12">
          <ElFormItem :label="credentialIdLabel" :required="credentialsRequired">
            <ElInput
              v-model="formModel.access_key_id"
              autocomplete="off"
              :placeholder="
                !credentialsRequired
                  ? `已保存 ${savedCredentialId}；留空保留`
                  : formModel.cloud_provider === 'pve'
                    ? 'user@realm!token'
                    : '只读账号标识'
              "
            />
          </ElFormItem>
        </ElCol>
        <ElCol :xs="24" :sm="12">
          <ElFormItem :label="credentialSecretLabel" :required="credentialsRequired">
            <ElInput
              v-model="formModel.access_key_secret"
              type="password"
              show-password
              autocomplete="new-password"
              :placeholder="!credentialsRequired ? '已保存；留空保留，填写后替换' : '只读凭据 Secret'"
            />
          </ElFormItem>
        </ElCol>
      </ElRow>
      <ElFormItem v-if="['aliyun', 'tencent'].includes(formModel.cloud_provider)">
        <template #label>
          <FormLabelHelp
            label="测试区域"
            :help="[
              '从上方区域 ID 中解析可选区域，最多选择 5 个；',
              '验证选定区域的主机和磁盘查询权限，不保存配置或导入资产。'
            ]"
          />
        </template>
        <div class="w-full flex flex-col gap-8px">
          <div class="flex gap-8px">
            <ElSelect
              v-model="selectedTestRegions"
              multiple
              :multiple-limit="5"
              class="min-w-0 flex-1"
              placeholder="选择要测试的区域"
            >
              <ElOption v-for="region in regionOptions" :key="region" :label="region" :value="region" />
            </ElSelect>
            <ElButton :loading="testing" @click="handleTestConnection">测试连接</ElButton>
          </div>
          <span v-if="untestedRegions.length" class="text-12px text-[var(--el-text-color-regular)]">
            尚未测试：{{ untestedRegions.join('、') }}。可切换测试区域后继续验证。
          </span>
          <ElAlert
            v-for="result in connectionResults"
            :key="result.region"
            :title="`${result.region}：${result.message}`"
            :type="result.success ? 'success' : 'error'"
            :closable="false"
            show-icon
          >
            <div v-if="result.checks?.length" class="mb-8px flex flex-wrap gap-8px">
              <ElTag
                v-for="check in result.checks"
                :key="check.key"
                :type="check.success ? 'success' : 'warning'"
                size="small"
              >
                {{ check.label }}：{{ check.success ? '通过' : '失败' }}
              </ElTag>
            </div>
            <div v-if="!result.success" class="min-w-0 flex flex-col gap-6px text-sm leading-6">
              <div v-if="result.errorCode || result.httpStatus" class="flex flex-wrap gap-x-16px">
                <span v-if="result.errorCode">
                  错误码：
                  <code class="break-all">{{ result.errorCode }}</code>
                </span>
                <span v-if="result.httpStatus">HTTP 状态：{{ result.httpStatus }}</span>
              </div>
              <div v-if="result.detail" class="whitespace-pre-wrap break-words">原因：{{ result.detail }}</div>
              <div v-if="result.suggestion">建议：{{ result.suggestion }}</div>
              <div class="text-regular break-all">
                请求 ID：{{ result.requestId || '未返回（请求可能未到达云 API）' }}
              </div>
            </div>
          </ElAlert>
        </div>
      </ElFormItem>
      <ElFormItem label="描述">
        <ElInput v-model="formModel.description" type="textarea" :rows="3" placeholder="账号描述" />
      </ElFormItem>
      <ElCollapse class="advanced-collapse">
        <ElCollapseItem title="同步策略与通知" name="sync">
          <ElFormItem label="周期同步">
            <ElSwitch v-model="formModel.syncEnabled" />
          </ElFormItem>
          <ElFormItem v-if="formModel.syncEnabled" label="同步间隔（分钟）">
            <ElInputNumber v-model="formModel.syncInterval" :min="5" :max="10080" :step="5" />
            <p class="text-regular mt-8px text-sm">
              开启后自动同步该账号可见范围内的新增和变化主机；不会删除或停用未返回的主机。首次将在下一次调度检查时执行。
            </p>
          </ElFormItem>
          <ElFormItem label="失败通知模板">
            <ElSelect
              v-model="formModel.alertTemplateId"
              clearable
              filterable
              remote
              :remote-method="loadAlertTemplates"
              class="w-full"
              placeholder="不发送通知"
            >
              <ElOption
                v-for="item in alertTemplates"
                :key="item.id"
                :label="item.name"
                :value="item.id"
                :disabled="!item.isActive"
              />
            </ElSelect>
            <p class="text-regular mt-8px text-sm">
              读取失败或部分入库失败时发送。模板变量：
              <code v-pre>{{ title }}、{{ sync.sourceName }}、{{ sync.errorMessage }}、{{ sync.id }}</code>
              。
            </p>
          </ElFormItem>
          <ElFormItem v-if="formModel.alertTemplateId" label="接收人">
            <ElInput v-model="formModel.alertReceivers" placeholder="留空使用通知模板配置" />
          </ElFormItem>
        </ElCollapseItem>
      </ElCollapse>
      <ElFormItem label="启用">
        <ElSwitch v-model="formModel.is_active" />
      </ElFormItem>
    </ElForm>
    <template #footer>
      <ElButton @click="visible = false">取消</ElButton>
      <ElButton type="primary" :loading="submitting" @click="handleSubmit">确定</ElButton>
    </template>
  </ElDrawer>
</template>
