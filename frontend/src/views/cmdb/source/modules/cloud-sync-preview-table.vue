<script setup lang="ts">
import { computed } from 'vue';
import { actionLabel, canSyncRow, countIncompleteSpecs, formatMemory, formatValue } from './cloud-preview';
import type { CloudPreviewRow } from './cloud-preview';

defineOptions({ name: 'CloudSyncPreviewTable' });

interface Props {
  rows: CloudPreviewRow[];
  selectedIds: string[];
  busy?: boolean;
}
const props = defineProps<Props>();
const emit = defineEmits<{ (event: 'toggle', sourceId: string): void }>();

const incompleteCount = computed(() => countIncompleteSpecs(props.rows));

function toggle(row: CloudPreviewRow) {
  emit('toggle', row.sourceId);
}

function actionType(action: CloudPreviewRow['action']): UI.ThemeColor {
  if (action === 'create') return 'success';
  return action === 'invalid' ? 'warning' : 'info';
}
</script>

<template>
  <div class="flex flex-col gap-12px">
    <ElAlert
      v-if="incompleteCount"
      type="warning"
      show-icon
      :closable="false"
      :title="`${incompleteCount} 台主机的规格或地域未完整返回`"
      description="公有云账号请确认后端 API 和 Celery Worker 均已更新并重启，再重新读取。缺失字段不会清空已有资产信息；私有云还需核对当前平台支持的采集字段。"
    />
    <ElTable :data="rows" row-key="index" border max-height="360" class="w-full">
      <ElTableColumn type="expand" width="40" align="center">
        <template #default="{ row }">
          <div class="p-16px">
            <p v-if="row.reason" class="text-regular mb-8px text-sm">
              {{ row.reason }}
            </p>
            <ElTable v-if="row.changes?.length" :data="row.changes" border size="small" class="w-full">
              <ElTableColumn prop="label" label="变更字段" width="160" align="center" />
              <ElTableColumn label="当前值" min-width="160" align="center" show-overflow-tooltip>
                <template #default="{ row: change }">{{ formatValue(change.before) }}</template>
              </ElTableColumn>
              <ElTableColumn label="同步后" min-width="160" align="center" show-overflow-tooltip>
                <template #default="{ row: change }">{{ formatValue(change.after) }}</template>
              </ElTableColumn>
            </ElTable>
            <p v-else-if="row.action === 'create'" class="text-regular text-sm">
              将新增主机；连接凭据、分组和标签可在导入后配置。
            </p>
            <p v-else-if="!row.reason" class="text-regular text-sm">此记录没有可展示的字段变化。</p>
          </div>
        </template>
      </ElTableColumn>
      <ElTableColumn label="选择" width="60" align="center">
        <template #default="{ row }">
          <ElCheckbox
            :model-value="selectedIds.includes(row.sourceId)"
            :disabled="!canSyncRow(row) || busy"
            :aria-label="`选择主机 ${row.hostname}`"
            @change="toggle(row)"
          />
        </template>
      </ElTableColumn>
      <ElTableColumn label="主机 / 实例 ID" min-width="170" align="center">
        <template #default="{ row }">
          <div class="min-w-0">
            <div class="truncate" :title="row.hostname">
              {{ row.hostname || '—' }}
            </div>
            <div class="text-regular truncate text-xs" :title="row.sourceId">
              {{ row.sourceId || '—' }}
            </div>
          </div>
        </template>
      </ElTableColumn>
      <ElTableColumn prop="internalIp" label="内网 IP" min-width="135" align="center" />
      <ElTableColumn label="配置" min-width="200" align="center">
        <template #default="{ row }">
          <div class="text-sm tabular-nums">
            <div>
              {{ row.specs?.cpu_cores === undefined ? '—' : `${row.specs.cpu_cores} 核` }}
              /
              {{ formatMemory(row.specs?.memory_mb) }}
            </div>
            <div class="text-regular text-xs">
              系统盘 {{ row.specs?.system_disk_gb ?? '—' }} GiB · 数据盘 {{ row.specs?.data_disk_gb ?? '—' }} GiB
            </div>
          </div>
        </template>
      </ElTableColumn>
      <ElTableColumn label="地域" min-width="120" align="center" show-overflow-tooltip>
        <template #default="{ row }">{{ row.specs?.region || '—' }}</template>
      </ElTableColumn>
      <ElTableColumn label="处理" width="90" align="center">
        <template #default="{ row }">
          <ElTag :type="actionType(row.action)" size="small">{{ actionLabel(row.action) }}</ElTag>
        </template>
      </ElTableColumn>
    </ElTable>
  </div>
</template>
