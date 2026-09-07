<script setup lang="ts">
import { computed } from 'vue';
import { useSiteConfigStore } from '@/store/modules/site-config';
import { $t } from '@/locales';

defineOptions({ name: 'GlobalLogo' });

interface Props {
  /** Whether to show the title */
  showTitle?: boolean;
  /** Whether to show the icon */
  showIcon?: boolean;
}

withDefaults(defineProps<Props>(), {
  showTitle: true,
  showIcon: true
});

const siteConfigStore = useSiteConfigStore();

/** 系统名称：优先取系统配置 basic.system.name，未配置回退 i18n */
const systemTitle = computed(() => siteConfigStore.siteName || $t('system.title'));
</script>

<template>
  <RouterLink to="/" class="w-full flex-center nowrap-hidden">
    <SystemLogo v-if="showIcon" class="size-32px" />
    <h2
      v-show="showTitle"
      class="text-16px text-primary font-bold transition duration-300 ease-in-out"
      :class="showIcon ? 'pl-8px' : ''"
    >
      {{ systemTitle }}
    </h2>
  </RouterLink>
</template>

<style scoped></style>
