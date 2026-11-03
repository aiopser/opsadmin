<script setup lang="tsx">
import { computed, h, ref, watch } from 'vue';
import { enableStatusOptions, menuIconTypeOptions, menuTypeOptions } from '@/constants/business';
import { addMenu, fetchGetAllRoles, updateMenu } from '@/service/api';
import { useMenuStore } from '@/store/modules/menu';
import { useForm, useFormRules } from '@/hooks/common/form';
import { getLocalIcons } from '@/utils/icon';
import { $t, $te } from '@/locales';
import SvgIcon from '@/components/custom/svg-icon.vue';
import {
  getLayoutAndPage,
  getPathParamFromRoutePath,
  getRoutePathByRouteName,
  resolveMenuRouteSubmission
} from './shared';

defineOptions({ name: 'MenuOperateModal' });

export type OperateType = UI.TableOperateType | 'addChild';

interface Props {
  /** 操作类型 */
  operateType: OperateType;
  /** 编辑的菜单数据，或添加子菜单时的父菜单数据 */
  rowData?: Api.SystemManage.Menu | null;
  /** 所有页面 */
  allPages: string[];
}

const props = defineProps<Props>();

interface Emits {
  (e: 'submitted'): void;
}

const emit = defineEmits<Emits>();

const visible = defineModel<boolean>('visible', {
  default: false
});

const { formRef, validate, restoreValidation } = useForm();
const { defaultRequiredRule } = useFormRules();

const title = computed(() => {
  const titles: Record<OperateType, string> = {
    add: $t('page.manage.menu.addMenu'),
    addChild: $t('page.manage.menu.addChildMenu'),
    edit: $t('page.manage.menu.editMenu')
  };
  return titles[props.operateType];
});

type Model = Pick<
  Api.SystemManage.Menu,
  | 'menuType'
  | 'menuName'
  | 'routeName'
  | 'routePath'
  | 'component'
  | 'order'
  | 'i18nKey'
  | 'icon'
  | 'iconType'
  | 'status'
  | 'parentId'
  | 'keepAlive'
  | 'constant'
  | 'href'
  | 'hideInMenu'
  | 'activeMenu'
  | 'multiTab'
  | 'fixedIndexInTab'
> & {
  query: NonNullable<Api.SystemManage.Menu['query']>;
  buttons: NonNullable<Api.SystemManage.Menu['buttons']>;
  layout: string;
  page: string;
  pathParam: string;
};

const model = ref(createDefaultModel());

function createDefaultModel(): Model {
  return {
    menuType: '1',
    menuName: '',
    routeName: '',
    routePath: '',
    pathParam: '',
    component: '',
    layout: '',
    page: '',
    i18nKey: null,
    icon: '',
    iconType: '1',
    parentId: 0,
    status: '1',
    keepAlive: false,
    constant: false,
    order: 0,
    href: null,
    hideInMenu: false,
    activeMenu: undefined,
    multiTab: false,
    fixedIndexInTab: undefined,
    query: [],
    buttons: []
  };
}

type RuleKey = Extract<keyof Model, 'menuName' | 'status' | 'routeName' | 'routePath' | 'href'>;

const rules: Record<RuleKey, App.Global.FormRule> = {
  menuName: defaultRequiredRule,
  status: defaultRequiredRule,
  routeName: defaultRequiredRule,
  routePath: defaultRequiredRule,
  href: {
    type: 'url',
    pattern: /^https?:\/\//,
    message: '外链须填写完整的 http:// 或 https:// 地址；内部页面请留空',
    trigger: 'blur'
  }
};

const disabledMenuType = computed(() => props.operateType === 'edit');

const localIcons = getLocalIcons();
const localIconOptions = localIcons.map(item => ({
  value: item
}));

function getIconLabelVNode(value: string) {
  return h('div', { class: 'flex-y-center gap-16px' }, [
    h(SvgIcon, { localIcon: value, class: 'text-icon' }),
    h('span', { class: 'text-sm' }, value)
  ]);
}

const showLayout = computed(() => model.value.parentId === 0);

const showPage = computed(() => model.value.menuType === '2');

const pageOptions = computed(() => {
  const allPages = [...props.allPages];

  if (model.value.page && !allPages.includes(model.value.page)) {
    allPages.unshift(model.value.page);
  }

  const opts: CommonType.Option[] = allPages.map(page => ({
    label: page,
    value: page
  }));

  return opts;
});

const layoutOptions: CommonType.Option[] = [
  { label: 'base', value: 'base' },
  { label: 'blank', value: 'blank' }
];

