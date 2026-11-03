<script setup lang="ts">
import { computed, onMounted, ref, shallowRef, watch } from 'vue';
import { fetchGetNotificationVariables, fetchPreviewNotificationTemplate } from '@/service/api';

defineOptions({ name: 'NotificationTemplatePreview' });

type TemplateField = 'subjectTemplate' | 'bodyTemplate' | 'receiverTemplate';

interface Props {
  subjectTemplate: string;
  bodyTemplate: string;
  receiverTemplate: string;
  channelType?: string;
  insertable?: boolean;
}

const props = defineProps<Props>();
const emit = defineEmits<{
  insert: [expression: string, field: TemplateField];
  validated: [sample: Api.Automation.NotificationSample | null];
}>();

const scenario = ref<Api.Automation.NotificationScenario>('failure');
const workflowVersionId = ref<number | null>(null);
const versions = shallowRef<Api.Automation.NotificationVariableCatalog['workflowVersions']>([]);
const variables = shallowRef<Api.Automation.NotificationVariable[]>([]);
const sampleText = ref('');
const insertTarget = ref<TemplateField>('bodyTemplate');
const activeTab = ref<'variables' | 'preview'>(props.insertable ? 'variables' : 'preview');
const testVariablesVisible = ref(false);
const sampleEditorVisible = ref(false);
const catalogLoading = ref(false);
const previewLoading = ref(false);
const catalogError = ref('');
const localError = ref('');
const preview = shallowRef<Api.Automation.NotificationPreviewResult | null>(null);
let catalogRevision = 0;
let previewRevision = 0;

const previewErrors = computed(() =>
  Object.entries(preview.value?.errors ?? {}).map(([field, message]) => {
    const labels: Record<string, string> = {
      subjectTemplate: '标题模板',
      bodyTemplate: '内容模板',
      receiverTemplate: '接收人模板'
    };
    return `${labels[field] ?? field}：${message}`;
  })
);
const textOnly = computed(() => ['dingtalk', 'feishu', 'wecom'].includes(props.channelType ?? ''));

function formatExample(value: unknown): string {
  return typeof value === 'string' ? value : JSON.stringify(value);
}

function insertVariable(expression: string) {
  emit('insert', expression, insertTarget.value);
}

function toggleTestVariables() {
  testVariablesVisible.value = !testVariablesVisible.value;
}

function toggleSampleEditor() {
  sampleEditorVisible.value = !sampleEditorVisible.value;
}

function invalidatePreview() {
  previewRevision += 1;
  previewLoading.value = false;
  preview.value = null;
  localError.value = '';
  emit('validated', null);
}

async function loadCatalog() {
  invalidatePreview();
  catalogRevision += 1;
  const revision = catalogRevision;
  catalogLoading.value = true;
  catalogError.value = '';
  variables.value = [];
  const { data, error } = await fetchGetNotificationVariables(scenario.value, workflowVersionId.value);
  if (revision !== catalogRevision) return;
  catalogLoading.value = false;
  if (error || !data) {
    catalogError.value = '变量目录加载失败，请重试';
    return;
  }
  variables.value = data.variables;
  versions.value = data.workflowVersions;
  sampleText.value = JSON.stringify(data.sampleContext, null, 2);
}

function changeScenario() {
  workflowVersionId.value = null;
  loadCatalog();
}

async function renderPreview() {
  invalidatePreview();
  const revision = previewRevision;
  let sampleContext: Record<string, unknown>;
  try {
    const parsed: unknown = JSON.parse(sampleText.value);
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) throw new Error('invalid context');
    sampleContext = Object.fromEntries(Object.entries(parsed));
  } catch {
    localError.value = '测试数据必须是有效的 JSON 对象';
    return;
  }
  const sample: Api.Automation.NotificationSample = {
    scenario: scenario.value,
    workflowVersionId: workflowVersionId.value,
    sampleContext
  };
  previewLoading.value = true;
  const { data, error } = await fetchPreviewNotificationTemplate({
    ...sample,
    subjectTemplate: props.subjectTemplate,
    bodyTemplate: props.bodyTemplate,
    receiverTemplate: props.receiverTemplate
  });
  if (revision !== previewRevision) return;
  previewLoading.value = false;
  if (error || !data) {
    localError.value = '预览请求失败，请重试';
    return;
  }
  preview.value = data;
  if (data.valid) emit('validated', sample);
}

watch(
  [sampleText, () => props.subjectTemplate, () => props.bodyTemplate, () => props.receiverTemplate],
  invalidatePreview
);

onMounted(loadCatalog);
</script>

