declare namespace Api {
  /**
   * namespace Cmdb
   *
   * 资产管理域：主机资产（AssetHostSerializer 输出，字段整体 camelCase）。
   */
  namespace Cmdb {
    type OsFamily = 'linux' | 'windows';
    type HostStatus = 'active' | 'inactive' | 'retired';

    /** 主机资产记录（AssetHostSerializer 输出） */
    interface HostRecord {
      id: number;
      hostname: string;
      internalIp: string;
      /** 外网IP，可选，未录入为 null */
      externalIp: string | null;
      assetType: string;
      osFamily: OsFamily | string;
      osType: string;
      imageName: string;
      cpuCores: number;
      memoryMb: number;
      systemDiskGb: number;
      dataDiskGb: number;
      environment: string;
      /** 主机所在地域（如 cn-east-1），调度时用于匹配同地域 Worker 池 */
      region: string;
      status: HostStatus | string;
      cloudState?: string;
      lastObservedAt?: string | null;
      connectionType: string;
      connectionPort: number;
      appCode: string;
      ownerTeam: string;
      groupIds: string[];
      credentialRef: number | null;
      credentialRefName: string;
      assetSource: number | null;
      assetSourceName: string;
      sourceType: string;
      lastSyncedAt: string | null;
      lastDiscoveredAt: string | null;
      createdAt: string | null;
      updatedAt: string | null;
      /** serializer 附加只读字段 */
      configSummary: string;
    }

    /** 主机列表查询参数（后端 filterset: os_family/environment/status/app_code，另支持 group_id 含子分组级联） */
    interface HostSearchParams {
      current: number;
      size: number;
      search?: string | null;
      osFamily?: OsFamily | null;
      status?: HostStatus | null;
      environment?: string | null;
      /** 按主机分组过滤（含子分组级联） */
      groupId?: number | null;
      /** 按 id 集合过滤（逗号分隔，用于编辑回填主机信息） */
      ids?: string | null;
    }

    /** 凭据类型（CredentialRef.CredentialType） */
    type CredentialType = 'ssh_key' | 'password' | 'vault_ref';

    /** 凭据作用域（CredentialRef.Scope） */
    type CredentialScope = 'global' | 'environment' | 'host_group' | 'host';

    /** 连接协议（CredentialRef.ConnectionProtocol） */
    type CredentialConnectionType = 'ssh' | 'winrm' | 'local';

    /**
     * 凭据引用记录（CredentialRefSerializer 输出）。
     * 基础字段 snake_case（fields="__all__"），hostCount/effectivePort 为 serializer 附加驼峰。
     */
    interface CredentialRefRecord {
      id: number;
      name: string;
      type: CredentialType | string;
      scope: CredentialScope | string;
      connection_type: CredentialConnectionType | string;
      username: string;
      default_port: number | null;
      secret_ref: string;
      /** 脱敏后的密文占位（后端 mask_secret 处理） */
      encrypted_secret: string;
      metadata: Record<string, unknown>;
      is_active: boolean;
      created_at: string | null;
      updated_at: string | null;
      /** serializer 附加只读字段 */
      hostCount: number;
      effectivePort: number;
    }

    /** 凭据创建/更新载荷（secret 为 write_only 明文，后端加密存储） */
    interface CredentialRefPayload {
      name: string;
      type: CredentialType;
      scope: CredentialScope;
      connection_type?: CredentialConnectionType;
      username?: string;
      default_port?: number | null;
      secret_ref?: string;
      secret?: string;
      metadata?: Record<string, unknown>;
      is_active?: boolean;
    }

    /** 凭据列表查询参数 */
    interface CredentialRefSearchParams {
      current: number;
      size: number;
      search?: string | null;
      type?: CredentialType | null;
      scope?: CredentialScope | null;
      isActive?: boolean | null;
    }

