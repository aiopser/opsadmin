<script setup lang="ts">
import { computed } from 'vue';
import ConfigFieldRow from './config-field-row.vue';
import { resolveFieldDef, toSwitchValue } from './config-fields';
import type { ConfigGroupDef, ConfigRowItem } from './config-fields';

defineOptions({ name: 'ConfigGroupPanel' });

interface Props {
  /** 分组定义 */
  group: ConfigGroupDef;
  /** 分组下的配置行 */
  items: ConfigRowItem[];
  /** 配置键 → 草稿值 */
  values: Record<string, string>;
  /** 已修改的配置键 */
  changedKeys: string[];
  /** 保存中 */
  saving?: boolean;
  busy?: boolean;
}

const props = withDefaults(defineProps<Props>(), { saving: false, busy: false });

interface Emits {
  (e: 'save'): void;
  (e: 'reset'): void;
  (e: 'update:value', configKey: string, value: string): void;
}

const emit = defineEmits<Emits>();

const changedKeySet = computed(() => new Set(props.changedKeys));
const changedCount = computed(() => props.changedKeys.length);
const statusText = computed(() => (changedCount.value ? `${changedCount.value} 项待保存` : '暂无未保存的修改'));

function isRowChanged(configKey: string) {
  return changedKeySet.value.has(configKey);
}

/** 依赖项未启用时禁用当前控件 */
function isRowDisabled(configKey: string) {
  const { dependsOn, inactiveReason } = resolveFieldDef(configKey);
  if (inactiveReason) return true;

  if (!dependsOn) {
    return false;
  }

  return !toSwitchValue(props.values[dependsOn]);
}

function handleSave() {
  emit('save');
}

function handleReset() {
  emit('reset');
}

function handleValueUpdate(configKey: string, value: string) {
  emit('update:value', configKey, value);
}
</script>

<template>
  <ElCard class="group-panel card-wrapper" :aria-label="group.name">
    <template #header>
      <div class="flex flex-wrap items-center justify-between gap-12px">
        <div class="min-w-0">
          <p>{{ group.name }}</p>
          <p class="group-desc">{{ group.desc }}</p>
        </div>
        <slot name="actions"></slot>
      </div>
    </template>

    <div class="panel-fields">
      <ConfigFieldRow
        v-for="item in items"
        :key="item.configKey"
        :item="item"
        :value="values[item.configKey] ?? ''"
        :disabled="isRowDisabled(item.configKey)"
        :changed="isRowChanged(item.configKey)"
        @update:value="handleValueUpdate(item.configKey, $event)"
      />
      <ElEmpty v-if="!items.length" :image-size="72" description="该分组暂无配置项" />
    </div>
    <div class="panel-footer">
      <span class="text-12px text-[var(--el-text-color-regular)]" role="status">{{ statusText }}</span>
      <ElSpace :size="8" wrap>
        <ElButton :disabled="!changedCount || busy" @click="handleReset">撤销修改</ElButton>
        <ElButton type="primary" :loading="saving" :disabled="!changedCount || busy" @click="handleSave">
          保存配置
        </ElButton>
      </ElSpace>
    </div>
  </ElCard>
</template>

<style lang="scss" scoped>
.group-desc {
  margin-top: 4px;
  font-size: 12px;
  font-weight: 400;
  line-height: 1.6;
  color: var(--el-text-color-regular);
  text-wrap: pretty;
}

.panel-fields {
  flex: 1;
  min-width: 0;
}

.panel-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--el-border-color-lighter);
}
</style>
