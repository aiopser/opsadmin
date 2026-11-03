/** The global namespace for the app */
declare namespace App {
  /** Theme namespace */
  namespace Theme {
    type ColorPaletteNumber = import('@sa/color').ColorPaletteNumber;

    /** Theme setting */
    interface ThemeSetting {
      /** Theme scheme */
      themeScheme: UnionKey.ThemeScheme;
      /** grayscale mode */
      grayscale: boolean;
      /** colour weakness mode */
      colourWeakness: boolean;
      /** Whether to recommend color */
      recommendColor: boolean;
      /** Theme color */
      themeColor: string;
      /** Other color */
      otherColor: OtherColor;
      /** Whether info color is followed by the primary color */
      isInfoFollowPrimary: boolean;
      /** Layout */
      layout: {
        /** Layout mode */
        mode: UnionKey.ThemeLayoutMode;
        /** Scroll mode */
        scrollMode: UnionKey.ThemeScrollMode;
        /**
         * Whether to reverse the horizontal mix
         *
         * if true, the vertical child level menus in left and horizontal first level menus in top
         */
        reverseHorizontalMix: boolean;
      };
      /** Page */
      page: {
        /** Whether to show the page transition */
        animate: boolean;
        /** Page animate mode */
        animateMode: UnionKey.ThemePageAnimateMode;
      };
      /** Header */
      header: {
        /** Header height */
        height: number;
        /** Header breadcrumb */
        breadcrumb: {
          /** Whether to show the breadcrumb */
          visible: boolean;
          /** Whether to show the breadcrumb icon */
          showIcon: boolean;
        };
        /** Multilingual */
        multilingual: {
          /** Whether to show the multilingual */
          visible: boolean;
        };
        /** Global search */
        globalSearch: {
          /** Whether to show the global search */
          visible: boolean;
        };
      };
      /** Tab */
      tab: {
        /** Whether to show the tab */
        visible: boolean;
        /**
         * Whether to cache the tab
         *
         * If cache, the tabs will get from the local storage when the page is refreshed
         */
        cache: boolean;
        /** Tab height */
        height: number;
        /** Tab mode */
        mode: UnionKey.ThemeTabMode;
      };
      /** Fixed header and tab */
      fixedHeaderAndTab: boolean;
      /** Sider */
      sider: {
        /** Inverted sider */
        inverted: boolean;
        /** Sider width */
        width: number;
        /** Collapsed sider width */
        collapsedWidth: number;
        /** Sider width when the layout is 'vertical-mix' or 'horizontal-mix' */
        mixWidth: number;
        /** Collapsed sider width when the layout is 'vertical-mix' or 'horizontal-mix' */
        mixCollapsedWidth: number;
        /** Child menu width when the layout is 'vertical-mix' or 'horizontal-mix' */
        mixChildMenuWidth: number;
      };
      /** Footer */
      footer: {
        /** Whether to show the footer */
        visible: boolean;
        /** Whether fixed the footer */
        fixed: boolean;
        /** Footer height */
        height: number;
        /** Whether float the footer to the right when the layout is 'horizontal-mix' */
        right: boolean;
      };
      /** Watermark */
      watermark: {
        /** Whether to show the watermark */
        visible: boolean;
        /** Watermark text */
        text: string;
        /** Whether to use user name as watermark text */
        enableUserName: boolean;
      };
      /** define some theme settings tokens, will transform to css variables */
      tokens: {
        light: ThemeSettingToken;
        dark?: {
          [K in keyof ThemeSettingToken]?: Partial<ThemeSettingToken[K]>;
        };
      };
    }

    interface OtherColor {
      info: string;
      success: string;
      warning: string;
      error: string;
    }

    interface ThemeColor extends OtherColor {
      primary: string;
    }

    type ThemeColorKey = keyof ThemeColor;

    type ThemePaletteColor = {
      [key in ThemeColorKey | `${ThemeColorKey}-${ColorPaletteNumber}`]: string;
    };

    type BaseToken = Record<string, Record<string, string>>;

