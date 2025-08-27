#!/usr/bin/env python3
"""
Complete SMS Financial Transaction Pipeline
Integrated: Regex Processing → Deduplication → LLM → Final Results
"""

import pandas as pd
import sqlite3
import hashlib
import re
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BucketType(Enum):
    BANK_LEDGER_SUCCESS = "ready"
    AMBIGUOUS = "ambiguous"
    REJECTED = "rejected"
    BANK_LEDGER_FAILED = "failed"
    INVESTMENT_OR_REMINDER = "investment"

class TransactionType(Enum):
    DEBIT = "debit"
    CREDIT = "credit"

class Rail(Enum):
    UPI = "UPI"
    IMPS = "IMPS"
    NEFT = "NEFT"
    RTGS = "RTGS"
    CARD = "CARD"
    POS = "POS"
    ATM = "ATM"
    NACH = "NACH"
    UNKNOWN = "UNKNOWN"

@dataclass
class ParsedTransaction:
    """Structured transaction data"""
    amount: Optional[float] = None
    txn_type: Optional[TransactionType] = None
    rail: Optional[Rail] = None
    balance: Optional[float] = None
    ref_id: Optional[str] = None
    card_last4: Optional[str] = None
    upi_vpa: Optional[str] = None
    merchant: Optional[str] = None
    date: Optional[str] = None
    bank: Optional[str] = None
    confidence_score: float = 0.0
    bucket: Optional[BucketType] = None
    original_sms: str = ""
    sender: str = ""
    timestamp: str = ""
    raw_hash: str = ""
    composite_key: str = ""
    penalties: List[str] = None
    signals: List[str] = None
    is_duplicate: bool = False
    duplicate_reason: str = ""
    
    def __post_init__(self):
        if self.penalties is None:
            self.penalties = []
        if self.signals is None:
            self.signals = []

class MultiStrategyDeduplicator:
    """
    Multi-strategy deduplication with 3 approaches:
    1. ref_id based (UPI IDs, bank references)
    2. Composite key (sender + amount + type + time bucket)
    3. Content hash (exact SMS duplicates)
    """
    
    def __init__(self):
        self.seen_ref_ids: Set[str] = set()
        self.seen_composite_keys: Set[str] = set()
        self.seen_content_hashes: Set[str] = set()
        self.duplicate_stats = {
            'ref_id_duplicates': 0,
            'composite_duplicates': 0,
            'content_duplicates': 0,
            'total_processed': 0,
            'unique_transactions': 0
        }
    
    def generate_ref_id(self, sms_text: str, amount: float, sender: str) -> str:
        """Generate or extract reference ID"""
        # Strategy 1: UPI Reference IDs
        upi_patterns = [
            r'UPI[:/]\s*(\w{10,})',  # UPI:123456789012
            r'Ref[:\s]+(\w{10,})',   # Ref: 123456789012
            r'TXN[:\s]*(\w{10,})',   # TXN:1234567890
            r'(\d{12,16})',          # Long numeric IDs
        ]
        
        for pattern in upi_patterns:
            match = re.search(pattern, sms_text, re.IGNORECASE)
            if match:
                ref_id = match.group(1)
                if len(ref_id) >= 10 and ref_id.lower() not in ['debit', 'credit', 'transaction']:
                    return f"UPI_{ref_id}"
        
        # Strategy 2: Bank-specific patterns
        bank_patterns = [
            r'(?:RRN|UTR)[:\s]*(\w{10,})',
            r'(?:Txn|Transaction)\s+(?:No|ID)[:\s]*(\w{8,})',
        ]
        
        for pattern in bank_patterns:
            match = re.search(pattern, sms_text, re.IGNORECASE)
            if match:
                return f"BANK_{match.group(1)}"
        
        # Strategy 3: Generated ID from content
        content_key = f"{amount}_{sender}_{sms_text[:50]}"
        hash_id = hashlib.md5(content_key.encode()).hexdigest()[:12]
        return f"GEN_{hash_id}"
    
    def generate_composite_key(self, sender: str, amount: float, txn_type: str, timestamp: str) -> str:
        """Generate composite key for deduplication"""
        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            minute_bucket = dt.strftime('%Y%m%d_%H%M')
        except:
            minute_bucket = "unknown"
        
        normalized_amount = f"{amount:.2f}" if amount else "0.00"
        composite = f"{sender}_{normalized_amount}_{txn_type}_{minute_bucket}"
        return hashlib.md5(composite.encode()).hexdigest()[:16]
    
    def is_duplicate(self, transaction: ParsedTransaction) -> Tuple[bool, str]:
        """
        Check if transaction is duplicate using 3 strategies
        Returns: (is_duplicate, reason)
        """
        self.duplicate_stats['total_processed'] += 1
        
        # Generate identifiers
        if transaction.ref_id:
            ref_id = transaction.ref_id
        else:
            ref_id = self.generate_ref_id(
                transaction.original_sms, 
                transaction.amount or 0, 
                transaction.sender
            )
        
        composite_key = self.generate_composite_key(
            transaction.sender,
            transaction.amount or 0,
            str(transaction.txn_type) if transaction.txn_type else "unknown",
            transaction.timestamp
        )
        
        content_hash = hashlib.md5(transaction.original_sms.encode()).hexdigest()
        
        # Update transaction with generated keys
        transaction.ref_id = ref_id
        transaction.composite_key = composite_key
        transaction.raw_hash = content_hash
        
        # Strategy 1: ref_id check
        if ref_id and ref_id in self.seen_ref_ids:
            self.duplicate_stats['ref_id_duplicates'] += 1
            return True, "ref_id_duplicate"
        
        # Strategy 2: composite key check
        if composite_key in self.seen_composite_keys:
            self.duplicate_stats['composite_duplicates'] += 1
            return True, "composite_key_duplicate"
        
        # Strategy 3: content hash check
        if content_hash in self.seen_content_hashes:
            self.duplicate_stats['content_duplicates'] += 1
            return True, "content_hash_duplicate"
        
        # Mark as seen
        if ref_id:
            self.seen_ref_ids.add(ref_id)
        self.seen_composite_keys.add(composite_key)
        self.seen_content_hashes.add(content_hash)
        
        self.duplicate_stats['unique_transactions'] += 1
        return False, ""
    
    def get_stats(self) -> Dict:
        """Get deduplication statistics"""
        return self.duplicate_stats.copy()

