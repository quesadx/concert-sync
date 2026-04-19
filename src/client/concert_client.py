import socket
import json

from src.utils.protocol_validator import (
    validate_reserve_payload,
    validate_confirm_payload,
    validate_cancel_payload,
    validate_query_payload,
    validate_response,
    ErrorCode,
)


# ============================================================================
# CLIENT EXCEPTIONS
# ============================================================================

class ConcertClientError(Exception):
    """Base exception for concert client errors."""
    pass


class InvalidInputError(ConcertClientError):
    """Raised when client validation fails (bad input)."""
    pass


class ServerError(ConcertClientError):
    """Raised when server returns error response."""
    pass


class ServerFailureError(ConcertClientError):
    """Raised when server returns failure response (business logic rejection)."""
    pass


class SeatNotAvailableError(ServerFailureError):
    """Raised when seat is not available for reservation."""
    pass


class NoCapacityError(ServerFailureError):
    """Raised when section has no reservation capacity."""
    pass


class TransactionNotFoundError(ServerFailureError):
    """Raised when transaction_id not found."""
    pass


class TransactionNotActiveError(ServerFailureError):
    """Raised when transaction is not in ACTIVE state."""
    pass


# ============================================================================
# ERROR CODE TO EXCEPTION MAPPING
# ============================================================================

ERROR_CODE_TO_EXCEPTION = {
    ErrorCode.SEAT_NOT_AVAILABLE: SeatNotAvailableError,
    ErrorCode.NO_CAPACITY: NoCapacityError,
    ErrorCode.TRANSACTION_NOT_FOUND: TransactionNotFoundError,
    ErrorCode.TRANSACTION_NOT_ACTIVE: TransactionNotActiveError,
}


class ConcertClient:
    def __init__(self, host='localhost', port=9999):
        self.host = host
        self.port = port

    def send_request(self, request):
        """
        Send request and receive response from server.
        
        Args:
            request: Dict with action and parameters
            
        Returns:
            Parsed response dict
            
        Raises:
            ConcertClientError: If network or protocol error occurs
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((self.host, self.port))
                s.send(json.dumps(request).encode())
                response_data = s.recv(4096).decode()
                
                try:
                    response = json.loads(response_data)
                except json.JSONDecodeError as e:
                    raise ServerError(f"Invalid JSON response from server: {str(e)}")
                
                # Validate response structure
                is_valid, error_msg = validate_response(response)
                if not is_valid:
                    raise ServerError(f"Response validation failed: {error_msg}")
                
                # Check for error/failure and raise appropriate exception
                self._process_response(response)
                
                return response
        
        except socket.error as e:
            raise ConcertClientError(f"Network error: {str(e)}")
        except (json.JSONDecodeError, ValueError) as e:
            raise ConcertClientError(f"Protocol error: {str(e)}")

    def _process_response(self, response):
        """
        Process response and raise exceptions for error/failure statuses.
        
        Args:
            response: Parsed response dict
            
        Raises:
            ServerError: If status="ERROR"
            ServerFailureError: If status="FAILURE"
        """
        status = response.get("status")
        
        if status == "ERROR":
            error_code = response.get("error_code", "UNKNOWN")
            message = response.get("message", "Unknown error")
            raise ServerError(f"[{error_code}] {message}")
        
        elif status == "FAILURE":
            error_code = response.get("error_code", "UNKNOWN")
            message = response.get("message", "Unknown failure")
            
            # Map error_code to specific exception
            exc_class = ERROR_CODE_TO_EXCEPTION.get(error_code, ServerFailureError)
            raise exc_class(f"[{error_code}] {message}")

    def reserve_seat(self, section, row, col):
        """
        Reserve a specific seat.
        
        Args:
            section: Section name (VIP, PREFERENTIAL, GENERAL)
            row: Row index (0-based)
            col: Column index (0-based)
            
        Returns:
            Response dict with transaction_id and ttl
            
        Raises:
            InvalidInputError: If inputs are invalid
            SeatNotAvailableError: If seat not available
            NoCapacityError: If section has no capacity
            ServerError: If server error occurs
        """
        # Validate inputs locally
        request = {
            "action": "RESERVE",
            "section": section,
            "row": row,
            "col": col
        }
        
        is_valid, error_msg = validate_reserve_payload(request)
        if not is_valid:
            raise InvalidInputError(f"Invalid reserve input: {error_msg}")
        
        response = self.send_request(request)
        return response

    def confirm(self, transaction_id):
        """
        Confirm a reservation (convert to SOLD state).
        
        Args:
            transaction_id: Transaction ID from reserve_seat()
            
        Returns:
            Response dict with transaction_id
            
        Raises:
            InvalidInputError: If transaction_id is invalid
            TransactionNotFoundError: If transaction not found
            TransactionNotActiveError: If transaction not in ACTIVE state
            ServerError: If server error occurs
        """
        # Validate input locally
        request = {
            "action": "CONFIRM",
            "transaction_id": transaction_id,
        }
        
        is_valid, error_msg = validate_confirm_payload(request)
        if not is_valid:
            raise InvalidInputError(f"Invalid confirm input: {error_msg}")
        
        response = self.send_request(request)
        return response

    def cancel(self, transaction_id):
        """
        Cancel a reservation (revert to AVAILABLE state).
        
        Args:
            transaction_id: Transaction ID from reserve_seat()
            
        Returns:
            Response dict with transaction_id
            
        Raises:
            InvalidInputError: If transaction_id is invalid
            TransactionNotFoundError: If transaction not found
            TransactionNotActiveError: If transaction not in ACTIVE state
            ServerError: If server error occurs
        """
        # Validate input locally
        request = {
            "action": "CANCEL",
            "transaction_id": transaction_id,
        }
        
        is_valid, error_msg = validate_cancel_payload(request)
        if not is_valid:
            raise InvalidInputError(f"Invalid cancel input: {error_msg}")
        
        response = self.send_request(request)
        return response

    def query(self):
        """
        Query current seat availability by section.
        
        Returns:
            Response dict with sections and counts
            
        Raises:
            ServerError: If server error occurs
        """
        request = {
            "action": "QUERY",
        }
        
        response = self.send_request(request)
        return response
