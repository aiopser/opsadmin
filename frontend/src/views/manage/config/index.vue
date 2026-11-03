<script setup lang="ts">
import ConfigGroupView from './modules/config-group-view.vue';

defineOptions({ name: 'ConfigManage' });
</script>

<template>
  <div class="min-h-500px flex-col-stretch">
    <ConfigGroupView />
  </div>
</template>
