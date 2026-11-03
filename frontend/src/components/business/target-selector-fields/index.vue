<script setup lang="ts">
import { onMounted, shallowRef } from 'vue';
import { fetchGetHostGroupList, fetchGetTagList } from '@/service/api';

defineOptions({ name: 'TargetSelectorFields' });
const groupIds = defineModel<number[]>('groupIds', { required: true });
const tagIds = defineModel<number[]>('tagIds', { required: true });
const groups = shallowRef<Api.Cmdb.HostGroupRecord[]>([]);
const tags = shallowRef<Api.Cmdb.HostTagRecord[]>([]);

async function loadGroups() {
  let records: Api.Cmdb.HostGroupRecord[] = [];
  for (let current = 1; ; current += 1) {
    // 顺序分页依赖上一页的总数，避免遗漏或重复请求。
    // eslint-disable-next-line no-await-in-loop
    const { data, error } = await fetchGetHostGroupList({ current, size: 100, isActive: true });
    if (error || !data) return;
    records = [...records, ...data.records];
    if (!data.records.length || records.length >= data.total) break;
  }
  groups.value = records;
}

async function loadTags() {
  let records: Api.Cmdb.HostTagRecord[] = [];
  for (let current = 1; ; current += 1) {
    // 顺序分页依赖上一页的总数，避免遗漏或重复请求。
    // eslint-disable-next-line no-await-in-loop
    const { data, error } = await fetchGetTagList({ current, size: 100 });
    if (error || !data) return;
    records = [...records, ...data.records];
    if (!data.records.length || records.length >= data.total) break;
  }
  tags.value = records;
}

onMounted(() => Promise.all([loadGroups(), loadTags()]));
</script>

<template>
  <div>
    <ElFormItem label="主机分组">
      <ElSelect v-model="groupIds" multiple filterable class="w-full" placeholder="选择资产分组">
        <ElOption v-for="group in groups" :key="group.id" :value="group.id" :label="group.name" />
      </ElSelect>
    </ElFormItem>
    <ElFormItem label="主机标签">
      <ElSelect v-model="tagIds" multiple filterable class="w-full" placeholder="选择资产标签">
        <ElOption v-for="tag in tags" :key="tag.id" :value="tag.id" :label="tag.label" />
      </ElSelect>
      <p class="mt-4px w-full text-12px text-gray-500 leading-5">
        主机、分组和标签取并集并去重；每次新运行解析当前资产并冻结目标，重跑沿用原运行目标。
      </p>
    </ElFormItem>
  </div>
</template>
