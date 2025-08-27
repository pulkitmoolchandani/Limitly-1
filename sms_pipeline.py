#!/usr/bin/env python3
"""
SMS Financial Transaction Pipeline
Comprehensive deterministic filtering + LLM fallback system
"""

import pandas as pd
import re
import sqlite3
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, asdict
from enum import Enum
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BucketType(Enum):
    BANK_LEDGER_SUCCESS = "bank_ledger_success"
    BANK_LEDGER_FAILED = "bank_ledger_failed"
    INVESTMENT_OR_REMINDER = "investment_or_reminder"
    AMBIGUOUS = "ambiguous"
    REJECTED = "rejected"

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
    penalties: List[str] = None
    signals: List[str] = None
    
    def __post_init__(self):
        if self.penalties is None:
            self.penalties = []
        if self.signals is None:
            self.signals = []

class DeterministicParser:
    """Deterministic SMS parser with confidence scoring"""
    
    def __init__(self):
        self.patterns = self._init_patterns()
        
    def _init_patterns(self) -> Dict:
        """Initialize regex patterns for extraction"""
        return {
            # Amount patterns - Enhanced for INR/Rupees
            'amount': [
                r'(?:INR|Rs\.?|₹|Rupees?)\s*([0-9,]+(?:\.\d{1,2})?)',
                r'Amount[:\s]*(?:INR|Rs\.?|₹|Rupees?)?\s*([0-9,]+(?:\.\d{1,2})?)',
                r'(?:debited|credited|spent|received|paid)\s+(?:INR|Rs\.?|₹|Rupees?)?\s*([0-9,]+(?:\.\d{1,2})?)',
                r'([0-9,]+(?:\.\d{1,2})?)\s*(?:INR|Rs\.?|₹|Rupees?)',
                r'(?:for|of)\s+(?:INR|Rs\.?|₹|Rupees?)\s*([0-9,]+(?:\.\d{1,2})?)',
            ],
            
            # Transaction type patterns
            'debit_verbs': [
                r'\b(?:debited|spent|charged|withdrawn|paid|purchase|deducted|debit)\b',
                r'\b(?:ATM|POS)\s+(?:withdrawal|transaction)\b',
                r'\b(?:bill\s+payment|online\s+payment)\b'
            ],
            'credit_verbs': [
                r'\b(?:credited|received|deposited|refund|cashback|interest)\b',
                r'\b(?:salary|bonus|dividend|transfer\s+credit)\b'
            ],
            
            # Rail detection
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
            
            # Balance patterns
            'balance': [
                r'(?:Avl\s+Bal|Available\s+Balance|Balance)[:\s]*(?:INR|Rs\.?|₹)?\s*([0-9,]+(?:\.\d{1,2})?)',
                r'Bal[:\s]*(?:INR|Rs\.?|₹)?\s*([0-9,]+(?:\.\d{1,2})?)'
            ],
            
            # Reference ID patterns
            'ref_id': [
                r'UPI[:/](\w+)',
                r'Ref[:\s]*(\w+)',
                r'TXN[:\s]*(\w+)',
                r'Transaction\s+ID[:\s]*(\w+)',
                r'(\d{12,})'  # Long numbers
            ],
            
            # Card last 4 digits
            'card_last4': [
                r'Card\s+ending\s+(\d{4})',
                r'XX(\d{4})',
                r'ending\s+(\d{4})'
            ],
            
            # UPI VPA patterns
            'upi_vpa': [
                r'([a-zA-Z0-9._-]+@[a-zA-Z0-9.-]+)',
                r'To[:/]\s*([a-zA-Z0-9._-]+@\w+)',
                r'From[:/]\s*([a-zA-Z0-9._-]+@\w+)'
            ],
            
            # Merchant patterns
            'merchant': [
                r'\bat\s+([A-Z0-9 &\-\.]{2,})',
                r'\bto\s+([A-Z0-9 &\-\.]{2,})',
                r'\bvia\s+([A-Z0-9 &\-\.]{2,})',
                r'\bfrom\s+([A-Z0-9 &\-\.]{2,})'
            ],
            
            # Bank patterns
            'banks': [
                r'\b(SBI|HDFC|ICICI|AXIS|KOTAK|PNB|BOB|CANARA|UNION|INDUSIND|YES|IDFC)\s*BANK\b',
                r'\b(HDFC|ICICI|AXIS|KOTAK|YES|IDFC)\b'
            ],
            
            # Date patterns
            'date': [
                r'(\d{2}[-/]\w{3}[-/]\d{4})',
                r'(\d{2}[-/]\d{2}[-/]\d{4})',
                r'(\d{2}\s+\w{3}\s+\d{4})'
            ],
            
            # Penalty patterns (reduce confidence)
            'penalties': {
                'future_tense': [r'\bwill\s+be\s+debited\b', r'\bwill\s+be\s+charged\b'],
                'sip_amc': [r'\b(?:SIP|folio|NAV|units|CAMS|KFintech|AMC|MF)\b'],
                'failed': [r'\b(?:failed|declined|rejected|insufficient|blocked)\b'],
                'otp': [r'\b(?:OTP|verification\s+code|PIN)\b'],
                'balance_enquiry': [r'\b(?:balance\s+enquiry|mini\s+statement)\b'],
                'maintenance': [r'\b(?:maintenance|service|update|KYC)\b'],
                'no_numbers': [r'^[^\d]*$']  # Messages with no numbers
            },
            
            # Signal patterns (increase confidence)
            'signals': {
                'executed_verbs': [r'\b(?:debited|credited|spent|received|paid|charged|withdrawn)\b'],
                'amount_present': [r'(?:INR|Rs\.?|₹)\s*[0-9,]+'],
                'account_cue': [r'\bA/c\s+(?:No\.?\s*)?[XX]*\d{4}\b'],
                'rail_cue': [r'\b(?:UPI|IMPS|NEFT|RTGS|Card|ATM|POS)\b'],
                'ref_id_present': [r'(?:Ref|TXN|UPI)[:/]\s*\w+'],
                'balance_cue': [r'(?:Avl\s+Bal|Balance)[:\s]*(?:INR|Rs\.?|₹)?\s*[0-9,]+']
            }
        }
    
    def parse(self, sms_text: str, sender: str = "", timestamp: str = "") -> ParsedTransaction:
        """Parse SMS with deterministic rules and confidence scoring"""
        
        # Early rejection: No numbers in message
        if not re.search(r'\d', sms_text):
            return ParsedTransaction(
                original_sms=sms_text,
                sender=sender,
                timestamp=timestamp,
                raw_hash=hashlib.md5(sms_text.encode()).hexdigest()[:16],
                confidence_score=0.0,
                bucket=BucketType.REJECTED,
                penalties=['no_numbers']
            )
        
        transaction = ParsedTransaction(
            original_sms=sms_text,
            sender=sender,
            timestamp=timestamp,
            raw_hash=hashlib.md5(sms_text.encode()).hexdigest()[:16]
        )
        
        # Extract basic fields
        transaction.amount = self._extract_amount(sms_text)
        transaction.txn_type = self._extract_transaction_type(sms_text)
        transaction.rail = self._extract_rail(sms_text)
        transaction.balance = self._extract_balance(sms_text)
        transaction.ref_id = self._extract_ref_id(sms_text)
        transaction.card_last4 = self._extract_card_last4(sms_text)
        transaction.upi_vpa = self._extract_upi_vpa(sms_text)
        transaction.merchant = self._extract_merchant(sms_text)
        transaction.date = self._extract_date(sms_text, timestamp)
        transaction.bank = self._extract_bank(sms_text, sender)
        
        # Calculate confidence and apply penalties/signals
        transaction.confidence_score = self._calculate_confidence(sms_text, transaction)
        
        # Determine bucket
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
        """Determine transaction type (debit/credit)"""
        text_lower = text.lower()
        
        # Check for credit verbs
        for pattern in self.patterns['credit_verbs']:
            if re.search(pattern, text_lower):
                return TransactionType.CREDIT
        
        # Check for debit verbs
        for pattern in self.patterns['debit_verbs']:
            if re.search(pattern, text_lower):
                return TransactionType.DEBIT
        
        return None
    
    def _extract_rail(self, text: str) -> Optional[Rail]:
        """Extract payment rail/method"""
        text_upper = text.upper()
        
        for rail, patterns in self.patterns['rails'].items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    return rail
        
        return Rail.UNKNOWN
    
    def _extract_balance(self, text: str) -> Optional[float]:
        """Extract account balance"""
        for pattern in self.patterns['balance']:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                balance_str = match.group(1).replace(',', '')
                try:
                    return float(balance_str)
                except ValueError:
                    continue
        return None
    
    def _extract_ref_id(self, text: str) -> Optional[str]:
        """Extract reference ID"""
        for pattern in self.patterns['ref_id']:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        return None
    
    def _extract_card_last4(self, text: str) -> Optional[str]:
        """Extract card last 4 digits"""
        for pattern in self.patterns['card_last4']:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        return None
    
    def _extract_upi_vpa(self, text: str) -> Optional[str]:
        """Extract UPI VPA"""
        for pattern in self.patterns['upi_vpa']:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        return None
    
    def _extract_merchant(self, text: str) -> Optional[str]:
        """Extract merchant name"""
        for pattern in self.patterns['merchant']:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                merchant = match.group(1).strip()
                # Clean up merchant name
                merchant = re.sub(r'\s+', ' ', merchant)
                return merchant
        return None
    
    def _extract_bank(self, text: str, sender: str = "") -> Optional[str]:
        """Extract bank name"""
        # Try sender first
        if sender:
            for pattern in self.patterns['banks']:
                match = re.search(pattern, sender, re.IGNORECASE)
                if match:
                    return match.group(1)
        
        # Try SMS text
        for pattern in self.patterns['banks']:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    def _extract_date(self, text: str, timestamp: str = "") -> Optional[str]:
        """Extract transaction date"""
        for pattern in self.patterns['date']:
            match = re.search(pattern, text)
            if match:
                date_str = match.group(1)
                # Try to parse and standardize
                try:
                    # Handle different date formats
                    for fmt in ['%d-%b-%Y', '%d/%b/%Y', '%d %b %Y', '%d-%m-%Y', '%d/%m/%Y']:
                        try:
                            parsed_date = datetime.strptime(date_str, fmt)
                            return parsed_date.strftime('%Y-%m-%d')
                        except ValueError:
                            continue
                except:
                    pass
        
        # Fallback to timestamp if provided
        if timestamp:
            try:
                parsed_ts = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                return parsed_ts.strftime('%Y-%m-%d')
            except:
                pass
        
        # Default to today
        return datetime.now().strftime('%Y-%m-%d')
    
    def _calculate_confidence(self, text: str, transaction: ParsedTransaction) -> float:
        """Calculate confidence score based on signals and penalties"""
        score = 0.0
        text_lower = text.lower()
        
        # Base signals (positive score)
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
                    elif signal_type in ['ref_id_present', 'balance_cue']:
                        score += 10
        
        # Field presence bonuses
        if transaction.amount is not None:
            score += 20
        if transaction.txn_type is not None:
            score += 15
        if transaction.rail != Rail.UNKNOWN:
            score += 10
        if transaction.ref_id:
            score += 10
        if transaction.balance is not None:
            score += 5
        
        # Penalties (negative score)
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
        
        # Normalize to 0-100
        score = max(0, min(100, score))
        return score
    
    def _determine_bucket(self, transaction: ParsedTransaction) -> BucketType:
        """Determine bucket based on confidence and content"""
        
        # Hard rejections
        if any(penalty in ['otp', 'balance_enquiry', 'maintenance', 'no_numbers'] for penalty in transaction.penalties):
            return BucketType.REJECTED
        
        # Investment/SIP transactions
        if any(penalty == 'sip_amc' for penalty in transaction.penalties):
            return BucketType.INVESTMENT_OR_REMINDER
        
        # Failed transactions
        if any(penalty == 'failed' for penalty in transaction.penalties):
            return BucketType.BANK_LEDGER_FAILED
        
        # High confidence transactions
        if transaction.confidence_score >= 70 and transaction.amount is not None and transaction.txn_type is not None:
            return BucketType.BANK_LEDGER_SUCCESS
        
        # Low confidence - needs LLM
        if transaction.confidence_score < 40:
            return BucketType.AMBIGUOUS
        
        # Medium confidence with missing critical fields
        if transaction.amount is None or transaction.txn_type is None:
            return BucketType.AMBIGUOUS
        
        return BucketType.BANK_LEDGER_SUCCESS

