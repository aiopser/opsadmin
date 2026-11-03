<script setup lang="tsx">
import { reactive, ref } from 'vue';
import { ElButton, ElTag } from 'element-plus';
import {
  fetchAddSecurityRule,
  fetchDeleteSecurityRule,
  fetchGetCommandIntercepts,
  fetchGetSecurityRules,
  fetchGetSecurityStats,
  fetchToggleSecurityRule,
  fetchUpdateSecurityRule
} from '@/service/api';
import { defaultTransform, useUIPaginatedTable } from '@/hooks/common/table';
import { $t } from '@/locales';

defineOptions({ name: 'OpsCommandFilter' });

const stats = ref<Api.Jobs.SecurityStats>({ ruleCount: 0, monthBlocked: 0 });
const saving = ref(false);
const togglingId = ref<number | null>(null);
const dialogVisible = ref(false);
const editingRule = ref<Api.Jobs.SecurityRuleRecord | null>(null);
const form = reactive<Api.Jobs.SecurityRulePayload>({
  pattern: '',
  match_mode: 'contains',
  risk_level: 'high',
  description: '',
  enabled: true
});

const matchModeOptions: Array<{ value: Api.Jobs.SecurityMatchMode; label: string }> = [
  { value: 'contains', label: $t('page.ops.commandFilter.matchModeContains') },
  { value: 'exact', label: $t('page.ops.commandFilter.matchModeExact') },
  { value: 'prefix', label: $t('page.ops.commandFilter.matchModePrefix') },
  { value: 'regex', label: $t('page.ops.commandFilter.matchModeRegex') }
];
const riskLevelOptions: Array<{ value: Api.Jobs.SecurityRiskLevel; label: string }> = [
  { value: 'medium', label: $t('page.ops.commandFilter.riskMedium') },
  { value: 'high', label: $t('page.ops.commandFilter.riskHigh') },
  { value: 'fatal', label: $t('page.ops.commandFilter.riskFatal') }
];

/** ============ 共用搜索（规则与拦截记录） ============ */

const filterSearch = ref('');

/** ============ 拦截规则列表 ============ */

const rulePage = reactive({ current: 1, size: 10 });

const {
  columns: ruleColumns,
  columnChecks: ruleColumnChecks,
  data: ruleRows,
  getData: loadRules,
  getDataByPage: getRulesByPage,
  loading: ruleLoading,
  mobilePagination: rulePagination
} = useUIPaginatedTable({
  paginationProps: {
    currentPage: rulePage.current,
    pageSize: rulePage.size
  },
  api: () =>
    fetchGetSecurityRules({
      current: rulePage.current,
      size: rulePage.size,
      search: filterSearch.value.trim() || undefined
    }),
  transform: response => defaultTransform(response),
  onPaginationParamsChange: params => {
    rulePage.current = params.currentPage ?? 1;
    rulePage.size = params.pageSize ?? 10;
  },
  columns: () => [
    { prop: 'id', label: 'ID', width: 70 },
    {
      prop: 'pattern',
      label: $t('page.ops.commandFilter.pattern'),
      minWidth: 210,
      showOverflowTooltip: true,
      formatter: row => (
        <code class="rounded-4px bg-[var(--el-fill-color-light)] px-8px py-4px text-13px">{row.pattern}</code>
      )
    },
    {
      prop: 'match_mode',
      label: $t('page.ops.commandFilter.matchMode'),
      width: 120,
      align: 'center',
      formatter: row => matchModeLabel(row.match_mode)
    },
    {
      prop: 'risk_level',
      label: $t('page.ops.commandFilter.riskLevel'),
      width: 100,
      align: 'center',
      formatter: row => (
        <ElTag type={riskTagType(row.risk_level)} effect="plain">
          {riskLevelLabel(row.risk_level)}
        </ElTag>
      )
    },
    {
      prop: 'description',
      label: $t('page.ops.commandFilter.descriptionColumn'),
      minWidth: 180,
      showOverflowTooltip: true,
      formatter: row => row.description || '-'
    },
    { prop: 'blocked_count', label: $t('page.ops.commandFilter.blockedCount'), width: 100, align: 'center' },
    {
      prop: 'enabled',
      label: $t('page.ops.commandFilter.status'),
      width: 90,
      align: 'center',
      formatter: row => (
        <ElTag type={row.enabled ? 'success' : 'info'} effect="plain">
          {$t(row.enabled ? 'page.ops.commandFilter.enabledState' : 'page.ops.commandFilter.disabledState')}
        </ElTag>
      )
    },
    {
      prop: 'operate',
      label: $t('page.ops.commandFilter.actions'),
      width: 190,
      align: 'center',
      fixed: 'right',
      formatter: row => (
        <>
          <ElButton type="primary" plain size="small" onClick={() => openEditDialog(row)}>
            {$t('common.edit')}
          </ElButton>
          <ElButton
            type="primary"
            plain
            size="small"
            loading={togglingId.value === row.id}
            onClick={() => toggleRule(row)}
          >
            {$t(row.enabled ? 'page.ops.commandFilter.disableAction' : 'page.ops.commandFilter.enableAction')}
          </ElButton>
          <ElPopconfirm
            title={$t('page.ops.commandFilter.deleteConfirm', { pattern: row.pattern })}
            onConfirm={() => deleteRule(row)}
          >
            {{
              reference: () => (
                <ElButton type="danger" plain size="small">
                  {$t('common.delete')}
                </ElButton>
              )
            }}
          </ElPopconfirm>
        </>
      )
    }
  ]
});

