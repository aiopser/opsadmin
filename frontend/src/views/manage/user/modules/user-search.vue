<script setup lang="ts">
import { computed } from 'vue';
import { enableStatusOptions, userGenderOptions } from '@/constants/business';
import { useForm, useFormRules } from '@/hooks/common/form';
import { translateOptions } from '@/utils/common';
import { $t } from '@/locales';

defineOptions({ name: 'UserSearch' });

interface Emits {
  (e: 'reset'): void;
  (e: 'search'): void;
}

const emit = defineEmits<Emits>();

const model = defineModel<Api.SystemManage.UserSearchParams>('model', { required: true });

const { formRef, validate, restoreValidation } = useForm();

type RuleKey = Extract<keyof Api.SystemManage.UserSearchParams, 'userEmail' | 'userPhone'>;

const rules = computed<Record<RuleKey, App.Global.FormRule>>(() => {
  const { patternRules } = useFormRules(); // inside computed to make locale reactive

  return {
    userEmail: patternRules.email,
    userPhone: patternRules.phone
  };
});

async function reset() {
  await restoreValidation();
  emit('reset');
}

async function search() {
  await validate();
  emit('search');
}
</script>

<template>
  <SearchPanel @reset="reset" @search="search">
    <ElForm
      ref="formRef"
      :model="model"
      :rules="rules"
      label-position="right"
      :label-width="80"
      @submit.prevent="search"
    >
      <ElFormItem :label="$t('page.manage.user.userName')" prop="userName">
        <ElInput v-model="model.userName" clearable :placeholder="$t('page.manage.user.form.userName')" />
      </ElFormItem>
      <ElFormItem :label="$t('page.manage.user.userGender')" prop="userGender">
        <ElSelect v-model="model.userGender" clearable :placeholder="$t('page.manage.user.form.userGender')">
          <ElOption
            v-for="{ label, value } in translateOptions(userGenderOptions)"
            :key="value"
            :label="label"
            :value="value"
          />
        </ElSelect>
      </ElFormItem>
      <ElFormItem :label="$t('page.manage.user.nickName')" prop="nickName">
        <ElInput v-model="model.nickName" clearable :placeholder="$t('page.manage.user.form.nickName')" />
      </ElFormItem>
      <ElFormItem :label="$t('page.manage.user.userPhone')" prop="userPhone">
        <ElInput v-model="model.userPhone" clearable :placeholder="$t('page.manage.user.form.userPhone')" />
      </ElFormItem>
      <ElFormItem :label="$t('page.manage.user.userEmail')" prop="userEmail">
        <ElInput v-model="model.userEmail" clearable :placeholder="$t('page.manage.user.form.userEmail')" />
      </ElFormItem>
      <ElFormItem :label="$t('page.manage.user.userStatus')" prop="status">
        <ElSelect v-model="model.status" clearable :placeholder="$t('page.manage.user.form.userStatus')">
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
