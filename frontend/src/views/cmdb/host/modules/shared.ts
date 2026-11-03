export interface HostForm {
  id?: number;
  hostname: string;
  internal_ip: string;
  external_ip: string;
  asset_type: string;
  os_family: Api.Cmdb.OsFamily;
  os_type: string;
  image_name: string;
  cpu_cores: number | null;
  memory_gb: number | null;
  system_disk_gb: number | null;
  data_disk_gb: number | null;
  environment: string;
  region: string;
  status: Api.Cmdb.HostStatus;
  owner_team: string;
  app_code: string;
  connection_type: Api.Cmdb.CredentialConnectionType;
  connection_port: number | null;
  credential_ref: number | null;
  group_ids: string[];
  tag_ids: string[];
  asset_source: number | null;
}

export function formatHostMemory(memoryMb: number): string {
  if (!memoryMb) return '-';
  return memoryMb % 1024 ? `${memoryMb} MB` : `${memoryMb / 1024} GB`;
}

/** 磁盘容量分段展示值：未采集（0/空）显示 -，与内存格式约定一致 */
export function formatHostDiskGb(diskGb: number): string {
  return diskGb && diskGb > 0 ? `${diskGb} GB` : '-';
}

export function buildHostPayload(form: HostForm): Api.Cmdb.HostPayload {
  return {
    hostname: form.hostname,
    internal_ip: form.internal_ip,
    external_ip: form.external_ip || null,
    asset_type: form.asset_type,
    os_family: form.os_family,
    os_type: form.os_type,
    image_name: form.image_name,
    cpu_cores: form.cpu_cores ?? 0,
    memory_mb: form.memory_gb ? form.memory_gb * 1024 : 0,
    system_disk_gb: form.system_disk_gb ?? 0,
    data_disk_gb: form.data_disk_gb ?? 0,
    environment: form.environment,
    region: form.region,
    status: form.status,
    owner_team: form.owner_team,
    app_code: form.app_code,
    connection_type: form.connection_type,
    connection_port: form.connection_port ?? 22,
    credential_ref: form.credential_ref || null,
    asset_source: form.asset_source || null
  };
}
