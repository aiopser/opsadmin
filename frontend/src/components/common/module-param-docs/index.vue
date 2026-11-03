<script setup lang="ts">
import type { ModuleParamDocOption } from '@/constants/ansible-module-param-docs';

defineOptions({ name: 'ModuleParamDocs' });

defineProps<{
  /** 待展示的参数说明条目 */
  options: ModuleParamDocOption[];
}>();
</script>

<template>
  <div class="param-table">
    <div class="param-row param-row--head">
      <div class="param-cell param-cell--name">参数</div>
      <div class="param-cell">说明</div>
    </div>
    <div v-for="opt in options" :key="opt.name" class="param-row">
      <div class="param-cell param-cell--name">
        <span class="param-mono">{{ opt.name }}</span>
        <span v-if="opt.required" class="param-required">必填</span>
      </div>
      <div class="param-cell">
        <div>{{ opt.description }}</div>
        <div v-if="opt.choices?.length" class="param-extra">可选值：{{ opt.choices.join(' / ') }}</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.param-table {
  border: 1px solid var(--el-border-color-lighter);
  overflow: hidden;
  font-size: 13px;
}

.param-row {
  display: flex;
}

.param-row + .param-row {
  border-top: 1px solid var(--el-border-color-lighter);
}

.param-row:not(.param-row--head):hover {
  background: var(--el-fill-color-lighter);
}

.param-row--head {
  background: var(--el-fill-color-light);
  color: var(--el-text-color-secondary);
  font-size: 13px;
  font-weight: 400;
}

.param-cell {
  flex: 1;
  min-width: 0;
  padding: 7px 12px;
  line-height: 1.6;
}

.param-row--head .param-cell {
  padding: 6px 12px;
}

.param-cell--name {
  width: 150px;
  flex-shrink: 0;
  border-right: 1px solid var(--el-border-color-lighter);
}

.param-mono {
  font-family: Consolas, Monaco, monospace;
}

.param-required {
  margin-left: 6px;
  color: var(--el-color-danger);
  font-size: 13px;
  font-weight: 400;
}

.param-extra {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
</style>
