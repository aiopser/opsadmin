<script setup lang="ts">
import { computed } from 'vue';
import { Codemirror } from 'vue-codemirror';
import { basicSetup } from 'codemirror';
import { StreamLanguage } from '@codemirror/language';
import { shell } from '@codemirror/legacy-modes/mode/shell';
import { powerShell } from '@codemirror/legacy-modes/mode/powershell';
import { javascript } from '@codemirror/legacy-modes/mode/javascript';
import { python } from '@codemirror/lang-python';
import { yaml } from '@codemirror/lang-yaml';
import type { Extension } from '@codemirror/state';

defineOptions({ name: 'CodeEditor' });

type CodeLanguage = 'shell' | 'python' | 'powershell' | 'yaml' | 'json' | 'plaintext';

interface Props {
  modelValue: string;
  language?: CodeLanguage;
  readonly?: boolean;
  height?: string;
  placeholder?: string;
  /** 暗色主题（终端风格深色背景） */
  dark?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  language: 'shell',
  readonly: false,
  height: '300px',
  placeholder: '',
  dark: false
});

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void;
}>();

const languageExtensions: Record<CodeLanguage, Extension[]> = {
  shell: [StreamLanguage.define(shell)],
  python: [python()],
  powershell: [StreamLanguage.define(powerShell)],
  yaml: [yaml()],
  /** JSON 是 JavaScript 子集，复用 JS 高亮（项目未安装 @codemirror/lang-json） */
  json: [StreamLanguage.define(javascript)],
  plaintext: []
};

const extensions = computed(() => [basicSetup, ...languageExtensions[props.language]]);

function onUpdate(value: string) {
  emit('update:modelValue', value);
}
</script>

<template>
  <div class="code-editor-wrapper" :class="{ dark }" :style="{ height }">
    <Codemirror
      :model-value="modelValue"
      :extensions="extensions"
      :disabled="readonly"
      :placeholder="placeholder"
      class="code-editor"
      @update:model-value="onUpdate"
    />
  </div>
</template>

<style scoped>
.code-editor-wrapper {
  width: 100%;
  overflow: hidden;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
}

.code-editor {
  height: 100%;
}

.code-editor :deep(.cm-editor) {
  height: 100%;
  background: #fff;
  font-size: 13px;
}

.code-editor :deep(.cm-editor.cm-focused) {
  outline: none;
}

.code-editor :deep(.cm-gutters) {
  background: #fafafa;
  border-right: 1px solid #ebeef5;
  color: #909399;
}

/* 暗色主题（终端风格，项目无暗色主题变量，此处为独立色板） */
.code-editor-wrapper.dark {
  border-color: #414243;
}

.dark :deep(.cm-editor) {
  background: #1e1e1e;
  color: #d4d4d4;
}

.dark :deep(.cm-editor.cm-focused) {
  outline: none;
}

.dark :deep(.cm-gutters) {
  background: #262727;
  border-right-color: #333;
  color: #858585;
}
</style>