    /** 主机创建/更新载荷（AssetHostSerializer 写入使用 snake_case 模型字段） */
    interface HostPayload {
      hostname: string;
      internal_ip: string;
      /** 外网IP，可选 */
      external_ip?: string | null;
      asset_type?: string;
      os_family: OsFamily | string;
      os_type?: string;
      image_name?: string;
      cpu_cores?: number;
      memory_mb?: number;
      system_disk_gb?: number;
      data_disk_gb?: number;
      environment?: string;
      region?: string;
      status?: HostStatus | string;
      asset_source?: number | null;
      owner_team?: string;
      app_code?: string;
      connection_type?: CredentialConnectionType | string;
      connection_port?: number;
      credential_ref?: number | null;
      metadata?: Record<string, unknown>;
    }

    /** 主机 Excel 导入结果（POST hosts/excel-import 响应） */
    interface HostImportSummary {
      total: number;
      created: number;
      skipped: number;
      invalid: Array<{ row: number; message: unknown }>;
      errors: Array<{ row: number; message: string }>;
    }

    /** 主机分组类型（HostGroup.GroupType） */
    type HostGroupType = 'static' | 'dynamic';

    /** 主机分组记录（HostGroupSerializer 输出，基础字段 snake_case） */
    interface HostGroupRecord {
      id: number;
      name: string;
      parent: number | null;
      /** serializer 附加："0" 表示无父级 */
      parentId: string;
      description: string;
      group_type: HostGroupType | string;
      match_rule: Record<string, unknown>;
      is_active: boolean;
      created_at: string | null;
      updated_at: string | null;
      /** serializer 附加只读字段 */
      hostCount: number;
    }

    /** 主机分组创建/更新载荷 */
    interface HostGroupPayload {
      name: string;
      parent?: number | null;
      description?: string;
      group_type?: HostGroupType;
      match_rule?: Record<string, unknown>;
      is_active?: boolean;
    }

    /** 主机分组列表查询参数 */
    interface HostGroupSearchParams {
      current: number;
      size: number;
      search?: string | null;
      groupType?: HostGroupType | null;
      isActive?: boolean | null;
    }

    /** 主机标签记录（HostTagSerializer 输出） */
    interface HostTagRecord {
      id: number;
      key: string;
      value: string;
      /** serializer 附加：key:value */
      label: string;
      created_at: string | null;
      updated_at: string | null;
    }

    /** 主机标签创建/更新载荷 */
    interface HostTagPayload {
      key: string;
      value: string;
    }

    /** 主机标签列表查询参数 */
    interface HostTagSearchParams {
      current: number;
      size: number;
      search?: string | null;
      key?: string | null;
      value?: string | null;
    }

    /** 资产来源类型（AssetSource.SourceType） */
    type AssetSourceType = 'manual' | 'cloud' | 'external_cmdb';

    /** 资产来源记录（AssetSourceSerializer 输出） */
    interface CloudConnectionResult {
      region: string;
      success: boolean;
      message: string;
      category?: string;
      errorCode?: string;
      requestId?: string;
      httpStatus?: number | null;
      detail?: string;
      suggestion?: string;
      checks?: Array<{
        key: string;
        label: string;
        success: boolean;
        message: string;
        errorCode?: string;
        requestId?: string;
        detail?: string;
        suggestion?: string;
      }>;
    }

    interface AssetSourceRecord {
      id: number;
      code: string;
      name: string;
      source_type: AssetSourceType | string;
      endpoint: string;
      description: string;
      is_active: boolean;
      cloud_provider: 'aliyun' | 'tencent' | 'vmware' | 'openstack' | 'pve' | '';
      regions: string[];
      has_credentials: boolean;
      masked_access_key_id?: string;
      metadata: Record<string, unknown>;
      last_synced_at: string | null;
      sync_interval_minutes?: number;
      last_sync_attempt_at?: string | null;
      sync_failure_alert?: { templateId?: number; receivers?: string };
      capabilities?: { fields: string[]; maxAssets: number; scope: string };
      created_at: string | null;
      updated_at: string | null;
    }

    /** 资产来源创建/更新载荷 */
    interface AssetSourcePayload {
      code: string;
      name: string;
      source_type: AssetSourceType;
      endpoint?: string;
      description?: string;
      is_active?: boolean;
      cloud_provider?: 'aliyun' | 'tencent' | 'vmware' | 'openstack' | 'pve' | '';
      regions?: string[];
      access_key_id?: string;
      access_key_secret?: string;
      metadata?: Record<string, unknown>;
      sync_interval_minutes?: number;
      sync_failure_alert?: { templateId?: number; receivers?: string };
    }

