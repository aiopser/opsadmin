/**
 * 常用 Ansible 模块参数说明（静态内置，避免依赖 ansible-doc 在线解析）。
 * key 为模块短名（content 去掉 FQCN 集合名后的部分，与后端 free-form 判断一致）。
 */

export interface ModuleParamDocOption {
  /** 参数名 */
  name: string;
  /** 参数说明 */
  description: string;
  /** 是否必填 */
  required?: boolean;
  /** 可选值 */
  choices?: string[];
}

export const ANSIBLE_MODULE_PARAM_DOCS: Record<string, ModuleParamDocOption[]> = {
  shell: [
    { name: 'free-form', description: '要执行的命令，经 /bin/bash 执行，支持管道与重定向', required: true },
    { name: 'chdir', description: '执行命令前切换到的工作目录' },
    { name: 'creates', description: '该文件已存在时跳过执行' },
    { name: 'removes', description: '该文件不存在时跳过执行' },
    { name: 'executable', description: '用于执行命令的 shell 路径' }
  ],
  command: [
    { name: 'free-form', description: '要执行的命令（不经 shell 解析，不支持管道/重定向）', required: true },
    { name: 'chdir', description: '执行命令前切换到的工作目录' },
    { name: 'creates', description: '该文件已存在时跳过执行' },
    { name: 'removes', description: '该文件不存在时跳过执行' }
  ],
  script: [
    { name: 'free-form', description: '本地脚本路径及参数，脚本先复制到目标主机再执行', required: true },
    { name: 'creates', description: '该文件已存在时跳过执行' },
    { name: 'removes', description: '该文件不存在时跳过执行' }
  ],
  raw: [{ name: 'free-form', description: '经 raw 直接下发的命令，目标机无需安装 Python', required: true }],
  yum: [
    { name: 'name', description: '包名，可传多个（逗号分隔或列表）', required: true },
    { name: 'state', description: '期望状态', choices: ['present', 'installed', 'latest', 'absent', 'removed'] },
    { name: 'enablerepo', description: '本次操作临时启用的 yum 仓库' },
    { name: 'disablerepo', description: '本次操作临时禁用的 yum 仓库' }
  ],
  apt: [
    { name: 'name', description: '包名，可传多个（逗号分隔或列表）', required: true },
    { name: 'state', description: '期望状态', choices: ['present', 'latest', 'absent'] },
    { name: 'update_cache', description: '安装前先更新 apt 缓存' }
  ],
  copy: [
    { name: 'src', description: '控制机上的源文件路径' },
    { name: 'content', description: '直接下发文件内容（与 src 二选一）' },
    { name: 'dest', description: '目标主机上的目标路径', required: true },
    { name: 'owner', description: '文件属主' },
    { name: 'group', description: '文件属组' },
    { name: 'mode', description: '权限，如 0644' },
    { name: 'backup', description: '覆盖前是否备份原文件' }
  ],
  service: [
    { name: 'name', description: '服务名', required: true },
    { name: 'state', description: '期望状态', choices: ['started', 'stopped', 'restarted', 'reloaded'] },
    { name: 'enabled', description: '是否开机自启' }
  ],
  systemd: [
    { name: 'name', description: '服务名' },
    { name: 'state', description: '期望状态', choices: ['started', 'stopped', 'restarted', 'reloaded'] },
    { name: 'enabled', description: '是否开机自启' },
    { name: 'daemon_reload', description: '执行前先执行 systemctl daemon-reload' }
  ],
  user: [
    { name: 'name', description: '用户名', required: true },
    { name: 'state', description: '期望状态', choices: ['present', 'absent'] },
    { name: 'groups', description: '附加组，逗号分隔' },
    { name: 'password', description: '加密后的密码哈希' },
    { name: 'shell', description: '登录 shell' },
    { name: 'uid', description: '指定 UID' }
  ],
  group: [
    { name: 'name', description: '组名', required: true },
    { name: 'state', description: '期望状态', choices: ['present', 'absent'] },
    { name: 'gid', description: '指定 GID' }
  ],
  file: [
    { name: 'path', description: '文件/目录路径', required: true },
    { name: 'state', description: '期望状态', choices: ['file', 'directory', 'link', 'absent', 'touch'] },
    { name: 'owner', description: '文件属主' },
    { name: 'group', description: '文件属组' },
    { name: 'mode', description: '权限，如 0755' }
  ],
  lineinfile: [
    { name: 'path', description: '要修改的文件路径', required: true },
    { name: 'regexp', description: '匹配要替换行的正则表达式' },
    { name: 'line', description: '要写入/替换的行内容' },
    { name: 'state', description: '期望状态', choices: ['present', 'absent'] },
    { name: 'backup', description: '修改前是否备份原文件' }
  ],
  get_url: [
    { name: 'url', description: '下载地址', required: true },
    { name: 'dest', description: '目标保存路径', required: true },
    { name: 'mode', description: '权限，如 0644' },
    { name: 'checksum', description: '校验和，如 sha256:xxx' }
  ],
  unarchive: [
    { name: 'src', description: '压缩包路径（控制机或目标机）', required: true },
    { name: 'dest', description: '解压目标路径', required: true },
    { name: 'remote_src', description: 'src 是否位于目标主机上' }
  ],
  firewalld: [
    { name: 'service', description: '放行的服务名（与 port 二选一）' },
    { name: 'port', description: '放行的端口，如 8080/tcp' },
    { name: 'state', description: '期望状态', choices: ['enabled', 'disabled'], required: true },
    { name: 'permanent', description: '是否写入永久配置' },
    { name: 'immediate', description: '是否立即生效（重启前）' }
  ],
  cron: [
    { name: 'name', description: '任务描述标识', required: true },
    { name: 'job', description: '要执行的命令' },
    { name: 'minute', description: '分钟，默认 *' },
    { name: 'hour', description: '小时，默认 *' },
    { name: 'day', description: '日，默认 *' },
    { name: 'month', description: '月，默认 *' },
    { name: 'weekday', description: '星期，默认 *' },
    { name: 'state', description: '期望状态', choices: ['present', 'absent'] }
  ],
  setup: [{ name: 'filter', description: '收集事实的过滤模式，如 ansible_mem*' }],
  ping: []
};

