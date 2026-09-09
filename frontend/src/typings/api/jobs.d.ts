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
      commandType: 'linux_shell' | 'windows_powershell';
      commandContent: string;
      hostIds: number[];
      workerPoolId?: number | null;
      sourceCommandVersionId?: number | null;
      gatewayId?: number | null;
    }

    /** 运行创建提交参数（WorkflowRunCreateSerializer） */
    interface WorkflowRunPayload {
      workflowVersionId: number;
      hostIds?: number[];
      groupIds?: number[];
      tagIds?: number[];
      inputVars?: Record<string, unknown>;
      workerPoolId?: number | null;
    }

    interface WorkflowInputField {
      name: string;
      label?: string;
      type: 'string' | 'number' | 'integer' | 'boolean' | 'secret';
      required?: boolean;
      default?: string | number | boolean;
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
      isActive: boolean;
      isDefault: boolean;
      executionKinds: string[];
    }
  }
}
