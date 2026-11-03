<script setup lang="ts">
import { computed, ref, shallowRef, watch } from 'vue';
import type { FormInstance, FormRules } from 'element-plus';
import { fetchGetNotificationTemplateList } from '@/service/api/automation';
import {
  createResourceApplication,
  fetchCreationCredentials,
  fetchResourceTemplates,
  fetchResourceVersions
} from '@/service/api/provisioning';
import type {
  CatalogKind,
  CreationCredential,
  ResourceParameters,
  ResourceTemplate,
  ResourceVersion
} from '@/service/api/provisioning';
import CloudResourcePicker from '@/components/business/cloud-resource-picker/index.vue';
import CloudResourceAvailability from '@/components/business/cloud-resource-picker/availability.vue';
import { resetDependencies } from '@/components/business/cloud-resource-picker/shared';

defineOptions({ name: 'ResourceApplicationDrawer' });
const emit = defineEmits<{ created: [id: number] }>();
const visible = defineModel<boolean>({ default: false });
const templates = shallowRef<ResourceTemplate[]>([]);
const versions = shallowRef<ResourceVersion[]>([]);
const credentials = shallowRef<CreationCredential[]>([]);
const formRef = shallowRef<FormInstance>();
const step = ref(0);
const loading = ref(false);
const notificationTemplate = ref<number>();
const notificationTemplates = shallowRef<Api.Automation.NotificationTemplateRecord[]>([]);

async function loadNotifications(search = '') {
  const { data, error } = await fetchGetNotificationTemplateList({ current: 1, size: 20, search });
  if (!error) notificationTemplates.value = (data?.records ?? []).filter(item => item.isActive);
}
const model = ref({
  name: '',
  version: undefined as number | undefined,
  credential: undefined as number | undefined,
  region: ''
});
const parameters = ref<ResourceParameters>({
  name: '',
  count: 1,
  image_id: '',
  instance_type: '',
  zone: '',
  vpc_id: '',
  subnet_id: '',
  security_group_ids: [],
  system_disk_gb: 40
});
const selectedVersion = computed(() => versions.value.find(item => item.id === model.value.version));
const dynamicResources = computed(() => selectedVersion.value?.constraints.schemaVersion === 2);
const regions = computed(() => selectedVersion.value?.constraints.regions ?? []);
const availableCredentials = computed(() =>
  credentials.value.filter(
    item =>
      selectedVersion.value?.constraints.selectors?.sourceIds.includes(item.source) ||
      selectedVersion.value?.constraints.networks?.some(network => network.source_id === item.source)
  )
);
const networks = computed(
  () =>
    selectedVersion.value?.constraints.networks?.filter(
      item =>
        item.source_id === credentials.value.find(credential => credential.id === model.value.credential)?.source &&
        item.region === model.value.region
    ) ?? []
);
const securityGroups = computed(
  () => networks.value.find(item => item.subnet_id === parameters.value.subnet_id)?.security_group_ids ?? []
);
const availableVersions = computed(() =>
  versions.value.filter(
    item =>
      item.status === 'published' &&
      templates.value.some(template => template.id === item.template && template.is_active)
  )
);
const rules: FormRules = Object.fromEntries(
  ['name', 'version', 'credential', 'region'].map(key => [
    key,
    [{ required: true, message: '请填写或选择此项', trigger: 'change' }]
  ])
);
const fields = [
  { key: 'image_id', label: '镜像 ID' },
  { key: 'instance_type', label: '实例规格' },
  { key: 'zone', label: '可用区' },
  { key: 'vpc_id', label: 'VPC ID' },
  { key: 'subnet_id', label: '子网 / 交换机 ID' }
] as const;

function versionLabel(item: ResourceVersion) {
  return `${templates.value.find(template => template.id === item.template)?.name ?? '资源模板'} · v${item.number}`;
}

function changeVersion() {
  model.value.region = '';
  parameters.value = {
    name: '',
    count: 1,
    image_id: '',
    instance_type: '',
    zone: '',
    vpc_id: '',
    subnet_id: '',
    security_group_ids: [],
    system_disk_gb: 40
  };
  model.value.credential = undefined;
}

function selectNetwork(subnet: string) {
  const network = networks.value.find(item => item.subnet_id === subnet);
  parameters.value.subnet_id = network?.subnet_id ?? '';
  parameters.value.vpc_id = network?.vpc_id ?? '';
  parameters.value.zone = network?.zone ?? '';
  parameters.value.security_group_ids = [];
}

function resetNetwork() {
  parameters.value = resetDependencies(parameters.value, 'account');
}

