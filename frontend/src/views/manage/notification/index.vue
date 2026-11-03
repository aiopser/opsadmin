<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import {
  fetchGetNotificationEmailSettings,
  fetchSaveNotificationEmailSettings,
  fetchTestNotificationEmail,
  fetchTestNotificationEmailConnection
} from '@/service/api';
import { useAuth } from '@/hooks/business/auth';
import SvgIcon from '@/components/custom/svg-icon.vue';
import NotificationChannelPanel from './modules/notification-channel-panel.vue';
import NotificationHistoryPanel from './modules/notification-history-panel.vue';

defineOptions({ name: 'ManageNotification' });

type EmailSettings = Api.SystemManage.NotificationEmailSettings;
type EmailProtocol = Api.SystemManage.NotificationEmailProtocol;

const DEFAULT_TITLE_PREFIX = 'DevOps消息通知：';
const PROTOCOL_OPTIONS: Array<{ label: string; value: EmailProtocol; port: number }> = [
  { label: 'SMTP', value: 'smtp', port: 25 },
  { label: 'SECURE_SMTP', value: 'secure_smtp', port: 465 }
];

const { hasAuth } = useAuth();

const activeTab = ref('email');
const loading = ref(false);
const saving = ref(false);
const connectionTesting = ref(false);
const drawerVisible = ref(false);
const drawerMode = ref<'create' | 'edit'>('create');
const helpVisible = ref(false);
const formRef = ref();
const password = ref('');
const settings = ref<EmailSettings>(createEmptySettings());
const form = ref<EmailSettings>(createEmptySettings());
const testDialogVisible = ref(false);
const testRecipient = ref('');
const testSending = ref(false);

const drawerTitle = computed(() => (drawerMode.value === 'create' ? '新建邮件服务器' : '编辑邮件服务器'));
const configured = computed(() => settings.value.configured);
const encryptionText = computed(() => {
  if (settings.value.protocol === 'secure_smtp') return 'SSL';
  return settings.value.useTls ? 'STARTTLS' : '不加密';
});
const tlsHelp = computed(() =>
  form.value.protocol === 'secure_smtp' ? 'SECURE_SMTP 已使用 SSL 加密，无需 STARTTLS' : '开启后使用 STARTTLS 加密连接'
);
const passwordPlaceholder = computed(() => (form.value.hasPassword ? '已配置，留空表示不修改' : '请输入密码'));

const rules = {
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  fromEmail: [
    { required: true, message: '请输入发送邮箱', trigger: 'blur' },
    { type: 'email' as const, message: '发送邮箱格式不正确', trigger: 'blur' }
  ],
  host: [{ required: true, message: '请输入SMTP主机', trigger: 'blur' }],
  port: [{ required: true, message: '请输入SMTP端口', trigger: 'blur' }],
  timeout: [{ required: true, message: '请输入超时秒数', trigger: 'blur' }]
};

function createEmptySettings(): EmailSettings {
  return {
    name: '',
    description: '',
    fromEmail: '',
    titlePrefix: DEFAULT_TITLE_PREFIX,
    protocol: 'smtp',
    host: '',
    port: 25,
    timeout: 10,
    useTls: false,
    username: '',
    hasPassword: false,
    configured: false
  };
}

async function loadSettings() {
  loading.value = true;
  try {
    const { data, error } = await fetchGetNotificationEmailSettings();
    if (error || !data) return;
    settings.value = data;
  } finally {
    loading.value = false;
  }
}

function openCreateDrawer() {
  drawerMode.value = 'create';
  form.value = createEmptySettings();
  password.value = '';
  drawerVisible.value = true;
}

function openEditDrawer() {
  drawerMode.value = 'edit';
  form.value = { ...settings.value };
  password.value = '';
  drawerVisible.value = true;
}

function handleProtocolChange(protocol: EmailProtocol) {
  const option = PROTOCOL_OPTIONS.find(item => item.value === protocol);
  if (option) {
    form.value.port = option.port;
  }
  if (protocol === 'secure_smtp') {
    form.value.useTls = false;
  }
}

