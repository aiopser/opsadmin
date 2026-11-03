<script setup lang="ts">
import { computed, ref, shallowRef } from 'vue';
import { fetchDeleteAssetSource, fetchGetAssetSourceList, fetchTestCloudConnection } from '@/service/api';
import { defaultTransform, useUIPaginatedTable } from '@/hooks/common/table';
import { useAuth } from '@/hooks/business/auth';
import AccountOperateDrawer from './account-operate-drawer.vue';
import AccountSyncDialog from './account-sync-dialog.vue';
import SyncRecordDrawer from './sync-record-drawer.vue';

defineOptions({ name: 'CmdbCloudAccountList' });

const { hasAuth } = useAuth();

/** ============ 云厂商标识（品牌色仅用于徽标识别） ============ */

const providerLabels: Record<string, string> = {
  aliyun: '阿里云 ECS',
  tencent: '腾讯云 CVM',
  vmware: 'VMware vSphere',
  openstack: 'OpenStack',
  pve: 'Proxmox VE'
};

function providerLabel(provider: string): string {
  return providerLabels[provider] ?? '待确认厂商';
}

/** ============ 搜索与列表 ============ */

const searchParams = ref({
  current: 1,
  size: 10,
  search: undefined as string | undefined
});

const { data, getData, getDataByPage, loading, mobilePagination } = useUIPaginatedTable({
  paginationProps: {
    currentPage: searchParams.value.current,
    pageSize: searchParams.value.size
  },
  api: () => fetchGetAssetSourceList({ ...searchParams.value, sourceType: 'cloud' }),
  transform: response => defaultTransform(response),
  onPaginationParamsChange: params => {
    searchParams.value.current = params.currentPage ?? 1;
    searchParams.value.size = params.pageSize ?? 10;
  },
  columns: () => []
});

const emptyDescription = computed(() => (searchParams.value.search ? '未找到匹配的云账号' : '暂无云账号'));
const accountGroups = computed(() => [
  {
    key: 'public',
    title: '公有云',
    accounts: data.value.filter(item => item.cloud_provider === 'aliyun' || item.cloud_provider === 'tencent')
  },
  {
    key: 'private',
    title: '私有云',
    accounts: data.value.filter(item => ['vmware', 'openstack', 'pve'].includes(item.cloud_provider))
  }
]);

/** ============ 新增 / 编辑 / 删除 ============ */

const operateDrawerRef = ref<InstanceType<typeof AccountOperateDrawer>>();
const syncDialogRef = ref<InstanceType<typeof AccountSyncDialog>>();
const recordDrawerRef = ref<InstanceType<typeof SyncRecordDrawer>>();

function openCreate() {
  operateDrawerRef.value?.open('add');
}

function openEdit(row: Api.Cmdb.AssetSourceRecord) {
  operateDrawerRef.value?.open('edit', row);
}

async function handleDelete(id: number) {
  const { error } = await fetchDeleteAssetSource(id);
  if (!error) {
    window.$notification?.success('删除成功');
    getData();
  }
}

/** ============ 同步与跳转 ============ */

function openSync(row: Api.Cmdb.AssetSourceRecord) {
  syncDialogRef.value?.open(row);
}

/** 同步提交成功后打开该账号的同步记录抽屉，形成操作闭环 */
function handleSynced(sourceId: number) {
  const account = data.value.find(item => item.id === sourceId);
  recordDrawerRef.value?.open(sourceId, account?.name);
}

function openRecords(row: Api.Cmdb.AssetSourceRecord) {
  recordDrawerRef.value?.open(row.id, row.name);
}

/** ============ 卡片快捷连接测试（复用已保存凭据，仅公有云） ============ */

interface AccountTestOutcome {
  results: Api.Cmdb.CloudConnectionResult[];
  untestedCount: number;
}

const testingAccountId = ref<number | null>(null);
const testOutcomes = shallowRef<Record<number, AccountTestOutcome>>({});

function canTestAccount(account: Api.Cmdb.AssetSourceRecord): boolean {
  return (
    ['aliyun', 'tencent'].includes(account.cloud_provider) && account.has_credentials && account.regions.length > 0
  );
}

function outcomeOf(accountId: number): AccountTestOutcome | undefined {
  return testOutcomes.value[accountId];
}