/** 已启用的角色选项 */
const roleOptions = ref<CommonType.Option<string>[]>([]);

async function getRoleOptions() {
  const { error, data } = await fetchGetAllRoles();

  if (!error) {
    const options = data.map(item => ({
      label: item.roleName,
      value: item.roleCode
    }));

    roleOptions.value = [...options];
  }
}

/** - 添加一个查询输入项 */
function addQuery(index: number) {
  model.value.query.splice(index + 1, 0, { key: '', value: '' });
}

/** - 移除一个查询输入项 */
function removeQuery(index: number) {
  model.value.query.splice(index, 1);
}

/** - 添加一个按钮表单项 */
function addButton(index: number) {
  model.value.buttons.splice(index + 1, 0, { code: '', desc: '' });
}

/** - 移除一个按钮表单项 */
function removeButton(index: number) {
  model.value.buttons.splice(index, 1);
}

function handleInitModel() {
  model.value = createDefaultModel();

  if (!props.rowData) return;

  if (props.operateType === 'addChild') {
    const { id } = props.rowData;

    Object.assign(model.value, { parentId: id });
  }

  if (props.operateType === 'edit') {
    const { component, ...rest } = props.rowData;

    const { layout, page } = getLayoutAndPage(component);
    const { path, param } = getPathParamFromRoutePath(rest.routePath);

    Object.assign(model.value, rest, { layout, page, routePath: path, pathParam: param });
  }

  if (!model.value.query) {
    model.value.query = [];
  }
  if (!model.value.buttons) {
    model.value.buttons = [];
  }
}

function closeDrawer() {
  visible.value = false;
}

