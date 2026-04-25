## What

<!-- Short summary of the change. -->

## Why

<!-- The motivation. Link the issue / ticket. -->

## How

<!-- Implementation notes a reviewer needs to follow the diff. -->

## Test plan

- [ ] Unit tests pass (`pytest -m unit`)
- [ ] Integration tests pass (`pytest -m integration`)
- [ ] Manually verified the affected pipeline / endpoint

## Risk

- [ ] Touches migrations
- [ ] Touches gold marts (REFRESH path)
- [ ] Touches a third-party connector (rate-limit / quota implications)
- [ ] Adds a new env var (documented in `.env.example`)

## Rollback plan

<!-- How do we revert if this breaks prod? -->