/** ============ 拦截记录列表 ============ */

const interceptPage = reactive({ current: 1, size: 10 });

const {
  columns: interceptColumns,
  columnChecks: interceptColumnChecks,
  data: interceptRows,
  getData: loadIntercepts,
  getDataByPage: getInterceptsByPage,
  loading: interceptLoading,
  mobilePagination: interceptPagination
} = useUIPaginatedTable({
  paginationProps: {
    currentPage: interceptPage.current,
    pageSize: interceptPage.size
  },
  api: () =>
    fetchGetCommandIntercepts({
      current: interceptPage.current,
      size: interceptPage.size,
      search: filterSearch.value.trim() || undefined
    }),
  transform: response => defaultTransform(response),
  onPaginationParamsChange: params => {
    interceptPage.current = params.currentPage ?? 1;
    interceptPage.size = params.pageSize ?? 10;
  },
  columns: () => [
    {
      prop: 'created_at',
      label: $t('page.ops.commandFilter.interceptTime'),
      width: 180,
      align: 'center',
      formatter: row => formatDate(row.created_at)
    },
    { prop: 'operatorName', label: $t('page.ops.commandFilter.operator'), width: 130, align: 'center' },
    {
      prop: 'command',
      label: $t('page.ops.commandFilter.command'),
      minWidth: 230,
      showOverflowTooltip: true
    },
    {
      prop: 'target_desc',
      label: $t('page.ops.commandFilter.target'),
      minWidth: 150,
      showOverflowTooltip: true,
      formatter: row => row.target_desc || '-'
    },
    {
      prop: 'hit_pattern',
      label: $t('page.ops.commandFilter.hitRule'),
      minWidth: 170,
      showOverflowTooltip: true,
      formatter: row => row.hit_pattern || '-'
    },
    {
      prop: 'risk_level',
      label: $t('page.ops.commandFilter.riskLevel'),
      width: 100,
      align: 'center',
      formatter: row => (
        <ElTag type={riskTagType(row.risk_level)} effect="plain">
          {riskLevelLabel(row.risk_level)}
        </ElTag>
      )
    }
  ]
});

/** ============ 共用搜索操作 ============ */

function searchAll() {
  getRulesByPage();
  getInterceptsByPage();
}

function resetSearch() {
  filterSearch.value = '';
  searchAll();
}

/** ============ 统计与规则维护 ============ */

async function loadStats() {
  const { data, error } = await fetchGetSecurityStats();
  if (!error && data) stats.value = data;
}

function resetForm() {
  form.pattern = '';
  form.match_mode = 'contains';
  form.risk_level = 'high';
  form.description = '';
  form.enabled = true;
}

