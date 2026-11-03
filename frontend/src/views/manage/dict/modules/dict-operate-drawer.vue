<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { enableStatusOptions } from '@/constants/business';
import { addDict, updateDict } from '@/service/api';
import { useForm, useFormRules } from '@/hooks/common/form';
import { $t } from '@/locales';

defineOptions({ name: 'DictOperateDrawer' });

interface Props {
  /** the type of operation */
  operateType: UI.TableOperateType;
  /** the edit row data */
  rowData?: Api.SystemManage.DictType | null;
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
    add: $t('page.manage.dict.addDictType'),
    edit: $t('page.manage.dict.editDictType')
  };
  return titles[props.operateType];
});

type Model = Pick<Api.SystemManage.DictTypeModel, 'dictName' | 'dictCode' | 'remark' | 'status'>;

const model = ref<Model>(createDefaultModel());

function createDefaultModel(): Model {
  return {
    dictName: '',
    dictCode: '',
    remark: null,
    status: '1'
  };
}

type RuleKey = Extract<keyof Model, 'dictName' | 'dictCode'>;

const rules: Record<RuleKey, App.Global.FormRule> = {
  dictName: defaultRequiredRule,
  dictCode: defaultRequiredRule
};

function handleInitModel() {
  model.value = createDefaultModel();

  if (props.operateType === 'edit' && props.rowData) {
    const { dictName, dictCode, remark, status } = props.rowData;
    Object.assign(model.value, { dictName, dictCode, remark, status });
  }
}

function closeDrawer() {
  visible.value = false;
}

async function handleSubmit() {
  await validate();

  const { error } =
    props.operateType === 'add' ? await addDict(model.value) : await updateDict(props.rowData!.id, model.value);

  if (!error) {
    window.$notification?.success($t(props.operateType === 'add' ? 'common.addSuccess' : 'common.updateSuccess'));
    closeDrawer();
    emit('submitted');
  }
}

watch(visible, () => {
  if (visible.value) {
    handleInitModel();
    restoreValidation();
  }
});
</script>

<template>
  <ElDrawer v-model="visible" :title="title" :size="360">
    <ElForm
      ref="formRef"
      :model="model"
      :rules="rules"
      label-position="top"
      label-suffix="："
      require-asterisk-position="left"
    >
      <ElFormItem :label="$t('page.manage.dict.dictName')" prop="dictName">
        <ElInput v-model="model.dictName" :placeholder="$t('page.manage.dict.form.dictName')" />
      </ElFormItem>
      <ElFormItem prop="dictCode">
        <template #label>
          <FormLabelHelp
            :label="$t('page.manage.dict.dictCode')"
            :help="['字典编码，全局唯一，创建后不可修改；', '程序按此编码获取对应字典项（如 gender）。']"
          />
        </template>
        <ElInput
          v-model="model.dictCode"
          :disabled="props.operateType === 'edit'"
          :placeholder="$t('page.manage.dict.form.dictCode')"
        />
      </ElFormItem>
      <ElFormItem :label="$t('page.manage.dict.dictStatus')" prop="status">
        <ElRadioGroup v-model="model.status">
          <ElRadio v-for="item in enableStatusOptions" :key="item.value" :value="item.value" :label="$t(item.label)" />
        </ElRadioGroup>
      </ElFormItem>
      <ElFormItem :label="$t('page.manage.dict.remark')" prop="remark">
        <ElInput v-model="model.remark" type="textarea" :rows="3" :placeholder="$t('page.manage.dict.form.remark')" />
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
