<script setup lang="ts">
import type { ModuleParamNote } from '@/constants/ansible-module-param-docs';
import CodeEditor from '@/components/common/code-editor/index.vue';

defineOptions({ name: 'AutomationVersionFormFields' });

/** 版本表单字段模型（新建/编辑抽屉与版本管理共用） */
interface VersionFormFieldsModel {
  commandType: Api.Automation.CommandType;
  content: string;
  moduleName: string;
  timeoutSeconds: number;
  becomeEnabled: boolean;
  checkModeSupported: boolean;
  remark: string;
  argumentSchema: string;
  defaultVars: string;
  outputExtractors: string;
  /** 参数名 → 参数说明，仅作为快速执行帮助 */
  moduleParamNotes: ModuleParamNote[];
}

defineProps<{
  /** 当前资源类型可选的执行类型 */
  commandTypeOptions: { value: string; label: string }[];
  /** 执行类型字段标签（脚本资源展示为"脚本类型"，默认"执行类型"） */
  commandTypeLabel?: string;
  /** 是否为 Module 资源（决定是否展示模块参数编辑器） */
  isModule?: boolean;
}>();

const emit = defineEmits<{
  /** 执行类型切换（父级按需替换内容模板） */
  typeChange: [commandType: string];
}>();

const model = defineModel<VersionFormFieldsModel>({ required: true });

/** 版本内容对应的编辑器语言 */
function getEditorLanguage(commandType: string) {
  const map: Record<string, 'shell' | 'python' | 'powershell' | 'yaml' | 'plaintext'> = {
    linux_shell: 'shell',
    python: 'python',
    windows_powershell: 'powershell',
    playbook: 'yaml',
    http_request: 'plaintext',
    ansible_module: 'plaintext'
  };
  return map[commandType] ?? 'plaintext';
}

function onTypeChange(commandType: string | number | boolean | undefined) {
  if (typeof commandType !== 'string') return;
  emit('typeChange', commandType);
}

function addModuleNote() {
  model.value.moduleParamNotes.push({ key: '', value: '' });
}

function removeModuleNote(index: number) {
  model.value.moduleParamNotes.splice(index, 1);
}
</script>

