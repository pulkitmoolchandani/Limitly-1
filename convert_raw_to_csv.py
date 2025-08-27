#!/usr/bin/env python3
"""
Convert SMS Raw Data to CSV
Converts sms_raw.txt format where each SMS starts with "Row: X" to CSV format
"""

import csv
import re
from datetime import datetime
from typing import List, Dict

def parse_sms_raw_file(filename: str) -> List[Dict]:
    """Parse the raw SMS file where each message starts with 'Row: X'"""
    
    sms_messages = []
    current_message = None
    
    print(f"📄 Reading {filename}...")
    
    with open(filename, 'r', encoding='utf-8', errors='ignore') as file:
        for line_num, line in enumerate(file, 1):
            line = line.strip()
            
            # Skip empty lines
            if not line:
                continue
            
            # Check if this line starts a new SMS message
            row_match = re.match(r'Row:\s*(\d+)\s+_id=(\d+),\s*address=([^,]+),\s*date=(\d+),\s*read=(\d+),\s*type=(\d+),\s*body=(.+)', line)
            
            if row_match:
                # Save previous message if it exists
                if current_message:
                    sms_messages.append(current_message)
                
                # Start new message
                row_id = int(row_match.group(1))
                message_id = row_match.group(2)
                address = row_match.group(3)
                timestamp = int(row_match.group(4))
                read_status = row_match.group(5)
                message_type = row_match.group(6)
                body = row_match.group(7)
                
                # Convert timestamp from milliseconds to readable format
                try:
                    readable_date = datetime.fromtimestamp(timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S')
                except:
                    readable_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                current_message = {
                    'id': row_id,
                    'message_id': message_id,
                    'sender': address,
                    'timestamp': readable_date,
                    'sms_body': body,
                    'read_status': read_status,
                    'message_type': message_type
                }
                
            else:
                # This line is a continuation of the current message body
                if current_message:
                    current_message['sms_body'] += ' ' + line
            
            # Progress indicator
            if line_num % 10000 == 0:
                print(f"   Processed {line_num:,} lines...")
        
        # Don't forget the last message
        if current_message:
            sms_messages.append(current_message)
    
    print(f"✅ Parsed {len(sms_messages):,} SMS messages")
    return sms_messages

def clean_sms_body(body: str) -> str:
    """Clean the SMS body text"""
    # Remove extra whitespace
    body = ' '.join(body.split())
    
    # Remove common unwanted patterns
    body = re.sub(r'\s+', ' ', body)  # Multiple spaces to single space
    body = body.strip()
    
    return body

def save_to_csv(sms_messages: List[Dict], output_filename: str = 'sms_data_from_raw.csv'):
    """Save SMS messages to CSV format"""
    
    print(f"💾 Saving to {output_filename}...")
    
    # Clean the SMS bodies
    for msg in sms_messages:
        msg['sms_body'] = clean_sms_body(msg['sms_body'])
    
    # Filter out very short or empty messages
    filtered_messages = [msg for msg in sms_messages if len(msg['sms_body']) > 10]
    
    print(f"📝 Filtered to {len(filtered_messages):,} messages (removed {len(sms_messages) - len(filtered_messages):,} short/empty messages)")
    
    with open(output_filename, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['id', 'sms_body', 'sender', 'timestamp', 'message_id', 'read_status', 'message_type']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        for msg in filtered_messages:
            writer.writerow(msg)
    
    print(f"✅ CSV file saved with {len(filtered_messages):,} messages")
    return output_filename

def analyze_sms_data(sms_messages: List[Dict]):
    """Provide basic analysis of the SMS data"""
    
    print("\n📊 SMS Data Analysis:")
    print("=" * 50)
    
    # Basic stats
    print(f"Total Messages: {len(sms_messages):,}")
    
    # Sender analysis
    senders = {}
    for msg in sms_messages:
        sender = msg['sender']
        senders[sender] = senders.get(sender, 0) + 1
    
    print(f"\nTop 10 Senders:")
    sorted_senders = sorted(senders.items(), key=lambda x: x[1], reverse=True)
    for i, (sender, count) in enumerate(sorted_senders[:10], 1):
        print(f"  {i:2}. {sender:<25}: {count:,} messages")
    
    # Look for potential financial SMS
    financial_keywords = ['debited', 'credited', 'transaction', 'payment', 'bank', 'card', 'upi', 'rs.', 'rs ', 'inr', 'balance', 'avl bal']
    financial_count = 0
    
    for msg in sms_messages:
        body_lower = msg['sms_body'].lower()
        if any(keyword in body_lower for keyword in financial_keywords):
            financial_count += 1
    
    print(f"\nPotential Financial SMS: {financial_count:,} ({financial_count/len(sms_messages)*100:.1f}%)")
    
    # Date range
    dates = []
    for msg in sms_messages:
        try:
            date_obj = datetime.strptime(msg['timestamp'], '%Y-%m-%d %H:%M:%S')
            dates.append(date_obj)
        except:
            pass
    
    if dates:
        min_date = min(dates)
        max_date = max(dates)
        print(f"Date Range: {min_date.strftime('%Y-%m-%d')} to {max_date.strftime('%Y-%m-%d')}")
    
    print("=" * 50)

def main():
    """Main function"""
    input_file = 'sms_raw.txt'
    output_file = 'sms_data_from_raw.csv'
    
    try:
        # Parse the raw SMS file
        sms_messages = parse_sms_raw_file(input_file)
        
        if not sms_messages:
            print("❌ No SMS messages found in the file")
            return
        
        # Analyze the data
        analyze_sms_data(sms_messages)
        
        # Save to CSV
        csv_file = save_to_csv(sms_messages, output_file)
        
        print(f"\n🎉 Conversion completed successfully!")
        print(f"📁 Output file: {csv_file}")
        print(f"📊 Ready for SMS parsing with sms_parser.py")
        
        # Show a few sample messages
        print(f"\n📋 Sample Messages:")
        for i, msg in enumerate(sms_messages[:5], 1):
            print(f"\n{i}. From: {msg['sender']}")
            print(f"   Date: {msg['timestamp']}")
            print(f"   Body: {msg['sms_body'][:100]}{'...' if len(msg['sms_body']) > 100 else ''}")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()