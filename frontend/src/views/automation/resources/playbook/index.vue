<script setup lang="ts">
import CommandResourcePage from '../modules/command-page.vue';

defineOptions({ name: 'AutomationResourcesPlaybook' });
</script>

<template>
  <CommandResourcePage
    resource-kind="playbook"
    title="Playbook"
    description="存储 Ansible Playbook，用于多主机批量作业编排"
  />
</template>
