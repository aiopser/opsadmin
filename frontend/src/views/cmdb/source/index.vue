<script setup lang="ts">
import CloudAccountList from './modules/cloud-account-list.vue';

defineOptions({ name: 'CmdbSource' });
</script>

<template>
  <div class="min-h-500px flex-col-stretch">
    <CloudAccountList />
  </div>
</template>
