<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { enableStatusOptions } from '@/constants/business';
import { addConfig, updateConfig } from '@/service/api';
import { useForm, useFormRules } from '@/hooks/common/form';
import { $t } from '@/locales';

defineOptions({ name: 'ConfigOperateDrawer' });

interface Props {
  /** the type of operation */
  operateType: UI.TableOperateType;
  /** the edit row data */
  rowData?: Api.SystemManage.SystemConfig | null;
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
    add: $t('page.manage.config.addConfig'),
    edit: $t('page.manage.config.editConfig')
  };
  return titles[props.operateType];
});

type Model = Pick<
  Api.SystemManage.SystemConfigModel,
  'configName' | 'configKey' | 'configValue' | 'configGroup' | 'remark' | 'status'
>;

const model = ref<Model>(createDefaultModel());

function createDefaultModel(): Model {
  return {
    configName: '',
    configKey: '',
    configValue: null,
    configGroup: '',
    remark: null,
    status: '1'
  };
}

type RuleKey = Extract<keyof Model, 'configName' | 'configKey'>;

const rules: Record<RuleKey, App.Global.FormRule> = {
  configName: defaultRequiredRule,
  configKey: defaultRequiredRule
};

function handleInitModel() {
  model.value = createDefaultModel();

  if (props.operateType === 'edit' && props.rowData) {
    const { configName, configKey, configValue, configGroup, remark, status } = props.rowData;
    Object.assign(model.value, { configName, configKey, configValue, configGroup, remark, status });
  }
}

function closeDrawer() {
  visible.value = false;
}

async function handleSubmit() {
  await validate();

  const { error } =
    props.operateType === 'add' ? await addConfig(model.value) : await updateConfig(props.rowData!.id, model.value);

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
  }
});
</script>

<template>
  <ElDrawer v-model="visible" :title="title" :size="360">
    <ElForm ref="formRef" :model="model" :rules="rules" label-position="top">
      <ElFormItem :label="$t('page.manage.config.configName')" prop="configName">
        <ElInput v-model="model.configName" :placeholder="$t('page.manage.config.form.configName')" />
      </ElFormItem>
      <ElFormItem :label="$t('page.manage.config.configKey')" prop="configKey">
        <ElInput
          v-model="model.configKey"
          :disabled="props.operateType === 'edit'"
          :placeholder="$t('page.manage.config.form.configKey')"
        />
      </ElFormItem>
      <ElFormItem :label="$t('page.manage.config.configValue')" prop="configValue">
        <ElInput
          v-model="model.configValue"
          type="textarea"
          :rows="3"
          :placeholder="$t('page.manage.config.form.configValue')"
        />
      </ElFormItem>
      <ElFormItem :label="$t('page.manage.config.configGroup')" prop="configGroup">
        <ElInput v-model="model.configGroup" :placeholder="$t('page.manage.config.form.configGroup')" />
      </ElFormItem>
      <ElFormItem :label="$t('page.manage.config.configStatus')" prop="status">
        <ElRadioGroup v-model="model.status">
          <ElRadio v-for="item in enableStatusOptions" :key="item.value" :value="item.value" :label="$t(item.label)" />
        </ElRadioGroup>
      </ElFormItem>
      <ElFormItem :label="$t('page.manage.config.remark')" prop="remark">
        <ElInput v-model="model.remark" type="textarea" :rows="2" :placeholder="$t('page.manage.config.form.remark')" />
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
