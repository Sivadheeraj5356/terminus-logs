# GPG tag gate

Release tag name: reelseal-v1.0.0
GNUPGHOME: /app/fixtures/gnupg
Git repository for tags: /app/state/release-git

release-tag must create an annotated GPG-signed tag. package must refuse to write /app/output/release-package.tar unless:

1. The tag exists
2. git verify-tag reelseal-v1.0.0 succeeds under GNUPGHOME=/app/fixtures/gnupg

Unsigned or missing tags yield exit code 3 and no package file.
