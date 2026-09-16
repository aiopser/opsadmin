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
    interface RunRecord {
      id: number;
      workflowVersionId: number | null;
      workerPoolId: number;
      triggeredById: number | null;
      runDomain: RunDomain;
      executionKind: ExecutionKind;
      triggerType: TriggerType;
      status: RunStatus;
      inputVars: Record<string, unknown>;
      targetSnapshot: TargetSnapshot[];
      contextVars: Record<string, unknown>;
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
      workflowVersion: number | null;
      workerPoolName: string;
      triggeredByName: string;
      targetCount: number;
    }

    /** 运行列表查询参数 */
    interface RunSearchParams {
      current: number;
      size: number;
      status?: RunStatus | null;
      executionKind?: ExecutionKind | null;
      runDomain?: RunDomain | null;
      search?: string | null;
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
      commandType: 'linux_shell' | 'windows_powershell' | 'python';
      commandContent: string;
      hostIds: number[];
      workerPoolId: number | null;
      sourceCommandVersionId?: number | null;
      gatewayId?: number | null;
    }

    interface PlaybookRunPayload {
      playbookContent: string;
      playbookName?: string;
      inputVars?: Record<string, unknown>;
      hostIds: number[];
      workerPoolId: number | null;
      gatewayId?: number | null;
    }

    interface ModuleRunPayload {
      moduleVersionId: number;
      moduleArgs?: string;
      hostIds: number[];
      workerPoolId: number | null;
      gatewayId?: number | null;
    }

    /** 运行创建提交参数（WorkflowRunCreateSerializer，全部 camelCase） */
    interface WorkflowRunPayload {
      workflowVersionId: number;
      hostIds?: number[];
      groupIds?: number[];
      tagIds?: number[];
      inputVars?: Record<string, unknown>;
      workerPoolId?: number | null;
      /** parallel / serial / rolling（host_strategy 的驼峰字段名） */
      hostStrategy?: 'parallel' | 'serial' | 'rolling';
      forks?: number;
      /** serial 策略批次大小（serial_batch） */
      serialBatch?: number;
      maxFailPercentage?: number;
      timeoutSeconds?: number;
      queueTimeoutSeconds?: number;
      bypassHostGateway?: boolean;
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
      version: number;
      workflowName: string;
      workflowCode: string;
      inputSchema: WorkflowInputField[] | { fields?: WorkflowInputField[] };
    }

    /** 资产主机（cmdb.AssetHost 精简，用于目标选择） */
    interface HostOption {
      id: number;
      hostname: string;
      primaryIp: string;
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
      network: string;
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
      network?: string;
      auth_type?: 'password' | 'key';
      username?: string;
      secret?: string;
    }

    /** 定时任务重叠策略（ScheduledJob.OverlapPolicy） */
    type ScheduleOverlapPolicy = 'skip' | 'allow' | 'queue';

    /** 定时任务错过策略（ScheduledJob.MisfirePolicy） */
    type ScheduleMisfirePolicy = 'fire' | 'skip';

    /** 定时任务记录（ScheduledJobSerializer：fields="__all__" 蛇形 + 附加驼峰只读） */
    interface ScheduledJobRecord {
      id: number;
      name: string;
      workflow_version: number | null;
      worker_pool: number;
      host_ids: number[];
      cron_expression: string;
      timezone: string;
      input_vars: Record<string, unknown>;
      host_strategy: 'parallel' | 'serial' | 'rolling';
      forks: number;
      serial_batch: number;
      max_fail_percentage: number;
      timeout_seconds: number;
      queue_timeout_seconds: number;
      bypass_host_gateway: boolean;
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
    }

    /** 定时任务创建/更新载荷 */
    interface ScheduledJobPayload {
      name: string;
      workflow_version: number;
      worker_pool?: number | null;
      host_ids: number[];
      cron_expression: string;
      timezone?: string;
      input_vars?: Record<string, unknown>;
      host_strategy?: 'parallel' | 'serial' | 'rolling';
      forks?: number;
      serial_batch?: number;
      max_fail_percentage?: number;
      timeout_seconds?: number;
      queue_timeout_seconds?: number;
      bypass_host_gateway?: boolean;
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

    /** 运行概览统计（GET /api/v1/jobs/dashboard/stats，固定统计 ops 域当日数据） */
    interface DashboardStats {
      todayExecutions: number;
      successRate: number;
      avgResponseSeconds: number;
      blockedCommands: number;
    }
  }
}
