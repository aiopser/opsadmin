from casbin import persist

from ..models import CasbinRule


class Adapter(persist.Adapter):
    """the interface for Casbin adapters."""

    def __init__(self):
        self.policy_model = CasbinRule

    def load_policy(self, model):
        """loads all policy rules from the storage."""
        for rule in self.policy_model.objects.all().order_by("id"):
            line = ", ".join(
                [
                    value
                    for value in [
                        rule.ptype,
                        rule.v0,
                        rule.v1,
                        rule.v2,
                        rule.v3,
                        rule.v4,
                        rule.v5,
                    ]
                    if value
                ]
            )
            persist.load_policy_line(line, model)

    def _create_policy_line(self, ptype, rule):
        values = list(rule[:6])
        return self.policy_model(
            ptype=ptype,
            v0=values[0] if len(values) > 0 else None,
            v1=values[1] if len(values) > 1 else None,
            v2=values[2] if len(values) > 2 else None,
            v3=values[3] if len(values) > 3 else None,
            v4=values[4] if len(values) > 4 else None,
            v5=values[5] if len(values) > 5 else None,
        )

    def save_policy(self, model):
        """saves all policy rules to the storage."""
        rows = []
        for sec in ("p", "g"):
            if sec not in model.model:
                continue
            for ptype, assertion in model.model[sec].items():
                for rule in assertion.policy:
                    rows.append(self._create_policy_line(ptype, rule))
        self.policy_model.objects.all().delete()
        self.policy_model.objects.bulk_create(rows, ignore_conflicts=True)
        return True

    def add_policy(self, sec, ptype, rule):
        """adds a policy rule to the storage."""
        self.policy_model.objects.get_or_create(
            ptype=ptype,
            v0=rule[0] if len(rule) > 0 else None,
            v1=rule[1] if len(rule) > 1 else None,
            v2=rule[2] if len(rule) > 2 else None,
            v3=rule[3] if len(rule) > 3 else None,
            v4=rule[4] if len(rule) > 4 else None,
            v5=rule[5] if len(rule) > 5 else None,
        )

    def remove_policy(self, sec, ptype, rule):
        """removes a policy rule from the storage."""
        filters = {"ptype": ptype}
        for index, value in enumerate(rule[:6]):
            filters[f"v{index}"] = value
        self.policy_model.objects.filter(**filters).delete()

    def remove_filtered_policy(self, sec, ptype, field_index, *field_values):
        """removes policy rules that match the filter from the storage.
        This is part of the Auto-Save feature.
        """
        filters = {"ptype": ptype}
        for index, value in enumerate(field_values):
            if value:
                filters[f"v{field_index + index}"] = value
        self.policy_model.objects.filter(**filters).delete()