/** 按模块短名取内置参数说明（未收录返回 null） */
export function getModuleParamDocs(moduleContent: string): ModuleParamDocOption[] | null {
  const name = moduleContent.trim();
  if (name.includes('.') && !name.startsWith('ansible.builtin.') && !name.startsWith('ansible.legacy.')) return null;
  const shortName = name.split('.').pop() ?? '';
  return ANSIBLE_MODULE_PARAM_DOCS[shortName] ?? null;
}

/** 取 schema 的 properties 映射（兼容 {"properties": {...}} 与扁平 {name: {...}} 两种形态） */
function pickSchemaProperties(argumentSchema: unknown): Record<string, Record<string, unknown>> {
  if (!argumentSchema || typeof argumentSchema !== 'object' || Array.isArray(argumentSchema)) return {};
  const schema = argumentSchema as Record<string, unknown>;
  const raw =
    schema.properties && typeof schema.properties === 'object' && !Array.isArray(schema.properties)
      ? (schema.properties as Record<string, unknown>)
      : schema;
  const result: Record<string, Record<string, unknown>> = {};
  Object.entries(raw).forEach(([name, definition]) => {
    if (name === 'properties' || name === 'required') return;
    if (definition && typeof definition === 'object' && !Array.isArray(definition)) {
      result[name] = definition as Record<string, unknown>;
    }
  });
  return result;
}

/** 取 schema 顶层的 required 名单 */
function pickSchemaRequired(argumentSchema: unknown): Set<string> {
  if (!argumentSchema || typeof argumentSchema !== 'object' || Array.isArray(argumentSchema)) return new Set();
  const required = (argumentSchema as Record<string, unknown>).required;
  return new Set(Array.isArray(required) ? required.map(String) : []);
}

/** 判断参数是否必填：兼容标准 required、顶层 required 列表与 x-required 扩展键 */
function isParamRequired(definition: Record<string, unknown>, name: string, requiredList: Set<string>): boolean {
  return Boolean(definition.required) || Boolean(definition['x-required']) || requiredList.has(name);
}

/** 参数说明是帮助文档，不参与执行参数或 extra_vars 校验。 */
export interface ModuleParamNote {
  key: string;
  value: string;
}

export function buildParameterDocs(rows: readonly ModuleParamNote[]): Api.Automation.ModuleParameterDoc[] {
  const notes = rows
    .filter(row => row.key.trim() || row.value.trim())
    .map(row => ({
      name: row.key.trim(),
      description: row.value.trim()
    }));
  const names = new Set<string>();
  notes.forEach(note => {
    if (!note.name || !note.description) throw new Error('请填写参数名和参数说明');
    if (names.has(note.name)) throw new Error(`参数名「${note.name}」重复`);
    names.add(note.name);
  });
  return notes;
}

/** Read-only compatibility for the previous storage format. */
export function buildModuleNotes(rows: readonly ModuleParamNote[]): Record<string, unknown> {
  return { 'x-module-parameter-docs': buildParameterDocs(rows) };
}

export function readModuleNotes(schema: unknown): ModuleParamNote[] {
  return (schemaToParamDocs(schema) ?? []).map(note => ({ key: note.name, value: note.description }));
}

export function readVersionModuleNotes(version: {
  parameterDocs?: Api.Automation.ModuleParameterDoc[];
  argumentSchema?: Record<string, unknown>;
}): ModuleParamNote[] {
  if (Array.isArray(version.parameterDocs)) {
    return version.parameterDocs.map(note => ({ key: note.name, value: note.description }));
  }
  return readModuleNotes(version.argumentSchema);
}

export function versionModuleParamDocs(version: {
  parameterDocs?: Api.Automation.ModuleParameterDoc[];
  argumentSchema?: Record<string, unknown>;
}): ModuleParamDocOption[] {
  return readVersionModuleNotes(version).map(note => ({ name: note.key, description: note.value }));
}

/** 版本自身 schema → 参数说明（无 properties 返回 null，交由调用方回退内置字典） */
export function schemaToParamDocs(argumentSchema: unknown): ModuleParamDocOption[] | null {
  if (argumentSchema && typeof argumentSchema === 'object' && 'x-module-parameter-docs' in argumentSchema) {
    const notes = argumentSchema['x-module-parameter-docs'];
    if (!Array.isArray(notes)) return [];
    return notes
      .filter((note): note is { name: string; description: string } =>
        Boolean(
          note && typeof note === 'object' && typeof note.name === 'string' && typeof note.description === 'string'
        )
      )
      .map(note => ({ name: note.name, description: note.description }));
  }
  const properties = pickSchemaProperties(argumentSchema);
  const entries = Object.entries(properties);
  if (!entries.length) return null;

  const requiredList = pickSchemaRequired(argumentSchema);

  return entries.map(([name, definition]) => ({
    name,
    description: String(definition.description ?? ''),
    required: isParamRequired(definition, name, requiredList),
    choices: Array.isArray(definition.choices) ? definition.choices.map(String) : []
  }));
}

/** 参数说明解析：优先取版本自身配置，为空回退内置字典 */
export function resolveModuleParamDocs(argumentSchema: unknown, moduleContent: string): ModuleParamDocOption[] | null {
  return schemaToParamDocs(argumentSchema) ?? getModuleParamDocs(moduleContent);
}
