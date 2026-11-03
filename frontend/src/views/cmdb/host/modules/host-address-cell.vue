<script setup lang="ts">
import { ref } from 'vue';
import { useSupported, useTimeoutFn } from '@vueuse/core';

defineOptions({ name: 'CmdbHostAddressCell' });

interface Props {
  ip?: string | null;
}

const props = defineProps<Props>();

const isSupported = useSupported(() => typeof navigator.clipboard?.writeText === 'function');
const copied = ref(false);
const copying = ref(false);
const { start: clearCopiedLater } = useTimeoutFn(
  () => {
    copied.value = false;
  },
  1500,
  { immediate: false }
);

/** 悬浮显示复制图标，点击写入剪贴板 */
async function handleCopy() {
  const address = props.ip;
  if (!address || copying.value) return;
  if (!isSupported.value) {
    window.$message?.warning('当前浏览器不支持一键复制');
    return;
  }
  copying.value = true;
  copied.value = false;
  try {
    // 直接使用浏览器的写入结果，避免工具库回退失败后仍标记为成功。
    await navigator.clipboard.writeText(address);
    copied.value = true;
    clearCopiedLater();
    window.$notification?.success(`已复制 ${address}`);
  } catch {
    window.$message?.error('复制失败，请检查浏览器剪贴板权限，或手动选择地址复制');
  } finally {
    copying.value = false;
  }
}
</script>

<template>
  <span v-if="ip" class="group inline-grid grid-cols-[16px_auto_16px] items-center gap-x-4px whitespace-nowrap">
    <span aria-hidden="true"></span>
    <span class="tabular-nums">{{ ip }}</span>
    <span class="relative h-32px w-16px">
      <ElTooltip :content="copied ? '已复制' : '复制 IP 地址'" placement="top" :show-after="200">
        <ElButton
          link
          size="small"
          native-type="button"
          :aria-label="`复制 IP 地址 ${ip}`"
          :disabled="copying"
          class="absolute left-1/2 top-1/2 h-32px w-32px opacity-0 transition-opacity duration-150 -translate-x-1/2 -translate-y-1/2 !p-0 focus-visible:opacity-100 group-focus-within:opacity-100 group-hover:opacity-100 lt-sm:opacity-100"
          @click="handleCopy"
        >
          <ElIcon aria-hidden="true">
            <icon-mdi-check v-if="copied" />
            <icon-mdi-content-copy v-else />
          </ElIcon>
        </ElButton>
      </ElTooltip>
    </span>
  </span>
  <span v-else>—</span>
</template>
