<script setup lang="ts">
import { computed, ref, shallowRef, watch } from 'vue';
import { fetchPreviewCloudAssets, fetchSyncCloudAssets } from '@/service/api';
import CloudSyncPreviewTable from './cloud-sync-preview-table.vue';
import { canSyncRow } from './cloud-preview';

defineOptions({ name: 'CmdbAccountSyncDialog' });

interface Emits {
  (e: 'synced', sourceId: number): void;
}

const emit = defineEmits<Emits>();

const visible = ref(false);
const account = ref<Api.Cmdb.AssetSourceRecord | null>(null);
const previewing = ref(false);
const syncing = ref(false);
const preview = shallowRef<Api.Cmdb.AssetSyncPreview | null>(null);
const selectedSourceIds = ref<string[]>([]);
const selectedCount = computed(() => selectedSourceIds.value.length);
const selectedImpact = computed(() => {
  const rows = preview.value?.rows.filter(row => selectedSourceIds.value.includes(row.sourceId)) ?? [];
  return {
    create: rows.filter(row => row.action === 'create').length,
    update: rows.filter(row => row.action === 'update').length
  };
});
let previewController: AbortController | null = null;

function cancelPreviewRequest() {
  previewController?.abort();
  previewController = null;
}

function open(row: Api.Cmdb.AssetSourceRecord) {
  cancelPreviewRequest();
  account.value = row;
  preview.value = null;
  selectedSourceIds.value = [];
  previewing.value = false;
  syncing.value = false;
  visible.value = true;
}

async function handlePreview() {
  if (!account.value) return;

  cancelPreviewRequest();
  const controller = new AbortController();
  previewController = controller;
  preview.value = null;
  selectedSourceIds.value = [];
  previewing.value = true;
  const { data, error } = await fetchPreviewCloudAssets(account.value.id, controller.signal);
  if (previewController !== controller) return;
  previewController = null;
  previewing.value = false;
  if (!error && data) {
    preview.value = data;
    selectedSourceIds.value = data.rows.filter(canSyncRow).map(row => row.sourceId);
  }
}

function toggleSelection(sourceId: string) {
  selectedSourceIds.value = selectedSourceIds.value.includes(sourceId)
    ? selectedSourceIds.value.filter(id => id !== sourceId)
    : [...selectedSourceIds.value, sourceId];
}

function selectAll() {
  selectedSourceIds.value = preview.value?.rows.filter(canSyncRow).map(row => row.sourceId) ?? [];
}

function clearSelection() {
  selectedSourceIds.value = [];
}

async function handleSync() {
  if (!account.value || !preview.value?.confirmationToken || !selectedCount.value) return;

  syncing.value = true;
  const { error, data: record } = await fetchSyncCloudAssets(
    account.value.id,
    preview.value.confirmationToken || '',
    selectedSourceIds.value
  );
  syncing.value = false;

  if (!error) {
    window.$notification?.success(`同步任务已提交，记录 #${record.id}`);
    visible.value = false;
    emit('synced', account.value.id);
  }
}

watch(visible, isVisible => {
  if (!isVisible) cancelPreviewRequest();
});

defineExpose({ open });
</script>

<template>
  <ElDialog
    v-model="visible"
    :title="`同步云主机 · ${account?.name ?? ''}`"
    width="min(960px, calc(100vw - 32px))"
    align-center
    :close-on-click-modal="false"
    :close-on-press-escape="!syncing"
    :show-close="!syncing"
  >
    <div class="flex flex-col gap-16px">
      <p class="text-regular m-0 text-sm leading-6">
        选择本次要同步的云主机。仅同步所选主机，未选中或本次未返回的已有主机不会删除、停用。
      </p>
      <ElSkeleton v-if="previewing" :rows="5" animated />
      <template v-else-if="preview">
        <div
          class="flex flex-wrap items-center gap-x-24px gap-y-8px bg-[var(--el-fill-color-light)] p-12px text-sm tabular-nums"
        >
          <span>读取 {{ preview.total }} 台</span>
          <span>可新增 {{ preview.create }} 台</span>
          <span>可更新 {{ preview.update }} 台</span>
          <span>未变化 {{ preview.unchanged ?? 0 }} 台</span>
          <span>无效 {{ preview.invalid }} 台</span>
        </div>
        <div class="flex flex-wrap items-center justify-between gap-12px text-sm">
          <div class="flex flex-wrap items-center gap-x-12px gap-y-4px">
            <span>待同步主机</span>
            <span class="text-regular">
              已选 {{ selectedCount }} 台：新增 {{ selectedImpact.create }} 台，更新 {{ selectedImpact.update }} 台
            </span>
          </div>
          <div class="flex gap-8px">
            <ElButton size="small" :disabled="syncing" @click="selectAll">全选可同步主机</ElButton>
            <ElButton size="small" :disabled="!selectedCount || syncing" @click="clearSelection">清空选择</ElButton>
          </div>
        </div>
        <CloudSyncPreviewTable
          :rows="preview.rows"
          :selected-ids="selectedSourceIds"
          :busy="syncing"
          @toggle="toggleSelection"
        />
        <p class="text-regular m-0 text-sm">展开主机行可查看字段旧值与同步后的值；未变化的主机无需同步。</p>
      </template>
      <ElEmpty v-else :image-size="64" description="尚未读取云主机">
        <ElButton type="primary" @click="handlePreview">读取云主机</ElButton>
      </ElEmpty>
    </div>
    <template #footer>
      <ElButton :disabled="syncing" @click="visible = false">取消</ElButton>
      <ElButton v-if="preview || previewing" :disabled="syncing" :loading="previewing" @click="handlePreview">
        重新读取
      </ElButton>
      <ElButton
        v-if="preview || previewing"
        type="primary"
        :loading="syncing"
        :disabled="previewing || !preview?.confirmationToken || !selectedCount"
        @click="handleSync"
      >
        确认同步 · {{ selectedCount }} 台
      </ElButton>
    </template>
  </ElDialog>
</template>
