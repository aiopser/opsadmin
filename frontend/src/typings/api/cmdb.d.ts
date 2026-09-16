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
      primaryIp: string;
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
      connectionType: string;
      connectionPort: number;
      appCode: string;
      ownerTeam: string;
      groupIds: string[];
      credentialRef: number | null;
      credentialRefName: string;
      defaultGateway: number | null;
      defaultGatewayName: string;
      serviceNode: number | null;
      serviceNodeName: string;
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

    /** 主机列表查询参数（后端 filterset: os_family/environment/service_node/status/app_code，另支持 business 与 service_node__in） */
    interface HostSearchParams {
      current: number;
      size: number;
      search?: string | null;
      osFamily?: OsFamily | null;
      status?: HostStatus | null;
      environment?: string | null;
      /** 按业务过滤（service_node__business） */
      business?: number | null;
      /** 按服务树节点集合过滤（service_node__in，含子树） */
      serviceNodeIds?: number[] | null;
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
      primary_ip: string;
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
      service_node?: number | null;
      asset_source?: number | null;
      owner_team?: string;
      app_code?: string;
      connection_type?: CredentialConnectionType | string;
      connection_port?: number;
      credential_ref?: number | null;
      default_gateway?: number | null;
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

    /** 业务系统记录（BusinessSerializer 输出，fields="__all__" snake_case） */
    interface BusinessRecord {
      id: number;
      code: string;
      name: string;
      description: string;
      is_active: boolean;
      created_at: string | null;
      updated_at: string | null;
      /** serializer 附加只读字段 */
      hostCount: number;
    }

    /** 业务系统创建/更新载荷 */
    interface BusinessPayload {
      code: string;
      name: string;
      description?: string;
      is_active?: boolean;
    }

    /** 业务系统列表查询参数 */
    interface BusinessSearchParams {
      current: number;
      size: number;
      search?: string | null;
      code?: string | null;
      isActive?: boolean | null;
    }

    /** 服务树节点类型（ServiceTreeNode.NodeType） */
    type ServiceNodeType = 'environment' | 'region' | 'module';

    /** 服务树节点记录（ServiceTreeNodeSerializer 输出） */
    interface ServiceTreeNodeRecord {
      id: number;
      business: number;
      businessName: string;
      parent: number | null;
      parentName: string;
      code: string;
      name: string;
      node_type: ServiceNodeType | string;
      description: string;
      sort_order: number;
      is_active: boolean;
      metadata: Record<string, unknown>;
      created_at: string | null;
      updated_at: string | null;
      /** serializer 附加只读字段 */
      hostCount: number;
    }

    /** 服务树节点创建/更新载荷（environment 不可有父级；region 挂 environment；module 挂 region） */
    interface ServiceTreeNodePayload {
      business: number;
      parent?: number | null;
      code: string;
      name: string;
      node_type: ServiceNodeType;
      description?: string;
      sort_order?: number;
      is_active?: boolean;
    }

    /** 服务树节点列表查询参数 */
    interface ServiceTreeNodeSearchParams {
      current: number;
      size: number;
      search?: string | null;
      business?: number | null;
      nodeType?: ServiceNodeType | null;
      isActive?: boolean | null;
    }

    /** 资产来源类型（AssetSource.SourceType） */
    type AssetSourceType = 'manual' | 'cloud' | 'external_cmdb';

    /** 资产来源记录（AssetSourceSerializer 输出） */
    interface AssetSourceRecord {
      id: number;
      code: string;
      name: string;
      source_type: AssetSourceType | string;
      endpoint: string;
      description: string;
      is_active: boolean;
      metadata: Record<string, unknown>;
      last_synced_at: string | null;
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
      metadata?: Record<string, unknown>;
    }

    /** 资产来源列表查询参数 */
    interface AssetSourceSearchParams {
      current: number;
      size: number;
      search?: string | null;
      sourceType?: AssetSourceType | null;
      isActive?: boolean | null;
    }

    /** 资产同步状态（AssetSyncRecord.Status） */
    type AssetSyncStatus = 'queued' | 'running' | 'succeeded' | 'failed';

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
      payload: unknown[];
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

    /** 主机资产左树节点行（业务根节点 / 服务树节点统一结构） */
    interface HostTreeRow {
      /** 树节点唯一键：business-{id} | node-{id} */
      key: string;
      type: 'business' | 'node';
      id: number;
      name: string;
      code: string;
      /** 服务树节点类型，业务根节点为空串 */
      nodeType: string;
      description: string;
      sortOrder: number;
      /** 含子树的主机总数 */
      hostCount: number;
      businessId: number;
      isActive: boolean;
      children: HostTreeRow[];
    }

    /** 左树选中事件载荷 */
    interface HostTreeSelectPayload {
      /** 选中业务根节点时为业务 id，否则为 null */
      business: number | null;
      /** 选中服务树节点时为其自身与全部子孙节点 id，否则为 null */
      serviceNodeIds: number[] | null;
      node: HostTreeRow | null;
    }

    /** 主机列表查询范围（由左树选中派生） */
    interface HostListQuery {
      business?: number | null;
      serviceNodeIds?: number[] | null;
    }

    /** 主机页右侧「管理」抽屉 key */
    type HostManageKey = 'host-group' | 'tag' | 'asset-source' | 'sync-record';

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
