from django.db import models

from common.authmodel import AuthorModelMixin
from common.models import StandardModelMixin


class WikiPage(AuthorModelMixin, StandardModelMixin):
    """知识库节点：目录（is_folder=True）与文档（is_folder=False）共用同一棵树。"""

    title = models.CharField(max_length=128)
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        related_name="children",
        null=True,
        blank=True,
    )
    is_folder = models.BooleanField(default=False)
    content = models.TextField(blank=True, default="")
    sort = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.title

    def collect_self_and_descendant_ids(self):
        """收集自身及全部后代节点 id，用于移动节点时的防环校验。"""
        ids = {self.pk}
        frontier = [self.pk]
        while frontier:
            frontier = list(
                WikiPage.objects.filter(parent_id__in=frontier).values_list(
                    "id", flat=True
                )
            )
            ids.update(frontier)
        return ids

    class Meta:
        db_table = "wiki_page"
        ordering = ["sort", "id"]
        indexes = [
            models.Index(fields=["parent", "sort"], name="wiki_page_parent_sort_idx")
        ]
