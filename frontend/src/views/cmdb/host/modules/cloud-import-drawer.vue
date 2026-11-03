<script setup lang="ts">
import { computed, ref, shallowRef, watch } from 'vue';
import {
  fetchAddAssetSource,
  fetchGetAssetSourceList,
  fetchPreviewCloudAssets,
  fetchSyncCloudAssets
} from '@/service/api';
import { useAuth } from '@/hooks/business/auth';
import CloudSyncPreviewTable from '@/views/cmdb/source/modules/cloud-sync-preview-table.vue';
import { canSyncRow } from '@/views/cmdb/source/modules/cloud-preview';
import SyncRecordDrawer from '@/views/cmdb/source/modules/sync-record-drawer.vue';

defineOptions({ name: 'CmdbCloudImportDrawer' });

type CloudProvider = 'aliyun' | 'tencent' | 'vmware' | 'openstack' | 'pve';
type SourceMode = 'existing' | 'new';

interface Emits {
  (e: 'submitted'): void;
}

const emit = defineEmits<Emits>();
const { hasAuth } = useAuth();

const visible = ref(false);
const provider = ref<CloudProvider>('aliyun');
const sourceMode = ref<SourceMode>('existing');
const sources = shallowRef<Api.Cmdb.AssetSourceRecord[]>([]);
const sourceId = ref<number>();
const loadingSources = ref(false);
const savingSource = ref(false);
const previewing = ref(false);
const syncing = ref(false);
const preview = shallowRef<Api.Cmdb.AssetSyncPreview | null>(null);
const selectedSourceIds = ref<string[]>([]);
const hostSearch = ref('');
const hostActionFilter = ref<'all' | 'create' | 'update' | 'unchanged' | 'invalid'>('all');
const submittedRecordId = ref<number>();
const activeStep = ref(0);
const sourceForm = ref({
  code: '',
  name: '',
  regionsText: '',
  endpoint: '',
  projectName: '',
  userDomainName: 'Default',
  projectDomainName: 'Default',
  accessKeyId: '',
  accessKeySecret: ''
});
let requestEpoch = 0;
let previewController: AbortController | null = null;

function cancelPreviewRequest() {
  previewController?.abort();
  previewController = null;
}

const providerNames: Record<CloudProvider, string> = {
  aliyun: '阿里云 ECS',
  tencent: '腾讯云 CVM',
  vmware: 'VMware vSphere',
  openstack: 'OpenStack',
  pve: 'Proxmox VE'
};
const providerName = computed(() => providerNames[provider.value]);
const isPrivateCloud = computed(() => ['vmware', 'openstack', 'pve'].includes(provider.value));
const needsRegion = computed(() => ['aliyun', 'tencent', 'openstack'].includes(provider.value));
const availableSources = computed(() => sources.value.filter(item => item.cloud_provider === provider.value));
const selectedSource = computed(() => availableSources.value.find(item => item.id === sourceId.value));
const canCreateSource = computed(() => hasAuth('cmdb.asset_source:create'));
const canSyncSource = computed(() => hasAuth('cmdb.asset_source:sync'));
const filteredPreviewRows = computed(() =>
  (preview.value?.rows ?? []).filter(row => {
    const keyword = hostSearch.value.trim().toLowerCase();
    const matchesAction = hostActionFilter.value === 'all' || row.action === hostActionFilter.value;
    const matchesKeyword =
      !keyword || [row.hostname, row.internalIp, row.sourceId].some(value => value.toLowerCase().includes(keyword));
    return matchesAction && matchesKeyword;
  })
);
const selectedRows = computed(() =>
  (preview.value?.rows ?? []).filter(row => selectedSourceIds.value.includes(row.sourceId) && canSyncRow(row))
);
const selectedCreateCount = computed(() => selectedRows.value.filter(row => row.action === 'create').length);
const selectedUpdateCount = computed(() => selectedRows.value.filter(row => row.action === 'update').length);
const recordDrawerRef = shallowRef<InstanceType<typeof SyncRecordDrawer>>();

