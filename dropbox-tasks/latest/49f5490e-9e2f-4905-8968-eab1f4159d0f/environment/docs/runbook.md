# Runbook

Build and regenerate policy:

```sh
/app/scripts/build.sh
/app/scripts/regenerate-policy.sh
```

Create a disposable lab from the bundled fixtures and generated policy:

```sh
/app/scripts/new-lab.sh /tmp/auth-lab
```

Useful commands:

```sh
/app/bin/authctl login --root /tmp/auth-lab --user alice --method password --secret correct-horse --session s1
/app/bin/authctl logout --root /tmp/auth-lab --session s1
/app/bin/authctl snapshot --root /tmp/auth-lab --user alice
/app/bin/authctl rebuild --root /tmp/auth-lab
/app/bin/authctl checkpoint --root /tmp/auth-lab --label baseline
/app/bin/authctl restore --root /tmp/auth-lab --label baseline
```

Denied logins return a nonzero status. Module probes do not commit effects and exist only for diagnosis. File digests use `openssl dgst -sha256`.
