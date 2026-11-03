<script setup lang="ts">
import { computed, onUnmounted, ref, shallowRef, watch } from 'vue';
import type { ConsulConnection, HostImportInput, HostImportPreview } from '@/service/api/monitoring';
import { commitHostImport, previewHostImport } from '@/service/api/monitoring';

defineOptions({ name: 'MonitoringHostImportDrawer' });

interface Props {
  visible: boolean;
  connections: ConsulConnection[];
}
const props = defineProps<Props>();
const emit = defineEmits<{
  'update:visible': [value: boolean];
  completed: [];
}>();

const open = computed({
  get: () => props.visible,
  set: value => emit('update:visible', value)
});
const step = ref(0);
const connectionId = ref<number>();
const selectedHosts = shallowRef<Api.Cmdb.HostRecord[]>([]);
const hostsVisible = ref(false);
const addressSource = ref<'internal' | 'external'>('internal');
const port = ref(9100);
const interval = ref(0);
const followAddress = ref(false);
const preview = shallowRef<HostImportPreview>();
const confirmedInput = shallowRef<HostImportInput>();
const loading = ref(false);
const saving = ref(false);
const page = ref(1);
const previewRows = computed(() => preview.value?.rows.slice((page.value - 1) * 20, page.value * 20) || []);
let sequence = 0;

function reset() {
  sequence += 1;
  step.value = 0;
  selectedHosts.value = [];
  connectionId.value = undefined;
  addressSource.value = 'internal';
  port.value = 9100;
  interval.value = 0;
  followAddress.value = false;
  preview.value = undefined;
  confirmedInput.value = undefined;
  page.value = 1;
  loading.value = false;
}
function chooseHosts() {
  hostsVisible.value = true;
}
function confirmHosts(hosts: Api.Cmdb.HostRecord[]) {
  selectedHosts.value = hosts;
  hostsVisible.value = false;
}
function buildInput(): HostImportInput | undefined {
  if (!connectionId.value) return undefined;
  return {
    connection: connectionId.value,
    host_ids: selectedHosts.value.map(host => host.id),
    address_source: addressSource.value,
    port: port.value,
    sync_interval_minutes: interval.value,
    follow_host_address: followAddress.value
  };
}
function validNumericConfig() {
  return (
    Number.isInteger(port.value) &&
    port.value >= 1 &&
    port.value <= 65535 &&
    Number.isInteger(interval.value) &&
    interval.value >= 0 &&
    interval.value <= 10080
  );
}
async function readPreview() {
  if (!validNumericConfig()) {
    window.$message?.warning('请填写有效的整数端口和同步间隔');
    return;
  }
  if (!connectionId.value || !selectedHosts.value.length) {
    window.$message?.warning('请选择连接和主机');
    return;
  }
  if (selectedHosts.value.length > 200) {
    window.$message?.warning('每次最多接入 200 台主机');
    return;
  }
  sequence += 1;
  const requestId = sequence;
  const input = buildInput();
  if (!input) return;
  loading.value = true;
  try {
    const { data, error } = await previewHostImport(input);
    if (requestId !== sequence || !props.visible) return;
    if (JSON.stringify(input) !== JSON.stringify(buildInput())) {
      window.$message?.warning('配置已变化，请重新预览');
      return;
    }
    if (!error && data) {
      preview.value = data;
      confirmedInput.value = input;
      step.value = 1;
      page.value = 1;
    }
  } finally {
    if (requestId === sequence) loading.value = false;
  }
}
function back() {
  step.value = 0;
  preview.value = undefined;
  confirmedInput.value = undefined;
}
async function confirm() {
  if (saving.value || !confirmedInput.value || !preview.value?.create_count) return;
  saving.value = true;
  try {
    const { data, error } = await commitHostImport({
      ...confirmedInput.value,
      preview_token: preview.value.preview_token
    });
    if (error) {
      preview.value = undefined;
      confirmedInput.value = undefined;
      step.value = 0;
      return;
    }
    if (data) {
      if (data.delivery_failed)
        window.$message?.warning(`已创建 ${data.created} 个目标，部分注册任务投递失败，请查看记录`);
      else window.$notification?.success(`已创建 ${data.created} 个目标，跳过 ${data.skipped} 台；请查看同步状态`);
      emit('completed');
      emit('update:visible', false);
    }
  } finally {
    saving.value = false;
  }
}
function actionLabel(value: string) {
  return (
    (
      {
        create: '新增',
        exists: '已存在',
        duplicate: '重复 IP',
        invalid: '无效'
      } as Record<string, string>
    )[value] || value
  );
}
function close() {
  if (!saving.value) emit('update:visible', false);
}

watch(
  () => props.visible,
  value => {
    if (value) reset();
    else {
      sequence += 1;
      hostsVisible.value = false;
    }
  }
);
onUnmounted(() => {
  sequence += 1;
});
</script>

