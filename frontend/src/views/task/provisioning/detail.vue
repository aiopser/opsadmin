<script setup lang="ts">
import { computed, ref, shallowRef, watch } from 'vue';
import { useIntervalFn } from '@vueuse/core';
import { ElMessageBox } from 'element-plus';
import { fetchResourceApplication, fetchResourceEvents, resourceAction } from '@/service/api/provisioning';
import type { ResourceApplication, ResourceEvent } from '@/service/api/provisioning';
import { statusLabel } from './shared';
import StateProtection from './state-protection.vue';
import ManualResolution from './manual-resolution.vue';

defineOptions({ name: 'ResourceApplicationDetail' });
const props = defineProps<{ requestId?: number }>();
const emit = defineEmits<{ updated: [] }>();
const visible = defineModel<boolean>({ default: false });
const record = shallowRef<ResourceApplication>();
const loading = ref(false);
const busy = ref(false);
const events = shallowRef<ResourceEvent[]>([]);
const executionKey = ref('');
const loadSequence = ref(0);
const plan = computed(() =>
  record.value?.plans.reduce<ResourceApplication['plans'][number] | undefined>(
    (latest, item) => (!latest || item.id > latest.id ? item : latest),
    undefined
  )
);
const canAct = (action: string) => Boolean(record.value?.allowed_actions.includes(action));
const running = computed(
  () =>
    ['queued', 'running'].includes(plan.value?.status ?? '') ||
    ['queued', 'running'].includes(record.value?.execution_status ?? '') ||
    record.value?.inventory_status === 'pending'
);

async function load() {
  if (!props.requestId || loading.value) return;
  const id = props.requestId;
  const sequence = loadSequence.value + 1;
  loadSequence.value = sequence;
  loading.value = true;
  try {
    const { data, error } = await fetchResourceApplication(id);
    if (sequence !== loadSequence.value) return;
    if (!error && data) record.value = data;
    const history = await fetchResourceEvents(id);
    if (sequence !== loadSequence.value) return;
    if (!history.error) events.value = history.data ?? [];
  } finally {
    if (sequence === loadSequence.value) loading.value = false;
  }
}

async function act(action: 'plan' | 'confirm' | 'approve' | 'reject' | 'execute' | 'reconcile') {
  if (!record.value || busy.value) return;
  if (action === 'execute') {
    try {
      await ElMessageBox.confirm(
        `将在 ${record.value.source_name} / ${record.value.region} 创建 ${record.value.parameters.count} 台主机，产生云资源费用。是否执行已审批计划？`,
        '确认创建资源',
        { type: 'warning', confirmButtonText: '确认执行', cancelButtonText: '取消' }
      );
    } catch {
      return;
    }
  }
  busy.value = true;
  try {
    const { error } = await resourceAction(record.value.id, action, { plan: plan.value, key: executionKey.value });
    if (!error) {
      await load();
      emit('updated');
    }
  } finally {
    busy.value = false;
  }
}

async function resolutionUpdated() {
  loadSequence.value += 1;
  loading.value = false;
  await load();
  emit('updated');
}

useIntervalFn(() => {
  if (visible.value && running.value) load();
}, 4000);

