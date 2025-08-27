#!/bin/bash
# SMS Pipeline - ULTIMATE AUTOMATION SCRIPT
# This script does EVERYTHING for you automatically

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

# Banner
echo -e "${PURPLE}"
cat << "EOF"
🚀 SMS FINANCIAL PIPELINE - ULTIMATE AUTOMATION
===============================================
           🎯 DOES EVERYTHING FOR YOU 🎯

✅ Environment Setup        ✅ Data Processing
✅ Dependency Installation  ✅ Deduplication  
✅ Pipeline Execution       ✅ Analytics Generation
✅ Dashboard Launch         ✅ Browser Opening
✅ Complete Results         ✅ Summary Report

            Starting in 3 seconds...
EOF
echo -e "${NC}"

sleep 3

echo -e "${CYAN}🏁 STARTING COMPLETE AUTOMATION...${NC}"
echo

# Step 1: Check Python
echo -e "${BLUE}📋 Step 1: Checking Python installation...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 not found. Please install Python 3.8+${NC}"
    exit 1
fi

python_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo -e "${GREEN}✅ Python $python_version detected${NC}"

# Step 2: Install dependencies
echo -e "${BLUE}📦 Step 2: Installing dependencies...${NC}"
pip3 install -q pandas streamlit plotly || {
    echo -e "${RED}❌ Failed to install dependencies${NC}"
    exit 1
}
echo -e "${GREEN}✅ Dependencies installed${NC}"

# Step 3: Prepare data
echo -e "${BLUE}📄 Step 3: Preparing SMS data...${NC}"
if [ -f "sms_raw.txt" ] && [ ! -f "sms_data_from_raw.csv" ]; then
    echo -e "${YELLOW}🔄 Converting raw SMS data...${NC}"
    python3 convert_raw_to_csv.py || {
        echo -e "${RED}❌ Data conversion failed${NC}"
        exit 1
    }
elif [ -f "sms_data_from_raw.csv" ]; then
    echo -e "${GREEN}✅ SMS data ready${NC}"
else
    echo -e "${RED}❌ No SMS data found${NC}"
    exit 1
fi

# Step 4: Run complete pipeline
echo -e "${BLUE}🚀 Step 4: Running SMS processing pipeline...${NC}"
echo -e "${YELLOW}⏳ Processing 22,000+ messages with deduplication...${NC}"

python3 complete_sms_pipeline.py || {
    echo -e "${RED}❌ Pipeline execution failed${NC}"
    exit 1
}

echo -e "${GREEN}✅ Pipeline completed successfully${NC}"

# Step 5: Generate summary
echo -e "${BLUE}📊 Step 5: Generating results summary...${NC}"

# Count results
if [ -f "final_final_ready.csv" ]; then
    ready_count=$(($(wc -l < final_final_ready.csv) - 1))
    echo -e "${GREEN}📈 Ready for Ledger: $ready_count transactions${NC}"
fi

if [ -f "final_final_ambiguous.csv" ]; then
    ambiguous_count=$(($(wc -l < final_final_ambiguous.csv) - 1))
    echo -e "${YELLOW}🤖 Need LLM Processing: $ambiguous_count transactions${NC}"
fi

if [ -f "final_duplicates_removed.csv" ]; then
    duplicates_count=$(($(wc -l < final_duplicates_removed.csv) - 1))
    echo -e "${CYAN}🔄 Duplicates Eliminated: $duplicates_count messages${NC}"
fi

# Step 6: Launch dashboards in background
echo -e "${BLUE}🎮 Step 6: Launching interactive dashboards...${NC}"

# Kill any existing streamlit processes
pkill -f streamlit 2>/dev/null || true

# Launch analytics dashboard
nohup python3 -m streamlit run sms_analytics_ui.py --server.port 8501 > analytics.log 2>&1 &
ANALYTICS_PID=$!

# Launch pipeline dashboard  
nohup python3 -m streamlit run pipeline_dashboard.py --server.port 8502 > pipeline.log 2>&1 &
PIPELINE_PID=$!

echo -e "${GREEN}✅ Dashboards launching...${NC}"

# Wait for servers to start
echo -e "${YELLOW}⏳ Waiting for dashboards to start (5 seconds)...${NC}"
sleep 5

# Step 7: Open browsers automatically
echo -e "${BLUE}🌐 Step 7: Opening browsers...${NC}"

