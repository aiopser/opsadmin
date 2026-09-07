from django.core.management.base import BaseCommand

from apps.permission.seed_data import seed_system_settings


class Command(BaseCommand):
    help = "Initialize built-in user management and RBAC menus, permissions, and roles."

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-bind-superusers",
            action="store_true",
            help="Do not automatically bind the system_admin role to superusers.",
        )
        parser.add_argument(
            "--sync-menu-layout",
            action="store_true",
            help=(
                "Overwrite existing menu order, icons, and icon visibility with "
                "the SYSTEM_MENUS seed definitions. By default, existing layout "
                "changes made in the menu administration page are preserved."
            ),
        )

    def handle(self, *args, **options):
        result = seed_system_settings(
            bind_superusers=not options["skip_bind_superusers"],
            sync_menu_layout=options["sync_menu_layout"],
        )
        self.stdout.write(
            self.style.SUCCESS(
                "System settings initialized: "
                f"{result['api_permissions']} api permissions, "
                f"{result['menu_permissions']} menu permissions, "
                f"{result['menus']} menus, "
                f"{result['configs']} configs, "
                f"{result['dict_items']} dict items, "
                f"roles={','.join(result['roles'])}"
            )
        )
