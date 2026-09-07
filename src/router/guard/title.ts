import type { Router } from 'vue-router';
import { useTitle } from '@vueuse/core';
import { useSiteConfigStore } from '@/store/modules/site-config';
import { $t } from '@/locales';

export function createDocumentTitleGuard(router: Router) {
  router.afterEach(to => {
    const { i18nKey, title } = to.meta;

    const routeTitle = i18nKey ? $t(i18nKey) : title;
    const documentTitle = useSiteConfigStore().composeDocumentTitle(routeTitle);

    useTitle(documentTitle);
  });
}