function openSyncRecords() {
  recordDrawerRef.value?.open(sourceId.value, selectedSource.value?.name);
}

function handleSyncCompleted() {
  emit('submitted');
}

function resetPreview() {
  preview.value = null;
  selectedSourceIds.value = [];
  hostSearch.value = '';
  hostActionFilter.value = 'all';
  submittedRecordId.value = undefined;
}

function toggleRowSelection(instanceId: string) {
  selectedSourceIds.value = selectedSourceIds.value.includes(instanceId)
    ? selectedSourceIds.value.filter(id => id !== instanceId)
    : [...selectedSourceIds.value, instanceId];
}

function selectFilteredRows() {
  selectedSourceIds.value = [
    ...new Set([...selectedSourceIds.value, ...filteredPreviewRows.value.filter(canSyncRow).map(row => row.sourceId)])
  ];
}

function clearSelection() {
  selectedSourceIds.value = [];
}

async function loadSources() {
  const epoch = requestEpoch;
  loadingSources.value = true;
  const { data, error } = await fetchGetAssetSourceList({ current: 1, size: 100, sourceType: 'cloud', isActive: true });
  if (epoch !== requestEpoch) return;
  loadingSources.value = false;
  if (error || !data) {
    window.$message?.error('加载云资产来源失败，请重试');
    return;
  }
  sources.value = data.records;
  if (!availableSources.value.some(item => item.id === sourceId.value)) {
    sourceId.value = availableSources.value[0]?.id;
  }
  if (!availableSources.value.length && canCreateSource.value) sourceMode.value = 'new';
}

function open(cloudProvider: CloudProvider = 'aliyun') {
  cancelPreviewRequest();
  requestEpoch += 1;
  provider.value = cloudProvider;
  sourceMode.value = 'existing';
  sourceId.value = undefined;
  activeStep.value = 0;
  loadingSources.value = false;
  savingSource.value = false;
  previewing.value = false;
  syncing.value = false;
  sourceForm.value = {
    code: '',
    name: '',
    regionsText: '',
    endpoint: '',
    projectName: '',
    userDomainName: 'Default',
    projectDomainName: 'Default',
    accessKeyId: '',
    accessKeySecret: ''
  };
  resetPreview();
  visible.value = true;
  loadSources();
}

function changeProvider(value: string | number | boolean | undefined) {
  if (value !== 'aliyun' && value !== 'tencent' && value !== 'vmware' && value !== 'openstack' && value !== 'pve')
    return;
  cancelPreviewRequest();
  requestEpoch += 1;
  provider.value = value;
  sourceMode.value = 'existing';
  sourceId.value = undefined;
  sourceForm.value = {
    code: '',
    name: '',
    regionsText: '',
    endpoint: '',
    projectName: '',
    userDomainName: 'Default',
    projectDomainName: 'Default',
    accessKeyId: '',
    accessKeySecret: ''
  };
  resetPreview();
  loadSources();
}

function changeMode(mode: SourceMode) {
  cancelPreviewRequest();
  requestEpoch += 1;
  sourceMode.value = mode;
  loadingSources.value = false;
  resetPreview();
  if (mode === 'existing') loadSources();
}

function handleModeChange(value: string | number | boolean | undefined) {
  if (value === 'existing' || value === 'new') changeMode(value);
}

function selectSource(id: number) {
  cancelPreviewRequest();
  requestEpoch += 1;
  sourceId.value = id;
  resetPreview();
}

function isSourceFormComplete(form: typeof sourceForm.value, regions: string[]): boolean {
  return Boolean(
    form.code.trim() &&
    form.name.trim() &&
    (!needsRegion.value || regions.length) &&
    (!isPrivateCloud.value || form.endpoint.trim()) &&
    (provider.value !== 'openstack' || form.projectName.trim()) &&
    form.accessKeyId.trim() &&
    form.accessKeySecret
  );
}