    interface ThemeSettingTokenColor {
      /** the progress bar color, if not set, will use the primary color */
      nprogress?: string;
      container: string;
      layout: string;
      inverted: string;
      'base-text': string;
    }

    interface ThemeSettingTokenBoxShadow {
      header: string;
      sider: string;
      tab: string;
    }

    interface ThemeSettingToken {
      colors: ThemeSettingTokenColor;
      boxShadow: ThemeSettingTokenBoxShadow;
    }

    type ThemeTokenColor = ThemePaletteColor & ThemeSettingTokenColor;

    /** Theme token CSS variables */
    type ThemeTokenCSSVars = {
      colors: ThemeTokenColor & { [key: string]: string };
      boxShadow: ThemeSettingTokenBoxShadow & { [key: string]: string };
    };
  }

  /** Global namespace */
  namespace Global {
    type VNode = import('vue').VNode;
    type RouteLocationNormalizedLoaded = import('vue-router').RouteLocationNormalizedLoaded;
    type RouteKey = import('@elegant-router/types').RouteKey;
    type RouteMap = import('@elegant-router/types').RouteMap;
    type RoutePath = import('@elegant-router/types').RoutePath;
    type LastLevelRouteKey = import('@elegant-router/types').LastLevelRouteKey;

    /** The global header props */
    interface HeaderProps {
      /** Whether to show the logo */
      showLogo?: boolean;
      /** Whether to show the menu toggler */
      showMenuToggler?: boolean;
      /** Whether to show the menu */
      showMenu?: boolean;
    }

    /** The global menu */
    type Menu = {
      /**
       * The menu key
       *
       * Equal to the route key
       */
      key: string;
      /** The menu label */
      label: string;
      /** The menu i18n key */
      i18nKey?: I18n.I18nKey | null;
      /** The route key */
      routeKey: RouteKey;
      /** The route path */
      routePath: RoutePath;
      /** The menu icon */
      icon?: () => VNode;
      /** The menu children */
      children?: Menu[];
    };

    type Breadcrumb = Omit<Menu, 'children'> & {
      options?: Breadcrumb[];
    };

    /** Tab route */
    type TabRoute = Pick<RouteLocationNormalizedLoaded, 'name' | 'path' | 'meta'> &
      Partial<Pick<RouteLocationNormalizedLoaded, 'fullPath' | 'query' | 'matched'>>;

    /** The global tab */
    type Tab = {
      /** The tab id */
      id: string;
      /** The tab label */
      label: string;
      /**
       * The new tab label
       *
       * If set, the tab label will be replaced by this value
       */
      newLabel?: string;
      /**
       * The old tab label
       *
       * when reset the tab label, the tab label will be replaced by this value
       */
      oldLabel?: string;
      /** The tab route key */
      routeKey: LastLevelRouteKey;
      /** The tab route path */
      routePath: RouteMap[LastLevelRouteKey];
      /** The tab route full path */
      fullPath: string;
      /** The tab fixed index */
      fixedIndex?: number | null;
      /**
       * Tab icon
       *
       * Iconify icon
       */
      icon?: string;
      /**
       * Tab local icon
       *
       * Local icon
       */
      localIcon?: string;
      /** I18n key */
      i18nKey?: I18n.I18nKey | null;
    };

    /** Form rule */
    type FormRule = import('element-plus').FormItemRule;

    /** The global dropdown key */
    type DropdownKey = 'closeCurrent' | 'closeOther' | 'closeLeft' | 'closeRight' | 'closeAll';
  }

  /**
   * I18n namespace
   *
   * Locales type
   */
  namespace I18n {
    type RouteKey = import('@elegant-router/types').RouteKey;

    type LangType = 'en-US' | 'zh-CN';

    type LangOption = {
      label: string;
      key: LangType;
    };

    type I18nRouteKey = Exclude<RouteKey, 'root' | 'not-found'>;

    type FormMsg = {
      required: string;
      invalid: string;
    };