function openCreateDialog() {
  editingRule.value = null;
  resetForm();
  dialogVisible.value = true;
}

function openEditDialog(row: Api.Jobs.SecurityRuleRecord) {
  editingRule.value = row;
  form.pattern = row.pattern;
  form.match_mode = row.match_mode;
  form.risk_level = row.risk_level;
  form.description = row.description;
  form.enabled = row.enabled;
  dialogVisible.value = true;
}

async function saveRule() {
  if (!form.pattern.trim()) {
    window.$message?.warning($t('page.ops.commandFilter.patternRequired'));
    return;
  }
  saving.value = true;
  try {
    const { error } = editingRule.value
      ? await fetchUpdateSecurityRule(editingRule.value.id, { ...form, pattern: form.pattern.trim() })
      : await fetchAddSecurityRule({ ...form, pattern: form.pattern.trim() });
    if (error) return;
    window.$notification?.success(
      $t(editingRule.value ? 'page.ops.commandFilter.updateSuccess' : 'page.ops.commandFilter.createSuccess')
    );
    dialogVisible.value = false;
    await Promise.all([loadRules(), loadStats()]);
  } finally {
    saving.value = false;
  }
}

async function toggleRule(row: Api.Jobs.SecurityRuleRecord) {
  togglingId.value = row.id;
  try {
    const { error } = await fetchToggleSecurityRule(row.id);
    if (error) return;
    window.$notification?.success(
      $t(row.enabled ? 'page.ops.commandFilter.disabled' : 'page.ops.commandFilter.enabled')
    );
    await Promise.all([loadRules(), loadStats()]);
  } finally {
    togglingId.value = null;
  }
}

async function deleteRule(row: Api.Jobs.SecurityRuleRecord) {
  const { error } = await fetchDeleteSecurityRule(row.id);
  if (error) return;
  window.$notification?.success($t('page.ops.commandFilter.deleteSuccess'));
  await Promise.all([loadRules(), loadStats()]);
}

function formatDate(value: string) {
  return value ? new Date(value).toLocaleString() : '-';
}

function riskTagType(level: Api.Jobs.SecurityRiskLevel | ''): 'info' | 'warning' | 'danger' {
  if (level === 'fatal') return 'danger';
  if (level === 'high') return 'warning';
  return 'info';
}

function matchModeLabel(mode: Api.Jobs.SecurityMatchMode) {
  return matchModeOptions.find(item => item.value === mode)?.label ?? mode;
}

function riskLevelLabel(level: Api.Jobs.SecurityRiskLevel | '') {
  return riskLevelOptions.find(item => item.value === level)?.label ?? '-';
}

loadStats();
getRulesByPage();
getInterceptsByPage();
</script>

