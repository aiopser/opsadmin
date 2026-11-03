<script setup lang="ts">
import { onMounted, ref, shallowRef } from 'vue';
import { fetchGetAssetSourceList } from '@/service/api/cmdb';
import { fetchCreationCredentials, saveCreationCredential } from '@/service/api/provisioning';
import type { CreationCredential } from '@/service/api/provisioning';

defineOptions({ name: 'ProvisioningCredentials' });
const credentials = shallowRef<CreationCredential[]>([]);
const sources = shallowRef<Api.Cmdb.AssetSourceRecord[]>([]);
const visible = ref(false);
const saving = ref(false);
const loading = ref(false);
const editId = ref<number>();
const model = ref({ name: '', source: undefined as number | undefined, key: '', secret: '', is_active: true });

async function load() {
  loading.value = true;
  try {
    const [a, b] = await Promise.all([
      fetchCreationCredentials(),
      fetchGetAssetSourceList({ current: 1, size: 1000, sourceType: 'cloud' })
    ]);
    credentials.value = a.data ?? [];
    sources.value = (b.data?.records ?? []).filter(item => ['aliyun', 'tencent'].includes(item.cloud_provider));
  } finally {
    loading.value = false;
  }
}

function open(row?: CreationCredential) {
  editId.value = row?.id;
  model.value = { name: row?.name ?? '', source: row?.source, key: '', secret: '', is_active: row?.is_active ?? true };
  visible.value = true;
}

function openCreate() {
  open();
}

function sourceName(id: number) {
  return sources.value.find(item => item.id === id)?.name ?? `#${id}`;
}

async function save() {
  if (!model.value.source || !model.value.name.trim() || saving.value) return;
  if (
    (!editId.value || model.value.key || model.value.secret) &&
    (!model.value.key.trim() || !model.value.secret.trim())
  ) {
    window.$message?.warning('请填写完整的 AccessKey ID 和 Secret');
    return;
  }
  const provider = sources.value.find(item => item.id === model.value.source)?.cloud_provider;
  const secret = credentialSecret(provider);
  saving.value = true;
  try {
    const { error } = await saveCreationCredential(
      { name: model.value.name, source: model.value.source, is_active: model.value.is_active, secret },
      editId.value
    );
    if (!error) {
      visible.value = false;
      await load();
    }
  } finally {
    saving.value = false;
  }
}

function clearSecrets() {
  model.value.key = '';
  model.value.secret = '';
}

function credentialSecret(provider?: string): Record<string, string> | undefined {
  if (!model.value.key) return undefined;
  if (provider === 'aliyun') return { access_key_id: model.value.key, access_key_secret: model.value.secret };
  return { secret_id: model.value.key, secret_key: model.value.secret };
}

onMounted(load);
</script>

<template>
  <div class="flex-col gap-16px">
    <div class="flex justify-end"><ElButton type="primary" @click="openCreate">新增创建凭据</ElButton></div>
    <ElTable v-loading="loading" :data="credentials" border>
      <ElTableColumn prop="name" label="凭据名称" min-width="160" show-overflow-tooltip />
      <ElTableColumn label="云账号" min-width="180" align="center">
        <template #default="{ row }">{{ sourceName(row.source) }}</template>
      </ElTableColumn>
      <ElTableColumn prop="revision" label="凭据版本" width="110" align="center" />
      <ElTableColumn label="状态" width="100" align="center">
        <template #default="{ row }">{{ row.is_active ? '启用' : '停用' }}</template>
      </ElTableColumn>
      <ElTableColumn label="操作" width="90" align="center">
        <template #default="{ row }"><ElButton link type="primary" @click="open(row)">编辑</ElButton></template>
      </ElTableColumn>
    </ElTable>
    <ElDrawer v-model="visible" :title="editId ? '编辑凭据' : '新增凭据'" size="560px" @closed="clearSecrets">
      <ElForm label-width="132px" label-suffix="：" require-asterisk-position="left">
        <ElFormItem label="凭据名称" required><ElInput v-model="model.name" maxlength="128" /></ElFormItem>
        <ElFormItem required>
          <template #label>
            <FormLabelHelp label="云账号" :help="['凭据归属的云账号；创建后不可更换。']" />
          </template>
          <ElSelect v-model="model.source" :disabled="Boolean(editId)" class="w-full">
            <ElOption v-for="item in sources" :key="item.id" :value="item.id" :label="item.name" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem :required="!editId || Boolean(model.key || model.secret)">
          <template #label>
            <FormLabelHelp label="AccessKey ID" :help="['创建主机使用的云 API 标识；编辑时留空保留原凭据。']" />
          </template>
          <ElInput v-model="model.key" autocomplete="off" :placeholder="editId ? '留空保留原凭据' : ''" />
        </ElFormItem>
        <ElFormItem :required="!editId || Boolean(model.key || model.secret)">
          <template #label>
            <FormLabelHelp label="Secret" :help="['加密保存且不回显；更新密钥后旧变更计划失效。']" />
          </template>
          <ElInput
            v-model="model.secret"
            type="password"
            show-password
            autocomplete="new-password"
            :placeholder="editId ? '留空保留原凭据' : ''"
          />
        </ElFormItem>
        <ElFormItem>
          <template #label>
            <FormLabelHelp label="状态" :help="['停用后不可用于创建主机；已创建资源不受影响。']" />
          </template>
          <ElRadioGroup v-model="model.is_active">
            <ElRadio :value="true">启用</ElRadio>
            <ElRadio :value="false">停用</ElRadio>
          </ElRadioGroup>
        </ElFormItem>
      </ElForm>
      <ElAlert
        title="创建凭据独立于资产读取凭据。更新密钥后，旧变更计划失效；已有密钥不回显。"
        type="info"
        :closable="false"
        show-icon
      />
      <template #footer><ElButton type="primary" :loading="saving" @click="save">保存</ElButton></template>
    </ElDrawer>
  </div>
</template>
