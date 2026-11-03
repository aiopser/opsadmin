<script setup lang="ts">
import { computed } from 'vue';
import { parseAnsiOutput } from './shared';

defineOptions({ name: 'AnsiConsole' });

interface Props {
  text: string;
  error?: boolean;
}

const props = defineProps<Props>();
const segments = computed(() => parseAnsiOutput(props.text));
</script>

<template>
  <pre class="run-console" :class="{ 'is-stderr': error }"><span
    v-for="(segment, index) in segments"
    :key="index"
    :class="[segment.color && `ansi-${segment.color}`, { 'ansi-bold': segment.bold }]"
  >{{ segment.text }}</span></pre>
</template>

<style scoped>
.run-console {
  min-height: 115px;
  max-height: 280px;
  margin: 0;
  overflow: auto;
  padding: 16px;
  background: color-mix(in srgb, var(--el-color-black) 85%, var(--el-color-info) 15%);
  color: var(--el-color-white);
  font-family: Consolas, 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.7;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.run-console.is-stderr,
.ansi-red {
  color: var(--el-color-danger-light-5);
}

.ansi-green {
  color: var(--el-color-success-light-5);
}

.ansi-yellow {
  color: var(--el-color-warning-light-5);
}

.ansi-blue {
  color: var(--el-color-primary-light-5);
}

.ansi-magenta {
  color: color-mix(in srgb, var(--el-color-primary-light-5) 50%, var(--el-color-danger-light-5) 50%);
}

.ansi-cyan {
  color: color-mix(in srgb, var(--el-color-primary-light-5) 55%, var(--el-color-success-light-5) 45%);
}

.ansi-black {
  color: var(--el-color-info-light-3);
}

.ansi-white {
  color: var(--el-color-white);
}

.ansi-bold {
  font-weight: 700;
}
</style>
