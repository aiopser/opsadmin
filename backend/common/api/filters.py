from rest_framework.filters import SearchFilter


class KeywordSearchFilter(SearchFilter):
    """兼容前端 keywords 参数的搜索过滤器。

    DRF 默认 SearchFilter 监听 `search` 参数，而前端统一传 `keywords`，
    此处覆盖 search_param 使声明式 search_fields 直接生效，
    替代各 ViewSet 在 get_queryset 中手写的 Q(...icontains) 逻辑。
    """

    search_param = "keywords"
