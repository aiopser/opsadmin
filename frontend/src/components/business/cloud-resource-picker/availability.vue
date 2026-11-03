<script setup lang="ts">
import { ref, shallowRef, watch } from 'vue';
import { fetchCloudCatalog } from '@/service/api/provisioning';
import type { CloudCatalogQuery } from '@/service/api/provisioning';
import { formatLocalDateTime } from '@/utils/common';
import { acceptResponse } from './shared';

defineOptions({ name: 'CloudResourceAvailability' });
const props = withDefaults(defineProps<{ query?: CloudCatalogQuery }>(), { query: undefined });
const sequence = ref(0);
const loading = ref(false);
const result = shallowRef<{ available: boolean | null; observedAt: string; reason: string }>();

async function load() {
  const current = sequence.value + 1;
  sequence.value = current;
  result.value = undefined;
  loading.value = false;
  if (!props.query?.instanceType || !props.query.zone) return;
  const query = props.query;
  loading.value = true;
  try {
    const { data, error } = await fetchCloudCatalog({ ...query, refresh: true });
    if (!acceptResponse(current, sequence.value) || error || !data) return;
    const match = data.items.find(item => item.id === query.instanceType && item.attributes.zone === query.zone);
    result.value = {
      available: match?.available ?? null,
      reason: match?.unavailableReason ?? '',
      observedAt: data.observedAt
    };
  } finally {
    if (acceptResponse(current, sequence.value)) loading.value = false;
  }
}

watch(() => JSON.stringify(props.query), load, { immediate: true });
</script>

<template>
  <div class="flex-col gap-8px">
    <div class="flex flex-wrap items-center gap-8px">
      <span v-if="loading">正在查询可用性…</span>
      <ElTag
        v-else
        :type="result?.available === true ? 'success' : result?.available === false ? 'warning' : 'info'"
        size="small"
      >
        {{ result?.available === true ? '当前可用' : result?.available === false ? '当前不可用' : '可用性未知' }}
      </ElTag>
      <ElButton text :disabled="!query?.instanceType || !query.zone" :loading="loading" @click="load">重读</ElButton>
    </div>
    <span class="text-color-secondary">{{ result?.reason || '未预留库存；精确可用台数未知，执行前会再次校验。' }}</span>
    <span v-if="result" class="text-color-secondary">读取于 {{ formatLocalDateTime(result.observedAt) }}</span>
  </div>
</template>
