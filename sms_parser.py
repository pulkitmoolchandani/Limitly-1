#!/usr/bin/env python3
"""
SMS Financial Transaction Parser
Parses SMS data from CSV files using Google Gemini API and stores results in structured format
"""

import os
import json
import csv
import pandas as pd
import sqlite3
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import matplotlib.pyplot as plt
import seaborn as sns
from collections import Counter
import google.generativeai as genai
from dataclasses import dataclass
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class Transaction:
    """Data class for financial transactions"""
    amount: float
    merchant: str
    date: str
    category: str
    ref_id: str  # Unique reference ID
    transaction_type: str  # 'debit' or 'credit'
    card_type: Optional[str] = None
    bank: Optional[str] = None
    payment_method: Optional[str] = None
    original_sms: str = ""
    is_valid: bool = True

class GeminiSMSParser:
    """SMS Parser using Google Gemini API"""
    
    def __init__(self, api_key: str):
        """Initialize the parser with Gemini API key"""
        self.api_key = api_key
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        
    def parse_sms(self, sms_text: str) -> Optional[Transaction]:
        """Parse a single SMS using Gemini API"""
        try:
            prompt = self._create_parsing_prompt(sms_text)
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()
            
            # Check if response is "null" (not a transaction)
            if response_text.lower() == 'null':
                logger.debug(f'Gemini determined this is not a valid transaction: {sms_text[:50]}...')
                return None
            
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if not json_match:
                logger.warning(f'No JSON found in Gemini response: {response_text}')
                return None
            
            json_str = json_match.group(0)
            parsed_data = json.loads(json_str)
            
            # Create transaction object
            transaction = Transaction(
                amount=float(parsed_data.get('amount', 0)),
                merchant=parsed_data.get('merchant', 'Unknown Merchant'),
                date=parsed_data.get('date', datetime.now().strftime('%Y-%m-%d')),
                category=parsed_data.get('category', 'Other'),
                ref_id=parsed_data.get('ref_id', self._generate_fallback_ref_id(sms_text)),
                transaction_type=parsed_data.get('transaction_type', 'debit'),
                card_type=parsed_data.get('card_type'),
                bank=parsed_data.get('bank'),
                payment_method=parsed_data.get('payment_method'),
                original_sms=sms_text,
                is_valid=True
            )
            
            return transaction
            
        except Exception as e:
            logger.error(f'Error parsing SMS with Gemini: {e}')
            return self._fallback_parse(sms_text)
    
    def _generate_fallback_ref_id(self, sms_text: str) -> str:
        """Generate a fallback reference ID from SMS content"""
        import hashlib
        
        # Try to extract UPI reference first
        upi_patterns = [
            r'UPI[:/]([A-Za-z0-9]+)',
            r'Ref[:/]\s*([A-Za-z0-9]+)',
            r'TXN[:/]\s*([A-Za-z0-9]+)',
            r'Txn[:/]\s*([A-Za-z0-9]+)',
            r'Transaction ID[:/]\s*([A-Za-z0-9]+)',
            r'(\d{12,})',  # Long numbers (12+ digits)
        ]
        
        for pattern in upi_patterns:
            match = re.search(pattern, sms_text, re.IGNORECASE)
            if match:
                return f"REF_{match.group(1)}"
        
        # If no reference found, create hash-based ID
        content_hash = hashlib.md5(sms_text.encode()).hexdigest()[:8]
        return f"HASH_{content_hash.upper()}"
    
    def _create_parsing_prompt(self, sms_text: str) -> str:
        """Create the parsing prompt for Gemini API"""
        return f'''
You are a financial transaction parser. Analyze the following Indian financial SMS and determine if it represents a valid SPENDING transaction.

CRITICAL: Only return a JSON response if this is a VALID FINANCIAL transaction. If the SMS is NOT a financial transaction, return "null" instead of JSON.

VALID FINANCIAL TRANSACTIONS include:
DEBIT TRANSACTIONS (money spent):
- Purchases at stores/merchants
- Bill payments
- Online payments
- ATM withdrawals
- UPI payments sent
- Card transactions
- Transfer sent

CREDIT TRANSACTIONS (money received):
- Salary deposits
- UPI payments received
- Bank transfers received
- Interest credits
- Refunds received
- Cashback credits
- Investment returns

DO NOT parse these as transactions:
- OTP messages
- Balance enquiries
- Account statements
- Welcome messages
- Service notifications
- KYC updates
- Card activation messages
- Maintenance messages
- Loan applications
- Insurance notifications

If this is a valid financial transaction, return ONLY a JSON object with this structure:

{{
  "amount": <number>,
  "merchant": "<string>",
  "date": "YYYY-MM-DD",
  "category": "<string>",
  "ref_id": "<unique_reference_id>",
  "transaction_type": "<debit or credit>",
  "card_type": "<string or null>",
  "bank": "<string or null>",
  "payment_method": "<string or null>"
}}

Requirements:
- amount: must be a positive number representing money amount
- merchant: the merchant/source name (for debit: where money spent, for credit: who sent money)
- date: transaction date in YYYY-MM-DD format
- category: one of: Food & Dining, Shopping, Entertainment, Transportation, Utilities, Telecommunications, Electronics, Salary, Investment, Refund, Transfer, or Other
- ref_id: extract transaction ID, UPI reference, or create unique identifier from SMS content
- transaction_type: "debit" for money spent, "credit" for money received
- card_type: Credit Card, Debit Card, UPI, Bank Transfer, etc.
- bank: Bank name if mentioned
- payment_method: Payment method used

SMS: {sms_text}

Response (either valid JSON or "null"):'''

    def _fallback_parse(self, sms_text: str) -> Optional[Transaction]:
        """Fallback parsing method if Gemini API fails"""
        try:
            # Check if this looks like a non-transaction SMS
            if self._is_non_transaction_sms(sms_text):
                return None
            
            amount = self._extract_amount(sms_text)
            if amount is None:
                return None
            
            # Determine transaction type
            transaction_type = self._determine_transaction_type(sms_text)
            
            merchant = self._extract_merchant(sms_text) or 'Unknown Merchant'
            date = self._extract_date(sms_text) or datetime.now().strftime('%Y-%m-%d')
            category = self._categorize_transaction(merchant, transaction_type)
            
            return Transaction(
                amount=amount,
                merchant=merchant,
                date=date,
                category=category,
                ref_id=self._generate_fallback_ref_id(sms_text),
                transaction_type=transaction_type,
                original_sms=sms_text,
                is_valid=True
            )
        except Exception as e:
            logger.error(f'Error in fallback parsing: {e}')
            return None
    
    def _determine_transaction_type(self, sms_text: str) -> str:
        """Determine if transaction is debit or credit"""
        sms_lower = sms_text.lower()
        
        # Credit indicators
        credit_patterns = [
            'credited', 'received', 'deposited', 'refund', 'cashback',
            'interest credit', 'salary credit', 'bonus credit', 'dividend',
            'investment return', 'upi/cr/', 'cr/', '/cr', 'transfer credit'
        ]
        
        # Debit indicators
        debit_patterns = [
            'debited', 'spent', 'charged', 'withdrawn', 'payment',
            'purchase', 'upi/dr/', 'dr/', '/dr', 'transfer debit'
        ]
        
        # Check for credit patterns first
        for pattern in credit_patterns:
            if pattern in sms_lower:
                return 'credit'
        
        # Check for debit patterns
        for pattern in debit_patterns:
            if pattern in sms_lower:
                return 'debit'
        
        # Default to debit if unclear
        return 'debit'
    
    def _categorize_transaction(self, merchant: str, transaction_type: str) -> str:
        """Categorize transaction based on merchant and type"""
        merchant_lower = merchant.lower()
        
        # Credit transaction categories
        if transaction_type == 'credit':
            if any(word in merchant_lower for word in ['salary', 'payroll', 'employer']):
                return 'Salary'
            elif any(word in merchant_lower for word in ['interest', 'dividend', 'investment']):
                return 'Investment'
            elif any(word in merchant_lower for word in ['refund', 'return']):
                return 'Refund'
            elif any(word in merchant_lower for word in ['cashback', 'reward']):
                return 'Cashback'
            else:
                return 'Transfer'
        
        # Debit transaction categories (existing logic)
        return self._categorize_merchant(merchant)
    
    def _is_non_transaction_sms(self, sms_text: str) -> bool:
        """Check if SMS is not a transaction"""
        sms_lower = sms_text.lower()
        non_transaction_patterns = [
            'otp', 'verification code', 'password', 'pin', 'login', 'welcome',
            'thank you', 'successfully registered', 'account created', 'kyc',
            'document', 'update', 'maintenance', 'service', 'support', 'help',
            'contact', 'balance enquiry', 'mini statement', 'cheque book',
            'card blocked', 'card unblocked', 'new card', 'replacement card',
            'insurance', 'investment', 'mutual fund', 'fixed deposit', 'loan',
            'emi', 'credit score', 'credit report', 'credited', 'received',
            'deposited', 'refund', 'reversal', 'adjustment'
        ]
        
        return any(pattern in sms_lower for pattern in non_transaction_patterns)
    
    def _extract_amount(self, text: str) -> Optional[float]:
        """Extract amount from SMS text"""
        amount_pattern = r'(INR|Rs\.?|Rs)\s*([0-9,]+(?:\.\d{1,2})?)'
        match = re.search(amount_pattern, text, re.IGNORECASE)
        if match:
            amount_str = match.group(2).replace(',', '')
            try:
                return float(amount_str)
            except ValueError:
                return None
        return None
    
    def _extract_merchant(self, text: str) -> Optional[str]:
        """Extract merchant name from SMS text"""
        patterns = [
            r'\bat\s+([A-Z0-9 &\-\.]{2,})',
            r'\bto\s+([A-Z0-9 &\-\.]{2,})',
            r'\bvia\s+([A-Z0-9 &\-\.]{2,})'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()
        
        # Fallback pattern
        token_pattern = r'\b([A-Z]{3,}[A-Z0-9 &\-]*)\b'
        match = re.search(token_pattern, text)
        return match.group(1) if match else None
    
    def _extract_date(self, text: str) -> Optional[str]:
        """Extract date from SMS text"""
        date_pattern = r'(\d{2}[/-][A-Za-z]{3}[/-]\d{4}|\d{2}[/-]\d{2}[/-]\d{4}|\d{2}\s+[A-Za-z]{3}\s+\d{4})'
        match = re.search(date_pattern, text)
        if match:
            date_str = match.group(0)
            # Try to parse different date formats
            for fmt in ['%d/%m/%Y', '%d-%m-%Y', '%d/%b/%Y', '%d-%b-%Y', '%d %b %Y']:
                try:
                    parsed_date = datetime.strptime(date_str, fmt)
                    return parsed_date.strftime('%Y-%m-%d')
                except ValueError:
                    continue
        return None
    
    def _categorize_merchant(self, merchant: str) -> str:
        """Categorize merchant based on name"""
        merchant_lower = merchant.lower()
        
        if any(word in merchant_lower for word in ['swiggy', 'zomato', 'starbucks', 'dominos', 'kfc', 'mcdonald']):
            return 'Food & Dining'
        elif any(word in merchant_lower for word in ['amazon', 'flipkart', 'big bazaar', 'reliance digital', 'mall']):
            return 'Shopping'
        elif any(word in merchant_lower for word in ['netflix', 'spotify', 'bookmyshow', 'cinema', 'movie']):
            return 'Entertainment'
        elif any(word in merchant_lower for word in ['uber', 'ola', 'metro', 'bus', 'railway']):
            return 'Transportation'
        elif any(word in merchant_lower for word in ['electricity', 'bill', 'utility', 'gas', 'water']):
            return 'Utilities'
        elif any(word in merchant_lower for word in ['airtel', 'jio', 'vodafone', 'telecom']):
            return 'Telecommunications'
        elif any(word in merchant_lower for word in ['electronics', 'mobile', 'laptop', 'computer']):
            return 'Electronics'
        else:
            return 'Other'

class SMSDataProcessor:
    """Process SMS data from CSV files and store results"""
    
    def __init__(self, parser: GeminiSMSParser, db_path: str = 'transactions.db'):
        self.parser = parser
        self.db_path = db_path
        self.setup_database()
    
    def setup_database(self):
        """Setup SQLite database for storing transactions"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                amount REAL NOT NULL,
                merchant TEXT NOT NULL,
                date TEXT NOT NULL,
                category TEXT NOT NULL,
                ref_id TEXT NOT NULL UNIQUE,
                transaction_type TEXT NOT NULL DEFAULT 'debit',
                card_type TEXT,
                bank TEXT,
                payment_method TEXT,
                original_sms TEXT NOT NULL,
                is_valid BOOLEAN NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create index on ref_id for faster lookups
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_ref_id ON transactions(ref_id)
        ''')
        
        conn.commit()
        conn.close()
    
    def process_csv_file(self, csv_file_path: str, sms_column: str = 'sms_body') -> List[Transaction]:
        """Process SMS data from CSV file"""
        logger.info(f"Processing CSV file: {csv_file_path}")
        
        transactions = []
        
        try:
            df = pd.read_csv(csv_file_path)
            logger.info(f"Found {len(df)} SMS messages in CSV")
            
            for index, row in df.iterrows():
                if pd.isna(row[sms_column]):
                    continue
                
                sms_text = str(row[sms_column])
                logger.debug(f"Processing SMS {index + 1}/{len(df)}: {sms_text[:50]}...")
                
                transaction = self.parser.parse_sms(sms_text)
                if transaction:
                    transactions.append(transaction)
                    logger.info(f"Valid transaction found: {transaction.merchant} - ₹{transaction.amount}")
            
            logger.info(f"Processed {len(df)} SMS messages, found {len(transactions)} valid transactions")
            return transactions
            
        except Exception as e:
            logger.error(f"Error processing CSV file: {e}")
            return []
    
    def store_transactions(self, transactions: List[Transaction]):
        """Store transactions in database with duplicate checking"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        stored_count = 0
        duplicate_count = 0
        
        for transaction in transactions:
            try:
                # Check if ref_id already exists
                cursor.execute('SELECT id FROM transactions WHERE ref_id = ?', (transaction.ref_id,))
                existing = cursor.fetchone()
                
                if existing:
                    duplicate_count += 1
                    logger.debug(f"Duplicate transaction found with ref_id: {transaction.ref_id}")
                    continue
                
                # Insert new transaction
                cursor.execute('''
                    INSERT INTO transactions 
                    (amount, merchant, date, category, ref_id, transaction_type, card_type, bank, payment_method, original_sms, is_valid)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    transaction.amount,
                    transaction.merchant or 'Unknown',  # Handle None values
                    transaction.date,
                    transaction.category or 'Other',    # Handle None values
                    transaction.ref_id,
                    transaction.transaction_type,
                    transaction.card_type,
                    transaction.bank,
                    transaction.payment_method,
                    transaction.original_sms,
                    transaction.is_valid
                ))
                stored_count += 1
                
            except sqlite3.IntegrityError as e:
                if "UNIQUE constraint failed" in str(e):
                    duplicate_count += 1
                    logger.debug(f"Duplicate ref_id detected: {transaction.ref_id}")
                else:
                    logger.error(f"Database integrity error: {e}")
        
        conn.commit()
        conn.close()
        logger.info(f"Stored {stored_count} new transactions, skipped {duplicate_count} duplicates")
    
    def get_all_transactions(self) -> pd.DataFrame:
        """Get all transactions as DataFrame"""
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query('SELECT * FROM transactions', conn)
        conn.close()
        return df
    
    def export_to_csv(self, output_path: str = 'parsed_transactions.csv'):
        """Export transactions to CSV"""
        df = self.get_all_transactions()
        df.to_csv(output_path, index=False)
        logger.info(f"Exported transactions to {output_path}")

class DataAnalyzer:
    """Analyze transaction data and generate insights"""
    
    def __init__(self, processor: SMSDataProcessor):
        self.processor = processor
    
    def generate_analytics_report(self) -> Dict:
        """Generate comprehensive analytics report"""
        df = self.processor.get_all_transactions()
        
        if df.empty:
            logger.warning("No transactions found for analysis")
            return {}
        
        # Convert amount to numeric and date to datetime
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        
        report = {
            'total_transactions': len(df),
            'total_amount': df['amount'].sum(),
            'average_transaction': df['amount'].mean(),
            'median_transaction': df['amount'].median(),
            'date_range': {
                'start': df['date'].min().strftime('%Y-%m-%d') if not df['date'].isnull().all() else 'N/A',
                'end': df['date'].max().strftime('%Y-%m-%d') if not df['date'].isnull().all() else 'N/A'
            },
            'category_distribution': df['category'].value_counts().to_dict(),
            'top_merchants': df['merchant'].value_counts().head(10).to_dict(),
            'payment_method_distribution': df['payment_method'].value_counts().to_dict() if 'payment_method' in df.columns else {},
            'bank_distribution': df['bank'].value_counts().to_dict() if 'bank' in df.columns else {},
            'monthly_spending': self._get_monthly_spending(df),
            'amount_ranges': self._get_amount_distribution(df)
        }
        
        return report
    
    def _get_monthly_spending(self, df: pd.DataFrame) -> Dict:
        """Get monthly spending distribution"""
        if df['date'].isnull().all():
            return {}
        
        df['month'] = df['date'].dt.to_period('M')
        monthly = df.groupby('month')['amount'].sum().to_dict()
        return {str(k): v for k, v in monthly.items()}
    
    def _get_amount_distribution(self, df: pd.DataFrame) -> Dict:
        """Get amount range distribution"""
        ranges = {
            '0-100': len(df[(df['amount'] >= 0) & (df['amount'] <= 100)]),
            '101-500': len(df[(df['amount'] > 100) & (df['amount'] <= 500)]),
            '501-1000': len(df[(df['amount'] > 500) & (df['amount'] <= 1000)]),
            '1001-5000': len(df[(df['amount'] > 1000) & (df['amount'] <= 5000)]),
            '5000+': len(df[df['amount'] > 5000])
        }
        return ranges
    
    def create_visualizations(self, output_dir: str = 'analytics_plots'):
        """Create visualization plots"""
        os.makedirs(output_dir, exist_ok=True)
        
        df = self.processor.get_all_transactions()
        if df.empty:
            logger.warning("No data available for visualization")
            return
        
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        
        # Set up the plotting style
        plt.style.use('seaborn-v0_8')
        
        # 1. Category Distribution Pie Chart
        plt.figure(figsize=(10, 8))
        category_counts = df['category'].value_counts()
        plt.pie(category_counts.values, labels=category_counts.index, autopct='%1.1f%%')
        plt.title('Transaction Distribution by Category')
        plt.savefig(os.path.join(output_dir, 'category_distribution.png'), dpi=300, bbox_inches='tight')
        plt.close()
        
        # 2. Monthly Spending Trend
        if not df['date'].isnull().all():
            plt.figure(figsize=(12, 6))
            monthly_spending = df.groupby(df['date'].dt.to_period('M'))['amount'].sum()
            monthly_spending.plot(kind='line', marker='o')
            plt.title('Monthly Spending Trend')
            plt.xlabel('Month')
            plt.ylabel('Amount (₹)')
            plt.xticks(rotation=45)
            plt.grid(True)
            plt.savefig(os.path.join(output_dir, 'monthly_trend.png'), dpi=300, bbox_inches='tight')
            plt.close()
        
        # 3. Top Merchants Bar Chart
        plt.figure(figsize=(12, 8))
        top_merchants = df['merchant'].value_counts().head(15)
        top_merchants.plot(kind='barh')
        plt.title('Top 15 Merchants by Transaction Count')
        plt.xlabel('Number of Transactions')
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, 'top_merchants.png'), dpi=300, bbox_inches='tight')
        plt.close()
        
        # 4. Amount Distribution Histogram
        plt.figure(figsize=(10, 6))
        plt.hist(df['amount'].dropna(), bins=30, edgecolor='black')
        plt.title('Transaction Amount Distribution')
        plt.xlabel('Amount (₹)')
        plt.ylabel('Frequency')
        plt.grid(True, alpha=0.3)
        plt.savefig(os.path.join(output_dir, 'amount_distribution.png'), dpi=300, bbox_inches='tight')
        plt.close()
        
        logger.info(f"Visualizations saved to {output_dir}")
    
    def print_summary_report(self):
        """Print a comprehensive summary report"""
        report = self.generate_analytics_report()
        
        if not report:
            print("No data available for analysis")
            return
        
        print("\n" + "="*60)
        print("        SMS TRANSACTION ANALYSIS REPORT")
        print("="*60)
        
        print(f"\n📊 OVERVIEW:")
        print(f"   Total Transactions: {report['total_transactions']:,}")
        print(f"   Total Amount: ₹{report['total_amount']:,.2f}")
        print(f"   Average Transaction: ₹{report['average_transaction']:,.2f}")
        print(f"   Median Transaction: ₹{report['median_transaction']:,.2f}")
        print(f"   Date Range: {report['date_range']['start']} to {report['date_range']['end']}")
        
        print(f"\n🏷️  CATEGORY DISTRIBUTION:")
        for category, count in report['category_distribution'].items():
            percentage = (count / report['total_transactions']) * 100
            print(f"   {category:<20}: {count:>5} ({percentage:>5.1f}%)")
        
        print(f"\n🏪 TOP 10 MERCHANTS:")
        for i, (merchant, count) in enumerate(list(report['top_merchants'].items())[:10], 1):
            print(f"   {i:>2}. {merchant:<25}: {count:>4} transactions")
        
        if report['payment_method_distribution']:
            print(f"\n💳 PAYMENT METHODS:")
            for method, count in report['payment_method_distribution'].items():
                if method:  # Skip None values
                    print(f"   {method:<20}: {count:>5}")
        
        if report['bank_distribution']:
            print(f"\n🏦 BANKS:")
            for bank, count in report['bank_distribution'].items():
                if bank:  # Skip None values
                    print(f"   {bank:<20}: {count:>5}")
        
        print(f"\n💰 AMOUNT RANGES:")
        for range_name, count in report['amount_ranges'].items():
            percentage = (count / report['total_transactions']) * 100
            print(f"   ₹{range_name:<15}: {count:>5} ({percentage:>5.1f}%)")
        
        if report['monthly_spending']:
            print(f"\n📅 MONTHLY SPENDING:")
            for month, amount in list(report['monthly_spending'].items())[-12:]:  # Last 12 months
                print(f"   {month}: ₹{amount:,.2f}")
        
        print("\n" + "="*60)

def main():
    """Main function to run the SMS parser"""
    # Configuration
    API_KEY = "AIzaSyArZpN-ZVmhAR3emZN9P5p2Y_hjEn8h97Q"  # Replace with your actual API key
    CSV_FILE_PATH = "sms_data_from_raw.csv"  # Path to your CSV file
    SMS_COLUMN = "sms_body"  # Column name containing SMS text
    
    try:
        # Initialize components
        logger.info("Initializing SMS Parser...")
        parser = GeminiSMSParser(API_KEY)
        processor = SMSDataProcessor(parser)
        analyzer = DataAnalyzer(processor)
        
        # Check if CSV file exists
        if not os.path.exists(CSV_FILE_PATH):
            logger.error(f"CSV file not found: {CSV_FILE_PATH}")
            logger.info("Please ensure your CSV file exists and update the CSV_FILE_PATH variable")
            return
        
        # Process CSV file
        transactions = processor.process_csv_file(CSV_FILE_PATH, SMS_COLUMN)
        
        if not transactions:
            logger.warning("No valid transactions found in the CSV file")
            return
        
        # Store transactions
        processor.store_transactions(transactions)
        
        # Export to CSV
        processor.export_to_csv()
        
        # Generate analytics
        analyzer.print_summary_report()
        analyzer.create_visualizations()
        
        logger.info("SMS parsing and analysis completed successfully!")
        
    except Exception as e:
        logger.error(f"Error in main execution: {e}")

if __name__ == "__main__":
    main()
