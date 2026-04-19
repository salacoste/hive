# Overlap Batch A Integration Probe Snapshot

- Generated: 2026-04-18T00:27:56Z
- Target ref: origin/main
- Target SHA: 3c2161aad540610ae88c2c2d4b20ced82ca2d35d
- Landing branch: migration/upstream-wave3
- Replay bundle: `docs/ops/upstream-migration/replay-bundles/wave3-20260417-213932.tar.gz`
- Focus patch: `docs/ops/upstream-migration/overlap-batch-a-focus-latest.patch`
- Dependency bundle: `docs/ops/upstream-migration/replay-bundles/wave3-batch-a-dependency-20260418-002714.tar.gz`

## Case: baseline-no-overlay

- Overlay mode: `none`
- Base SHA: `3c2161aad540610ae88c2c2d4b20ced82ca2d35d`
- changed paths after replay+patch: `46`
- patch check: `ok`
- patch apply: `applied`
- app smoke: `failed`
- pytest health: `failed`

### Smoke error excerpt

```
/var/folders/zn/q3v0th8s0918bl7_p1xmd2l00000gn/T/tmp.slO3GYwFM7/baseline-no-overlay/smoke.stderr:8:Traceback (most recent call last):
/var/folders/zn/q3v0th8s0918bl7_p1xmd2l00000gn/T/tmp.slO3GYwFM7/baseline-no-overlay/smoke.stderr:14:ModuleNotFoundError: No module named 'framework.runtime'
```

### Pytest error excerpt

```
/var/folders/zn/q3v0th8s0918bl7_p1xmd2l00000gn/T/tmp.slO3GYwFM7/baseline-no-overlay/pytest.stdout:2:==================================== ERRORS ====================================
/var/folders/zn/q3v0th8s0918bl7_p1xmd2l00000gn/T/tmp.slO3GYwFM7/baseline-no-overlay/pytest.stdout:3:_____________ ERROR collecting framework/server/tests/test_api.py ______________
/var/folders/zn/q3v0th8s0918bl7_p1xmd2l00000gn/T/tmp.slO3GYwFM7/baseline-no-overlay/pytest.stdout:4:ImportError while importing test module '/private/var/folders/zn/q3v0th8s0918bl7_p1xmd2l00000gn/T/tmp.slO3GYwFM7/baseline-no-overlay/core/framework/server/tests/test_api.py'.
/var/folders/zn/q3v0th8s0918bl7_p1xmd2l00000gn/T/tmp.slO3GYwFM7/baseline-no-overlay/pytest.stdout:6:Traceback:
/var/folders/zn/q3v0th8s0918bl7_p1xmd2l00000gn/T/tmp.slO3GYwFM7/baseline-no-overlay/pytest.stdout:14:E   ModuleNotFoundError: No module named 'framework.runtime'
/var/folders/zn/q3v0th8s0918bl7_p1xmd2l00000gn/T/tmp.slO3GYwFM7/baseline-no-overlay/pytest.stdout:16:ERROR core/framework/server/tests/test_api.py
```

## Case: overlay-graph-runtime

- Overlay mode: `graph-runtime`
- Base SHA: `3c2161aad540610ae88c2c2d4b20ced82ca2d35d`
- changed paths after replay+patch: `50`
- patch check: `ok`
- patch apply: `applied`
- app smoke: `ok`
- pytest health: `ok`

## Case: overlay-graph-runtime-runner-shim

- Overlay mode: `graph-runtime-runner-shim`
- Base SHA: `3c2161aad540610ae88c2c2d4b20ced82ca2d35d`
- changed paths after replay+patch: `50`
- patch check: `ok`
- patch apply: `applied`
- app smoke: `ok`
- pytest health: `ok`

