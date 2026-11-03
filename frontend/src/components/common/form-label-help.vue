<script setup lang="ts">
import { computed } from 'vue';

defineOptions({ name: 'FormLabelHelp' });

interface Props {
  /** 字段名称 */
  label: string;
  /** 使用说明：字符串按换行拆分，数组每一项为一行 */
  help: string | string[];
  /** 标签后缀，渲染在问号之后；默认中文冒号，传空字符串则不渲染 */
  suffix?: string;
}

const props = withDefaults(defineProps<Props>(), {
  suffix: '：'
});

const lines = computed(() => (Array.isArray(props.help) ? props.help : props.help.split('\n')));
</script>

<template>
  <span class="inline-flex items-center gap-4px whitespace-nowrap">
    <span class="shrink-0">{{ label }}</span>
    <ElTooltip placement="top" effect="dark">
      <template #content>
        <p v-for="(line, idx) in lines" :key="idx" class="leading-22px">{{ line }}</p>
      </template>
      <icon-fe-question class="shrink-0 cursor-help text-15px text-gray-400 hover:text-gray-600" />
    </ElTooltip>
    <span v-if="suffix" class="shrink-0">{{ suffix }}</span>
  </span>
</template>