watch([visible, () => props.requestId], ([value]) => {
  if (value) {
    loadSequence.value += 1;
    loading.value = false;
    record.value = undefined;
    events.value = [];
    executionKey.value = globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random()}`;
    load();
  }
});
</script>

<template>
  <ElDrawer v-model="visible" title="资源申请详情" size="900px">
    <ElSkeleton v-if="!record" :loading="loading" animated :rows="8" />
    <div v-else class="flex-col gap-24px">
      <div class="flex items-center justify-between gap-16px">
        <span>{{ record.name }} · #{{ record.id }}</span>
        <ElButton :loading="loading" @click="load">刷新</ElButton>
      </div>
      <ElDescriptions :column="2" border>
        <ElDescriptionsItem label="云账号">{{ record.source_name }}</ElDescriptionsItem>
        <ElDescriptionsItem label="地域">{{ record.region }}</ElDescriptionsItem>
        <ElDescriptionsItem label="资源模板">{{ record.template_name }}</ElDescriptionsItem>
        <ElDescriptionsItem label="数量">{{ record.parameters.count }} 台</ElDescriptionsItem>
        <ElDescriptionsItem label="审批">{{ statusLabel(record.approval_status) }}</ElDescriptionsItem>
        <ElDescriptionsItem label="执行">{{ statusLabel(record.execution_status) }}</ElDescriptionsItem>
        <ElDescriptionsItem label="纳管">{{ statusLabel(record.inventory_status) }}</ElDescriptionsItem>
        <ElDescriptionsItem label="系统盘">{{ record.parameters.system_disk_gb }} GiB</ElDescriptionsItem>
        <ElDescriptionsItem label="规格">{{ record.parameters.instance_type }}</ElDescriptionsItem>
        <ElDescriptionsItem label="镜像">{{ record.parameters.image_id }}</ElDescriptionsItem>
        <ElDescriptionsItem label="VPC">{{ record.parameters.vpc_id }}</ElDescriptionsItem>
        <ElDescriptionsItem label="子网">{{ record.parameters.subnet_id }}</ElDescriptionsItem>
        <ElDescriptionsItem label="安全组" :span="2">
          {{ record.parameters.security_group_ids.join('、') }}
        </ElDescriptionsItem>
      </ElDescriptions>
      <StateProtection :record="record" @updated="load" />
      <ElAlert
        v-if="plan?.attempt?.error_message"
        :title="plan.attempt.error_message"
        type="error"
        :closable="false"
        show-icon
      />
      <ElDescriptions v-if="plan?.attempt?.instance_ids.length" :column="1" border>
        <ElDescriptionsItem label="云实例 ID">{{ plan.attempt.instance_ids.join('、') }}</ElDescriptionsItem>
        <ElDescriptionsItem label="资产 ID">{{ plan.attempt.asset_ids.join('、') || '等待纳管' }}</ElDescriptionsItem>
      </ElDescriptions>
      <div class="flex-col gap-12px">
        <div class="flex items-center justify-between gap-12px">
          <span>
            变更计划
            <span v-if="plan" class="text-color-secondary ml-12px">{{ statusLabel(plan.status) }}</span>
          </span>
          <ElButton
            v-if="canAct('plan')"
            :disabled="running || record.execution_status !== 'not_started'"
            :loading="busy"
            @click="act('plan')"
          >
            生成计划
          </ElButton>
        </div>
        <ElAlert v-if="plan?.error_message" :title="plan.error_message" type="error" :closable="false" show-icon />
        <ElTable v-if="plan?.summary.length" :data="plan.summary" border>
          <ElTableColumn prop="address" label="资源" min-width="240" show-overflow-tooltip />
          <ElTableColumn prop="type" label="资源类型" min-width="160" align="center" />
          <ElTableColumn label="变更" width="100" align="center">
            <template #default><ElTag type="success" size="small">新增</ElTag></template>
          </ElTableColumn>
        </ElTable>
        <ElEmpty v-else-if="!plan" description="尚未生成变更计划" :image-size="64" />
        <span v-if="plan?.status === 'ready'" class="text-color-secondary">
          计划有效期至 {{ plan.expires_at }}。参数或凭据变化后需重新生成。
        </span>
      </div>
      <ElAlert
        v-if="record.execution_status === 'needs_reconciliation'"
        title="执行结果待核实。请回读已知资源，由独立复核人依据完整证据核实结案，勿重复申请。"
        type="warning"
        :closable="false"
        show-icon
      />
      <ManualResolution :key="record.id" :record="record" @updated="resolutionUpdated" />
      <ElAlert
        v-if="record.execution_status === 'success' && record.inventory_status !== 'success'"
        title="资源已创建，尚未完成纳管。重新核实只回读资产，不会再次创建。"
        type="warning"
        :closable="false"
        show-icon
      />
      <div class="flex flex-wrap justify-end gap-8px">
        <ElButton
          v-if="canAct('confirm') && plan?.status === 'ready' && !plan.confirmed_by"
          :loading="busy"
          @click="act('confirm')"
        >
          确认计划并提交审批
        </ElButton>
        <ElButton
          v-if="canAct('reject') && plan?.confirmed_by && record.approval_status === 'pending'"
          :loading="busy"
          @click="act('reject')"
        >
          拒绝
        </ElButton>
        <ElButton
          v-if="canAct('approve') && plan?.confirmed_by && record.approval_status === 'pending'"
          type="primary"
          :loading="busy"
          @click="act('approve')"
        >
          审批通过
        </ElButton>
        <ElButton
          v-if="
            canAct('execute') &&
            ['approved', 'not_required'].includes(record.approval_status) &&
            record.execution_status === 'not_started'
          "
          type="primary"
          :loading="busy"
          @click="act('execute')"
        >
          执行创建
        </ElButton>
        <ElButton
          v-if="canAct('reconcile') && ['success', 'needs_reconciliation'].includes(record.execution_status)"
          :loading="busy"
          @click="act('reconcile')"
        >
          重新核实与纳管
        </ElButton>
      </div>
      <ElCollapse v-if="events.length">
        <ElCollapseItem title="操作记录" name="events">
          <ElTimeline>
            <ElTimelineItem v-for="item in events" :key="item.id" :timestamp="item.created_at">
              {{ item.message }}
            </ElTimelineItem>
          </ElTimeline>
        </ElCollapseItem>
      </ElCollapse>
    </div>
  </ElDrawer>
</template>
