<script setup lang="ts">
import type { ConfigGroupKey, ConfigNavGroup as ConfigNavGroupItem } from './config-fields';

defineOptions({ name: 'ConfigGroupNav' });

defineProps<{ groups: ConfigNavGroupItem[] }>();

const activeKey = defineModel<ConfigGroupKey>('activeKey', { required: true });

function handleSelect(key: ConfigGroupKey) {
  activeKey.value = key;
}
</script>

<template>
  <ElCard class="group-nav card-wrapper">
    <template #header>
      <p>配置分组</p>
    </template>

    <nav aria-label="配置分组">
      <button
        v-for="group in groups"
        :key="group.key"
        type="button"
        class="nav-item"
        :class="{ 'is-active': group.key === activeKey }"
        :aria-current="group.key === activeKey ? 'page' : undefined"
        @click="handleSelect(group.key)"
      >
        <span class="flex-1 text-left">{{ group.name }}</span>
        <span v-if="group.changed" class="text-12px">未保存</span>
        <span v-else class="nav-count">{{ group.count }}</span>
      </button>
    </nav>
  </ElCard>
</template>

<style lang="scss" scoped>
.group-nav {
  align-self: stretch;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  min-height: 40px;
  margin-bottom: 4px;
  padding: 8px 12px;
  border: none;
  background: transparent;
  font: inherit;
  font-size: 13px;
  color: var(--el-text-color-regular);
  cursor: pointer;
  transition: background-color 0.15s ease-out;

  &:last-child {
    margin-bottom: 0;
  }

  &:hover {
    background: var(--el-fill-color-light);
  }

  &:active {
    transform: scale(0.98);
  }

  &:focus-visible {
    outline: 2px solid var(--el-color-primary);
    outline-offset: 2px;
  }

  &.is-active {
    background: var(--el-color-primary-light-9);
    color: var(--el-color-primary);
  }
}

.nav-count {
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}
</style>
