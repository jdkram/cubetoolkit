# Pool management: dormancy + last-gasp email (9.96) — unreleased

- [ ] Pool health page at `/volunteers/view/pool-health/`: "Preview auto-dormancy" section lists candidates and reason
  RESULT:

- [ ] "Apply dormancy" action marks candidates as dormant; list updates (idempotent on re-run)
  RESULT:

- [ ] "Restore to active" button on a dormant/retired row works
  RESULT:

- [ ] `retention_exempt` checkbox on volunteer profile: volunteer excluded from purge candidates after saving
  RESULT:

- [ ] Last-gasp email: preview renders correctly with configured subject/body from Site Settings
  RESULT:

- [ ] Sending a last-gasp email logs to `LastGaspEmailLog`; attempting to send again within cooldown is blocked
  RESULT:

- [ ] Anonymise view: blocked with a clear error if volunteer has an active membership
  RESULT:

- [ ] `purge_stale_volunteers` management command runs without error; `--include-members` flag needed to include active members
  RESULT:
