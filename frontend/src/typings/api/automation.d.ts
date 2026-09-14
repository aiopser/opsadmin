declare namespace Api {
  /**
   * namespace Automation
   *
   * 自动化资源域：命令原子（command/script/playbook/module 四类 resource_kind）、
   * 工作流模板与版本、API 端点、Jenkins 服务、通知模板。
   * 序列化器 fields="__all__" 输出 snake_case，附加展示字段为驼峰。
   */
  namespace Automation {
    /** 节点资源分类（CommandAtom.ResourceKind） */
    type ResourceKind = 'command' | 'script' | 'playbook' | 'module';

    /** 命令/模板状态（CommandAtom.Status / WorkflowTemplate.Status） */
    type AtomStatus = 'draft' | 'published' | 'disabled';

    /** 风险等级（CommandAtom.RiskLevel） */
    type RiskLevel = 'low' | 'medium' | 'high';

    /** 版本状态（CommandVersion.Status / WorkflowVersion.Status） */
    type VersionStatus = 'draft' | 'published' | 'archived';

    /** 版本执行类型（CommandVersion.CommandType） */
    type CommandType = 'linux_shell' | 'windows_powershell' | 'python' | 'http_request' | 'ansible_module' | 'playbook';

    /** 命令原子记录（CommandAtomSerializer 输出） */
    interface CommandRecord {
      id: number;
      name: string;
      code: string;
      category: string;
      resource_kind: ResourceKind | string;
      description: string;
      status: AtomStatus | string;
      risk_level: RiskLevel | string;
      created_at: string | null;
      updated_at: string | null;
      /** serializer 附加只读字段 */
      latestVersion: number | null;
      publishedVersion: number | null;
      versionCount: number;
      runCount: number;
      lastRunAt: string | null;
      nodeCount: number;
    }

    /** 命令原子创建/更新载荷 */
    interface CommandPayload {
      name: string;
      code: string;
      category?: string;
      resource_kind?: ResourceKind;
      description?: string;
      status?: AtomStatus;
      risk_level?: RiskLevel;
    }

    /** 命令列表查询参数（filterset: status/risk_level/category/resource_kind） */
    interface CommandSearchParams {
      current: number;
      size: number;
      search?: string | null;
      status?: AtomStatus | null;
      riskLevel?: RiskLevel | null;
      category?: string | null;
      resourceKind?: ResourceKind | null;
    }

    /** 命令版本记录（CommandVersionSerializer 输出） */
    interface CommandVersionRecord {
      id: number;
      command: number;
      version: number;
      status: VersionStatus | string;
      command_type: CommandType | string;
      content: string;
      argument_schema: Record<string, unknown>;
      default_vars: Record<string, unknown>;
      output_extractors: unknown[];
      timeout_seconds: number;
      become_enabled: boolean;
      check_mode_supported: boolean;
      published_at: string | null;
      created_at: string | null;
    }

    /** 命令版本创建载荷 */
    interface CommandVersionPayload {
      command: number;
      command_type: CommandType;
      content: string;
      timeout_seconds?: number;
      argument_schema?: Record<string, unknown>;
      default_vars?: Record<string, unknown>;
      output_extractors?: unknown[];
    }

    /** 工作流模板记录（WorkflowTemplateSerializer 输出） */
    interface WorkflowTemplateRecord {
      id: number;
      name: string;
      code: string;
      description: string;
      status: AtomStatus | string;
      owner_team: string;
      created_at: string | null;
      updated_at: string | null;
      /** serializer 附加只读字段 */
      latestVersion: number | null;
      /** 当前已发布版本号（无则为 null） */
      publishedVersion: number | null;
      /** 当前草稿版本号（无则为 null） */
      draftVersion: number | null;
    }

    /** 工作流模板创建/更新载荷 */
    interface WorkflowTemplatePayload {
      name: string;
      code: string;
      description?: string;
      status?: AtomStatus;
      owner_team?: string;
    }

    /** 工作流版本记录（WorkflowVersionSerializer 输出，蛇形键已转驼峰） */
    interface WorkflowVersionRecord {
      id: number;
      workflow: number;
      version: number;
      status: VersionStatus | string;
      inputSchema: Record<string, unknown> | null;
      globalVars?: Record<string, unknown> | null;
      targetSelectorSchema?: Record<string, unknown> | null;
      editorMode: string;
      workflowName: string;
      workflowCode: string;
      publishedAt: string | null;
      createdAt: string | null;
      updatedAt?: string | null;
    }

    /** 工作流节点记录（WorkflowNodeSerializer 输出） */
    interface WorkflowNodeRecord {
      id: number;
      workflow_version: number;
      node_key: string;
      name: string;
      node_type: string;
      command_version: number | null;
      resource_type: string;
      config: Record<string, unknown>;
      order_index: number;
      timeout_seconds: number | null;
      failure_policy: 'stop' | 'ignore' | 'retry' | string;
      continue_on_error: boolean;
      /** serializer 附加只读字段 */
      commandName: string;
    }

    /** 工作流边记录（WorkflowEdgeSerializer 输出） */
    interface WorkflowEdgeRecord {
      id: number;
      workflow_version: number;
      edge_key: string;
      source_node: number;
      target_node: number;
      condition_expression: string;
      is_default: boolean;
      order_index: number;
    }

    /** API 端点记录（ApiEndpointSerializer 输出，secret 为脱敏占位） */
    interface ApiEndpointRecord {
      id: number;
      name: string;
      description: string;
      method: string;
      url: string;
      query_params: Record<string, unknown>;
      headers: Record<string, unknown>;
      body_type: 'none' | 'json' | 'form' | 'raw' | string;
      body: string;
      auth_type: 'none' | 'basic' | 'bearer' | 'api_key' | string;
      username: string;
      /** 脱敏后的密钥占位 */
      secret: string;
      api_key_name: string;
      api_key_location: string;
      success_rules: unknown[];
      output_extractors: unknown[];
      timeout_seconds: number;
      verify_ssl: boolean;
      is_active: boolean;
      created_at: string | null;
      updated_at: string | null;
    }

    /** API 端点创建/更新载荷（secret 为 write_only 明文） */
    interface ApiEndpointPayload {
      name: string;
      description?: string;
      method?: string;
      url: string;
      headers?: Record<string, unknown>;
      query_params?: Record<string, unknown>;
      body_type?: 'none' | 'json' | 'form' | 'raw';
      body?: string;
      auth_type?: 'none' | 'basic' | 'bearer' | 'api_key';
      username?: string;
      secret?: string;
      timeout_seconds?: number;
      verify_ssl?: boolean;
      is_active?: boolean;
    }

    /** Jenkins 服务记录（JenkinsServerSerializer 输出） */
    interface JenkinsServerRecord {
      id: number;
      name: string;
      base_url: string;
      username: string;
      /** 脱敏后的 token 占位 */
      secret: string;
      verify_ssl: boolean;
      is_active: boolean;
      created_at: string | null;
      updated_at: string | null;
    }

    /** Jenkins 服务创建/更新载荷（secret 为 write_only 明文 token） */
    interface JenkinsServerPayload {
      name: string;
      base_url: string;
      username?: string;
      secret?: string;
      verify_ssl?: boolean;
      is_active?: boolean;
    }

    /** 通知模板记录（NotificationTemplateSerializer 输出） */
    interface NotificationTemplateRecord {
      id: number;
      name: string;
      code: string;
      description: string;
      channel: number | null;
      subject_template: string;
      body_template: string;
      receiver_template: string;
      is_active: boolean;
      created_at: string | null;
      updated_at: string | null;
      /** serializer 附加只读字段 */
      channelName: string;
      channelType: string;
    }

    /** 通知模板创建/更新载荷 */
    interface NotificationTemplatePayload {
      name: string;
      code: string;
      description?: string;
      channel?: number | null;
      subject_template?: string;
      body_template?: string;
      receiver_template?: string;
      is_active?: boolean;
    }

    /** 通知渠道记录（NotificationChannelSerializer 输出，notification 页渠道下拉用） */
    interface NotificationChannelRecord {
      id: number;
      name: string;
      channel_type: 'webhook' | 'wecom' | 'dingtalk' | 'email' | string;
      is_active: boolean;
    }

    /** Jenkins 任务记录（JenkinsJobSerializer 输出，流程编排 jenkins 步骤引用） */
    interface JenkinsJobRecord {
      id: number;
      server: number;
      name: string;
      url: string;
      color: string;
      parameters: unknown[];
      is_active: boolean;
      last_synced_at: string | null;
      created_at: string | null;
      updated_at: string | null;
      /** serializer 附加只读字段 */
      serverName: string;
    }

    /** ============ 工作流图协议（graph 接口请求/响应） ============ */

    /** 图节点（保存与读取同构；commandVersion{Id}、resourceType{Id} 用于绑定资源） */
    interface GraphNode {
      id: string;
      name: string;
      type: string;
      /** Ansible 类节点绑定已发布命令版本 */
      commandVersionId?: number | null;
      /** 后端附加：绑定的命令版本摘要（含 commandId/commandName，用于回显） */
      commandVersion?: {
        id: number;
        version: number;
        command_type: string;
        content: string;
        default_vars: Record<string, unknown>;
        argument_schema: unknown;
        timeout_seconds: number;
        become_enabled: boolean;
        check_mode_supported: boolean;
        output_extractors: unknown[];
        commandId: number;
        commandName: string;
      } | null;
      /** api/jenkins/notify 节点绑定资源类型与资源 ID */
      resourceType?: string | null;
      resourceId?: number | null;
      /** 节点执行配置（hostStrategy/forks/content/module 等） */
      config?: Record<string, unknown>;
      /** 上游输出到节点输入的映射（Jinja2 模板） */
      inputMapping?: Record<string, unknown>;
      inputSchema?: Record<string, unknown> | null;
      outputSchema?: Record<string, unknown> | null;
      retryPolicy?: Record<string, unknown> | null;
      failurePolicy?: 'stop' | 'ignore' | string;
      continueOnError?: boolean;
      timeoutSeconds?: number | null;
      position?: { x: number; y: number };
    }

    /** 图边（顺序编排保存时由步骤顺序生成） */
    interface GraphEdge {
      id?: string;
      source: string;
      target: string;
      condition?: string | null;
      isDefault?: boolean;
    }

    /** graph 接口载荷 */
    interface WorkflowGraph {
      nodes: GraphNode[];
      edges: GraphEdge[];
      globalVars?: Record<string, unknown>;
      inputSchema?: Record<string, unknown>;
    }
  }
}
