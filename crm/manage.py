"""
Small admin CLI (run from the project root):

    python -m crm.manage set-admin 0501234567      # promote a registered user to admin
    python -m crm.manage unset-admin 0501234567
    python -m crm.manage sync                      # push rules, bindings and users to the proxy DB
"""
import sys

from crm.services import (
    get_user_by_phone,
    set_user_admin,
    sync_crm_rules_to_core,
    sync_ip_bindings_to_core,
    sync_users_to_core,
)


def main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[0] in ("set-admin", "unset-admin"):
        user = get_user_by_phone(argv[1])
        if not user:
            print(f"No user with phone {argv[1]}")
            return 1
        set_user_admin(user["id"], argv[0] == "set-admin")
        print(f"user {user['id']} is_admin={argv[0] == 'set-admin'}")
        return 0
    if argv[:1] == ["sync"]:
        sync_crm_rules_to_core(None)
        sync_ip_bindings_to_core()
        sync_users_to_core()
        print("synced")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
