<script setup lang="ts">
import { $t } from '@/locales';

defineOptions({ name: 'TableHeaderOperation' });

interface Props {
  disabledDelete?: boolean;
  loading?: boolean;
  /** 是否显示新增按钮（只读页面可关闭） */
  showAdd?: boolean;
  /** 是否显示批量删除按钮（只读页面可关闭） */
  showBatchDelete?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  disabledDelete: false,
  loading: false,
  showAdd: true,
  showBatchDelete: true
});

interface Emits {
  (e: 'add'): void;
  (e: 'delete'): void;
  (e: 'refresh'): void;
}

const emit = defineEmits<Emits>();

const columns = defineModel<UI.TableColumnCheck[]>('columns', {
  default: () => []
});

function add() {
  emit('add');
}

function batchDelete() {
  emit('delete');
}

function refresh() {
  emit('refresh');
}
</script>

<template>
  <ElSpace direction="horizontal" wrap justify="end" class="lt-sm:w-200px">
    <slot name="prefix"></slot>
    <slot name="default">
      <ElButton v-if="props.showAdd" plain type="primary" @click="add">
        <template #icon>
          <icon-ic-round-plus class="text-icon" />
        </template>
        {{ $t('common.add') }}
      </ElButton>
      <ElPopconfirm v-if="props.showBatchDelete" :title="$t('common.confirmDelete')" @confirm="batchDelete">
        <template #reference>
          <ElButton type="danger" plain :disabled="disabledDelete">
            <template #icon>
              <icon-ic-round-delete class="text-icon" />
            </template>
            {{ $t('common.batchDelete') }}
          </ElButton>
        </template>
      </ElPopconfirm>
    </slot>
    <ElButton @click="refresh">
      <template #icon>
        <icon-mdi-refresh class="text-icon" :class="{ 'animate-spin': loading }" />
      </template>
      {{ $t('common.refresh') }}
    </ElButton>
    <TableColumnSetting v-model:columns="columns" />
    <slot name="suffix"></slot>
  </ElSpace>
</template>

<style scoped></style>
