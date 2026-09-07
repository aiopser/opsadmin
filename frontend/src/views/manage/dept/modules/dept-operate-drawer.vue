<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { enableStatusOptions } from '@/constants/business';
import { addDept, fetchGetDeptTree, updateDept } from '@/service/api';
import type { DeptTreeOption } from '@/service/api';
import { useForm, useFormRules } from '@/hooks/common/form';
import { $t } from '@/locales';

defineOptions({ name: 'DeptOperateDrawer' });

interface Props {
  /** the type of operation */
  operateType: UI.TableOperateType;
  /** the edit row data */
  rowData?: Api.SystemManage.Department | null;
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
  const titles: Record<UI.TableOperateType, string> = {
    add: $t('page.manage.dept.addDept'),
    edit: $t('page.manage.dept.editDept')
  };
  return titles[props.operateType];
});

type Model = Pick<Api.SystemManage.Department, 'deptName' | 'deptCode' | 'parentId' | 'sort' | 'status'>;

const model = ref<Model>(createDefaultModel());

function createDefaultModel(): Model {
  return {
    deptName: '',
    deptCode: '',
    parentId: 0,
    sort: 0,
    status: '1'
  };
}

type RuleKey = Extract<keyof Model, 'deptName' | 'status'>;

const rules: Record<RuleKey, App.Global.FormRule> = {
  deptName: defaultRequiredRule,
  status: defaultRequiredRule
};

/** 上级部门树选项 */
const deptTreeOptions = ref<DeptTreeOption[]>([]);

async function getDeptTreeOptions() {
  const { error, data } = await fetchGetDeptTree();

  if (!error) {
    deptTreeOptions.value = data;
  }
}

/** 编辑时过滤掉当前部门自身，防止把上级设为自己 */
const selectableDeptTreeOptions = computed(() => {
  const excludeId = props.operateType === 'edit' ? props.rowData?.id : undefined;
  if (excludeId === undefined) {
    return deptTreeOptions.value;
  }

  function filterTree(nodes: DeptTreeOption[]): DeptTreeOption[] {
    return nodes
      .filter(node => node.id !== excludeId)
      .map(node => ({ ...node, children: node.children ? filterTree(node.children) : undefined }));
  }

  return filterTree(deptTreeOptions.value);
});

function handleInitModel() {
  model.value = createDefaultModel();

  if (props.operateType === 'edit' && props.rowData) {
    const { deptName, deptCode, parentId, sort, status } = props.rowData;
    Object.assign(model.value, { deptName, deptCode, parentId, sort, status });
  }
}

function closeDrawer() {
  visible.value = false;
}

async function handleSubmit() {
  await validate();

  const { error } =
    props.operateType === 'add' ? await addDept(model.value) : await updateDept(props.rowData!.id, model.value);

  if (!error) {
    window.$message?.success($t(props.operateType === 'add' ? 'common.addSuccess' : 'common.updateSuccess'));
    closeDrawer();
    emit('submitted');
  }
}

watch(visible, () => {
  if (visible.value) {
    handleInitModel();
    restoreValidation();
    getDeptTreeOptions();
  }
});
</script>

<template>
  <ElDrawer v-model="visible" :title="title" :size="360">
    <ElForm ref="formRef" :model="model" :rules="rules" label-position="top">
      <ElFormItem :label="$t('page.manage.dept.parentDept')" prop="parentId">
        <ElTreeSelect
          v-model="model.parentId"
          :data="selectableDeptTreeOptions"
          node-key="value"
          check-strictly
          clearable
          :render-after-expand="false"
          default-expand-all
          :placeholder="$t('page.manage.dept.form.parentDept')"
        />
      </ElFormItem>
      <ElFormItem :label="$t('page.manage.dept.deptName')" prop="deptName">
        <ElInput v-model="model.deptName" :placeholder="$t('page.manage.dept.form.deptName')" />
      </ElFormItem>
      <ElFormItem :label="$t('page.manage.dept.deptCode')" prop="deptCode">
        <ElInput v-model="model.deptCode" :placeholder="$t('page.manage.dept.form.deptCode')" />
      </ElFormItem>
      <ElFormItem :label="$t('page.manage.dept.sort')" prop="sort">
        <ElInputNumber v-model="model.sort" :min="0" :precision="0" />
      </ElFormItem>
      <ElFormItem :label="$t('page.manage.dept.deptStatus')" prop="status">
        <ElRadioGroup v-model="model.status">
          <ElRadio v-for="item in enableStatusOptions" :key="item.value" :value="item.value" :label="$t(item.label)" />
        </ElRadioGroup>
      </ElFormItem>
    </ElForm>
    <template #footer>
      <ElSpace :size="16">
        <ElButton @click="closeDrawer">{{ $t('common.cancel') }}</ElButton>
        <ElButton type="primary" @click="handleSubmit">{{ $t('common.confirm') }}</ElButton>
      </ElSpace>
    </template>
  </ElDrawer>
</template>

<style scoped></style>
