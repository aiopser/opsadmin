<script setup lang="ts">
import { computed, onMounted, ref, shallowRef } from 'vue';
import {
  fetchAddNotificationChannel,
  fetchDeleteNotificationChannel,
  fetchGetNotificationChannels,
  fetchUpdateNotificationChannel
} from '@/service/api';

defineOptions({ name: 'NotificationChannelPanel' });

type ChannelType = Api.Automation.NotificationChannelRecord['channelType'];

interface ChannelForm extends Api.Automation.NotificationChannelPayload {
  id?: number;
  hasSigningSecret?: boolean;
  payloadText: string;
  fromEmailText: string;
}

const CHANNEL_TYPE_OPTIONS: Array<{ label: string; value: ChannelType }> = [
  { label: '企业微信', value: 'wecom' },
  { label: '钉钉', value: 'dingtalk' },
  { label: '飞书', value: 'feishu' },
  { label: 'Webhook', value: 'webhook' },
  { label: '邮件', value: 'email' }
];

const channels = shallowRef<Api.Automation.NotificationChannelRecord[]>([]);
const loading = ref(false);
const drawerVisible = ref(false);
const submitting = ref(false);
const formRef = ref();
const form = ref<ChannelForm>(createEmptyForm());

const drawerTitle = computed(() => (form.value.id ? '编辑通知渠道' : '新增通知渠道'));
const formRules = computed(() => ({
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  secret:
    form.value.channelType !== 'email' && !form.value.id
      ? [{ required: true, message: '请输入 Webhook 地址', trigger: 'blur' }]
      : []
}));

function createEmptyForm(): ChannelForm {
  return {
    name: '',
    channelType: 'wecom',
    config: {},
    secret: '',
    signingSecret: '',
    hasSigningSecret: false,
    payloadText: '',
    fromEmailText: '',
    isActive: true
  };
}

async function loadChannels() {
  loading.value = true;
  try {
    const { data, error } = await fetchGetNotificationChannels();
    if (error || !data) return;
    channels.value = data;
  } finally {
    loading.value = false;
  }
}

function openDrawer(row?: Api.Automation.NotificationChannelRecord) {
  form.value = row
    ? {
        id: row.id,
        name: row.name,
        channelType: row.channelType,
        config: row.config,
        secret: '',
        signingSecret: '',
        hasSigningSecret: row.hasSigningSecret,
        payloadText: row.config?.payload ? JSON.stringify(row.config.payload, null, 2) : '',
        fromEmailText: typeof row.config?.fromEmail === 'string' ? row.config.fromEmail : '',
        isActive: row.isActive
      }
    : createEmptyForm();
  drawerVisible.value = true;
}

async function saveChannel() {
  const valid = await formRef.value?.validate().catch(() => false);
  if (!valid) return;

  let config: Record<string, unknown> = { ...form.value.config };
  if (form.value.channelType === 'webhook' && form.value.payloadText.trim()) {
    try {
      const value: unknown = JSON.parse(form.value.payloadText);
      if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('invalid payload');
      config = { ...config, payload: value };
    } catch {
      window.$message?.error('Webhook 请求体必须是 JSON 对象');
      return;
    }
  }
  if (form.value.channelType === 'webhook' && !form.value.payloadText.trim()) {
    delete config.payload;
  }

  const fromEmail = form.value.fromEmailText.trim();
  if (form.value.channelType === 'email' && fromEmail) {
    config.fromEmail = fromEmail;
  } else {
    delete config.fromEmail;
  }

  const { id, name, channelType, secret, signingSecret, isActive } = form.value;
  const signingSecretValue = channelType === 'dingtalk' || channelType === 'feishu' ? signingSecret : '';
  const payload = { name, channelType, secret, signingSecret: signingSecretValue, isActive, config };
  submitting.value = true;
  try {
    const result = id ? await fetchUpdateNotificationChannel(id, payload) : await fetchAddNotificationChannel(payload);
    if (result.error) return;
    drawerVisible.value = false;
    window.$notification?.success(id ? '渠道已更新' : '渠道已创建');
    await loadChannels();
  } finally {
    submitting.value = false;
  }
}

async function deleteChannel(id: number) {
  const { error } = await fetchDeleteNotificationChannel(id);
  if (error) return;
  window.$notification?.success('渠道已删除');
  await loadChannels();
}

function channelTypeText(type: ChannelType) {
  return CHANNEL_TYPE_OPTIONS.find(item => item.value === type)?.label ?? type;
}

onMounted(loadChannels);
</script>