# Try to open browsers (works on macOS, Linux with desktop)
if command -v open &> /dev/null; then
    # macOS
    open http://localhost:8501 2>/dev/null || true
    sleep 1
    open http://localhost:8502 2>/dev/null || true
elif command -v xdg-open &> /dev/null; then
    # Linux
    xdg-open http://localhost:8501 2>/dev/null || true
    sleep 1  
    xdg-open http://localhost:8502 2>/dev/null || true
elif command -v start &> /dev/null; then
    # Windows
    start http://localhost:8501 2>/dev/null || true
    sleep 1
    start http://localhost:8502 2>/dev/null || true
fi

echo -e "${GREEN}✅ Browsers opened (or attempted)${NC}"

# Step 8: Create summary report
cat > AUTOMATION_RESULTS.md << EOF
# 🎉 SMS Pipeline Automation - COMPLETE RESULTS

**Generated:** $(date)

## 📊 Processing Results

### 🎯 Transaction Summary
- **Ready for Ledger:** $ready_count transactions  
- **Need LLM Processing:** $ambiguous_count transactions
- **Duplicates Eliminated:** $duplicates_count messages

### 📁 Generated Files
- \`final_final_ready.csv\` - Production-ready transactions
- \`final_final_ambiguous.csv\` - Transactions needing LLM  
- \`final_duplicates_removed.csv\` - Eliminated duplicates
- \`final_rejected.csv\` - Non-financial messages
- \`final_failed.csv\` - Failed transactions
- \`final_investment.csv\` - Investment/SIP messages

### 🎮 Active Dashboards
- **Analytics Dashboard:** http://localhost:8501
- **Pipeline Dashboard:** http://localhost:8502

## 🚀 What's Ready

✅ **Complete SMS processing pipeline executed**  
✅ **Multi-strategy deduplication completed**  
✅ **Interactive dashboards launched**  
✅ **All results generated and organized**  
✅ **Production-ready transaction data available**

## 💡 Next Steps

1. **Review Dashboards** - Analytics opened in your browser
2. **Check Results** - CSV files contain processed data  
3. **Use Ready Data** - \`final_final_ready.csv\` for production ledger
4. **Process Ambiguous** - \`final_final_ambiguous.csv\` through LLM if needed

**Everything is automated and ready! 🎉**
EOF

# Final success message
echo
echo -e "${PURPLE}════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}🎉 COMPLETE AUTOMATION SUCCESSFUL! 🎉${NC}"
echo -e "${PURPLE}════════════════════════════════════════════════════════${NC}"
echo
echo -e "${CYAN}📊 RESULTS:${NC}"
echo -e "  🎯 Ready for Ledger: ${GREEN}$ready_count${NC} transactions"
echo -e "  🤖 Need LLM: ${YELLOW}$ambiguous_count${NC} transactions"  
echo -e "  🔄 Duplicates Removed: ${CYAN}$duplicates_count${NC} messages"
echo
echo -e "${CYAN}🎮 ACTIVE DASHBOARDS:${NC}"
echo -e "  📈 Analytics: ${BLUE}http://localhost:8501${NC}"
echo -e "  🔧 Pipeline: ${BLUE}http://localhost:8502${NC}"
echo
echo -e "${CYAN}📁 OUTPUT FILES:${NC}"
echo -e "  📄 final_final_ready.csv - Production transactions"
echo -e "  📄 final_final_ambiguous.csv - For LLM processing"
echo -e "  📄 AUTOMATION_RESULTS.md - Complete summary"
echo
echo -e "${GREEN}✅ Everything completed automatically!${NC}"
echo -e "${YELLOW}⚡ Dashboards are running in background${NC}"
echo -e "${PURPLE}🌐 Check your browser for interactive analytics${NC}"
echo

# Keep script running to maintain dashboards
echo -e "${BLUE}📌 Press Ctrl+C to stop dashboards and exit${NC}"
echo

# Wait for user interrupt
trap 'echo -e "\n${YELLOW}🛑 Stopping dashboards...${NC}"; kill $ANALYTICS_PID $PIPELINE_PID 2>/dev/null; echo -e "${GREEN}✅ Automation stopped${NC}"; exit 0' INT

# Keep dashboards alive
while kill -0 $ANALYTICS_PID 2>/dev/null && kill -0 $PIPELINE_PID 2>/dev/null; do
    sleep 1
done

echo -e "${RED}⚠️  Dashboards stopped unexpectedly${NC}"
