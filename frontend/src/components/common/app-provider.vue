<script setup lang="ts">
import { createTextVNode, defineComponent } from 'vue';

defineOptions({ name: 'AppProvider' });

type NotificationContent = string | { title: string; message?: string };

function toNotifyOptions(content: NotificationContent, detail?: string) {
  return typeof content === 'string' ? { title: content, message: detail } : content;
}

const ContextHolder = defineComponent({
  name: 'ContextHolder',
  setup() {
    function register() {
      /** 右上角通知：success/warning/info 4 秒自动关闭，error 需手动关闭 */
      window.$notification = {
        success: (content, detail) =>
          ElNotification.success({ duration: 4000, showClose: true, ...toNotifyOptions(content, detail) }),
        warning: (content, detail) =>
          ElNotification.warning({ duration: 4000, showClose: true, ...toNotifyOptions(content, detail) }),
        info: (content, detail) =>
          ElNotification.info({ duration: 4000, showClose: true, ...toNotifyOptions(content, detail) }),
        error: (content, detail) =>
          ElNotification.error({ duration: 0, showClose: true, ...toNotifyOptions(content, detail) })
      };
      window.$messageBox = ElMessageBox;
      window.$message = ElMessage;
    }

    register();

    return () => createTextVNode();
  }
});
</script>

<template>
  <div class="h-full">
    <ContextHolder />
    <slot></slot>
  </div>
</template>

<style scoped></style>
