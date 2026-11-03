<script setup lang="tsx">
import { computed, ref, watch } from 'vue';
import { enableStatusRecord } from '@/constants/business';
import { addDictItem, deleteDictItem, fetchGetDictItemList, updateDictItem } from '@/service/api';
import { defaultTransform, useUIPaginatedTable } from '@/hooks/common/table';
import { useForm, useFormRules } from '@/hooks/common/form';
import { $t } from '@/locales';

defineOptions({ name: 'DictItemModal' });

interface Props {
  /** 当前查看字典项的字典类型 */
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

const dictCode = computed(() => props.rowData?.dictCode ?? '');

const itemSearchParams = ref<Api.SystemManage.DictItemSearchParams>({
  current: 1,
  size: 10,
  label: undefined,
  status: undefined
});

const { columns, data, getData, getDataByPage, loading, mobilePagination } = useUIPaginatedTable({
  paginationProps: {
    currentPage: itemSearchParams.value.current,
    pageSize: itemSearchParams.value.size
  },
  api: () => fetchGetDictItemList(dictCode.value, itemSearchParams.value),
  transform: response => defaultTransform(response),
  onPaginationParamsChange: params => {
    itemSearchParams.value.current = params.currentPage;
    itemSearchParams.value.size = params.pageSize;
  },
  columns: () => [
    { prop: 'index', type: 'index', label: $t('common.index'), width: 64 },
    { prop: 'label', label: $t('page.manage.dict.itemLabel'), minWidth: 120 },
    { prop: 'value', label: $t('page.manage.dict.itemValue'), minWidth: 120 },
    { prop: 'sort', label: $t('page.manage.dict.itemSort'), width: 80, align: 'center' },
    {
      prop: 'status',
      label: $t('page.manage.dict.dictStatus'),
      width: 90,
      align: 'center',
      formatter: row => {
        if (row.status === undefined) {
          return '';
        }

        const tagMap: Record<Api.Common.EnableStatus, UI.ThemeColor> = {
          1: 'success',
          2: 'warning'
        };

        return <ElTag type={tagMap[row.status]}>{$t(enableStatusRecord[row.status])}</ElTag>;
      }
    },
    {
      prop: 'operate',
      label: $t('common.operate'),
      align: 'center',
      width: 120,
      fixed: 'right',
      formatter: row => (
        <div class="flex-center">
          <ElButton type="primary" plain size="small" onClick={() => handleEditItem(row)}>
            {$t('common.edit')}
          </ElButton>
          <ElPopconfirm title={$t('common.confirmDelete')} onConfirm={() => handleDeleteItem(row.id)}>
            {{
              reference: () => (
                <ElButton type="danger" plain size="small">
                  {$t('common.delete')}
                </ElButton>
              )
            }}
          </ElPopconfirm>
        </div>
      )
    }
  ]
});

const itemFormVisible = ref(false);

const itemOperateType = ref<UI.TableOperateType>('add');

const editingItemId = ref<number | null>(null);

const { formRef, validate } = useForm();
const { defaultRequiredRule } = useFormRules();

type ItemModel = Pick<Api.SystemManage.DictItemModel, 'label' | 'value' | 'sort' | 'tagType' | 'status'>;

const itemModel = ref<ItemModel>(createDefaultItemModel());

function createDefaultItemModel(): ItemModel {
  return {
    label: '',
    value: '',
    sort: 0,
    tagType: '',
    status: '1'
  };
}

const itemRules: Record<'label' | 'value', App.Global.FormRule> = {
  label: defaultRequiredRule,
  value: defaultRequiredRule
};

const tagTypeOptions = ['primary', 'success', 'warning', 'danger', 'info'];

const itemFormTitle = computed(() =>
  $t(itemOperateType.value === 'add' ? 'page.manage.dict.addItem' : 'page.manage.dict.editItem')
);

function handleAddItem() {
  itemOperateType.value = 'add';
  editingItemId.value = null;
  itemModel.value = createDefaultItemModel();
  itemFormVisible.value = true;
}

function handleEditItem(row: Api.SystemManage.DictItem) {
  itemOperateType.value = 'edit';
  editingItemId.value = row.id;
  itemModel.value = { label: row.label, value: row.value, sort: row.sort, tagType: row.tagType, status: row.status };
  itemFormVisible.value = true;
}

async function handleSubmitItem() {
  await validate();

  const { error } =
    itemOperateType.value === 'add'
      ? await addDictItem(dictCode.value, itemModel.value)
      : await updateDictItem(dictCode.value, editingItemId.value!, itemModel.value);

  if (!error) {
    window.$notification?.success($t(itemOperateType.value === 'add' ? 'common.addSuccess' : 'common.updateSuccess'));
    itemFormVisible.value = false;
    getDataByPage();
    emit('submitted');
  }
}

async function handleDeleteItem(id: number) {
  const { error } = await deleteDictItem(dictCode.value, id);

  if (!error) {
    window.$notification?.success($t('common.deleteSuccess'));
    getDataByPage();
  }
}

watch(visible, val => {
  if (val && dictCode.value) {
    itemSearchParams.value.current = 1;
    getData();
  }
});
</script>

<template>
  <ElDialog
    v-model="visible"
    :title="`${$t('page.manage.dict.dictItems')} - ${props.rowData?.dictName ?? ''}`"
    width="800px"
  >
    <div class="flex-y-center justify-between pb-12px">
      <span>{{ dictCode }}</span>
      <ElButton type="primary" @click="handleAddItem">{{ $t('common.add') }}</ElButton>
    </div>
    <ElTable v-loading="loading" border :data="data" row-key="id">
      <ElTableColumn v-for="col in columns" :key="col.prop" v-bind="col" />
    </ElTable>
    <div class="mt-12px flex justify-end">
      <ElPagination
        v-if="mobilePagination.total"
        layout="total,prev,pager,next"
        v-bind="mobilePagination"
        @current-change="mobilePagination['current-change']"
        @size-change="mobilePagination['size-change']"
      />
    </div>

