<script setup lang="ts">
defineOptions({ name: 'QuickExecutionPolicyFields' });

type HostStrategy = 'inherit' | 'parallel' | 'serial' | 'rolling';

interface ExecutionPolicyModel {
  hostStrategy: HostStrategy;
  forks: number | null;
  serialBatch: number | null;
  maxFailPercentage: number | null;
  timeoutSeconds: number | null;
}

const model = defineModel<ExecutionPolicyModel>({ required: true });

const hostStrategyOptions: Array<{ label: string; value: HostStrategy }> = [
  { value: 'inherit', label: '继承全局' },
  { value: 'parallel', label: '并行' },
  { value: 'serial', label: '串行' },
  { value: 'rolling', label: '滚动' }
];
</script>

<template>
  <ElCollapse>
    <ElCollapseItem name="execution-policy">
      <template #title>
        高级执行策略
        <span class="ml-8px text-12px text-gray-500">留空项继承全局执行引擎</span>
      </template>
      <div class="grid grid-cols-1 gap-x-16px gap-y-4px md:grid-cols-2 xl:grid-cols-3">
        <ElFormItem label="主机执行策略">
          <template #label>
            <FormLabelHelp
              label="主机执行策略"
              :help="[
                '并行：所有主机同时执行；',
                '串行：按每批主机数逐批执行；',
                '滚动：每批执行完评估结果，失败比例超限即中止；',
                '继承全局：使用执行引擎的全局默认配置。'
              ]"
            />
          </template>
          <ElRadioGroup v-model="model.hostStrategy">
            <ElRadio v-for="option in hostStrategyOptions" :key="option.value" :value="option.value">
              {{ option.label }}
            </ElRadio>
          </ElRadioGroup>
        </ElFormItem>
        <ElFormItem v-if="model.hostStrategy !== 'parallel'" label="每批主机数">
          <template #label>
            <FormLabelHelp label="每批主机数" :help="['串行 / 滚动策略下每批执行的主机数量，留空继承全局。']" />
          </template>
          <ElInputNumber v-model="model.serialBatch" :min="1" placeholder="留空继承全局" />
        </ElFormItem>
        <ElFormItem label="并发数（forks）">
          <template #label>
            <FormLabelHelp
              label="并发数（forks）"
              :help="['Ansible 同时执行的主机数上限，串行策略下不可用；', '留空继承全局。']"
            />
          </template>
          <ElInputNumber
            v-model="model.forks"
            :min="1"
            :max="100"
            :disabled="model.hostStrategy === 'serial'"
            placeholder="留空继承全局"
          />
        </ElFormItem>
        <ElFormItem label="最大失败比例">
          <template #label>
            <FormLabelHelp
              label="最大失败比例"
              :help="['失败主机占比达到该值时中止执行，仅滚动策略生效；', '留空继承全局。']"
            />
          </template>
          <ElInputNumber v-model="model.maxFailPercentage" :min="0" :max="100" placeholder="留空继承全局" />
        </ElFormItem>
        <ElFormItem label="执行超时（秒）">
          <template #label>
            <FormLabelHelp
              label="执行超时（秒）"
              :help="['单次执行的整体超时时间，超时后任务标记为失败；', '留空继承全局。']"
            />
          </template>
          <ElInputNumber v-model="model.timeoutSeconds" :min="1" :max="86400" :step="60" placeholder="留空继承全局" />
        </ElFormItem>
      </div>
    </ElCollapseItem>
  </ElCollapse>
</template>