<template>
  <div class="w-full">
    <ElFormItem v-if="commandTypeOptions.length > 1" prop="commandType">
      <template #label>
        <FormLabelHelp
          :label="commandTypeLabel || '执行类型'"
          :help="[
            '决定内容的解析方式与执行引擎：',
            'linux_shell / python / windows_powershell 按脚本执行，playbook 按 Ansible 剧本执行，ansible_module 按 Ansible 模块执行。'
          ]"
        />
      </template>
      <ElRadioGroup v-model="model.commandType" @change="onTypeChange">
        <ElRadio v-for="item in commandTypeOptions" :key="item.value" :value="item.value">
          {{ item.label }}
        </ElRadio>
      </ElRadioGroup>
    </ElFormItem>
    <ElFormItem :prop="isModule ? 'moduleName' : 'content'">
      <template #label>
        <FormLabelHelp
          :label="isModule ? 'Ansible 模块名' : model.commandType === 'playbook' ? 'Playbook 内容' : '执行内容'"
          :help="
            isModule
              ? [
                  '建议使用完整模块名，如 ansible.builtin.service、ansible.builtin.yum；',
                  '下方自主维护参数名和参数说明，实际值在快速执行时填写。'
                ]
              : ['按上方执行类型填写对应的命令、脚本或 Playbook 内容；', '支持 {{ 变量 }} 占位，运行时由执行参数替换。']
          "
        />
      </template>
      <ElInput v-if="isModule" v-model="model.moduleName" placeholder="如 ansible.builtin.service" />
      <CodeEditor
        v-else
        v-model="model.content"
        :language="getEditorLanguage(model.commandType)"
        :height="model.commandType === 'playbook' ? '360px' : '240px'"
        placeholder="输入命令、脚本或 Playbook 内容"
      />
    </ElFormItem>
    <div v-if="model.commandType === 'playbook'" class="mb-20px text-13px text-[var(--el-text-color-regular)]">
      当前保存单文件 Playbook，不包含仓库中的 roles、files、templates；保存时校验 YAML 格式，不代表已通过 Ansible
      执行校验。
    </div>
    <ElFormItem v-if="isModule" prop="moduleParamNotes" label-position="left" label-width="100px">
      <template #label>
        <FormLabelHelp label="参数说明" :help="['参数名对应说明文字，供快速执行时参考；实际参数值在执行时填写。']" />
      </template>
      <div class="w-full flex flex-col gap-8px">
        <div v-if="!model.moduleParamNotes.length" class="text-12px text-gray-500">暂无参数说明，点击下方按钮添加</div>
        <div class="flex flex-col gap-8px" role="list" aria-label="模块参数说明列表">
          <div
            v-for="(row, index) in model.moduleParamNotes"
            :key="index"
            class="flex items-start gap-8px"
            role="listitem"
          >
            <ElInput v-model="row.key" class="w-180px shrink-0" aria-label="参数名" placeholder="参数名（Key）" />
            <ElInput
              v-model="row.value"
              class="min-w-0 flex-1"
              type="textarea"
              :autosize="{ minRows: 1, maxRows: 4 }"
              aria-label="参数说明"
              placeholder="参数说明（Value），如：服务名称，例如 nginx"
            />
            <ElButton link type="danger" class="min-h-32px" @click="removeModuleNote(index)">删除</ElButton>
          </div>
        </div>
        <div>
          <ElButton size="small" class="min-h-32px" @click="addModuleNote">＋ 添加参数说明</ElButton>
        </div>
      </div>
    </ElFormItem>
    <ElFormItem v-if="!isModule" label="额外变量 extra_vars" prop="defaultVars">
      <div class="w-full">
        <ElInput v-model="model.defaultVars" type="textarea" :rows="4" placeholder='如 {"service_name": "nginx"}' />
        <p class="mb-0 mt-8px text-13px text-[var(--el-text-color-regular)]">
          {{
            model.commandType === 'playbook'
              ? 'Playbook 的默认 extra_vars；任务单参数可覆盖同名值，步骤 extra_vars 优先于任务单参数。'
              : '脚本默认变量；标量值自动注入环境变量，Shell 使用 $变量名，PowerShell 使用 $env:变量名。'
          }}
        </p>
      </div>
    </ElFormItem>
    <ElFormItem label="版本备注">
      <ElInput v-model="model.remark" type="textarea" :rows="2" placeholder="本次版本的变更说明（可选）" />
    </ElFormItem>
    <ElCollapse v-if="!isModule" class="advanced-collapse">
      <ElCollapseItem title="高级配置" name="advanced">
        <ElFormItem label="默认步骤超时" prop="timeoutSeconds">
          <ElInputNumber v-model="model.timeoutSeconds" :min="1" :max="86400" controls-position="right" />
          <span class="ml-8px">秒</span>
        </ElFormItem>
        <ElFormItem label="提权执行">
          <template #label>
            <FormLabelHelp label="提权执行" :help="['以 sudo 提权到 root 执行，目标主机的执行用户需有提权权限。']" />
          </template>
          <ElSwitch v-model="model.becomeEnabled" />
        </ElFormItem>
        <ElFormItem label="支持检查模式">
          <template #label>
            <FormLabelHelp
              label="支持检查模式"
              :help="['允许使用 --check；实际行为取决于模块支持和任务配置，不能保证完全不产生变更。']"
            />
          </template>
          <ElSwitch v-model="model.checkModeSupported" />
        </ElFormItem>
        <template v-if="!isModule">
          <ElFormItem
            v-if="model.argumentSchema.trim() && model.argumentSchema.trim() !== '{}'"
            label="历史参数校验"
            prop="argumentSchema"
          >
            <template #label>
              <FormLabelHelp
                label="历史参数校验"
                :help="[
                  '兼容已有版本的参数校验规则；新资源直接使用 extra_vars。',
                  '如 {&quot;count&quot;: {&quot;type&quot;: &quot;number&quot;}}'
                ]"
              />
            </template>
            <ElInput
              v-model="model.argumentSchema"
              type="textarea"
              :rows="2"
              placeholder='JSON 对象，如 {"count": {"type": "number"}}'
            />
          </ElFormItem>
        </template>
        <ElFormItem
          v-if="model.outputExtractors.trim() && model.outputExtractors.trim() !== '[]'"
          label="历史输出提取"
          prop="outputExtractors"
        >
          <template #label>
            <FormLabelHelp
              label="历史输出提取"
              :help="[
                '从执行输出中提取变量，供后续节点引用，JSON 数组；',
                '如 [{&quot;name&quot;: &quot;result&quot;, &quot;pattern&quot;: &quot;RESULT=(\\\\w+)&quot;}]；多主机时分别保存在各主机输出中。'
              ]"
            />
          </template>
          <ElInput v-model="model.outputExtractors" type="textarea" :rows="2" placeholder="JSON 数组，如 []" />
        </ElFormItem>
      </ElCollapseItem>
    </ElCollapse>
  </div>
</template>