class SMSPipeline:
    """Main SMS processing pipeline"""
    
    def __init__(self, cutoff_days: int = 90):
        self.cutoff_days = cutoff_days
        self.parser = DeterministicParser()
        self.cutoff_date = datetime.now() - timedelta(days=cutoff_days)
        
    def process_csv(self, csv_path: str, output_path: str = "sms_pipeline_results.csv") -> pd.DataFrame:
        """Process SMS CSV through the complete pipeline"""
        
        logger.info(f"Loading SMS data from {csv_path}")
        df = pd.read_csv(csv_path)
        
        # Filter to last N days
        df['timestamp_dt'] = pd.to_datetime(df['timestamp'], errors='coerce')
        recent_df = df[df['timestamp_dt'] >= self.cutoff_date]
        
        logger.info(f"Filtered to {len(recent_df):,} messages from last {self.cutoff_days} days")
        
        results = []
        
        for idx, row in recent_df.iterrows():
            sms_text = str(row.get('sms_body', ''))
            sender = str(row.get('sender', ''))
            timestamp = str(row.get('timestamp', ''))
            
            # Parse with deterministic rules
            transaction = self.parser.parse(sms_text, sender, timestamp)
            
            # Convert to dict for CSV
            result = asdict(transaction)
            result['original_row_id'] = idx
            
            results.append(result)
            
            if len(results) % 1000 == 0:
                logger.info(f"Processed {len(results):,} messages...")
        
        # Create results DataFrame
        results_df = pd.DataFrame(results)
        
        # Add summary stats
        bucket_counts = results_df['bucket'].value_counts()
        
        logger.info("Pipeline Results:")
        for bucket, count in bucket_counts.items():
            percentage = (count / len(results_df)) * 100
            logger.info(f"  {bucket}: {count:,} ({percentage:.1f}%)")
        
        # Save results
        results_df.to_csv(output_path, index=False)
        logger.info(f"Results saved to {output_path}")
        
        return results_df
    
    def get_llm_candidates(self, results_df: pd.DataFrame) -> pd.DataFrame:
        """Get messages that need LLM processing"""
        return results_df[results_df['bucket'] == BucketType.AMBIGUOUS.value]
    
    def get_transactions(self, results_df: pd.DataFrame) -> pd.DataFrame:
        """Get successful transactions for ledger"""
        return results_df[results_df['bucket'] == BucketType.BANK_LEDGER_SUCCESS.value]

