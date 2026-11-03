<script setup lang="ts">
defineOptions({ name: 'ExecutionSettingsFields' });

type HostStrategy = 'inherit' | 'parallel' | 'serial' | 'rolling';

const hostStrategy = defineModel<HostStrategy>('hostStrategy', { required: true });
const forks = defineModel<number | null>('forks', { required: true, set: value => value ?? null });
const serialBatch = defineModel<number | null>('serialBatch', { required: true, set: value => value ?? null });
const maxFailPercentage = defineModel<number | null>('maxFailPercentage', {
  required: true,
  set: value => value ?? null
});
const timeoutSeconds = defineModel<number | null>('timeoutSeconds', { required: true, set: value => value ?? null });

const hostStrategyOptions = [
  { value: 'inherit', label: '继承全局' },
  { value: 'parallel', label: '并行' },
  { value: 'serial', label: '串行' },
  { value: 'rolling', label: '滚动' }
] as const;
</script>

<template>
  <div>
    <ElFormItem label="执行策略">
      <ElRadioGroup v-model="hostStrategy">
        <ElRadio v-for="item in hostStrategyOptions" :key="item.value" :value="item.value">
          {{ item.label }}
        </ElRadio>
      </ElRadioGroup>
      <p class="mb-0 mt-6px w-full text-12px text-[var(--el-text-color-regular)]">
        并行按并发数执行，串行逐台执行，滚动分批执行；未填写的值继承全局。
      </p>
    </ElFormItem>
    <ElFormItem v-if="hostStrategy === 'rolling' || hostStrategy === 'inherit'" label="每批主机数">
      <ElInputNumber v-model="serialBatch" :min="1" :precision="0" placeholder="留空继承全局" />
    </ElFormItem>
    <ElFormItem label="并发数（forks）">
      <ElInputNumber
        v-model="forks"
        :min="1"
        :max="100"
        :precision="0"
        :disabled="hostStrategy === 'serial'"
        placeholder="留空继承全局"
      />
      <p v-if="hostStrategy === 'serial'" class="mb-0 mt-6px w-full text-12px text-[var(--el-text-color-regular)]">
        串行策略固定为 1，逐台执行。
      </p>
    </ElFormItem>
    <ElFormItem label="最大失败比例（%）">
      <ElInputNumber v-model="maxFailPercentage" :min="0" :max="100" :precision="0" placeholder="留空继承全局" />
      <p class="mb-0 mt-6px w-full text-12px text-[var(--el-text-color-regular)]">
        0 表示零容忍；失败主机占比超过设置值时终止剩余执行。
      </p>
    </ElFormItem>
    <ElFormItem label="整个流程超时（秒）">
      <ElInputNumber
        v-model="timeoutSeconds"
        :min="1"
        :max="86400"
        :step="60"
        :precision="0"
        placeholder="留空继承全局"
      />
      <p class="mb-0 mt-6px w-full text-12px text-[var(--el-text-color-regular)]">
        限制整个流程的总耗时，包含所有步骤。
      </p>
    </ElFormItem>
  </div>
</template>
