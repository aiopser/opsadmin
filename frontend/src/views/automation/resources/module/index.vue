<script setup lang="ts">
import CommandResourcePage from '../modules/command-page.vue';

defineOptions({ name: 'AutomationResourcesModule' });
</script>

<template>
  <CommandResourcePage
    resource-kind="module"
    title="Module"
    description="存储 Ansible Module 调用配置，供模块执行使用"
  />
</template>
