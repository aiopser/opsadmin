<script setup lang="ts">
import { ref } from 'vue';
import { useFormItem } from 'element-plus';
import HostSelectModal from '@/components/business/host-select-modal/index.vue';

defineOptions({ name: 'HostSelectField' });

interface Props {
  /** 主机选择弹窗的 OS 预过滤（linux/windows） */
  expectedOsFamily: string;
}

defineProps<Props>();

const hosts = defineModel<Api.Cmdb.HostRecord[]>('hosts', { required: true });

const modalVisible = ref(false);

// 自定义组件无原生 change 事件冒泡，hosts 的 trigger:'change' 校验不会自动触发，
// 用户确认选择/移除主机后需手动触发，否则已显示的"请选择目标主机"错误不会消除
const { formItem } = useFormItem();

function onHostsConfirm(selected: Api.Cmdb.HostRecord[]) {
  hosts.value = selected;
  formItem?.validate('change');
}

function removeHost(id: number) {
  hosts.value = hosts.value.filter(host => host.id !== id);
  formItem?.validate('change');
}

function clearAll() {
  hosts.value = [];
}

defineExpose({ clear: clearAll });
</script>

<template>
  <div class="w-3/4">
    <div class="flex items-center gap-8px">
      <ElButton type="primary" plain @click="modalVisible = true">选择目标主机</ElButton>
      <span class="text-12px text-gray-500">已选 {{ hosts.length }} 台</span>
      <ElButton v-if="hosts.length" link type="danger" size="small" @click="clearAll">清空</ElButton>
    </div>
    <ElTable v-if="hosts.length" :data="hosts" size="small" max-height="240" border class="mt-8px">
      <ElTableColumn prop="hostname" label="主机名称" min-width="100" align="center" show-overflow-tooltip />
      <ElTableColumn prop="internalIp" label="内网IP" min-width="100" align="center" />
      <ElTableColumn prop="osFamily" label="系统" width="70" align="center" />
      <ElTableColumn label="操作" width="60" align="center">
        <template #default="{ row }">
          <ElButton link type="danger" size="small" @click="removeHost(row.id)">移除</ElButton>
        </template>
      </ElTableColumn>
    </ElTable>

    <HostSelectModal
      v-model:visible="modalVisible"
      :selected-hosts="hosts"
      :default-os-family="expectedOsFamily"
      @confirm="onHostsConfirm"
    />
  </div>
</template>
