"""Evaluate data-only workflow conditions without calls or object access."""

from jinja2 import StrictUndefined, nodes
from jinja2.exceptions import TemplateError
from jinja2.sandbox import SandboxedEnvironment


class InvalidCondition(ValueError):
    pass


_ENV = SandboxedEnvironment(undefined=StrictUndefined, autoescape=False)
_ENV.globals.clear()
_ENV.filters.clear()
_ENV.tests.clear()
_ALLOWED = (
    nodes.Template,
    nodes.Output,
    nodes.Name,
    nodes.Const,
    nodes.Getattr,
    nodes.Getitem,
    nodes.Compare,
    nodes.Operand,
    nodes.And,
    nodes.Or,
    nodes.Not,
    nodes.List,
    nodes.Tuple,
)


def expression_is_true(expression: str, context: dict) -> bool:
    if not isinstance(expression, str) or not expression.strip():
        raise InvalidCondition("Condition must be a nonempty expression")
    if len(expression) > 4096:
        raise InvalidCondition("Condition is too long")
    try:
        tree = _ENV.parse("{{ " + expression + " }}")
        for item in (tree, *tree.find_all(nodes.Node)):
            if not isinstance(item, _ALLOWED):
                raise InvalidCondition("Condition permits only data comparisons")
            if isinstance(item, nodes.Getattr) and item.attr.startswith("_"):
                raise InvalidCondition("Private attributes are forbidden")
            if isinstance(item, nodes.Name) and item.name not in context:
                raise InvalidCondition("Unknown condition variable")
        return bool(
            _ENV.compile_expression(expression, undefined_to_none=False)(context)
        )
    except (TemplateError, TypeError, ValueError) as exc:
        raise InvalidCondition("Invalid workflow condition") from exc
