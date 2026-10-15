"""Grant roles to a Google-signed-in user via Firebase custom claims (they take effect at next sign-in).

    python -m scripts.grant_roles someone@example.com engineering sre
"""
import sys

from firebase_admin import auth

from app.firebase import get_firebase_app


def main() -> None:
    email, roles = sys.argv[1], sys.argv[2:]
    app = get_firebase_app()
    user = auth.get_user_by_email(email, app=app)
    auth.set_custom_user_claims(user.uid, {"roles": roles}, app=app)
    print(f"{email} ({user.uid}) now has roles: {roles or 'none (public documents only)'}")


if __name__ == "__main__":
    main()
