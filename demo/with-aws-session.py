#!/usr/bin/env python3
"""Bridge AWS CLI login to older SDKs, with renewable process credentials."""
import configparser
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile


def session_config(env, aws):
    original_config = env.get("AWS_CONFIG_FILE", str(Path.home() / ".aws/config"))
    original_credentials = env.get("AWS_SHARED_CREDENTIALS_FILE", str(Path.home() / ".aws/credentials"))
    profile = env.get("AWS_PROFILE", env.get("AWS_DEFAULT_PROFILE", "default"))
    # The nested CLI reads the ORIGINAL profile, never this process profile.
    command = ["env", f"AWS_CONFIG_FILE={original_config}",
               f"AWS_SHARED_CREDENTIALS_FILE={original_credentials}",
               f"AWS_PROFILE={profile}", f"AWS_DEFAULT_PROFILE={profile}",
               aws, "configure", "export-credentials", "--profile", profile, "--format", "process"]
    config = configparser.RawConfigParser()
    config["profile community-day-session"] = {"credential_process": shlex.join(command)}
    return config


def main():
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python3 demo/with-aws-session.py <command> [arguments...]")
    env = os.environ.copy()
    if env.get("AWS_ACCESS_KEY_ID"):
        # Explicit environment credentials already work with Terraform's SDK.
        return subprocess.call(sys.argv[1:], env=env)
    aws = shutil.which("aws")
    if not aws:
        raise SystemExit("AWS CLI is required.")
    with tempfile.TemporaryDirectory(prefix="community-day-aws-") as folder:
        path = Path(folder) / "config"
        with path.open("w") as f:
            session_config(env, aws).write(f)
        path.chmod(0o600)
        empty_credentials = Path(folder) / "credentials"
        empty_credentials.touch(mode=0o600)
        env.update(AWS_CONFIG_FILE=str(path), AWS_PROFILE="community-day-session",
                   AWS_SHARED_CREDENTIALS_FILE=str(empty_credentials),
                   AWS_DEFAULT_PROFILE="community-day-session", AWS_SDK_LOAD_CONFIG="1")
        # No credentials are written to disk. The SDK refreshes credential_process
        # using the Expiration returned by AWS CLI during long operations.
        return subprocess.call(sys.argv[1:], env=env)


if __name__ == "__main__":
    raise SystemExit(main())
