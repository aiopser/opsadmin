<script setup lang="ts">
import { computed, onScopeDispose, ref, shallowRef, watch } from 'vue';
import { useNow } from '@vueuse/core';
import type { FormInstance, FormRules } from 'element-plus';
import { confirmResourceResolution, previewResourceResolution } from '@/service/api/provisioning';
import type { ResolutionConfirmation, ResolutionPreview, ResourceApplication } from '@/service/api/provisioning';
import { formatLocalDateTime } from '@/utils/common';

defineOptions({ name: 'ProvisioningManualResolution' });

const props = defineProps<{ record: ResourceApplication }>();
const emit = defineEmits<{ updated: [] }>();

const now = useNow({ interval: 1000 });
const visible = ref(false);
const preview = shallowRef<ResolutionPreview>();
const errorMessage = ref('');
const previewLoading = ref(false);
const submitting = ref(false);
const sequence = ref(0);
const form = shallowRef<FormInstance>();
const evidenceReference = ref('');
const comment = ref('');
const acknowledged = ref(false);
const formModel = computed(() => ({ evidenceReference: evidenceReference.value, comment: comment.value }));
const rules: FormRules<Pick<ResolutionConfirmation, 'evidenceReference' | 'comment'>> = {
  evidenceReference: [
    { required: true, whitespace: true, max: 300, message: '请填写工单或外部证据编号', trigger: 'blur' }
  ],
  comment: [
    { required: true, whitespace: true, max: 500, message: '请说明云端清单与执行结果的核实依据', trigger: 'blur' }
  ]
};
const canResolve = computed(
  () =>
    props.record.execution_status === 'needs_reconciliation' &&
    props.record.allowed_actions.includes('resolution-preview') &&
    props.record.allowed_actions.includes('resolution-confirm')
);
const expired = computed(() => {
  if (!preview.value) return false;
  const expiresAt = Date.parse(preview.value.expiresAt);
  return !Number.isFinite(expiresAt) || expiresAt <= now.value.getTime();
});
const canConfirm = computed(
  () =>
    visible.value &&
    canResolve.value &&
    Boolean(preview.value) &&
    !expired.value &&
    acknowledged.value &&
    !previewLoading.value &&
    !submitting.value
);

function isCurrent(id: number, current: number): boolean {
  return visible.value && props.record.id === id && current === sequence.value;
}

function invalidate() {
  sequence.value += 1;
  preview.value = undefined;
  errorMessage.value = '';
  acknowledged.value = false;
  previewLoading.value = false;
  submitting.value = false;
}

async function loadPreview() {
  if (!visible.value || !canResolve.value || submitting.value) return;
  invalidate();
  const id = props.record.id;
  const current = sequence.value;
  previewLoading.value = true;
  try {
    const result = await previewResourceResolution(id);
    if (!isCurrent(id, current)) return;
    if (result.error) {
      errorMessage.value = result.error.response?.data?.msg || '云资源证据暂时无法校验，请稍后重新核实。';
      return;
    }
    preview.value = result.data;
  } catch {
    if (isCurrent(id, current)) errorMessage.value = '核实请求未完成，请检查连接后重新核实。';
  } finally {
    if (isCurrent(id, current)) previewLoading.value = false;
  }
}

async function open() {
  if (!canResolve.value) return;
  evidenceReference.value = '';
  comment.value = '';
  visible.value = true;
  await loadPreview();
}

function close() {
  if (!submitting.value) visible.value = false;
}

async function confirm() {
  if (!canConfirm.value || !preview.value || !form.value) return;
  const valid = await form.value.validate().catch(() => false);
  if (!valid || !canConfirm.value || !preview.value) return;
  const id = props.record.id;
  const current = sequence.value;
  const payload: ResolutionConfirmation = {
    previewId: preview.value.previewId,
    digest: preview.value.digest,
    evidenceReference: evidenceReference.value.trim(),
    comment: comment.value.trim()
  };
  submitting.value = true;
  errorMessage.value = '';
  try {
    const result = await confirmResourceResolution(id, payload);
    if (!isCurrent(id, current)) return;
    if (result.error) {
      preview.value = undefined;
      acknowledged.value = false;
      errorMessage.value = result.error.response?.data?.msg || '结案确认未通过，请重新核实云资源证据。';
      return;
    }
    visible.value = false;
    window.$notification?.success('已核实创建结果，现有实例已纳管并结案');
    emit('updated');
  } catch {
    if (!isCurrent(id, current)) return;
    preview.value = undefined;
    acknowledged.value = false;
    errorMessage.value = '确认响应未完成，请刷新申请状态后重新核实。';
  } finally {
    if (isCurrent(id, current)) submitting.value = false;
  }
}

