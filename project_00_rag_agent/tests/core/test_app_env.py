"""APP_ENV / 生产护栏单测。"""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch


class TestAppEnvConfig(unittest.TestCase):
    def test_resolve_app_env_defaults_local(self):
        from app.core.config import resolve_app_env

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("APP_ENV", None)
            # resolve 只看当前环境变量；未设置时为 local
            with patch.dict(os.environ, {"APP_ENV": ""}, clear=False):
                os.environ.pop("APP_ENV", None)
                self.assertEqual(resolve_app_env(), "local")

    def test_resolve_app_env_accepts_known_values(self):
        from app.core.config import resolve_app_env

        for value in ("local", "test", "prod"):
            with patch.dict(os.environ, {"APP_ENV": value}):
                self.assertEqual(resolve_app_env(), value)

    def test_prod_rejects_weak_jwt(self):
        from app.core.config import Settings

        with self.assertRaises(ValueError):
            Settings(
                APP_ENV="prod",
                JWT_SECRET="change-me-in-production",
            )

    def test_prod_accepts_strong_jwt(self):
        from app.core.config import Settings

        s = Settings(
            APP_ENV="prod",
            JWT_SECRET="a" * 32,
            CHECKPOINTER_BACKEND="postgres",
        )
        self.assertEqual(s.app_env, "prod")
        self.assertEqual(len(s.jwt_secret), 32)


if __name__ == "__main__":
    unittest.main()
