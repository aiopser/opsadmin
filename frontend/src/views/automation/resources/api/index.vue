<script setup lang="tsx">
import { computed, ref } from 'vue';
import {
  fetchAddApiEndpoint,
  fetchDeleteApiEndpoint,
  fetchGetApiEndpointList,
  fetchUpdateApiEndpoint
} from '@/service/api';
import { defaultTransform, useUIPaginatedTable } from '@/hooks/common/table';
import CodeEditor from '@/components/common/code-editor/index.vue';

defineOptions({ name: 'AutomationApiResource' });

/** ============ 搜索 ============ */

function getInitSearchParams() {
  return { current: 1, size: 10, search: undefined as string | undefined };
}

const searchParams = ref(getInitSearchParams());

/** ============ 列表 ============ */

const methodOptions = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS'];

const methodTagType: Record<string, 'primary' | 'success' | 'warning' | 'info' | 'danger'> = {
  GET: 'success',
  POST: 'warning',
  PUT: 'info',
  PATCH: 'primary',
  DELETE: 'danger'
};

const authTypeOptions = [
  { value: 'none', label: '匿名' },
  { value: 'basic', label: 'basic_auth' },
  { value: 'bearer', label: 'bearer' },
  { value: 'api_key', label: 'api_key' }
];

const authTypeText: Record<string, string> = Object.fromEntries(authTypeOptions.map(item => [item.value, item.label]));

const { columns, columnChecks, data, getData, getDataByPage, loading, mobilePagination } = useUIPaginatedTable({
  paginationProps: {
    currentPage: searchParams.value.current,
    pageSize: searchParams.value.size
  },
  api: () => fetchGetApiEndpointList(searchParams.value),
  transform: response => defaultTransform(response),
  onPaginationParamsChange: params => {
    searchParams.value.current = params.currentPage ?? 1;
    searchParams.value.size = params.pageSize ?? 10;
  },
  columns: () => [
    { prop: 'id', label: 'ID', width: 70 },
    { prop: 'name', label: '名称', minWidth: 140, showOverflowTooltip: true },
    {
      prop: 'description',
      label: '描述',
      minWidth: 140,
      showOverflowTooltip: true,
      formatter: row => row.description || '-'
    },
    {
      prop: 'method',
      label: '请求方法',
      width: 100,
      align: 'center',
      formatter: row => <ElTag type={methodTagType[row.method] ?? 'info'}>{row.method}</ElTag>
    },
    {
      prop: 'url',
      label: 'URL',
      minWidth: 200,
      showOverflowTooltip: true,
      formatter: row => <span class="text-12px font-mono">{row.url}</span>
    },
    {
      prop: 'authType',
      label: '认证',
      width: 90,
      align: 'center',
      formatter: row => authTypeText[row.authType] ?? row.authType
    },
    { prop: 'timeoutSeconds', label: '超时(s)', width: 90, align: 'center' },
    {
      prop: 'isActive',
      label: '状态',
      width: 90,
      align: 'center',
      formatter: row => <ElTag type={row.isActive ? 'success' : 'info'}>{row.isActive ? '启用' : '停用'}</ElTag>
    },
    { prop: 'updatedAt', label: '更新时间', width: 170, formatter: row => row.updatedAt || '-' },
    {
      prop: 'operate',
      label: '操作',
      width: 150,
      align: 'center',
      fixed: 'right',
      formatter: row => (
        <>
          <ElButton type="primary" plain size="small" onClick={() => openOperateDrawer('edit', row)}>
            编辑
          </ElButton>
          <ElPopconfirm title="确认删除该 API 端点？" onConfirm={() => handleDelete(row.id)}>
            {{
              reference: () => (
                <ElButton type="danger" plain size="small">
                  删除
                </ElButton>
              )
            }}
          </ElPopconfirm>
        </>
      )
    }
  ]
});

const hasFilter = computed(() => Boolean(searchParams.value.search));

function resetSearchParams() {
  searchParams.value = getInitSearchParams();
  getDataByPage();
}

/** ============ 新增/编辑抽屉 ============ */

/** 抽屉宽度与表单最大宽度：左侧留白 = drawerSize - formMaxWidth，自行调整这两个值 */
const drawerSize = '1200px';
const formMaxWidth = '1120px';

type OperateType = 'add' | 'edit';

interface FormModel {
  id?: number;
  name: string;
  description: string;
  method: string;
  url: string;
  authType: 'none' | 'basic' | 'bearer' | 'api_key';
  username: string;
  secret: string;
  apiKeyName: string;
  apiKeyLocation: 'header' | 'query';
  headersText: string;
  bodyText: string;
  successRulesText: string;
  timeoutSeconds: number;
  verifySsl: boolean;
  isActive: boolean;
}

