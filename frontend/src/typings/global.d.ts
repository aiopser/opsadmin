export {};

type AppNotificationContent = string | { title: string; message?: string; duration?: number };

interface AppNotificationApi {
  success: (content: AppNotificationContent, detail?: string) => void;
  warning: (content: AppNotificationContent, detail?: string) => void;
  info: (content: AppNotificationContent, detail?: string) => void;
  error: (content: AppNotificationContent, detail?: string) => void;
}

declare global {
  export interface Window {
    /** NProgress instance */
    NProgress?: import('nprogress').NProgress;
    /** MessageBox instance */
    $messageBox?: import('element-plus').IElMessageBox;
    /** Message instance */
    $message?: import('element-plus').Message;
    /** Notification instance（右上角通知；内容可传标题字符串或 { title, message } 对象） */
    $notification?: AppNotificationApi;
  }

  /** Build time of the project */
  export const BUILD_TIME: string;
}
