<script setup lang="ts">
import { computed, ref, shallowRef, watch } from 'vue';
import { fetchCloudCatalog, fetchCloudConfigurationCatalog } from '@/service/api/provisioning';
import type { CloudCatalogItem, CloudCatalogQuery } from '@/service/api/provisioning';
import { formatLocalDateTime } from '@/utils/common';
import { acceptResponse, resourceDescription } from './shared';

defineOptions({ name: 'CloudResourcePicker' });
const props = withDefaults(
  defineProps<{ query?: CloudCatalogQuery; configuration?: boolean; multiple?: boolean; disabled?: boolean }>(),
  { query: undefined, configuration: false, multiple: false, disabled: false }
);
const model = defineModel<string | string[]>({ default: '' });
const emit = defineEmits<{ selected: [items: CloudCatalogItem[]] }>();
const items = shallowRef<CloudCatalogItem[]>([]);
const loading = ref(false);
const failure = ref(false);
const observedAt = ref('');
const cursor = ref<string | null>(null);
const sequence = ref(0);
const search = ref('');
const warnings = shallowRef<string[]>([]);
const ready = computed(() =>
  Boolean(props.query?.versionId && props.query.region && (props.query.credentialId || props.query.sourceId))
);

async function load(append = false, refresh = false) {
  if (!props.query || !ready.value || props.disabled) return;
  const current = sequence.value + 1;
  sequence.value = current;
  loading.value = true;
  failure.value = false;
  try {
    const fetcher = props.configuration ? fetchCloudConfigurationCatalog : fetchCloudCatalog;
    const { data, error } = await fetcher({
      ...props.query,
      refresh,
      search: search.value || undefined,
      cursor: append ? (cursor.value ?? undefined) : undefined
    });
    if (!acceptResponse(current, sequence.value)) return;
    if (error || !data) {
      failure.value = true;
      return;
    }
    items.value = append
      ? [...new Map([...items.value, ...data.items].map(item => [item.id, item])).values()]
      : data.items;
    cursor.value = data.nextCursor;
    observedAt.value = data.observedAt;
    warnings.value = data.warnings;
  } finally {
    if (acceptResponse(current, sequence.value)) loading.value = false;
  }
}

function reload() {
  load(false, true);
}
function more() {
  load(true);
}
function searchRemote(value: string) {
  search.value = value;
  load();
}
function select(value: string | string[]) {
  const ids = Array.isArray(value) ? value : [value];
  emit(
    'selected',
    items.value.filter(item => ids.includes(item.id))
  );
}

watch(
  () => JSON.stringify(props.query),
  () => {
    sequence.value += 1;
    items.value = [];
    model.value = props.multiple ? [] : '';
    cursor.value = null;
    observedAt.value = '';
    search.value = '';
    loading.value = false;
    load();
  },
  { immediate: true }
);
</script>

<template>
  <div class="w-full flex-col gap-8px">
    <div class="flex items-center gap-8px">
      <ElSelect
        v-model="model"
        class="min-w-0 flex-1"
        :multiple="multiple"
        :disabled="disabled || !ready"
        filterable
        remote
        clearable
        :remote-method="searchRemote"
        :loading="loading"
        placeholder="请选择云资源"
        @change="select"
      >
        <ElOption
          v-for="item in items"
          :key="item.id"
          :value="item.id"
          :label="item.name === item.id ? item.id : `${item.name} · ${item.id}`"
          :disabled="item.available === false"
        >
          <div class="flex items-center justify-between gap-16px">
            <span class="truncate">
              {{ item.name }}
              <span class="text-color-secondary ml-8px">{{ resourceDescription(item) }}</span>
            </span>
            <span class="text-color-secondary">{{ item.id }}</span>
          </div>
        </ElOption>
        <template #footer><ElButton v-if="cursor" text :loading="loading" @click="more">加载更多</ElButton></template>
      </ElSelect>
      <ElButton :disabled="disabled || !ready" :loading="loading" @click="reload">重读</ElButton>
    </div>
    <span v-if="failure" class="text-color-secondary">读取失败，请根据错误提示检查账号权限或网络后重试。</span>
    <span v-else-if="!ready" class="text-color-secondary">请先选择模板、云账号及地域。</span>
    <template v-for="item in items" :key="item.id">
      <span v-if="(Array.isArray(model) ? model : [model]).includes(item.id)" class="text-color-secondary">
        {{ resourceDescription(item) || '资源详情未返回' }}
      </span>
    </template>
    <span v-if="observedAt" class="text-color-secondary">
      读取于 {{ formatLocalDateTime(observedAt) }}
      <template v-if="cursor">· 还有更多资源</template>
    </span>
    <span v-for="warning in warnings" :key="warning" class="text-color-secondary">{{ warning }}</span>
  </div>
</template>
