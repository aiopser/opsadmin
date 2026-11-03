declare namespace Api {
  /**
   * namespace SystemManage
   *
   * backend api module: "systemManage"
   */
  namespace SystemManage {
    type CommonSearchParams = Pick<Common.PaginatingCommonParams, 'current' | 'size'>;

    /** role */
    type Role = Common.CommonRecord<{
      /** role name */
      roleName: string;
      /** role code */
      roleCode: string;
      /** role description */
      roleDesc: string;
      /** job data scope: visible run scope for job executions */
      jobDataScope: 'own' | 'department' | 'all';
      /** whether the role is a protected built-in role (cannot be deleted) */
      isSystem: boolean;
    }>;

    /** role search params */
    type RoleSearchParams = CommonType.RecordNullable<
      Pick<Api.SystemManage.Role, 'roleName' | 'roleCode' | 'status'> & CommonSearchParams
    >;

    /** role list */
    type RoleList = Common.PaginatingQueryRecord<Role>;

    /** all role */
    type AllRole = Pick<Role, 'id' | 'roleName' | 'roleCode'>;

    /** role model for create/update */
    type RoleModel = Pick<Role, 'roleName' | 'roleCode' | 'roleDesc' | 'status' | 'jobDataScope'>;

    /**
     * user gender
     *
     * - "1": "male"
     * - "2": "female"
     */
    type UserGender = '1' | '2';

    /** user */
    type User = Common.CommonRecord<{
      /** user name */
      userName: string;
      /** user gender */
      userGender: UserGender | undefined;
      /** user nick name */
      nickName: string;
      /** user phone */
      userPhone: string;
      /** user email */
      userEmail: string;
      /** user role code collection */
      userRoles: string[];
      /** whether the user is a protected super admin (cannot be deleted/disabled) */
      isSuperuser: boolean;
    }>;

    /** user search params */
    type UserSearchParams = CommonType.RecordNullable<
      Pick<Api.SystemManage.User, 'userName' | 'userGender' | 'nickName' | 'userPhone' | 'userEmail' | 'status'> &
        CommonSearchParams
    >;

    /** user list */
    type UserList = Common.PaginatingQueryRecord<User>;

    /** user model for create/update */
    type UserModel = Pick<
      User,
      'userName' | 'userGender' | 'nickName' | 'userPhone' | 'userEmail' | 'userRoles' | 'status'
    >;

    /**
     * menu type
     *
     * - "1": directory
     * - "2": menu
     */
    type MenuType = '1' | '2';

    type MenuButton = {
      /** button id（后端返回的记录包含，新建表单项中由后端生成） */
      id?: number;
      /**
       * button code
       *
       * it can be used to control the button permission
       */
      code: string;
      /** button description */
      desc: string;
    };

    /**
     * icon type
     *
     * - "1": iconify icon
     * - "2": local icon
     */
    type IconType = '1' | '2';

    type MenuPropsOfRoute = Pick<
      import('vue-router').RouteMeta,
      | 'i18nKey'
      | 'keepAlive'
      | 'constant'
      | 'order'
      | 'href'
      | 'hideInMenu'
      | 'activeMenu'
      | 'multiTab'
      | 'fixedIndexInTab'
      | 'query'
    >;

    type Menu = Common.CommonRecord<{
      /** parent menu id */
      parentId: number;
      /** menu type */
      menuType: MenuType;
      /** menu name */
      menuName: string;
      /** route name */
      routeName: string;
      /** route path */
      routePath: string;
      /** component */
      component?: string;
      /** iconify icon name or local icon name */
      icon: string;
      /** icon type */
      iconType: IconType;
      /** buttons */
      buttons?: MenuButton[] | null;
      /** children menu */
      children?: Menu[] | null;
    }> &
      MenuPropsOfRoute;

    /** menu list */
    type MenuList = Common.PaginatingQueryRecord<Menu>;

    /** menu model for create/update */
    type MenuModel = Pick<
      Menu,
      | 'menuType'
      | 'menuName'
      | 'routeName'
      | 'routePath'
      | 'component'
      | 'order'
      | 'i18nKey'
      | 'icon'
      | 'iconType'
      | 'status'
      | 'parentId'
      | 'keepAlive'
      | 'constant'
      | 'href'
      | 'hideInMenu'
      | 'activeMenu'
      | 'multiTab'
      | 'fixedIndexInTab'
      | 'query'
      | 'buttons'
    >;

    type MenuTree = {
      id: number;
      label: string;
      pId: number;
      children?: MenuTree[];
    };

    /**
     * department
     *
     * 树形结构，children 由后端 /api/v1/depts 树形列表返回
     */
    type Department = Common.CommonRecord<{
      /** department name */
      deptName: string;
      /** department code */
      deptCode: string;
      /** parent department id，0 表示顶级 */
      parentId: number;
      /** sort order */
      sort: number;
      /** children departments */
      children?: Department[] | null;
    }>;

    /** department search params（列表接口不分页，current/size 仅用于兼容） */
    type DepartmentSearchParams = CommonType.RecordNullable<Pick<Api.SystemManage.Department, 'deptName' | 'status'>>;

    /** department model for create/update */
    type DepartmentModel = Pick<Department, 'deptName' | 'deptCode' | 'parentId' | 'sort' | 'status'>;

    /** dict type */
    type DictType = Common.CommonRecord<{
      /** dict name */
      dictName: string;
      /** dict code */
      dictCode: string;
      /** remark */
      remark: string | null;
    }>;

    /** dict type search params */
    type DictTypeSearchParams = CommonType.RecordNullable<
      Pick<Api.SystemManage.DictType, 'dictName' | 'status'> & CommonSearchParams
    >;

    /** dict type list */
    type DictTypeList = Common.PaginatingQueryRecord<DictType>;

    /** dict type model for create/update */
    type DictTypeModel = Pick<DictType, 'dictName' | 'dictCode' | 'remark' | 'status'>;

    /** dict item */
    type DictItem = Common.CommonRecord<{
      /** 所属字典类型 code */
      dictCode: string;
      /** item label */
      label: string;
      /** item value */
      value: string;
      /** sort order */
      sort: number;
      /** tag type（前端标签颜色） */
      tagType: string;
    }>;

    /** dict item search params */
    type DictItemSearchParams = CommonType.RecordNullable<
      Pick<Api.SystemManage.DictItem, 'label' | 'status'> & CommonSearchParams
    >;

    /** dict item list */
    type DictItemList = Common.PaginatingQueryRecord<DictItem>;

    /** dict item model for create/update */
    type DictItemModel = Pick<DictItem, 'label' | 'value' | 'sort' | 'tagType' | 'status'>;

    /** system config */
    type SystemConfig = Common.CommonRecord<{
      /** config name */
      configName: string;
      /** config key */
      configKey: string;
      /** config value */
      configValue: string | null;
      /** config group */
      configGroup: string;
      /** remark */
      remark: string | null;
      /** built-in config（内置配置项） */
      isSystem: boolean;
    }>;

    /** system config search params */
    type SystemConfigSearchParams = CommonType.RecordNullable<
      Pick<Api.SystemManage.SystemConfig, 'configName' | 'configKey' | 'status'> & CommonSearchParams
    >;

    /** system config list */
    type SystemConfigList = Common.PaginatingQueryRecord<SystemConfig>;

    /** system config model for create/update */
    type SystemConfigModel = Pick<
      SystemConfig,
      'configName' | 'configKey' | 'configValue' | 'configGroup' | 'remark' | 'status'
    >;

    /** 邮件服务器传输协议 */
    type NotificationEmailProtocol = 'smtp' | 'secure_smtp';

    /** 通知邮件服务器设置 */
    type NotificationEmailSettings = {
      /** 服务器名称 */
      name: string;
      /** 描述 */
      description: string;
      /** SMTP 服务器地址，空字符串表示未配置（回退服务端环境变量） */
      host: string;
      /** SMTP 端口 */
      port: number;
      /** 登录用户名 */
      username: string;
      /** 默认发件人 */
      fromEmail: string;
      /** 邮件主题前缀 */
      titlePrefix: string;
      /** 传输协议：SMTP / SECURE_SMTP */
      protocol: NotificationEmailProtocol;
      /** 连接超时秒数，0 表示不超时 */
      timeout: number;
      /** 是否启用 STARTTLS，SECURE_SMTP 下恒为 false */
      useTls: boolean;
      /** 是否已保存密码 */
      hasPassword: boolean;
      /** 是否已完成配置 */
      configured: boolean;
    };

    /** 通知邮件服务器保存参数；密码留空表示不修改 */
    type NotificationEmailSettingsPayload = Omit<NotificationEmailSettings, 'hasPassword' | 'configured'> & {
      password: string;
    };

    /** 通知邮件服务器连接测试参数；密码留空表示使用已保存密码 */
    type NotificationEmailConnectionTestPayload = Pick<
      NotificationEmailSettings,
      'protocol' | 'host' | 'port' | 'timeout' | 'useTls' | 'username'
    > & {
      password: string;
    };

    /** 通知历史清理设置 */
    type NotificationHistorySettings = {
      /** 发送成功记录的保留天数 */
      retentionDays: number;
    };

    /** 通知历史清理结果 */
    type NotificationHistoryPurgeResult = {
      /** 符合条件或已删除的记录数 */
      count: number;
      /** 已删除记录数，预览时为 0 */
      deleted: number;
      /** 是否为预览（不实际删除） */
      dryRun: boolean;
    };

    /** 通知应用渠道 */
    type NotificationAppProvider = 'wecom' | 'dingtalk' | 'feishu';

    /** 通知应用凭据设置（企业微信 / 钉钉 / 飞书） */
    type NotificationAppSettings = {
      provider: NotificationAppProvider;
      /** 应用标识：企业微信 CorpID、钉钉 AppKey、飞书 AppID */
      appId: string;
      /** 企业微信/钉钉 AgentId，飞书固定为空 */
      agentId: string;
      /** 开放平台 API 地址 */
      apiBase: string;
      /** 是否已保存 Secret */
      hasSecret: boolean;
      /** 是否已完成配置 */
      configured: boolean;
    };

    /** 通知应用凭据保存参数；Secret 留空表示不修改 */
    type NotificationAppSettingsPayload = Omit<NotificationAppSettings, 'provider' | 'hasSecret' | 'configured'> & {
      appSecret: string;
    };

    /** 通知应用连接测试参数；Secret 留空表示使用已保存值 */
    type NotificationAppConnectionTestPayload = Pick<NotificationAppSettings, 'appId' | 'apiBase'> & {
      appSecret: string;
    };

    /** operation log（只读，无增删改） */
    type OperationLog = {
      id: number;
      /** 业务模块 */
      module: string;
      /** 操作类型 */
      actionType: string;
      /** 操作标题 */
      title: string;
      /** 请求 URI */
      requestUri: string;
      /** 请求方法 */
      requestMethod: string;
      /** 操作人 */
      operatorName: string;
      /** 操作 IP */
      ip: string;
      /** 1 成功 / 2 失败 */
      status: Api.Common.EnableStatus;
      /** 执行耗时（ms） */
      executionTime: number;
      /** 错误信息 */
      errorMsg: string;
      /** 操作时间 */
      createTime: string;
    };

    /** operation log search params */
    type OperationLogSearchParams = CommonType.RecordNullable<
      { keywords?: string | null; createTime?: string[] | null } & CommonSearchParams
    >;
  }
}
