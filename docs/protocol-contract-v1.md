# ConcertSync JSON Protocol Contract v1.0

**Version:** 1.0  
**Status:** Formal Specification  
**Last Updated:** 2026-04-18  

---

## Table of Contents
1. [Overview](#overview)
2. [Protocol Semantics](#protocol-semantics)
3. [Request Schemas](#request-schemas)
4. [Response Schemas](#response-schemas)
5. [Error Codes](#error-codes)
6. [Data Types](#data-types)
7. [Examples](#examples)
8. [Validation Rules](#validation-rules)
9. [Versioning & Changelog](#versioning--changelog)

---

## Overview

The ConcertSync server uses **JSON over TCP** for client-server communication. 

- **Transport:** Raw TCP sockets (port 9999 by default)
- **Serialization:** JSON (UTF-8 encoded)
- **Frame Format:** Complete JSON object per send/receive (no delimiters; caller responsible for message boundaries)
- **Protocol Version:** v1.0 (required for v2+ compatibility)

### Key Principles

1. **Deterministic Error Codes:** Every failure/error response includes a unique `error_code` identifying the problem
2. **Status Triality:** Responses always have `status` = one of: `"SUCCESS"`, `"FAILURE"`, `"ERROR"`
3. **Validation Dual-Layer:** Client validates before sending; Server validates on receipt
4. **Atomicity by Action:** Each action (RESERVE, CONFIRM, CANCEL, QUERY, QUERY_SEAT_MAP) is atomic at the server
5. **Transaction Context:** RESERVE returns `transaction_id`; CONFIRM/CANCEL reference that ID

---

## Protocol Semantics

### Actions Supported

| Action | Semantics | Idempotent |
|--------|-----------|-----------|
| `RESERVE` | Reserve a single specific seat in a section; returns transient `transaction_id` with TTL | No (creates new tx each time) |
| `RESERVE_BATCH` | Reserve multiple specific seats (same or different sections) atomically; returns single `transaction_id` covering all seats | No (creates new tx each time) |
| `CONFIRM` | Convert active reservation to permanent SOLD state (applies to all seats in tx) | Yes (second attempt on same tx_id → success w/ same result) |
| `CANCEL` | Release reservation and revert all seats to AVAILABLE (applies to all seats in tx) | Yes (second attempt on already-cancelled tx_id → idempotent) |
| `QUERY` | Fetch current seat availability counts by section | Yes (no state change) |
| `QUERY_SEAT_MAP` | Fetch full seat-state matrix by section (AVAILABLE/RESERVED/SOLD) | Yes (no state change) |

---

## Request Schemas

### RESERVE Request

```json
{
  "action": "RESERVE",
  "section": "<SECTION_NAME>",
  "row": <int>,
  "col": <int>
}
```

**Field Definitions:**

| Field | Type | Required | Constraints | Example |
|-------|------|----------|-------------|---------|
| `action` | string | ✅ | Literal: `"RESERVE"` | `"RESERVE"` |
| `section` | string | ✅ | Enum: `"VIP"`, `"PREFERENTIAL"`, `"GENERAL"` | `"VIP"` |
| `row` | integer | ✅ | 0 ≤ row < max_rows_in_section | `5` |
| `col` | integer | ✅ | 0 ≤ col < max_cols_in_section | `10` |

**Capacity per Section** (from `src/utils/config.py`):
- `VIP`: 5 rows x 10 cols = 50 seats
- `PREFERENTIAL`: 10 rows x 15 cols = 150 seats
- `GENERAL`: 20 rows × 20 cols = 400 seats

---

### RESERVE_BATCH Request

```json
{
  "action": "RESERVE_BATCH",
  "seats": [
    {"section": "<SECTION_NAME>", "row": <int>, "col": <int>},
    {"section": "<SECTION_NAME>", "row": <int>, "col": <int>}
  ]
}
```

**Field Definitions:**

| Field | Type | Required | Constraints | Example |
|-------|------|----------|-------------|---------|
| `action` | string | ✅ | Literal: `"RESERVE_BATCH"` | `"RESERVE_BATCH"` |
| `seats` | array | ✅ | Array of seat objects; at least 1, at most 10 | `[{...}]` |
| `seats[i].section` | string | ✅ | Enum: `"VIP"`, `"PREFERENTIAL"`, `"GENERAL"` | `"VIP"` |
| `seats[i].row` | integer | ✅ | 0 ≤ row < max_rows_in_section | `5` |
| `seats[i].col` | integer | ✅ | 0 ≤ col < max_cols_in_section | `10` |

**Additional Constraints:**

- **Batch size:** 1 ≤ seats.length ≤ 10
- **Uniqueness:** No duplicate (section, row, col) tuples allowed
- **Atomicity:** All seats reserved together or none; no partial success

**Validation Errors:**

| Condition | Error Code | Status |
|-----------|-----------|--------|
| seats array empty or > 10 | `ERR_INVALID_PAYLOAD` | ERROR |
| Duplicate seat coordinates | `ERR_INVALID_PAYLOAD` | ERROR |
| Any seat has invalid section | `ERR_INVALID_SECTION` | ERROR |
| Any seat has invalid coordinates (negative, out-of-bounds) | `ERR_INVALID_COORDINATES` or `ERR_SEAT_OUT_OF_BOUNDS` | ERROR |
| Any seat already unavailable | `ERR_SEAT_NOT_AVAILABLE` | FAILURE |
| Any section at capacity (semaphore) | `ERR_NO_CAPACITY` | FAILURE |

---

### CONFIRM Request

```json
{
  "action": "CONFIRM",
  "transaction_id": "<tx_id>"
}
```

**Field Definitions:**

| Field | Type | Required | Constraints | Example |
|-------|------|----------|-------------|---------|
| `action` | string | ✅ | Literal: `"CONFIRM"` | `"CONFIRM"` |
| `transaction_id` | string | ✅ | Format: UUID or server-generated unique ID; must be ACTIVE | `"tx_12345"` |

---

### CANCEL Request

```json
{
  "action": "CANCEL",
  "transaction_id": "<tx_id>"
}
```

**Field Definitions:**

| Field | Type | Required | Constraints | Example |
|-------|------|----------|-------------|---------|
| `action` | string | ✅ | Literal: `"CANCEL"` | `"CANCEL"` |
| `transaction_id` | string | ✅ | Format: UUID or server-generated unique ID; must be ACTIVE | `"tx_12345"` |

---

### QUERY Request

```json
{
  "action": "QUERY"
}
```

**Field Definitions:**

| Field | Type | Required | Constraints | Example |
|-------|------|----------|-------------|---------|
| `action` | string | ✅ | Literal: `"QUERY"` | `"QUERY"` |

---

### QUERY_SEAT_MAP Request

```json
{
  "action": "QUERY_SEAT_MAP"
}
```

**Field Definitions:**

| Field | Type | Required | Constraints | Example |
|-------|------|----------|-------------|---------|
| `action` | string | ✅ | Literal: `"QUERY_SEAT_MAP"` | `"QUERY_SEAT_MAP"` |

---

## Response Schemas

### SUCCESS Response (RESERVE)

```json
{
  "status": "SUCCESS",
  "transaction_id": "<tx_id>",
  "ttl": <int>
}
```

**Field Definitions:**

| Field | Type | Presence | Semantics |
|-------|------|----------|-----------|
| `status` | string | Always | Literal: `"SUCCESS"` |
| `transaction_id` | string | Always | Unique identifier for this reservation; use for CONFIRM/CANCEL |
| `ttl` | integer | Always | Seconds until reservation expires (from config `RESERVATION_TTL`); typically 300 |

---

### SUCCESS Response (RESERVE_BATCH)

```json
{
  "status": "SUCCESS",
  "transaction_id": "<tx_id>",
  "reserved_seats": [
    {"section": "VIP", "row": 0, "col": 0},
    {"section": "VIP", "row": 0, "col": 1},
    {"section": "PREFERENTIAL", "row": 5, "col": 10}
  ],
  "ttl": <int>
}
```

**Field Definitions:**

| Field | Type | Presence | Semantics |
|-------|------|----------|-----------|
| `status` | string | Always | Literal: `"SUCCESS"` |
| `transaction_id` | string | Always | Unique identifier for batch reservation; use for CONFIRM/CANCEL (applies to all seats in batch) |
| `reserved_seats` | array | Always | Echo of all reserved seats as requested; facilitates transaction logging |
| `ttl` | integer | Always | Seconds until batch reservation expires (from config `RESERVATION_TTL`); typically 300; applies to entire batch |

**Atomicity Guarantee:**
- All seats transition from AVAILABLE → RESERVED simultaneously
- Single transaction_id covers entire batch
- CONFIRM/CANCEL apply to all seats in batch

---

### SUCCESS Response (CONFIRM)

```json
{
  "status": "SUCCESS",
  "transaction_id": "<tx_id>"
}
```

**Field Definitions:**

| Field | Type | Presence | Semantics |
|-------|------|----------|-----------|
| `status` | string | Always | Literal: `"SUCCESS"` |
| `transaction_id` | string | Always | Echo of the confirmed transaction ID |

---

### SUCCESS Response (CANCEL)

```json
{
  "status": "SUCCESS",
  "transaction_id": "<tx_id>"
}
```

**Field Definitions:**

| Field | Type | Presence | Semantics |
|-------|------|----------|-----------|
| `status` | string | Always | Literal: `"SUCCESS"` |
| `transaction_id` | string | Always | Echo of the cancelled transaction ID |

---

### SUCCESS Response (QUERY)

```json
{
  "status": "SUCCESS",
  "sections": {
    "VIP": {
      "available": <int>,
      "reserved": <int>,
      "sold": <int>
    },
    "PREFERENTIAL": {
      "available": <int>,
      "reserved": <int>,
      "sold": <int>
    },
    "GENERAL": {
      "available": <int>,
      "reserved": <int>,
      "sold": <int>
    }
  }
}
```

**Field Definitions:**

| Path | Type | Semantics |
|------|------|-----------|
| `status` | string | Literal: `"SUCCESS"` |
| `sections[section_name].available` | integer | Count of seats in AVAILABLE state |
| `sections[section_name].reserved` | integer | Count of seats in RESERVED state (active transactions) |
| `sections[section_name].sold` | integer | Count of seats in SOLD state (confirmed transactions) |

**Invariants:**
- `available + reserved + sold = total_capacity_for_section`
- All counts ≥ 0

**Atomicity & Idempotence:**
- QUERY is **atomic**: returns a consistent snapshot despite concurrent modifications
- QUERY is **idempotent**: safe to retry on failure; multiple calls without modifications return identical results
- No transient states exposed: counts reflect atomic moment-in-time state

---

### SUCCESS Response (QUERY_SEAT_MAP)

```json
{
  "status": "SUCCESS",
  "seat_map": {
    "VIP": [["AVAILABLE", "RESERVED"], ["SOLD", "AVAILABLE"]],
    "PREFERENTIAL": [["AVAILABLE", "AVAILABLE"]],
    "GENERAL": [["AVAILABLE", "AVAILABLE"]]
  }
}
```

**Field Definitions:**

| Path | Type | Semantics |
|------|------|-----------|
| `status` | string | Literal: `"SUCCESS"` |
| `seat_map[section_name]` | array[row][col] | Complete seat-state grid for each section |
| `seat_map[section_name][r][c]` | string | One of: `"AVAILABLE"`, `"RESERVED"`, `"SOLD"` |

---

### FAILURE Response

```json
{
  "status": "FAILURE",
  "error_code": "<ERROR_CODE>",
  "message": "<human_readable_message>"
}
```

**Field Definitions:**

| Field | Type | Presence | Semantics |
|-------|------|----------|-----------|
| `status` | string | Always | Literal: `"FAILURE"` |
| `error_code` | string | Always | Deterministic error identifier (see [Error Codes](#error-codes)) |
| `message` | string | Always | Human-readable explanation suited for logging/debugging |

**When to use FAILURE:**
- Business logic prevented the operation (e.g., seat already sold, no capacity, transaction not found)
- Client request was syntactically valid but semantically invalid for current state

---

### ERROR Response

```json
{
  "status": "ERROR",
  "error_code": "<ERROR_CODE>",
  "message": "<human_readable_message>"
}
```

**Field Definitions:**

| Field | Type | Presence | Semantics |
|-------|------|----------|-----------|
| `status` | string | Always | Literal: `"ERROR"` |
| `error_code` | string | Always | Deterministic error identifier (see [Error Codes](#error-codes)) |
| `message` | string | Always | Human-readable explanation (typically stack trace info for debug) |

**When to use ERROR:**
- Payload malformed or missing required fields
- Protocol violation (e.g., unknown action, invalid data types)
- Unexpected exception in server processing (should be rare)

---

## Error Codes

### Error Code Taxonomy

Error codes follow pattern: `ERR_<CATEGORY>_<REASON>` or `INTERNAL_ERROR`

### Complete Error Code List

| Error Code | HTTP Equiv | When Triggered | Example Message |
|------------|-----------|-----------------|-----------------|
| **ERR_INVALID_PAYLOAD** | 400 | Payload missing required fields or unparseable JSON | `"Missing required field: section"` |
| **ERR_INVALID_SECTION** | 400 | `section` not in enum (VIP/PREFERENTIAL/GENERAL) | `"Section 'BALCONY' not supported"` |
| **ERR_INVALID_COORDINATES** | 400 | `row` or `col` < 0 or non-integer | `"Row must be non-negative integer; got: -5"` |
| **ERR_SEAT_OUT_OF_BOUNDS** | 400 | `row` or `col` exceeds section capacity | `"Seat (15, 20) out of bounds for VIP (10x20)"` |
| **ERR_SEAT_NOT_AVAILABLE** | 409 | Seat state != AVAILABLE (already reserved or sold) | `"Seat (5, 10) in VIP is SOLD"` |
| **ERR_NO_CAPACITY** | 409 | Section has no available semaphore slots | `"No reservation capacity in GENERAL section"` |
| **ERR_TRANSACTION_NOT_FOUND** | 404 | `transaction_id` not in reservation table | `"Transaction 'tx_99999' not found"` |
| **ERR_TRANSACTION_NOT_ACTIVE** | 409 | `transaction_id` exists but not in ACTIVE state | `"Transaction 'tx_12345' is CONFIRMED, not ACTIVE"` |
| **ERR_INVALID_ACTION** | 400 | `action` not in (RESERVE/CONFIRM/CANCEL/QUERY) | `"Unknown action: REFUND"` |
| **INTERNAL_ERROR** | 500 | Unexpected server exception (should be rare) | `"Exception: <actual exception message>"` |

### Error Code Determination Flow

```
1. Is payload valid JSON?
   NO → ERR_INVALID_PAYLOAD
   
2. Does action exist?
   NO → ERR_INVALID_ACTION
   
3. Is action RESERVE?
   YES → Check section/row/col:
      - section ∉ enum? → ERR_INVALID_SECTION
      - row/col not int? → ERR_INVALID_COORDINATES
      - row/col < 0? → ERR_INVALID_COORDINATES
      - row/col out of bounds? → ERR_SEAT_OUT_OF_BOUNDS
      - seat != AVAILABLE? → ERR_SEAT_NOT_AVAILABLE
      - no capacity in section? → ERR_NO_CAPACITY
      - Proceed → SUCCESS
      
4. Is action CONFIRM or CANCEL?
   YES → Check transaction_id:
      - Missing transaction_id? → ERR_INVALID_PAYLOAD
      - transaction_id not in table? → ERR_TRANSACTION_NOT_FOUND
      - transaction_id not ACTIVE? → ERR_TRANSACTION_NOT_ACTIVE
      - Proceed → SUCCESS
      
5. Is action QUERY?
   YES → Return seat counts → SUCCESS
   
6. Unexpected exception?
   Catch & return INTERNAL_ERROR
```

---

## Data Types

### Enums

#### Section (string)
```
"VIP" | "PREFERENTIAL" | "GENERAL"
```

#### SeatState (string)
```
"AVAILABLE" | "RESERVED" | "SOLD"
```

#### ReservationStatus (string)
```
"ACTIVE" | "CONFIRMED" | "CANCELLED" | "EXPIRED"
```

### Primitives

| Type | Format | Example |
|------|--------|---------|
| string | UTF-8 | `"VIP"`, `"tx_12345"` |
| integer | 32-bit signed | `5`, `10`, `300` |
| object | JSON object | `{"status": "SUCCESS", ...}` |
| array | JSON array | (used in QUERY response) |

---

## Examples

### Example 1: Reserve a seat (SUCCESS)

**Client Request:**
```json
{
  "action": "RESERVE",
  "section": "VIP",
  "row": 5,
  "col": 10
}
```

**Server Response:**
```json
{
  "status": "SUCCESS",
  "transaction_id": "tx_1681203600_001",
  "ttl": 300
}
```

---

### Example 2: Reserve with invalid section (ERROR)

**Client Request:**
```json
{
  "action": "RESERVE",
  "section": "BALCONY",
  "row": 5,
  "col": 10
}
```

**Server Response:**
```json
{
  "status": "ERROR",
  "error_code": "ERR_INVALID_SECTION",
  "message": "Section 'BALCONY' not supported. Valid sections: VIP, PREFERENTIAL, GENERAL"
}
```

---

### Example 3: Reserve already-sold seat (FAILURE)

**Client Request:**
```json
{
  "action": "RESERVE",
  "section": "VIP",
  "row": 5,
  "col": 10
}
```

**Server Response:**
```json
{
  "status": "FAILURE",
  "error_code": "ERR_SEAT_NOT_AVAILABLE",
  "message": "Seat VIP(5,10) is in SOLD state, not available for reservation"
}
```

---

### Example 4: Confirm reservation (SUCCESS)

**Client Request:**
```json
{
  "action": "CONFIRM",
  "transaction_id": "tx_1681203600_001"
}
```

**Server Response:**
```json
{
  "status": "SUCCESS",
  "transaction_id": "tx_1681203600_001"
}
```

---

### Example 5: Confirm non-existent transaction (FAILURE)

**Client Request:**
```json
{
  "action": "CONFIRM",
  "transaction_id": "tx_nonexistent"
}
```

**Server Response:**
```json
{
  "status": "FAILURE",
  "error_code": "ERR_TRANSACTION_NOT_FOUND",
  "message": "Transaction 'tx_nonexistent' not found in reservation table"
}
```

---

### Example 6: Query availability (SUCCESS)

**Client Request:**
```json
{
  "action": "QUERY"
}
```

**Server Response:**
```json
{
  "status": "SUCCESS",
  "sections": {
    "VIP": {
      "available": 150,
      "reserved": 35,
      "sold": 15
    },
    "PREFERENTIAL": {
      "available": 250,
      "reserved": 40,
      "sold": 10
    },
    "GENERAL": {
      "available": 380,
      "reserved": 15,
      "sold": 5
    }
  }
}
```

---

### Example 7: Reserve multiple seats (SUCCESS)

**Client Request:**
```json
{
  "action": "RESERVE_BATCH",
  "seats": [
    {"section": "VIP", "row": 0, "col": 0},
    {"section": "VIP", "row": 0, "col": 1},
    {"section": "PREFERENTIAL", "row": 5, "col": 10}
  ]
}
```

**Server Response:**
```json
{
  "status": "SUCCESS",
  "transaction_id": "tx_1681203600_002",
  "reserved_seats": [
    {"section": "VIP", "row": 0, "col": 0},
    {"section": "VIP", "row": 0, "col": 1},
    {"section": "PREFERENTIAL", "row": 5, "col": 10}
  ],
  "ttl": 300
}
```

---

### Example 8: Reserve batch with unavailable seat (FAILURE - No Partial Reserve)

**Client Request:**
```json
{
  "action": "RESERVE_BATCH",
  "seats": [
    {"section": "VIP", "row": 0, "col": 0},
    {"section": "VIP", "row": 0, "col": 2},
    {"section": "PREFERENTIAL", "row": 5, "col": 10}
  ]
}
```

**Server Response (assuming VIP(0,2) is already SOLD):**
```json
{
  "status": "FAILURE",
  "error_code": "ERR_SEAT_NOT_AVAILABLE",
  "message": "Seat VIP(0,2) is in SOLD state, not available for reservation. Batch reservation aborted (zero seats reserved)."
}
```

**Note:** Even if VIP(0,0) and PREFERENTIAL(5,10) were available, they are NOT reserved because another seat in the batch is unavailable. This is atomic behavior.

---

### Example 9: Reserve batch with duplicate coordinates (ERROR)

**Client Request:**
```json
{
  "action": "RESERVE_BATCH",
  "seats": [
    {"section": "VIP", "row": 0, "col": 0},
    {"section": "VIP", "row": 0, "col": 0}
  ]
}
```

**Server Response:**
```json
{
  "status": "ERROR",
  "error_code": "ERR_INVALID_PAYLOAD",
  "message": "Batch contains duplicate seat coordinates: VIP(0,0) appears multiple times"
}
```

---

## Validation Rules

### Server-Side Validation (Mandatory)

All requests MUST be validated server-side before processing:

1. **JSON Parse Validation:** Payload must be valid UTF-8 JSON
2. **Action Validation:** `action` field must exist and be one of (RESERVE, CONFIRM, CANCEL, QUERY)
3. **Field Presence:** Required fields for action must be present
4. **Type Validation:** Fields must be correct types (int for row/col, string for transaction_id)
5. **Range Validation:** row/col must be within section bounds
6. **State Validation:** Seat must be in expected state for operation
7. **Capacity Validation:** Section must have available semaphore slots (for RESERVE)
8. **Transaction Validation:** transaction_id must exist and be ACTIVE (for CONFIRM/CANCEL)

### Client-Side Validation (Best Practice)

Clients SHOULD validate before sending to avoid wasted round-trips:

1. **Action Enum:** Ensure action is valid before constructing request
2. **Section Enum:** Ensure section is VIP/PREFERENTIAL/GENERAL
3. **Coordinates:** Ensure row ≥ 0, col ≥ 0, and within expected section bounds
4. **Transaction ID Format:** Ensure transaction_id is present and non-empty (if CONFIRM/CANCEL)

### Response Validation (Client Responsibility)

Clients MUST validate responses before processing:

1. **Status Field:** Response must contain `"status"` key
2. **Status Value:** Status must be one of (SUCCESS, FAILURE, ERROR)
3. **Required Fields by Status:**
   - SUCCESS + RESERVE: Must have `transaction_id`, `ttl`
   - SUCCESS + CONFIRM/CANCEL: Must have `transaction_id`
   - SUCCESS + QUERY: Must have `sections` object with VIP/PREFERENTIAL/GENERAL keys
   - FAILURE/ERROR: Must have `error_code`, `message`
4. **Field Types:** Types must match schema (int for ttl/counts, string for transaction_id/error_code)

---

## Versioning & Changelog

### Version 1.0 (Current)

- **Date:** 2026-04-18
- **Status:** Formal Specification
- **Changes:**
  - Initial formal specification of protocol
  - Defined request/response schemas for RESERVE, CONFIRM, CANCEL, QUERY
  - Established error code taxonomy
  - Defined validation rules and flow
  - Examples for all major scenarios

### Future Versions

#### Version 2.0 (Planned - Breaking Changes)

If future changes require backwards-incompatibility:
1. Responses will include `"protocol_version": "2.0"` field
2. Clients SHOULD check for version and handle gracefully
3. v1.0 clients may reject v2.0 responses if they do not recognize the version

#### Backward Compatibility Strategy

- v1.0 clients connecting to v2.0 server: Server MAY return v2.0 responses; v1.0 clients will fail on unknown fields
- v2.0 clients connecting to v1.0 server: Client SHOULD accept responses without `protocol_version` field as v1.0

**Recommendation:** Include `protocol_version` in all responses starting v1.1 (non-breaking addition)

---

## References

- [src/utils/enums.py](../src/utils/enums.py) — Enum definitions
- [src/utils/config.py](../src/utils/config.py) — Configuration constants
- [src/server/transactional_thread.py](../src/server/transactional_thread.py) — Server implementation
- [src/client/concert_client.py](../src/client/concert_client.py) — Client implementation
