<script setup lang="ts">
import { computed, reactive, shallowRef, watch } from 'vue';
import { fetchGetCommandList } from '@/service/api/automation';

defineOptions({ name: 'ScriptSelectModal' });

interface Props {
  visible: boolean;
  /** 当前已选脚本，打开弹窗时回显 */
  selected?: Api.Automation.CommandRecord | null;
}

const props = withDefaults(defineProps<Props>(), { selected: null });

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void;
  (e: 'confirm', command: Api.Automation.CommandRecord): void;
}>();

/** ============ 展示映射 ============ */

const riskLevelMeta: Record<string, { label: string; type: 'success' | 'warning' | 'danger' }> = {
  low: { label: '低风险', type: 'success' },
  medium: { label: '中风险', type: 'warning' },
  high: { label: '高风险', type: 'danger' }
};

function getRiskMeta(level: string) {
  return riskLevelMeta[level] ?? { label: level || '-', type: 'warning' as const };
}

function formatDay(value: string | null) {
  return value ? value.slice(0, 10) : '-';
}

/** ============ 查询参数（分类树与脚本列表共用） ============ */

const searchParams = reactive({
  current: 1,
  size: 10,
  search: '',
  category: ''
});

/** ============ 左侧分类树（category 为自由文本，从已发布脚本聚合） ============ */

const categories = shallowRef<string[]>([]);

const treeData = computed(() => [
  { id: '', label: '全部分类' },
  ...categories.value.map(item => ({ id: item, label: item }))
]);

async function loadCategories() {
  const { data, error } = await fetchGetCommandList({
    current: 1,
    size: 500,
    status: 'published',
    resourceKind: 'script'
  });
  if (!error && data) {
    categories.value = [...new Set(data.records.map(item => item.category).filter(Boolean))];
  }
}

function onTreeNodeClick(data: { id: string }) {
  searchParams.category = data.id;
  searchParams.current = 1;
  loadScripts();
}

/** ============ 右侧脚本列表（已发布脚本，后端分页） ============ */

const total = shallowRef(0);
const scripts = shallowRef<Api.Automation.CommandRecord[]>([]);
const listLoading = shallowRef(false);

async function loadScripts() {
  listLoading.value = true;
  try {
    const { data, error } = await fetchGetCommandList({
      current: searchParams.current,
      size: searchParams.size,
      search: searchParams.search || undefined,
      category: searchParams.category || undefined,
      status: 'published',
      resourceKind: 'script'
    });
    if (!error && data) {
      scripts.value = data.records;
      total.value = data.total;
    }
  } finally {
    listLoading.value = false;
  }
}

function onSearch() {
  searchParams.current = 1;
  loadScripts();
}

function onPageChange(current: number) {
  searchParams.current = current;
  loadScripts();
}

function onSizeChange(size: number) {
  searchParams.size = size;
  searchParams.current = 1;
  loadScripts();
}

/** ============ 单选与确认 ============ */

const innerSelected = shallowRef<Api.Automation.CommandRecord | null>(null);

function handleRowClick(row: Api.Automation.CommandRecord) {
  innerSelected.value = row;
}

function handleConfirm() {
  if (!innerSelected.value) return;
  emit('confirm', innerSelected.value);
  emit('update:visible', false);
}

function handleClose() {
  emit('update:visible', false);
}

watch(
  () => props.visible,
  visible => {
    if (!visible) return;
    innerSelected.value = props.selected;
    searchParams.current = 1;
    searchParams.search = '';
    searchParams.category = '';
    loadCategories();
    loadScripts();
  }
);
</script>

<template>
  <ElDialog
    :model-value="visible"
    title="脚本库选择"
    width="780px"
    :close-on-click-modal="false"
    append-to-body
    @update:model-value="handleClose"
  >
    <div class="flex gap-12px">
      <!-- 左：分类树 -->
      <div class="w-180px shrink-0 border border-gray-200 rounded-4px p-8px">
        <div class="mb-4px font-bold">脚本分类</div>
        <ElTree
          :data="treeData"
          node-key="id"
          :current-node-key="searchParams.category || undefined"
          :expand-on-click-node="false"
          :props="{ label: 'label', children: 'children' }"
          :highlight-current="true"
          class="max-h-380px overflow-auto"
          @node-click="onTreeNodeClick"
        />
      </div>
      <!-- 右：脚本表格 -->
      <div class="min-w-0 flex-1">
        <div class="mb-8px flex items-center gap-8px">
          <ElInput
            v-model="searchParams.search"
            clearable
            placeholder="检索名称 / 编码"
            class="w-200px"
            @keyup.enter="onSearch"
            @clear="onSearch"
          />
          <ElButton type="primary" plain @click="onSearch">查询</ElButton>
        </div>
        <ElTable
          v-loading="listLoading"
          :data="scripts"
          border
          height="380px"
          row-key="id"
          highlight-current-row
          @row-click="handleRowClick"
        >
          <ElTableColumn prop="name" label="名称" min-width="140" align="center" show-overflow-tooltip />
          <ElTableColumn prop="code" label="编码" min-width="120" align="center" show-overflow-tooltip />
          <ElTableColumn label="分类" width="100" align="center" show-overflow-tooltip>
            <template #default="{ row }">{{ row.category || '-' }}</template>
          </ElTableColumn>
          <ElTableColumn label="风险" width="88" align="center">
            <template #default="{ row }">
              <ElTag size="small" :type="getRiskMeta(row.riskLevel).type">
                {{ getRiskMeta(row.riskLevel).label }}
              </ElTag>
            </template>
          </ElTableColumn>
          <ElTableColumn label="发布版本" width="88" align="center">
            <template #default="{ row }">{{ row.publishedVersion ? `v${row.publishedVersion}` : '-' }}</template>
          </ElTableColumn>
          <ElTableColumn label="更新时间" width="104" align="center">
            <template #default="{ row }">{{ formatDay(row.updatedAt) }}</template>
          </ElTableColumn>
        </ElTable>
        <div class="mt-8px flex justify-end">
          <ElPagination
            layout="total, prev, pager, next, sizes"
            :total="total"
            :current-page="searchParams.current"
            :page-size="searchParams.size"
            :page-sizes="[10, 20, 50, 100]"
            @current-change="onPageChange"
            @size-change="onSizeChange"
          />
        </div>
      </div>
    </div>
    <template #footer>
      <div class="flex items-center justify-between">
        <div class="min-w-0 flex-1 text-left">
          <template v-if="innerSelected">
            <span class="font-bold">已选：</span>
            <span>{{ innerSelected.name }}</span>
            <ElTag v-if="innerSelected.category" size="small" class="ml-8px">{{ innerSelected.category }}</ElTag>
            <span class="ml-8px text-12px text-gray-500">{{ innerSelected.code }}</span>
          </template>
          <span v-else class="text-gray-500">点击表格行选择脚本（仅显示已发布脚本）</span>
        </div>
        <div class="shrink-0">
          <ElButton @click="handleClose">取消</ElButton>
          <ElButton type="primary" :disabled="!innerSelected" @click="handleConfirm">确定</ElButton>
        </div>
      </div>
    </template>
  </ElDialog>
</template>
