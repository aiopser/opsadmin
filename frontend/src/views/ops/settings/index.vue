<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { fetchGetEngineSettings, fetchSaveEngineSettings } from '@/service/api';
import { $t } from '@/locales';
import CommandFilter from './modules/command-filter.vue';

defineOptions({ name: 'OpsEngineSettings' });

const settings = ref<Api.Jobs.EngineSettings>({
  timeout: 300,
  forks: 10,
  host_strategy: 'parallel',
  serial_batch: 5,
  max_fail_percentage: 0
});
const loading = ref(false);
const saving = ref(false);
const activeTab = ref('engine');

async function loadSettings() {
  loading.value = true;
  try {
    const { data, error } = await fetchGetEngineSettings();
    if (error || !data) {
      if (error) window.$message?.error($t('page.ops.engineSettings.loadError'));
      return;
    }
    settings.value = data;
  } finally {
    loading.value = false;
  }
}

async function saveSettings() {
  saving.value = true;
  try {
    const { error } = await fetchSaveEngineSettings(settings.value);
    if (error) return;
    window.$notification?.success($t('page.ops.engineSettings.saveSuccess'));
    await loadSettings();
  } finally {
    saving.value = false;
  }
}

onMounted(loadSettings);
</script>

<template>
  <div class="min-h-500px flex-col-stretch gap-16px overflow-y-auto">
    <ElTabs v-model="activeTab" class="flex-shrink-0">
      <ElTabPane :label="$t('page.ops.engineSettings.engineTab')" name="engine">
        <ElCard v-loading="loading" class="mt-16px flex-shrink-0 card-wrapper">
          <ElAlert :closable="false" show-icon type="info" class="mb-16px">
            {{ $t('page.ops.engineSettings.overrideHint') }}
          </ElAlert>

          <ElForm
            :model="settings"
            label-position="top"
            class="max-w-900px"
            label-suffix="："
            require-asterisk-position="left"
          >
            <div class="grid grid-cols-1 gap-x-20px md:grid-cols-2">
              <ElFormItem :label="$t('page.ops.engineSettings.timeout')">
                <ElInputNumber
                  v-model="settings.timeout"
                  :min="1"
                  :step="30"
                  controls-position="right"
                  class="w-full"
                />
              </ElFormItem>
              <ElFormItem :label="$t('page.ops.engineSettings.forks')">
                <ElInputNumber v-model="settings.forks" :min="1" controls-position="right" class="w-full" />
              </ElFormItem>
              <ElFormItem :label="$t('page.ops.engineSettings.strategy')" class="md:col-span-2">
                <ElRadioGroup v-model="settings.host_strategy">
                  <ElRadio value="parallel">{{ $t('page.ops.engineSettings.parallel') }}</ElRadio>
                  <ElRadio value="serial">{{ $t('page.ops.engineSettings.serial') }}</ElRadio>
                  <ElRadio value="rolling">{{ $t('page.ops.engineSettings.rolling') }}</ElRadio>
                </ElRadioGroup>
              </ElFormItem>
              <ElFormItem :label="$t('page.ops.engineSettings.serialBatch')">
                <ElInputNumber
                  v-model="settings.serial_batch"
                  :min="1"
                  controls-position="right"
                  :disabled="settings.host_strategy !== 'rolling'"
                  class="w-full"
                />
              </ElFormItem>
              <ElFormItem :label="$t('page.ops.engineSettings.maxFailPercentage')">
                <ElInputNumber
                  v-model="settings.max_fail_percentage"
                  :min="0"
                  :max="100"
                  controls-position="right"
                  class="w-full"
                >
                  <template #suffix>%</template>
                </ElInputNumber>
              </ElFormItem>
            </div>
          </ElForm>

          <div class="mt-8px flex justify-end">
            <ElButton type="primary" :loading="saving" @click="saveSettings">
              {{ $t('page.ops.engineSettings.saveButton') }}
            </ElButton>
          </div>
        </ElCard>
      </ElTabPane>
      <ElTabPane :label="$t('page.ops.commandFilter.tab')" name="command-filter" lazy>
        <CommandFilter class="mt-16px" />
      </ElTabPane>
    </ElTabs>
  </div>
</template>
