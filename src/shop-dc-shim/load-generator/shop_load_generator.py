#!/usr/bin/env python3
# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""
Shop Datacenter Load Generator
YeetCoded (locust may have been simpler but hey...)

This generates realistic on-premises shop purchase traffic to simulate:
- Physical store transactions 
- Terminal-based purchases
- Local inventory integration
- Enterprise retail patterns

The generator creates realistic purchase patterns that would originate
from datacenter-deployed point-of-sale systems calling cloud checkout.

ERROR HANDLING & BACKOFF LOGIC:
- Purchase requests are NEVER affected by error handling
- Transaction status polling implements circuit breaker pattern
- 500 errors on status checks trigger exponential backoff (1.5x multiplier)
- After 10 consecutive status check failures, circuit breaker opens for 10 minutes
- Purchase flow continues normally even when status checks are failing
- This prevents overwhelming the service with failed status check requests
- Designed to keep demo errors visible while preventing system overload
"""

import json
import random
import time
import uuid
import logging
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from typing import List, Dict, Any
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class StoreLocation:
    store_code: str
    store_name: str
    city: str
    state: str
    terminals: List[str]

@dataclass
class Product:
    product_id: str
    name: str
    price: float
    category: str

@dataclass
class Customer:
    name: str
    email: str
    phone: str

class ShopLoadGenerator:
    """Generate realistic on-premises shop transaction load"""
    
    def __init__(self, shop_service_url: str = "http://localhost:8070"):
        self.shop_service_url = shop_service_url
        self.session = self._create_session()
        
        # Status check error tracking and backoff logic
        self.status_check_failures = 0
        self.consecutive_failures = 0
        self.last_failure_time = 0
        self.status_check_enabled = True
        self.backoff_delay = 1  # Initial backoff delay in seconds
        self.max_backoff_delay = 300  # Maximum backoff delay (5 minutes)
        self.circuit_breaker_threshold = 10  # Number of consecutive failures before backing off more
        self.circuit_breaker_reset_time = 600  # Time to wait before resetting circuit breaker (10 minutes)
        
        # Store locations (simulating datacenter-deployed stores)
        self.stores = [
            StoreLocation("DC-NYC-01", "Manhattan Flagship", "New York", "NY", 
                         ["TERM-001", "TERM-002", "TERM-003", "TERM-004"]),
            StoreLocation("DC-NYC-02", "Brooklyn Heights", "Brooklyn", "NY", 
                         ["TERM-001", "TERM-002", "TERM-003"]),
            StoreLocation("DC-BOS-01", "Boston Downtown", "Boston", "MA", 
                         ["TERM-001", "TERM-002"]),
            StoreLocation("DC-PHI-01", "Philadelphia Center", "Philadelphia", "PA", 
                         ["TERM-001", "TERM-002", "TERM-003"]),
            StoreLocation("DC-DC-01", "Washington Capitol", "Washington", "DC", 
                         ["TERM-001", "TERM-002"])
        ]
        
        # Product catalog (simulating local inventory)
        self.products = [
            Product("SKU-TELE-001", "Professional Telescope", 299.99, "telescopes"),
            Product("SKU-BINO-001", "High-Power Binoculars", 149.99, "binoculars"),
            Product("SKU-LENS-001", "Camera Lens Set", 199.99, "accessories"),
            Product("SKU-TRIPOD-001", "Carbon Fiber Tripod", 89.99, "accessories"),
            Product("SKU-BOOK-001", "Astronomy Guide Book", 24.99, "books"),
            Product("SKU-COMPASS-001", "Digital Compass", 39.99, "navigation"),
            Product("SKU-FILTER-001", "Light Pollution Filter", 79.99, "accessories"),
            Product("SKU-MOUNT-001", "Telescope Mount", 159.99, "accessories")
        ]
        
        # Customer database (simulating local customer records)
        self.customers = self._generate_customers(500)
        
    def _create_session(self) -> requests.Session:
        """Create HTTP session with retry logic"""
        session = requests.Session()
        
        retry_strategy = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
    
    def _generate_customers(self, count: int) -> List[Customer]:
        """Generate a pool of realistic customers"""
        first_names = ["James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael", "Linda", 
                      "David", "Elizabeth", "William", "Barbara", "Richard", "Susan", "Joseph", "Jessica"]
        last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
                     "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas"]
        
        customers = []
        for i in range(count):
            first = random.choice(first_names)
            last = random.choice(last_names)
            email_domain = random.choice(["gmail.com", "yahoo.com", "outlook.com", "company.com", "enterprise.net"])
            
            customers.append(Customer(
                name=f"{first} {last}",
                email=f"{first.lower()}.{last.lower()}@{email_domain}",
                phone=f"{random.randint(200,999)}-{random.randint(200,999)}-{random.randint(1000,9999)}"
            ))
        
        return customers
    
    def create_purchase_request(self, store: StoreLocation, terminal: str) -> Dict[str, Any]:
        """Create a realistic purchase request"""
        customer = random.choice(self.customers)
        
        # Realistic purchase patterns
        num_items = random.choices([1, 2, 3, 4, 5], weights=[40, 30, 20, 7, 3])[0]
        items = random.sample(self.products, min(num_items, len(self.products)))
        
        total_amount = sum(item.price * random.randint(1, 2) for item in items)
        
        # Add realistic address
        street_numbers = ["123", "456", "789", "321", "654", "987"]
        street_names = ["Main St", "Oak Ave", "Pine Rd", "Elm Dr", "First St", "Second Ave", "Park Blvd"]
        
        purchase_items = []
        for item in items:
            quantity = random.randint(1, 2)
            purchase_items.append({
                "productId": item.product_id,
                "quantity": quantity,
                "unitPrice": item.price,
                "productName": item.name
            })
        
        return {
            "customerName": customer.name,
            "customerEmail": customer.email,
            "totalAmount": round(total_amount, 2),
            "currencyCode": "USD",
            "storeLocation": store.store_code,
            "terminalId": terminal,
            "shippingAddress": {
                "streetAddress": f"{random.choice(street_numbers)} {random.choice(street_names)}",
                "city": store.city,
                "state": store.state,
                "country": "USA",
                "zipCode": f"{random.randint(10000, 99999)}"
            },
            "creditCard": {
                "creditCardNumber": "4111-1111-1111-1111",  # Test card number
                "creditCardCvv": random.randint(100, 999),
                "expirationMonth": random.randint(1, 12),
                "expirationYear": random.randint(2025, 2030)
            },
            "items": purchase_items
        }
    
    def submit_purchase(self, purchase_request: Dict[str, Any]) -> Dict[str, Any]:
        """Submit a purchase to the shop service"""
        try:
            start_time = time.time()
            
            response = self.session.post(
                f"{self.shop_service_url}/api/shop/purchase",
                json=purchase_request,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            response_time = time.time() - start_time
            
            if response.status_code == 202:
                result = response.json()
                logger.info(f"Purchase submitted successfully - Transaction: {result.get('transactionId')} "
                          f"Store: {purchase_request['storeLocation']} Terminal: {purchase_request['terminalId']} "
                          f"Amount: ${purchase_request['totalAmount']} Response time: {response_time:.2f}s")
                return {"success": True, "data": result, "response_time": response_time}
            else:
                logger.error(f"Purchase failed - Store: {purchase_request['storeLocation']} "
                           f"Status: {response.status_code} Response: {response.text}")
                return {"success": False, "error": f"HTTP {response.status_code}: {response.text}"}
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error for store {purchase_request['storeLocation']}: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def check_transaction_status(self, transaction_id: str) -> Dict[str, Any]:
        """Check the status of a transaction with backoff logic for 500 errors"""
        # Check if circuit breaker is open and should be reset
        current_time = time.time()
        if not self.status_check_enabled and (current_time - self.last_failure_time) > self.circuit_breaker_reset_time:
            logger.info("Resetting status check circuit breaker - attempting to resume normal operation")
            self.status_check_enabled = True
            self.consecutive_failures = 0
            self.backoff_delay = 1
        
        # If circuit breaker is open, return immediately without making request
        if not self.status_check_enabled:
            time_until_reset = self.circuit_breaker_reset_time - (current_time - self.last_failure_time)
            return {
                "success": False, 
                "error": f"Circuit breaker open - status checks disabled for {time_until_reset:.0f} more seconds",
                "circuit_breaker_open": True
            }
        
        # Apply current backoff delay before making request
        if self.backoff_delay > 1:
            logger.debug(f"Applying backoff delay of {self.backoff_delay:.1f}s before status check")
            time.sleep(self.backoff_delay)
        
        try:
            response = self.session.get(
                f"{self.shop_service_url}/api/shop/transaction/{transaction_id}",
                timeout=10
            )
            
            if response.status_code == 200:
                # Success - reset failure counters
                self.consecutive_failures = 0
                self.backoff_delay = 1
                return {"success": True, "data": response.json()}
            elif response.status_code == 500:
                # Handle 500 errors with backoff logic (but still allow them for demo)
                self._handle_status_check_failure("500 Internal Server Error - Jackson serialization issue (demo)")
                return {"success": False, "error": f"HTTP {response.status_code} (demo error)", "server_error": True}
            elif response.status_code == 404:
                # 404 is expected for new transactions, don't count as failure
                return {"success": False, "error": f"HTTP {response.status_code} - Transaction not found"}
            else:
                # Other error codes
                self._handle_status_check_failure(f"HTTP {response.status_code}")
                return {"success": False, "error": f"HTTP {response.status_code}"}
                
        except requests.exceptions.RequestException as e:
            self._handle_status_check_failure(f"Request exception: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def _handle_status_check_failure(self, error_msg: str):
        """Handle status check failures with exponential backoff and circuit breaker logic"""
        self.status_check_failures += 1
        self.consecutive_failures += 1
        self.last_failure_time = time.time()
        
        # Implement exponential backoff
        self.backoff_delay = min(self.backoff_delay * 1.5, self.max_backoff_delay)
        
        if self.consecutive_failures >= self.circuit_breaker_threshold:
            self.status_check_enabled = False
            logger.warning(f"Status check circuit breaker opened after {self.consecutive_failures} consecutive failures. "
                         f"Last error: {error_msg}. Status checks disabled for {self.circuit_breaker_reset_time} seconds.")
        else:
            logger.debug(f"Status check failure #{self.consecutive_failures}: {error_msg}. "
                        f"Next request will have {self.backoff_delay:.1f}s backoff delay.")
    
    def run_single_transaction(self) -> Dict[str, Any]:
        """Execute a single transaction (for use with thread pool)
        
        NOTE: Purchase requests are NEVER affected by status check backoff logic.
        Only transaction status polling is subject to circuit breaker protection.
        This ensures purchases continue to flow even when status checks are failing.
        """
        store = random.choice(self.stores)
        terminal = random.choice(store.terminals)
        
        purchase_request = self.create_purchase_request(store, terminal)
        result = self.submit_purchase(purchase_request)
        
        # Add store and terminal info to result
        result["store_location"] = store.store_code
        result["terminal_id"] = terminal
        
        return result
    
    def run_continuous_load(self, transactions_per_minute: int = 10, duration_minutes: int = 6000):
        """Run continuous load generation"""
        run_forever = duration_minutes == 0
        
        if run_forever:
            logger.info(f"Starting continuous load generation: {transactions_per_minute} TPM (running indefinitely)")
        else:
            logger.info(f"Starting continuous load generation: {transactions_per_minute} TPM for {duration_minutes} minutes")
        
        # Validate input parameters
        if duration_minutes < 0:
            logger.error(f"Invalid duration: {duration_minutes} minutes. Duration must be greater than or equal to 0.")
            return
        
        if transactions_per_minute <= 0:
            logger.error(f"Invalid transaction rate: {transactions_per_minute} TPM. Rate must be greater than 0.")
            return
        
        start_time = time.time()
        end_time = start_time + (duration_minutes * 60) if not run_forever else float('inf')
        interval = 60.0 / transactions_per_minute
        
        transaction_count = 0
        success_count = 0
        pending_transactions = []
        
        try:
            while time.time() < end_time:
                loop_start = time.time()
                
                # Submit transaction
                result = self.run_single_transaction()
                transaction_count += 1
                
                if result["success"]:
                    success_count += 1
                    # Track transaction for later status checking
                    if "data" in result and "transactionId" in result["data"]:
                        pending_transactions.append({
                            "transaction_id": result["data"]["transactionId"],
                            "submitted_at": datetime.now(),
                            "store": result["store_location"]
                        })
                
                # Periodically check status of pending transactions (every 50 transactions)
                if transaction_count % 50 == 0 and pending_transactions:
                    self._check_pending_transactions(pending_transactions)
                
                # Print progress every minute
                if transaction_count % transactions_per_minute == 0:
                    elapsed_minutes = (time.time() - start_time) / 60
                    success_rate = (success_count / transaction_count) * 100 if transaction_count > 0 else 0
                    stats = self.get_status_check_stats()
                    
                    status_info = ""
                    if not stats["circuit_breaker_enabled"]:
                        status_info = f" | Status checks: CIRCUIT BREAKER OPEN ({stats['consecutive_failures']} failures)"
                    elif stats["total_failures"] > 0:
                        status_info = f" | Status checks: {stats['total_failures']} total failures, {stats['backoff_delay']:.1f}s backoff"
                    
                    if run_forever:
                        logger.info(f"Progress: {transaction_count} transactions in {elapsed_minutes:.1f} minutes "
                                f"(Success rate: {success_rate:.1f}%) - Running indefinitely{status_info}")
                    else:
                        logger.info(f"Progress: {transaction_count} transactions in {elapsed_minutes:.1f} minutes "
                                f"(Success rate: {success_rate:.1f}%){status_info}")
                
                # Sleep to maintain target rate
                elapsed = time.time() - loop_start
                sleep_time = max(0, interval - elapsed)
                if sleep_time > 0:
                    time.sleep(sleep_time)
                    
        except KeyboardInterrupt:
            if run_forever:
                logger.info("Continuous load generation interrupted by user (Ctrl+C)")
            else:
                logger.info("Load generation interrupted by user (Ctrl+C)")
        
        # Final status check
        if pending_transactions:
            logger.info("Checking final status of pending transactions...")
            self._check_pending_transactions(pending_transactions)
        
        total_time = time.time() - start_time
        
        # Handle case where no transactions were executed
        if transaction_count == 0:
            logger.warning("No transactions were executed. Check duration and rate parameters.")
            return
        
        final_success_rate = (success_count / transaction_count) * 100
        stats = self.get_status_check_stats()
        
        logger.info(f"Load generation completed:")
        logger.info(f"  Total transactions: {transaction_count}")
        logger.info(f"  Successful submissions: {success_count}")
        logger.info(f"  Success rate: {final_success_rate:.1f}%")
        logger.info(f"  Total time: {total_time:.1f} seconds")
        logger.info(f"  Average TPM: {(transaction_count / (total_time / 60)):.1f}")
        logger.info(f"Status check circuit breaker stats:")
        logger.info(f"  Total status check failures: {stats['total_failures']}")
        logger.info(f"  Circuit breaker status: {'OPEN' if not stats['circuit_breaker_enabled'] else 'CLOSED'}")
        logger.info(f"  Final backoff delay: {stats['backoff_delay']:.1f}s")
        
        if stats["total_failures"] > 0:
            logger.info("NOTE: Status check failures are expected for this demo (Jackson LocalDateTime serialization errors)")
            logger.info("Purchase requests were never affected by status check failures - they continued successfully!")
    
    def _check_pending_transactions(self, pending_transactions: List[Dict[str, Any]]):
        """Check status of pending transactions with backoff logic"""
        completed_indices = []
        status_check_skipped = 0
        
        for i, txn in enumerate(pending_transactions):
            # Only check transactions that are at least 30 seconds old
            if (datetime.now() - txn["submitted_at"]).total_seconds() < 30:
                continue
                
            status_result = self.check_transaction_status(txn["transaction_id"])
            
            # Handle circuit breaker case
            if status_result.get("circuit_breaker_open"):
                status_check_skipped += 1
                continue
            
            if status_result["success"]:
                data = status_result["data"]
                status = data.get("status")
                store = data.get("storeLocation")
                
                if status in ["COMPLETED", "FAILED"]:
                    logger.info(f"Transaction {txn['transaction_id'][:8]}... from {store} -> {status}")
                    completed_indices.append(i)
            elif status_result.get("server_error"):
                # 500 errors are expected for demo - log but continue tracking
                logger.debug(f"Transaction {txn['transaction_id'][:8]}... status check failed with expected demo error: {status_result['error']}")
            else:
                # Other errors (404, network issues, etc.)
                logger.debug(f"Transaction {txn['transaction_id'][:8]}... status check failed: {status_result['error']}")
        
        # Remove completed transactions from tracking
        for i in reversed(completed_indices):
            pending_transactions.pop(i)
        
        # Log circuit breaker status if any checks were skipped
        if status_check_skipped > 0:
            logger.info(f"Skipped {status_check_skipped} status checks due to circuit breaker protection")
            logger.info(f"Status check circuit breaker stats: {self.consecutive_failures} consecutive failures, "
                       f"next backoff delay: {self.backoff_delay:.1f}s")
    
    def get_status_check_stats(self) -> Dict[str, Any]:
        """Get current status check statistics for monitoring"""
        return {
            "total_failures": self.status_check_failures,
            "consecutive_failures": self.consecutive_failures,
            "backoff_delay": self.backoff_delay,
            "circuit_breaker_enabled": self.status_check_enabled,
            "last_failure_time": self.last_failure_time,
            "time_since_last_failure": time.time() - self.last_failure_time if self.last_failure_time > 0 else 0
        }
    
    def run_burst_load(self, concurrent_transactions: int = 20, total_transactions: int = 100):
        """Run burst load with concurrent transactions"""
        logger.info(f"Starting burst load: {total_transactions} transactions with {concurrent_transactions} concurrent")
        
        start_time = time.time()
        success_count = 0
        
        with ThreadPoolExecutor(max_workers=concurrent_transactions) as executor:
            # Submit all transactions
            future_to_txn = {
                executor.submit(self.run_single_transaction): i 
                for i in range(total_transactions)
            }
            
            # Process results as they complete
            for future in as_completed(future_to_txn):
                try:
                    result = future.result()
                    if result["success"]:
                        success_count += 1
                except Exception as e:
                    logger.error(f"Transaction failed with exception: {str(e)}")
        
        total_time = time.time() - start_time
        success_rate = (success_count / total_transactions) * 100
        
        logger.info(f"Burst load completed:")
        logger.info(f"  Total transactions: {total_transactions}")
        logger.info(f"  Successful: {success_count}")
        logger.info(f"  Success rate: {success_rate:.1f}%")
        logger.info(f"  Total time: {total_time:.1f} seconds")
        logger.info(f"  TPS: {(total_transactions / total_time):.1f}")


def main():
    """Main function to run the load generator"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Shop Datacenter Load Generator")
    parser.add_argument("--url", default="http://localhost:8070", 
                       help="Shop service URL (default: http://localhost:8070)")
    parser.add_argument("--mode", choices=["continuous", "burst", "single"], default="continuous",
                       help="Load generation mode (default: continuous)")
    parser.add_argument("--tpm", type=int, default=10, 
                       help="Transactions per minute for continuous mode (default: 10)")
    parser.add_argument("--duration", type=int, default=6000, 
                       help="Duration in minutes for continuous mode (default: 6000)")
    parser.add_argument("--concurrent", type=int, default=20, 
                       help="Concurrent transactions for burst mode (default: 20)")
    parser.add_argument("--total", type=int, default=100, 
                       help="Total transactions for burst mode (default: 100)")
    
    args = parser.parse_args()
    
    generator = ShopLoadGenerator(args.url)
    
    # Check service health before starting
    try:
        health_response = generator.session.get(f"{args.url}/api/shop/health", timeout=10)
        if health_response.status_code == 200:
            health_data = health_response.json()
            logger.info(f"Service health check passed: {health_data.get('service')} in {health_data.get('environment')}")
        else:
            logger.warning(f"Service health check returned {health_response.status_code}")
    except Exception as e:
        logger.error(f"Service health check failed: {str(e)}")
        return
    
    if args.mode == "continuous":
        generator.run_continuous_load(args.tpm, args.duration)
    elif args.mode == "burst":
        generator.run_burst_load(args.concurrent, args.total)
    elif args.mode == "single":
        result = generator.run_single_transaction()
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
