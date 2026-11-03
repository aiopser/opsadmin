<script setup lang="ts">
import { computed, onMounted, ref, shallowRef } from 'vue';
import { fetchGetConfigList, fetchRefreshConfig, updateConfig } from '@/service/api';
import { loadConfigPages, mergeConfigSnapshot, persistConfigChanges } from './config-state';
import ConfigGroupNav from './config-group-nav.vue';
import ConfigGroupPanel from './config-group-panel.vue';
import ConfigOperateDrawer from './config-operate-drawer.vue';
import { CONFIG_GROUPS, isValueDirty, resolveFieldDef, resolveGroupDef } from './config-fields';
import type { ConfigGroupKey, ConfigNavGroup, ConfigRowItem } from './config-fields';

defineOptions({ name: 'ConfigGroupView' });

const configs = shallowRef<Api.SystemManage.SystemConfig[]>([]);
const draftValues = ref<Record<string, string>>({});
const savedValues = ref<Record<string, string>>({});
const activeGroup = ref<ConfigGroupKey>('basic');
const loading = ref(false);
const savingGroup = ref<ConfigGroupKey | null>(null);
const drawerVisible = ref(false);

function createEmptyGroups(): Record<ConfigGroupKey, ConfigRowItem[]> {
  return { basic: [], security: [], log: [], file: [] };
}

function toRowItem(row: Api.SystemManage.SystemConfig): ConfigRowItem {
  return {
    id: row.id,
    configKey: row.configKey,
    configName: row.configName,
    remark: row.remark ?? '',
    isSystem: row.isSystem
  };
}

/** 按分组归集配置行 */
const itemsByGroup = computed(() => {
  const grouped = createEmptyGroups();

  configs.value.forEach(row => {
    const group = resolveGroupDef(row.configGroup);

    if (group) {
      grouped[group.key].push(toRowItem(row));
    }
  });

  return grouped;
});

/** 各分组中已修改的配置键 */
const changedKeysByGroup = computed(() => {
  const changed: Record<ConfigGroupKey, string[]> = { basic: [], security: [], log: [], file: [] };

  CONFIG_GROUPS.forEach(def => {
    changed[def.key] = itemsByGroup.value[def.key]
      .filter(item => isValueDirty(item.configKey, draftValues.value, savedValues.value))
      .map(item => item.configKey);
  });

  return changed;
});

/** 命中搜索关键词的配置行 */
const navGroups = computed<ConfigNavGroup[]>(() =>
  CONFIG_GROUPS.map(def => ({
    key: def.key,
    name: def.name,
    count: itemsByGroup.value[def.key].length,
    changed: changedKeysByGroup.value[def.key].length > 0
  }))
);

/** 当前激活分组的定义与配置行 */
const activeGroupDef = computed(() => CONFIG_GROUPS.find(def => def.key === activeGroup.value) ?? CONFIG_GROUPS[0]);
const activeGroupItems = computed(() => itemsByGroup.value[activeGroup.value]);
const activeGroupChangedKeys = computed(() => changedKeysByGroup.value[activeGroup.value]);

async function loadConfigs() {
  loading.value = true;
  try {
    const records = await loadConfigPages(async (current, size) => {
      const { data, error } = await fetchGetConfigList({ current, size });
      return error || !data ? null : data;
    });
    const next = mergeConfigSnapshot(records, draftValues.value, savedValues.value);
    configs.value = records;
    draftValues.value = next.drafts;
    savedValues.value = next.saved;
  } catch (error) {
    window.$message?.error(error instanceof Error ? error.message : '配置加载失败，请重试');
  } finally {
    loading.value = false;
  }
}

