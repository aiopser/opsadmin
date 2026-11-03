<script setup lang="ts">
defineOptions({ name: 'RunPreviewDialog' });

interface Props {
  visible: boolean;
  preview: Api.Jobs.RunPreview | null;
  loading?: boolean;
  title?: string;
  confirmText?: string;
  note?: string;
}

defineProps<Props>();

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void;
  (e: 'confirm'): void;
}>();

const policySourceLabels: Record<string, string> = {
  native: 'Playbook 原生策略',
  step: '步骤单独设置',
  run: '继承任务运行设置',
  none: '无需主机'
};
const strategyLabels: Record<string, string> = {
  inherit: '继承全局',
  parallel: '并行',
  serial: '串行',
  rolling: '滚动'
};

function close() {
  emit('update:visible', false);
}

function confirm() {
  emit('confirm');
}
</script>

<template>
  <ElDialog :model-value="visible" :title="title || '确认执行范围'" width="720px" @close="close">
    <div v-if="preview" class="flex flex-col gap-16px">
      <ElAlert v-if="note" type="warning" :title="note" :closable="false" show-icon />
      <ElAlert type="info" :closable="false" show-icon>
        <template #title>
          {{ preview.workflowName }} · {{ preview.targetCount }} 台目标主机 · {{ preview.steps.length }} 个执行步骤
        </template>
      </ElAlert>
      <div>
        <div class="mb-8px font-500">执行步骤</div>
        <ElTable :data="preview.steps" border class="w-full" max-height="220">
          <ElTableColumn type="index" label="#" width="55" />
          <ElTableColumn prop="name" label="步骤" min-width="180" show-overflow-tooltip />
          <ElTableColumn label="主机策略" width="160" align="center">
            <template #default="{ row }">{{ policySourceLabels[row.hostPolicySource] || '—' }}</template>
          </ElTableColumn>
          <ElTableColumn label="目标范围" width="160">
            <template #default="{ row }">
              {{ row.targetScope === 'all' ? '继承本次任务目标' : '无需主机' }}
            </template>
          </ElTableColumn>
        </ElTable>
      </div>
      <div v-if="preview.contentSummary?.length">
        <div class="mb-8px font-500">执行内容</div>
        <ElDescriptions :column="2" border>
          <ElDescriptionsItem v-for="item in preview.contentSummary" :key="item.name" :label="item.name">
            {{ item.value }}
          </ElDescriptionsItem>
        </ElDescriptions>
        <div class="mt-8px text-12px text-gray-500">脚本、剧本正文和模块参数不在预览中展示，请在原表单确认。</div>
      </div>
      <div>
        <div class="mb-8px font-500">任务单参数与执行策略</div>
        <div class="text-13px">平台主机策略：{{ strategyLabels[preview.hostStrategy] || '继承全局' }}</div>
        <p class="mb-0 mt-6px text-12px text-[var(--el-text-color-regular)]">
          Playbook 原生策略以剧本为准；步骤单独设置优先于任务运行设置。
        </p>
        <ElTable
          v-if="preview.parameters.length"
          :data="preview.parameters"
          border
          class="mt-8px w-full"
          max-height="180"
        >
          <ElTableColumn prop="name" label="参数" min-width="150" show-overflow-tooltip />
          <ElTableColumn prop="value" label="本次输入" min-width="240" show-overflow-tooltip />
        </ElTable>
      </div>
      <div>
        <div class="mb-8px font-500">实际目标主机（{{ preview.targetCount }} 台）</div>
        <ElTable v-if="preview.targets.length" :data="preview.targets" border class="w-full" max-height="240">
          <ElTableColumn prop="hostname" label="主机名" min-width="180" show-overflow-tooltip />
          <ElTableColumn prop="address" label="连接地址" min-width="180" show-overflow-tooltip />
        </ElTable>
        <ElAlert v-else type="warning" title="本次没有目标主机，仅适用于无需主机的集成步骤" :closable="false" />
      </div>
      <div class="text-12px text-gray-500">
        执行节点：{{ preview.workerPoolName || '自动选择' }} · 连接方式：{{ preview.gatewayName || '直连' }}。
        提交时将再次校验目标；目标变化需要重新确认。
      </div>
    </div>
    <template #footer>
      <ElButton @click="close">返回修改</ElButton>
      <ElButton type="primary" :loading="loading" :disabled="!preview" @click="confirm">
        {{ confirmText || '确认并执行' }}
      </ElButton>
    </template>
  </ElDialog>
</template>
