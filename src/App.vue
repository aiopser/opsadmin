<script setup lang="ts">
import { computed } from 'vue';
import type { WatermarkProps } from 'element-plus';
import { useAppStore } from './store/modules/app';
import { useSiteConfigStore } from './store/modules/site-config';
import { useThemeStore } from './store/modules/theme';
import { useAuthStore } from './store/modules/auth';
import { UILocales } from './locales/ui';

defineOptions({ name: 'App' });

const appStore = useAppStore();
const themeStore = useThemeStore();
const authStore = useAuthStore();
const siteConfigStore = useSiteConfigStore();
// 拉取站点公开配置（系统名称/登录页标题），完成后刷新浏览器标题使站点名后缀立即生效
siteConfigStore.init().then(() => {
  appStore.updateDocumentTitleByLocale();
});
const locale = computed(() => {
  return UILocales[appStore.locale];
});

const watermarkProps = computed<WatermarkProps>(() => {
  const content =
    themeStore.watermark.enableUserName && authStore.userInfo.userName
      ? authStore.userInfo.userName
      : themeStore.watermark.text;

  return {
    content: themeStore.watermark.visible ? content : '',
    cross: true,
    fontSize: 16,
    lineHeight: 16,
    gap: [100, 120],
    rotate: -15,
    zIndex: 9999
  };
});
</script>

<template>
  <ElConfigProvider :locale="locale">
    <AppProvider>
      <ElWatermark class="h-full" v-bind="watermarkProps">
        <RouterView class="bg-layout" />
      </ElWatermark>
    </AppProvider>
  </ElConfigProvider>
</template>

<style scoped></style>