async function handleConnectionTest() {
  if (!form.value.host.trim()) {
    window.$message?.warning('请先填写 SMTP 主机');
    return;
  }
  connectionTesting.value = true;
  try {
    const { error } = await fetchTestNotificationEmailConnection({
      protocol: form.value.protocol,
      host: form.value.host.trim(),
      port: form.value.port,
      timeout: form.value.timeout,
      useTls: form.value.useTls,
      username: form.value.username.trim(),
      password: password.value
    });
    if (error) return;
    window.$notification?.success('连接成功');
  } finally {
    connectionTesting.value = false;
  }
}

async function handleSave() {
  const valid = await formRef.value?.validate().catch(() => false);
  if (!valid) return;
  saving.value = true;
  try {
    const { data, error } = await fetchSaveNotificationEmailSettings({
      name: form.value.name.trim(),
      description: form.value.description.trim(),
      fromEmail: form.value.fromEmail.trim(),
      titlePrefix: form.value.titlePrefix,
      protocol: form.value.protocol,
      host: form.value.host.trim(),
      port: form.value.port,
      timeout: form.value.timeout,
      useTls: form.value.useTls,
      username: form.value.username.trim(),
      password: password.value
    });
    if (error || !data) return;
    settings.value = data;
    drawerVisible.value = false;
    password.value = '';
    window.$notification?.success('邮件服务器配置已保存');
  } finally {
    saving.value = false;
  }
}

function openTestDialog() {
  testRecipient.value = settings.value.fromEmail;
  testDialogVisible.value = true;
}

async function submitTest() {
  const recipient = testRecipient.value.trim();
  if (!recipient) {
    window.$message?.warning('请输入收件人邮箱');
    return;
  }
  testSending.value = true;
  try {
    const { error } = await fetchTestNotificationEmail({ recipient });
    if (error) return;
    testDialogVisible.value = false;
    window.$notification?.success('测试邮件已发送，请检查收件箱');
  } finally {
    testSending.value = false;
  }
}

onMounted(loadSettings);
</script>

