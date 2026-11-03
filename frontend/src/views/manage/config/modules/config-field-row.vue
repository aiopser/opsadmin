<script setup lang="ts">
import { computed, ref } from 'vue';
import {
  resolveFieldDef,
  toExtensionList,
  toNumberValue,
  toStoredExtensions,
  toStoredNumber,
  toStoredSwitch,
  toSwitchValue
} from './config-fields';
import type { ConfigRowItem } from './config-fields';

defineOptions({ name: 'ConfigFieldRow' });

interface Props {
  /** 配置行数据 */
  item: ConfigRowItem;
  /** 当前草稿值（后端存储的字符串格式） */
  value: string;
  /** 依赖项未启用时禁用控件 */
  disabled?: boolean;
  /** 相对已保存值是否已修改 */
  changed?: boolean;
}

const props = withDefaults(defineProps<Props>(), { disabled: false, changed: false });

interface Emits {
  (e: 'update:value', value: string): void;
}

const emit = defineEmits<Emits>();

const fieldDef = computed(() => resolveFieldDef(props.item.configKey));
const displayName = computed(() => fieldDef.value.label ?? props.item.configName);
const description = computed(() => fieldDef.value.hint || props.item.remark);
const switchValue = computed(() => toSwitchValue(props.value));
const numberValue = computed(() => toNumberValue(props.value));
const extensionList = computed(() => toExtensionList(props.value));

const newExtension = ref('');

function handleTextInput(value: string | number) {
  emit('update:value', String(value));
}

function handleSwitchChange(value: string | number | boolean) {
  emit('update:value', toStoredSwitch(value === true));
}

function handleNumberChange(value: number | undefined) {
  emit('update:value', toStoredNumber(value));
}

function handleAddExtension() {
  if (props.disabled) return;

  const extension = newExtension.value.trim();

  if (!extension) {
    return;
  }

  newExtension.value = '';

  if (extensionList.value.includes(extension)) {
    return;
  }

  emit('update:value', toStoredExtensions([...extensionList.value, extension]));
}

function handleRemoveExtension(extension: string) {
  if (props.disabled) return;
  emit('update:value', toStoredExtensions(extensionList.value.filter(item => item !== extension)));
}
</script>

<template>
  <div class="config-field-row" :class="{ 'is-changed': changed }">
    <div class="field-label">
      <div class="field-title">
        <span>{{ displayName }}</span>
        <ElTag v-if="fieldDef.inactiveReason" type="info" size="small">暂未生效</ElTag>
        <span v-if="changed" class="text-12px text-[var(--el-color-warning)]">已修改</span>
      </div>
    </div>

    <div class="field-control">
      <ElInput
        v-if="fieldDef.type === 'text'"
        :model-value="value"
        :disabled="disabled"
        :aria-label="displayName"
        class="field-input"
        @update:model-value="handleTextInput"
      />

      <ElInput
        v-else-if="fieldDef.type === 'password'"
        :model-value="value"
        :disabled="disabled"
        type="password"
        show-password
        :aria-label="displayName"
        class="field-input"
        @update:model-value="handleTextInput"
      />

      <div v-else-if="fieldDef.type === 'number'" class="field-number">
        <ElInputNumber
          :model-value="numberValue"
          :disabled="disabled"
          :aria-label="displayName"
          :min="1"
          class="w-200px"
          controls-position="right"
          @update:model-value="handleNumberChange"
        />
        <span v-if="fieldDef.unit" class="field-unit">{{ fieldDef.unit }}</span>
      </div>

      <div v-else-if="fieldDef.type === 'switch'" class="field-switch">
        <ElSwitch
          :aria-label="displayName"
          :model-value="switchValue"
          :disabled="disabled"
          @change="handleSwitchChange"
        />
        <span class="field-switch-text">{{ switchValue ? '已开启' : '已关闭' }}</span>
      </div>

      <div v-else-if="fieldDef.type === 'chips'" class="field-chips">
        <ElTag
          v-for="extension in extensionList"
          :key="extension"
          :closable="!disabled"
          :disable-transitions="true"
          @close="handleRemoveExtension(extension)"
        >
          {{ extension }}
        </ElTag>
        <ElInput
          v-model="newExtension"
          :disabled="disabled"
          class="chips-input"
          placeholder="输入后缀后回车"
          @keyup.enter="handleAddExtension"
        />
      </div>

      <div v-else class="field-avatar">
        <ElInput
          :model-value="value"
          :disabled="disabled"
          :aria-label="displayName"
          class="field-input"
          @update:model-value="handleTextInput"
        />
        <ElTooltip content="头像预览；显示默认图标时表示图片为空或无法加载">
          <ElAvatar :key="value" :src="value" :size="32" shape="square" aria-label="默认头像预览">
            <icon-ic-round-person class="text-20px" />
          </ElAvatar>
        </ElTooltip>
      </div>

      <p v-if="description" class="field-hint">{{ description }}</p>
      <p v-if="fieldDef.inactiveReason" class="field-hint">{{ fieldDef.inactiveReason }}</p>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.config-field-row {
  display: grid;
  grid-template-columns: 140px minmax(0, 440px);
  gap: 16px;
  padding: 12px 0;
}

.field-label {
  padding-top: 5px;
  text-align: right;
}

.field-title {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  font-size: 13px;
  color: var(--el-text-color-primary);
}

.field-control {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
  max-width: 440px;
}

.field-input {
  width: 100%;
  max-width: 440px;
}

.field-number {
  display: flex;
  align-items: center;
  gap: 8px;
}

.field-unit {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.field-switch {
  min-height: 32px;
  display: flex;
  align-items: center;
  gap: 10px;
}

.field-switch-text {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.field-chips {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.chips-input {
  width: 160px;
}

.field-avatar {
  max-width: 440px;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 10px;
}

.field-hint {
  font-size: 12px;
  line-height: 1.6;
  color: var(--el-text-color-secondary);
}
@media (max-width: 767px) {
  .config-field-row {
    grid-template-columns: minmax(0, 1fr);
    gap: 8px;
  }

  .field-label {
    text-align: left;
    padding-top: 0;
  }
  .field-title {
    justify-content: flex-start;
  }
}
</style>
