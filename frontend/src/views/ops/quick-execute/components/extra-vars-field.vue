<script setup lang="ts">
import { ref } from 'vue';

defineOptions({ name: 'QuickExecuteExtraVarsField' });

const text = ref('');
const error = ref('');

function getValue(): Record<string, unknown> | null {
  try {
    const value: unknown = JSON.parse(text.value.trim() || '{}');
    if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('JSON object required');
    error.value = '';
    return value as Record<string, unknown>;
  } catch {
    error.value = '请填写有效的 JSON 对象';
    return null;
  }
}

function reset() {
  text.value = '';
  error.value = '';
}

defineExpose({ getValue, reset });
</script>

<template>
  <ElFormItem label="额外变量" :error="error">
    <div class="w-full">
      <ElInput
        v-model="text"
        type="textarea"
        :rows="3"
        placeholder='extra_vars，JSON 对象，例如 {"service_name": "nginx"}'
      />
      <p class="mb-0 mt-6px text-12px text-[var(--el-text-color-regular)]">
        自动继承所选资源的默认 extra_vars；此处仅填写本次覆盖值。变量传入
        Ansible，不会自动转成脚本环境变量或命令行参数。
      </p>
    </div>
  </ElFormItem>
</template>
