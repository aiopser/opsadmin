<script setup lang="ts">
import { enableStatusOptions } from '@/constants/business';
import { translateOptions } from '@/utils/common';
import { $t } from '@/locales';

defineOptions({ name: 'RoleSearch' });

interface Emits {
  (e: 'reset'): void;
  (e: 'search'): void;
}

const emit = defineEmits<Emits>();

const model = defineModel<Api.SystemManage.RoleSearchParams>('model', { required: true });

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
      <ElFormItem :label="$t('page.manage.role.roleName')" prop="roleName">
        <ElInput v-model="model.roleName" clearable :placeholder="$t('page.manage.role.form.roleName')" />
      </ElFormItem>
      <ElFormItem :label="$t('page.manage.role.roleCode')" prop="roleCode">
        <ElInput v-model="model.roleCode" clearable :placeholder="$t('page.manage.role.form.roleCode')" />
      </ElFormItem>
      <ElFormItem :label="$t('page.manage.role.roleStatus')" prop="status">
        <ElSelect v-model="model.status" clearable :placeholder="$t('page.manage.role.form.roleStatus')">
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
