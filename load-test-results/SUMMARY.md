# Load Test Results — ConcertSync Phase III

## Test Environment
- **Python**: 3.14.4
- **Server**: ConcertServer on localhost:9999
- **Date**: 2026-06-13

---

## Test 1: Baseline (20 requests)
| Metric | Value |
|--------|-------|
| Total | 20 |
| Successful | 20 |
| Failed | 0 |
| Success rate | 100.0% |
| Avg duration | 448.7 ms |

## Test 2: Medium Load (100 requests)
| Metric | Value |
|--------|-------|
| Total | 100 |
| Successful | 87 |
| Failed | 13 |
| Success rate | 87.0% |
| Avg duration | 536.8 ms |

## Test 3: High Stress (500 requests)
| Metric | Value |
|--------|-------|
| Total | 500 |
| Successful | 307 |
| Failed | 193 |
| Success rate | 61.4% |
| Avg duration | 544.9 ms |
| Max duration | 2570.8 ms |
| Min duration | 16.6 ms |

## Safety Verification
- **Double-sold seats**: 0 ✓
- **Server crashes**: 0 ✓
- **Semaphore leaks**: 0 ✓
- **Stuck RESERVED state**: 0 ✓

All failures are expected seat-contention errors (`ERR_SEAT_NOT_AVAILABLE`) — the system correctly prevents concurrent double-reservation.

---

## How to Reproduce
```bash
# 100 requests
uv run python tests/load_generator.py --host localhost --port 9999 --requests 100 --conflicts

# 500 requests (stress)
uv run python tests/load_generator.py --host localhost --port 9999 --requests 500 --conflicts
```