<template>
  <ElDrawer
    v-model="open"
    title="从主机资产接入监控"
    size="820px"
    :close-on-click-modal="false"
    :close-on-press-escape="!saving"
    :show-close="!saving"
  >
    <div class="flex-col gap-20px">
      <ElSteps :active="step" finish-status="success" simple>
        <ElStep title="选择主机与配置" />
        <ElStep title="预览并接入" />
      </ElSteps>
      <ElForm
        v-if="step === 0"
        :disabled="loading"
        label-width="132px"
        label-suffix="："
        require-asterisk-position="left"
      >
        <ElFormItem required>
          <template #label>
            <FormLabelHelp label="Consul 连接" :help="['主机服务将注册到该 Agent；停用的连接不可选择。']" />
          </template>
          <ElSelect v-model="connectionId" class="w-full" placeholder="请选择连接">
            <ElOption
              v-for="item in connections"
              :key="item.id"
              :value="item.id"
              :label="item.name"
              :disabled="!item.is_active"
            />
          </ElSelect>
        </ElFormItem>
        <ElFormItem required>
          <template #label>
            <FormLabelHelp
              label="主机"
              :help="['仅可选择已启用 SSH 的 Linux 主机；批量接入共用相同的端口与同步设置。']"
            />
          </template>
          <div class="flex items-center gap-12px">
            <ElButton @click="chooseHosts">选择主机</ElButton>
            <span>已选 {{ selectedHosts.length }} 台</span>
          </div>
        </ElFormItem>
        <ElFormItem>
          <template #label>
            <FormLabelHelp
              label="监控地址"
              :help="['注册服务时使用 CMDB 内网或外网 IP；缺失所选 IP 的主机在同步时跳过。']"
            />
          </template>
          <ElRadioGroup v-model="addressSource">
            <ElRadio value="internal">内网 IP</ElRadio>
            <ElRadio value="external">外网 IP</ElRadio>
          </ElRadioGroup>
        </ElFormItem>
        <ElFormItem label="Exporter 端口">
          <div>
            <ElInputNumber v-model="port" :min="1" :max="65535" controls-position="right" />
            <p class="mt-6px text-12px text-[var(--el-text-color-secondary)]">
              需要预先部署主机 Exporter；不同端口的主机请分批接入。
            </p>
          </div>
        </ElFormItem>
        <ElFormItem label="定时同步">
          <div>
            <ElInputNumber v-model="interval" :min="0" :max="10080" controls-position="right" />
            <span class="ml-8px">分钟</span>
            <p class="mt-6px text-12px text-[var(--el-text-color-secondary)]">
              0 为关闭，启用后由当前账号授权执行；不会自动纳管以后新增的资产。
            </p>
          </div>
        </ElFormItem>
        <ElFormItem label="跟随资产 IP">
          <div>
            <ElRadioGroup v-model="followAddress">
              <ElRadio :value="false">保持当前地址</ElRadio>
              <ElRadio :value="true">跟随所选 IP</ElRadio>
            </ElRadioGroup>
            <p class="mt-6px text-12px text-[var(--el-text-color-secondary)]">
              启用定时同步后生效。资产失效或缺少所选 IP 时跳过，不注销旧服务。
            </p>
          </div>
        </ElFormItem>
      </ElForm>
      <template v-else>
        <p class="text-12px text-[var(--el-text-color-secondary)]">
          可新增 {{ preview?.create_count || 0 }} 台，跳过
          {{ preview?.skip_count || 0 }}
          台。已有目标保留原配置；确认后创建目标并提交注册，不安装 Exporter。
        </p>
        <ElTable :data="previewRows" border>
          <ElTableColumn prop="name" label="主机" min-width="150" align="center" show-overflow-tooltip />
          <ElTableColumn prop="address" label="监控地址" min-width="140" align="center" />
          <ElTableColumn label="处理" width="100" align="center">
            <template #default="{ row }">{{ actionLabel(row.action) }}</template>
          </ElTableColumn>
          <ElTableColumn prop="reason" label="说明" min-width="230" align="center" show-overflow-tooltip />
        </ElTable>
        <ElPagination
          v-model:current-page="page"
          class="justify-end"
          :total="preview?.rows.length || 0"
          :page-size="20"
          layout="total, prev, pager, next"
        />
      </template>
    </div>
    <template #footer>
      <ElButton :disabled="saving" @click="close">取消</ElButton>
      <ElButton v-if="step === 1" :disabled="saving" @click="back">上一步</ElButton>
      <ElButton v-if="step === 0" type="primary" :loading="loading" @click="readPreview">读取并预览</ElButton>
      <ElButton v-else type="primary" :loading="saving" :disabled="!preview?.create_count" @click="confirm">
        确认接入 · {{ preview?.create_count || 0 }} 台
      </ElButton>
    </template>
    <HostSelectModal v-model:visible="hostsVisible" :selected-hosts="selectedHosts" @confirm="confirmHosts" />
  </ElDrawer>
</template>