function createDefaultForm(): FormModel {
  return {
    name: '',
    description: '',
    method: 'GET',
    url: '',
    authType: 'none',
    username: '',
    secret: '',
    apiKeyName: 'X-API-Key',
    apiKeyLocation: 'header',
    headersText: '',
    bodyText: '{}',
    successRulesText: '{"statusCodes": [200]}',
    timeoutSeconds: 180,
    verifySsl: true,
    isActive: true
  };
}

const drawerVisible = ref(false);
const operateType = ref<OperateType>('add');
const submitting = ref(false);
const formRef = ref();
const formModel = ref<FormModel>(createDefaultForm());

const formRules = {
  name: [{ required: true, message: '请输入 API 名称', trigger: 'blur' }],
  url: [{ required: true, message: '请输入接口地址', trigger: 'blur' }],
  successRulesText: [{ required: true, message: '请输入成功判断', trigger: 'blur' }]
};

type JsonParseResult = { ok: true; value?: Record<string, unknown> } | { ok: false };

/** 空文本视为未填写，其余必须解析为 JSON 对象 */
function parseJsonObject(text: string): JsonParseResult {
  const trimmed = text.trim();
  if (!trimmed) return { ok: true };
  try {
    const parsed: unknown = JSON.parse(trimmed);
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return { ok: false };
    return { ok: true, value: parsed as Record<string, unknown> };
  } catch {
    return { ok: false };
  }
}

function stringifyJsonField(value: Record<string, unknown> | null | undefined) {
  return value && Object.keys(value).length ? JSON.stringify(value) : '';
}

function openOperateDrawer(type: OperateType, row?: Api.Automation.ApiEndpointRecord) {
  operateType.value = type;
  formModel.value = row
    ? {
        id: row.id,
        name: row.name,
        description: row.description,
        method: row.method,
        url: row.url,
        authType: (row.authType || 'none') as FormModel['authType'],
        username: row.username,
        secret: '',
        apiKeyName: row.apiKeyName || 'X-API-Key',
        apiKeyLocation: (row.apiKeyLocation || 'header') as FormModel['apiKeyLocation'],
        headersText: stringifyJsonField(row.headers),
        bodyText: row.body || '{}',
        successRulesText: stringifyJsonField(row.successRules) || '{"statusCodes": [200]}',
        timeoutSeconds: row.timeoutSeconds,
        verifySsl: row.verifySsl,
        isActive: row.isActive
      }
    : createDefaultForm();
  drawerVisible.value = true;
}

/** 按认证方式校验必填项：basic 需用户名；新增时 bearer/api_key 需密钥；api_key 另需密钥名称 */
function validateAuthFields(): string | null {
  const form = formModel.value;
  if (form.authType === 'basic' && !form.username.trim()) {
    return 'Basic 认证需要填写用户名';
  }
  if (form.authType !== 'none' && !form.secret && operateType.value === 'add') {
    return `请填写${authTypeLabel(form.authType)}密钥`;
  }
  if (form.authType === 'api_key' && !form.apiKeyName.trim()) {
    return 'API Key 认证需要填写密钥名称（请求头或查询参数名）';
  }
  return null;
}

function authTypeLabel(type: FormModel['authType']): string {
  return authTypeOptions.find(item => item.value === type)?.label ?? '';
}

/** 组装提交载荷：按认证方式决定携带的字段 */
function buildPayload(): Api.Automation.ApiEndpointPayload {
  const form = formModel.value;
  const headers = parseJsonObject(form.headersText);
  const successRules = parseJsonObject(form.successRulesText);
  const body = parseJsonObject(form.bodyText);

  const payload: Api.Automation.ApiEndpointPayload = {
    name: form.name,
    description: form.description,
    method: form.method,
    url: form.url,
    authType: form.authType,
    timeoutSeconds: form.timeoutSeconds,
    verifySsl: form.verifySsl,
    isActive: form.isActive,
    body: form.bodyText.trim(),
    bodyType: form.bodyText.trim() ? 'json' : 'none'
  };
  // 匿名认证不显示也不提交 Headers
  if (form.authType !== 'none' && headers.ok && headers.value) {
    payload.headers = headers.value;
  }
  if (body.ok && body.value) {
    payload.body = JSON.stringify(body.value);
  }
  if (successRules.ok && successRules.value) {
    payload.successRules = successRules.value;
  }
  if (form.authType === 'basic') {
    payload.username = form.username;
  }
  if (form.authType === 'api_key') {
    payload.apiKeyName = form.apiKeyName.trim();
    payload.apiKeyLocation = form.apiKeyLocation;
  }
  // secret 仅在填写时提交（编辑留空表示不修改密钥）
  if (form.secret) {
    payload.secret = form.secret;
  }
  return payload;
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false);
  if (!valid) return;

  const authError = validateAuthFields();
  if (authError) {
    window.$message?.error(authError);
    return;
  }

  const jsonFields = [formModel.value.headersText, formModel.value.successRulesText, formModel.value.bodyText];
  if (jsonFields.some(text => !parseJsonObject(text).ok)) {
    window.$message?.error('Headers、参数与成功判断必须是合法的 JSON 对象');
    return;
  }

  submitting.value = true;
  const payload = buildPayload();
  const { error } =
    operateType.value === 'add'
      ? await fetchAddApiEndpoint(payload)
      : await fetchUpdateApiEndpoint(formModel.value.id!, payload);
  submitting.value = false;

  if (!error) {
    window.$notification?.success(operateType.value === 'add' ? '新增成功' : '修改成功');
    drawerVisible.value = false;
    getData();
  }
}

