"""The renewable credentials subprocess must not recurse into its own profile."""
import importlib.util
from pathlib import Path
import shlex
import unittest

spec = importlib.util.spec_from_file_location("aws_session", Path(__file__).with_name("with-aws-session.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SessionConfigTests(unittest.TestCase):
    def test_credential_process_restores_original_profile_and_paths(self):
        config = module.session_config({"AWS_CONFIG_FILE": "/tmp/a b/config",
                                        "AWS_SHARED_CREDENTIALS_FILE": "/tmp/a b/credentials",
                                        "AWS_PROFILE": "original profile"}, "/opt/aws cli/aws")
        command = shlex.split(config["profile community-day-session"]["credential_process"])
        self.assertIn("AWS_CONFIG_FILE=/tmp/a b/config", command)
        self.assertIn("AWS_SHARED_CREDENTIALS_FILE=/tmp/a b/credentials", command)
        self.assertIn("AWS_PROFILE=original profile", command)
        self.assertEqual(command[-5:], ["export-credentials", "--profile", "original profile", "--format", "process"])
        self.assertNotIn("AWS_PROFILE=community-day-session", command)

    def test_config_does_not_embed_credentials(self):
        config = module.session_config({"AWS_SECRET_ACCESS_KEY": "never-write-me"}, "/usr/bin/aws")
        value = config["profile community-day-session"]["credential_process"]
        self.assertNotIn("never-write-me", value)
        self.assertIn("--profile default", value)


if __name__ == "__main__":
    unittest.main()
