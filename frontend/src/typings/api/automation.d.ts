declare namespace Api {
  /**
   * namespace Automation
   *
   * 自动化资源域：命令原子（command/script/playbook/module 四类资源）、
   * 工作流模板与版本、API 端点、Jenkins 服务、通知模板。
   * 对外统一 camelCase：DRF 序列化器的 snake_case 由 API 层（service/api/automation.ts）
   * 做顶层 key 转换；嵌套业务 JSON（default_vars/argument_schema/config 等）内部保持用户数据原样。
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
      resourceKind: ResourceKind | string;
      description: string;
      status: AtomStatus | string;
      riskLevel: RiskLevel | string;
      createdAt: string | null;
      updatedAt: string | null;
      /** serializer 附加只读字段 */
      latestVersion: number | null;
      publishedVersion: number | null;
      draftVersion: number | null;
      /** 已发布版本的内容（Module 页用于展示模块短名） */
      publishedContent: string | null;
      publishedModuleName?: string | null;
      versionCount: number;
      runCount: number;
      lastRunAt: string | null;
      nodeCount: number;
      /** 创建人用户名（serializer 附加只读字段） */
      createdByName: string | null;
    }

    /** 命令原子创建/更新载荷 */
    interface CommandPayload {
      name: string;
      code: string;
      category?: string;
      resourceKind?: ResourceKind;
      description?: string;
      status?: AtomStatus;
      riskLevel?: RiskLevel;
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

    interface ModuleParameterDoc {
      name: string;
      description: string;
    }

    /** 命令版本记录（CommandVersionSerializer 输出） */
    interface CommandVersionRecord {
      id: number;
      command: number;
      version: number;
      status: VersionStatus | string;
      commandType: CommandType | string;
      content: string;
      /** 独立 Module 字段；可选用于兼容旧后端 DTO */
      moduleName?: string;
      parameterDocs?: ModuleParameterDoc[];
      argumentSchema: Record<string, unknown>;
      defaultVars: Record<string, unknown>;
      outputExtractors: unknown[];
      timeoutSeconds: number;
      becomeEnabled: boolean;
      checkModeSupported: boolean;
      /** 版本备注 */
      remark: string;
      publishedAt: string | null;
      createdAt: string | null;
    }

    /** 命令版本创建载荷 */
    interface CommandVersionPayload {
      command: number;
      commandType: CommandType;
      content?: string;
      moduleName?: string;
      parameterDocs?: ModuleParameterDoc[];
      timeoutSeconds?: number;
      becomeEnabled?: boolean;
      checkModeSupported?: boolean;
      argumentSchema?: Record<string, unknown>;
      defaultVars?: Record<string, unknown>;
      outputExtractors?: unknown[];
      /** 版本备注 */
      remark?: string;
    }

    /** 工作流模板记录（WorkflowTemplateSerializer 输出） */
    interface WorkflowTemplateRecord {
      id: number;
      name: string;
      code: string;
      description: string;
      failureAlert: { templateId: number; receivers: string } | Record<string, never>;
      status: AtomStatus | string;
      ownerTeam: string;
      createdAt: string | null;
      updatedAt: string | null;
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
      failureAlert?: { templateId: number; receivers: string } | Record<string, never>;
      status?: AtomStatus;
      ownerTeam?: string;
    }

    /** 工作流版本记录（WorkflowVersionSerializer 输出，蛇形键已转驼峰） */
    interface WorkflowVersionRecord {
      id: number;
      workflow: number;
      version: number;
      status: VersionStatus | string;
      inputSchema: Record<string, unknown> | null;
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
      workflowVersion: number;
      nodeKey: string;
      name: string;
      nodeType: string;
      commandVersion: number | null;
      resourceType: string;
      config: Record<string, unknown>;
      orderIndex: number;
      timeoutSeconds: number | null;
      failurePolicy: 'stop' | 'ignore' | 'retry' | string;
      continueOnError: boolean;
      /** serializer 附加只读字段 */
      commandName: string;
    }

    /** 工作流边记录（WorkflowEdgeSerializer 输出） */
    interface WorkflowEdgeRecord {
      id: number;
      workflowVersion: number;
      edgeKey: string;
      sourceNode: number;
      targetNode: number;
      conditionExpression: string;
      isDefault: boolean;
      orderIndex: number;
    }

    /** API 端点记录（ApiEndpointSerializer 输出，secret 为脱敏占位） */
    interface ApiEndpointRecord {
      id: number;
      name: string;
      description: string;
      method: string;
      url: string;
      queryParams: Record<string, unknown>;
      headers: Record<string, unknown>;
      bodyType: 'none' | 'json' | 'form' | 'raw' | string;
      body: string;
      authType: 'none' | 'basic' | 'bearer' | 'api_key' | string;
      username: string;
      /** 脱敏后的密钥占位 */
      secret: string;
      apiKeyName: string;
      apiKeyLocation: string;
      successRules: Record<string, unknown>;
      outputExtractors: unknown[];
      timeoutSeconds: number;
      verifySsl: boolean;
      isActive: boolean;
      createdAt: string | null;
      updatedAt: string | null;
    }

    /** API 端点创建/更新载荷（secret 为 write_only 明文） */
    interface ApiEndpointPayload {
      name: string;
      description?: string;
      method?: string;
      url: string;
      headers?: Record<string, unknown>;
      queryParams?: Record<string, unknown>;
      bodyType?: 'none' | 'json' | 'form' | 'raw';
      body?: string;
      successRules?: Record<string, unknown>;
      authType?: 'none' | 'basic' | 'bearer' | 'api_key';
      username?: string;
      secret?: string;
      apiKeyName?: string;
      apiKeyLocation?: 'header' | 'query';
      timeoutSeconds?: number;
      verifySsl?: boolean;
      isActive?: boolean;
    }

    /** Jenkins 服务记录（JenkinsServerSerializer 输出） */
    interface JenkinsServerRecord {
      id: number;
      name: string;
      baseUrl: string;
      username: string;
      /** 脱敏后的 token 占位 */
      secret: string;
      verifySsl: boolean;
      isActive: boolean;
      createdAt: string | null;
      updatedAt: string | null;
    }

    /** Jenkins 服务创建/更新载荷（secret 为 write_only 明文 token） */
    interface JenkinsServerPayload {
      name: string;
      baseUrl: string;
      username?: string;
      secret?: string;
      verifySsl?: boolean;
      isActive?: boolean;
    }

    /** Git 仓库记录（GitRepositorySerializer 输出） */
    interface GitRepositoryRecord {
      id: number;
      name: string;
      repoUrl: string;
      username: string;
      branch: string;
      verifySsl: boolean;
      isActive: boolean;
      createdAt: string | null;
      updatedAt: string | null;
    }

    /** Git 仓库创建/更新载荷（secret 为 write_only 明文令牌） */
    interface GitRepositoryPayload {
      name: string;
      repoUrl: string;
      username?: string;
      branch?: string;
      secret?: string;
      verifySsl?: boolean;
      isActive?: boolean;
    }

    /** Git 仓库文件列表条目 */
    interface GitRepoFileEntry {
      ref: string;
      files: string[];
    }

    /** Git 仓库文件加载结果 */
    interface GitRepoLoadResult {
      ref: string;
      name: string;
      content: string;
    }

    /** 通知模板记录（NotificationTemplateSerializer 输出） */
    interface NotificationTemplateRecord {
      id: number;
      name: string;
      code: string;
      description: string;
      channel: number | null;
      subjectTemplate: string;
      bodyTemplate: string;
      receiverTemplate: string;
      isActive: boolean;
      createdAt: string | null;
      updatedAt: string | null;
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
      subjectTemplate?: string;
      bodyTemplate?: string;
      receiverTemplate?: string;
      isActive?: boolean;
    }

    /** 通知渠道记录（NotificationChannelSerializer 输出，notification 页渠道下拉用） */
    interface NotificationChannelRecord {
      id: number;
      name: string;
      channelType: 'webhook' | 'wecom' | 'dingtalk' | 'feishu' | 'email';
      config: Record<string, unknown>;
      secret: string;
      hasSigningSecret: boolean;
      isActive: boolean;
    }

    interface NotificationChannelPayload {
      name: string;
      channelType: NotificationChannelRecord['channelType'];
      secret?: string;
      signingSecret?: string;
      config?: Record<string, unknown>;
      isActive: boolean;
    }

    type NotificationScenario = 'failure' | 'workflow' | 'asset_sync' | 'provisioning' | 'security';

    interface NotificationVariable {
      expression: string;
      label: string;
      example: unknown;
      source: string;
    }

    interface NotificationVariableCatalog {
      variables: NotificationVariable[];
      sampleContext: Record<string, unknown>;
      workflowVersions: Pick<WorkflowVersionRecord, 'id' | 'workflowName' | 'version'>[];
    }

    interface NotificationSample {
      scenario: NotificationScenario;
      workflowVersionId: number | null;
      sampleContext: Record<string, unknown>;
    }

    interface NotificationPreviewPayload extends NotificationSample {
      subjectTemplate: string;
      bodyTemplate: string;
      receiverTemplate: string;
    }

    interface NotificationPreviewResult {
      valid: boolean;
      errors: Partial<Record<'subjectTemplate' | 'bodyTemplate' | 'receiverTemplate', string>>;
      subject: string;
      body: string;
      receivers: string;
    }

    interface NotificationRecord {
      id: number;
      templateName: string;
      channelName: string;
      status: 'pending' | 'sending' | 'success' | 'failed';
      subject: string;
      failureReason: string;
      sentAt: string | null;
      workflowRunId: number | null;
      attemptCount: number;
      nextRetryAt: string | null;
    }

    /** Jenkins 任务记录（JenkinsJobSerializer 输出，流程编排 jenkins 步骤引用） */
    interface JenkinsJobRecord {
      id: number;
      server: number;
      name: string;
      url: string;
      color: string;
      parameters: unknown[];
      isActive: boolean;
      lastSyncedAt: string | null;
      createdAt: string | null;
      updatedAt: string | null;
      /** serializer 附加只读字段 */
      serverName: string;
    }

    /** ============ 工作流图协议（graph 接口请求/响应） ============ */

    /** Jenkins 任务参数定义（parameters 探测接口返回） */
    interface JenkinsJobParameter {
      name: string;
      type: string;
      default: string | number | boolean | null;
      choices: string[];
    }

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
      inputSchema?: Record<string, unknown>;
    }
  }
}
