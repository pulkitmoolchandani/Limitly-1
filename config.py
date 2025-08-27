#!/usr/bin/env python3
"""
SMS Pipeline Configuration
Centralized configuration for the SMS processing pipeline
"""

import os
from pathlib import Path

# Base configuration
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
LOGS_DIR = BASE_DIR / "logs"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

# File paths
SMS_RAW_FILE = "sms_raw.txt"
SMS_CSV_FILE = "sms_data_from_raw.csv"

# Processing configuration
PROCESSING_CONFIG = {
    # Time filtering
    "cutoff_days": int(os.getenv("SMS_CUTOFF_DAYS", 90)),
    
    # Confidence thresholds
    "high_confidence_threshold": int(os.getenv("CONFIDENCE_THRESHOLD", 70)),
    "low_confidence_threshold": int(os.getenv("LOW_CONFIDENCE_THRESHOLD", 40)),
    
    # Batch processing
    "batch_size": int(os.getenv("BATCH_SIZE", 1000)),
    "llm_batch_size": int(os.getenv("LLM_BATCH_SIZE", 100)),
    
    # Performance
    "max_workers": int(os.getenv("MAX_WORKERS", 4)),
    "memory_limit_mb": int(os.getenv("MEMORY_LIMIT_MB", 2048))
}

# Database configuration
DATABASE_CONFIG = {
    "filename": "sms_transactions.db",
    "timeout": 30,
    "check_same_thread": False
}

# API configuration
API_CONFIG = {
    "gemini_api_key": os.getenv("GEMINI_API_KEY", ""),
    "api_timeout": int(os.getenv("API_TIMEOUT", 30)),
    "max_retries": int(os.getenv("MAX_RETRIES", 3)),
    "temperature": float(os.getenv("LLM_TEMPERATURE", 0.0))
}

# Logging configuration
LOGGING_CONFIG = {
    "level": os.getenv("LOG_LEVEL", "INFO"),
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "file": LOGS_DIR / "sms_pipeline.log",
    "max_size_mb": 10,
    "backup_count": 5
}

# UI configuration
UI_CONFIG = {
    "streamlit_port": int(os.getenv("STREAMLIT_PORT", 8501)),
    "dashboard_port": int(os.getenv("DASHBOARD_PORT", 8502)),
    "page_size": int(os.getenv("PAGE_SIZE", 100)),
    "chart_height": int(os.getenv("CHART_HEIGHT", 400))
}

# Security configuration
SECURITY_CONFIG = {
    "mask_pii": os.getenv("MASK_PII", "true").lower() == "true",
    "max_file_size_mb": int(os.getenv("MAX_FILE_SIZE_MB", 100)),
    "allowed_extensions": [".txt", ".csv", ".json"]
}

# Deduplication configuration
DEDUPLICATION_CONFIG = {
    "strategies": ["ref_id", "composite_key", "content_hash"],
    "ref_id_min_length": 8,
    "composite_key_components": ["sender", "amount", "txn_type", "minute_bucket"],
    "content_hash_algorithm": "md5",
    "similarity_threshold": 0.95
}

# Export configuration
EXPORT_CONFIG = {
    "final_ready_file": "final_ready_transactions.csv",
    "final_ambiguous_file": "final_ambiguous_transactions.csv",
    "duplicates_file": "duplicates_removed.csv",
    "rejected_file": "rejected_messages.csv",
    "failed_file": "failed_transactions.csv",
    "investment_file": "investment_messages.csv"
}

# Pipeline stages
PIPELINE_STAGES = {
    "raw_data_conversion": True,
    "regex_processing": True,
    "deduplication": True,
    "llm_processing": False,  # Set to True to enable actual LLM calls
    "final_storage": True,
    "analytics_generation": True
}

def get_config():
    """Get complete configuration dictionary"""
    return {
        "processing": PROCESSING_CONFIG,
        "database": DATABASE_CONFIG,
        "api": API_CONFIG,
        "logging": LOGGING_CONFIG,
        "ui": UI_CONFIG,
        "security": SECURITY_CONFIG,
        "deduplication": DEDUPLICATION_CONFIG,
        "export": EXPORT_CONFIG,
        "pipeline": PIPELINE_STAGES
    }

def print_config():
    """Print current configuration"""
    config = get_config()
    print("🔧 SMS Pipeline Configuration:")
    print("=" * 40)
    for section, settings in config.items():
        print(f"\n📋 {section.upper()}:")
        for key, value in settings.items():
            print(f"  {key}: {value}")

if __name__ == "__main__":
    print_config()