function handleUpdateRoutePathByRouteName() {
  if (props.operateType === 'edit') return;
  if (model.value.routeName) {
    const path = getRoutePathByRouteName(model.value.routeName).toLowerCase();
    model.value.routePath = model.value.parentId ? path.replace(/^\//, '') : path;
  } else {
    model.value.routePath = '';
  }
}

function handleUpdateI18nKeyByRouteName() {
  const key = `route.${model.value.routeName}` as App.I18n.I18nKey;
  model.value.i18nKey = model.value.routeName && $te(key) ? key : null;
}

function handleRouteNameChange(value: string) {
  model.value.routeName = value;
  handleUpdateRoutePathByRouteName();
  handleUpdateI18nKeyByRouteName();
}

function getSubmitParams() {
  const { layout, page, pathParam, ...params } = model.value;

  const { component, routePath } = resolveMenuRouteSubmission(
    { layout, page, routePath: model.value.routePath, pathParam },
    props.operateType === 'edit' ? props.rowData : null
  );

  params.component = component;
  params.routePath = routePath;

  return params;
}

async function handleSubmit() {
  await validate();

  const params = getSubmitParams();

  const editId = props.operateType === 'edit' ? props.rowData?.id : undefined;
  const { error } =
    editId !== undefined ? await updateMenu(editId, params) : await addMenu(params as Api.SystemManage.MenuModel);

  if (!error) {
    window.$notification?.success($t('common.updateSuccess'));
    useMenuStore().invalidate();
    closeDrawer();
    emit('submitted');
  }
}

watch(visible, () => {
  if (visible.value) {
    handleInitModel();
    restoreValidation();
    getRoleOptions();
  }
});
</script>

<template>
  <ElDialog v-model="visible" :title="title" preset="card" class="w-800px">
    <ElScrollbar class="h-480px pr-20px">
      <ElForm
        ref="formRef"
        :model="model"
        :rules="rules"
        label-position="right"
        label-width="180px"
        label-suffix="："
        require-asterisk-position="left"
      >
        <ElRow>
          <ElCol :span="12">
            <ElFormItem :label="$t('page.manage.menu.menuType')" prop="menuType">
              <ElRadioGroup v-model="model.menuType" :disabled="disabledMenuType">
                <ElRadio
                  v-for="item in menuTypeOptions"
                  :key="item.value"
                  :value="item.value"
                  :label="$t(item.label)"
                />
              </ElRadioGroup>
            </ElFormItem>
          </ElCol>
          <ElCol :span="12">
            <ElFormItem :label="$t('page.manage.menu.menuName')" prop="menuName">
              <ElInput v-model="model.menuName" :placeholder="$t('page.manage.menu.form.menuName')" />
            </ElFormItem>
          </ElCol>
          <ElCol :span="12">
            <ElFormItem prop="routeName">
              <template #label>
                <FormLabelHelp
                  :label="$t('page.manage.menu.routeName')"
                  :help="[
                    '路由名称全局唯一，不可包含斜杠和连字符；',
                    '路由名称是唯一标识，可保留历史命名；修改名称不会改写已有路径。'
                  ]"
                />
              </template>
              <ElInput
                :model-value="model.routeName"
                :placeholder="$t('page.manage.menu.form.routeName')"
                @update:model-value="handleRouteNameChange"
              />
            </ElFormItem>
          </ElCol>
          <ElCol :span="12">
            <ElFormItem prop="routePath">
              <template #label>
                <FormLabelHelp
                  :label="$t('page.manage.menu.routePath')"
                  :help="['顶级路径以 / 开头；子菜单通常填写 user、config 等相对路径。以 / 开头表示绝对路径。']"
                />
              </template>
              <ElInput v-model="model.routePath" :placeholder="$t('page.manage.menu.form.routePath')" />
            </ElFormItem>
          </ElCol>
          <ElCol :span="12">
            <ElFormItem prop="pathParam">
              <template #label>
                <FormLabelHelp
                  :label="$t('page.manage.menu.pathParam')"
                  :help="['动态路由参数，将追加到路由路径末尾，如填写 id 生成 /manage/user/:id。']"
                />
              </template>
              <ElInput v-model="model.pathParam" :placeholder="$t('page.manage.menu.form.pathParam')" />
            </ElFormItem>
          </ElCol>
          <ElCol v-if="showLayout" :span="12">
            <ElFormItem prop="layout">
              <template #label>
                <FormLabelHelp
                  :label="$t('page.manage.menu.layout')"
                  :help="['顶级菜单的页面布局：base 为带导航布局，blank 为无导航空白布局。']"
                />
              </template>
              <ElSelect v-model="model.layout" clearable :placeholder="$t('page.manage.menu.form.layout')">
                <ElOption
                  v-for="{ label, value } in layoutOptions"
                  :key="value"
                  :label="label"
                  :value="value"
                ></ElOption>
              </ElSelect>
            </ElFormItem>
          </ElCol>
          <ElCol v-if="showPage" :span="12">
            <ElFormItem prop="page">
              <template #label>
                <FormLabelHelp
                  :label="$t('page.manage.menu.page')"
                  :help="['菜单类型为「菜单」时生效，选择对应的页面组件（view.* 路由），如 view.manage_user。']"
                />
              </template>
              <ElSelect v-model="model.page" clearable :placeholder="$t('page.manage.menu.form.page')">
                <ElOption v-for="{ label, value } in pageOptions" :key="value" :label="label" :value="value"></ElOption>
              </ElSelect>
            </ElFormItem>
          </ElCol>
          <ElCol :span="12">
            <ElFormItem prop="i18nKey">
              <template #label>
                <FormLabelHelp
                  :label="$t('page.manage.menu.i18nKey')"
                  :help="['可选；仅在语言文件中有对应翻译时填写，留空使用菜单名称。']"
                />
              </template>
              <ElInput v-model="model.i18nKey" :placeholder="$t('page.manage.menu.form.i18nKey')" />
            </ElFormItem>
          </ElCol>
          <ElCol :span="12">
            <ElFormItem :label="$t('page.manage.menu.order')" prop="order">
              <ElInputNumber v-model="model.order" class="w-full" :placeholder="$t('page.manage.menu.form.order')" />
            </ElFormItem>
          </ElCol>
          <ElCol :span="12">
            <ElFormItem :label="$t('page.manage.menu.iconTypeTitle')" prop="iconType">
              <ElRadioGroup v-model="model.iconType">
                <ElRadio
                  v-for="item in menuIconTypeOptions"
                  :key="item.value"
                  :value="item.value"
                  :label="$t(item.label)"
                />
              </ElRadioGroup>
            </ElFormItem>
          </ElCol>
          <ElCol :span="12">
            <ElFormItem :label="$t('page.manage.menu.icon')" prop="icon">
              <template v-if="model.iconType === '1'">
                <ElInput v-model="model.icon" :placeholder="$t('page.manage.menu.form.icon')" class="flex-1">
                  <template #suffix>
                    <SvgIcon v-if="model.icon" :icon="model.icon" class="text-icon" />
                  </template>
                </ElInput>
              </template>
              <template v-if="model.iconType === '2'">
                <ElSelect v-model="model.icon" :placeholder="$t('page.manage.menu.form.localIcon')">
                  <template #label="{ value }">
                    <component :is="getIconLabelVNode(value)" />
                  </template>
                  <ElOption v-for="{ value } in localIconOptions" :key="value" :value="value">
                    <component :is="getIconLabelVNode(value)" />
                  </ElOption>
                </ElSelect>
              </template>
            </ElFormItem>
          </ElCol>
          <ElCol :span="12">
            <ElFormItem :label="$t('page.manage.menu.menuStatus')" prop="status">
              <ElRadioGroup v-model="model.status">
                <ElRadio
                  v-for="{ label, value } in enableStatusOptions"
                  :key="value"
                  :value="value"
                  :label="$t(label)"
                />
              </ElRadioGroup>
            </ElFormItem>
          </ElCol>
          <ElCol :span="12">
            <ElFormItem prop="keepAlive">
              <template #label>
                <FormLabelHelp
                  :label="$t('page.manage.menu.keepAlive')"
                  :help="['开启后切换再回到该页面时保留页面状态，不重新加载。']"
                />
              </template>
              <ElRadioGroup v-model="model.keepAlive">
                <ElRadio :value="true" :label="$t('common.yesOrNo.yes')" />
                <ElRadio :value="false" :label="$t('common.yesOrNo.no')" />
              </ElRadioGroup>
            </ElFormItem>
          </ElCol>
          <ElCol :span="12">
            <ElFormItem prop="constant">
              <template #label>
                <FormLabelHelp
                  :label="$t('page.manage.menu.constant')"
                  :help="['开启后为常量路由：无需登录即可访问，如登录页、404 页，请谨慎开启。']"
                />
              </template>
              <ElRadioGroup v-model="model.constant">
                <ElRadio :value="true" :label="$t('common.yesOrNo.yes')" />
                <ElRadio :value="false" :label="$t('common.yesOrNo.no')" />
              </ElRadioGroup>
            </ElFormItem>
          </ElCol>
          <ElCol :span="12">
            <ElFormItem prop="href">
              <template #label>
                <FormLabelHelp
                  :label="$t('page.manage.menu.href')"
                  :help="['填写外链地址后菜单直接跳转外部链接，需以 http:// 或 https:// 开头。']"
                />
              </template>
              <ElInput v-model="model.href" autocomplete="off" placeholder="内部页面留空；外链填写 https://..." />
            </ElFormItem>
          </ElCol>
          <ElCol :span="12">
            <ElFormItem prop="hideInMenu">
              <template #label>
                <FormLabelHelp
                  :label="$t('page.manage.menu.hideInMenu')"
                  :help="['开启后菜单不在侧边栏显示，但路由仍可正常访问。']"
                />
              </template>
              <ElRadioGroup v-model="model.hideInMenu">
                <ElRadio :value="true" :label="$t('common.yesOrNo.yes')" />
                <ElRadio :value="false" :label="$t('common.yesOrNo.no')" />
              </ElRadioGroup>
            </ElFormItem>
          </ElCol>
          <ElCol v-if="model.hideInMenu" :span="12">
            <ElFormItem prop="activeMenu">
              <template #label>
                <FormLabelHelp
                  :label="$t('page.manage.menu.activeMenu')"
                  :help="['隐藏菜单时，指定访问该路由时要高亮的菜单（填写其路由名称）。']"
                />
              </template>
              <ElSelect
                v-model="model.activeMenu"
                :options="pageOptions"
                clearable
                :placeholder="$t('page.manage.menu.form.activeMenu')"
              >
                <ElOption v-for="{ label, value } in pageOptions" :key="value" :label="label" :value="value"></ElOption>
              </ElSelect>
            </ElFormItem>
          </ElCol>
          <ElCol :span="12">
            <ElFormItem prop="multiTab">
              <template #label>
                <FormLabelHelp
                  :label="$t('page.manage.menu.multiTab')"
                  :help="['开启后同一页面带不同查询参数时会打开多个页签。']"
                />
              </template>
              <ElRadioGroup v-model="model.multiTab">
                <ElRadio :value="true" :label="$t('common.yesOrNo.yes')" />
                <ElRadio :value="false" :label="$t('common.yesOrNo.no')" />
              </ElRadioGroup>
            </ElFormItem>
          </ElCol>
          <ElCol :span="12">
            <ElFormItem prop="fixedIndexInTab">
              <template #label>
                <FormLabelHelp
                  :label="$t('page.manage.menu.fixedIndexInTab')"
                  :help="['页签固定在页签栏的位置序号，从 0 开始，越小越靠前；不填则不固定。']"
                />
              </template>
              <ElInputNumber
                v-model="model.fixedIndexInTab"
                class="w-full"
                clearable
                :placeholder="$t('page.manage.menu.form.fixedIndexInTab')"
              />
            </ElFormItem>
          </ElCol>
          <ElCol :span="24">
            <ElFormItem prop="query">
              <template #label>
                <FormLabelHelp
                  :label="$t('page.manage.menu.query')"
                  :help="[
                    '路由默认查询参数，访问页面时自动拼接到地址后；',
                    '格式如 [{&quot;key&quot;: &quot;id&quot;, &quot;value&quot;: &quot;1&quot;}]'
                  ]"
                />
              </template>
              <ElButton v-if="model.query.length === 0" class="w-full border-dashed" @click="addQuery(-1)">
                <template #icon>
                  <icon-carbon-add class="align-sub text-icon" />
                </template>
                <span class="ml-8px">{{ $t('common.add') }}</span>
              </ElButton>
              <template v-else>
                <div v-for="(item, index) in model.query" :key="index" class="flex gap-3">
                  <ElCol :span="10">
                    <ElFormItem :prop="['query', index.toString(), 'key']">
                      <ElInput v-model="item.key" :placeholder="$t('page.manage.menu.form.queryKey')" class="flex-1" />
                    </ElFormItem>
                  </ElCol>
                  <ElCol :span="10">
                    <ElFormItem :prop="['query', index.toString(), 'value']">
                      <ElInput
                        v-model="item.value"
                        :placeholder="$t('page.manage.menu.form.queryValue')"
                        class="flex-1"
                      />
                    </ElFormItem>
                  </ElCol>
                  <ElCol :span="4">
                    <ElSpace class="ml-12px">
                      <ElButton @click="addQuery(index)">
                        <template #icon>
                          <icon-ic-round-plus class="align-sub text-icon" />
                        </template>
                      </ElButton>
                      <ElButton @click="removeQuery(index)">
                        <template #icon>
                          <icon-ic-round-remove class="align-sub text-icon" />
                        </template>
                      </ElButton>
                    </ElSpace>
                  </ElCol>
                </div>
              </template>
            </ElFormItem>
          </ElCol>
          <ElCol :span="24">
            <ElFormItem :label-col="{ span: 4 }" prop="buttons">
              <template #label>
                <FormLabelHelp
                  :label="$t('page.manage.menu.button')"
                  :help="[
                    '按钮权限编码，即前端按钮的权限标识，同一菜单下不可重复；',
                    '编码需与后端权限标识一致，用于控制按钮的显示与操作。'
                  ]"
                />
              </template>
              <ElButton v-if="model.buttons.length === 0" class="w-full border-dashed" @click="addButton(-1)">
                <template #icon>
                  <icon-carbon-add class="align-sub text-icon" />
                </template>
                <span class="ml-8px">{{ $t('common.add') }}</span>
              </ElButton>
              <template v-else>
                <div v-for="(item, index) in model.buttons" :key="index" class="flex gap-3">
                  <ElCol :span="10">
                    <ElFormItem :prop="['buttons', index.toString(), 'code']">
                      <ElInput
                        v-model="item.code"
                        :placeholder="$t('page.manage.menu.form.buttonCode')"
                        class="flex-1"
                      ></ElInput>
                    </ElFormItem>
                  </ElCol>
                  <ElCol :span="10">
                    <ElFormItem :prop="['buttons', index.toString(), 'desc']">
                      <ElInput
                        v-model="item.desc"
                        :placeholder="$t('page.manage.menu.form.buttonDesc')"
                        class="flex-1"
                      ></ElInput>
                    </ElFormItem>
                  </ElCol>
                  <ElCol :span="4">
                    <ElSpace class="ml-12px">
                      <ElButton @click="addButton(index)">
                        <template #icon>
                          <icon-ic-round-plus class="align-sub text-icon" />
                        </template>
                      </ElButton>
                      <ElButton @click="removeButton(index)">
                        <template #icon>
                          <icon-ic-round-remove class="align-sub text-icon" />
                        </template>
                      </ElButton>
                    </ElSpace>
                  </ElCol>
                </div>
              </template>
            </ElFormItem>
          </ElCol>
        </ElRow>
      </ElForm>
    </ElScrollbar>
    <template #footer>
      <ElSpace :size="16" class="float-right">
        <ElButton @click="closeDrawer">{{ $t('common.cancel') }}</ElButton>
        <ElButton type="primary" @click="handleSubmit">{{ $t('common.confirm') }}</ElButton>
      </ElSpace>
    </template>
  </ElDialog>
</template>

<style scoped></style>