    type Schema = {
      system: {
        title: string;
        updateTitle: string;
        updateContent: string;
        updateConfirm: string;
        updateCancel: string;
      };
      common: {
        action: string;
        add: string;
        addSuccess: string;
        backToHome: string;
        batchDelete: string;
        cancel: string;
        close: string;
        check: string;
        expandColumn: string;
        expand: string;
        hide: string;
        columnSetting: string;
        config: string;
        confirm: string;
        delete: string;
        deleteSuccess: string;
        confirmDelete: string;
        edit: string;
        warning: string;
        error: string;
        index: string;
        detail: string;
        keywordSearch: string;
        logout: string;
        logoutConfirm: string;
        lookForward: string;
        modify: string;
        modifySuccess: string;
        noData: string;
        operate: string;
        pleaseCheckValue: string;
        refresh: string;
        reset: string;
        search: string;
        switch: string;
        tip: string;
        trigger: string;
        update: string;
        updateSuccess: string;
        userCenter: string;
        yesOrNo: {
          yes: string;
          no: string;
        };
      };
      request: {
        logout: string;
        logoutMsg: string;
        logoutWithModal: string;
        logoutWithModalMsg: string;
        refreshToken: string;
        tokenExpired: string;
      };
      theme: {
        themeSchema: { title: string } & Record<UnionKey.ThemeScheme, string>;
        grayscale: string;
        colourWeakness: string;
        layoutMode: { title: string; reverseHorizontalMix: string } & Record<UnionKey.ThemeLayoutMode, string>;
        recommendColor: string;
        recommendColorDesc: string;
        themeColor: {
          title: string;
          followPrimary: string;
        } & Record<Theme.ThemeColorKey, string>;
        scrollMode: { title: string } & Record<UnionKey.ThemeScrollMode, string>;
        page: {
          animate: string;
          mode: { title: string } & Record<UnionKey.ThemePageAnimateMode, string>;
        };
        fixedHeaderAndTab: string;
        header: {
          height: string;
          breadcrumb: {
            visible: string;
            showIcon: string;
          };
          multilingual: {
            visible: string;
          };
          globalSearch: {
            visible: string;
          };
        };
        tab: {
          visible: string;
          cache: string;
          height: string;
          mode: { title: string } & Record<UnionKey.ThemeTabMode, string>;
        };
        sider: {
          inverted: string;
          width: string;
          collapsedWidth: string;
          mixWidth: string;
          mixCollapsedWidth: string;
          mixChildMenuWidth: string;
        };
        footer: {
          visible: string;
          fixed: string;
          height: string;
          right: string;
        };
        watermark: {
          visible: string;
          text: string;
          enableUserName: string;
        };
        themeDrawerTitle: string;
        pageFunTitle: string;
        configOperation: {
          copyConfig: string;
          copySuccessMsg: string;
          resetConfig: string;
          resetSuccessMsg: string;
        };
      };
      route: Record<I18nRouteKey, string>;
      page: {
        login: {
          common: {
            loginOrRegister: string;
            userNamePlaceholder: string;
            phonePlaceholder: string;
            codePlaceholder: string;
            passwordPlaceholder: string;
            confirmPasswordPlaceholder: string;
            confirm: string;
            back: string;
            validateSuccess: string;
            loginSuccess: string;
            welcomeBack: string;
          };
          pwdLogin: {
            title: string;
            rememberMe: string;
            forgetPassword: string;
          };
          resetPwd: {
            title: string;
          };
        };
        home: {
          branchDesc: string;
          greeting: string;
          loginTime: string;
          loginTimeUnavailable: string;
          downloadCount: string;
          registerCount: string;
          jobExecutionCount: string;
          taskExecutionCount: string;
          todayJobExecutions: string;
          todayJobSuccessRate: string;
          sevenDayTaskExecutions: string;
          sevenDayTaskSuccessRate: string;
          dashboardMetrics: {
            loadError: string;
          };
          executionDistribution: {
            title: string;
            period: string;
            total: string;
            loadError: string;
            opsScript: string;
            opsPlaybook: string;
            opsModule: string;
            opsOther: string;
            taskScheduled: string;
            taskWorkflow: string;
          };
          schedule: string;
          study: string;
          work: string;
          rest: string;
          entertainment: string;
          visitCount: string;
          turnover: string;
          dealCount: string;
          projectNews: {
            title: string;
            moreNews: string;
            desc1: string;
            desc2: string;
            desc3: string;
            desc4: string;
            desc5: string;
          };
          creativity: string;
        };
        manage: {
          common: {
            status: {
              enable: string;
              disable: string;
            };
            profileTitle: string;
            username: string;
            userNickname: string;
            userRole: string;
            userDept: string;
            userEmail: string;
            userPhone: string;
            userCreateTime: string;
            securityTitle: string;
            saveProfile: string;
            savePassword: string;
            language: string;
            passwordRuleTip: string;
            passwordResetNote: string;
            oldPassword: string;
            newPassword: string;
            confirmPassword: string;
            oldPasswordRequired: string;
            newPasswordRequired: string;
            passwordUpdated: string;
            profileUpdated: string;
          };
          role: {
            title: string;
            roleName: string;
            roleCode: string;
            roleStatus: string;
            roleDesc: string;
            form: {
              roleName: string;
              roleCode: string;
              roleStatus: string;
              roleDesc: string;
            };
            addRole: string;
            editRole: string;
            menuAuth: string;
            buttonAuth: string;
            systemRoleProtected: string;
          };
          user: {
            title: string;
            userName: string;
            userGender: string;
            nickName: string;
            userPhone: string;
            userEmail: string;
            userStatus: string;
            userRole: string;
            superuserProtected: string;
            form: {
              userName: string;
              userGender: string;
              nickName: string;
              userPhone: string;
              userEmail: string;
              userStatus: string;
              userRole: string;
            };
            addUser: string;
            editUser: string;
            gender: {
              male: string;
              female: string;
            };
          };
          menu: {
            home: string;
            title: string;
            id: string;
            parentId: string;
            menuType: string;
            menuName: string;
            routeName: string;
            routePath: string;
            pathParam: string;
            layout: string;
            page: string;
            i18nKey: string;
            icon: string;
            localIcon: string;
            iconTypeTitle: string;
            order: string;
            constant: string;
            keepAlive: string;
            href: string;
            hideInMenu: string;
            activeMenu: string;
            multiTab: string;
            fixedIndexInTab: string;
            query: string;
            button: string;
            buttonCode: string;
            buttonDesc: string;
            menuStatus: string;
            form: {
              home: string;
              menuType: string;
              menuName: string;
              routeName: string;
              routePath: string;
              pathParam: string;
              layout: string;
              page: string;
              i18nKey: string;
              icon: string;
              localIcon: string;
              order: string;
              keepAlive: string;
              href: string;
              hideInMenu: string;
              activeMenu: string;
              multiTab: string;
              fixedInTab: string;
              fixedIndexInTab: string;
              queryKey: string;
              queryValue: string;
              button: string;
              buttonCode: string;
              buttonDesc: string;
              menuStatus: string;
            };
            addMenu: string;
            editMenu: string;
            addChildMenu: string;
            type: {
              directory: string;
              menu: string;
            };
            iconType: {
              iconify: string;
              local: string;
            };
          };
          dept: {
            title: string;
            deptName: string;
            deptCode: string;
            parentDept: string;
            sort: string;
            deptStatus: string;
            form: {
              deptName: string;
              deptCode: string;
              parentDept: string;
              sort: string;
              deptStatus: string;
            };
            addDept: string;
            editDept: string;
          };
          dict: {
            title: string;
            dictName: string;
            dictCode: string;
            remark: string;
            dictStatus: string;
            dictItems: string;
            addDictType: string;
            editDictType: string;
            addItem: string;
            editItem: string;
            itemValue: string;
            itemLabel: string;
            itemSort: string;
            itemTagType: string;
            form: {
              dictName: string;
              dictCode: string;
              remark: string;
              dictStatus: string;
              itemLabel: string;
              itemValue: string;
              itemSort: string;
              itemTagType: string;
            };
          };
          log: {
            title: string;
            logTitle: string;
            module: string;
            actionType: string;
            operator: string;
            requestUri: string;
            requestMethod: string;
            ip: string;
            logStatus: string;
            executionTime: string;
            errorMsg: string;
            keywords: string;
            createTime: string;
          };
          config: {
            title: string;
            configName: string;
            configKey: string;
            configValue: string;
            configGroup: string;
            remark: string;
            configStatus: string;
            addConfig: string;
            editConfig: string;
            form: {
              configName: string;
              configKey: string;
              configValue: string;
              configGroup: string;
              remark: string;
              configStatus: string;
            };
          };
        };
        audit: {
          login: {
            title: string;
            time: string;
            username: string;
            result: string;
            success: string;
            failure: string;
            reason: string;
            invalidRequest: string;
            authFailed: string;
            internalError: string;
            ipAddress: string;
            userAgent: string;
          };
          event: {
            title: string;
            time: string;
            domain: string;
            result: string;
            success: string;
            failure: string;
            actor: string;
            operation: string;
            object: string;
            actionCode: string;
            resourceTypeCode: string;
            action: string;
            resourceType: string;
            resourceId: string;
            ipAddress: string;
            keywords: string;
            failReason: string;
            detail: string;
            changes: string;
            changedHint: string;
            field: string;
            before: string;
            after: string;
            copy: string;
            copied: string;
            copyUnsupported: string;
            userAgent: string;
            form: {
              domain: string;
              keywords: string;
            };
          };
        };
        cmdb: {
          host: {
            title: string;
            id: string;
            hostname: string;
            internalIp: string;
            externalIp: string;
            assetType: string;
            osFamily: string;
            osType: string;
            statusLabel: string;
            environment: string;
            region: string;
            spec: string;
            cpu: string;
            memory: string;
            disk: string;
            appCode: string;
            ownerTeam: string;
            credential: string;
            updatedAt: string;
            keyword: string;
            keywordPlaceholder: string;
            status: {
              active: string;
              inactive: string;
              retired: string;
            };
          };
        };
        task: {
          run: {
            title: string;
            id: string;
            workflowName: string;
            statusLabel: string;
            executionKind: string;
            runDomain: string;
            targetCount: string;
            triggeredBy: string;
            startedAt: string;
            finishedAt: string;
            duration: string;
            failureReason: string;
            workerPool: string;
            keyword: string;
            cancel: string;
            retry: string;
            rerun: string;
            snapshotExecutionHint: string;
            log: string;
            logTruncated: string;
            retryCreated: string;
            status: {
              pending: string;
              queued: string;
              running: string;
              waiting: string;
              cancel_requested: string;
              success: string;
              failed: string;
              timeout: string;
              canceled: string;
            };
            kind: {
              workflow: string;
              quick_command: string;
              playbook: string;
              module: string;
            };
            domain: {
              task: string;
              ops: string;
            };
          };
          detail: {
            live: string;
            fallback: string;
            node: {
              title: string;
              key: string;
              type: string;
              command: string;
              attempts: string;
              exitCode: string;
              hostResults: string;
              status: {
                pending: string;
                queued: string;
                running: string;
                success: string;
                failed: string;
                skipped: string;
                ignored: string;
                timeout: string;
                canceled: string;
              };
            };
            event: {
              title: string;
              dropped: string;
            };
            host: {
              hostname: string;
              ip: string;
              viewOutput: string;
              stdout: string;
              stderr: string;
            };
          };
        };
        ops: {
          engineSettings: {
            title: string;
            engineTab: string;
            description: string;
            overrideHint: string;
            timeout: string;
            forks: string;
            strategy: string;
            parallel: string;
            serial: string;
            rolling: string;
            serialBatch: string;
            maxFailPercentage: string;
            saveButton: string;
            loadError: string;
            saveSuccess: string;
          };
          commandFilter: {
            tab: string;
            description: string;
            enabledRuleCount: string;
            monthBlocked: string;
            rulesTitle: string;
            ruleSearchPlaceholder: string;
            addRule: string;
            pattern: string;
            patternRequired: string;
            matchMode: string;
            matchModeContains: string;
            matchModeExact: string;
            matchModePrefix: string;
            matchModeRegex: string;
            riskLevel: string;
            riskMedium: string;
            riskHigh: string;
            riskFatal: string;
            descriptionColumn: string;
            blockedCount: string;
            status: string;
            enabledState: string;
            disabledState: string;
            actions: string;
            enableAction: string;
            disableAction: string;
            interceptsTitle: string;
            interceptSearchPlaceholder: string;
            interceptTime: string;
            operator: string;
            command: string;
            target: string;
            hitRule: string;
            addTitle: string;
            editTitle: string;
            createSuccess: string;
            updateSuccess: string;
            enabled: string;
            disabled: string;
            deleteTitle: string;
            deleteConfirm: string;
            deleteSuccess: string;
          };
          quickExecute: {
            title: string;
            commandType: string;
            commandContent: string;
            hosts: string;
            workerPool: string;
            submit: string;
            submitted: string;
            form: {
              commandContentPlaceholder: string;
              commandContentRequired: string;
              hostIdsRequired: string;
              hostsPlaceholder: string;
              workerPoolPlaceholder: string;
            };
          };
        };
      };
      form: {
        required: string;
        userName: FormMsg;
        phone: FormMsg;
        pwd: FormMsg;
        confirmPwd: FormMsg;
        code: FormMsg;
        email: FormMsg;
      };
      dropdown: Record<Global.DropdownKey, string>;
      icon: {
        themeConfig: string;
        themeSchema: string;
        lang: string;
        fullscreen: string;
        fullscreenExit: string;
        reload: string;
        collapse: string;
        expand: string;
        pin: string;
        unpin: string;
      };
      datatable: {
        itemCount: string;
      };
    };

