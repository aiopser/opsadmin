declare namespace Api {
  /**
   * namespace Jobs
   *
   * 任务执行域：运行记录、节点状态、主机结果、事件流（T13/T14 契约）。
   * 字段与后端 apps/jobs 序列化器输出一一对应（snake_case 原样）。
   */
  namespace Jobs {
    /** 运行状态机（jobs.WorkflowRun.Status） */
    type RunStatus =
      | 'pending'
      | 'queued'
      | 'running'
      | 'waiting'
      | 'cancel_requested'
      | 'success'
      | 'failed'
      | 'timeout'
      | 'canceled';

    /** 运域：task / ops */
    type RunDomain = 'task' | 'ops';

    /** 执行类型 */
    type ExecutionKind = 'workflow' | 'quick_command' | 'playbook' | 'module';

    /** 触发方式 */
    type TriggerType = 'manual' | 'api' | 'scheduled';

    /** T04 非敏感目标快照 */
    interface TargetSnapshot {
      hostId: number;
      hostname: string;
      address: string;
      port: number;
      connectionType: string;
      credentialRefId: number | null;
      variables: Record<string, unknown>;
    }

    /** 运行记录（WorkflowRunSerializer 输出，剔除加密输入） */
    interface TargetSelector {
      hostIds: number[];
      groupIds: number[];
      tagIds: number[];
    }

    interface RunRecord {
      targetSelector: TargetSelector;
      id: number;
      workflowVersionId: number | null;
      workerPoolId: number;
      triggeredById: number | null;
      runDomain: RunDomain;
      executionKind: ExecutionKind;
      triggerType: TriggerType;
      scheduledJobId: number | null;
      scheduledJobName: string;
      status: RunStatus;
      inputVars: Record<string, unknown>;
      targetSnapshot: TargetSnapshot[];
      contextVars: Record<string, unknown>;
      executionSettings: ExecutionSettingsSnapshot;
      graphSnapshot: Record<string, unknown>;
      celeryTaskId: string;
      workerName: string;
      timeoutSeconds: number;
      queueTimeoutSeconds: number;
      queueDeadlineAt: string | null;
      startedAt: string | null;
      finishedAt: string | null;
      durationMs: number | null;
      failureReason: string;
      eventSequence: number;
      createdAt: string;
      updatedAt: string;
      /** serializer 追加的展示字段 */
      workflowName: string;
      /** 运行显示名（快速执行可自定义/自动生成，普通工作流回退模板名） */
      name?: string;
      workflowVersion: number | null;
      workerPoolName: string;
      triggeredByName: string;
      targetCount: number;
      /** 全部主机结果中失败/不可达台数（serializer 追加展示字段） */
      failedHostCount?: number;
      /** 来源任务单（由任务单运行时写入） */
      ticketId?: number | null;
      ticketName?: string | null;
    }

    /** 运行列表查询参数 */
    interface RunSearchParams {
      current: number;
      size: number;
      status?: RunStatus | null;
      executionKind?: ExecutionKind | null;
      triggerType?: TriggerType | null;
      scheduledJobId?: number | null;
      runDomain?: RunDomain | null;
      search?: string | null;
      /** 按流程模板 ID 过滤，覆盖该模板的全部版本 */
      workflowId?: number | null;
      /** 按来源任务单过滤 */
      ticketId?: number | null;
    }

    /** 节点运行状态（NodeRun.Status） */
    type NodeStatus =
      | 'pending'
      | 'queued'
      | 'running'
      | 'success'
      | 'failed'
      | 'skipped'
      | 'ignored'
      | 'canceled'
      | 'timeout';

    /** 节点运行记录（NodeRunSerializer 输出） */
    interface NodeRunRecord {
      id: number;
      workflowRun: number;
      workflowNode: number | null;
      commandVersion: number | null;
      nodeKey: string;
      nodeName: string;
      nodeType: string;
      status: NodeStatus;
      attemptCount: number;
      exitCode: number | null;
      configSnapshot: Record<string, unknown>;
      inputVars: Record<string, unknown>;
      outputVars: Record<string, unknown>;
      startedAt: string | null;
      finishedAt: string | null;
      durationMs: number | null;
      failureReason: string;
      /** ansible-runner 原生控制台输出（脱敏截断后存储），新执行才有 */
      consoleOutput?: string;
      createdAt: string;
      updatedAt: string;
      /** serializer 追加的展示字段 */
      commandName: string;
    }

    /** 主机结果状态（HostRunResult.Status） */
    type HostResultStatus =
      | 'pending'
      | 'running'
      | 'ok'
      | 'changed'
      | 'failed'
      | 'unreachable'
      | 'canceled'
      | 'skipped';

    /** 主机结果记录（HostRunResultSerializer 输出） */
    interface HostResultRecord {
      id: number;
      nodeRun: number;
      hostKey: string;
      hostId: number | null;
      hostname: string;
      ip: string;
      status: HostResultStatus;
      lastSequence: number;
      attemptId: number | null;
      stdout: string;
      stderr: string;
      rawEventData: Record<string, unknown>;
      changed: boolean;
      exitCode: number;
      startedAt: string | null;
      finishedAt: string | null;
      createdAt: string;
      updatedAt: string;
    }

    /** 主机结果分页列表只返回排障摘要，输出按主机单独读取。 */
    type HostResultSummary = Pick<
      HostResultRecord,
      'id' | 'hostname' | 'ip' | 'status' | 'changed' | 'exitCode' | 'startedAt' | 'finishedAt'
    >;

    interface HostResultPage {
      records: HostResultSummary[];
      current: number;
      size: number;
      total: number;
      summary: { total: number; success: number; failed: number };
    }

    /** 事件日志（JobEventLogSerializer 输出） */
    interface RunEvent {
      id: number;
      sequence: number;
      eventKey: string;
      attemptId: number | null;
      workflowRun: number;
      nodeRun: number | null;
      hostId: number | null;
      eventType: string;
      message: string;
      payload: Record<string, unknown>;
      createdAt: string;
      updatedAt: string;
      /** serializer 追加的规范化字段 */
      normalizedEventType: string;
      runnerEvent: Record<string, unknown>;
    }

    /** 唯一事件接口的游标分页响应（T10 契约） */
    interface RunEventPage {
      events: RunEvent[];
      nextCursor: number;
      hasMore: boolean;
      terminal: boolean;
      snapshotVersion: number;
    }

    /** WS 票据（realtime-ticket 子资源输出） */
    interface RealtimeTicket {
      ticket: string;
      expires_in: number;
    }

    /** 快速执行提交参数（QuickCommandRunCreateSerializer） */
    interface QuickCommandRunPayload {
      extraVars?: Record<string, unknown>;
      expectedTargetIds?: number[];
      expectedTargetFingerprint?: string;
      expectedConfirmationFingerprint?: string;
      executionRequestId?: string;
      commandType: 'linux_shell' | 'windows_powershell' | 'python';
      commandContent: string;
      hostIds: number[];
      workerPoolId: number | null;
      sourceCommandVersionId?: number | null;
      gatewayId?: number | null;
      hostStrategy?: 'parallel' | 'serial' | 'rolling' | null;
      forks?: number | null;
      serialBatch?: number | null;
      maxFailPercentage?: number | null;
      timeoutSeconds?: number | null;
      /** 作业名称：留空由后端自动生成（脚本执行-时间戳） */
      name?: string;
    }

    interface PlaybookRunPayload {
      extraVars?: Record<string, unknown>;
      expectedTargetIds?: number[];
      expectedTargetFingerprint?: string;
      expectedConfirmationFingerprint?: string;
      executionRequestId?: string;
      playbookVersionId?: number | null;
      playbookContent: string;
      playbookName?: string;
      inputVars?: Record<string, unknown>;
      hostIds: number[];
      workerPoolId: number | null;
      gatewayId?: number | null;
      hostStrategy?: 'parallel' | 'serial' | 'rolling' | null;
      forks?: number | null;
      serialBatch?: number | null;
      maxFailPercentage?: number | null;
      timeoutSeconds?: number | null;
      /** 作业名称：留空由后端自动生成（剧本执行-时间戳） */
      name?: string;
    }

    interface ModuleRunPayload {
      extraVars?: Record<string, unknown>;
      expectedTargetIds?: number[];
      expectedTargetFingerprint?: string;
      expectedConfirmationFingerprint?: string;
      executionRequestId?: string;
      /** 内容来源=资源库时的模块版本 ID（与 moduleName 二选一） */
      moduleVersionId?: number;
      /** 内容来源=在线编写时的模块名（如 shell / ansible.builtin.yum，与 moduleVersionId 二选一） */
      moduleName?: string;
      moduleArgs?: string;
      hostIds: number[];
      workerPoolId: number | null;
      gatewayId?: number | null;
      /** 主机执行策略（缺省继承执行引擎） */
      hostStrategy?: 'parallel' | 'serial' | 'rolling' | null;
      forks?: number | null;
      serialBatch?: number | null;
      maxFailPercentage?: number | null;
      timeoutSeconds?: number | null;
      /** 试运行（Ansible check mode，不做实际变更） */
      checkMode?: boolean;
      /** 作业名称：留空由后端自动生成（模块执行-时间戳） */
      name?: string;
    }

    /** 运行创建提交参数（WorkflowRunCreateSerializer，全部 camelCase） */
    interface WorkflowRunPayload {
      workflowVersionId: number;
      hostIds?: number[];
      groupIds?: number[];
      tagIds?: number[];
      inputVars?: Record<string, unknown>;
      workerPoolId?: number | null;
      /** 连接网关：留空全部直连，选定后所有 SSH 主机统一走该网关 */
      gatewayId?: number | null;
      /** parallel / serial / rolling（host_strategy 的驼峰字段名） */
      hostStrategy?: 'parallel' | 'serial' | 'rolling' | null;
      forks?: number | null;
      /** serial 策略批次大小（serial_batch） */
      serialBatch?: number | null;
      maxFailPercentage?: number | null;
      timeoutSeconds?: number | null;
      queueTimeoutSeconds?: number;
      /** 防止预览后分组/标签成员变化导致执行范围扩大 */
      expectedTargetIds?: number[];
      expectedTargetFingerprint?: string;
      expectedConfirmationFingerprint?: string;
      executionRequestId?: string;
    }

    interface RunPreview {
      executionRequestId: string;
      valid: boolean;
      workflowVersionId: number;
      workflowName: string;
      targetCount: number;
      targetFingerprint: string;
      confirmationFingerprint: string;
      targets: Array<{ hostId: number; hostname: string; address: string }>;
      steps: Array<{
        key: string;
        name: string;
        type: string;
        targetScope: 'all' | 'none';
        hostPolicySource: 'native' | 'step' | 'run' | 'none';
      }>;
      workerPoolId: number | null;
      workerPoolName: string;
      gatewayName: string;
      parameters: Array<{ name: string; value: string }>;
      contentSummary?: Array<{ name: string; value: string }>;
      hostStrategy: string;
    }

    interface WorkflowInputFieldOption {
      label?: string;
      value: string | number;
    }

    interface WorkflowInputField {
      name: string;
      label?: string;
      type: 'string' | 'text' | 'secret' | 'number' | 'integer' | 'boolean' | 'select' | 'multiselect' | 'host';
      required?: boolean;
      default?: string | number | boolean | Array<string | number>;
      /** select / multiselect 可选项 */
      options?: (string | number | WorkflowInputFieldOption)[];
    }

    interface WorkflowVersionOption {
      id: number;
      /** 所属流程模板 id（跳转编排页用） */
      workflow: number;
      version: number;
      workflowName: string;
      workflowCode: string;
      inputSchema: WorkflowInputField[] | { fields?: WorkflowInputField[] };
    }

    /** 资产主机（cmdb.AssetHost 精简，用于目标选择） */
    interface HostOption {
      id: number;
      hostname: string;
      internalIp: string;
      externalIp?: string | null;
      osFamily: string;
      isActive?: boolean;
      groupNames?: string[];
    }

    /** Worker 池（jobs.WorkerPool） */
    interface WorkerPoolOption {
      id: number;
      code: string;
      name: string;
      queueName: string;
      /** 部署地域，如 cn-east-1 / us-west-2；空表示未指定（不参与地域路由） */
      region: string;
      isActive: boolean;
      isDefault: boolean;
      executionKinds: string[];
    }

    /** Worker 池完整记录（WorkerPoolSerializer 输出，camelCase） */
    interface WorkerPoolRecord extends WorkerPoolOption {
      concurrencyLimit: number;
      createdAt: string;
      updatedAt: string;
    }

    /** Worker 池创建/更新载荷（serializer 字段名，source 映射到 snake_case 模型列） */
    interface WorkerPoolPayload {
      code: string;
      name: string;
      queueName: string;
      /** 部署地域，与主机 region 匹配时调度就近执行 */
      region?: string;
      isDefault?: boolean;
      isActive?: boolean;
      concurrencyLimit?: number;
      executionKinds?: string[];
    }

    /** 网关代理（jobs.Gateway，GatewaySerializer 输出 snake_case） */
    interface GatewayRecord {
      id: number;
      name: string;
      address: string;
      cloud: string;
      /** CIDR 网段列表（逗号分隔，如 10.0.0.0/8,172.16.0.0/12），目标地址命中时自动经该网关代理 */
      auth_type: 'password' | 'key';
      username: string;
      status: 'normal' | 'abnormal';
      last_tested_at: string | null;
      created_at: string;
      updated_at: string;
    }

    /** 网关创建/更新载荷（secret 为明文，服务端加密存储；编辑留空表示不修改） */
    interface GatewayPayload {
      name: string;
      address: string;
      cloud?: string;
      auth_type?: 'password' | 'key';
      username?: string;
      secret?: string;
    }

    /** 定时任务重叠策略（ScheduledJob.OverlapPolicy） */
    type ScheduleOverlapPolicy = 'skip' | 'allow' | 'queue';

    /** 定时任务错过策略（ScheduledJob.MisfirePolicy） */
    type ScheduleMisfirePolicy = 'fire' | 'skip';

    /** 定时任务调度类型（ScheduledJob.ScheduleType） */
    type ScheduleType = 'periodic' | 'once';

    /** 定时任务记录（ScheduledJobSerializer：fields="__all__" 蛇形 + 附加驼峰只读） */
    interface ScheduledJobRecord {
      id: number;
      name: string;
      workflow_version: number | null;
      worker_pool: number;
      host_ids: number[];
      group_ids: number[];
      tag_ids: number[];
      cron_expression: string;
      timezone: string;
      /** 周期性（cron）或一次性（run_at 触发一次） */
      schedule_type: ScheduleType;
      /** 一次性任务的计划执行时间 */
      run_at: string | null;
      /** 超过该时间后不再开始新的运行 */
      expires_at: string | null;
      remark: string;
      input_vars: Record<string, unknown>;
      host_strategy: 'parallel' | 'serial' | 'rolling' | null;
      forks: number | null;
      serial_batch: number | null;
      max_fail_percentage: number | null;
      timeout_seconds: number | null;
      queue_timeout_seconds: number;
      gateway: number | null;
      enabled: boolean;
      /** 上次运行仍活跃时的处理策略 */
      overlap_policy: ScheduleOverlapPolicy | string;
      /** 错过调度窗口（超过宽限期）后补跑还是跳过 */
      misfire_policy: ScheduleMisfirePolicy | string;
      misfire_grace_seconds: number;
      /** queue 策略下：等待上次运行结束后补投一次 */
      pending_dispatch: boolean;
      /** 最近一次跳过原因（overlap/misfire/派发被拒），成功派发后清空 */
      last_skip_reason: string;
      next_run_at: string | null;
      last_run_at: string | null;
      /** serializer 附加只读字段 */
      workflowName: string;
      workflowVersion: number | null;
      workerPoolName: string;
      lastRunId: number | null;
      lastRunStatus: RunStatus | null;
      /** 最近一次调度结果留痕（ScheduledJobOutcome） */
      lastOutcome: { outcome: string; reason: string; scheduledFor: string; runId: number | null } | null;
    }

    /** 定时任务创建/更新载荷 */
    interface ScheduledJobPayload {
      expectedTargetIds?: number[];
      expectedTargetFingerprint?: string;
      name: string;
      workflow_version: number;
      worker_pool?: number | null;
      host_ids: number[];
      group_ids: number[];
      tag_ids: number[];
      cron_expression?: string;
      timezone?: string;
      schedule_type?: ScheduleType;
      run_at?: string | null;
      expires_at?: string | null;
      remark?: string;
      input_vars?: Record<string, unknown>;
      host_strategy?: 'parallel' | 'serial' | 'rolling' | null;
      forks?: number | null;
      serial_batch?: number | null;
      max_fail_percentage?: number | null;
      timeout_seconds?: number | null;
      queue_timeout_seconds?: number;
      gateway?: number | null;
      enabled?: boolean;
      overlap_policy?: ScheduleOverlapPolicy;
      misfire_policy?: ScheduleMisfirePolicy;
      misfire_grace_seconds?: number;
    }

    /** 定时任务列表查询参数 */
    interface ScheduledJobSearchParams {
      current: number;
      size: number;
      search?: string | null;
      enabled?: boolean | null;
    }

    /** 任务单记录（WorkflowTaskTicketSerializer：camelCase） */
    interface TaskTicketRecord {
      id: number;
      name: string;
      remark: string;
      failureAlert: { templateId: number; receivers: string } | Record<string, never> | null;
      workflowVersionId: number | null;
      workflowName: string | null;
      workflowVersion: number | null;
      inputVars: Record<string, unknown>;
      hostIds: number[];
      groupIds: number[];
      tagIds: number[];
      workerPoolId: number | null;
      workerPoolName: string | null;
      gatewayId: number | null;
      gatewayName: string | null;
      hostStrategy: 'parallel' | 'serial' | 'rolling' | null;
      forks: number | null;
      serialBatch: number | null;
      maxFailPercentage: number | null;
      timeoutSeconds: number | null;
      runCount: number;
      lastRunId: number | null;
      lastRunStatus: RunStatus | null;
      lastRunStartedAt: string | null;
      createdByName: string | null;
      createdAt: string;
      updatedAt: string;
    }

    /** 任务单创建/更新载荷 */
    interface TaskTicketPayload {
      name: string;
      remark?: string;
      failureAlert?: { templateId: number; receivers: string } | Record<string, never> | null;
      workflowVersionId: number;
      hostIds: number[];
      groupIds: number[];
      tagIds: number[];
      workerPoolId?: number | null;
      gatewayId?: number | null;
      inputVars?: Record<string, unknown>;
      hostStrategy?: 'parallel' | 'serial' | 'rolling' | null;
      forks?: number | null;
      serialBatch?: number | null;
      maxFailPercentage?: number | null;
      timeoutSeconds?: number | null;
    }

    /** 任务单列表查询参数 */
    interface TaskTicketSearchParams {
      current: number;
      size: number;
      search?: string | null;
    }

    /** 按领域统计当日运行（GET /api/v1/jobs/dashboard/stats） */
    interface DashboardStats {
      todayExecutions: number;
      finishedExecutions: number;
      successRate: number | null;
      avgResponseSeconds: number | null;
      blockedCommands: number;
      scheduledExecutions: number;
    }

    /** 作业执行全局默认参数（实际执行可由流程节点或运行配置覆盖） */
    type ExecutionSettingSource = 'global' | 'run' | 'step' | 'resource' | 'serial' | 'default';
    interface ExecutionSettingsValues {
      hostPolicy?: 'native' | 'platform';
      hostStrategy: 'parallel' | 'serial' | 'rolling';
      forks: number;
      serialBatch: number;
      maxFailPercentage: number;
      timeoutSeconds: number;
      checkMode: boolean;
    }
    interface ExecutionSettingsEntry {
      values: ExecutionSettingsValues;
      sources: Record<Exclude<keyof ExecutionSettingsValues, 'hostPolicy'>, ExecutionSettingSource> & {
        hostPolicy?: ExecutionSettingSource;
      };
    }
    interface ExecutionSettingsSnapshot extends ExecutionSettingsEntry {
      nodes: Record<string, ExecutionSettingsEntry>;
    }

    interface EngineSettings {
      timeout: number;
      forks: number;
      host_strategy: 'parallel' | 'serial' | 'rolling';
      serial_batch: number;
      max_fail_percentage: number;
    }

    type SecurityMatchMode = 'contains' | 'exact' | 'prefix' | 'regex';
    type SecurityRiskLevel = 'medium' | 'high' | 'fatal';

    interface SecurityRuleRecord {
      id: number;
      pattern: string;
      match_mode: SecurityMatchMode;
      risk_level: SecurityRiskLevel;
      description: string;
      blocked_count: number;
      enabled: boolean;
      created_at: string;
      updated_at: string;
    }

    interface SecurityRulePayload {
      pattern: string;
      match_mode: SecurityMatchMode;
      risk_level: SecurityRiskLevel;
      description: string;
      enabled: boolean;
    }

    interface CommandInterceptRecord {
      id: number;
      operatorName: string;
      command: string;
      target_desc: string;
      rule: number | null;
      hit_pattern: string;
      risk_level: SecurityRiskLevel | '';
      created_at: string;
    }

    interface SecurityStats {
      ruleCount: number;
      monthBlocked: number;
    }

    interface SecurityListParams {
      current: number;
      size: number;
      search?: string;
    }

    type DashboardExecutionCategory =
      | 'ops_script'
      | 'ops_playbook'
      | 'ops_module'
      | 'ops_other'
      | 'task_scheduled'
      | 'task_workflow';

    interface DashboardExecutionDistribution {
      periodDays: number;
      total: number;
      items: Array<{ key: DashboardExecutionCategory; count: number }>;
    }

    /** 健康检查响应（redis/workers/queues/websocket/sevenDay/checkedAt） */
    interface DashboardHealth {
      environment?: {
        sdks: { name: string; available: boolean; version: string | null }[];
        credentialsEncryptionConfigured: boolean;
        credentialsEncryptionValid: boolean;
        apiVersion: string;
        workersVersionStatus: 'not_reported' | 'matched' | 'mismatch';
        workerVersions?: Record<string, string>;
      };
      redis: { healthy: boolean; error: string };
      workers: {
        healthy: boolean;
        count: number;
        nodes: string[];
        queues: Record<string, string[]>;
        missingQueues: string[];
      };
      queues: Record<string, number>;
      websocket: { healthy: boolean; backend: string };
      sevenDay: { total: number; finished: number; successRate: number };
      checkedAt: string;
    }

    /** 概览最近运行条目（后端返回裸数组） */
    interface DashboardRecentItem {
      id: number;
      name: string;
      type: string;
      target: string;
      status: RunStatus;
      executor: string;
      time: string;
    }
  }
}