<template>
  <div class="flex-col-stretch flex-shrink-0 gap-16px">
    <SearchPanel @reset="resetSearch" @search="searchAll">
      <ElForm label-width="80px" @submit.prevent="searchAll">
        <ElFormItem :label="$t('page.task.run.keyword')">
          <ElInput
            v-model="filterSearch"
            clearable
            :placeholder="$t('page.ops.commandFilter.ruleSearchPlaceholder')"
            @keyup.enter="searchAll"
            @clear="searchAll"
          />
        </ElFormItem>
      </ElForm>
    </SearchPanel>

    <ElCard class="card-wrapper">
      <template #header>
        <div class="flex flex-wrap items-center justify-between gap-12px">
          <div class="flex flex-col gap-4px">
            <p>{{ $t('page.ops.commandFilter.rulesTitle') }}</p>
            <span class="text-12px text-gray-400">
              {{ $t('page.ops.commandFilter.description') }}
              （{{ $t('page.ops.commandFilter.enabledRuleCount') }} {{ stats.ruleCount }} ·
              {{ $t('page.ops.commandFilter.monthBlocked') }} {{ stats.monthBlocked }}）
            </span>
          </div>
          <TableHeaderOperation
            v-model:columns="ruleColumnChecks"
            :loading="ruleLoading"
            :show-batch-delete="false"
            @refresh="loadRules"
          >
            <template #default>
              <ElButton type="primary" @click="openCreateDialog">
                {{ $t('page.ops.commandFilter.addRule') }}
              </ElButton>
            </template>
          </TableHeaderOperation>
        </div>
      </template>

      <ElTable v-loading="ruleLoading" border :data="ruleRows" row-key="id">
        <ElTableColumn v-for="col in ruleColumns" :key="col.prop" v-bind="col" />
      </ElTable>
      <div class="mt-20px flex justify-end">
        <ElPagination
          v-if="rulePagination.total"
          layout="total,prev,pager,next,sizes"
          v-bind="rulePagination"
          @current-change="rulePagination['current-change']"
          @size-change="rulePagination['size-change']"
        />
      </div>
    </ElCard>

    <ElCard class="card-wrapper">
      <template #header>
        <div class="flex items-center justify-between">
          <p>{{ $t('page.ops.commandFilter.interceptsTitle') }}</p>
          <TableHeaderOperation
            v-model:columns="interceptColumnChecks"
            :loading="interceptLoading"
            :show-add="false"
            :show-batch-delete="false"
            @refresh="loadIntercepts"
          />
        </div>
      </template>

      <ElTable v-loading="interceptLoading" border :data="interceptRows" row-key="id">
        <ElTableColumn v-for="col in interceptColumns" :key="col.prop" v-bind="col" />
      </ElTable>
      <div class="mt-20px flex justify-end">
        <ElPagination
          v-if="interceptPagination.total"
          layout="total,prev,pager,next,sizes"
          v-bind="interceptPagination"
          @current-change="interceptPagination['current-change']"
          @size-change="interceptPagination['size-change']"
        />
      </div>
    </ElCard>

    <ElDialog
      v-model="dialogVisible"
      :title="$t(editingRule ? 'page.ops.commandFilter.editTitle' : 'page.ops.commandFilter.addTitle')"
      width="560px"
    >
      <ElForm :model="form" label-width="110px" label-suffix="：" require-asterisk-position="left">
        <ElFormItem required>
          <template #label>
            <FormLabelHelp
              :label="$t('page.ops.commandFilter.pattern')"
              :help="[
                '命令中要拦截的特征内容，按所选匹配模式与待执行命令比对；',
                '命中规则的命令会被拒绝执行，并记录到拦截记录。'
              ]"
            />
          </template>
          <ElInput v-model="form.pattern" maxlength="255" show-word-limit />
        </ElFormItem>
        <ElFormItem>
          <template #label>
            <FormLabelHelp
              :label="$t('page.ops.commandFilter.matchMode')"
              :help="[
                '包含：命令中包含该内容即拦截；',
                '完全匹配：整条命令与特征完全一致；',
                '前缀匹配：命令以该内容开头；',
                '正则表达式：按 Python 正则（re.search）匹配命令。'
              ]"
            />
          </template>
          <ElSelect v-model="form.match_mode" class="w-full">
            <ElOption v-for="item in matchModeOptions" :key="item.value" :label="item.label" :value="item.value" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem>
          <template #label>
            <FormLabelHelp
              :label="$t('page.ops.commandFilter.riskLevel')"
              :help="['仅用于拦截记录的等级标注与筛选，不影响规则是否拦截。']"
            />
          </template>
          <ElSelect v-model="form.risk_level" class="w-full">
            <ElOption v-for="item in riskLevelOptions" :key="item.value" :label="item.label" :value="item.value" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem :label="$t('page.ops.commandFilter.descriptionColumn')">
          <ElInput v-model="form.description" type="textarea" :rows="3" maxlength="500" show-word-limit />
        </ElFormItem>
        <ElFormItem :label="$t('page.ops.commandFilter.status')">
          <ElSwitch
            v-model="form.enabled"
            :active-text="$t('page.ops.commandFilter.enabledState')"
            :inactive-text="$t('page.ops.commandFilter.disabledState')"
          />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="dialogVisible = false">{{ $t('common.cancel') }}</ElButton>
        <ElButton type="primary" :loading="saving" @click="saveRule">{{ $t('common.confirm') }}</ElButton>
      </template>
    </ElDialog>
  </div>
</template>
