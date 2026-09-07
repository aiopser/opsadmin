import type { App } from 'vue';
import { createI18n } from 'vue-i18n';
import { localStg } from '@/utils/storage';
import messages from './locale';

const i18n = createI18n({
  locale: localStg.get('lang') || 'zh-CN',
  fallbackLocale: 'en',
  messages,
  legacy: false
});

/**
 * Setup plugin i18n
 *
 * @param app
 */
export function setupI18n(app: App) {
  app.use(i18n);
}

export const $t = i18n.global.t as App.I18n.$T;

/** 判断国际化 key 是否存在于语言文件中（防止无效 key 原样显示） */
export const $te = i18n.global.te as (key: string) => boolean;

export function setLocale(locale: App.I18n.LangType) {
  i18n.global.locale.value = locale;
}
