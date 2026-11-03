<script setup lang="ts">
import { $t } from '@/locales';

defineOptions({ name: 'LogSearch' });

interface Emits {
  (e: 'reset'): void;
  (e: 'search'): void;
}

const emit = defineEmits<Emits>();

const model = defineModel<Api.SystemManage.OperationLogSearchParams>('model', { required: true });

function reset() {
  emit('reset');
}

function search() {
  emit('search');
}
</script>

<template>
  <SearchPanel @reset="reset" @search="search">
    <ElForm :model="model" label-position="right" :label-width="80" @submit.prevent="search">
      <ElFormItem :label="$t('page.manage.log.keywords')" prop="keywords">
        <ElInput v-model="model.keywords" clearable :placeholder="$t('page.manage.log.keywords')" />
      </ElFormItem>
      <ElFormItem :label="$t('page.manage.log.createTime')" prop="createTime">
        <ElDatePicker
          v-model="model.createTime"
          class="w-full"
          type="daterange"
          value-format="YYYY-MM-DD"
          start-placeholder="YYYY-MM-DD"
          end-placeholder="YYYY-MM-DD"
        />
      </ElFormItem>
    </ElForm>
  </SearchPanel>
</template>
