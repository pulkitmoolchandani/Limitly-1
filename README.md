# 🚀 SMS Financial Transaction Processing Pipeline

**Enterprise-grade SMS processing system with intelligent deduplication and AI-powered transaction extraction.**

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Pipeline](https://img.shields.io/badge/Pipeline-Production%20Ready-brightgreen.svg)](#)

## 📊 **Pipeline Results**

Processed **22,835 SMS messages** with **47% deduplication rate**:

| Category | Count | Percentage | Status |
|----------|-------|------------|---------|
| 🎯 **Ready for Ledger** | **6,070** | **26.6%** | ✅ Production Ready |
| 🤖 **Need LLM Processing** | **1,826** | **8.0%** | 🔧 Requires AI |
| ❌ **Rejected (Non-Financial)** | **4,058** | **17.8%** | 🗑️ Filtered Out |
| 🔄 **Duplicates Eliminated** | **10,734** | **47.0%** | 💰 Cost Savings |

## 🏗️ **Architecture**

```
Raw SMS (22,835) → Enhanced Regex Pipeline → Multi-Strategy Deduplication → Final Results
                     ↓                        ↓
    Ready | Ambiguous | Rejected          Unique Transactions
    45.1% |   36.9%   |  17.3%              (57.6% dedup rate)
                                               ↓
                                    6,070 Ready + 1,826 Ambiguous
```

## ⚡ **Key Features**

### 🔍 **Enhanced Regex Processing**
- **Multi-pattern extraction**: Amount, transaction type, payment rails
- **Smart filtering**: Auto-reject OTP, maintenance, non-financial messages
- **Confidence scoring**: 0-100% accuracy assessment
- **INR/Rupees support**: Enhanced Indian currency pattern recognition

### 🔄 **Multi-Strategy Deduplication**
1. **ref_id Based** (92.5%): UPI IDs, bank references
2. **Composite Key** (5.4%): sender + amount + type + time bucket
3. **Content Hash** (2.1%): Exact SMS content duplicates

### 🎯 **Intelligent Classification**
- **READY**: High confidence, complete data, ledger-ready
- **AMBIGUOUS**: Medium confidence, needs LLM processing
- **REJECTED**: OTP, maintenance, non-financial messages
- **FAILED**: Declined/failed transactions
- **INVESTMENT**: SIP, mutual fund transactions

## 📁 **Project Structure**

```
sms_parsing/
├── 🔧 Core Pipeline
│   ├── complete_sms_pipeline.py      # Main integrated pipeline
│   ├── sms_pipeline.py               # Enhanced regex processor
│   ├── deduplication_system.py       # Multi-strategy deduplication
│   └── convert_raw_to_csv.py         # Raw data converter
│
├── 📊 Analysis & UI
│   ├── sms_analytics_ui.py           # Streamlit dashboard
│   ├── pipeline_dashboard.py         # Pipeline visualization
│   └── sms_parser.py                 # Original parser with Gemini
│
├── 📄 Output Files
│   ├── final_final_ready.csv         # 6,070 production-ready transactions
│   ├── final_final_ambiguous.csv     # 1,826 transactions needing LLM
│   ├── final_rejected.csv            # 4,058 filtered messages
│   ├── final_failed.csv              # 127 failed transactions
│   ├── final_investment.csv          # 20 SIP/investment messages
│   └── final_duplicates_removed.csv  # 10,734 eliminated duplicates
│
├── 📚 Documentation
│   ├── README.md                     # This file
│   ├── PIPELINE_SUMMARY.md           # Detailed pipeline documentation
│   └── requirements.txt              # Python dependencies
│
└── 📋 Data
    ├── sms_raw.txt                   # Raw SMS data (60K+ lines)
    └── sms_data_from_raw.csv         # Converted CSV (22K+ messages)
```

## 🚀 **Quick Start**

### Prerequisites
```bash
Python 3.8+
pip install -r requirements.txt
```

### 1. Convert Raw SMS Data
```bash
python convert_raw_to_csv.py
```

### 2. Run Complete Pipeline
```bash
python complete_sms_pipeline.py
```

### 3. Launch Analytics Dashboard
```bash
streamlit run sms_analytics_ui.py
```

### 4. View Pipeline Visualization
```bash
streamlit run pipeline_dashboard.py --server.port 8502
```

## 💡 **Usage Examples**

### Basic Pipeline Processing
```python
from complete_sms_pipeline import EnhancedSMSPipeline

# Initialize pipeline
pipeline = EnhancedSMSPipeline(cutoff_days=90)

# Process SMS with deduplication
results = pipeline.process_with_deduplication('sms_data.csv')

# Save results
pipeline.save_results(results, 'output')
```

### Deduplication Only
```python
from complete_sms_pipeline import MultiStrategyDeduplicator
import pandas as pd

# Load transactions
df = pd.read_csv('transactions.csv')

# Initialize deduplicator
deduplicator = MultiStrategyDeduplicator()

# Check for duplicates
for _, txn in df.iterrows():
    is_duplicate, reason = deduplicator.is_duplicate(txn)
    print(f"Duplicate: {is_duplicate}, Reason: {reason}")
```

## 📈 **Performance Metrics**

### ⚡ **Processing Speed**
- **22,835 messages** processed in **3.8 seconds**
- **Throughput**: ~6,000 messages per second
- **Memory efficient**: Processes large datasets

### 💰 **Cost Optimization**
- **47% duplicate elimination** (10,734 messages)
- **92% cost optimization** (only 8% need LLM)
- **Estimated savings**: $50-150 per batch

### 🎯 **Accuracy**
- **Deterministic success**: 76.9%
- **Confidence scoring**: 0-100% with signal/penalty system
- **Multi-strategy validation**: 3-layer deduplication

## 🔧 **Configuration**

### Environment Variables
```bash
# Gemini API (for LLM processing)
export GEMINI_API_KEY="your_api_key_here"

# Processing settings
export SMS_CUTOFF_DAYS=90
export CONFIDENCE_THRESHOLD=70
export BATCH_SIZE=1000
```

### Pipeline Settings
```python
# In complete_sms_pipeline.py
CUTOFF_DAYS = 90          # Process last N days
CONFIDENCE_THRESHOLD = 70  # Ready transaction threshold
LLM_BATCH_SIZE = 100      # Batch size for LLM processing
```

## 📊 **Financial Analysis**

### 💰 **Transaction Summary**
- **Total Value**: ₹44,832,141.41 (₹44.8 Million)
- **Average Transaction**: ₹7,385.86
- **Net Cash Flow**: +₹34,195,392.67 (Positive)

### 🏦 **Top Banks**
1. **AU Bank**: 2,926 transactions (48.2%)
2. **IDFC**: 950 transactions (15.7%)  
3. **YES Bank**: 892 transactions (14.7%)
4. **HDFC**: 372 transactions (6.1%)

### 💳 **Payment Methods**
- **UPI**: 41.9% of transactions
- **Card**: 10.1% of transactions
- **IMPS/NEFT**: 0.5% of transactions

## 🔍 **Regex Patterns**

### Amount Extraction
```python
patterns = [
    r'(?:INR|Rs\.?|₹|Rupees?)\s*([0-9,]+(?:\.\d{1,2})?)',
    r'([0-9,]+(?:\.\d{1,2})?)\s*(?:INR|Rs\.?|₹|Rupees?)',
    r'(?:debited|credited)\s+(?:INR|Rs\.?)?\s*([0-9,]+(?:\.\d{1,2})?)'
]
```

### Transaction Type Detection
```python
debit_patterns = [
    r'\b(?:debited|spent|charged|withdrawn|paid|purchase)\b',
    r'\b(?:ATM|POS)\s+(?:withdrawal|transaction)\b'
]

credit_patterns = [
    r'\b(?:credited|received|deposited|refund|cashback)\b',
    r'\b(?:salary|bonus|dividend)\b'
]
```

## 🛠️ **API Reference**

### EnhancedSMSPipeline
```python
class EnhancedSMSPipeline:
    def __init__(self, cutoff_days: int = 90)
    def parse_sms(self, sms_text: str, sender: str, timestamp: str) -> ParsedTransaction
    def process_with_deduplication(self, csv_path: str) -> Dict
    def save_results(self, results: Dict, base_name: str = "final") -> List[Tuple]
```

### MultiStrategyDeduplicator
```python
class MultiStrategyDeduplicator:
    def __init__(self)
    def is_duplicate(self, transaction: ParsedTransaction) -> Tuple[bool, str]
    def generate_ref_id(self, sms_text: str, amount: float, sender: str) -> str
    def get_stats(self) -> Dict
```

## 🔒 **Security & Privacy**

- **No external API calls** in regex processing
- **Local processing** of sensitive financial data
- **Configurable data retention** policies
- **Audit trail** for all transactions
- **PII handling** with optional redaction

## 📋 **Requirements**

### Core Dependencies
```
pandas>=1.5.0
sqlite3 (built-in)
streamlit>=1.28.0
plotly>=5.15.0
```

### Optional Dependencies
```
google-generativeai>=0.3.0  # For Gemini LLM processing
python-dotenv>=1.0.0        # For environment variables
```

## 🤝 **Contributing**

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 **License**

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 **Acknowledgments**

- **Regex patterns** optimized for Indian banking SMS formats
- **Deduplication strategies** inspired by enterprise data processing
- **UI components** built with Streamlit and Plotly
- **Performance optimizations** for large-scale SMS processing

## 📞 **Support**

- 🐛 **Bug Reports**: [GitHub Issues](../../issues)
- 💡 **Feature Requests**: [GitHub Discussions](../../discussions)
- 📧 **Email**: support@sms-pipeline.com

---

## 🎯 **Production Deployment**

### Docker Setup
```dockerfile
FROM python:3.9-slim
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . /app
WORKDIR /app
CMD ["python", "complete_sms_pipeline.py"]
```

### Cloud Deployment
- **AWS Lambda**: For serverless processing
- **Google Cloud Functions**: For event-driven processing
- **Azure Functions**: For enterprise integration

### Monitoring
- **Prometheus metrics** for performance monitoring
- **Grafana dashboards** for visualization
- **Alert integration** for failure notifications

---

**Built with ❤️ for financial data processing**

*Last updated: August 26, 2025*