/** 删除确认由表格列的 ElPopconfirm 承担，此处直接执行 */
async function handleDelete(id: number) {
  const { error } = await fetchDeleteApiEndpoint(id);

  if (!error) {
    window.$notification?.success('删除成功');
    getData();
  }
}
</script>

<template>
  <div class="min-h-500px flex-col-stretch gap-16px overflow-hidden lt-sm:overflow-auto">
    <SearchPanel @reset="resetSearchParams" @search="getDataByPage">
      <ElForm :model="searchParams" label-width="80px" @submit.prevent="getDataByPage">
        <ElFormItem label="关键词">
          <ElInput v-model="searchParams.search" clearable placeholder="名称/URL/描述" @keyup.enter="getDataByPage()" />
        </ElFormItem>
      </ElForm>
    </SearchPanel>

    <ElCard class="card-wrapper sm:flex-1-hidden">
      <template #header>
        <div class="flex items-center justify-between">
          <div class="flex items-baseline gap-8px">
            <p>API 端点</p>
            <span class="text-13px text-gray-500">供节点执行调用的外部接口，密钥加密存储</span>
          </div>
          <TableHeaderOperation
            v-model:columns="columnChecks"
            :loading="loading"
            :show-batch-delete="false"
            @refresh="getData"
          >
            <template #default>
              <ElButton type="primary" @click="openOperateDrawer('add')">
                <template #icon>
                  <icon-ic-round-plus class="text-icon" />
                </template>
                新增
              </ElButton>
            </template>
          </TableHeaderOperation>
        </div>
      </template>
      <div class="h-[calc(100%-52px)]">
        <ElTable v-loading="loading" height="100%" border class="sm:h-full" :data="data" row-key="id">
          <ElTableColumn v-for="col in columns" :key="col.prop" v-bind="col" />
          <template #empty>
            <ElEmpty
              v-if="!loading"
              :description="hasFilter ? '没有符合条件的 API 端点' : '暂无 API 端点'"
              :image-size="80"
            >
              <ElButton v-if="!hasFilter" type="primary" @click="openOperateDrawer('add')">新增 API 端点</ElButton>
            </ElEmpty>
          </template>
        </ElTable>
      </div>
      <div class="mt-20px flex justify-end">
        <ElPagination
          v-if="mobilePagination.total"
          layout="total,prev,pager,next,sizes"
          v-bind="mobilePagination"
          @current-change="mobilePagination['current-change']"
          @size-change="mobilePagination['size-change']"
        />
      </div>
    </ElCard>

    <ElDrawer
      v-model="drawerVisible"
      :title="operateType === 'add' ? '添加API' : '编辑API'"
      :size="drawerSize"
      :close-on-click-modal="false"
    >
      <ElForm
        ref="formRef"
        :model="formModel"
        :rules="formRules"
        label-width="130px"
        label-suffix="："
        require-asterisk-position="left"
        class="ml-auto"
        :style="{ maxWidth: formMaxWidth }"
      >
        <ElFormItem label="API名称" prop="name">
          <ElInput v-model="formModel.name" placeholder="请输入" />
        </ElFormItem>
        <ElFormItem label="认证方式" prop="authType">
          <ElRadioGroup v-model="formModel.authType">
            <ElRadio v-for="item in authTypeOptions" :key="item.value" :value="item.value">
              {{ item.label }}
            </ElRadio>
          </ElRadioGroup>
        </ElFormItem>
        <ElFormItem v-if="formModel.authType === 'basic'" label="用户名">
          <ElInput v-model="formModel.username" placeholder="Basic 认证用户名" />
        </ElFormItem>
        <ElFormItem v-if="formModel.authType !== 'none'" label="密钥">
          <template #label>
            <FormLabelHelp
              label="密钥"
              :help="[
                'Basic 认证填登录密码，bearer 填 Token，api_key 填密钥值；',
                '密钥加密存储，编辑时留空表示不修改。'
              ]"
            />
          </template>
          <ElInput
            v-model="formModel.secret"
            type="password"
            show-password
            :placeholder="operateType === 'edit' ? '留空则不修改密钥' : '密码 / Token / API Key'"
          />
        </ElFormItem>
        <ElFormItem v-if="formModel.authType === 'api_key'" label="密钥名称">
          <ElInput v-model="formModel.apiKeyName" placeholder="请求头 / 查询参数名，如 X-API-Key" />
        </ElFormItem>
        <ElFormItem v-if="formModel.authType === 'api_key'" label="密钥位置">
          <ElRadioGroup v-model="formModel.apiKeyLocation">
            <ElRadio value="header">请求头 Header</ElRadio>
            <ElRadio value="query">查询参数 Query</ElRadio>
          </ElRadioGroup>
        </ElFormItem>
        <ElFormItem v-if="formModel.authType !== 'none'" label="Headers">
          <template #label>
            <FormLabelHelp
              label="Headers"
              :help="[
                '自定义请求头，仅支持 JSON 对象，如 {&quot;Content-Type&quot;: &quot;application/json&quot;}；',
                '匿名认证不会提交 Headers。'
              ]"
            />
          </template>
          <ElInput
            v-model="formModel.headersText"
            class="font-mono"
            clearable
            placeholder='{"Content-Type": "application/json"}'
          />
        </ElFormItem>
        <ElFormItem label="接口地址" prop="url">
          <ElInput v-model="formModel.url" placeholder="请输入" />
        </ElFormItem>
        <ElFormItem label="请求方式" prop="method">
          <ElRadioGroup v-model="formModel.method">
            <ElRadio v-for="item in methodOptions" :key="item" :value="item">
              {{ item }}
            </ElRadio>
          </ElRadioGroup>
        </ElFormItem>
        <ElFormItem label="参数" prop="bodyText">
          <template #label>
            <FormLabelHelp
              label="参数"
              :help="[
                '请求体内容，仅支持 JSON 对象；',
                'JSON 类型请求会自动添加 Content-Type: application/json 请求头。'
              ]"
            />
          </template>
          <CodeEditor
            v-model="formModel.bodyText"
            language="json"
            dark
            height="140px"
            placeholder="请输入请求体 JSON"
          />
        </ElFormItem>
        <ElFormItem label="成功判断" prop="successRulesText">
          <template #label>
            <FormLabelHelp
              label="成功判断"
              :help="[
                '1、statusCodes：接受的 HTTP 状态码列表，如 [200]，不填则 2xx/3xx 均视为成功；',
                '2、bodyRules：响应体 JSON 匹配规则，全部满足才算成功，如 {&quot;path&quot;: &quot;$.code&quot;, &quot;operator&quot;: &quot;eq&quot;, &quot;value&quot;: 0}',
                'operator 可选 eq / ne / contains / exists。'
              ]"
            />
          </template>
          <ElInput
            v-model="formModel.successRulesText"
            class="font-mono"
            clearable
            placeholder='{"statusCodes": [200], "bodyRules": []}'
          />
        </ElFormItem>
        <ElFormItem label="描述">
          <ElInput v-model="formModel.description" placeholder="请输入" />
        </ElFormItem>
        <ElFormItem label="超时与运行配置">
          <div class="grid grid-cols-3 items-center gap-16px">
            <div class="flex items-center">
              <FormLabelHelp
                label="超时时间"
                class="config-sub-label shrink-0 text-14px"
                :help="['单次请求的超时时间，范围 1-600 秒。']"
              />
              <ElInputNumber v-model="formModel.timeoutSeconds" :min="1" :max="600" :controls="false" class="flex-1" />
            </div>
            <div class="flex items-center">
              <FormLabelHelp
                label="校验SSL"
                class="config-sub-label shrink-0 text-14px"
                :help="['关闭后跳过 HTTPS 证书校验，仅用于内网自签证书等可信场景。']"
              />
              <ElSwitch v-model="formModel.verifySsl" />
            </div>
            <div class="flex items-center">
              <FormLabelHelp
                label="启用"
                class="config-sub-label shrink-0 text-14px"
                :help="['停用后流程节点引用该端点将执行失败。']"
              />
              <ElSwitch v-model="formModel.isActive" />
            </div>
          </div>
        </ElFormItem>
      </ElForm>
      <template #footer>
        <div class="ml-auto text-right" :style="{ maxWidth: formMaxWidth }">
          <ElButton @click="drawerVisible = false">取消</ElButton>
          <ElButton type="primary" :loading="submitting" @click="handleSubmit">确定</ElButton>
        </div>
      </template>
    </ElDrawer>
  </div>
</template>

<style scoped>
.config-sub-label {
  color: var(--el-text-color-regular);
}
</style>
