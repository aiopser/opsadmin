const local: App.I18n.Schema = {
  system: {
    title: 'SoybeanAdmin',
    updateTitle: 'System Version Update Notification',
    updateContent: 'A new version of the system has been detected. Do you want to refresh the page immediately?',
    updateConfirm: 'Refresh immediately',
    updateCancel: 'Later'
  },
  common: {
    action: 'Action',
    add: 'Add',
    addSuccess: 'Add Success',
    backToHome: 'Back to home',
    batchDelete: 'Batch Delete',
    cancel: 'Cancel',
    close: 'Close',
    check: 'Check',
    expandColumn: 'Expand Column',
    expand: 'Expand',
    hide: 'Hide',
    columnSetting: 'Column Setting',
    config: 'Config',
    confirm: 'Confirm',
    delete: 'Delete',
    deleteSuccess: 'Delete Success',
    confirmDelete: 'Are you sure you want to delete?',
    edit: 'Edit',
    warning: 'Warning',
    error: 'Error',
    index: 'Index',
    detail: 'Detail',
    keywordSearch: 'Please enter keyword',
    logout: 'Logout',
    logoutConfirm: 'Are you sure you want to log out?',
    lookForward: 'Coming soon',
    modify: 'Modify',
    modifySuccess: 'Modify Success',
    noData: 'No Data',
    operate: 'Operate',
    pleaseCheckValue: 'Please check whether the value is valid',
    refresh: 'Refresh',
    reset: 'Reset',
    search: 'Search',
    switch: 'Switch',
    tip: 'Tip',
    trigger: 'Trigger',
    update: 'Update',
    updateSuccess: 'Update Success',
    userCenter: 'User Center',
    yesOrNo: {
      yes: 'Yes',
      no: 'No'
    }
  },
  request: {
    logout: 'Logout user after request failed',
    logoutMsg: 'User status is invalid, please log in again',
    logoutWithModal: 'Pop up modal after request failed and then log out user',
    logoutWithModalMsg: 'User status is invalid, please log in again',
    refreshToken: 'The requested token has expired, refresh the token',
    tokenExpired: 'The requested token has expired'
  },
  theme: {
    themeSchema: {
      title: 'Theme Schema',
      light: 'Light',
      dark: 'Dark',
      auto: 'Follow System'
    },
    grayscale: 'Grayscale',
    colourWeakness: 'Colour Weakness',
    layoutMode: {
      title: 'Layout Mode',
      vertical: 'Vertical Menu Mode',
      horizontal: 'Horizontal Menu Mode',
      'vertical-mix': 'Vertical Mix Menu Mode',
      'horizontal-mix': 'Horizontal Mix menu Mode',
      reverseHorizontalMix: 'Reverse first level menus and child level menus position'
    },
    recommendColor: 'Apply Recommended Color Algorithm',
    recommendColorDesc: 'The recommended color algorithm refers to',
    themeColor: {
      title: 'Theme Color',
      primary: 'Primary',
      info: 'Info',
      success: 'Success',
      warning: 'Warning',
      error: 'Error',
      followPrimary: 'Follow Primary'
    },
    scrollMode: {
      title: 'Scroll Mode',
      wrapper: 'Wrapper',
      content: 'Content'
    },
    page: {
      animate: 'Page Animate',
      mode: {
        title: 'Page Animate Mode',
        fade: 'Fade',
        'fade-slide': 'Slide',
        'fade-bottom': 'Fade Zoom',
        'fade-scale': 'Fade Scale',
        'zoom-fade': 'Zoom Fade',
        'zoom-out': 'Zoom Out',
        none: 'None'
      }
    },
    fixedHeaderAndTab: 'Fixed Header And Tab',
    header: {
      height: 'Header Height',
      breadcrumb: {
        visible: 'Breadcrumb Visible',
        showIcon: 'Breadcrumb Icon Visible'
      },
      multilingual: {
        visible: 'Display multilingual button'
      },
      globalSearch: {
        visible: 'Display global search button'
      }
    },
    tab: {
      visible: 'Tab Visible',
      cache: 'Tag Bar Info Cache',
      height: 'Tab Height',
      mode: {
        title: 'Tab Mode',
        chrome: 'Chrome',
        button: 'Button'
      }
    },
    sider: {
      inverted: 'Dark Sider',
      width: 'Sider Width',
      collapsedWidth: 'Sider Collapsed Width',
      mixWidth: 'Mix Sider Width',
      mixCollapsedWidth: 'Mix Sider Collapse Width',
      mixChildMenuWidth: 'Mix Child Menu Width'
    },
    footer: {
      visible: 'Footer Visible',
      fixed: 'Fixed Footer',
      height: 'Footer Height',
      right: 'Right Footer'
    },
    watermark: {
      visible: 'Watermark Full Screen Visible',
      text: 'Watermark Text',
      enableUserName: 'Enable User Name Watermark'
    },
    themeDrawerTitle: 'Theme Configuration',
    pageFunTitle: 'Page Function',
    configOperation: {
      copyConfig: 'Copy Config',
      copySuccessMsg: 'Copy Success, Please replace the variable "themeSettings" in "src/theme/settings.ts"',
      resetConfig: 'Reset Config',
      resetSuccessMsg: 'Reset Success'
    }
  },
  route: {
    monitoring: 'Monitoring',
    monitoring_consul: 'Consul Management',
    'monitoring_consul-template': 'Template Config',
    monitoring_targets: 'Monitoring Targets',
    monitoring_policies: 'Enrollment Policies',
    monitoring_integrations: 'JumpServer Integration',
    monitoring_security: 'Security Advisories',
    login: 'Login',
    403: 'No Permission',
    404: 'Page Not Found',
    500: 'Server Error',
    'iframe-page': 'Iframe',
    home: 'Home',
    audit: 'Audit Center',
    audit_event: 'Audit Log',
    audit_login: 'Login Log',
    audit_operation: 'Operation Log',
    cmdb: 'Asset Management',
    cmdb_host: 'Host Assets',
    cmdb_source: 'Asset Access',
    cmdb_credential: 'Credential Refs',
    cmdb_execution: 'Executors',
    cmdb_group: 'Host Groups',
    cmdb_resource: 'Resource View',
    automation: 'Automation Config',
    automation_resource: 'Workflow Versions',
    automation_resources: 'Automation Config',
    automation_resources_script: 'Scripts',
    automation_resources_playbook: 'Playbooks',
    automation_resources_module: 'Modules',
    automation_resources_api: 'API Endpoints',
    automation_resources_jenkins: 'Jenkins',
    automation_resources_git: 'Git Repositories',
    automation_resources_notification: 'Notification Templates',
    automation_resources_gateway: 'Gateway Proxy',
    ops_dashboard: 'Ops Dashboard',
    ops_history: 'Run History',
    'ops_run-detail': 'Run Detail',
    ops_settings: 'Execution Engine',
    task_dashboard: 'Task Dashboard',
    'task_execution-history': 'Execution History',
    'task_run-create': 'Start Execution',
    task_templates: 'Templates',
    'task_flow-design': 'Flow Design',
    task_schedule: 'Schedules',
    task_provisioning: 'Resource Requests',
    'task_provisioning-operations': 'Delivery Health',
    automation_resources_provisioning: 'Resource Templates',
    'task_worker-pool': 'Worker Pools',
    ops: 'Ops',
    'ops_quick-execute': 'Quick Execute',
    'ops_quick-execute_script': 'Script Execute',
    'ops_quick-execute_playbook': 'Playbook Execute',
    'ops_quick-execute_module': 'Module Execute',
    task: 'Task',
    task_run: 'Task List',
    'task_run-detail': 'Run Detail',
    document: 'Document',
    document_project: 'Project Document',
    'document_project-link': 'Project Document(External Link)',
    document_vue: 'Vue Document',
    document_vite: 'Vite Document',
    document_unocss: 'UnoCSS Document',
    document_naive: 'Naive UI Document',
    document_antd: 'Ant Design Vue Document',
    'document_element-plus': 'Element Plus Document',
    document_alova: 'Alova Document',
    'user-center': 'User Center',
    manage: 'System Manage',
    manage_user: 'User Manage',
    'manage_user-detail': 'User Detail',
    manage_role: 'Role Manage',
    manage_menu: 'Menu Manage',
    manage_dept: 'Department Manage',
    manage_dict: 'Dict Manage',
    manage_config: 'System Config',
    manage_notification: 'Notification Settings',
    exception: 'Exception',
    exception_403: '403',
    exception_404: '404',
    exception_500: '500',
    plugin: 'Plugin',
    plugin_copy: 'Copy',
    plugin_charts: 'Charts',
    plugin_charts_echarts: 'ECharts',
    plugin_charts_antv: 'AntV',
    plugin_charts_vchart: 'VChart',
    plugin_editor: 'Editor',
    plugin_editor_quill: 'Quill',
    plugin_editor_markdown: 'Markdown',
    plugin_icon: 'Icon',
    plugin_map: 'Map',
    plugin_print: 'Print',
    plugin_swiper: 'Swiper',
    plugin_video: 'Video',
    plugin_barcode: 'Barcode',
    plugin_pinyin: 'pinyin',
    plugin_excel: 'Excel',
    plugin_pdf: 'PDF preview',
    plugin_gantt: 'Gantt Chart',
    plugin_gantt_dhtmlx: 'dhtmlxGantt',
    plugin_gantt_vtable: 'VTableGantt',
    plugin_typeit: 'Typeit',
    plugin_tables: 'Tables',
    plugin_tables_vtable: 'VTable',
    wiki: 'Wiki'
  },
  page: {
    login: {
      common: {
        loginOrRegister: 'Login / Register',
        userNamePlaceholder: 'Please enter user name',
        phonePlaceholder: 'Please enter phone number',
        codePlaceholder: 'Please enter verification code',
        passwordPlaceholder: 'Please enter password',
        confirmPasswordPlaceholder: 'Please enter password again',
        confirm: 'Confirm',
        back: 'Back',
        validateSuccess: 'Verification passed',
        loginSuccess: 'Login successfully',
        welcomeBack: 'Welcome back, {userName} !'
      },
      pwdLogin: {
        title: 'Password Login',
        rememberMe: 'Remember me',
        forgetPassword: 'Forget password?'
      },
      resetPwd: {
        title: 'Reset Password'
      }
    },
    home: {
      branchDesc:
        'For the convenience of everyone in developing and updating the merge, we have streamlined the code of the main branch, only retaining the homepage menu, and the rest of the content has been moved to the example branch for maintenance. The preview address displays the content of the example branch.',
      greeting: 'Good morning, {userName}, today is another day full of vitality!',
      loginTime: 'Login time',
      loginTimeUnavailable: 'Unavailable',
      downloadCount: 'Download Count',
      registerCount: 'Register Count',
      jobExecutionCount: 'Job Executions',
      taskExecutionCount: 'Task Executions',
      todayJobExecutions: 'Job Runs Today',
      todayJobSuccessRate: 'Job Success Rate Today',
      sevenDayTaskExecutions: 'Task Runs · Last 7 Days',
      sevenDayTaskSuccessRate: 'Task Success Rate · Last 7 Days',
      dashboardMetrics: {
        loadError: 'Failed to load dashboard run metrics'
      },
      executionDistribution: {
        title: 'Execution Types · Last 30 Days',
        period: 'Last {days} days',
        total: '{total} runs total',
        loadError: 'Failed to load execution distribution',
        opsScript: 'Ops · Script',
        opsPlaybook: 'Ops · Playbook',
        opsModule: 'Ops · Module',
        opsOther: 'Ops · Other',
        taskScheduled: 'Tasks · Scheduled',
        taskWorkflow: 'Tasks · Workflow'
      },
      schedule: 'Work and rest Schedule',
      study: 'Study',
      work: 'Work',
      rest: 'Rest',
      entertainment: 'Entertainment',
      visitCount: 'Visit Count',
      turnover: 'Turnover',
      dealCount: 'Deal Count',
      projectNews: {
        title: 'Project News',
        moreNews: 'More News',
        desc1: 'Soybean created the open source project soybean-admin on May 28, 2021!',
        desc2: 'Yanbowe submitted a bug to soybean-admin, the multi-tab bar will not adapt.',
        desc3: 'Soybean is ready to do sufficient preparation for the release of soybean-admin!',
        desc4: 'Soybean is busy writing project documentation for soybean-admin!',
        desc5: 'Soybean just wrote some of the workbench pages casually, and it was enough to see!'
      },
      creativity: 'Creativity'
    },
    manage: {
      common: {
        status: {
          enable: 'Enable',
          disable: 'Disable'
        },
        profileTitle: 'Personal Info',
        username: 'Username',
        userNickname: 'Nickname',
        userRole: 'Role',
        userDept: 'Department',
        userEmail: 'Email',
        userPhone: 'Phone',
        userCreateTime: 'Joined At',
        securityTitle: 'Security Info',
        saveProfile: 'Save Info',
        savePassword: 'Save Password',
        language: 'Language',
        passwordRuleTip:
          'The password must be 6 to 18 characters long and can only contain letters, numbers and underscores.',
        passwordResetNote:
          'After the password is updated, you will be redirected to the login page and can log in again with the new password.',
        oldPassword: 'Old Password',
        newPassword: 'New Password',
        confirmPassword: 'Confirm Password',
        oldPasswordRequired: 'Please enter old password',
        newPasswordRequired: 'Please enter new password',
        passwordUpdated: 'Password changed, please log in again',
        profileUpdated: 'Profile updated'
      },
      role: {
        title: 'Role List',
        roleName: 'Role Name',
        roleCode: 'Role Code',
        roleStatus: 'Role Status',
        roleDesc: 'Role Description',
        menuAuth: 'Menu Auth',
        buttonAuth: 'Button Auth',
        systemRoleProtected: 'Built-in role is protected and cannot be deleted',
        form: {
          roleName: 'Please enter role name',
          roleCode: 'Please enter role code',
          roleStatus: 'Please select role status',
          roleDesc: 'Please enter role description'
        },
        addRole: 'Add Role',
        editRole: 'Edit Role'
      },
      user: {
        title: 'User List',
        userName: 'User Name',
        userGender: 'Gender',
        nickName: 'Nick Name',
        userPhone: 'Phone Number',
        userEmail: 'Email',
        userStatus: 'User Status',
        userRole: 'User Role',
        superuserProtected: 'Built-in super admin is protected and cannot be deleted',
        form: {
          userName: 'Please enter user name',
          userGender: 'Please select gender',
          nickName: 'Please enter nick name',
          userPhone: 'Please enter phone number',
          userEmail: 'Please enter email',
          userStatus: 'Please select user status',
          userRole: 'Please select user role'
        },
        addUser: 'Add User',
        editUser: 'Edit User',
        gender: {
          male: 'Male',
          female: 'Female'
        }
      },
      menu: {
        home: 'Home',
        title: 'Menu List',
        id: 'ID',
        parentId: 'Parent ID',
        menuType: 'Menu Type',
        menuName: 'Menu Name',
        routeName: 'Route Name',
        routePath: 'Route Path',
        pathParam: 'Path Param',
        layout: 'Layout Component',
        page: 'Page Component',
        i18nKey: 'I18n Key',
        icon: 'Icon',
        localIcon: 'Local Icon',
        iconTypeTitle: 'Icon Type',
        order: 'Order',
        constant: 'Constant',
        keepAlive: 'Keep Alive',
        href: 'Href',
        hideInMenu: 'Hide In Menu',
        activeMenu: 'Active Menu',
        multiTab: 'Multi Tab',
        fixedIndexInTab: 'Fixed Index In Tab',
        query: 'Query Params',
        button: 'Button',
        buttonCode: 'Button Code',
        buttonDesc: 'Button Desc',
        menuStatus: 'Menu Status',
        form: {
          home: 'Please select home',
          menuType: 'Please select menu type',
          menuName: 'Please enter menu name',
          routeName: 'Please enter route name',
          routePath: 'Please enter route path',
          pathParam: 'Please enter path param',
          page: 'Please select page component',
          layout: 'Please select layout component',
          i18nKey: 'Please enter i18n key',
          icon: 'Please enter iconify name',
          localIcon: 'Please enter local icon name',
          order: 'Please enter order',
          keepAlive: 'Please select whether to cache route',
          href: 'Please enter href',
          hideInMenu: 'Please select whether to hide menu',
          activeMenu: 'Please select route name of the highlighted menu',
          multiTab: 'Please select whether to support multiple tabs',
          fixedInTab: 'Please select whether to fix in the tab',
          fixedIndexInTab: 'Please enter the index fixed in the tab',
          queryKey: 'Please enter route parameter Key',
          queryValue: 'Please enter route parameter Value',
          button: 'Please select whether it is a button',
          buttonCode: 'Please enter button code',
          buttonDesc: 'Please enter button description',
          menuStatus: 'Please select menu status'
        },
        addMenu: 'Add Menu',
        editMenu: 'Edit Menu',
        addChildMenu: 'Add Child Menu',
        type: {
          directory: 'Directory',
          menu: 'Menu'
        },
        iconType: {
          iconify: 'Iconify Icon',
          local: 'Local Icon'
        }
      },
      dept: {
        title: 'Department List',
        deptName: 'Department Name',
        deptCode: 'Department Code',
        parentDept: 'Parent Department',
        sort: 'Sort',
        deptStatus: 'Department Status',
        form: {
          deptName: 'Please enter department name',
          deptCode: 'Please enter department code',
          parentDept: 'Please select parent department (empty for root)',
          sort: 'Please enter sort order',
          deptStatus: 'Please select department status'
        },
        addDept: 'Add Department',
        editDept: 'Edit Department'
      },
      dict: {
        title: 'Dict Type List',
        dictName: 'Dict Name',
        dictCode: 'Dict Code',
        remark: 'Remark',
        dictStatus: 'Dict Status',
        dictItems: 'Dict Items',
        addDictType: 'Add Dict',
        editDictType: 'Edit Dict',
        addItem: 'Add Item',
        editItem: 'Edit Item',
        itemValue: 'Value',
        itemLabel: 'Label',
        itemSort: 'Sort',
        itemTagType: 'Tag Color',
        form: {
          dictName: 'Please enter dict name',
          dictCode: 'Please enter dict code',
          remark: 'Please enter remark',
          dictStatus: 'Please select dict status',
          itemLabel: 'Please enter label',
          itemValue: 'Please enter value',
          itemSort: 'Please enter sort order',
          itemTagType: 'Please select tag color'
        }
      },
      log: {
        title: 'Operation Log List',
        logTitle: 'Operation Title',
        module: 'Module',
        actionType: 'Action Type',
        operator: 'Operator',
        requestUri: 'Request URI',
        requestMethod: 'Method',
        ip: 'IP',
        logStatus: 'Status',
        executionTime: 'Cost(ms)',
        errorMsg: 'Error Message',
        keywords: 'Keywords',
        createTime: 'Operation Time'
      },
      config: {
        title: 'System Config List',
        configName: 'Config Name',
        configKey: 'Config Key',
        configValue: 'Config Value',
        configGroup: 'Config Group',
        remark: 'Remark',
        configStatus: 'Config Status',
        addConfig: 'Add Config',
        editConfig: 'Edit Config',
        form: {
          configName: 'Please enter config name',
          configKey: 'Please enter config key',
          configValue: 'Please enter config value',
          configGroup: 'Please enter config group',
          remark: 'Please enter remark',
          configStatus: 'Please select config status'
        }
      }
    },
    audit: {
      login: {
        title: 'Login Log',
        time: 'Login Time',
        username: 'Username',
        result: 'Result',
        success: 'Success',
        failure: 'Failure',
        reason: 'Failure Reason',
        invalidRequest: 'Invalid request',
        authFailed: 'Authentication failed',
        internalError: 'System error',
        ipAddress: 'Source IP',
        userAgent: 'Device Information'
      },
      event: {
        title: 'Audit Event List',
        time: 'Time',
        domain: 'Domain',
        result: 'Result',
        success: 'Success',
        failure: 'Failure',
        actor: 'Operator',
        operation: 'Operation',
        object: 'Object',
        actionCode: 'Action code',
        resourceTypeCode: 'Object type code',
        action: 'Action',
        resourceType: 'Resource Type',
        resourceId: 'Resource ID',
        ipAddress: 'IP Address',
        keywords: 'Keywords',
        failReason: 'Failure reason',
        detail: 'Event Detail',
        changes: 'Data Changes',
        changedHint: '{count} changed',
        field: 'Field',
        before: 'Before',
        after: 'After',
        copy: 'Copy',
        copied: 'Copied to clipboard',
        copyUnsupported: 'Clipboard is not supported in this browser',
        userAgent: 'User Agent',
        form: {
          domain: 'Please select domain',
          keywords: 'Operator / Operation / Object / Resource ID / IP'
        }
      }
    },
    cmdb: {
      host: {
        title: 'Host Asset List',
        id: 'ID',
        hostname: 'Hostname',
        internalIp: 'Internal IP',
        externalIp: 'External IP',
        assetType: 'Asset Type',
        osFamily: 'Operating System',
        osType: 'OS Version',
        statusLabel: 'Status',
        environment: 'Environment',
        region: 'Region',
        spec: 'Spec',
        cpu: 'CPU',
        memory: 'Memory',
        disk: 'Disk',
        appCode: 'App',
        ownerTeam: 'Owner Team',
        credential: 'Credential',
        updatedAt: 'Updated At',
        keyword: 'Keyword',
        keywordPlaceholder: 'Hostname/IP/Image/App/Team',
        status: {
          active: 'Active',
          inactive: 'Inactive',
          retired: 'Retired'
        }
      }
    },
    task: {
      run: {
        title: 'Execution History',
        id: 'Run ID',
        workflowName: 'Workflow Template',
        statusLabel: 'Status',
        executionKind: 'Execution Kind',
        runDomain: 'Run Domain',
        targetCount: 'Targets',
        triggeredBy: 'Triggered By',
        startedAt: 'Started At',
        finishedAt: 'Finished At',
        duration: 'Duration',
        failureReason: 'Failure Reason',
        workerPool: 'Worker Pool',
        keyword: 'Keyword',
        cancel: 'Cancel',
        retry: 'Retry',
        rerun: 'Rerun',
        snapshotExecutionHint:
          'Execute the original workflow with its target snapshot and execution settings after checking current access, asset and credential status. Start a new execution from the task definition or job page to use current asset configuration.',
        log: 'Log',
        logTruncated: 'The log may be incomplete due to size limits or incomplete chunk archiving',
        retryCreated: 'New run created',
        status: {
          pending: 'Pending',
          queued: 'Queued',
          running: 'Running',
          waiting: 'Waiting',
          cancel_requested: 'Cancel Requested',
          success: 'Success',
          failed: 'Failed',
          timeout: 'Timeout',
          canceled: 'Canceled'
        },
        kind: {
          workflow: 'Workflow Execution',
          quick_command: 'Quick Command',
          playbook: 'Playbook',
          module: 'Module'
        },
        domain: {
          task: 'Task',
          ops: 'Ops'
        }
      },
      detail: {
        live: 'Live',
        fallback: 'Polling',
        node: {
          title: 'Node Execution Status',
          key: 'Node',
          type: 'Type',
          command: 'Command',
          attempts: 'Attempts',
          exitCode: 'Exit Code',
          hostResults: 'Host Results',
          status: {
            pending: 'Pending',
            queued: 'Queued',
            running: 'Running',
            success: 'Success',
            failed: 'Failed',
            skipped: 'Skipped',
            ignored: 'Ignored',
            timeout: 'Timeout',
            canceled: 'Canceled'
          }
        },
        event: {
          title: 'Execution Events',
          dropped: 'Showing the latest {count} events; {dropped} earlier events were cleared'
        },
        host: {
          hostname: 'Hostname',
          ip: 'IP Address',
          viewOutput: 'Output',
          stdout: 'Stdout',
          stderr: 'Stderr'
        }
      }
    },
    ops: {
      engineSettings: {
        title: 'Execution Engine Configuration',
        engineTab: 'Execution Engine',
        description: 'Configure global defaults for job execution.',
        overrideHint:
          'These are global defaults. Settings on workflow nodes, task tickets, or scheduled jobs take precedence.',
        timeout: 'Default timeout (seconds)',
        forks: 'Concurrent hosts',
        strategy: 'Host execution strategy',
        parallel: 'Parallel',
        serial: 'One host at a time',
        rolling: 'Rolling batches',
        serialBatch: 'Rolling batch size',
        maxFailPercentage: 'Maximum failure percentage',
        saveButton: 'Save settings',
        loadError: 'Failed to load execution engine settings',
        saveSuccess: 'Execution engine settings saved'
      },
      commandFilter: {
        tab: 'Command Filtering',
        description:
          'Block quick commands and Ansible module executions that match these rules. Intercepted attempts record the operator and target. Rule changes apply to subsequent executions.',
        enabledRuleCount: 'Enabled rules',
        monthBlocked: 'Blocked this month',
        rulesTitle: 'Command Filtering Rules',
        ruleSearchPlaceholder: 'Search rules or descriptions',
        addRule: 'Add Rule',
        pattern: 'Command Pattern',
        patternRequired: 'Enter a command pattern',
        matchMode: 'Match Mode',
        matchModeContains: 'Contains',
        matchModeExact: 'Exact match',
        matchModePrefix: 'Prefix match',
        matchModeRegex: 'Regular expression',
        riskLevel: 'Risk Level',
        riskMedium: 'Medium',
        riskHigh: 'High',
        riskFatal: 'Fatal',
        descriptionColumn: 'Description',
        blockedCount: 'Blocked',
        status: 'Status',
        enabledState: 'Enabled',
        disabledState: 'Disabled',
        actions: 'Actions',
        enableAction: 'Enable',
        disableAction: 'Disable',
        interceptsTitle: 'Intercept Records',
        interceptSearchPlaceholder: 'Search command, rule, or target',
        interceptTime: 'Intercepted At',
        operator: 'Operator',
        command: 'Command',
        target: 'Target',
        hitRule: 'Matched Rule',
        addTitle: 'Add Command Filtering Rule',
        editTitle: 'Edit Command Filtering Rule',
        createSuccess: 'Rule created',
        updateSuccess: 'Rule updated',
        enabled: 'Rule enabled',
        disabled: 'Rule disabled',
        deleteTitle: 'Confirm Deletion',
        deleteConfirm: 'Delete rule "{pattern}"? This action cannot be undone.',
        deleteSuccess: 'Rule deleted'
      },
      quickExecute: {
        title: 'Quick Execute',
        commandType: 'Command Type',
        commandContent: 'Command Content',
        hosts: 'Target Hosts',
        workerPool: 'Worker Pool',
        submit: 'Execute',
        submitted: 'Execution submitted',
        form: {
          commandContentPlaceholder: 'Enter the command content to execute',
          commandContentRequired: 'Please enter command content',
          hostIdsRequired: 'Please select target hosts',
          hostsPlaceholder: 'Select target hosts (searchable)',
          workerPoolPlaceholder: 'Use system default worker pool'
        }
      }
    }
  },
  form: {
    required: 'Cannot be empty',
    userName: {
      required: 'Please enter user name',
      invalid: 'User name format is incorrect'
    },
    phone: {
      required: 'Please enter phone number',
      invalid: 'Phone number format is incorrect'
    },
    pwd: {
      required: 'Please enter password',
      invalid: '6-18 characters, including letters, numbers, and underscores'
    },
    confirmPwd: {
      required: 'Please enter password again',
      invalid: 'The two passwords are inconsistent'
    },
    code: {
      required: 'Please enter verification code',
      invalid: 'Verification code format is incorrect'
    },
    email: {
      required: 'Please enter email',
      invalid: 'Email format is incorrect'
    }
  },
  dropdown: {
    closeCurrent: 'Close Current',
    closeOther: 'Close Other',
    closeLeft: 'Close Left',
    closeRight: 'Close Right',
    closeAll: 'Close All'
  },
  icon: {
    themeConfig: 'Theme Configuration',
    themeSchema: 'Theme Schema',
    lang: 'Switch Language',
    fullscreen: 'Fullscreen',
    fullscreenExit: 'Exit Fullscreen',
    reload: 'Reload Page',
    collapse: 'Collapse Menu',
    expand: 'Expand Menu',
    pin: 'Pin',
    unpin: 'Unpin'
  },
  datatable: {
    itemCount: 'Total {total} items'
  }
};

export default local;
