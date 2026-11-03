<script setup lang="ts">
import CommandResourcePage from '../modules/command-page.vue';

defineOptions({ name: 'AutomationResourcesScript' });
</script>

<template>
  <CommandResourcePage
    resource-kind="script"
    title="脚本"
    description="维护可复用脚本；编辑草稿并发布后供作业和流程引用"
  />
</template>
