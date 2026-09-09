<script setup lang="tsx">
import { computed, onMounted, reactive, ref, shallowRef } from 'vue';
import { useRouter } from 'vue-router';
import type { FormInstance } from 'element-plus';
import { fetchCreateQuickCommandRun, fetchGetHostOptions, fetchGetWorkerPools } from '@/service/api';
import { useAuth } from '@/hooks/business/auth';
import { $t } from '@/locales';

defineOptions({ name: 'OpsQuickExecute' });

const router = useRouter();
const { hasAuth } = useAuth();

type CommandType = 'linux_shell' | 'windows_powershell';

const commandTypeOptions: { value: CommandType; label: string; osFamily: string }[] = [
  { value: 'linux_shell', label: 'Linux Shell', osFamily: 'linux' },
  { value: 'windows_powershell', label: 'Windows PowerShell', osFamily: 'windows' }
];

const form = reactive({
  commandType: 'linux_shell' as CommandType,
  commandContent: '',
  hostIds: [] as number[],
  workerPoolId: null as number | null
});

const formRules = {
  commandContent: [
    { required: true, message: $t('page.ops.quickExecute.form.commandContentRequired'), trigger: 'blur' }
  ],
  hostIds: [{ required: true, message: $t('page.ops.quickExecute.form.hostIdsRequired'), trigger: 'change' }]
};

const formRef = shallowRef<FormInstance>();
const submitting = ref(false);

/** 命令类型对应的 OS family（后端同规则校验） */
const expectedOsFamily = computed(
  () => commandTypeOptions.find(item => item.value === form.commandType)?.osFamily ?? 'linux'
);

/** ============ 主机选择 ============ */

const hostOptions = ref<Api.Jobs.HostOption[]>([]);
const hostOptionsLoading = ref(false);
const hostKeyword = ref('');

async function loadHosts() {
  hostOptionsLoading.value = true;
  try {
    const { data, error } = await fetchGetHostOptions(hostKeyword.value || undefined);
    if (!error && data) {
      hostOptions.value = data.list;
    }
  } finally {
    hostOptionsLoading.value = false;
  }
}

/** 按命令类型过滤 OS family；切换类型时清掉不匹配的选择 */
const filteredHostOptions = computed(() =>
  hostOptions.value.filter(host => (host.osFamily ?? '').toLowerCase() === expectedOsFamily.value)
);

function onCommandTypeChange() {
  const valid = new Set(filteredHostOptions.value.map(host => host.id));
  form.hostIds = form.hostIds.filter(id => valid.has(id));
}

/** ============ Worker 池 ============ */

const workerPools = ref<Api.Jobs.WorkerPoolOption[]>([]);

async function loadWorkerPools() {
  const { data, error } = await fetchGetWorkerPools();
  if (!error && data) {
    workerPools.value = data.list.filter(pool => pool.isActive);
    const defaultPool = workerPools.value.find(pool => pool.isDefault);
    if (defaultPool) {
      form.workerPoolId = defaultPool.id;
    }
  }
}

/** ============ 提交 ============ */

async function onSubmit() {
  if (!hasAuth('jobs.quick_command:execute')) return;
  const valid = await formRef.value?.validate().catch(() => false);
  if (!valid) return;

  submitting.value = true;
  try {
    const { data, error } = await fetchCreateQuickCommandRun({
      commandType: form.commandType,
      commandContent: form.commandContent,
      hostIds: form.hostIds,
      workerPoolId: form.workerPoolId
    });
    if (!error && data) {
      window.$message?.success($t('page.ops.quickExecute.submitted'));
      router.push({ name: 'task_run-detail', params: { id: data.id }, query: { domain: 'ops' } });
    }
  } finally {
    submitting.value = false;
  }
}

function onReset() {
  formRef.value?.resetFields();
  form.commandContent = '';
  form.hostIds = [];
}

onMounted(() => {
  loadHosts();
  loadWorkerPools();
});
</script>

<template>
  <div class="min-h-500px flex-col-stretch gap-16px overflow-hidden lt-sm:overflow-auto">
    <ElCard class="card-wrapper">
      <p class="mb-16px text-16px font-bold">{{ $t('page.ops.quickExecute.title') }}</p>
      <ElForm ref="formRef" :model="form" :rules="formRules" label-width="100px" class="max-w-760px">
        <ElFormItem :label="$t('page.ops.quickExecute.commandType')">
          <ElRadioGroup v-model="form.commandType" @change="onCommandTypeChange">
            <ElRadioButton v-for="item in commandTypeOptions" :key="item.value" :value="item.value">
              {{ item.label }}
            </ElRadioButton>
          </ElRadioGroup>
        </ElFormItem>
        <ElFormItem :label="$t('page.ops.quickExecute.commandContent')" prop="commandContent">
          <ElInput
            v-model="form.commandContent"
            type="textarea"
            :rows="6"
            class="font-mono"
            :placeholder="$t('page.ops.quickExecute.form.commandContentPlaceholder')"
          />
        </ElFormItem>
        <ElFormItem :label="$t('page.ops.quickExecute.hosts')" prop="hostIds">
          <div class="w-full flex-col gap-8px">
            <ElSelect
              v-model="form.hostIds"
              multiple
              filterable
              clearable
              :loading="hostOptionsLoading"
              :placeholder="$t('page.ops.quickExecute.form.hostsPlaceholder')"
              class="w-full"
            >
              <ElOption
                v-for="host in filteredHostOptions"
                :key="host.id"
                :label="`${host.hostname} (${host.primaryIp})`"
                :value="host.id"
              />
            </ElSelect>
            <div class="flex items-center gap-8px">
              <ElInput
                v-model="hostKeyword"
                clearable
                :placeholder="$t('common.keywordSearch')"
                class="w-200px"
                @keyup.enter="loadHosts()"
              />
              <ElButton @click="loadHosts()">
                {{ $t('common.search') }}
              </ElButton>
            </div>
          </div>
        </ElFormItem>
        <ElFormItem :label="$t('page.ops.quickExecute.workerPool')">
          <ElSelect
            v-model="form.workerPoolId"
            clearable
            :placeholder="$t('page.ops.quickExecute.form.workerPoolPlaceholder')"
            class="w-280px"
          >
            <ElOption
              v-for="pool in workerPools"
              :key="pool.id"
              :label="`${pool.name}${pool.isDefault ? '（默认）' : ''}`"
              :value="pool.id"
            />
          </ElSelect>
        </ElFormItem>
        <ElFormItem>
          <ElButton
            type="primary"
            :loading="submitting"
            :disabled="!hasAuth('jobs.quick_command:execute')"
            @click="onSubmit"
          >
            {{ $t('page.ops.quickExecute.submit') }}
          </ElButton>
          <ElButton @click="onReset">
            {{ $t('common.reset') }}
          </ElButton>
        </ElFormItem>
      </ElForm>
    </ElCard>
  </div>
</template>

<style scoped></style>