watch(visible, value => {
  if (!value) invalidate();
});
watch([() => props.record.id, canResolve], () => {
  visible.value = false;
  invalidate();
});
onScopeDispose(invalidate);
</script>

<template>
  <div v-if="canResolve" class="flex justify-end">
    <ElButton @click="open">人工核实结案</ElButton>
    <ElDialog
      v-model="visible"
      title="人工核实创建结果"
      width="min(920px, calc(100vw - 48px))"
      append-to-body
      :close-on-click-modal="false"
      :close-on-press-escape="!submitting"
      :show-close="!submitting"
    >
      <div class="flex-col gap-20px">
        <ElAlert
          title="逐一核对现有实例与外部证据后，再确认纳管并结案。"
          description="仅处理已有执行的创建结果，不会重新创建主机。缺少完整状态证据、备份或实例时，申请继续保留待核实。"
          type="warning"
          :closable="false"
          show-icon
        />
        <ElDescriptions :column="2" border>
          <ElDescriptionsItem label="申请">{{ record.name }} · #{{ record.id }}</ElDescriptionsItem>
          <ElDescriptionsItem label="云账号">{{ record.source_name }}</ElDescriptionsItem>
          <ElDescriptionsItem label="地域">{{ record.region }}</ElDescriptionsItem>
          <ElDescriptionsItem label="申请数量">{{ record.parameters.count }} 台</ElDescriptionsItem>
        </ElDescriptions>
        <ElSkeleton v-if="previewLoading" :rows="5" animated />
        <ElAlert
          v-if="errorMessage"
          :title="errorMessage"
          description="请保留工单和执行归档，修复上述问题后重新核实。"
          type="error"
          :closable="false"
          show-icon
        />
        <template v-if="preview">
          <ElDescriptions :column="2" border>
            <ElDescriptionsItem label="状态证据版本">#{{ preview.stateVersionId }}</ElDescriptionsItem>
            <ElDescriptionsItem label="状态序列">{{ preview.serial }}</ElDescriptionsItem>
            <ElDescriptionsItem label="状态证据摘要" :span="2">
              <span class="break-all text-12px font-mono">{{ preview.stateDigest }}</span>
            </ElDescriptionsItem>
            <ElDescriptionsItem label="预览有效期" :span="2">
              {{ formatLocalDateTime(preview.expiresAt) }}
            </ElDescriptionsItem>
          </ElDescriptions>
          <div class="flex-col gap-8px">
            <span>云端已核实 {{ preview.instanceIds.length }} 台实例</span>
            <ElTable :data="preview.observedAssets" border max-height="280">
              <ElTableColumn prop="instanceId" label="实例 ID" min-width="170" show-overflow-tooltip />
              <ElTableColumn prop="hostname" label="主机名称" min-width="130" show-overflow-tooltip />
              <ElTableColumn prop="internal_ip" label="私网 IP" min-width="140" align="center" />
              <ElTableColumn prop="os_family" label="系统" width="100" align="center" />
              <ElTableColumn prop="cloud_state" label="云运行状态" min-width="110" align="center" />
            </ElTable>
          </div>
          <ElAlert v-if="expired" title="证据预览已过期，请重新核实。" type="warning" :closable="false" show-icon />
        </template>
        <ElForm
          ref="form"
          :model="formModel"
          :rules="rules"
          :disabled="!preview || previewLoading || submitting || expired"
          label-width="120px"
          label-suffix="："
          require-asterisk-position="left"
        >
          <ElFormItem label="外部证据编号" prop="evidenceReference">
            <ElInput
              v-model="evidenceReference"
              maxlength="300"
              placeholder="例如 INC-20261023-001 或内部核实工单链接"
            />
          </ElFormItem>
          <ElFormItem label="核实说明" prop="comment">
            <ElInput
              v-model="comment"
              type="textarea"
              :rows="3"
              maxlength="500"
              show-word-limit
              placeholder="说明云控制台、实例清单与执行状态相符的核实依据"
            />
          </ElFormItem>
          <ElFormItem>
            <ElCheckbox v-model="acknowledged">已将实例清单与云控制台、工单证据逐一核对</ElCheckbox>
          </ElFormItem>
        </ElForm>
      </div>
      <template #footer>
        <ElButton :disabled="submitting" @click="close">取消</ElButton>
        <ElButton :disabled="submitting" :loading="previewLoading" @click="loadPreview">重新核实</ElButton>
        <ElButton type="primary" :disabled="!canConfirm" :loading="submitting" @click="confirm">
          确认纳管并结案
        </ElButton>
      </template>
    </ElDialog>
  </div>
</template>