class EnhancedSMSPipeline:
    """Complete SMS processing pipeline with integrated deduplication"""
    
    def __init__(self, cutoff_days: int = 10000):
        self.cutoff_days = cutoff_days
        self.cutoff_date = datetime.now() - timedelta(days=cutoff_days)
        self.deduplicator = MultiStrategyDeduplicator()
        self.patterns = self._init_patterns()
        
    def _init_patterns(self) -> Dict:
        """Initialize regex patterns"""
        return {
            'amount': [
                r'(?:INR|Rs\.?|₹|Rupees?)\s*([0-9,]+(?:\.\d{1,2})?)',
                r'Amount[:\s]*(?:INR|Rs\.?|₹|Rupees?)?\s*([0-9,]+(?:\.\d{1,2})?)',
                r'(?:debited|credited|spent|received|paid)\s+(?:INR|Rs\.?|₹|Rupees?)?\s*([0-9,]+(?:\.\d{1,2})?)',
                r'([0-9,]+(?:\.\d{1,2})?)\s*(?:INR|Rs\.?|₹|Rupees?)',
                r'(?:for|of)\s+(?:INR|Rs\.?|₹|Rupees?)\s*([0-9,]+(?:\.\d{1,2})?)',
            ],
            'debit_verbs': [
                r'\b(?:debited|spent|charged|withdrawn|paid|purchase|deducted|debit)\b',
                r'\b(?:ATM|POS)\s+(?:withdrawal|transaction)\b',
                r'\b(?:bill\s+payment|online\s+payment)\b'
            ],
            'credit_verbs': [
                r'\b(?:credited|received|deposited|refund|cashback|interest)\b',
                r'\b(?:salary|bonus|dividend|transfer\s+credit)\b'
            ],
            'rails': {
                Rail.UPI: [r'\bUPI\b', r'@\w+', r'UPI[:/]'],
                Rail.IMPS: [r'\bIMPS\b'],
                Rail.NEFT: [r'\bNEFT\b'],
                Rail.RTGS: [r'\bRTGS\b'],
                Rail.CARD: [r'\bCard\b', r'ending\s+\d{4}'],
                Rail.POS: [r'\bPOS\b'],
                Rail.ATM: [r'\bATM\b'],
                Rail.NACH: [r'\bNACH\b', r'auto-debit']
            },
            'penalties': {
                'future_tense': [r'\bwill\s+be\s+debited\b', r'\bwill\s+be\s+charged\b'],
                'sip_amc': [r'\b(?:SIP|folio|NAV|units|CAMS|KFintech|AMC|MF)\b'],
                'failed': [r'\b(?:failed|declined|rejected|insufficient|blocked)\b'],
                'otp': [r'\b(?:OTP|verification\s+code|PIN|code\s+is)\b'],
                'balance_enquiry': [r'\b(?:balance\s+enquiry|mini\s+statement)\b'],
                'maintenance': [r'\b(?:maintenance|service|update|KYC|upgrade)\b'],
                'no_numbers': [r'^[^\d]*$']
            },
            'signals': {
                'executed_verbs': [r'\b(?:debited|credited|spent|received|paid|charged|withdrawn)\b'],
                'amount_present': [r'(?:INR|Rs\.?|₹|Rupees?)\s*[0-9,]+'],
                'account_cue': [r'\bA/c\s+(?:No\.?\s*)?[XX]*\d{4}\b'],
                'rail_cue': [r'\b(?:UPI|IMPS|NEFT|RTGS|Card|ATM|POS)\b'],
                'ref_id_present': [r'(?:Ref|TXN|UPI)[:/]\s*\w+'],
                'balance_cue': [r'(?:Avl\s+Bal|Balance)[:\s]*(?:INR|Rs\.?|₹)?\s*[0-9,]+']
            }
        }
    
    def parse_sms(self, sms_text: str, sender: str = "", timestamp: str = "") -> ParsedTransaction:
        """Parse SMS with enhanced regex"""
        
        # Early rejection: No numbers
        if not re.search(r'\d', sms_text):
            return ParsedTransaction(
                original_sms=sms_text,
                sender=sender,
                timestamp=timestamp,
                confidence_score=0.0,
                bucket=BucketType.REJECTED,
                penalties=['no_numbers']
            )
        
        transaction = ParsedTransaction(
            original_sms=sms_text,
            sender=sender,
            timestamp=timestamp
        )
        
        # Extract fields
        transaction.amount = self._extract_amount(sms_text)
        transaction.txn_type = self._extract_transaction_type(sms_text)
        transaction.rail = self._extract_rail(sms_text)
        transaction.merchant = self._extract_merchant(sms_text)
        transaction.bank = self._extract_bank(sms_text, sender)
        transaction.date = self._extract_date(sms_text, timestamp)
        
        # Calculate confidence and determine bucket
        transaction.confidence_score = self._calculate_confidence(sms_text, transaction)
        transaction.bucket = self._determine_bucket(transaction)
        
        return transaction
    
    def _extract_amount(self, text: str) -> Optional[float]:
        """Extract amount from SMS"""
        for pattern in self.patterns['amount']:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                amount_str = match.group(1).replace(',', '')
                try:
                    return float(amount_str)
                except ValueError:
                    continue
        return None
    
    def _extract_transaction_type(self, text: str) -> Optional[TransactionType]:
        """Determine transaction type"""
        text_lower = text.lower()
        
        for pattern in self.patterns['credit_verbs']:
            if re.search(pattern, text_lower):
                return TransactionType.CREDIT
        
        for pattern in self.patterns['debit_verbs']:
            if re.search(pattern, text_lower):
                return TransactionType.DEBIT
        
        return None
    
    def _extract_rail(self, text: str) -> Optional[Rail]:
        """Extract payment rail"""
        for rail, patterns in self.patterns['rails'].items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    return rail
        return Rail.UNKNOWN
    
    def _extract_merchant(self, text: str) -> Optional[str]:
        """Extract merchant name"""
        merchant_patterns = [
            r'\bat\s+([A-Z0-9 &\-\.]{2,})',
            r'\bto\s+([A-Z0-9 &\-\.]{2,})',
            r'\bvia\s+([A-Z0-9 &\-\.]{2,})',
        ]
        
        for pattern in merchant_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                merchant = match.group(1).strip()
                return re.sub(r'\s+', ' ', merchant)
        return None
    
    def _extract_bank(self, text: str, sender: str = "") -> Optional[str]:
        """Extract bank name"""
        bank_patterns = [
            r'\b(SBI|HDFC|ICICI|AXIS|KOTAK|PNB|BOB|CANARA|UNION|INDUSIND|YES|IDFC|AU)\s*BANK\b',
            r'\b(HDFC|ICICI|AXIS|KOTAK|YES|IDFC|AU)\b'
        ]
        
        # Try sender first
        for pattern in bank_patterns:
            match = re.search(pattern, sender, re.IGNORECASE)
            if match:
                return match.group(1)
        
        # Try SMS text
        for pattern in bank_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    def _extract_date(self, text: str, timestamp: str = "") -> Optional[str]:
        """Extract date"""
        if timestamp:
            try:
                parsed_ts = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                return parsed_ts.strftime('%Y-%m-%d')
            except:
                pass
        return datetime.now().strftime('%Y-%m-%d')
    
    def _calculate_confidence(self, text: str, transaction: ParsedTransaction) -> float:
        """Calculate confidence score"""
        score = 0.0
        
        # Signal detection
        for signal_type, patterns in self.patterns['signals'].items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    transaction.signals.append(signal_type)
                    if signal_type == 'executed_verbs':
                        score += 25
                    elif signal_type == 'amount_present':
                        score += 20
                    elif signal_type in ['account_cue', 'rail_cue']:
                        score += 15
                    else:
                        score += 10
        
        # Field presence bonuses
        if transaction.amount is not None:
            score += 20
        if transaction.txn_type is not None:
            score += 15
        if transaction.rail != Rail.UNKNOWN:
            score += 10
        
        # Penalty detection
        for penalty_type, patterns in self.patterns['penalties'].items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    transaction.penalties.append(penalty_type)
                    if penalty_type in ['future_tense', 'failed']:
                        score -= 30
                    elif penalty_type == 'sip_amc':
                        score -= 25
                    elif penalty_type in ['otp', 'balance_enquiry']:
                        score -= 40
                    elif penalty_type == 'maintenance':
                        score -= 20
        
        return max(0, min(100, score))
    
    def _determine_bucket(self, transaction: ParsedTransaction) -> BucketType:
        """Determine classification bucket"""
        
        # Hard rejections
        if any(penalty in ['otp', 'balance_enquiry', 'maintenance', 'no_numbers'] 
               for penalty in transaction.penalties):
            return BucketType.REJECTED
        
        # Investment/SIP
        if any(penalty == 'sip_amc' for penalty in transaction.penalties):
            return BucketType.INVESTMENT_OR_REMINDER
        
        # Failed transactions
        if any(penalty == 'failed' for penalty in transaction.penalties):
            return BucketType.BANK_LEDGER_FAILED
        
        # High confidence
        if (transaction.confidence_score >= 70 and 
            transaction.amount is not None and 
            transaction.txn_type is not None):
            return BucketType.BANK_LEDGER_SUCCESS
        
        # Low confidence
        if transaction.confidence_score < 40:
            return BucketType.AMBIGUOUS
        
        # Missing critical fields
        if transaction.amount is None or transaction.txn_type is None:
            return BucketType.AMBIGUOUS
        
        return BucketType.BANK_LEDGER_SUCCESS
    
    def process_with_deduplication(self, csv_path: str) -> Dict:
        """Process SMS with integrated deduplication"""
        
        logger.info(f"🚀 Starting Complete SMS Pipeline: {csv_path}")
        
        # Load data
        df = pd.read_csv(csv_path)
        df['timestamp_dt'] = pd.to_datetime(df['timestamp'], errors='coerce')
        recent_df = df[df['timestamp_dt'] >= self.cutoff_date]
        
        logger.info(f"📊 Processing {len(recent_df):,} messages from last {self.cutoff_days} days")
        
        # Process through regex pipeline
        results = []
        buckets = {bucket.value: [] for bucket in BucketType}
        
        for idx, row in recent_df.iterrows():
            sms_text = str(row.get('sms_body', ''))
            sender = str(row.get('sender', ''))
            timestamp = str(row.get('timestamp', ''))
            
            # Parse with regex
            transaction = self.parse_sms(sms_text, sender, timestamp)
            
            # Add to appropriate bucket
            buckets[transaction.bucket.value].append(transaction)
            
            if len(results) % 1000 == 0 and len(results) > 0:
                logger.info(f"Processed {len(results):,} messages...")
            
            results.append(transaction)
        
        logger.info("📈 Initial Classification Complete:")
        for bucket, transactions in buckets.items():
            logger.info(f"  {bucket}: {len(transactions):,}")
        
        # Deduplication on Ready and Ambiguous
        logger.info("🔄 Starting Deduplication...")
        
        ready_unique = []
        ambiguous_unique = []
        duplicates_removed = []
        
        # Deduplicate Ready transactions
        for txn in buckets['ready']:
            is_dup, reason = self.deduplicator.is_duplicate(txn)
            if is_dup:
                txn.is_duplicate = True
                txn.duplicate_reason = reason
                duplicates_removed.append(txn)
            else:
                ready_unique.append(txn)
        
        # Deduplicate Ambiguous transactions
        for txn in buckets['ambiguous']:
            is_dup, reason = self.deduplicator.is_duplicate(txn)
            if is_dup:
                txn.is_duplicate = True
                txn.duplicate_reason = reason
                duplicates_removed.append(txn)
            else:
                ambiguous_unique.append(txn)
        
        # Compile final results
        final_results = {
            'ready_unique': ready_unique,
            'ambiguous_unique': ambiguous_unique,
            'rejected': buckets['rejected'],
            'failed': buckets['failed'],
            'investment': buckets['investment'],
            'duplicates_removed': duplicates_removed,
            'dedup_stats': self.deduplicator.get_stats()
        }
        
        logger.info("✅ Deduplication Complete:")
        logger.info(f"  Ready (unique): {len(ready_unique):,}")
        logger.info(f"  Ambiguous (unique): {len(ambiguous_unique):,}")
        logger.info(f"  Duplicates removed: {len(duplicates_removed):,}")
        
        return final_results
    
    def save_results(self, results: Dict, base_name: str = "final"):
        """Save all results to CSV files"""
        
        logger.info("💾 Saving Results to CSV...")
        
        # Convert to DataFrames and save
        files_created = []
        
        for category, transactions in results.items():
            if category == 'dedup_stats':
                continue
                
            if transactions:
                df = pd.DataFrame([asdict(txn) for txn in transactions])
                filename = f"{base_name}_{category}.csv"
                df.to_csv(filename, index=False)
                files_created.append((filename, len(transactions)))
                logger.info(f"  ✅ {filename}: {len(transactions):,} records")
        
        return files_created