def main():
    """Run the SMS pipeline"""
    
    # Configuration
    CSV_PATH = "sms_data_from_raw.csv"
    OUTPUT_PATH = "sms_pipeline_results.csv"
    CUTOFF_DAYS = 90
    
    try:
        # Initialize pipeline
        pipeline = SMSPipeline(cutoff_days=CUTOFF_DAYS)
        
        # Process all SMS
        results_df = pipeline.process_csv(CSV_PATH, OUTPUT_PATH)
        
        # Get LLM candidates
        llm_candidates = pipeline.get_llm_candidates(results_df)
        logger.info(f"Messages needing LLM processing: {len(llm_candidates):,}")
        
        if len(llm_candidates) > 0:
            llm_candidates.to_csv("llm_candidates.csv", index=False)
            logger.info("LLM candidates saved to llm_candidates.csv")
        
        # Get successful transactions
        transactions = pipeline.get_transactions(results_df)
        logger.info(f"Ready for ledger: {len(transactions):,} transactions")
        
        if len(transactions) > 0:
            transactions.to_csv("ready_transactions.csv", index=False)
            logger.info("Ready transactions saved to ready_transactions.csv")
        
        # Summary statistics
        logger.info("\nPipeline Summary:")
        logger.info(f"Total messages processed: {len(results_df):,}")
        logger.info(f"Confidence >= 70%: {len(results_df[results_df['confidence_score'] >= 70]):,}")
        logger.info(f"Needs LLM processing: {len(llm_candidates):,}")
        logger.info(f"Ready for ledger: {len(transactions):,}")
        
    except Exception as e:
        logger.error(f"Pipeline error: {e}")
        raise

if __name__ == "__main__":
    main()