function catalogQuery(kind: CatalogKind) {
  if (!model.value.version || !model.value.credential || !model.value.region) return undefined;
  return {
    kind,
    versionId: model.value.version,
    credentialId: model.value.credential,
    region: model.value.region,
    zone: kind === 'zones' ? undefined : parameters.value.zone || undefined,
    vpcId: ['subnets', 'security_groups'].includes(kind) ? parameters.value.vpc_id || undefined : undefined,
    instanceType: ['images', 'availability'].includes(kind) ? parameters.value.instance_type || undefined : undefined
  };
}

async function next() {
  if (await formRef.value?.validate().catch(() => false)) {
    if (networks.value.length === 1) selectNetwork(networks.value[0].subnet_id);
    step.value = 1;
  }
}

function previous() {
  step.value = 0;
}

async function submit() {
  if (!model.value.version || !model.value.credential) return;
  const missing = fields.some(field => !parameters.value[field.key].trim());
  if (missing || !parameters.value.security_group_ids.length || !parameters.value.name.trim()) {
    window.$message?.warning('请填写主机名称、规格、镜像及网络参数');
    return;
  }
  loading.value = true;
  try {
    const payload = {
      ...model.value,
      version: model.value.version,
      credential: model.value.credential,
      notification_config: notificationTemplate.value ? { templateId: notificationTemplate.value } : undefined,
      parameters: { ...parameters.value }
    };
    const { data, error } = await createResourceApplication(payload);
    if (!error && data) emit('created', data.id);
  } finally {
    loading.value = false;
  }
}

async function init() {
  step.value = 0;
  notificationTemplate.value = undefined;
  model.value = { name: '', version: undefined, credential: undefined, region: '' };
  changeVersion();
  loading.value = true;
  try {
    const [a, b, c] = await Promise.all([
      fetchResourceTemplates(),
      fetchResourceVersions(),
      fetchCreationCredentials()
    ]);
    templates.value = a.data ?? [];
    versions.value = b.data ?? [];
    credentials.value = (c.data ?? []).filter(item => item.is_active && item.has_secret);
  } finally {
    loading.value = false;
  }
}

watch(visible, value => {
  if (value) init();
});
watch(
  () => parameters.value.zone,
  () => {
    if (dynamicResources.value) parameters.value = resetDependencies(parameters.value, 'zone');
  }
);
watch(
  () => parameters.value.vpc_id,
  () => {
    if (dynamicResources.value) parameters.value = resetDependencies(parameters.value, 'vpc');
  }
);
watch(
  () => parameters.value.instance_type,
  () => {
    if (dynamicResources.value) parameters.value.image_id = '';
  }
);
</script>