/** 仅保存当前可见项；请求快照与后续输入分开追踪。 */
async function handleSave(groupKey: ConfigGroupKey) {
  if (savingGroup.value) return;
  const changedKeys = changedKeysByGroup.value[groupKey];
  if (!changedKeys.length) return;
  const targets = configs.value.filter(
    row => changedKeys.includes(row.configKey) && !resolveFieldDef(row.configKey).inactiveReason
  );
  savingGroup.value = groupKey;
  try {
    const result = await persistConfigChanges(targets, draftValues.value, (row, value) =>
      updateConfig(row.id, {
        configName: row.configName,
        configKey: row.configKey,
        configValue: value,
        configGroup: row.configGroup,
        remark: row.remark ?? '',
        status: row.status
      })
    );
    savedValues.value = { ...savedValues.value, ...result.saved };
    const savedCount = Object.keys(result.saved).length;
    if (result.failedKeys.length) {
      window.$message?.error(`已保存 ${savedCount} 项，${result.failedKeys.length} 项失败；失败项保留修改，可重试`);
    }
    if (!savedCount) return;
    const { error } = await fetchRefreshConfig();
    if (error) {
      window.$message?.warning('配置已保存，但刷新缓存失败，请点击“刷新配置缓存”重试');
    } else if (!result.failedKeys.length) {
      window.$notification?.success(`已保存 ${savedCount} 项配置`);
    }
  } finally {
    savingGroup.value = null;
  }
}

/** 重置分组：草稿还原为已保存值 */
function handleReset(groupKey: ConfigGroupKey) {
  const nextDraft = { ...draftValues.value };

  itemsByGroup.value[groupKey].forEach(item => {
    nextDraft[item.configKey] = savedValues.value[item.configKey] ?? '';
  });

  draftValues.value = nextDraft;
  window.$notification?.success('当前显示的配置已撤销修改');
}

function handleValueUpdate(configKey: string, value: string) {
  if (resolveFieldDef(configKey).inactiveReason) return;
  draftValues.value = { ...draftValues.value, [configKey]: value };
}

const refreshingCache = ref(false);

async function handleRefreshCache() {
  refreshingCache.value = true;
  try {
    const { error } = await fetchRefreshConfig();
    if (!error) window.$notification?.success('配置缓存已刷新');
  } finally {
    refreshingCache.value = false;
  }
}

function handleSelectGroup(groupKey: ConfigGroupKey) {
  activeGroup.value = groupKey;
}

function handleAdd() {
  drawerVisible.value = true;
}

async function handleSubmitted() {
  await loadConfigs();
}

function init() {
  loadConfigs();
}

onMounted(() => {
  init();
});
</script>

<template>
  <div class="config-group-view">
    <ConfigGroupNav :active-key="activeGroup" :groups="navGroups" @update:active-key="handleSelectGroup" />

    <section v-loading="loading" class="group-panels">
      <ConfigGroupPanel
        :key="activeGroup"
        :group="activeGroupDef"
        :items="activeGroupItems"
        :values="draftValues"
        :changed-keys="activeGroupChangedKeys"
        :saving="savingGroup === activeGroup"
        :busy="savingGroup !== null"
        @save="handleSave(activeGroup)"
        @reset="handleReset(activeGroup)"
        @update:value="handleValueUpdate"
      >
        <template #actions>
          <ElSpace :size="8">
            <ElButton :loading="refreshingCache" :disabled="savingGroup !== null" @click="handleRefreshCache">
              刷新配置缓存
            </ElButton>
            <ElButton :disabled="savingGroup !== null" @click="handleAdd">新增配置项</ElButton>
          </ElSpace>
        </template>
      </ConfigGroupPanel>
    </section>

    <ConfigOperateDrawer v-model:visible="drawerVisible" operate-type="add" @submitted="handleSubmitted" />
  </div>
</template>

<style lang="scss" scoped>
.config-group-view {
  display: grid;
  flex: 1;
  grid-template-columns: 212px minmax(0, 1fr);
  grid-template-rows: minmax(min-content, 1fr);
  align-items: stretch;
  gap: 12px;
}

.group-panels {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

@media (max-width: 767px) {
  .config-group-view {
    flex: none;
    grid-template-columns: minmax(0, 1fr);
    grid-template-rows: auto;
  }
}
</style>