    type GetI18nKey<T extends Record<string, unknown>, K extends keyof T = keyof T> = K extends string
      ? T[K] extends Record<string, unknown>
        ? `${K}.${GetI18nKey<T[K]>}`
        : K
      : never;

    type I18nKey = GetI18nKey<Schema>;

    type TranslateOptions<Locales extends string> = import('vue-i18n').TranslateOptions<Locales>;

    interface $T {
      (key: I18nKey): string;
      (key: I18nKey, plural: number, options?: TranslateOptions<LangType>): string;
      (key: I18nKey, defaultMsg: string, options?: TranslateOptions<I18nKey>): string;
      (key: I18nKey, list: unknown[], options?: TranslateOptions<I18nKey>): string;
      (key: I18nKey, list: unknown[], plural: number): string;
      (key: I18nKey, list: unknown[], defaultMsg: string): string;
      (key: I18nKey, named: Record<string, unknown>, options?: TranslateOptions<LangType>): string;
      (key: I18nKey, named: Record<string, unknown>, plural: number): string;
      (key: I18nKey, named: Record<string, unknown>, defaultMsg: string): string;
    }
  }

  /** Service namespace */
  namespace Service {
    /** Other baseURL key */
    type OtherBaseURLKey = 'demo';

    interface ServiceConfigItem {
      /** The backend service base url */
      baseURL: string;
      /** The proxy pattern of the backend service base url */
      proxyPattern: string;
    }

    interface OtherServiceConfigItem extends ServiceConfigItem {
      key: OtherBaseURLKey;
    }

    /** The backend service config */
    interface ServiceConfig extends ServiceConfigItem {
      /** Other backend service config */
      other: OtherServiceConfigItem[];
    }

    interface SimpleServiceConfig extends Pick<ServiceConfigItem, 'baseURL'> {
      other: Record<OtherBaseURLKey, string>;
    }

    /** The backend service response data */
    type Response<T = unknown> = {
      /** The backend service response code */
      code: string;
      /** The backend service response message */
      msg: string;
      /** The backend service response data */
      data: T;
    };

    /** The demo backend service response data */
    type DemoResponse<T = unknown> = {
      /** The backend service response code */
      status: string;
      /** The backend service response message */
      message: string;
      /** The backend service response data */
      result: T;
    };
  }
}