<template>
  <div class="min-h-500px flex-col-stretch overflow-y-auto">
    <ElTabs v-model="activeTab" class="flex-shrink-0">
      <ElTabPane label="邮件服务器" name="email">
        <ElCard v-if="!configured" v-loading="loading" class="mt-16px card-wrapper">
          <div class="min-h-420px flex items-center justify-center px-16px">
            <div class="max-w-660px flex flex-col items-center gap-24px md:flex-row">
              <SvgIcon icon="carbon:email" class="shrink-0 text-80px text-gray-300" />
              <div class="text-center md:text-left">
                <h3 class="text-wrap-balance text-16px font-600">SMTP邮件服务器</h3>
                <p class="text-wrap-pretty mt-8px text-14px text-gray-500 leading-6">
                  支持通过邮件来进行事件通知、消息通知、告警等，请配置邮件服务器进行邮件发送。
                  <ElLink type="primary" @click="helpVisible = true">查看邮件服务器配置说明</ElLink>
                </p>
                <ElButton
                  v-if="hasAuth('sys:notification:update')"
                  type="primary"
                  class="mt-16px"
                  @click="openCreateDrawer"
                >
                  <template #icon>
                    <SvgIcon icon="carbon:add" />
                  </template>
                  创建SMTP邮件服务器
                </ElButton>
              </div>
            </div>
          </div>
        </ElCard>

        <ElCard v-else v-loading="loading" class="mt-16px card-wrapper">
          <template #header>
            <div class="flex flex-wrap items-center justify-between gap-8px">
              <div class="min-w-0 flex flex-wrap items-center gap-8px">
                <span class="text-15px font-500">{{ settings.name || settings.host }}</span>
                <ElTag size="small" type="success">已配置</ElTag>
              </div>
              <div class="flex items-center gap-8px">
                <ElButton v-if="hasAuth('sys:notification:test')" @click="openTestDialog">发送测试邮件</ElButton>
                <ElButton v-if="hasAuth('sys:notification:update')" type="primary" @click="openEditDrawer">
                  编辑配置
                </ElButton>
              </div>
            </div>
          </template>
          <ElDescriptions :column="2" border>
            <ElDescriptionsItem label="发送邮箱">{{ settings.fromEmail || '-' }}</ElDescriptionsItem>
            <ElDescriptionsItem label="SMTP 主机">{{ settings.host }}</ElDescriptionsItem>
            <ElDescriptionsItem label="端口">{{ settings.port }}</ElDescriptionsItem>
            <ElDescriptionsItem label="协议">
              {{ settings.protocol === 'secure_smtp' ? 'SECURE_SMTP' : 'SMTP' }}
            </ElDescriptionsItem>
            <ElDescriptionsItem label="加密方式">{{ encryptionText }}</ElDescriptionsItem>
            <ElDescriptionsItem label="超时">
              {{ settings.timeout ? `${settings.timeout} 秒` : '不超时' }}
            </ElDescriptionsItem>
            <ElDescriptionsItem label="用户名">{{ settings.username || '-' }}</ElDescriptionsItem>
            <ElDescriptionsItem label="密码">{{ settings.hasPassword ? '已配置' : '未配置' }}</ElDescriptionsItem>
            <ElDescriptionsItem label="标题前缀" :span="2">{{ settings.titlePrefix || '未设置' }}</ElDescriptionsItem>
            <ElDescriptionsItem label="描述" :span="2">{{ settings.description || '-' }}</ElDescriptionsItem>
          </ElDescriptions>
        </ElCard>
      </ElTabPane>

      <ElTabPane label="通知渠道" name="channels">
        <NotificationChannelPanel class="mt-16px" />
      </ElTabPane>

      <ElTabPane label="历史数据清理" name="history">
        <NotificationHistoryPanel class="mt-16px" />
      </ElTabPane>
    </ElTabs>

    <ElDrawer
      v-model="drawerVisible"
      class="notification-email-drawer"
      :title="drawerTitle"
      size="min(720px, 100vw)"
      :close-on-click-modal="false"
    >
      <ElForm
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        label-suffix="："
        require-asterisk-position="left"
      >
        <p class="mb-16px text-14px font-600">配置基本信息</p>
        <div class="grid grid-cols-1 gap-x-16px md:grid-cols-2">
          <ElFormItem label="名称" prop="name">
            <ElInput v-model="form.name" placeholder="请输入名称" maxlength="64" />
          </ElFormItem>
          <ElFormItem prop="fromEmail">
            <template #label>
              <FormLabelHelp label="发送邮箱" help="使用此地址进行邮件发送" />
            </template>
            <ElInput v-model="form.fromEmail" placeholder="请输入发送邮箱" />
          </ElFormItem>
          <ElFormItem label="描述" class="md:col-span-2">
            <ElInput v-model="form.description" type="textarea" :rows="2" placeholder="请输入描述" maxlength="200" />
          </ElFormItem>
          <ElFormItem class="md:col-span-2">
            <template #label>
              <FormLabelHelp label="标题前缀" help="设置发送的邮件标题前缀" />
            </template>
            <ElInput v-model="form.titlePrefix" placeholder="请输入标题前缀" maxlength="64" />
          </ElFormItem>
        </div>

        <p class="mb-16px mt-8px text-14px font-600">SMTP 主机设置</p>
        <div class="grid grid-cols-1 gap-x-16px md:grid-cols-2">
          <ElFormItem prop="protocol">
            <template #label>
              <FormLabelHelp label="协议" help="SMTP 通过明文或 STARTTLS 发送；SECURE_SMTP 使用 SSL 直连" />
            </template>
            <ElSelect v-model="form.protocol" class="w-full" @change="handleProtocolChange">
              <ElOption v-for="item in PROTOCOL_OPTIONS" :key="item.value" :label="item.label" :value="item.value" />
            </ElSelect>
          </ElFormItem>
          <ElFormItem>
            <template #label>
              <FormLabelHelp label="TLS" :help="tlsHelp" />
            </template>
            <ElSwitch v-model="form.useTls" :disabled="form.protocol === 'secure_smtp'" />
          </ElFormItem>
          <ElFormItem prop="host" class="md:col-span-2">
            <template #label>
              <FormLabelHelp label="SMTP主机" help="SMTP 服务器主机地址" />
            </template>
            <ElInput v-model="form.host" placeholder="请输入SMTP主机" />
          </ElFormItem>
          <ElFormItem prop="port">
            <template #label>
              <FormLabelHelp label="SMTP端口" help="SMTP 默认 25，SECURE_SMTP 默认 465；切换协议时自动带出" />
            </template>
            <ElInputNumber v-model="form.port" :min="1" :max="65535" controls-position="right" class="w-full" />
          </ElFormItem>
          <ElFormItem prop="timeout">
            <template #label>
              <FormLabelHelp label="超时秒" help="超时以秒为单位，0 表示永不超时" />
            </template>
            <ElInputNumber v-model="form.timeout" :min="0" :max="3600" controls-position="right" class="w-full" />
          </ElFormItem>
          <ElFormItem>
            <template #label>
              <FormLabelHelp label="用户名" help="可选，SMTP 需要身份验证时填写" />
            </template>
            <ElInput v-model="form.username" placeholder="请输入用户名" autocomplete="off" />
          </ElFormItem>
          <ElFormItem>
            <template #label>
              <FormLabelHelp label="密码" help="可选；已保存的密码留空表示不修改" />
            </template>
            <ElInput
              v-model="password"
              type="password"
              show-password
              autocomplete="new-password"
              :placeholder="passwordPlaceholder"
            />
          </ElFormItem>
        </div>
      </ElForm>
      <template #footer>
        <div class="flex items-center justify-between gap-8px">
          <ElButton v-if="hasAuth('sys:notification:test')" :loading="connectionTesting" @click="handleConnectionTest">
            连接测试
          </ElButton>
          <div class="flex items-center gap-8px">
            <ElButton @click="drawerVisible = false">取消</ElButton>
            <ElButton v-if="hasAuth('sys:notification:update')" type="primary" :loading="saving" @click="handleSave">
              确定
            </ElButton>
          </div>
        </div>
      </template>
    </ElDrawer>

    <ElDialog v-model="testDialogVisible" title="发送测试邮件" width="min(480px, 92vw)">
      <ElForm label-width="80px" label-suffix="：" require-asterisk-position="left" @submit.prevent="submitTest">
        <ElFormItem label="收件人" required>
          <ElInput v-model="testRecipient" placeholder="name@example.com" @keyup.enter="submitTest" />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="testDialogVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="testSending" @click="submitTest">发送</ElButton>
      </template>
    </ElDialog>

    <ElDialog v-model="helpVisible" title="邮件服务器配置说明" width="min(560px, 92vw)">
      <div class="flex flex-col gap-8px text-14px leading-6">
        <p>1. 填写 SMTP 主机与端口：SMTP 常用 25 或 587（STARTTLS），SECURE_SMTP 常用 465（SSL 直连）。</p>
        <p>2. 若邮箱服务商要求「授权码」，请在密码中填写授权码而不是登录密码。</p>
        <p>3. 发送邮箱会作为默认发件人；通知渠道中单独配置的发件人优先。</p>
        <p>4. 未创建邮件服务器时，发送会回退到服务端环境变量（EMAIL_HOST 等）。</p>
      </div>
      <template #footer>
        <ElButton type="primary" @click="helpVisible = false">知道了</ElButton>
      </template>
    </ElDialog>
  </div>
</template>
