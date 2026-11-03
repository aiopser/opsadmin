<script setup lang="ts">
import { ref } from 'vue';
import { $t } from '@/locales';

defineOptions({ name: 'SearchPanel' });

interface Emits {
  (e: 'reset'): void;
  (e: 'search'): void;
}

const emit = defineEmits<Emits>();

/** 搜索条件是否隐藏：隐藏后仅保留底部操作栏 */
const collapsed = ref(false);

function toggleCollapsed() {
  collapsed.value = !collapsed.value;
}

function reset() {
  emit('reset');
}

function search() {
  emit('search');
}
</script>

<template>
  <ElCard class="search-panel overflow-hidden card-wrapper" :body-style="{ padding: '0px' }">
    <ElCollapseTransition>
      <div v-show="!collapsed" class="search-panel-body">
        <!-- 默认插槽放一个 ElForm（label-width 80），内部自动应用网格布局 -->
        <slot></slot>
      </div>
    </ElCollapseTransition>
    <div class="search-panel-actions" :class="{ 'search-panel-actions-bordered': !collapsed }">
      <div class="search-panel-extra">
        <slot name="extra"></slot>
      </div>
      <ElSpace :size="8">
        <ElButton text :aria-expanded="!collapsed" @click="toggleCollapsed">
          <template #icon>
            <icon-mdi-eye-off-outline v-if="!collapsed" class="text-icon" />
            <icon-mdi-eye-outline v-else class="text-icon" />
          </template>
          {{ collapsed ? $t('common.expand') : $t('common.hide') }}
        </ElButton>
        <ElButton @click="reset">
          <template #icon>
            <icon-ic-round-refresh class="text-icon" />
          </template>
          {{ $t('common.reset') }}
        </ElButton>
        <ElButton type="primary" plain @click="search">
          <template #icon>
            <icon-ic-round-search class="text-icon" />
          </template>
          {{ $t('common.search') }}
        </ElButton>
      </ElSpace>
    </div>
  </ElCard>
</template>

<style lang="scss" scoped>
.search-panel-body :deep(.el-form) {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  row-gap: 12px;
  padding: 16px 0;
}

.search-panel-body :deep(.el-form-item) {
  margin-bottom: 0;
  padding: 0 16px;
}

/* 仅在四列单行布局下显示列分隔线，避免折行时出现孤立竖线 */
@media (min-width: 1200px) {
  .search-panel-body :deep(.el-form-item:not(:nth-child(4n + 1))) {
    border-left: 1px solid var(--el-border-color-lighter);
  }
}

@media (max-width: 1199px) {
  .search-panel-body :deep(.el-form) {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 991px) {
  .search-panel-body :deep(.el-form) {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 767px) {
  .search-panel-body :deep(.el-form) {
    grid-template-columns: minmax(0, 1fr);
  }
}

.search-panel-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  justify-content: flex-end;
  padding: 8px 16px;
}

/* 仅在展开状态用一条浅色分隔线区分操作栏，收起时避免卡片顶部多一条线 */
.search-panel-actions-bordered {
  border-top: 1px solid var(--el-border-color-lighter);
}

.search-panel-extra {
  margin-right: auto;
}

.search-panel-extra:empty {
  display: none;
}
</style>
