/** 流程输入参数 Schema 的共享解析与校验（run-create / ticket-create-drawer 共用） */

export type FieldOption = NonNullable<Api.Jobs.WorkflowInputField['options']>[number];

/** 解析版本的 inputSchema 为字段数组（兼容数组与 { fields: [] } 两种历史形态） */
export function getSchemaFields(
  version: Api.Jobs.WorkflowVersionOption | null | undefined
): Api.Jobs.WorkflowInputField[] {
  const schema = version?.inputSchema;
  if (Array.isArray(schema)) return schema;
  if (schema && typeof schema === 'object' && Array.isArray((schema as { fields?: unknown }).fields)) {
    return (schema as { fields: Api.Jobs.WorkflowInputField[] }).fields;
  }
  return [];
}

/** 按字段默认值构建初始参数表 */
export function buildDefaultVars(fields: Api.Jobs.WorkflowInputField[]): Record<string, unknown> {
  const next: Record<string, unknown> = {};
  fields.forEach(field => {
    if (field.default !== undefined) next[field.name] = field.default;
  });
  return next;
}

/** select / multiselect 选项取值 */
export function optValue(opt: FieldOption) {
  return typeof opt === 'object' ? opt.value : opt;
}

/** select / multiselect 选项标签 */
export function optLabel(opt: FieldOption) {
  return typeof opt === 'object' ? (opt.label ?? String(opt.value)) : String(opt);
}

/** 未填写的必填字段（undefined / 空字符串视为未填） */
export function missingRequiredFields(
  fields: Api.Jobs.WorkflowInputField[],
  vars: Record<string, unknown>
): Api.Jobs.WorkflowInputField[] {
  return fields.filter(field => field.required && (vars[field.name] === undefined || vars[field.name] === ''));
}
