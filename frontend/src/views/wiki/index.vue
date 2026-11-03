<script setup lang="ts">
import { ref, shallowRef } from 'vue';
import WikiEditor from './modules/wiki-editor.vue';
import WikiTree from './modules/wiki-tree.vue';

defineOptions({ name: 'WikiDocs' });

const treeRef = ref<InstanceType<typeof WikiTree>>();
const editorRef = ref<InstanceType<typeof WikiEditor>>();

/** 当前打开的节点（null 表示未选中） */
const activeNode = shallowRef<Api.Wiki.PageNode | null>(null);

/** 切换节点前拦截未保存的修改 */
async function handleTreeSelect(node: Api.Wiki.PageNode | null) {
  const previous = activeNode.value;
  if ((node?.id ?? null) === (previous?.id ?? null)) return;

  if (previous && editorRef.value?.isDirty()) {
    try {
      await ElMessageBox.confirm('当前文档有未保存的修改，切换后将丢失，是否继续？', '未保存提示', { type: 'warning' });
    } catch {
      treeRef.value?.selectNode(previous);
      return;
    }
  }

  activeNode.value = node;
}

/** 树结构变化（重命名 / 删除 / 移动）后同步详情 */
async function handleTreeChanged() {
  if (!activeNode.value) return;
  await editorRef.value?.reload();
}

/** 保存成功后同步树上的标题 */
function handleSaved() {
  treeRef.value?.refresh();
}
</script>

<template>
  <div class="min-h-500px flex-col-stretch overflow-hidden lt-sm:overflow-auto">
    <div class="min-h-0 flex flex-1 gap-12px lt-sm:flex-col">
      <ElCard class="workspace-card min-h-0 w-300px shrink-0 card-wrapper lt-sm:w-full">
        <WikiTree ref="treeRef" class="min-h-0 flex-1" @select="handleTreeSelect" @changed="handleTreeChanged" />
      </ElCard>

      <ElCard class="workspace-card min-h-0 min-w-0 flex-1 card-wrapper">
        <WikiEditor ref="editorRef" :node="activeNode" @saved="handleSaved" />
      </ElCard>
    </div>
  </div>
</template>

<style scoped></style>
