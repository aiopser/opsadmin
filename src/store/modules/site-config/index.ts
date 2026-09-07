import { ref } from 'vue';
import { defineStore } from 'pinia';
import { fetchGetPublicConfigs } from '@/service/api';
import { SetupStoreId } from '@/enum';

/**
 * 站点公开配置缓存（对应后端 basic.* 配置项）
 *
 * 登录页标题、浏览器标题等展示型配置在登录前就要使用，
 * 因此走后端公开接口（/api/v1/configs/public，无需认证），
 * 会话内只拉取一次；未配置时由消费方回退到 i18n 文案。
 */
export const useSiteConfigStore = defineStore(SetupStoreId.SiteConfig, () => {
  /** 系统名称（basic.system.name），用于浏览器标题 */
  const siteName = ref('');

  /** 登录页主标题（basic.login.title） */
  const loginTitle = ref('');

  /** 默认头像地址（basic.user.default_avatar），暂未接 UI，预留 */
  const defaultAvatar = ref('');

  let initialized = false;

  async function init() {
    if (initialized) {
      return;
    }
    initialized = true;

    const { error, data } = await fetchGetPublicConfigs();

    if (!error && data) {
      siteName.value = data['basic.system.name'] ?? '';
      loginTitle.value = data['basic.login.title'] ?? '';
      defaultAvatar.value = data['basic.user.default_avatar'] ?? '';
    }
  }

  /** 浏览器标题：路由标题 + 站点名后缀（未配置站点名时保持原样） */
  function composeDocumentTitle(routeTitle?: string) {
    if (!routeTitle) {
      return routeTitle;
    }
    return siteName.value ? `${routeTitle} - ${siteName.value}` : routeTitle;
  }

  return {
    siteName,
    loginTitle,
    defaultAvatar,
    init,
    composeDocumentTitle
  };
});
