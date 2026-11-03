<script setup lang="ts">
import { enableStatusOptions } from '@/constants/business';
import { translateOptions } from '@/utils/common';
import { $t } from '@/locales';

defineOptions({ name: 'DeptSearch' });

interface Emits {
  (e: 'reset'): void;
  (e: 'search'): void;
}

const emit = defineEmits<Emits>();

const model = defineModel<Api.SystemManage.DepartmentSearchParams>('model', { required: true });

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
      <ElFormItem :label="$t('page.manage.dept.deptName')" prop="deptName">
        <ElInput v-model="model.deptName" clearable :placeholder="$t('page.manage.dept.form.deptName')" />
      </ElFormItem>
      <ElFormItem :label="$t('page.manage.dept.deptStatus')" prop="status">
        <ElSelect v-model="model.status" clearable :placeholder="$t('page.manage.dept.form.deptStatus')">
          <ElOption
            v-for="{ label, value } in translateOptions(enableStatusOptions)"
            :key="value"
            :label="label"
            :value="value"
          />
        </ElSelect>
      </ElFormItem>
    </ElForm>
  </SearchPanel>
</template>