    <ElDialog v-model="itemFormVisible" :title="itemFormTitle" width="420px" append-to-body>
      <ElForm
        ref="formRef"
        :model="itemModel"
        :rules="itemRules"
        label-position="top"
        label-suffix="："
        require-asterisk-position="left"
      >
        <ElFormItem :label="$t('page.manage.dict.itemLabel')" prop="label">
          <ElInput v-model="itemModel.label" :placeholder="$t('page.manage.dict.form.itemLabel')" />
        </ElFormItem>
        <ElFormItem prop="value">
          <template #label>
            <FormLabelHelp
              :label="$t('page.manage.dict.itemValue')"
              :help="['字典项的存储值，程序按此值取数；', '同一字典下不可重复。']"
            />
          </template>
          <ElInput v-model="itemModel.value" :placeholder="$t('page.manage.dict.form.itemValue')" />
        </ElFormItem>
        <ElFormItem :label="$t('page.manage.dict.itemSort')" prop="sort">
          <ElInputNumber v-model="itemModel.sort" :min="0" :precision="0" />
        </ElFormItem>
        <ElFormItem :label="$t('page.manage.dict.itemTagType')" prop="tagType">
          <ElSelect v-model="itemModel.tagType" clearable :placeholder="$t('page.manage.dict.form.itemTagType')">
            <ElOption v-for="tag in tagTypeOptions" :key="tag" :label="tag" :value="tag" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem :label="$t('page.manage.dict.dictStatus')" prop="status">
          <ElRadioGroup v-model="itemModel.status">
            <ElRadio value="1" :label="$t(enableStatusRecord['1'])" />
            <ElRadio value="2" :label="$t(enableStatusRecord['2'])" />
          </ElRadioGroup>
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElSpace :size="16">
          <ElButton @click="itemFormVisible = false">{{ $t('common.cancel') }}</ElButton>
          <ElButton type="primary" @click="handleSubmitItem">{{ $t('common.confirm') }}</ElButton>
        </ElSpace>
      </template>
    </ElDialog>
  </ElDialog>
</template>

<style scoped></style>
