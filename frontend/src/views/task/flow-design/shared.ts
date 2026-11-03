export function nativeParameterField(type: string): string | undefined {
  const fields: Record<string, string> = {
    script: 'environment',
    command: 'environment',
    playbook: 'extraVars',
    module: 'args'
  };
  return fields[type];
}

export function nativeParameterText(type: string, config: Record<string, unknown>): string {
  const field = nativeParameterField(type);
  const value = field ? (config[field] ?? (type === 'module' ? config.moduleArgs : undefined)) : undefined;
  if (value === undefined) return '';
  return typeof value === 'string' ? value : JSON.stringify(value, null, 2);
}

export function nativeParameterConfig(type: string, text: string): Record<string, unknown> {
  const field = nativeParameterField(type);
  if (!field || !text.trim()) return {};
  if (type === 'module' && !/^\s*\{\s*(?:"|}|$)/.test(text)) return { [field]: text };
  const value: unknown = JSON.parse(text);
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('参数必须为 JSON 对象');
  return { [field]: value };
}

export function nativeParameterError(type: string, text: string): string {
  try {
    nativeParameterConfig(type, text);
    return '';
  } catch {
    return '请填写有效 JSON 对象';
  }
}

export interface StepHostSettings {
  hostPolicy: 'native' | 'platform';
  overrideHostSettings: boolean;
  hostStrategy: 'inherit' | 'parallel' | 'rolling' | 'serial';
  forks: number | null;
  serialBatch: number | null;
  maxFailPercentage: number | null;
}

export function hasStepHostOverrides(config: Record<string, unknown>): boolean {
  return ['hostStrategy', 'forks', 'serialBatch', 'maxFailPercentage'].some(
    key => config[key] !== undefined && config[key] !== null
  );
}

export function stepHostConfig(type: string, settings: StepHostSettings): Record<string, unknown> {
  const policy = type === 'playbook' ? { hostPolicy: settings.hostPolicy } : {};
  if ((type === 'playbook' && settings.hostPolicy === 'native') || !settings.overrideHostSettings) return policy;
  return {
    ...policy,
    ...(settings.hostStrategy !== 'inherit' ? { hostStrategy: settings.hostStrategy } : {}),
    ...(settings.hostStrategy !== 'serial' && typeof settings.forks === 'number' ? { forks: settings.forks } : {}),
    ...(['rolling', 'inherit'].includes(settings.hostStrategy) && typeof settings.serialBatch === 'number'
      ? { serialBatch: settings.serialBatch }
      : {}),
    ...(typeof settings.maxFailPercentage === 'number' ? { maxFailPercentage: settings.maxFailPercentage } : {})
  };
}
