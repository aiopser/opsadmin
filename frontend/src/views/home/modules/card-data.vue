<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { createReusableTemplate } from '@vueuse/core';
import { fetchGetDashboardHealth, fetchGetDashboardStats } from '@/service/api';
import { $t } from '@/locales';

defineOptions({ name: 'CardData' });

interface CardData {
  key: string;
  title: string;
  value: number | null;
  unit: '%' | ' 次' | '';
  color: {
    start: string;
    end: string;
  };
  icon: string;
}

const dashboardStats = ref<Api.Jobs.DashboardStats | null>(null);
const dashboardHealth = ref<Api.Jobs.DashboardHealth | null>(null);

const cardData = computed<CardData[]>(() => [
  {
    key: 'jobExecutions',
    title: $t('page.home.todayJobExecutions'),
    value: dashboardStats.value?.todayExecutions ?? null,
    unit: ' 次',
    color: {
      start: '#ec4786',
      end: '#b955a4'
    },
    icon: 'mdi:script-text-outline'
  },
  {
    key: 'jobSuccessRate',
    title: $t('page.home.todayJobSuccessRate'),
    value: dashboardStats.value?.successRate ?? null,
    unit: '%',
    color: {
      start: '#865ec0',
      end: '#5144b4'
    },
    icon: 'mdi:check-decagram-outline'
  },
  {
    key: 'taskExecutions',
    title: $t('page.home.sevenDayTaskExecutions'),
    value: dashboardHealth.value?.sevenDay.total ?? null,
    unit: ' 次',
    color: {
      start: '#56cdf3',
      end: '#719de3'
    },
    icon: 'mdi:calendar-clock-outline'
  },
  {
    key: 'taskSuccessRate',
    title: $t('page.home.sevenDayTaskSuccessRate'),
    value: dashboardHealth.value?.sevenDay.successRate ?? null,
    unit: '%',
    color: {
      start: '#fcbc25',
      end: '#f68057'
    },
    icon: 'mdi:check-circle-outline'
  }
]);

async function loadDashboardMetrics() {
  const [statsResult, healthResult] = await Promise.all([fetchGetDashboardStats(), fetchGetDashboardHealth()]);

  if (statsResult.data) dashboardStats.value = statsResult.data;
  if (healthResult.data) dashboardHealth.value = healthResult.data;
  if (statsResult.error || healthResult.error) window.$message?.error($t('page.home.dashboardMetrics.loadError'));
}

interface GradientBgProps {
  gradientColor: string;
}

const [DefineGradientBg, GradientBg] = createReusableTemplate<GradientBgProps>();

function getGradientColor(color: CardData['color']) {
  return `linear-gradient(to bottom right, ${color.start}, ${color.end})`;
}

onMounted(loadDashboardMetrics);
</script>

<template>
  <ElCard class="card-wrapper">
    <!-- define component start: GradientBg -->
    <DefineGradientBg v-slot="{ $slots, gradientColor }">
      <div class="rd-8px px-16px pb-4px pt-8px text-white" :style="{ backgroundImage: gradientColor }">
        <component :is="$slots.default" />
      </div>
    </DefineGradientBg>
    <!-- define component end: GradientBg -->
    <ElRow :gutter="16">
      <ElCol v-for="item in cardData" :key="item.key" :lg="6" :md="12" :sm="24" class="my-8px">
        <GradientBg :gradient-color="getGradientColor(item.color)" class="flex-1">
          <h3 class="text-16px">{{ item.title }}</h3>
          <div class="flex justify-between pt-12px">
            <SvgIcon :icon="item.icon" class="text-32px" />
            <CountTo
              v-if="item.value !== null"
              :suffix="item.unit"
              :start-value="0"
              :end-value="item.value"
              class="text-30px text-white dark:text-dark"
            />
            <span v-else class="text-30px text-white dark:text-dark">-</span>
          </div>
        </GradientBg>
      </ElCol>
    </ElRow>
  </ElCard>
</template>

<style scoped></style>