function createSourcePayload(form: typeof sourceForm.value, regions: string[]): Api.Cmdb.AssetSourcePayload {
  return {
    code: form.code.trim(),
    name: form.name.trim(),
    source_type: 'cloud',
    cloud_provider: provider.value,
    regions: needsRegion.value ? regions : [],
    endpoint: isPrivateCloud.value ? form.endpoint.trim() : '',
    metadata:
      provider.value === 'openstack'
        ? {
            project_name: form.projectName.trim(),
            user_domain_name: form.userDomainName.trim() || 'Default',
            project_domain_name: form.projectDomainName.trim() || 'Default'
          }
        : {},
    access_key_id: form.accessKeyId.trim(),
    access_key_secret: form.accessKeySecret,
    is_active: true
  };
}

async function createSource() {
  const form = sourceForm.value;
  const regions = form.regionsText
    .split(',')
    .map(item => item.trim())
    .filter(Boolean);
  if (!isSourceFormComplete(form, regions)) {
    window.$message?.warning('请填写账号名称、接入信息和完整的只读凭据');
    return;
  }
  savingSource.value = true;
  const epoch = requestEpoch;
  const { data, error } = await fetchAddAssetSource(createSourcePayload(form, regions));
  if (epoch !== requestEpoch) return;
  savingSource.value = false;
  if (error || !data) return;
  sourceForm.value.accessKeyId = '';
  sourceForm.value.accessKeySecret = '';
  window.$notification?.success('云账号已保存，请读取云主机');
  sourceMode.value = 'existing';
  sources.value = [...sources.value, data];
  sourceId.value = data.id;
  resetPreview();
  activeStep.value = 1;
}

function goPreviewStep() {
  if (!sourceId.value || !selectedSource.value?.has_credentials || !canSyncSource.value) return;
  activeStep.value = 1;
}

function goConfirmStep() {
  if (!preview.value?.confirmationToken || !selectedRows.value.length) return;
  activeStep.value = 2;
}

function goPreviousStep() {
  if (activeStep.value > 0 && activeStep.value < 3) activeStep.value -= 1;
}

async function loadPreview() {
  if (!sourceId.value) return;
  cancelPreviewRequest();
  const controller = new AbortController();
  previewController = controller;
  const epoch = requestEpoch;
  previewing.value = true;
  resetPreview();
  const { data, error } = await fetchPreviewCloudAssets(sourceId.value, controller.signal);
  if (previewController === controller) previewController = null;
  if (epoch !== requestEpoch) return;
  previewing.value = false;
  if (!error && data) preview.value = data;
}

async function confirmSync() {
  if (!sourceId.value || !preview.value?.confirmationToken || !selectedRows.value.length) return;
  const epoch = requestEpoch;
  syncing.value = true;
  const { data, error } = await fetchSyncCloudAssets(
    sourceId.value,
    preview.value.confirmationToken,
    selectedSourceIds.value
  );
  if (epoch !== requestEpoch) return;
  syncing.value = false;
  if (error || !data) return;
  submittedRecordId.value = data.id;
  preview.value = null;
  activeStep.value = 3;
  emit('submitted');
  window.$notification?.success('云资产同步任务已提交');
}

watch(visible, isVisible => {
  if (isVisible) return;
  cancelPreviewRequest();
  requestEpoch += 1;
  loadingSources.value = false;
  savingSource.value = false;
  previewing.value = false;
  syncing.value = false;
  sourceForm.value.accessKeyId = '';
  sourceForm.value.accessKeySecret = '';
});

defineExpose({ open });
</script>