    /** 资产来源列表查询参数 */
    interface AssetSourceSearchParams {
      current: number;
      size: number;
      search?: string | null;
      sourceType?: AssetSourceType | null;
      excludeSourceType?: AssetSourceType | null;
      isActive?: boolean | null;
    }

    /** 资产同步状态（AssetSyncRecord.Status） */
    type AssetSyncStatus = 'queued' | 'running' | 'succeeded' | 'partial' | 'failed';

    interface AssetSyncPreview {
      confirmationToken?: string;
      total: number;
      create: number;
      update: number;
      unchanged?: number;
      invalid: number;
      rows: Array<{
        index: number;
        hostname: string;
        internalIp: string;
        sourceId: string;
        action: 'create' | 'update' | 'unchanged' | 'invalid';
        reason: string;
        changes?: { field: string; label: string; before: unknown; after: unknown }[];
        specs?: {
          cpu_cores?: number;
          memory_mb?: number;
          system_disk_gb?: number;
          data_disk_gb?: number;
          region?: string;
        };
      }>;
    }

    /** 资产同步记录（AssetSyncRecordSerializer 输出，只读） */
    interface AssetSyncRecordRecord {
      id: number;
      source: number;
      sourceName: string;
      status: AssetSyncStatus | string;
      task_id: string;
      started_at: string | null;
      finished_at: string | null;
      total_count: number;
      created_count: number;
      updated_count: number;
      skipped_count: number;
      error_message: string;
      trigger?: 'manual' | 'scheduled';
      observed_at?: string | null;
      collection_scope?: {
        provider?: string;
        regions?: string[];
        complete?: boolean;
        selectedCount?: number;
        readCount?: number;
      };
      changes?: Array<{
        hostId: number;
        sourceId: string;
        hostname: string;
        action: string;
        fields: Array<{ label: string; before: unknown; after: unknown }>;
      }>;
      created_at: string | null;
      updated_at: string | null;
    }

    /** 资产同步记录列表查询参数 */
    interface AssetSyncRecordSearchParams {
      current: number;
      size: number;
      search?: string | null;
      source?: number | null;
      status?: AssetSyncStatus | null;
    }

    /** 主机分组/标签关系（GET|POST hosts/{id}/relations） */
    interface HostRelations {
      groupIds: string[];
      tagIds: string[];
    }

    /** 主机资产左树节点行（根「全部主机」/ 主机分组统一结构） */
    interface HostTreeRow {
      /** 树节点唯一键：all | group-{id} */
      key: string;
      type: 'all' | 'group';
      id: number;
      name: string;
      description: string;
      /** static | dynamic */
      groupType: string;
      isActive: boolean;
      /** 含子分组的主机总数 */
      hostCount: number;
      children: HostTreeRow[];
    }

    /** 左树选中事件载荷 */
    interface HostTreeSelectPayload {
      /** 选中分组时为分组 id（含子分组级联过滤），根「全部主机」时为 null */
      groupId: number | null;
      node: HostTreeRow | null;
    }

    /** 主机列表查询范围（由左树选中派生） */
    interface HostListQuery {
      groupId?: number | null;
    }

    /** 探测状态（AssetProbe.Status） */
    type AssetProbeStatus = 'pending' | 'running' | 'success' | 'failed';

    /** 探测类型（AssetProbe.Kind） */
    type AssetProbeKind = 'connect' | 'facts';

    /** 资产探测记录（AssetProbeSerializer 输出，只读） */
    interface AssetProbeRecord {
      id: number;
      hostname: string;
      kind: AssetProbeKind | string;
      module: string;
      status: AssetProbeStatus | string;
      worker_pool: number | null;
      workerPoolName: string;
      attempt: number;
      result: Record<string, unknown>;
      error: string;
      created_at: string | null;
      updated_at: string | null;
    }

    /** 触发探测的响应（POST credential-refs/test-connection） */
    interface ProbeDispatchResult {
      probeId: number;
      status: AssetProbeStatus | string;
    }
  }
}
