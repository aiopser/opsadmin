<script setup lang="ts">
import { computed } from 'vue';
import { Codemirror } from 'vue-codemirror';
import { basicSetup } from 'codemirror';
import { StreamLanguage } from '@codemirror/language';
import { shell } from '@codemirror/legacy-modes/mode/shell';
import { powerShell } from '@codemirror/legacy-modes/mode/powershell';
import { python } from '@codemirror/lang-python';
import { yaml } from '@codemirror/lang-yaml';
import type { Extension } from '@codemirror/state';

defineOptions({ name: 'CodeEditor' });

type CodeLanguage = 'shell' | 'python' | 'powershell' | 'yaml' | 'plaintext';

interface Props {
  modelValue: string;
  language?: CodeLanguage;
  readonly?: boolean;
  height?: string;
  placeholder?: string;
}

const props = withDefaults(defineProps<Props>(), {
  language: 'shell',
  readonly: false,
  height: '300px',
  placeholder: ''
});

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void;
}>();

const languageExtensions: Record<CodeLanguage, Extension[]> = {
  shell: [StreamLanguage.define(shell)],
  python: [python()],
  powershell: [StreamLanguage.define(powerShell)],
  yaml: [yaml()],
  plaintext: []
};

const extensions = computed(() => [basicSetup, ...languageExtensions[props.language]]);

function onUpdate(value: string) {
  emit('update:modelValue', value);
}
</script>

<template>
  <div class="code-editor-wrapper" :style="{ height }">
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
</style>