<template>
  <div class="flex-col-stretch">
    <ElCard class="card-wrapper">
      <template #header>
        <div class="flex flex-wrap items-center justify-between gap-8px">
          <div class="min-w-0 flex flex-wrap items-baseline gap-8px">
            <p>通知渠道</p>
            <span class="text-13px text-gray-500">维护企业微信、钉钉、飞书与 Webhook 群机器人地址</span>
          </div>
          <div class="flex items-center gap-8px">
            <ElButton @click="loadChannels">刷新</ElButton>
            <ElButton type="primary" @click="openDrawer()">新增渠道</ElButton>
          </div>
        </div>
      </template>
      <ElTable v-loading="loading" :data="channels" border class="w-full" row-key="id">
        <ElTableColumn
          prop="name"
          label="名称"
          min-width="180"
          align="center"
          header-align="center"
          show-overflow-tooltip
        />
        <ElTableColumn label="类型" width="120" align="center" header-align="center">
          <template #default="{ row }">{{ channelTypeText(row.channelType) }}</template>
        </ElTableColumn>
        <ElTableColumn label="状态" width="100" align="center" header-align="center">
          <template #default="{ row }">
            <ElTag size="small" :type="row.isActive ? 'success' : 'info'">{{ row.isActive ? '启用' : '停用' }}</ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn label="操作" width="160" align="center" header-align="center">
          <template #default="{ row }">
            <ElButton type="primary" plain size="small" @click="openDrawer(row)">编辑</ElButton>
            <ElPopconfirm title="确定删除该渠道？已被模板引用时无法删除。" @confirm="deleteChannel(row.id)">
              <template #reference>
                <ElButton type="danger" plain size="small">删除</ElButton>
              </template>
            </ElPopconfirm>
          </template>
        </ElTableColumn>
        <template #empty>
          <ElEmpty description="暂无通知渠道" :image-size="80">
            <ElButton type="primary" @click="openDrawer()">新增渠道</ElButton>
          </ElEmpty>
        </template>
      </ElTable>

      <ElDrawer
        v-model="drawerVisible"
        class="notification-channel-drawer"
        :title="drawerTitle"
        size="min(720px, 100vw)"
        :close-on-click-modal="false"
      >
        <ElForm
          ref="formRef"
          :model="form"
          :rules="formRules"
          label-position="top"
          label-suffix="："
          require-asterisk-position="left"
        >
          <div class="grid grid-cols-1 gap-x-16px md:grid-cols-2">
            <ElFormItem label="名称" prop="name">
              <ElInput v-model="form.name" placeholder="请输入名称" maxlength="64" />
            </ElFormItem>
            <ElFormItem>
              <template #label>
                <FormLabelHelp
                  label="渠道类型"
                  help="企业微信、钉钉、飞书与 Webhook 均为群机器人地址；邮件渠道使用全局 SMTP 服务器"
                />
              </template>
              <ElSelect v-model="form.channelType" class="w-full">
                <ElOption
                  v-for="item in CHANNEL_TYPE_OPTIONS"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
                />
              </ElSelect>
            </ElFormItem>
            <ElFormItem v-if="form.channelType !== 'email'" prop="secret" class="md:col-span-2">
              <template #label>
                <FormLabelHelp label="Webhook 地址" help="编辑时留空表示保持原地址；地址加密保存，不在列表展示" />
              </template>
              <ElInput
                v-model="form.secret"
                type="password"
                show-password
                autocomplete="off"
                placeholder="机器人或 Webhook 地址"
              />
            </ElFormItem>
            <ElFormItem
              v-if="form.channelType === 'dingtalk' || form.channelType === 'feishu'"
              prop="signingSecret"
              class="md:col-span-2"
            >
              <template #label>
                <FormLabelHelp label="签名密钥" help="机器人开启加签后填写；编辑时留空表示保持原密钥" />
              </template>
              <ElInput
                v-model="form.signingSecret"
                type="password"
                show-password
                autocomplete="off"
                :placeholder="form.hasSigningSecret ? '已配置，留空表示不修改' : '可选，未开启加签可留空'"
              />
            </ElFormItem>
            <ElFormItem v-if="form.channelType === 'email'" class="md:col-span-2">
              <template #label>
                <FormLabelHelp label="发件人" help="留空使用服务端全局默认发件人；收件人由通知模板的接收人模板决定" />
              </template>
              <ElInput v-model="form.fromEmailText" placeholder="可选，留空使用服务端默认发件人" />
            </ElFormItem>
            <ElFormItem v-if="form.channelType === 'webhook'" class="md:col-span-2">
              <template #label>
                <FormLabelHelp label="请求体模板" help="仅 Webhook 类型生效；留空使用文本消息格式" />
              </template>
              <ElInput
                v-model="form.payloadText"
                type="textarea"
                :rows="5"
                placeholder='可选，如 {"text": "{{ message }}"}；留空沿用文本消息格式'
              />
            </ElFormItem>
            <ElFormItem>
              <template #label>
                <FormLabelHelp label="启用" help="停用后引用该渠道的通知模板不会发送" />
              </template>
              <ElSwitch v-model="form.isActive" />
            </ElFormItem>
          </div>
        </ElForm>
        <template #footer>
          <div class="flex items-center justify-end gap-8px">
            <ElButton @click="drawerVisible = false">取消</ElButton>
            <ElButton type="primary" :loading="submitting" @click="saveChannel">保存</ElButton>
          </div>
        </template>
      </ElDrawer>
    </ElCard>
  </div>
</template>
