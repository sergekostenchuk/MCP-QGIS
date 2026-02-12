# MVP Release Checklist

- [ ] All `pytest` suites pass (unit + integration + e2e + regression)
- [ ] Coverage >= 80%
- [ ] Smoke script passes on target profile
- [ ] 5 reference scenarios from `testdata/` are green
- [ ] SLO/SLA integration checks pass
- [ ] Backup/restore scripts verified on current runtime snapshot
- [ ] `git_snapshot` works on clean and dirty repository states
- [ ] Audit log is produced for successful and failed requests
- [ ] Security controls verified (`role`, allowlist, HITL token)
- [ ] Release notes prepared
