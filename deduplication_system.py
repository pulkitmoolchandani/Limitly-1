#!/usr/bin/env python3
"""
SMS Transaction Deduplication System
Handles deduplication at database storage level using multiple strategies
"""

import pandas as pd
import sqlite3
import hashlib
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set, Tuple
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TransactionDeduplicator:
    """
    Multi-strategy deduplication system for SMS transactions
    
    Strategy Hierarchy:
    1. Primary: ref_id based deduplication (UPI IDs, bank references)
    2. Secondary: Composite key (sender, amount, txn_type, minute_bucket)
    3. Tertiary: Content hash for exact duplicates
    4. Special: SIP linking (NACH debits with AMC credits)
    """
    
    def __init__(self, db_path: str = "deduplicated_transactions.db"):
        self.db_path = db_path
        self.setup_database()
        
    def setup_database(self):
        """Setup database with proper deduplication constraints"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Main transactions table with deduplication constraints
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount REAL NOT NULL,
            merchant TEXT,
            date TEXT NOT NULL,
            category TEXT,
            ref_id TEXT,
            transaction_type TEXT NOT NULL,
            card_type TEXT,
            bank TEXT,
            payment_method TEXT,
            original_sms TEXT NOT NULL,
            sender TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            confidence_score REAL NOT NULL,
            raw_hash TEXT NOT NULL,
            composite_key TEXT NOT NULL,
            minute_bucket TEXT NOT NULL,
            is_duplicate BOOLEAN DEFAULT FALSE,
            duplicate_strategy TEXT,
            sip_group_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            -- Unique constraints for deduplication
            UNIQUE(composite_key),
            UNIQUE(raw_hash)
        )
        """)
        
        # Duplicate tracking table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS duplicate_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_id INTEGER,
            duplicate_hash TEXT,
            duplicate_reason TEXT,
            duplicate_count INTEGER DEFAULT 1,
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (original_id) REFERENCES transactions (id)
        )
        """)
        
        # SIP linking table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS sip_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sip_group_id TEXT NOT NULL,
            nach_transaction_id INTEGER,
            amc_transaction_id INTEGER,
            amount_match_tolerance REAL DEFAULT 1.0,
            time_match_tolerance_hours INTEGER DEFAULT 24,
            confidence_score REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (nach_transaction_id) REFERENCES transactions (id),
            FOREIGN KEY (amc_transaction_id) REFERENCES transactions (id)
        )
        """)
        
        # Create indexes for performance
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_ref_id_unique ON transactions (ref_id) WHERE ref_id IS NOT NULL AND ref_id != ''")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ref_id ON transactions (ref_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_composite_key ON transactions (composite_key)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_raw_hash ON transactions (raw_hash)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_amount_date ON transactions (amount, date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sip_group ON transactions (sip_group_id)")
        
        conn.commit()
        conn.close()
        
        logger.info("Deduplication database setup complete")
    
    def generate_ref_id(self, sms_text: str, amount: float, sender: str) -> str:
        """
        Generate or extract reference ID using multiple strategies
        
        Priority:
        1. UPI transaction IDs
        2. Bank reference numbers
        3. Transaction IDs from SMS
        4. Generated hash-based ID
        """
        
        # Strategy 1: UPI Reference IDs
        upi_patterns = [
            r'UPI[:/]\s*(\w{12,})',  # UPI:123456789012
            r'Ref[:\s]+(\w{12,})',   # Ref: 123456789012
            r'TXN[:\s]*(\w{10,})',   # TXN:1234567890
            r'(\d{12,15})',          # Long numeric IDs
        ]
        
        for pattern in upi_patterns:
            match = re.search(pattern, sms_text, re.IGNORECASE)
            if match:
                ref_id = match.group(1)
                # Validate ref_id quality
                if len(ref_id) >= 10 and not ref_id.lower() in ['debit', 'credit', 'transaction']:
                    return f"UPI_{ref_id}"
        
        # Strategy 2: Bank-specific patterns
        bank_patterns = [
            r'(?:RRN|UTR)[:\s]*(\w{10,})',
            r'(?:Txn|Transaction)\s+(?:No|ID)[:\s]*(\w{8,})',
            r'(?:Ref|Reference)\s+(?:No|ID)[:\s]*(\w{8,})',
        ]
        
        for pattern in bank_patterns:
            match = re.search(pattern, sms_text, re.IGNORECASE)
            if match:
                return f"BANK_{match.group(1)}"
        
        # Strategy 3: Generated composite ID
        # Use amount, sender, and SMS content hash
        content_for_hash = f"{amount}_{sender}_{sms_text[:100]}"
        hash_digest = hashlib.md5(content_for_hash.encode()).hexdigest()[:12]
        return f"GEN_{hash_digest}"
    
    def generate_composite_key(self, sender: str, amount: float, txn_type: str, timestamp: str) -> str:
        """Generate composite key for fallback deduplication"""
        try:
            # Create minute bucket (transactions within same minute are likely duplicates)
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            minute_bucket = dt.strftime('%Y%m%d_%H%M')
        except:
            minute_bucket = "unknown"
        
        # Normalize amount (handle float precision)
        normalized_amount = f"{amount:.2f}" if amount else "0.00"
        
        # Create composite key
        composite = f"{sender}_{normalized_amount}_{txn_type}_{minute_bucket}"
        return hashlib.md5(composite.encode()).hexdigest()[:16]
    
    def is_sip_transaction(self, sms_text: str, amount: float) -> bool:
        """Detect if transaction is SIP/investment related"""
        sip_indicators = [
            r'\b(?:SIP|Systematic|Investment|Plan)\b',
            r'\b(?:AMC|Asset\s+Management|Fund)\b',
            r'\b(?:CAMS|KFintech|Mutual\s+Fund)\b',
            r'\b(?:NAV|Net\s+Asset\s+Value)\b',
            r'\b(?:Folio|Units|Scheme)\b'
        ]
        
        for pattern in sip_indicators:
            if re.search(pattern, sms_text, re.IGNORECASE):
                return True
        
        return False
    
    def find_sip_matches(self, nach_txn: Dict, transactions_df: pd.DataFrame) -> List[Dict]:
        """Find matching AMC credits for NACH debits (SIP linking)"""
        matches = []
        
        if not self.is_sip_transaction(nach_txn['original_sms'], nach_txn['amount']):
            return matches
        
        # Look for AMC credits within ±1 day with ±₹1 amount tolerance
        nach_date = datetime.fromisoformat(nach_txn['timestamp'].replace('Z', '+00:00'))
        amount_tolerance = 1.0
        
        # Filter potential matches
        candidates = transactions_df[
            (transactions_df['transaction_type'] == 'CREDIT') &
            (transactions_df['amount'].between(
                nach_txn['amount'] - amount_tolerance, 
                nach_txn['amount'] + amount_tolerance
            ))
        ]
        
        for _, candidate in candidates.iterrows():
            try:
                candidate_date = datetime.fromisoformat(candidate['timestamp'].replace('Z', '+00:00'))
                time_diff = abs((candidate_date - nach_date).total_seconds() / 3600)  # hours
                
                if time_diff <= 24:  # Within 24 hours
                    confidence = max(0, 100 - (time_diff * 2))  # Confidence decreases with time
                    
                    if self.is_sip_transaction(candidate['original_sms'], candidate['amount']):
                        matches.append({
                            'amc_transaction': candidate,
                            'time_diff_hours': time_diff,
                            'amount_diff': abs(candidate['amount'] - nach_txn['amount']),
                            'confidence': confidence
                        })
            except:
                continue
        
        return sorted(matches, key=lambda x: x['confidence'], reverse=True)
    
    def process_transactions(self, transactions_df: pd.DataFrame) -> Dict:
        """
        Process transactions through deduplication pipeline
        
        Returns:
        - stats: Deduplication statistics
        - unique_transactions: Deduplicated transaction list
        - duplicates: Information about found duplicates
        """
        
        logger.info(f"Starting deduplication of {len(transactions_df):,} transactions")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        stats = {
            'total_input': len(transactions_df),
            'unique_transactions': 0,
            'duplicates_ref_id': 0,
            'duplicates_composite': 0,
            'duplicates_content': 0,
            'sip_links_created': 0,
            'errors': 0
        }
        
        processed_ref_ids: Set[str] = set()
        processed_composite_keys: Set[str] = set()
        processed_content_hashes: Set[str] = set()
        sip_groups: Dict[str, List] = {}
        
        for idx, row in transactions_df.iterrows():
            try:
                # Generate identifiers
                ref_id = self.generate_ref_id(row['original_sms'], row.get('amount', 0), row['sender'])
                composite_key = self.generate_composite_key(
                    row['sender'], 
                    row.get('amount', 0), 
                    row.get('transaction_type', 'unknown'),
                    row['timestamp']
                )
                content_hash = hashlib.md5(row['original_sms'].encode()).hexdigest()
                
                # Minute bucket for time-based grouping
                try:
                    dt = datetime.fromisoformat(row['timestamp'].replace('Z', '+00:00'))
                    minute_bucket = dt.strftime('%Y%m%d_%H%M')
                except:
                    minute_bucket = "unknown"
                
                # Deduplication logic
                is_duplicate = False
                duplicate_strategy = None
                
                # Strategy 1: ref_id deduplication
                if ref_id and ref_id in processed_ref_ids:
                    is_duplicate = True
                    duplicate_strategy = "ref_id"
                    stats['duplicates_ref_id'] += 1
                
                # Strategy 2: composite key deduplication
                elif composite_key in processed_composite_keys:
                    is_duplicate = True
                    duplicate_strategy = "composite_key"
                    stats['duplicates_composite'] += 1
                
                # Strategy 3: content hash deduplication
                elif content_hash in processed_content_hashes:
                    is_duplicate = True
                    duplicate_strategy = "content_hash"
                    stats['duplicates_content'] += 1
                
                if not is_duplicate:
                    # Insert unique transaction
                    cursor.execute("""
                    INSERT INTO transactions (
                        amount, merchant, date, category, ref_id, transaction_type,
                        card_type, bank, payment_method, original_sms, sender, timestamp,
                        confidence_score, raw_hash, composite_key, minute_bucket,
                        is_duplicate, duplicate_strategy
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        row.get('amount'), row.get('merchant'), row.get('date'), 
                        row.get('category'), ref_id, row.get('transaction_type'),
                        row.get('card_type'), row.get('bank'), row.get('payment_method'),
                        row['original_sms'], row['sender'], row['timestamp'],
                        row.get('confidence_score', 0), content_hash, composite_key, minute_bucket,
                        False, None
                    ))
                    
                    transaction_id = cursor.lastrowid
                    
                    # Track processed identifiers
                    if ref_id:
                        processed_ref_ids.add(ref_id)
                    processed_composite_keys.add(composite_key)
                    processed_content_hashes.add(content_hash)
                    
                    # SIP linking logic
                    if (row.get('transaction_type') == 'DEBIT' and 
                        self.is_sip_transaction(row['original_sms'], row.get('amount', 0))):
                        
                        sip_group_id = f"SIP_{ref_id}_{row.get('amount', 0):.2f}"
                        if sip_group_id not in sip_groups:
                            sip_groups[sip_group_id] = []
                        sip_groups[sip_group_id].append({
                            'id': transaction_id,
                            'type': 'NACH_DEBIT',
                            'data': row
                        })
                        
                        # Update transaction with SIP group
                        cursor.execute(
                            "UPDATE transactions SET sip_group_id = ? WHERE id = ?",
                            (sip_group_id, transaction_id)
                        )
                    
                    stats['unique_transactions'] += 1
                    
                else:
                    # Log duplicate
                    cursor.execute("""
                    INSERT INTO duplicate_log (duplicate_hash, duplicate_reason)
                    VALUES (?, ?)
                    """, (content_hash, duplicate_strategy))
                
                if idx % 1000 == 0 and idx > 0:
                    logger.info(f"Processed {idx:,} transactions...")
                    
            except Exception as e:
                logger.error(f"Error processing transaction {idx}: {e}")
                stats['errors'] += 1
                continue
        
        # Process SIP linking
        for sip_group_id, transactions in sip_groups.items():
            if len(transactions) > 1:
                # Create SIP links for transactions in same group
                for i, txn1 in enumerate(transactions):
                    for txn2 in transactions[i+1:]:
                        cursor.execute("""
                        INSERT INTO sip_links (
                            sip_group_id, nach_transaction_id, amc_transaction_id, confidence_score
                        ) VALUES (?, ?, ?, ?)
                        """, (sip_group_id, txn1['id'], txn2['id'], 95.0))
                        
                        stats['sip_links_created'] += 1
        
        conn.commit()
        conn.close()
        
        logger.info(f"Deduplication complete. Unique: {stats['unique_transactions']:,}, Duplicates: {stats['total_input'] - stats['unique_transactions']:,}")
        
        return stats
    
    def get_deduplication_report(self) -> Dict:
        """Generate comprehensive deduplication report"""
        conn = sqlite3.connect(self.db_path)
        
        # Get summary statistics
        unique_count = pd.read_sql("SELECT COUNT(*) as count FROM transactions WHERE NOT is_duplicate", conn)['count'].iloc[0]
        duplicate_count = pd.read_sql("SELECT COUNT(*) as count FROM duplicate_log", conn)['count'].iloc[0]
        sip_links = pd.read_sql("SELECT COUNT(*) as count FROM sip_links", conn)['count'].iloc[0]
        
        # Get duplicate breakdown
        duplicate_breakdown = pd.read_sql("""
        SELECT duplicate_reason, COUNT(*) as count 
        FROM duplicate_log 
        GROUP BY duplicate_reason 
        ORDER BY count DESC
        """, conn)
        
        # Get transaction type breakdown
        txn_breakdown = pd.read_sql("""
        SELECT transaction_type, COUNT(*) as count 
        FROM transactions 
        WHERE NOT is_duplicate 
        GROUP BY transaction_type
        """, conn)
        
        # Get bank breakdown
        bank_breakdown = pd.read_sql("""
        SELECT bank, COUNT(*) as count 
        FROM transactions 
        WHERE NOT is_duplicate AND bank IS NOT NULL 
        GROUP BY bank 
        ORDER BY count DESC 
        LIMIT 10
        """, conn)
        
        conn.close()
        
        return {
            'summary': {
                'unique_transactions': unique_count,
                'duplicates_removed': duplicate_count,
                'sip_links_created': sip_links,
                'deduplication_rate': (duplicate_count / (unique_count + duplicate_count)) * 100 if (unique_count + duplicate_count) > 0 else 0
            },
            'duplicate_breakdown': duplicate_breakdown.to_dict('records'),
            'transaction_breakdown': txn_breakdown.to_dict('records'),
            'bank_breakdown': bank_breakdown.to_dict('records')
        }

def main():
    """Run deduplication on enhanced ready transactions"""
    
    # Load enhanced ready transactions
    df = pd.read_csv('enhanced_ready_transactions.csv')
    
    print("🔄 SMS TRANSACTION DEDUPLICATION SYSTEM")
    print("=" * 50)
    print(f"Input transactions: {len(df):,}")
    print()
    
    # Initialize deduplicator
    deduplicator = TransactionDeduplicator()
    
    # Process transactions
    stats = deduplicator.process_transactions(df)
    
    # Generate report
    report = deduplicator.get_deduplication_report()
    
    print("📊 DEDUPLICATION RESULTS:")
    print("-" * 30)
    print(f"✅ Unique Transactions: {report['summary']['unique_transactions']:,}")
    print(f"🔄 Duplicates Removed: {report['summary']['duplicates_removed']:,}")
    print(f"🔗 SIP Links Created: {report['summary']['sip_links_created']:,}")
    print(f"📈 Deduplication Rate: {report['summary']['deduplication_rate']:.1f}%")
    
    print()
    print("🎯 DUPLICATE BREAKDOWN:")
    print("-" * 25)
    for item in report['duplicate_breakdown']:
        print(f"{item['duplicate_reason']}: {item['count']:,}")
    
    print()
    print("💰 TRANSACTION TYPE BREAKDOWN:")
    print("-" * 35)
    for item in report['transaction_breakdown']:
        print(f"{item['transaction_type']}: {item['count']:,}")
    
    print()
    print("🏦 TOP BANKS (Unique Transactions):")
    print("-" * 40)
    for item in report['bank_breakdown'][:5]:
        print(f"{item['bank']}: {item['count']:,}")
    
    print()
    print("📁 Database created: deduplicated_transactions.db")
    print("✅ Deduplication complete!")

if __name__ == "__main__":
    main()
