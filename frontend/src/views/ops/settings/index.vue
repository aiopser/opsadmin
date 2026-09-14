<script setup lang="ts">
import { onMounted, ref } from 'vue';
import {
  fetchGetEngineSettings,
  fetchGetNotifySettings,
  fetchSaveEngineSettings,
  fetchSaveNotifySettings
} from '@/service/api';

defineOptions({ name: 'OpsSettings' });

/**
 * 设置结构由后端 get_engine_settings/get_notify_settings 决定，
 * 页面按返回对象的键值动态渲染表单（数值/布尔/字符串），保存时整体提交。
 */
type SettingValue = string | number | boolean | null | Record<string, unknown> | Array<unknown>;

const activeTab = ref('engine');

const engineSettings = ref<Record<string, SettingValue>>({});
const notifySettings = ref<Record<string, SettingValue>>({});
const loading = ref(false);
const saving = ref(false);

function isEditablePrimitive(value: SettingValue) {
  return ['string', 'number', 'boolean'].includes(typeof value) || value === null;
}

const engineEntries = ref<[string, SettingValue][]>([]);
const notifyEntries = ref<[string, SettingValue][]>([]);

function toEntries(record: Record<string, SettingValue>) {
  return Object.entries(record).filter(([, value]) => isEditablePrimitive(value));
}

async function loadSettings() {
  loading.value = true;
  const [engineRes, notifyRes] = await Promise.all([fetchGetEngineSettings(), fetchGetNotifySettings()]);
  if (!engineRes.error) {
    engineSettings.value = (engineRes.data ?? {}) as Record<string, SettingValue>;
    engineEntries.value = toEntries(engineSettings.value);
  }
  if (!notifyRes.error) {
    notifySettings.value = (notifyRes.data ?? {}) as Record<string, SettingValue>;
    notifyEntries.value = toEntries(notifySettings.value);
  }
  loading.value = false;
}

async function handleSave() {
  saving.value = true;
  const target = activeTab.value === 'engine' ? engineSettings.value : notifySettings.value;
  const saveFn = activeTab.value === 'engine' ? fetchSaveEngineSettings : fetchSaveNotifySettings;
  const { error } = await saveFn(target);
  saving.value = false;

  if (!error) {
    window.$message?.success('保存成功');
    loadSettings();
  }
}

function settingLabel(key: string) {
  return key;
}

onMounted(loadSettings);
</script>

<template>
  <div class="min-h-500px flex-col-stretch gap-16px overflow-hidden lt-sm:overflow-auto">
    <ElCard v-loading="loading" class="card-wrapper sm:flex-1-hidden">
      <ElTabs v-model="activeTab">
        <ElTabPane label="执行引擎" name="engine">
          <ElForm label-width="220px" class="max-w-720px">
            <ElFormItem v-for="[key, value] in engineEntries" :key="key" :label="settingLabel(key)">
              <ElSwitch v-if="typeof value === 'boolean'" v-model="engineSettings[key] as boolean" />
              <ElInputNumber
                v-else-if="typeof value === 'number'"
                v-model="engineSettings[key] as number"
                class="w-full"
              />
              <ElInput v-else v-model="engineSettings[key] as string" :placeholder="`请输入 ${key}`" />
            </ElFormItem>
            <ElEmpty v-if="!engineEntries.length" description="暂无可配置项" />
          </ElForm>
        </ElTabPane>
        <ElTabPane label="通知" name="notify">
          <ElForm label-width="220px" class="max-w-720px">
            <ElFormItem v-for="[key, value] in notifyEntries" :key="key" :label="settingLabel(key)">
              <ElSwitch v-if="typeof value === 'boolean'" v-model="notifySettings[key] as boolean" />
              <ElInputNumber
                v-else-if="typeof value === 'number'"
                v-model="notifySettings[key] as number"
                class="w-full"
              />
              <ElInput v-else v-model="notifySettings[key] as string" :placeholder="`请输入 ${key}`" />
            </ElFormItem>
            <ElEmpty v-if="!notifyEntries.length" description="暂无可配置项" />
          </ElForm>
        </ElTabPane>
      </ElTabs>
      <div class="mt-16px">
        <ElButton type="primary" :loading="saving" @click="handleSave">保存</ElButton>
      </div>
    </ElCard>
  </div>
</template>
