<script setup lang="ts">
import { computed } from 'vue';
import { useAppStore } from '@/store/modules/app';
import { useAuthStore } from '@/store/modules/auth';
import { $t } from '@/locales';

defineOptions({ name: 'HeaderBanner' });

const appStore = useAppStore();
const authStore = useAuthStore();

const loginTime = computed(() => {
  const value = authStore.userInfo.lastLogin;
  if (!value) return $t('page.home.loginTimeUnavailable');

  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? $t('page.home.loginTimeUnavailable') : date.toLocaleString(appStore.locale);
});
</script>

<template>
  <ElCard class="card-wrapper">
    <ElRow class="px-8px">
      <ElCol :span="24">
        <div class="flex-y-center gap-12px">
          <div class="size-72px shrink-0 overflow-hidden rd-1/2">
            <img src="@/assets/imgs/soybean.jpg" class="size-full" alt="" />
          </div>
          <div class="min-w-0">
            <h3 class="text-18px font-semibold">
              {{ $t('page.home.greeting', { userName: authStore.userInfo.userName }) }}
            </h3>
            <p class="text-12px text-gray-500 leading-30px">{{ $t('page.home.loginTime') }}：{{ loginTime }}</p>
          </div>
        </div>
      </ElCol>
    </ElRow>
  </ElCard>
</template>

<style scoped></style>