async function handleTestAccount(account: Api.Cmdb.AssetSourceRecord) {
  testingAccountId.value = account.id;
  try {
    const { data: outcome, error } = await fetchTestCloudConnection({
      code: account.code,
      name: account.name,
      source_type: 'cloud',
      cloud_provider: account.cloud_provider,
      regions: account.regions,
      source_id: account.id,
      test_regions: account.regions.slice(0, 5)
    });
    if (error || !outcome) return;
    testOutcomes.value = {
      ...testOutcomes.value,
      [account.id]: { results: outcome.results, untestedCount: outcome.untestedRegions?.length ?? 0 }
    };
  } finally {
    testingAccountId.value = null;
  }
}

function resetSearch() {
  searchParams.value.search = undefined;
  getDataByPage();
}

function handleRecordsUpdated() {
  getData();
}
</script>

<template>
  <div class="flex-col-stretch gap-12px">
    <SearchPanel @reset="resetSearch" @search="getDataByPage">
      <ElForm :model="searchParams" label-width="80px" @submit.prevent="getDataByPage">
        <ElFormItem label="关键词">
          <ElInput
            v-model="searchParams.search"
            clearable
            placeholder="账号名称或编码"
            @keyup.enter="getDataByPage()"
            @clear="getDataByPage()"
          />
        </ElFormItem>
      </ElForm>
    </SearchPanel>

    <ElCard class="card-wrapper">
      <template #header>
        <div class="flex flex-wrap items-center justify-end gap-8px [&>.el-button+.el-button]:!ml-0">
          <ElButton :loading="loading" @click="getData">刷新</ElButton>
          <ElButton v-if="hasAuth('cmdb.asset_source:create')" type="primary" @click="openCreate">新增云账号</ElButton>
        </div>
      </template>

      <div v-loading="loading" class="min-h-240px">
        <ElEmpty v-if="!loading && !data.length" :description="emptyDescription">
          <ElButton v-if="hasAuth('cmdb.asset_source:create')" type="primary" @click="openCreate">新增云账号</ElButton>
        </ElEmpty>
        <div v-else-if="data.length" class="flex flex-col gap-20px">
          <section v-for="group in accountGroups" :key="group.key">
            <p class="mb-10px text-14px font-medium">{{ group.title }}</p>
            <div v-if="group.accounts.length" class="grid grid-cols-1 gap-12px 2xl:grid-cols-3 md:grid-cols-2">
              <ElCard v-for="account in group.accounts" :key="account.id" shadow="never" class="min-w-0">
                <div class="flex items-center justify-between gap-8px">
                  <div class="min-w-0 flex items-center gap-12px">
                    <div
                      class="h-40px w-40px flex shrink-0 items-center justify-center rounded-6px bg-[var(--el-fill-color-light)]"
                    >
                      <icon-local-aliyun v-if="account.cloud_provider === 'aliyun'" class="text-24px" />
                      <icon-local-tencent-cloud v-else-if="account.cloud_provider === 'tencent'" class="text-24px" />
                      <icon-local-vmware v-else-if="account.cloud_provider === 'vmware'" class="text-24px" />
                      <icon-local-openstack v-else-if="account.cloud_provider === 'openstack'" class="text-24px" />
                      <icon-local-proxmox-ve v-else-if="account.cloud_provider === 'pve'" class="text-24px" />
                      <icon-mdi-cloud-outline v-else class="text-24px text-[var(--el-text-color-secondary)]" />
                    </div>
                    <div class="min-w-0">
                      <p class="truncate text-15px font-medium">{{ account.name }}</p>
                      <p class="mt-2px truncate text-12px text-[var(--el-text-color-secondary)] font-mono">
                        {{ account.code }}
                      </p>
                    </div>
                  </div>
                  <ElTag size="small" :type="account.is_active ? 'success' : 'info'">
                    {{ account.is_active ? '启用' : '停用' }}
                  </ElTag>
                </div>

                <div class="mt-12px flex flex-col gap-6px text-13px">
                  <div class="flex items-center gap-8px">
                    <span class="w-64px shrink-0 text-[var(--el-text-color-secondary)]">云厂商</span>
                    <span class="min-w-0 flex-1 truncate">{{ providerLabel(account.cloud_provider) }}</span>
                  </div>
                  <div class="flex items-center gap-8px">
                    <span class="w-64px shrink-0 text-[var(--el-text-color-secondary)]">只读凭据</span>
                    <ElTag size="small" :type="account.has_credentials ? 'success' : 'warning'">
                      {{ account.has_credentials ? '已配置' : '未配置' }}
                    </ElTag>
                  </div>
                  <div v-if="account.regions.length" class="flex items-start gap-8px">
                    <span class="w-64px shrink-0 text-[var(--el-text-color-secondary)]">同步区域</span>
                    <span
                      class="min-w-0 flex-1 truncate text-12px leading-22px font-mono"
                      :title="account.regions.join('、')"
                    >
                      {{ account.regions.join('、') }}
                    </span>
                  </div>
                  <div v-else class="flex items-start gap-8px">
                    <span class="w-64px shrink-0 text-[var(--el-text-color-secondary)]">接入地址</span>
                    <span class="min-w-0 flex-1 truncate text-12px leading-22px font-mono" :title="account.endpoint">
                      {{ account.endpoint || '未配置' }}
                    </span>
                  </div>
                  <div class="flex items-start gap-8px">
                    <span class="w-64px shrink-0 text-[var(--el-text-color-secondary)]">最近同步</span>
                    <span class="min-w-0 flex-1 truncate">{{ account.last_synced_at || '尚未同步' }}</span>
                  </div>
                  <div class="flex items-start gap-8px">
                    <span class="w-64px shrink-0 text-[var(--el-text-color-secondary)]">周期同步</span>
                    <span>
                      {{ account.sync_interval_minutes ? `每 ${account.sync_interval_minutes} 分钟` : '未开启' }}
                    </span>
                  </div>
                  <div v-if="account.capabilities" class="flex items-start gap-8px">
                    <span class="w-64px shrink-0 text-[var(--el-text-color-secondary)]">采集能力</span>
                    <ElTooltip
                      placement="top"
                      :content="`${account.capabilities.fields.join('、')}。${account.capabilities.scope}；单次最多 ${account.capabilities.maxAssets} 台。`"
                    >
                      <span tabindex="0" class="cursor-help">支持 {{ account.capabilities.fields.length }} 项字段</span>
                    </ElTooltip>
                  </div>
                  <div v-if="outcomeOf(account.id)" class="flex items-start gap-8px">
                    <span class="w-64px shrink-0 text-[var(--el-text-color-secondary)]">连接测试</span>
                    <div class="min-w-0 flex flex-1 flex-wrap items-center gap-4px">
                      <ElTooltip
                        v-for="result in outcomeOf(account.id)?.results ?? []"
                        :key="result.region"
                        placement="top"
                        :content="result.message"
                      >
                        <ElTag size="small" :type="result.success ? 'success' : 'danger'">
                          {{ result.region }} {{ result.success ? '通过' : '失败' }}
                        </ElTag>
                      </ElTooltip>
                      <span
                        v-if="(outcomeOf(account.id)?.untestedCount ?? 0) > 0"
                        class="text-12px text-[var(--el-text-color-secondary)]"
                      >
                        另有 {{ outcomeOf(account.id)?.untestedCount }} 个区域未测
                      </span>
                    </div>
                  </div>
                </div>

                <div
                  class="mt-12px flex flex-wrap items-center gap-8px border-t border-[var(--el-border-color-lighter)] border-solid pt-12px [&>.el-button+.el-button]:!ml-0"
                >
                  <ElButton
                    v-if="hasAuth('cmdb.asset_source:sync')"
                    size="small"
                    type="primary"
                    plain
                    :disabled="!account.is_active || !account.has_credentials"
                    @click="openSync(account)"
                  >
                    同步云主机
                  </ElButton>
                  <ElButton type="primary" plain size="small" @click="openRecords(account)">同步记录</ElButton>
                  <ElButton
                    v-if="canTestAccount(account)"
                    type="primary"
                    plain
                    size="small"
                    :loading="testingAccountId === account.id"
                    @click="handleTestAccount(account)"
                  >
                    测试连接
                  </ElButton>
                  <ElButton
                    v-if="hasAuth('cmdb.asset_source:update')"
                    type="primary"
                    plain
                    size="small"
                    @click="openEdit(account)"
                  >
                    编辑
                  </ElButton>
                  <ElPopconfirm
                    v-if="hasAuth('cmdb.asset_source:delete')"
                    title="确认删除该云账号？已有同步记录关联时将无法删除"
                    @confirm="handleDelete(account.id)"
                  >
                    <template #reference>
                      <ElButton size="small" type="danger" plain>删除</ElButton>
                    </template>
                  </ElPopconfirm>
                </div>
              </ElCard>
            </div>
            <p v-else class="text-13px text-[var(--el-text-color-regular)]">暂无{{ group.title }}账号</p>
          </section>
        </div>
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

    <AccountOperateDrawer ref="operateDrawerRef" @submitted="getData" />
    <AccountSyncDialog ref="syncDialogRef" @synced="handleSynced" />
    <SyncRecordDrawer ref="recordDrawerRef" @updated="handleRecordsUpdated" />
  </div>
</template>
