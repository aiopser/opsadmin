<script setup lang="ts">
import { onMounted, ref, shallowRef } from 'vue';
import {
  createResourceTemplate,
  createResourceVersion,
  fetchResourceTemplates,
  fetchResourceVersions,
  publishResourceVersion
} from '@/service/api/provisioning';
import type { CatalogKind, ResourceTemplate, ResourceVersion } from '@/service/api/provisioning';
import { fetchGetAssetSourceList } from '@/service/api/cmdb';
import CloudResourcePicker from '@/components/business/cloud-resource-picker/index.vue';
import CreationCredentials from './credentials.vue';

defineOptions({ name: 'ProvisioningResourceTemplates' });
const templates = shallowRef<ResourceTemplate[]>([]);
const versions = shallowRef<ResourceVersion[]>([]);
const loading = ref(false);
const saving = ref(false);
const visible = ref(false);
const form = ref({ name: '', provider: 'aliyun' as 'aliyun' | 'tencent', description: '' });
const versionVisible = ref(false);
const selected = shallowRef<ResourceTemplate>();
const versionNumber = ref(1);
const regions = ref('');
const bundleDigest = ref('');
const tab = ref('templates');
const sources = shallowRef<Api.Cmdb.AssetSourceRecord[]>([]);
const scopeMode = ref('discovery');
const discovery = ref({
  imagePrefix: '',
  cpuMin: 1,
  cpuMax: 64,
  memoryMin: 1,
  memoryMax: 256,
  networkTagKey: '',
  networkTagValue: '',
  groupTagKey: '',
  groupTagValue: ''
});
const previewVersion = shallowRef<ResourceVersion>();
const previewVisible = ref(false);
const previewSource = ref<number>();
const previewRegion = ref('');
const previewKind = ref<CatalogKind>('images');
const previewSelection = ref<string | string[]>('');
const scope = ref({
  source: undefined as number | undefined,
  zone: '',
  vpc: '',
  subnet: '',
  groups: '',
  images: '',
  types: ''
});