<template>
  <ElDrawer v-model="visible" title="申请主机" size="680px" :close-on-click-modal="false">
    <div v-loading="loading" class="flex-col gap-24px">
      <ElSteps :active="step" simple>
        <ElStep title="模板与账号" />
        <ElStep title="资源参数" />
        <ElStep title="计划与审批" />
      </ElSteps>
      <ElForm
        v-if="step === 0"
        ref="formRef"
        :model="model"
        :rules="rules"
        label-width="110px"
        label-suffix="："
        require-asterisk-position="left"
      >
        <ElFormItem label="申请名称" prop="name"><ElInput v-model="model.name" maxlength="128" /></ElFormItem>
        <ElFormItem prop="version">
          <template #label>
            <FormLabelHelp label="资源模板" :help="['模板决定可用云账号、地域和资源约束；仅已发布版本可选。']" />
          </template>
          <ElSelect v-model="model.version" class="w-full" @change="changeVersion">
            <ElOption v-for="item in availableVersions" :key="item.id" :value="item.id" :label="versionLabel(item)" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem prop="credential">
          <template #label>
            <FormLabelHelp label="创建凭据" :help="['用于 Terraform 创建主机的云 API 凭据，不同于资产读取凭据。']" />
          </template>
          <ElSelect v-model="model.credential" class="w-full" @change="resetNetwork">
            <ElOption v-for="item in availableCredentials" :key="item.id" :value="item.id" :label="item.name" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem prop="region">
          <template #label>
            <FormLabelHelp label="地域" :help="['受资源模板允许地域限制；切换地域会重置已选网络资源。']" />
          </template>
          <ElSelect v-model="model.region" class="w-full" @change="resetNetwork">
            <ElOption v-for="region in regions" :key="region" :label="region" :value="region" />
          </ElSelect>
        </ElFormItem>
      </ElForm>
      <ElForm v-else label-width="130px" label-suffix="：" require-asterisk-position="left">
        <ElFormItem label="主机名称前缀" required><ElInput v-model="parameters.name" maxlength="100" /></ElFormItem>
        <ElFormItem required>
          <template #label>
            <FormLabelHelp label="主机数量" :help="['单次最多创建 20 台；主机名按前缀自动编号。']" />
          </template>
          <ElInputNumber v-model="parameters.count" :min="1" :max="20" />
        </ElFormItem>
        <template v-if="dynamicResources">
          <ElFormItem label="可用区" required>
            <CloudResourcePicker v-model="parameters.zone" :query="catalogQuery('zones')" />
          </ElFormItem>
          <ElFormItem label="实例规格" required>
            <CloudResourcePicker
              v-model="parameters.instance_type"
              :query="catalogQuery('instance_types')"
              :disabled="!parameters.zone"
            />
          </ElFormItem>
          <ElFormItem label="镜像" required>
            <CloudResourcePicker
              v-model="parameters.image_id"
              :query="catalogQuery('images')"
              :disabled="!parameters.instance_type"
            />
          </ElFormItem>
          <ElFormItem label="规格可用性">
            <CloudResourceAvailability :query="catalogQuery('availability')" />
          </ElFormItem>
          <ElFormItem label="VPC" required>
            <CloudResourcePicker
              v-model="parameters.vpc_id"
              :query="catalogQuery('vpcs')"
              :disabled="!parameters.zone"
            />
          </ElFormItem>
          <ElFormItem label="子网 / 交换机" required>
            <CloudResourcePicker
              v-model="parameters.subnet_id"
              :query="catalogQuery('subnets')"
              :disabled="!parameters.vpc_id"
            />
          </ElFormItem>
          <ElFormItem label="安全组" required>
            <CloudResourcePicker
              v-model="parameters.security_group_ids"
              :query="catalogQuery('security_groups')"
              :disabled="!parameters.vpc_id"
              multiple
            />
          </ElFormItem>
        </template>
        <template v-else>
          <ElFormItem label="镜像" required>
            <ElSelect v-model="parameters.image_id" class="w-full">
              <ElOption
                v-for="image in selectedVersion?.constraints.allowed_image_ids ?? []"
                :key="image"
                :value="image"
                :label="image"
              />
            </ElSelect>
          </ElFormItem>
          <ElFormItem label="实例规格" required>
            <ElSelect v-model="parameters.instance_type" class="w-full">
              <ElOption
                v-for="type in selectedVersion?.constraints.allowed_instance_types ?? []"
                :key="type"
                :value="type"
                :label="type"
              />
            </ElSelect>
          </ElFormItem>
          <ElFormItem label="网络" required>
            <ElSelect :model-value="parameters.subnet_id" class="w-full" @change="selectNetwork">
              <ElOption
                v-for="network in networks"
                :key="network.subnet_id"
                :value="network.subnet_id"
                :label="`${network.zone} / ${network.subnet_id}`"
              />
            </ElSelect>
          </ElFormItem>
          <ElFormItem label="VPC">{{ parameters.vpc_id || '选择网络后显示' }}</ElFormItem>
          <ElFormItem label="安全组" required>
            <ElSelect v-model="parameters.security_group_ids" multiple class="w-full">
              <ElOption v-for="group in securityGroups" :key="group" :value="group" :label="group" />
            </ElSelect>
          </ElFormItem>
        </template>
        <ElFormItem required>
          <template #label>
            <FormLabelHelp label="系统盘" :help="['单位 GiB，范围 20~2048；数据盘与磁盘类型由资源模板约束决定。']" />
          </template>
          <ElInputNumber v-model="parameters.system_disk_gb" :min="20" :max="2048" />
          <span class="ml-8px">GiB</span>
        </ElFormItem>
        <ElFormItem>
          <template #label>
            <FormLabelHelp
              label="交付通知"
              :help="['可选；主机创建完成后按所选通知模板发送交付信息，留空则不通知。']"
            />
          </template>
          <ElSelect
            v-model="notificationTemplate"
            clearable
            filterable
            remote
            :remote-method="loadNotifications"
            placeholder="可选；选择资源申请场景的通知模板"
            class="w-full"
            @visible-change="loadNotifications()"
          >
            <ElOption v-for="item in notificationTemplates" :key="item.id" :value="item.id" :label="item.name" />
          </ElSelect>
        </ElFormItem>
        <ElAlert
          title="提交申请不会立即创建主机。请在详情中生成计划、确认影响并等待审批。费用以云平台账单为准。"
          type="info"
          :closable="false"
          show-icon
        />
      </ElForm>
    </div>
    <template #footer>
      <ElSpace>
        <ElButton v-if="step === 1" @click="previous">上一步</ElButton>
        <ElButton v-if="step === 0" type="primary" :loading="loading" @click="next">下一步</ElButton>
        <ElButton v-else type="primary" :loading="loading" @click="submit">提交申请</ElButton>
      </ElSpace>
    </template>
  </ElDrawer>
</template>