def simulate_llm_processing(ambiguous_transactions: List[ParsedTransaction]) -> List[ParsedTransaction]:
    """
    Simulate LLM processing on ambiguous transactions
    In production, this would call Gemini API
    """
    logger.info(f"🧠 Simulating LLM processing on {len(ambiguous_transactions):,} transactions...")
    
    processed = []
    for txn in ambiguous_transactions:
        # Simulate LLM analysis
        if txn.amount and txn.amount > 0:
            # LLM would determine transaction type if missing
            if not txn.txn_type:
                # Simple heuristic for simulation
                if any(word in txn.original_sms.lower() for word in ['debit', 'spent', 'paid']):
                    txn.txn_type = TransactionType.DEBIT
                else:
                    txn.txn_type = TransactionType.CREDIT
            
            # Upgrade to ready if now has required fields
            if txn.txn_type and txn.amount:
                txn.bucket = BucketType.BANK_LEDGER_SUCCESS
                txn.confidence_score = min(txn.confidence_score + 20, 100)
        
        processed.append(txn)
    
    logger.info(f"✅ LLM processing complete")
    return processed

def main():
    """Run the complete SMS pipeline"""
    
    print("🚀 COMPLETE SMS FINANCIAL TRANSACTION PIPELINE")
    print("=" * 60)
    print()
    
    # Configuration
    CSV_PATH = "sms_data_from_raw.csv"
    
    if not os.path.exists(CSV_PATH):
        logger.error(f"❌ CSV file not found: {CSV_PATH}")
        return
    
    # Initialize pipeline
    pipeline = EnhancedSMSPipeline(cutoff_days=10000)
    
    # Process with deduplication
    start_time = time.time()
    results = pipeline.process_with_deduplication(CSV_PATH)
    processing_time = time.time() - start_time
    
    # Simulate LLM processing on unique ambiguous transactions
    if results['ambiguous_unique']:
        llm_processed = simulate_llm_processing(results['ambiguous_unique'])
        
        # Separate LLM results into ready and still ambiguous
        llm_ready = [txn for txn in llm_processed if txn.bucket == BucketType.BANK_LEDGER_SUCCESS]
        llm_ambiguous = [txn for txn in llm_processed if txn.bucket == BucketType.AMBIGUOUS]
        
        # Combine with original ready transactions
        results['final_ready'] = results['ready_unique'] + llm_ready
        results['final_ambiguous'] = llm_ambiguous
    else:
        results['final_ready'] = results['ready_unique']
        results['final_ambiguous'] = []
    
    # Save all results
    files_created = pipeline.save_results(results)
    
    # Final summary
    print("\n🎯 FINAL PIPELINE RESULTS:")
    print("=" * 35)
    
    total_transactions = (len(results['final_ready']) + 
                         len(results['final_ambiguous']) + 
                         len(results['rejected']) + 
                         len(results['failed']) + 
                         len(results['investment']) + 
                         len(results['duplicates_removed']))
    
    print(f"📊 Total Messages Processed: {total_transactions:,}")
    print(f"⏱️  Processing Time: {processing_time:.1f} seconds")
    print()
    
    print("📈 FINAL CLASSIFICATION:")
    print(f"  ✅ Ready for Ledger: {len(results['final_ready']):,} ({len(results['final_ready'])/total_transactions*100:.1f}%)")
    print(f"  🤖 Still Ambiguous: {len(results['final_ambiguous']):,} ({len(results['final_ambiguous'])/total_transactions*100:.1f}%)")
    print(f"  ❌ Rejected: {len(results['rejected']):,} ({len(results['rejected'])/total_transactions*100:.1f}%)")
    print(f"  ⚠️  Failed: {len(results['failed']):,} ({len(results['failed'])/total_transactions*100:.1f}%)")
    print(f"  💼 Investment: {len(results['investment']):,} ({len(results['investment'])/total_transactions*100:.1f}%)")
    print(f"  🔄 Duplicates Removed: {len(results['duplicates_removed']):,} ({len(results['duplicates_removed'])/total_transactions*100:.1f}%)")
    
    print("\n🔄 DEDUPLICATION STATISTICS:")
    stats = results['dedup_stats']
    print(f"  Total Processed: {stats['total_processed']:,}")
    print(f"  Unique Transactions: {stats['unique_transactions']:,}")
    print(f"  ref_id Duplicates: {stats['ref_id_duplicates']:,}")
    print(f"  Composite Key Duplicates: {stats['composite_duplicates']:,}")
    print(f"  Content Hash Duplicates: {stats['content_duplicates']:,}")
    print(f"  Deduplication Rate: {((stats['total_processed'] - stats['unique_transactions'])/stats['total_processed']*100):.1f}%")
    
    print("\n💰 FINANCIAL SUMMARY:")
    ready_with_amounts = [txn for txn in results['final_ready'] if txn.amount]
    if ready_with_amounts:
        total_value = sum(txn.amount for txn in ready_with_amounts)
        avg_value = total_value / len(ready_with_amounts)
        print(f"  Total Transaction Value: ₹{total_value:,.2f}")
        print(f"  Average Transaction: ₹{avg_value:,.2f}")
        
        debits = [txn for txn in ready_with_amounts if txn.txn_type == TransactionType.DEBIT]
        credits = [txn for txn in ready_with_amounts if txn.txn_type == TransactionType.CREDIT]
        
        if debits:
            debit_total = sum(txn.amount for txn in debits)
            print(f"  Total Debits: ₹{debit_total:,.2f} ({len(debits):,} transactions)")
        
        if credits:
            credit_total = sum(txn.amount for txn in credits)
            print(f"  Total Credits: ₹{credit_total:,.2f} ({len(credits):,} transactions)")
    
    print("\n📁 FILES CREATED:")
    for filename, count in files_created:
        print(f"  📄 {filename}: {count:,} records")
    
    print("\n✅ COMPLETE PIPELINE FINISHED!")
    print(f"🎯 Final Ready Transactions: {len(results['final_ready']):,}")
    print(f"🔄 Duplicates Eliminated: {len(results['duplicates_removed']):,}")
    print(f"💰 Cost Savings: {len(results['duplicates_removed'])} fewer LLM calls needed")

if __name__ == "__main__":
    main()