async function load() {
  loading.value = true;
  try {
    const [a, b, c] = await Promise.all([
      fetchResourceTemplates(),
      fetchResourceVersions(),
      fetchGetAssetSourceList({ current: 1, size: 1000, sourceType: 'cloud' })
    ]);
    if (!a.error) templates.value = a.data ?? [];
    if (!b.error) versions.value = b.data ?? [];
    sources.value = c.data?.records ?? [];
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  form.value = { name: '', provider: 'aliyun', description: '' };
  visible.value = true;
}

async function save() {
  if (!form.value.name.trim() || saving.value) return;
  saving.value = true;
  try {
    const { error } = await createResourceTemplate({ ...form.value, is_active: true });
    if (!error) {
      visible.value = false;
      await load();
    }
  } finally {
    saving.value = false;
  }
}

function openVersion(row: ResourceTemplate) {
  selected.value = row;
  versionNumber.value =
    Math.max(0, ...versions.value.filter(item => item.template === row.id).map(item => item.number)) + 1;
  regions.value = '';
  bundleDigest.value = '';
  scope.value = { source: undefined, zone: '', vpc: '', subnet: '', groups: '', images: '', types: '' };
  scopeMode.value = 'discovery';
  discovery.value = {
    imagePrefix: '',
    cpuMin: 1,
    cpuMax: 64,
    memoryMin: 1,
    memoryMax: 256,
    networkTagKey: '',
    networkTagValue: '',
    groupTagKey: '',
    groupTagValue: ''
  };
  versionVisible.value = true;
}

async function saveVersion() {
  if (
    !selected.value ||
    !regions.value.trim() ||
    !scope.value.source ||
    (scopeMode.value === 'fixed' &&
      (!scope.value.zone ||
        !scope.value.vpc ||
        !scope.value.subnet ||
        !scope.value.groups ||
        !scope.value.images ||
        !scope.value.types)) ||
    !/^[a-f0-9]{64}$/.test(bundleDigest.value) ||
    saving.value
  ) {
    window.$message?.warning('请填写地域、网络授权范围、镜像规格及审核后的模板包摘要');
    return;
  }
  saving.value = true;
  try {
    const split = (value: string) =>
      value
        .split(/[,，]/)
        .map(item => item.trim())
        .filter(Boolean);
    const { error } = await createResourceVersion({
      template: selected.value.id,
      number: versionNumber.value,
      constraints: {
        regions: [regions.value.trim()],
        bundle_digest: bundleDigest.value,
        ...(scopeMode.value === 'discovery'
          ? {
              schemaVersion: 2 as const,
              selectors: {
                sourceIds: [scope.value.source],
                imageNamePrefix: discovery.value.imagePrefix.trim(),
                cpuMin: discovery.value.cpuMin,
                cpuMax: discovery.value.cpuMax,
                memoryMinMiB: discovery.value.memoryMin * 1024,
                memoryMaxMiB: discovery.value.memoryMax * 1024,
                networkTags: discovery.value.networkTagKey.trim()
                  ? { [discovery.value.networkTagKey.trim()]: discovery.value.networkTagValue.trim() }
                  : {},
                securityGroupTags: discovery.value.groupTagKey.trim()
                  ? { [discovery.value.groupTagKey.trim()]: discovery.value.groupTagValue.trim() }
                  : {}
              }
            }
          : {
              allowed_image_ids: split(scope.value.images),
              allowed_instance_types: split(scope.value.types),
              networks: [
                {
                  source_id: scope.value.source,
                  region: regions.value.trim(),
                  zone: scope.value.zone,
                  vpc_id: scope.value.vpc,
                  subnet_id: scope.value.subnet,
                  security_group_ids: split(scope.value.groups)
                }
              ]
            })
      }
    });
    if (!error) {
      versionVisible.value = false;
      await load();
    }
  } finally {
    saving.value = false;
  }
}

async function publish(version: ResourceVersion) {
  saving.value = true;
  try {
    const { error } = await publishResourceVersion(version.id);
    if (!error) await load();
  } finally {
    saving.value = false;
  }
}

function templateVersions(id: number) {
  return versions.value.filter(item => item.template === id);
}

function browse(version: ResourceVersion) {
  previewVersion.value = version;
  previewSource.value = version.constraints.selectors?.sourceIds[0] ?? version.constraints.networks?.[0]?.source_id;
  previewRegion.value = version.constraints.regions[0] ?? '';
  previewSelection.value = '';
  previewVisible.value = true;
}

function previewQuery() {
  if (!previewVersion.value || !previewSource.value || !previewRegion.value) return undefined;
  return {
    kind: previewKind.value,
    versionId: previewVersion.value.id,
    sourceId: previewSource.value,
    region: previewRegion.value
  };
}

onMounted(load);
</script>

<template>
  <div class="flex-col-stretch gap-16px">
    <ElCard class="card-wrapper" shadow="never">
      <ElTabs v-model="tab">
        <ElTabPane label="资源模板" name="templates" />
        <ElTabPane label="创建凭据" name="credentials" />
      </ElTabs>
      <CreationCredentials v-if="tab === 'credentials'" />
      <div v-else>
        <div class="mb-16px flex items-center justify-between">
          <span>资源模板</span>
          <ElSpace>
            <ElButton @click="load">刷新</ElButton>
            <ElButton type="primary" @click="openCreate">新增模板</ElButton>
          </ElSpace>
        </div>
        <ElTable v-loading="loading" :data="templates" border>
          <ElTableColumn prop="name" label="模板名称" min-width="180" show-overflow-tooltip />
          <ElTableColumn label="云平台" width="120" align="center">
            <template #default="{ row }">{{ row.provider === 'aliyun' ? '阿里云' : '腾讯云' }}</template>
          </ElTableColumn>
          <ElTableColumn prop="description" label="描述" min-width="200" show-overflow-tooltip />
          <ElTableColumn label="版本" min-width="240">
            <template #default="{ row }">
              <ElSpace wrap>
                <span v-for="version in templateVersions(row.id)" :key="version.id">
                  v{{ version.number }} · {{ version.status === 'published' ? '已发布' : '草稿' }}
                  <ElButton link type="primary" @click="browse(version)">浏览资源</ElButton>
                  <ElButton
                    v-if="version.status === 'draft'"
                    link
                    type="primary"
                    :loading="saving"
                    @click="publish(version)"
                  >
                    发布
                  </ElButton>
                </span>
              </ElSpace>
            </template>
          </ElTableColumn>
          <ElTableColumn label="操作" width="140" align="center">
            <template #default="{ row }">
              <ElButton type="primary" plain size="small" @click="openVersion(row)">新建版本</ElButton>
            </template>
          </ElTableColumn>
        </ElTable>
      </div>
    </ElCard>
    <ElDrawer v-model="visible" title="新增资源模板" size="560px">
      <ElForm label-width="100px" label-suffix="：" require-asterisk-position="left">
        <ElFormItem label="模板名称" required><ElInput v-model="form.name" maxlength="128" /></ElFormItem>
        <ElFormItem required>
          <template #label>
            <FormLabelHelp label="云平台" :help="['决定可选的云账号与资源类型；请与后续版本使用的账号保持一致。']" />
          </template>
          <ElRadioGroup v-model="form.provider">
            <ElRadio value="aliyun">阿里云</ElRadio>
            <ElRadio value="tencent">腾讯云</ElRadio>
          </ElRadioGroup>
        </ElFormItem>
        <ElFormItem label="描述"><ElInput v-model="form.description" type="textarea" /></ElFormItem>
      </ElForm>
      <template #footer><ElButton type="primary" :loading="saving" @click="save">保存</ElButton></template>
    </ElDrawer>
    <ElDrawer v-model="versionVisible" title="新建资源模板版本" size="600px">
      <ElForm label-width="132px" label-suffix="：" require-asterisk-position="left">
        <ElFormItem label="模板">{{ selected?.name }}</ElFormItem>
        <ElFormItem required>
          <template #label>
            <FormLabelHelp label="版本号" :help="['同一模板内递增；发布后不可修改。']" />
          </template>
          <ElInputNumber v-model="versionNumber" :min="1" />
        </ElFormItem>
        <ElFormItem required>
          <template #label>
            <FormLabelHelp
              label="允许地域"
              :help="['多个地域用英文逗号分隔，如 cn-shanghai, cn-hangzhou；按规则发现受此限制。']"
            />
          </template>
          <ElInput v-model="regions" placeholder="例如 cn-shanghai" />
        </ElFormItem>
        <ElFormItem required>
          <template #label>
            <FormLabelHelp label="云账号" :help="['仅同厂商账号可选；版本绑定该账号的凭据与地域范围。']" />
          </template>
          <ElSelect v-model="scope.source" class="w-full">
            <ElOption
              v-for="source in sources"
              :key="source.id"
              :value="source.id"
              :label="source.name"
              :disabled="source.cloud_provider !== selected?.provider"
            />
          </ElSelect>
        </ElFormItem>
        <ElFormItem required>
          <template #label>
            <FormLabelHelp
              label="授权方式"
              :help="['按规则发现：按镜像、规格、标签等条件动态读取账号资源；固定 ID 清单：只允许指定资源。']"
            />
          </template>
          <ElRadioGroup v-model="scopeMode">
            <ElRadio value="discovery">按规则发现</ElRadio>
            <ElRadio value="fixed">固定 ID 清单</ElRadio>
          </ElRadioGroup>
        </ElFormItem>
        <template v-if="scopeMode === 'discovery'">
          <ElFormItem>
            <template #label>
              <FormLabelHelp label="镜像名称前缀" :help="['按名称前缀过滤可用镜像；留空不限制。']" />
            </template>
            <ElInput v-model="discovery.imagePrefix" placeholder="可选；留空允许账号内全部可用镜像" />
          </ElFormItem>
          <ElFormItem>
            <template #label>
              <FormLabelHelp label="CPU 范围" :help="['按 CPU 核数过滤规格；范围包含两端。']" />
            </template>
            <ElInputNumber v-model="discovery.cpuMin" :min="1" :max="discovery.cpuMax" />
            <span class="mx-8px">至</span>
            <ElInputNumber v-model="discovery.cpuMax" :min="discovery.cpuMin" :max="1024" />
            <span class="ml-8px">核</span>
          </ElFormItem>
          <ElFormItem>
            <template #label>
              <FormLabelHelp label="内存范围" :help="['按内存大小过滤规格；范围包含两端。']" />
            </template>
            <ElInputNumber v-model="discovery.memoryMin" :min="1" :max="discovery.memoryMax" />
            <span class="mx-8px">至</span>
            <ElInputNumber v-model="discovery.memoryMax" :min="discovery.memoryMin" :max="1024" />
            <span class="ml-8px">GiB</span>
          </ElFormItem>
          <ElFormItem>
            <template #label>
              <FormLabelHelp label="网络标签" :help="['按标签过滤可用 VPC / 子网；标签键留空表示不限制。']" />
            </template>
            <div class="w-full flex gap-8px">
              <ElInput v-model="discovery.networkTagKey" placeholder="标签键（可选）" />
              <ElInput v-model="discovery.networkTagValue" placeholder="标签值" />
            </div>
          </ElFormItem>
          <ElFormItem>
            <template #label>
              <FormLabelHelp label="安全组标签" :help="['按标签过滤可用安全组；标签键留空表示不限制。']" />
            </template>
            <div class="w-full flex gap-8px">
              <ElInput v-model="discovery.groupTagKey" placeholder="标签键（可选）" />
              <ElInput v-model="discovery.groupTagValue" placeholder="标签值" />
            </div>
          </ElFormItem>
          <ElAlert
            title="发现范围受所选账号和地域约束；未填写标签时不按标签限制。保存草稿后可浏览云资源，核对范围后再发布。"
            type="info"
            :closable="false"
            class="mb-16px"
          />
        </template>
        <template v-else>
          <ElFormItem label="可用区" required><ElInput v-model="scope.zone" /></ElFormItem>
          <ElFormItem label="VPC ID" required><ElInput v-model="scope.vpc" /></ElFormItem>
          <ElFormItem label="子网 ID" required><ElInput v-model="scope.subnet" /></ElFormItem>
          <ElFormItem label="安全组 ID" required>
            <ElInput v-model="scope.groups" placeholder="多个 ID 用逗号分隔" />
          </ElFormItem>
          <ElFormItem label="允许镜像" required>
            <ElInput v-model="scope.images" placeholder="多个镜像 ID 用逗号分隔" />
          </ElFormItem>
          <ElFormItem label="允许规格" required>
            <ElInput v-model="scope.types" placeholder="多个实例规格用逗号分隔" />
          </ElFormItem>
        </template>
        <ElFormItem required>
          <template #label>
            <FormLabelHelp
              label="模板包摘要"
              :help="['Terraform 模板包的 SHA256 摘要，由管理员在专用执行环境审核后提供；发布后不可修改。']"
            />
          </template>
          <ElInput v-model="bundleDigest" maxlength="64" />
        </ElFormItem>
      </ElForm>
      <ElAlert
        title="由管理员在专用执行环境安装并审核 Terraform 模板包，填入锁定包的摘要。发布后不可修改。"
        type="info"
        :closable="false"
        show-icon
      />
      <template #footer><ElButton type="primary" :loading="saving" @click="saveVersion">保存草稿</ElButton></template>
    </ElDrawer>
    <ElDrawer v-model="previewVisible" title="浏览云资源" size="680px">
      <ElForm label-width="100px" label-suffix="：" require-asterisk-position="left">
        <ElFormItem label="云账号" required>
          <ElSelect v-model="previewSource" class="w-full">
            <ElOption v-for="source in sources" :key="source.id" :value="source.id" :label="source.name" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="地域" required>
          <ElSelect v-model="previewRegion" class="w-full">
            <ElOption
              v-for="region in previewVersion?.constraints.regions ?? []"
              :key="region"
              :value="region"
              :label="region"
            />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="资源类别">
          <ElRadioGroup v-model="previewKind">
            <ElRadio value="images">镜像</ElRadio>
            <ElRadio value="instance_types">规格</ElRadio>
            <ElRadio value="vpcs">VPC</ElRadio>
            <ElRadio value="subnets">子网</ElRadio>
            <ElRadio value="security_groups">安全组</ElRadio>
          </ElRadioGroup>
        </ElFormItem>
        <ElFormItem label="云资源">
          <CloudResourcePicker v-model="previewSelection" :query="previewQuery()" configuration />
        </ElFormItem>
      </ElForm>
      <ElAlert
        title="此处为管理员账号目录，不代表申请人可选择全部资源；申请目录仍会按已发布模板规则筛选。"
        type="info"
        :closable="false"
      />
    </ElDrawer>
  </div>
</template>
