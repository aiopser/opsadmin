/**
 * 系统配置控件映射表
 *
 * 后端 SystemConfig 只存「键 → 字符串值」，控件类型无法从数据推断，
 * 因此由前端维护「配置键 → 控件类型 / 单位 / 提示 / 依赖」映射表。
 * 未登记的键统一回退为文本输入框。
 */

/** 配置分组固定枚举（与后端 SystemConfig.ConfigGroup 保持一致） */
export type ConfigGroupKey = 'basic' | 'security' | 'log' | 'file';

/** 配置项控件类型 */
export type ConfigControlType = 'text' | 'number' | 'switch' | 'password' | 'chips' | 'avatar';

/** 分组展示定义 */
export interface ConfigGroupDef {
  key: ConfigGroupKey;
  name: string;
  desc: string;
}

/** 单个配置项的控件定义 */
export interface ConfigFieldDef {
  /** 内置配置的用户可读名称，不携带单位或技术键 */
  label?: string;
  /** 控件类型 */
  type: ConfigControlType;
  /** 数值控件的单位后缀 */
  unit?: string;
  /** 控件下方的补充说明 */
  hint?: string;
  /** 依赖的配置键：依赖项关闭时本项不可编辑 */
  dependsOn?: string;
  /** 当前未接入运行逻辑时展示原因，并禁止编辑。 */
  inactiveReason?: string;
}

/** 左侧分组导航项 */
export interface ConfigNavGroup {
  key: ConfigGroupKey;
  name: string;
  /** 配置项数量 */
  count: number;
  /** 是否存在未保存修改 */
  changed: boolean;
}

/** 分组视图渲染所需的配置行 */
export interface ConfigRowItem {
  id: number;
  configKey: string;
  configName: string;
  remark: string;
  isSystem: boolean;
}

/** 分组定义（顺序即导航顺序） */
export const CONFIG_GROUPS: ConfigGroupDef[] = [
  {
    key: 'basic',
    name: '基础配置',
    desc: '站点标识与对外展示文案，影响浏览器标题、登录页主标题与系统水印。'
  },
  {
    key: 'security',
    name: '安全配置',
    desc: '密码与登录安全策略。部分项为建议值，实际校验以上线策略为准。'
  },
  {
    key: 'log',
    name: '日志与审计',
    desc: '操作日志记录范围与保留策略。'
  },
  {
    key: 'file',
    name: '文件与上传',
    desc: '上传限制与媒体资源访问路径。'
  }
];

/** 配置键 → 控件定义 */
export const CONFIG_FIELD_DEFS: Record<string, ConfigFieldDef> = {
  'basic.system.name': { type: 'text' },
  'basic.login.title': { type: 'text' },
  'basic.user.default_avatar': {
    type: 'avatar',
    hint: '支持 /media/ 相对路径或完整 URL。',
    inactiveReason: '暂未生效：当前头像展示尚未使用此默认值。'
  },
  'security.password.min_length': { label: '密码最小长度', type: 'number', unit: '位', hint: '建议不小于 8 位。' },
  'security.user.default_password': {
    label: '用户初始密码',
    type: 'password',
    hint: '未指定密码时使用；新建或重置后首次登录必须修改。'
  },
  'security.login.max_failures': {
    label: '连续登录失败次数',
    type: 'number',
    unit: '次',
    hint: '连续失败达到阈值后锁定 15 分钟；成功登录或锁定到期后重新计数。'
  },
  'security.jwt.access_token_seconds': {
    label: '访问令牌有效期',
    type: 'number',
    unit: '秒',
    hint: '86400 秒 ≈ 24 小时。',
    inactiveReason: '暂未生效：当前令牌有效期由服务端部署配置决定。'
  },
  'log.operation.enabled': { type: 'switch', hint: '关闭后「审计日志」页面不再产生新记录。' },
  'log.operation.record_get': {
    type: 'switch',
    dependsOn: 'log.operation.enabled',
    hint: '依赖上方的「启用操作日志」，关闭后本项不生效。'
  },
  'log.operation.retention_days': {
    type: 'number',
    unit: '天',
    hint: '建议 30 ~ 180 天。',
    inactiveReason: '暂未生效：当前尚未接入按此期限自动清理日志的任务。'
  },
  'file.upload.max_size_mb': { label: '单文件大小上限', type: 'number', unit: 'MB' },
  'file.upload.allowed_extensions': {
    label: '允许上传类型',
    type: 'chips',
    hint: '输入扩展名后按回车添加，点击 × 移除。'
  },
  'file.media.base_url': {
    type: 'text',
    inactiveReason: '暂未生效：当前媒体访问路径由服务端部署配置决定。'
  }
};

const DEFAULT_FIELD_DEF: ConfigFieldDef = { type: 'text' };

/** 取配置键对应的控件定义（未登记则回退文本） */
export function resolveFieldDef(configKey: string): ConfigFieldDef {
  return CONFIG_FIELD_DEFS[configKey] ?? DEFAULT_FIELD_DEF;
}

/** 按分组键取分组定义 */
export function resolveGroupDef(configGroup: string): ConfigGroupDef | undefined {
  return CONFIG_GROUPS.find(group => group.key === configGroup);
}

/** switch 控件：后端字符串值 → 布尔 */
export function toSwitchValue(raw: string | null | undefined): boolean {
  return raw === 'true' || raw === '1';
}

/** 布尔 → 后端存储字符串 */
export function toStoredSwitch(value: boolean): string {
  return value ? 'true' : 'false';
}

/** chips 控件：逗号分隔字符串 → 后缀数组 */
export function toExtensionList(raw: string | null | undefined): string[] {
  return (raw ?? '')
    .split(',')
    .map(item => item.trim())
    .filter(Boolean);
}

/** 后缀数组 → 后端存储字符串 */
export function toStoredExtensions(list: string[]): string {
  return list.join(',');
}

/** number 控件：后端字符串值 → 数字（非法值回退 0） */
export function toNumberValue(raw: string | null | undefined): number {
  const parsed = Number(raw);

  return Number.isFinite(parsed) ? parsed : 0;
}

/** 数字 → 后端存储字符串 */
export function toStoredNumber(value: number | undefined): string {
  return value === undefined ? '' : String(value);
}

/** 草稿值相对已保存值是否已修改 */
export function isValueDirty(
  configKey: string,
  draftValues: Record<string, string>,
  savedValues: Record<string, string>
): boolean {
  return (draftValues[configKey] ?? '') !== (savedValues[configKey] ?? '');
}
