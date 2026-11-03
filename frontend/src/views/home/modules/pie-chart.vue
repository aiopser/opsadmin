<script setup lang="ts">
import { ref, watch } from 'vue';
import { fetchGetDashboardExecutionDistribution } from '@/service/api';
import { useAppStore } from '@/store/modules/app';
import { useEcharts } from '@/hooks/common/echarts';
import { $t } from '@/locales';

defineOptions({ name: 'ExecutionDistributionChart' });

const appStore = useAppStore();
const distribution = ref<Api.Jobs.DashboardExecutionDistribution | null>(null);
const loading = ref(false);

const categoryLabel: Record<Api.Jobs.DashboardExecutionCategory, App.I18n.I18nKey> = {
  ops_script: 'page.home.executionDistribution.opsScript',
  ops_playbook: 'page.home.executionDistribution.opsPlaybook',
  ops_module: 'page.home.executionDistribution.opsModule',
  ops_other: 'page.home.executionDistribution.opsOther',
  task_scheduled: 'page.home.executionDistribution.taskScheduled',
  task_workflow: 'page.home.executionDistribution.taskWorkflow'
};

const { domRef, updateOptions } = useEcharts(() => ({
  tooltip: { trigger: 'item' },
  legend: {
    orient: 'vertical',
    left: 'left',
    top: 'center',
    itemGap: 12,
    textStyle: { width: 112, overflow: 'truncate' },
    itemStyle: { borderWidth: 0 }
  },
  title: {
    show: false
  },
  series: [
    {
      color: ['#5da8ff', '#8e9dff', '#fedc69', '#26deca', '#ff9f7f', '#a3d977'],
      name: $t('page.home.executionDistribution.title'),
      type: 'pie',
      center: ['70%', '50%'],
      radius: ['38%', '66%'],
      avoidLabelOverlap: false,
      itemStyle: {
        borderRadius: 10,
        borderColor: '#fff',
        borderWidth: 1
      },
      label: {
        show: false,
        position: 'center'
      },
      emphasis: {
        label: {
          show: true,
          fontSize: '12'
        }
      },
      labelLine: { show: false },
      data: [] as { name: string; value: number }[]
    }
  ]
}));

function renderChart() {
  updateOptions((options, factory) => {
    const baseOptions = factory();
    options.series[0].name = baseOptions.series[0].name;
    options.series[0].data = (distribution.value?.items ?? []).map(item => ({
      name: $t(categoryLabel[item.key]),
      value: item.count
    }));
    return options;
  });
}

async function loadDistribution() {
  loading.value = true;
  try {
    const { data, error } = await fetchGetDashboardExecutionDistribution();
    if (error || !data) {
      if (error) window.$message?.error($t('page.home.executionDistribution.loadError'));
      return;
    }
    distribution.value = data;
    renderChart();
  } finally {
    loading.value = false;
  }
}

function updateLocale() {
  renderChart();
}

watch(() => appStore.locale, updateLocale);

loadDistribution();
</script>

<template>
  <ElCard v-loading="loading" class="card-wrapper">
    <template #header>
      <div class="flex items-center justify-between gap-8px">
        <span>{{ $t('page.home.executionDistribution.title') }}</span>
        <span class="text-12px text-gray-500">
          {{ $t('page.home.executionDistribution.period', { days: distribution?.periodDays ?? 30 }) }}
          · {{ $t('page.home.executionDistribution.total', { total: distribution?.total ?? 0 }) }}
        </span>
      </div>
    </template>
    <div ref="domRef" class="h-320px min-h-320px overflow-hidden"></div>
  </ElCard>
</template>

<style scoped></style>
