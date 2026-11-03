<script setup lang="ts">
import { computed, nextTick, onUnmounted, ref, shallowRef, watch } from 'vue';
import Vditor from 'vditor';
import 'vditor/dist/index.css';
import { fetchGetWikiPage, fetchUpdateWikiPage, fetchUploadWikiFile } from '@/service/api';
import { useThemeStore } from '@/store/modules/theme';
import { useAuth } from '@/hooks/business/auth';

defineOptions({ name: 'WikiEditor' });

interface Props {
  node: Api.Wiki.PageNode | null;
}
const props = defineProps<Props>();

interface Emits {
  (e: 'saved'): void;
}

const emit = defineEmits<Emits>();

const { hasAuth } = useAuth();
const theme = useThemeStore();

const canUpdate = computed(() => hasAuth('wiki.page:update'));

/** ============ 文档状态 ============ */

const loading = ref(false);
const saving = ref(false);
/** 正文或标题有未保存的修改 */
const dirty = ref(false);
/** 标题单独用 ref 承载，避免依赖 shallowRef 内部字段的深层响应式 */
const title = ref('');
const detail = shallowRef<Api.Wiki.PageDetail | null>(null);
const editorDom = ref<HTMLElement>();
const vditor = shallowRef<Vditor>();

const updatedLabel = computed(() => {
  const time = detail.value?.updated_at;
  if (!time) return '';
  const author = detail.value?.updated_by ? ` · ${detail.value.updated_by}` : '';
  return `最后更新：${time.replace('T', ' ').slice(0, 19)}${author}`;
});

/** ============ vditor 编辑器 ============ */

function renderVditor(content: string) {
  if (!editorDom.value) return;
  vditor.value?.destroy();
  vditor.value = new Vditor(editorDom.value, {
    value: content,
    mode: 'ir',
    minHeight: 420,
    theme: theme.darkMode ? 'dark' : 'classic',
    icon: 'material',
    cache: { enable: false },
    input: handleEditorInput,
    upload: { accept: 'image/*', handler: handleUploadFiles }
  });
}

function handleEditorInput() {
  dirty.value = true;
}

function handleTitleInput() {
  dirty.value = true;
}

/** 返回 null 表示上传由业务自行处理（避免 vditor 默认上传逻辑覆盖鉴权头） */
function handleUploadFiles(files: File[]) {
  files.forEach(file => {
    uploadImage(file);
  });
  return null;
}

async function uploadImage(file: File) {
  const { data, error } = await fetchUploadWikiFile(file);
  if (error || !data) {
    window.$message?.error('图片上传失败');
    return;
  }
  vditor.value?.insertValue(`![${data.name}](${data.url})`);
  dirty.value = true;
}

/** ============ 数据加载与保存 ============ */

async function loadDetail(id: number) {
  loading.value = true;
  const { data, error } = await fetchGetWikiPage(id);
  loading.value = false;
  if (error || !data) return;

  detail.value = data;
  title.value = data.title ?? '';
  dirty.value = false;
  await nextTick();
  renderVditor(data.content ?? '');
}

async function save() {
  const current = detail.value;
  if (!current) return;

  saving.value = true;
  const { error } = await fetchUpdateWikiPage(current.id, {
    title: title.value,
    content: vditor.value?.getValue() ?? current.content
  });
  saving.value = false;
  if (error) return;

  dirty.value = false;
  window.$notification?.success('已保存');
  emit('saved');
}

/** ============ watch / 生命周期 ============ */

const stopThemeHandle = watch(
  () => theme.darkMode,
  value => {
    vditor.value?.setTheme(value ? 'dark' : 'classic');
  }
);

const stopNodeHandle = watch(
  () => props.node?.id,
  async id => {
    if (id) await loadDetail(id);
  }
);

onUnmounted(() => {
  stopThemeHandle();
  stopNodeHandle();
  vditor.value?.destroy();
});

defineExpose({
  isDirty: () => dirty.value,
  /** 节点被重命名等场景下同步详情（有未保存修改时跳过，避免覆盖编辑内容） */
  reload: async () => {
    if (props.node && !dirty.value) await loadDetail(props.node.id);
  }
});
</script>

<template>
  <div class="flex-col-stretch gap-8px overflow-hidden">
    <ElEmpty v-if="!node" description="请选择左侧目录或文档">
      <span class="text-12px text-[var(--el-text-color-regular)]">或在左侧新建一份文档</span>
    </ElEmpty>

    <div v-else-if="!detail" v-loading="loading" class="min-h-300px" />

    <template v-else>
      <div class="flex items-center gap-8px">
        <ElInput v-model="title" placeholder="文档标题" :disabled="!canUpdate" @input="handleTitleInput" />
        <ElTooltip v-if="canUpdate" content="保存当前文档" placement="top">
          <ElButton type="primary" :disabled="!dirty" :loading="saving" @click="save">保存</ElButton>
        </ElTooltip>
        <ElTag v-else type="info" size="small">只读</ElTag>
      </div>

      <p v-if="updatedLabel" class="text-12px text-[var(--el-text-color-regular)]">{{ updatedLabel }}</p>

      <div v-loading="loading" class="min-h-0 flex-1 overflow-auto">
        <div ref="editorDom"></div>
      </div>
    </template>
  </div>
</template>

<style scoped></style>
