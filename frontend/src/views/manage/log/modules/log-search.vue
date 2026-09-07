<script setup lang="ts">
import { $t } from '@/locales';

defineOptions({ name: 'LogSearch' });

interface Emits {
  (e: 'reset'): void;
  (e: 'search'): void;
}

const emit = defineEmits<Emits>();

const model = defineModel<Api.SystemManage.OperationLogSearchParams>('model', { required: true });

function reset() {
  emit('reset');
}

function search() {
  emit('search');
}
</script>

<template>
  <ElCard class="card-wrapper">
    <ElCollapse>
      <ElCollapseItem :title="$t('common.search')" name="log-search">
        <ElForm :model="model" label-position="right" :label-width="80">
          <ElRow :gutter="24">
            <ElCol :lg="6" :md="8" :sm="12">
              <ElFormItem :label="$t('page.manage.log.keywords')" prop="keywords">
                <ElInput
                  v-model="model.keywords"
                  clearable
                  :placeholder="$t('page.manage.log.keywords')"
                  @keyup.enter="search"
                />
              </ElFormItem>
            </ElCol>
            <ElCol :lg="8" :md="8" :sm="12">
              <ElFormItem :label="$t('page.manage.log.createTime')" prop="createTime">
                <ElDatePicker
                  v-model="model.createTime"
                  type="daterange"
                  value-format="YYYY-MM-DD"
                  start-placeholder="YYYY-MM-DD"
                  end-placeholder="YYYY-MM-DD"
                />
              </ElFormItem>
            </ElCol>
            <ElCol :lg="10" :md="8" :sm="24">
              <ElSpace class="w-full justify-end" alignment="end">
                <ElButton @click="reset">
                  <template #icon>
                    <icon-ic-round-refresh class="text-icon" />
                  </template>
                  {{ $t('common.reset') }}
                </ElButton>
                <ElButton type="primary" plain @click="search">
                  <template #icon>
                    <icon-ic-round-search class="text-icon" />
                  </template>
                  {{ $t('common.search') }}
                </ElButton>
              </ElSpace>
            </ElCol>
          </ElRow>
        </ElForm>
      </ElCollapseItem>
    </ElCollapse>
  </ElCard>
</template>

<style scoped></style>