<template>
  <ElDrawer
    v-model="visible"
    :title="`导入${providerName}主机`"
    size="min(1040px, 100vw)"
    :close-on-click-modal="false"
  >
    <div class="flex-col-stretch gap-20px">
      <ElSteps :active="activeStep" finish-status="success" align-center>
        <ElStep title="选择云账号" />
        <ElStep title="读取云主机" />
        <ElStep title="确认同步" />
      </ElSteps>

      <section v-if="activeStep === 0">
        <p class="mb-12px text-13px text-[var(--el-text-color-regular)]">
          选择已配置只读凭据的云账号，或新建账号。凭据不会展示在主机清单和运行快照中。
        </p>
        <ElForm label-position="top">
          <ElFormItem label="云厂商">
            <ElRadioGroup :model-value="provider" @change="changeProvider">
              <ElRadio value="aliyun">阿里云 ECS</ElRadio>
              <ElRadio value="tencent">腾讯云 CVM</ElRadio>
              <ElRadio value="vmware">VMware vSphere</ElRadio>
              <ElRadio value="openstack">OpenStack</ElRadio>
              <ElRadio value="pve">Proxmox VE</ElRadio>
            </ElRadioGroup>
          </ElFormItem>
        </ElForm>
        <ElRadioGroup :model-value="sourceMode" class="mb-16px" @change="handleModeChange">
          <ElRadio value="existing">已有来源</ElRadio>
          <ElRadio v-if="canCreateSource" value="new">新建来源</ElRadio>
        </ElRadioGroup>

        <template v-if="sourceMode === 'existing'">
          <ElSkeleton v-if="loadingSources" :rows="2" animated />
          <ElEmpty v-else-if="!availableSources.length" :image-size="72" description="暂无可用的该厂商云账号">
            <ElButton v-if="canCreateSource" type="primary" @click="changeMode('new')">新建云账号</ElButton>
            <ElButton v-else @click="loadSources">重新加载</ElButton>
          </ElEmpty>
          <ElForm v-else label-position="top">
            <ElFormItem>
              <template #label>
                <FormLabelHelp
                  label="云账号"
                  :help="['仅列出已配置只读凭据的账号；无凭据的账号需先到「资产接入 → 云账号管理」配置。']"
                />
              </template>
              <ElSelect :model-value="sourceId" class="w-full" placeholder="选择已配置的云账号" @change="selectSource">
                <ElOption
                  v-for="item in availableSources"
                  :key="item.id"
                  :label="`${item.name} · ${item.regions.join('、')}`"
                  :value="item.id"
                />
              </ElSelect>
            </ElFormItem>
            <p
              v-if="selectedSource && !selectedSource.has_credentials"
              class="text-13px text-[var(--el-color-warning)]"
            >
              此云账号尚未配置只读凭据，请到“资产接入 → 云账号管理”编辑后再同步。
            </p>
          </ElForm>
        </template>

        <ElForm v-else label-position="top" require-asterisk-position="left" label-suffix="：">
          <ElRow :gutter="16">
            <ElCol :xs="24" :sm="12">
              <ElFormItem required>
                <template #label>
                  <FormLabelHelp label="账号编码" :help="['唯一标识，建议「厂商-环境」，如 aliyun-prod。']" />
                </template>
                <ElInput v-model="sourceForm.code" placeholder="如 aliyun-prod" autocomplete="off" />
              </ElFormItem>
            </ElCol>
            <ElCol :xs="24" :sm="12">
              <ElFormItem label="账号名称" required>
                <ElInput v-model="sourceForm.name" :placeholder="`${providerName}生产环境`" />
              </ElFormItem>
            </ElCol>
            <ElCol v-if="isPrivateCloud" :span="24">
              <ElFormItem required>
                <template #label>
                  <FormLabelHelp
                    label="HTTPS 接入地址"
                    :help="['私有云 API 地址：vCenter 默认 443、PVE 默认 8006、OpenStack Keystone 以 /v3 结尾。']"
                  />
                </template>
                <ElInput
                  v-model="sourceForm.endpoint"
                  :placeholder="
                    provider === 'pve'
                      ? 'https://pve.example.com:8006'
                      : provider === 'openstack'
                        ? 'https://keystone.example.com/v3'
                        : 'https://vcenter.example.com'
                  "
                />
              </ElFormItem>
            </ElCol>
            <ElCol v-if="needsRegion" :span="24">
              <ElFormItem required>
                <template #label>
                  <FormLabelHelp
                    label="区域 ID"
                    :help="['云账号覆盖的地域；多个地域用英文逗号分隔，如 cn-hangzhou, cn-shanghai。']"
                  />
                </template>
                <ElInput
                  v-model="sourceForm.regionsText"
                  :placeholder="
                    provider === 'openstack' ? '如 RegionOne' : '多个区域用英文逗号分隔，如 cn-hangzhou, cn-shanghai'
                  "
                />
              </ElFormItem>
            </ElCol>
            <template v-if="provider === 'openstack'">
              <ElCol :xs="24" :sm="12">
                <ElFormItem required>
                  <template #label>
                    <FormLabelHelp label="项目名称" :help="['OpenStack 项目（租户）名称。']" />
                  </template>
                  <ElInput v-model="sourceForm.projectName" placeholder="如 admin" />
                </ElFormItem>
              </ElCol>
              <ElCol :xs="24" :sm="12">
                <ElFormItem>
                  <template #label>
                    <FormLabelHelp label="用户域 / 项目域" :help="['OpenStack 认证域；留空使用 Default。']" />
                  </template>
                  <div class="w-full flex gap-8px">
                    <ElInput v-model="sourceForm.userDomainName" placeholder="用户域" />
                    <ElInput v-model="sourceForm.projectDomainName" placeholder="项目域" />
                  </div>
                </ElFormItem>
              </ElCol>
            </template>
            <ElCol :xs="24" :sm="12">
              <ElFormItem required>
                <template #label>
                  <FormLabelHelp
                    :label="provider === 'pve' ? 'API Token ID' : isPrivateCloud ? '只读用户名' : 'AccessKey ID'"
                    :help="['只读凭据标识，仅用于读取云主机清单；建议使用最小权限账号。']"
                  />
                </template>
                <ElInput
                  v-model="sourceForm.accessKeyId"
                  autocomplete="off"
                  :placeholder="provider === 'pve' ? 'user@realm!token' : '只读账号标识'"
                />
              </ElFormItem>
            </ElCol>
            <ElCol :xs="24" :sm="12">
              <ElFormItem required>
                <template #label>
                  <FormLabelHelp
                    :label="provider === 'pve' ? 'API Token Secret' : isPrivateCloud ? '登录密码' : 'AccessKey Secret'"
                    :help="['只读凭据 Secret，加密保存且不会展示在主机清单和快照中。']"
                  />
                </template>
                <ElInput
                  v-model="sourceForm.accessKeySecret"
                  type="password"
                  show-password
                  autocomplete="new-password"
                  placeholder="只读凭据 Secret"
                />
              </ElFormItem>
            </ElCol>
          </ElRow>
        </ElForm>
      </section>

      <section v-if="activeStep === 1">
        <p class="mb-12px text-13px text-[var(--el-text-color-regular)]">
          使用“{{ selectedSource?.name }}”的只读凭据读取
          {{ providerName }} 实例。读取完成后核对本次新增、更新及无效主机。
        </p>
        <ElButton :loading="previewing" @click="loadPreview">{{ preview ? '重新读取' : '读取云主机' }}</ElButton>
        <div v-if="preview" class="mt-16px">
          <p class="mb-8px text-13px">
            共 {{ preview.total }} 台 · 新增 {{ preview.create }} 台 · 更新 {{ preview.update }} 台 · 未变化
            {{ preview.unchanged ?? 0 }} 台 · 无效 {{ preview.invalid }} 台
          </p>
          <div class="mb-12px flex flex-wrap items-center gap-8px">
            <ElInput v-model="hostSearch" clearable class="w-full sm:w-220px" placeholder="搜索主机名、IP 或实例 ID" />
            <ElSelect v-model="hostActionFilter" class="w-130px">
              <ElOption label="全部结果" value="all" />
              <ElOption label="新增" value="create" />
              <ElOption label="更新" value="update" />
              <ElOption label="未变化" value="unchanged" />
              <ElOption label="无效" value="invalid" />
            </ElSelect>
            <ElButton @click="selectFilteredRows">选择当前结果</ElButton>
            <ElButton :disabled="!selectedSourceIds.length" @click="clearSelection">清空选择</ElButton>
          </div>
          <p class="mb-8px text-13px">
            已选 {{ selectedRows.length }} 台：新增 {{ selectedCreateCount }} 台，更新 {{ selectedUpdateCount }} 台
          </p>
          <CloudSyncPreviewTable
            :rows="filteredPreviewRows"
            :selected-ids="selectedSourceIds"
            :busy="syncing"
            @toggle="toggleRowSelection"
          />
          <p class="text-regular mt-8px text-sm">展开主机行可查看变更前后的值；未变化的主机无需同步。</p>
          <p v-if="preview.invalid" class="mt-8px text-13px text-[var(--el-color-warning)]">
            无效主机不可选择；可先同步其他有效主机，修正云端数据后再重新读取。
          </p>
        </div>
        <ElEmpty v-else-if="!previewing" :image-size="72" description="尚未读取云主机" />
      </section>

      <section v-if="activeStep === 2 && preview">
        <p class="mb-12px text-14px">确认本次同步范围</p>
        <ElDescriptions :column="1" border>
          <ElDescriptionsItem label="云厂商">{{ providerName }}</ElDescriptionsItem>
          <ElDescriptionsItem label="云账号">{{ selectedSource?.name }}</ElDescriptionsItem>
          <ElDescriptionsItem label="区域">{{ selectedSource?.regions.join('、') }}</ElDescriptionsItem>
          <ElDescriptionsItem label="读取实例">{{ preview.total }} 台</ElDescriptionsItem>
          <ElDescriptionsItem label="本次选择">{{ selectedRows.length }} 台</ElDescriptionsItem>
          <ElDescriptionsItem label="预计变更">
            新增 {{ selectedCreateCount }} 台，更新 {{ selectedUpdateCount }} 台
          </ElDescriptionsItem>
        </ElDescriptions>
        <ElAlert class="mt-16px" type="info" :closable="false" show-icon>
          <template #title>确认后提交异步同步任务</template>
          未出现在本次清单中的已有主机不会删除或停用；提交前云端资产如有变化，请重新读取后确认同步。
        </ElAlert>
      </section>

      <ElAlert v-if="activeStep === 0 && !canSyncSource" type="warning" :closable="false" show-icon>
        <template #title>当前账号没有云资产同步权限，请联系管理员。</template>
      </ElAlert>
      <ElAlert v-if="activeStep === 3 && submittedRecordId" type="success" :closable="false" show-icon>
        <template #title>同步任务已提交（记录 #{{ submittedRecordId }}）</template>
        主机将在异步同步完成后更新，可查看同步记录跟踪结果。
      </ElAlert>
      <SyncRecordDrawer ref="recordDrawerRef" @updated="handleSyncCompleted" />
    </div>
    <template #footer>
      <ElButton @click="visible = false">关闭</ElButton>
      <ElButton v-if="activeStep === 3" type="primary" @click="openSyncRecords">查看同步记录</ElButton>
      <ElButton v-if="activeStep === 1 || activeStep === 2" :disabled="previewing || syncing" @click="goPreviousStep">
        上一步
      </ElButton>
      <ElButton
        v-if="activeStep === 0 && sourceMode === 'new'"
        type="primary"
        :loading="savingSource"
        :disabled="!canCreateSource || !canSyncSource"
        @click="createSource"
      >
        保存云账号并继续
      </ElButton>
      <ElButton
        v-if="activeStep === 0 && sourceMode === 'existing'"
        type="primary"
        :disabled="!selectedSource?.has_credentials || !canSyncSource || loadingSources"
        @click="goPreviewStep"
      >
        下一步
      </ElButton>
      <ElButton
        v-if="activeStep === 1"
        type="primary"
        :disabled="!preview?.confirmationToken || !selectedRows.length || previewing"
        @click="goConfirmStep"
      >
        下一步：确认同步
      </ElButton>
      <ElButton
        v-if="activeStep === 2 && preview"
        type="primary"
        :disabled="!selectedRows.length || !preview.confirmationToken"
        :loading="syncing"
        @click="confirmSync"
      >
        确认同步 · {{ selectedRows.length }} 台
      </ElButton>
    </template>
  </ElDrawer>
</template>
