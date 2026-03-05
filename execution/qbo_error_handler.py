#!/usr/bin/env python3
"""
QuickBooks Online Error Handling and Logging
Captures API errors, intuit_tid, and maintains error logs
"""

import os
import json
import logging
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Configuration
LOG_DIR = '.tmp/logs'
ERROR_LOG_FILE = os.path.join(LOG_DIR, 'qbo_errors.log')
SUPPORT_EMAIL = os.getenv('SUPPORT_EMAIL', 'support@example.com')

# Ensure log directory exists
os.makedirs(LOG_DIR, exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(ERROR_LOG_FILE),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('qbo_api')


class QBOError(Exception):
    """Base exception for QuickBooks API errors"""
    def __init__(self, message, error_code=None, intuit_tid=None, details=None):
        self.message = message
        self.error_code = error_code
        self.intuit_tid = intuit_tid
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self):
        return {
            'error': self.message,
            'error_code': self.error_code,
            'intuit_tid': self.intuit_tid,
            'details': self.details,
            'timestamp': datetime.now().isoformat()
        }


class QBOAuthError(QBOError):
    """Authentication/Authorization errors"""
    pass


class QBOValidationError(QBOError):
    """Validation errors from API"""
    pass


class QBOSyntaxError(QBOError):
    """Syntax errors in API requests"""
    pass


class QBORateLimitError(QBOError):
    """Rate limit exceeded errors"""
    pass


def extract_intuit_tid(response):
    """
    Extract intuit_tid from response headers

    Args:
        response: HTTP response object

    Returns:
        intuit_tid string or None
    """
    if hasattr(response, 'headers'):
        return response.headers.get('intuit_tid') or response.headers.get('Intuit_TID')
    return None


def log_error(error, context=None):
    """
    Log error with full context

    Args:
        error: Exception or error object
        context: Additional context dictionary
    """
    error_data = {
        'timestamp': datetime.now().isoformat(),
        'error_type': type(error).__name__,
        'error_message': str(error),
        'context': context or {}
    }

    # Add intuit_tid if available
    if isinstance(error, QBOError) and error.intuit_tid:
        error_data['intuit_tid'] = error.intuit_tid
        error_data['error_code'] = error.error_code
        error_data['details'] = error.details

    logger.error(json.dumps(error_data, indent=2))

    return error_data


def handle_api_response(response, operation=None):
    """
    Handle API response and check for errors

    Args:
        response: HTTP response object
        operation: String describing the operation

    Returns:
        Response data or raises appropriate exception

    Raises:
        QBOError subclasses based on error type
    """
    intuit_tid = extract_intuit_tid(response)

    # Log the intuit_tid for successful requests too
    if intuit_tid:
        logger.info(f"Request intuit_tid: {intuit_tid} - Operation: {operation or 'unknown'}")

    # Check for HTTP errors
    if hasattr(response, 'status_code'):
        if response.status_code >= 400:
            error_message = f"API Error {response.status_code}"
            error_details = {}

            # Try to parse error response
            try:
                error_data = response.json()
                if 'Fault' in error_data:
                    fault = error_data['Fault']
                    error_message = fault.get('Error', [{}])[0].get('Message', error_message)
                    error_code = fault.get('Error', [{}])[0].get('code')
                    error_details = fault.get('Error', [{}])[0].get('Detail', {})

                    # Determine error type
                    if response.status_code == 401:
                        raise QBOAuthError(error_message, error_code, intuit_tid, error_details)
                    elif response.status_code == 400:
                        if 'validation' in error_message.lower():
                            raise QBOValidationError(error_message, error_code, intuit_tid, error_details)
                        else:
                            raise QBOSyntaxError(error_message, error_code, intuit_tid, error_details)
                    elif response.status_code == 429:
                        raise QBORateLimitError(error_message, error_code, intuit_tid, error_details)
                    else:
                        raise QBOError(error_message, error_code, intuit_tid, error_details)
            except (ValueError, KeyError):
                # Couldn't parse error response
                raise QBOError(error_message, None, intuit_tid, {'status_code': response.status_code})

    return response


def get_support_info():
    """
    Get support contact information

    Returns:
        Dictionary with support contact details
    """
    return {
        'support_email': SUPPORT_EMAIL,
        'error_log_location': ERROR_LOG_FILE,
        'message': f'For support, please contact {SUPPORT_EMAIL} and include the error log from {ERROR_LOG_FILE}'
    }


def handle_exception(func):
    """
    Decorator to handle exceptions in QBO functions

    Usage:
        @handle_exception
        def my_function():
            # code here
    """
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except QBOError as e:
            log_error(e, {
                'function': func.__name__,
                'args': str(args)[:100],  # Truncate for safety
                'kwargs': str(kwargs)[:100]
            })
            print(f"\n✗ QuickBooks API Error: {e.message}")
            if e.intuit_tid:
                print(f"  Transaction ID (intuit_tid): {e.intuit_tid}")
            if e.error_code:
                print(f"  Error Code: {e.error_code}")
            print(f"\n{get_support_info()['message']}\n")
            raise
        except Exception as e:
            log_error(e, {
                'function': func.__name__,
                'args': str(args)[:100],
                'kwargs': str(kwargs)[:100]
            })
            print(f"\n✗ Unexpected Error: {str(e)}")
            print(f"{get_support_info()['message']}\n")
            raise

    return wrapper


if __name__ == '__main__':
    # Test the error handler
    print("QuickBooks Error Handler Test\n")
    print(f"Error logs will be written to: {ERROR_LOG_FILE}")
    print(f"Support contact: {SUPPORT_EMAIL}\n")

    # Test logging
    test_error = QBOError("Test error", "TEST_001", "test-tid-12345", {"test": "data"})
    log_error(test_error, {"context": "test"})

    print(f"\n✓ Test error logged to {ERROR_LOG_FILE}")
    print(f"\nSupport Info:")
    print(json.dumps(get_support_info(), indent=2))
