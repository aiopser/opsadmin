"""Public execution facade for the migrated JumpServer runner."""

from .adapters import AnsibleExecutionInput


class JumpServerAnsibleService:
    def run(self, execution: AnsibleExecutionInput, **callbacks):
        # Keep optional Ansible dependencies out of Django startup imports.
        from .ansible import AdHocRunner, PlaybookRunner

        callback = callbacks.pop("callback", None)

        common = {
            "inventory": str(execution.inventory),
            "project_dir": str(execution.private_data_dir),
            "extra_vars": dict(execution.extra_vars),
        }
        if execution.playbook:
            runner = PlaybookRunner(
                playbook=str(execution.playbook), callback=callback, **common
            )
        else:
            if not execution.module:
                raise ValueError("module is required for an ad-hoc execution")
            runner = AdHocRunner(
                pattern=execution.host_pattern,
                module=execution.module,
                module_args=execution.module_args,
                job_module=execution.module,
                timeout=execution.timeout,
                **common,
            )
        if callback is not None:
            runner.cb = callback
        runner.envs.update(execution.env_vars)
        return runner.run(verbosity=execution.verbosity, **callbacks)
