#!/bin/bash
# SMS Financial Transaction Pipeline - Quick Start Script

set -e

echo "🚀 SMS Financial Transaction Pipeline"
echo "====================================="
echo

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 is not installed. Please install Python 3.8 or higher."
    exit 1
fi

print_status "Python 3 found"

# Check Python version
python_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
min_version="3.8"

if [ "$(printf '%s\n' "$min_version" "$python_version" | sort -V | head -n1)" = "$min_version" ]; then
    print_status "Python version $python_version is compatible"
else
    print_error "Python version $python_version is too old. Please upgrade to Python 3.8 or higher."
    exit 1
fi

# Install dependencies
print_info "Installing dependencies..."
if pip3 install -r requirements.txt; then
    print_status "Dependencies installed successfully"
else
    print_error "Failed to install dependencies"
    exit 1
fi

# Check if SMS data file exists
if [ ! -f "sms_raw.txt" ] && [ ! -f "sms_data_from_raw.csv" ]; then
    print_warning "No SMS data file found (sms_raw.txt or sms_data_from_raw.csv)"
    print_info "Please add your SMS data file and run again"
    exit 1
fi

# Convert raw data if needed
if [ -f "sms_raw.txt" ] && [ ! -f "sms_data_from_raw.csv" ]; then
    print_info "Converting raw SMS data to CSV..."
    if python3 convert_raw_to_csv.py; then
        print_status "SMS data converted to CSV"
    else
        print_error "Failed to convert SMS data"
        exit 1
    fi
else
    print_status "SMS CSV data found"
fi

# Run the complete pipeline
print_info "Running SMS processing pipeline..."
if python3 complete_sms_pipeline.py; then
    print_status "Pipeline completed successfully!"
else
    print_error "Pipeline failed"
    exit 1
fi

# Show results
echo
echo "📊 PIPELINE RESULTS:"
echo "==================="

if [ -f "final_final_ready.csv" ]; then
    ready_count=$(wc -l < final_final_ready.csv)
    ready_count=$((ready_count - 1))  # Subtract header
    print_status "Ready for ledger: $ready_count transactions"
fi

if [ -f "final_final_ambiguous.csv" ]; then
    ambiguous_count=$(wc -l < final_final_ambiguous.csv)
    ambiguous_count=$((ambiguous_count - 1))  # Subtract header
    print_info "Need LLM processing: $ambiguous_count transactions"
fi

if [ -f "final_duplicates_removed.csv" ]; then
    duplicates_count=$(wc -l < final_duplicates_removed.csv)
    duplicates_count=$((duplicates_count - 1))  # Subtract header
    print_status "Duplicates eliminated: $duplicates_count"
fi

echo
print_info "Launch analytics dashboard:"
echo "  streamlit run sms_analytics_ui.py"
echo
print_info "Launch pipeline dashboard:"
echo "  streamlit run pipeline_dashboard.py --server.port 8502"
echo

print_status "SMS Pipeline setup complete! 🎉"
