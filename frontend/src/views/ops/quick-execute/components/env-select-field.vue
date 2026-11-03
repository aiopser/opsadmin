<script setup lang="ts">
import { ref, shallowRef } from 'vue';
import { fetchGetGatewayList, fetchGetWorkerPools } from '@/service/api';

defineOptions({ name: 'EnvSelectField' });

const workerPoolId = defineModel<number | null>('workerPoolId', { required: true });
const gatewayId = defineModel<number | null>('gatewayId', { required: true });

/** ============ 执行资源与网关选项 ============ */

const workerPools = shallowRef<Api.Jobs.WorkerPoolOption[]>([]);
const gateways = shallowRef<Api.Jobs.GatewayRecord[]>([]);
const defaultWorkerPoolId = ref<number | null>(null);

async function loadWorkerPools() {
  const { data, error } = await fetchGetWorkerPools();
  if (!error && data) {
    workerPools.value = data.list.filter(pool => pool.isActive);
    const defaultPool = workerPools.value.find(pool => pool.isDefault);
    if (defaultPool) {
      defaultWorkerPoolId.value = defaultPool.id;
      if (workerPoolId.value === null) {
        workerPoolId.value = defaultPool.id;
      }
    }
  }
}

async function loadGateways() {
  const { data, error } = await fetchGetGatewayList({ current: 1, size: 100 });
  if (!error && data) {
    gateways.value = data.records;
  }
}

/** 重置：恢复默认池、清空网关 */
function resetSelection() {
  gatewayId.value = null;
  workerPoolId.value = defaultWorkerPoolId.value;
}

loadWorkerPools();
loadGateways();

defineExpose({ resetSelection });
</script>

<template>
  <div class="w-full flex flex-col gap-8px">
    <ElSelect v-model="workerPoolId" placeholder="请选择执行资源" class="w-3/4">
      <ElOption
        v-for="pool in workerPools"
        :key="pool.id"
        :label="`${pool.name}${pool.isDefault ? '（默认）' : ''}`"
        :value="pool.id"
      />
    </ElSelect>
    <ElSelect v-model="gatewayId" clearable placeholder="连接网关（不选则直连）" class="w-3/4">
      <ElOption
        v-for="gateway in gateways"
        :key="gateway.id"
        :label="`${gateway.name}（${gateway.address}）`"
        :value="gateway.id"
      />
    </ElSelect>
  </div>
</template>