<template>
  <div class="notification-preview flex flex-col gap-16px text-13px leading-22px">
    <section
      class="flex flex-col gap-8px border border-[var(--el-border-color-lighter)] bg-[var(--el-fill-color-lighter)] px-16px py-12px"
    >
      <div class="flex flex-wrap items-center gap-12px">
        <span class="w-64px shrink-0 text-[var(--el-text-color-regular)]">使用场景</span>
        <ElRadioGroup v-model="scenario" @change="changeScenario">
          <ElRadio value="failure">失败告警</ElRadio>
          <ElRadio value="workflow">流程通知步骤</ElRadio>
          <ElRadio value="asset_sync">资产同步失败</ElRadio>
          <ElRadio value="provisioning">资源申请与交付</ElRadio>
          <ElRadio value="security">漏洞公告订阅</ElRadio>
        </ElRadioGroup>
      </div>
      <div v-if="scenario === 'workflow'" class="flex flex-wrap items-start gap-12px">
        <span class="w-64px shrink-0 text-[var(--el-text-color-regular)] leading-32px">流程版本</span>
        <div class="min-w-200px flex flex-col flex-1 gap-4px">
          <ElSelect
            v-model="workflowVersionId"
            clearable
            filterable
            placeholder="选择已发布流程版本，加载自定义变量"
            @change="loadCatalog"
          >
            <ElOption
              v-for="version in versions"
              :key="version.id"
              :value="version.id"
              :label="`${version.workflowName} · v${version.version}`"
            />
          </ElSelect>
          <p class="text-12px text-[var(--el-text-color-regular)]">
            {{
              workflowVersionId
                ? '仅展示声明的参数；步骤输出须在运行时已产生才能引用。'
                : '未选择流程时使用通用示例；选择版本后加载该流程的变量。'
            }}
          </p>
        </div>
      </div>
      <p class="text-12px text-[var(--el-text-color-regular)]">
        示例均为模拟值，不读取真实运行或秘密参数；切换场景会重置测试数据。
      </p>
    </section>
    <ElAlert v-if="catalogError" :title="catalogError" type="error" :closable="false" show-icon>
      <ElButton size="small" @click="loadCatalog">重新加载</ElButton>
    </ElAlert>
    <ElTabs v-if="insertable" v-model="activeTab">
      <ElTabPane label="可用变量" name="variables" />
      <ElTabPane label="渲染预览" name="preview" />
    </ElTabs>
    <div v-show="!insertable || activeTab === 'preview'" class="flex flex-wrap items-center gap-12px">
      <span v-if="!insertable" class="font-medium">渲染预览</span>
      <div class="ml-auto flex flex-wrap items-center gap-8px">
        <ElButton
          v-if="!insertable"
          link
          type="primary"
          :aria-expanded="testVariablesVisible"
          @click="toggleTestVariables"
        >
          {{ testVariablesVisible ? '收起变量说明' : '查看可用变量' }}
        </ElButton>
        <ElButton size="small" :aria-expanded="sampleEditorVisible" @click="toggleSampleEditor">
          {{ sampleEditorVisible ? '收起测试数据' : '编辑测试数据' }}
        </ElButton>
        <ElButton
          size="small"
          type="primary"
          plain
          :loading="previewLoading"
          :disabled="catalogLoading || Boolean(catalogError) || !sampleText"
          @click="renderPreview"
        >
          {{ preview?.valid ? '重新生成' : '生成预览' }}
        </ElButton>
      </div>
    </div>
    <div v-show="insertable ? activeTab === 'variables' : testVariablesVisible" class="flex flex-col gap-12px">
      <div v-if="insertable" class="flex flex-wrap items-center gap-12px">
        <span class="w-64px shrink-0 text-[var(--el-text-color-regular)]">插入位置</span>
        <ElRadioGroup v-model="insertTarget">
          <ElRadio value="subjectTemplate">标题</ElRadio>
          <ElRadio value="bodyTemplate">正文</ElRadio>
          <ElRadio value="receiverTemplate">接收人</ElRadio>
        </ElRadioGroup>
      </div>
      <ElTable v-loading="catalogLoading" :data="variables" border max-height="260" row-key="expression">
        <ElTableColumn
          prop="expression"
          label="变量占位符"
          min-width="230"
          align="center"
          header-align="center"
          show-overflow-tooltip
        >
          <template #default="{ row }">
            <code class="text-12px">{{ row.expression }}</code>
          </template>
        </ElTableColumn>
        <ElTableColumn
          prop="label"
          label="含义"
          min-width="150"
          align="center"
          header-align="center"
          show-overflow-tooltip
        />
        <ElTableColumn label="示例" min-width="140" align="center" header-align="center" show-overflow-tooltip>
          <template #default="{ row }">{{ formatExample(row.example) }}</template>
        </ElTableColumn>
        <ElTableColumn v-if="insertable" label="操作" width="70" align="center" header-align="center" fixed="right">
          <template #default="{ row }">
            <ElButton link type="primary" @click="insertVariable(row.expression)">插入</ElButton>
          </template>
        </ElTableColumn>
      </ElTable>
    </div>
    <div v-show="!insertable || activeTab === 'preview'" class="flex flex-col gap-16px">
      <ElCollapseTransition>
        <div v-show="sampleEditorVisible" class="flex flex-col gap-8px">
          <div
            class="flex flex-wrap items-center justify-between gap-8px text-12px text-[var(--el-text-color-regular)]"
          >
            <span>测试数据 · JSON</span>
            <span>仅用于模拟渲染和测试发送</span>
          </div>
          <ElInput
            v-model="sampleText"
            class="text-12px font-mono"
            aria-label="通知测试数据"
            type="textarea"
            :autosize="{ minRows: 6, maxRows: 12 }"
            spellcheck="false"
          />
        </div>
      </ElCollapseTransition>
      <div aria-live="polite" :aria-busy="previewLoading" class="min-w-0">
        <ElSkeleton v-if="previewLoading" animated>
          <template #template>
            <div class="grid grid-cols-[64px_minmax(0,1fr)] items-start gap-x-12px gap-y-16px py-4px">
              <ElSkeletonItem variant="text" class="w-40px!" />
              <ElSkeletonItem variant="text" class="w-1/2!" />
              <ElSkeletonItem variant="text" class="w-40px!" />
              <div class="flex flex-col gap-8px">
                <ElSkeletonItem variant="text" />
                <ElSkeletonItem variant="text" />
                <ElSkeletonItem variant="text" class="w-2/3!" />
              </div>
              <ElSkeletonItem variant="text" class="w-40px!" />
              <ElSkeletonItem variant="text" class="w-1/2!" />
            </div>
          </template>
        </ElSkeleton>
        <ElAlert
          v-else-if="localError || previewErrors.length"
          title="预览未通过"
          type="error"
          :closable="false"
          show-icon
        >
          <ul class="flex flex-col gap-4px break-words text-12px leading-20px">
            <li v-if="localError">{{ localError }}</li>
            <li v-for="message in previewErrors" :key="message">
              {{ message }}
            </li>
          </ul>
        </ElAlert>
        <dl
          v-else-if="preview?.valid"
          class="grid grid-cols-[64px_minmax(0,1fr)] gap-x-12px gap-y-16px border border-[var(--el-border-color-lighter)] bg-[var(--el-fill-color-lighter)] px-16px py-12px"
        >
          <dt class="text-[var(--el-text-color-regular)]">标题</dt>
          <dd class="min-w-0 flex flex-col gap-4px">
            <span class="whitespace-pre-wrap break-words font-medium">{{ preview.subject || '未设置标题' }}</span>
            <span v-if="textOnly" class="text-12px text-[var(--el-text-color-regular)]">
              当前渠道仅发送正文，标题已完成校验。
            </span>
          </dd>
          <dt class="text-[var(--el-text-color-regular)]">正文</dt>
          <dd class="min-w-0">
            <div class="max-h-240px overflow-auto whitespace-pre-wrap break-words leading-24px">
              {{ preview.body || '未设置正文' }}
            </div>
          </dd>
          <dt class="text-[var(--el-text-color-regular)]">接收人</dt>
          <dd class="min-w-0 whitespace-pre-wrap break-words">
            {{ preview.receivers || '由渠道或运行配置决定' }}
          </dd>
        </dl>
        <div
          v-else
          class="min-h-140px flex flex-col items-center justify-center gap-6px border border-[var(--el-border-color)] border-dashed bg-[var(--el-fill-color-lighter)] px-16px py-20px text-center text-[var(--el-text-color-regular)]"
        >
          <icon-ep-document class="text-24px" aria-hidden="true" />
          <span>待生成预览</span>
          <span class="text-12px">使用当前模板和模拟数据，检查通知的实际显示内容。</span>
          <ElButton
            class="mt-6px"
            size="small"
            type="primary"
            plain
            :loading="previewLoading"
            :disabled="catalogLoading || Boolean(catalogError) || !sampleText"
            @click="renderPreview"
          >
            生成预览
          </ElButton>
        </div>
      </div>
      <p class="text-12px text-[var(--el-text-color-regular)] leading-20px">
        {{
          insertable
            ? '预览不会发送通知。保存模板后，可从列表发起测试。'
            : '预览不会发送通知。确认内容后，点击“发送测试”投递到真实渠道。'
        }}
      </p>
    </div>
  </div>
</template>
