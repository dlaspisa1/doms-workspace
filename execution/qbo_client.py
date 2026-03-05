#!/usr/bin/env python3
"""
QuickBooks Online API Client
Base client for making authenticated API requests with error handling and logging
"""

import os
import json
from dotenv import load_dotenv
from intuitlib.client import AuthClient
from quickbooks import QuickBooks
from qbo_auth import load_tokens, refresh_tokens, get_valid_tokens
from qbo_error_handler import (
    handle_exception, log_error, extract_intuit_tid,
    QBOError, QBOAuthError, QBOValidationError, get_support_info
)

load_dotenv()

CLIENT_ID = os.getenv('QBO_CLIENT_ID')
CLIENT_SECRET = os.getenv('QBO_CLIENT_SECRET')
REDIRECT_URI = os.getenv('QBO_REDIRECT_URI', 'http://localhost:8080/callback')
ENVIRONMENT = os.getenv('QBO_ENVIRONMENT', 'sandbox')
REALM_ID = os.getenv('QBO_REALM_ID')


class QBOClient:
    """QuickBooks Online API client wrapper"""

    def __init__(self, realm_id=None):
        """Initialize client with authentication and error handling"""
        self.realm_id = realm_id or REALM_ID
        self.last_intuit_tid = None  # Track last transaction ID

        if not self.realm_id:
            raise ValueError("QBO_REALM_ID must be set in .env or passed to constructor")

        if not CLIENT_ID or not CLIENT_SECRET:
            raise ValueError("QBO_CLIENT_ID and QBO_CLIENT_SECRET must be set in .env")

        # Get valid tokens with error handling
        try:
            tokens = get_valid_tokens()
            if not tokens:
                raise QBOAuthError(
                    "No valid tokens found. Please authenticate first.",
                    error_code="NO_TOKENS",
                    details={'help': 'Run: python execution/qbo_auth.py'}
                )
        except Exception as e:
            if not isinstance(e, QBOAuthError):
                raise QBOAuthError(f"Authentication error: {str(e)}")
            raise

        # Create auth client
        self.auth_client = AuthClient(
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            redirect_uri=REDIRECT_URI,
            environment=ENVIRONMENT,
            access_token=tokens['access_token'],
            refresh_token=tokens['refresh_token'],
        )

        # Create QuickBooks client
        self.client = QuickBooks(
            auth_client=self.auth_client,
            refresh_token=tokens['refresh_token'],
            company_id=self.realm_id,
        )

        self.is_sandbox = (ENVIRONMENT == 'sandbox')

    @handle_exception
    def query(self, query_string):
        """
        Execute a QuickBooks SQL-like query with error handling

        Args:
            query_string: SQL-like query string

        Returns:
            Query results

        Raises:
            QBOError subclasses on API errors
        """
        try:
            result = self.client.query(query_string)
            # Note: intuit_tid would be in the HTTP response, which is abstracted by the library
            return result
        except Exception as e:
            # Wrap and re-raise with context
            error_msg = f"Query failed: {str(e)}"
            log_error(e, {'query': query_string, 'realm_id': self.realm_id})
            raise QBOError(error_msg, details={'query': query_string})

    @handle_exception
    def get_report(self, report_type, start_date=None, end_date=None, **kwargs):
        """
        Get a financial report with error handling

        Args:
            report_type: 'ProfitAndLoss', 'BalanceSheet', 'CashFlow', etc.
            start_date: Report start date (YYYY-MM-DD)
            end_date: Report end date (YYYY-MM-DD)
            **kwargs: Additional report parameters

        Returns:
            Report object

        Raises:
            QBOError subclasses on API errors
        """
        from quickbooks.objects.reports import Report

        params = {}
        if start_date:
            params['start_date'] = start_date
        if end_date:
            params['end_date'] = end_date

        params.update(kwargs)

        try:
            report = Report()
            report.query(self.client, report_type, params)
            return report
        except Exception as e:
            error_msg = f"Report query failed: {str(e)}"
            log_error(e, {'report_type': report_type, 'params': params})
            raise QBOError(error_msg, details={'report_type': report_type, 'params': params})

    def get_all(self, entity_class, max_results=1000):
        """
        Get all records of a specific entity type

        Args:
            entity_class: QuickBooks entity class (Customer, Invoice, Vendor, etc.)
            max_results: Maximum number of results to return

        Returns:
            List of entity objects
        """
        return entity_class.all(qb=self.client, max_results=max_results)

    def get_by_id(self, entity_class, entity_id):
        """Get a specific entity by ID"""
        return entity_class.get(entity_id, qb=self.client)

    def create(self, entity):
        """Create a new entity"""
        entity.save(qb=self.client)
        return entity

    def update(self, entity):
        """Update an existing entity"""
        entity.save(qb=self.client)
        return entity

    def delete(self, entity):
        """Delete an entity (soft delete in QuickBooks)"""
        entity.delete(qb=self.client)
        return entity


def get_client(realm_id=None):
    """
    Get authenticated QuickBooks client

    Args:
        realm_id: Optional realm ID (defaults to QBO_REALM_ID from .env)

    Returns:
        QBOClient instance
    """
    return QBOClient(realm_id=realm_id)


if __name__ == '__main__':
    # Test the client with error handling
    try:
        client = get_client()
        print(f"✓ Connected to QuickBooks Online")
        print(f"✓ Company ID: {client.realm_id}")
        print(f"✓ Environment: {ENVIRONMENT}")
        print(f"✓ Error handling: Enabled")
        print(f"✓ Error logging: {os.path.join('.tmp/logs', 'qbo_errors.log')}")

        support = get_support_info()
        print(f"\nSupport Contact: {support['support_email']}")
        print(f"\nClient ready for use!")
    except QBOError as e:
        print(f"✗ QuickBooks Error: {e.message}")
        if e.intuit_tid:
            print(f"  Transaction ID: {e.intuit_tid}")
    except Exception as e:
        print(f"✗ Error: {e}")
