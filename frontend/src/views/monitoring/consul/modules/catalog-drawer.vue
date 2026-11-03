<script setup lang="ts">
import { computed, onUnmounted, ref, shallowRef, watch } from 'vue';
import type { CatalogInstance, ConsulConnection } from '@/service/api/monitoring';
import { getCatalogInstances, getCatalogServices, getConsulDatacenters } from '@/service/api/monitoring';

defineOptions({ name: 'ConsulCatalogDrawer' });

interface Props {
  visible: boolean;
  connection?: ConsulConnection;
}
const props = defineProps<Props>();
const emit = defineEmits<{ 'update:visible': [value: boolean] }>();

const open = computed({
  get: () => props.visible,
  set: value => emit('update:visible', value)
});
const datacenters = shallowRef<string[]>([]);
const services = shallowRef<{ name: string; tags: string[] }[]>([]);
const instances = shallowRef<CatalogInstance[]>([]);
const datacenter = ref('');
const service = ref('');
const page = ref(1);
const total = ref(0);
const loading = ref(false);
const servicesLoading = ref(false);
const errorMessage = ref('');
const details = ref('');
const detailsVisible = ref(false);
let sequence = 0;
let listSequence = 0;

async function loadInstances() {
  const connection = props.connection;
  if (!connection || !service.value) return;
  sequence += 1;
  const requestId = sequence;
  instances.value = [];
  total.value = 0;
  loading.value = true;
  errorMessage.value = '';
  try {
    const { data, error } = await getCatalogInstances(connection.id, {
      datacenter: datacenter.value,
      service: service.value,
      page: page.value
    });
    if (requestId !== sequence || !props.visible) return;
    if (error) errorMessage.value = 'Catalog 实例读取失败，请检查连接和 Catalog / Health 读取权限。';
    else if (data) {
      instances.value = data.list;
      total.value = data.total;
    }
  } finally {
    if (requestId === sequence) loading.value = false;
  }
}
async function loadServices() {
  const connection = props.connection;
  if (!connection) return;
  listSequence += 1;
  sequence += 1;
  const requestId = listSequence;
  instances.value = [];
  services.value = [];
  total.value = 0;
  service.value = '';
  page.value = 1;
  errorMessage.value = '';
  servicesLoading.value = true;
  loading.value = false;
  try {
    const { data, error } = await getCatalogServices(connection.id, datacenter.value);
    if (requestId !== listSequence || !props.visible) return;
    if (error) errorMessage.value = 'Catalog 读取失败，请检查权限后重试。';
    else if (data) services.value = data;
  } finally {
    if (requestId === listSequence) servicesLoading.value = false;
  }
}
async function init() {
  listSequence += 1;
  sequence += 1;
  const requestId = listSequence;
  datacenters.value = [];
  instances.value = [];
  services.value = [];
  total.value = 0;
  service.value = '';
  errorMessage.value = '';
  datacenter.value = props.connection?.datacenter || '';
  if (!props.connection) return;
  servicesLoading.value = true;
  const { data, error } = await getConsulDatacenters(props.connection.id);
  if (requestId !== listSequence || !props.visible) return;
  if (error) {
    servicesLoading.value = false;
    errorMessage.value = 'Datacenter 读取失败，请检查权限后重新打开。';
    return;
  }
  datacenters.value = data || [];
  await loadServices();
}
async function changeService() {
  page.value = 1;
  await loadInstances();
}
function healthText(value: string) {
  return (
    (
      {
        passing: '正常',
        warning: '警告',
        critical: '异常',
        unknown: '无检查结果'
      } as Record<string, string>
    )[value] || '未知'
  );
}
function showDetails(row: CatalogInstance) {
  details.value = JSON.stringify({ tags: row.tags, meta: row.meta }, null, 2);
  detailsVisible.value = true;
}
function invalidate() {
  sequence += 1;
  listSequence += 1;
}

watch(
  () => props.visible,
  value => {
    if (value) init();
    else invalidate();
  }
);
onUnmounted(invalidate);
</script>

<template>
  <ElDrawer v-model="open" :title="`Catalog · ${connection?.name || ''}`" size="85%">
    <div class="flex-col gap-16px">
      <p class="text-12px text-[var(--el-text-color-secondary)]">
        Catalog 只读浏览（跨 Node）；Catalog 中的 Node 不是当前 Agent 的写入地址。
      </p>
      <ElForm inline label-width="80px" @submit.prevent="loadInstances">
        <ElFormItem label="Datacenter">
          <ElSelect v-model="datacenter" class="w-200px" @change="loadServices">
            <ElOption label="连接默认" value="" />
            <ElOption v-for="dc in datacenters" :key="dc" :value="dc" :label="dc" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="Services">
          <ElSelect
            v-model="service"
            class="w-260px"
            filterable
            :loading="servicesLoading"
            placeholder="请选择服务"
            @change="changeService"
          >
            <ElOption v-for="item in services" :key="item.name" :value="item.name" :label="item.name" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem>
          <ElButton :disabled="!service" :loading="loading" @click="loadInstances">刷新实例</ElButton>
        </ElFormItem>
      </ElForm>
      <ElAlert v-if="errorMessage" :title="errorMessage" type="error" :closable="false" />
      <ElTable v-loading="loading" :data="instances" border>
        <ElTableColumn prop="node" label="Node" min-width="150" align="center" show-overflow-tooltip />
        <ElTableColumn prop="id" label="Instance ID" min-width="190" align="center" show-overflow-tooltip />
        <ElTableColumn prop="address" label="地址" min-width="150" align="center" show-overflow-tooltip />
        <ElTableColumn prop="port" label="端口" width="90" align="center" />
        <ElTableColumn label="Health" width="130" align="center">
          <template #default="{ row }">{{ healthText(row.health) }}</template>
        </ElTableColumn>
        <ElTableColumn label="操作" width="120" align="center">
          <template #default="{ row }">
            <ElButton link type="primary" @click="showDetails(row)">标签与 Meta</ElButton>
          </template>
        </ElTableColumn>
        <template #empty><ElEmpty :description="service ? '暂无实例' : '请选择 Services 查看实例'" /></template>
      </ElTable>
      <ElPagination
        v-model:current-page="page"
        class="justify-end"
        :page-size="20"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="loadInstances"
      />
    </div>
    <ElDialog v-model="detailsVisible" title="标签与 Meta" width="640px">
      <ElInput :model-value="details" type="textarea" :rows="15" readonly />
    </ElDialog>
  </ElDrawer>
</template>
