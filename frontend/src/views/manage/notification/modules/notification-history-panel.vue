<script setup lang="ts">
import { onMounted, ref } from 'vue';
import {
  fetchGetNotificationHistorySettings,
  fetchPurgeNotificationHistory,
  fetchSaveNotificationHistorySettings
} from '@/service/api';
import { useAuth } from '@/hooks/business/auth';

defineOptions({ name: 'NotificationHistoryPanel' });

const { hasAuth } = useAuth();

const retentionDays = ref(180);
const loading = ref(false);
const saving = ref(false);
const purging = ref(false);

async function loadSettings() {
  loading.value = true;
  try {
    const { data, error } = await fetchGetNotificationHistorySettings();
    if (error || !data) return;
    retentionDays.value = data.retentionDays;
  } finally {
    loading.value = false;
  }
}

async function saveSettings() {
  saving.value = true;
  try {
    const { data, error } = await fetchSaveNotificationHistorySettings({ retentionDays: retentionDays.value });
    if (error || !data) return;
    retentionDays.value = data.retentionDays;
    window.$notification?.success('清理设置已保存');
  } finally {
    saving.value = false;
  }
}

async function purgeHistory() {
  const preview = await fetchPurgeNotificationHistory({ dryRun: true, retentionDays: retentionDays.value });
  if (preview.error || !preview.data) return;
  const count = preview.data.count;
  if (count === 0) {
    window.$message?.info('没有可清理的发送成功记录');
    return;
  }

  try {
    await ElMessageBox.confirm(
      `将永久删除 ${count} 条超过 ${retentionDays.value} 天的发送成功记录，失败记录与告警记录不受影响。`,
      '立即清理',
      { confirmButtonText: '确认清理', cancelButtonText: '取消', type: 'warning' }
    );
  } catch {
    return;
  }

  purging.value = true;
  try {
    const result = await fetchPurgeNotificationHistory({ dryRun: false, retentionDays: retentionDays.value });
    if (result.error || !result.data) return;
    window.$notification?.success(`已清理 ${result.data.deleted} 条记录`);
  } finally {
    purging.value = false;
  }
}

onMounted(loadSettings);
</script>

<template>
  <div>
    <ElCard v-loading="loading" class="card-wrapper">
      <template #header>
        <div class="flex flex-wrap items-center justify-between gap-8px">
          <div class="min-w-0 flex flex-wrap items-baseline gap-8px">
            <p>历史数据清理</p>
            <span class="text-13px text-gray-500">按保留期清理发送成功的通知记录</span>
          </div>
          <ElButton @click="loadSettings">刷新</ElButton>
        </div>
      </template>
      <ElForm label-position="top" class="max-w-420px">
        <ElFormItem>
          <template #label>
            <FormLabelHelp label="保留天数" help="超过该天数的发送成功记录会被清理；失败记录与告警去重记录不会被删除" />
          </template>
          <ElInputNumber v-model="retentionDays" :min="1" :max="3650" class="w-full" />
        </ElFormItem>
      </ElForm>
      <div class="flex items-center gap-8px">
        <ElButton v-if="hasAuth('sys:notification:update')" type="primary" :loading="saving" @click="saveSettings">
          保存设置
        </ElButton>
        <ElButton v-if="hasAuth('sys:notification:update')" :loading="purging" @click="purgeHistory">立即清理</ElButton>
      </div>
      <p class="mt-12px text-12px text-gray-500 leading-5">
        系统每日 03:30 自动执行一次清理；「立即清理」只会删除超过保留天数且发送成功的记录。
      </p>
    </ElCard>
  </div>
</template>
