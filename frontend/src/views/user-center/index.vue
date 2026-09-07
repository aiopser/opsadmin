<script setup lang="ts">
import { computed, ref, shallowRef } from 'vue';
import { REG_PWD } from '@/constants/reg';
import { fetchGetUserProfile, fetchUpdateUserPassword, fetchUpdateUserProfile } from '@/service/api';
import { useAppStore } from '@/store/modules/app';
import { useAuthStore } from '@/store/modules/auth';
import { useForm, useFormRules } from '@/hooks/common/form';
import { $t } from '@/locales';

defineOptions({ name: 'UserCenter' });

interface ProfileInfo {
  userId: string;
  username: string;
  nickname: string;
  roles: string[];
  email: string;
  mobile: string;
  deptName: string;
  avatar: string;
  createTime: string;
}

const appStore = useAppStore();
const authStore = useAuthStore();

const profile = shallowRef<ProfileInfo>({
  userId: '',
  username: '',
  nickname: '',
  roles: [],
  email: '',
  mobile: '',
  deptName: '',
  avatar: '',
  createTime: ''
});

const profileLoading = ref(false);

async function getProfile() {
  profileLoading.value = true;

  const { error, data } = await fetchGetUserProfile();

  if (!error && data) {
    profile.value = data;
    initProfileModel();
  }

  profileLoading.value = false;
}

// ── 个人信息 ──
const { formRef: profileFormRef, validate: validateProfile } = useForm();

const profileModel = ref(createProfileModel());

function createProfileModel() {
  return {
    nickname: '',
    email: '',
    mobile: ''
  };
}

function initProfileModel() {
  profileModel.value = {
    nickname: profile.value.nickname || '',
    email: profile.value.email || '',
    mobile: profile.value.mobile || ''
  };
}

async function handleSaveProfile() {
  await validateProfile();

  const { error } = await fetchUpdateUserProfile({ ...profileModel.value });

  if (!error) {
    window.$message?.success($t('page.manage.common.profileUpdated'));
    getProfile();
  }
}

// ── 安全信息 ──
const { formRef: passwordFormRef, validate: validatePassword, restoreValidation: resetPasswordForm } = useForm();

const { createRequiredRule, createConfirmPwdRule } = useFormRules();

const passwordModel = ref(createPasswordModel());

const passwordRules = computed(() => ({
  oldPassword: [createRequiredRule($t('page.manage.common.oldPasswordRequired'))],
  newPassword: [
    createRequiredRule($t('page.manage.common.newPasswordRequired')),
    { pattern: REG_PWD, message: $t('form.pwd.invalid'), trigger: 'input' }
  ],
  confirmPassword: createConfirmPwdRule(computed(() => passwordModel.value.newPassword))
}));

function createPasswordModel() {
  return {
    oldPassword: '',
    newPassword: '',
    confirmPassword: ''
  };
}

async function handleSavePassword() {
  await validatePassword();

  const { error } = await fetchUpdateUserPassword(passwordModel.value.oldPassword, passwordModel.value.newPassword);

  if (!error) {
    window.$message?.success($t('page.manage.common.passwordUpdated'));
    resetPasswordForm();
    passwordModel.value = createPasswordModel();
    // 修改密码后强制重新登录
    authStore.resetStore();
  }
}

getProfile();
</script>

<template>
  <div class="flex-col-stretch gap-16px">
    <ElCard v-loading="profileLoading" class="card-wrapper">
      <template #header>
        <p>{{ $t('page.manage.common.profileTitle') }}</p>
      </template>
      <ElForm ref="profileFormRef" :model="profileModel" label-position="top" class="max-w-480px">
        <ElFormItem :label="$t('page.manage.common.userNickname')" prop="nickname">
          <ElInput v-model="profileModel.nickname" :placeholder="$t('page.manage.common.userNickname')" />
        </ElFormItem>
        <ElFormItem :label="$t('page.manage.common.userPhone')" prop="mobile">
          <ElInput v-model="profileModel.mobile" :placeholder="$t('page.manage.common.userPhone')" />
        </ElFormItem>
        <ElFormItem :label="$t('page.manage.common.userEmail')" prop="email">
          <ElInput v-model="profileModel.email" :placeholder="$t('page.manage.common.userEmail')" />
        </ElFormItem>
        <ElFormItem :label="$t('page.manage.common.language')">
          <ElSelect :model-value="appStore.locale" @update:model-value="appStore.changeLocale">
            <ElOption
              v-for="option in appStore.localeOptions"
              :key="option.key"
              :label="option.label"
              :value="option.key"
            />
          </ElSelect>
        </ElFormItem>
        <ElButton type="primary" @click="handleSaveProfile">{{ $t('page.manage.common.saveProfile') }}</ElButton>
      </ElForm>
    </ElCard>

    <ElCard class="card-wrapper">
      <template #header>
        <p>{{ $t('page.manage.common.securityTitle') }}</p>
      </template>
      <ElAlert type="info" :closable="false" class="mb-16px">
        <p>{{ $t('page.manage.common.passwordRuleTip') }}</p>
        <p class="mt-4px">{{ $t('page.manage.common.passwordResetNote') }}</p>
      </ElAlert>
      <ElForm
        ref="passwordFormRef"
        :model="passwordModel"
        :rules="passwordRules"
        label-position="top"
        class="max-w-480px"
      >
        <ElFormItem :label="$t('page.manage.common.oldPassword')" prop="oldPassword">
          <ElInput
            v-model="passwordModel.oldPassword"
            type="password"
            show-password
            show-word-limit
            maxlength="32"
            :placeholder="$t('page.manage.common.oldPasswordRequired')"
          />
        </ElFormItem>
        <ElFormItem :label="$t('page.manage.common.newPassword')" prop="newPassword">
          <ElInput
            v-model="passwordModel.newPassword"
            type="password"
            show-password
            show-word-limit
            maxlength="32"
            :placeholder="$t('page.manage.common.newPasswordRequired')"
          />
        </ElFormItem>
        <ElFormItem :label="$t('page.manage.common.confirmPassword')" prop="confirmPassword">
          <ElInput
            v-model="passwordModel.confirmPassword"
            type="password"
            show-password
            show-word-limit
            maxlength="32"
            :placeholder="$t('form.confirmPwd.required')"
          />
        </ElFormItem>
        <ElButton type="primary" @click="handleSavePassword">{{ $t('page.manage.common.savePassword') }}</ElButton>
      </ElForm>
    </ElCard>
  </div>
</template>

<style scoped></style>
