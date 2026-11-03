<script setup lang="ts">
import { computed, ref, shallowRef, watch } from 'vue';
import { ElMessageBox } from 'element-plus';
import { confirmStateRestore, fetchStateVersions, previewStateRestore } from '@/service/api/provisioning';
import type { ResourceApplication, StateVersion } from '@/service/api/provisioning';
import { formatLocalDateTime } from '@/utils/common';

defineOptions({ name: 'ProvisioningStateProtection' });
const props = defineProps<{ record: ResourceApplication }>();
const emit = defineEmits<{ updated: [] }>();
const expanded = ref<string[]>([]);
const versions = shallowRef<StateVersion[]>([]);
const loading = ref(false);
const busy = ref(false);
const sequence = ref(0);
const labels: Record<string, string> = {
  protected: '已保护',
  degraded: '备份异常',
  pending: '待校验',
  unverified: '待核实',
  not_applicable: '尚未创建'
};
const summary = computed(() => labels[props.record.stateProtection.status] ?? '待核实');
const canRestore = computed(
  () =>
    props.record.allowed_actions.includes('restore-preview') &&
    props.record.allowed_actions.includes('restore-confirm') &&
    !['queued', 'running', 'needs_reconciliation'].includes(props.record.execution_status)
);
const canRead = computed(() => props.record.allowed_actions.includes('state-versions'));

function statusLabel(status: string) {
  return labels[status] ?? status;
}

async function load() {
  const id = props.record.id;
  const current = sequence.value + 1;
  sequence.value = current;
  loading.value = true;
  try {
    const { data, error } = await fetchStateVersions(id);
    if (sequence.value === current && !error) versions.value = data ?? [];
  } finally {
    if (sequence.value === current) loading.value = false;
  }
}

async function restore(version: StateVersion) {
  if (busy.value) return;
  const id = props.record.id;
  busy.value = true;
  try {
    const { data, error } = await previewStateRestore(id, version.id);
    if (error || !data || props.record.id !== id) return;
    try {
      await ElMessageBox.confirm(
        `恢复状态版本 v${version.version}（序列 ${data.serial}）。涉及实例：${data.instanceIds.join('、') || '未识别到实例 ID'}。${data.notice}，随后只读回查云资源。预览有效期至 ${formatLocalDateTime(data.expiresAt)}。`,
        '确认恢复控制状态',
        { type: 'warning', confirmButtonText: '确认恢复', cancelButtonText: '取消' }
      );
    } catch {
      return;
    }
    if (props.record.id !== id) return;
    const result = await confirmStateRestore(id, data);
    if (!result.error) {
      await load();
      emit('updated');
    }
  } finally {
    busy.value = false;
  }
}

watch(
  () => props.record.id,
  () => {
    sequence.value += 1;
    expanded.value = [];
    versions.value = [];
  }
);
watch(expanded, value => {
  if (value.length && canRead.value) load();
});
</script>

<template>
  <div class="flex-col gap-12px">
    <div class="flex flex-wrap items-center gap-12px">
      <span>状态备份</span>
      <ElTag :type="record.stateProtection.status === 'protected' ? 'success' : 'info'" size="small">
        {{ summary }}
      </ElTag>
      <span v-if="record.stateProtection.verifiedAt" class="text-color-secondary">
        校验时间 {{ formatLocalDateTime(record.stateProtection.verifiedAt) }}
      </span>
    </div>
    <ElAlert
      v-if="
        record.stateProtection.message &&
        (record.stateProtection.status === 'degraded' ||
          (record.execution_status === 'success' && record.stateProtection.status === 'unverified'))
      "
      :title="record.stateProtection.message"
      type="warning"
      :closable="false"
      show-icon
    />
    <ElCollapse v-if="canRead" v-model="expanded">
      <ElCollapseItem title="备份版本与恢复" name="versions">
        <div class="flex-col gap-12px">
          <span class="text-color-secondary">恢复仅修复系统保存的控制状态，不会回滚或重新创建云主机。</span>
          <ElTable v-loading="loading" :data="versions" border empty-text="暂无备份版本">
            <ElTableColumn prop="version" label="版本" width="80" align="center" />
            <ElTableColumn label="保护状态" width="110" align="center">
              <template #default="{ row }">{{ statusLabel(row.status) }}</template>
            </ElTableColumn>
            <ElTableColumn label="创建时间" min-width="180" align="center">
              <template #default="{ row }">{{ formatLocalDateTime(row.createdAt) }}</template>
            </ElTableColumn>
            <ElTableColumn prop="message" label="说明" min-width="160" show-overflow-tooltip />
            <ElTableColumn v-if="canRestore" label="操作" width="110" align="center">
              <template #default="{ row }">
                <ElButton
                  link
                  type="primary"
                  :disabled="!['protected', 'degraded'].includes(row.status)"
                  :loading="busy"
                  @click="restore(row)"
                >
                  校验并恢复
                </ElButton>
              </template>
            </ElTableColumn>
          </ElTable>
        </div>
      </ElCollapseItem>
    </ElCollapse>
  </div>
</template>
