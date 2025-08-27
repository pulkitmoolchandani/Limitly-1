#!/usr/bin/env python3
"""
Test Credit and Debit Transaction Parsing
Quick test to demonstrate the enhanced parsing for both debit and credit transactions
"""

from sms_parser import GeminiSMSParser
import pandas as pd

def test_credit_debit_parsing():
    """Test the enhanced parser with both credit and debit SMS examples"""
    
    API_KEY = "AIzaSyArZpN-ZVmhAR3emZN9P5p2Y_hjEn8h97Q"
    
    # Sample SMS messages with both credit and debit transactions
    test_messages = [
        # Debit transactions
        "YES BANK Ac X1505 debited for INR 375.90 on 26AUG25 20:45. UPI:560315589355/To:ZOMATO. Bal INR 3,915.66",
        "Spent Rs.250.00 On HDFC Bank Card 5279 At AMAZON INDIA On 2025-08-25:15:30:20",
        "Alert! Your AU Bank A/c No. X9135 has been Debited with INR 100.00 on 25-AUG-2025 for ATM Withdrawal",
        
        # Credit transactions
        "Credited INR 5,000.00 to A/c X9135 on 25-AUG-2025 Ref UPI/CR/560298765432/SALARY DEPOSIT - COMPANY ABC",
        "INR 50.00 credited to your SBI A/c XX1234 on 26-AUG-25. UPI Ref: 560401234567. From: GOOGLE PAY CASHBACK",
        "Rs.1500 credited to your HDFC Bank A/c ending 4567 on 24-Aug-2025. Interest Credit for Q2-2025",
        "Amount Rs.200.00 credited to A/c XX9876 via UPI from FRIEND_NAME@okaxis on 23-AUG-2025",
        
        # Non-transactions (should be filtered out)
        "Your OTP for UPI transaction is 123456. Do not share with anyone",
        "Your account balance is Rs 15,430.50 as on 26-Aug-2025"
    ]
    
    try:
        print("🧪 Testing Enhanced Credit/Debit Transaction Parsing")
        print("=" * 60)
        
        parser = GeminiSMSParser(API_KEY)
        results = []
        
        for i, sms in enumerate(test_messages, 1):
            print(f"\n{i}. Processing: {sms[:60]}...")
            
            transaction = parser.parse_sms(sms)
            
            if transaction:
                results.append({
                    'amount': transaction.amount,
                    'merchant': transaction.merchant,
                    'date': transaction.date,
                    'category': transaction.category,
                    'transaction_type': transaction.transaction_type,
                    'ref_id': transaction.ref_id,
                    'bank': transaction.bank,
                    'payment_method': transaction.payment_method,
                    'original_sms': sms[:80] + '...' if len(sms) > 80 else sms
                })
                
                type_symbol = "💸" if transaction.transaction_type == "debit" else "💰"
                print(f"   {type_symbol} {transaction.transaction_type.upper()}: ₹{transaction.amount} at {transaction.merchant}")
                print(f"      Category: {transaction.category} | Ref: {transaction.ref_id}")
            else:
                print(f"   ❌ Not a transaction (filtered out)")
        
        print(f"\n📊 PARSING RESULTS:")
        print("=" * 60)
        
        if results:
            df = pd.DataFrame(results)
            
            # Summary statistics
            debits = df[df['transaction_type'] == 'debit']
            credits = df[df['transaction_type'] == 'credit']
            
            print(f"Total Transactions Parsed: {len(df)}")
            print(f"Debit Transactions: {len(debits)} (Total: ₹{debits['amount'].sum():,.2f})")
            print(f"Credit Transactions: {len(credits)} (Total: ₹{credits['amount'].sum():,.2f})")
            print(f"Net Amount: ₹{credits['amount'].sum() - debits['amount'].sum():,.2f}")
            
            print(f"\n📋 Transaction Breakdown:")
            print("-" * 60)
            
            for i, row in df.iterrows():
                type_icon = "💸" if row['transaction_type'] == 'debit' else "💰"
                print(f"{type_icon} {row['transaction_type'].upper()}: ₹{row['amount']}")
                print(f"   Merchant: {row['merchant']}")
                print(f"   Category: {row['category']}")
                print(f"   Bank: {row['bank']}")
                print(f"   Ref ID: {row['ref_id']}")
                print(f"   SMS: {row['original_sms']}")
                print()
            
            # Save results
            df.to_csv('credit_debit_test_results.csv', index=False)
            print(f"💾 Results saved to: credit_debit_test_results.csv")
            
        else:
            print("❌ No transactions were successfully parsed")
        
        print(f"\n🎉 Enhanced parsing test completed!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_credit_debit_parsing()
