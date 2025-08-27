#!/usr/bin/env python3
"""
SMS Financial Pipeline - Complete Automation Script
Does everything automatically: setup, processing, analysis, and dashboard launch
"""

import os
import sys
import subprocess
import time
import webbrowser
from pathlib import Path
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('automation.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class SMSPipelineAutomation:
    """Complete automation for SMS pipeline"""
    
    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.results = {}
        self.start_time = time.time()
        
    def print_banner(self):
        """Print startup banner"""
        banner = """
🚀 SMS FINANCIAL PIPELINE - COMPLETE AUTOMATION
===============================================
🎯 Does Everything Automatically:
   ✅ Environment setup
   ✅ Data processing  
   ✅ Deduplication
   ✅ Analytics generation
   ✅ Dashboard launch
   ✅ Results summary

Starting automated pipeline...
"""
        print(banner)
        logger.info("SMS Pipeline Automation Started")
    
    def check_dependencies(self):
        """Check and install dependencies"""
        logger.info("🔧 Checking dependencies...")
        
        # Check Python version
        if sys.version_info < (3, 8):
            logger.error("❌ Python 3.8+ required")
            sys.exit(1)
        
        logger.info(f"✅ Python {sys.version_info.major}.{sys.version_info.minor} detected")
        
        # Install requirements
        try:
            logger.info("📦 Installing dependencies...")
            subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'], 
                         check=True, capture_output=True)
            logger.info("✅ Dependencies installed")
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Failed to install dependencies: {e}")
            return False
        
        return True
    
    def prepare_data(self):
        """Prepare SMS data for processing"""
        logger.info("📄 Preparing SMS data...")
        
        # Check if raw data exists
        if not os.path.exists('sms_raw.txt'):
            logger.warning("⚠️  sms_raw.txt not found - using existing CSV if available")
            if not os.path.exists('sms_data_from_raw.csv'):
                logger.error("❌ No SMS data found (sms_raw.txt or sms_data_from_raw.csv)")
                return False
            else:
                logger.info("✅ Using existing CSV data")
                return True
        
        # Convert raw to CSV if needed
        if not os.path.exists('sms_data_from_raw.csv') or \
           os.path.getmtime('sms_raw.txt') > os.path.getmtime('sms_data_from_raw.csv'):
            
            logger.info("🔄 Converting raw SMS data to CSV...")
            try:
                subprocess.run([sys.executable, 'convert_raw_to_csv.py'], 
                             check=True, capture_output=True)
                logger.info("✅ SMS data converted to CSV")
            except subprocess.CalledProcessError as e:
                logger.error(f"❌ Failed to convert SMS data: {e}")
                return False
        else:
            logger.info("✅ CSV data is up to date")
        
        return True
    
    def run_pipeline(self):
        """Run the complete SMS processing pipeline"""
        logger.info("🚀 Running SMS processing pipeline...")
        
        try:
            # Run the complete pipeline
            result = subprocess.run([sys.executable, 'complete_sms_pipeline.py'], 
                                  check=True, capture_output=True, text=True)
            
            # Parse results from output
            output_lines = result.stdout.split('\n')
            for line in output_lines:
                if 'Ready for Ledger:' in line:
                    self.results['ready_count'] = self._extract_number(line)
                elif 'Still Ambiguous:' in line:
                    self.results['ambiguous_count'] = self._extract_number(line)
                elif 'Duplicates Removed:' in line:
                    self.results['duplicates_count'] = self._extract_number(line)
                elif 'Total Transaction Value:' in line:
                    self.results['total_value'] = self._extract_value(line)
            
            logger.info("✅ Pipeline processing completed")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Pipeline failed: {e}")
            logger.error(f"Error output: {e.stderr}")
            return False
    
    def generate_analytics(self):
        """Generate additional analytics"""
        logger.info("📊 Generating analytics...")
        
        try:
            # Create analytics summary
            self._create_summary_report()
            logger.info("✅ Analytics generated")
            return True
        except Exception as e:
            logger.error(f"❌ Analytics generation failed: {e}")
            return False
    
    def launch_dashboards(self):
        """Launch Streamlit dashboards"""
        logger.info("🎮 Launching interactive dashboards...")
        
        # Launch analytics dashboard
        try:
            analytics_process = subprocess.Popen([
                sys.executable, '-m', 'streamlit', 'run', 
                'sms_analytics_ui.py', '--server.port', '8501'
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # Launch pipeline dashboard
            pipeline_process = subprocess.Popen([
                sys.executable, '-m', 'streamlit', 'run', 
                'pipeline_dashboard.py', '--server.port', '8502'
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # Wait a moment for servers to start
            time.sleep(3)
            
            # Open browsers automatically
            try:
                webbrowser.open('http://localhost:8501')
                time.sleep(1)
                webbrowser.open('http://localhost:8502')
                logger.info("✅ Dashboards launched and browsers opened")
            except Exception as e:
                logger.warning(f"⚠️  Could not open browsers automatically: {e}")
                logger.info("🌐 Manual access:")
                logger.info("   Analytics: http://localhost:8501")
                logger.info("   Pipeline: http://localhost:8502")
            
            return analytics_process, pipeline_process
            
        except Exception as e:
            logger.error(f"❌ Dashboard launch failed: {e}")
            return None, None
    
    def _extract_number(self, text):
        """Extract number from text"""
        import re
        match = re.search(r'(\d{1,3}(?:,\d{3})*)', text)
        return match.group(1) if match else "0"
    
    def _extract_value(self, text):
        """Extract currency value from text"""
        import re
        match = re.search(r'₹([\d,]+(?:\.\d{2})?)', text)
        return match.group(1) if match else "0"
    
    def _create_summary_report(self):
        """Create a summary report"""
        report_content = f"""
# SMS Pipeline Automation Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 🎯 Pipeline Results

### 📊 Processing Summary
- Ready for Ledger: {self.results.get('ready_count', 'N/A')} transactions
- Need LLM Processing: {self.results.get('ambiguous_count', 'N/A')} transactions  
- Duplicates Eliminated: {self.results.get('duplicates_count', 'N/A')} messages
- Total Transaction Value: ₹{self.results.get('total_value', 'N/A')}

### 📁 Generated Files
- final_final_ready.csv - Production-ready transactions
- final_final_ambiguous.csv - Transactions needing LLM
- final_duplicates_removed.csv - Eliminated duplicates
- final_rejected.csv - Non-financial messages
- final_failed.csv - Failed transactions
- final_investment.csv - Investment/SIP messages

### 🎮 Active Dashboards
- Analytics Dashboard: http://localhost:8501
- Pipeline Dashboard: http://localhost:8502

### ⏱️ Performance
- Processing Time: {time.time() - self.start_time:.1f} seconds
- Status: ✅ Complete

## 🚀 Next Steps
1. Review the analytics dashboards (opened automatically)
2. Check the generated CSV files for detailed data
3. Use final_final_ready.csv for production financial ledger
4. Process final_final_ambiguous.csv through LLM if needed

Automation completed successfully! 🎉
"""
        
        with open('automation_report.md', 'w') as f:
            f.write(report_content)
    
    def print_completion_summary(self):
        """Print final completion summary"""
        elapsed_time = time.time() - self.start_time
        
        summary = f"""
🎉 SMS PIPELINE AUTOMATION COMPLETED!
=====================================
⏱️  Total Time: {elapsed_time:.1f} seconds

📊 RESULTS:
  🎯 Ready for Ledger: {self.results.get('ready_count', 'N/A')} transactions
  🤖 Need LLM: {self.results.get('ambiguous_count', 'N/A')} transactions
  🔄 Duplicates Removed: {self.results.get('duplicates_count', 'N/A')} messages
  💰 Total Value: ₹{self.results.get('total_value', 'N/A')}

🎮 ACTIVE DASHBOARDS:
  📈 Analytics: http://localhost:8501
  🔧 Pipeline: http://localhost:8502

📁 OUTPUT FILES:
  • final_final_ready.csv - Ready for production ledger
  • final_final_ambiguous.csv - For LLM processing
  • final_duplicates_removed.csv - Eliminated duplicates
  • automation_report.md - Complete summary

✅ Everything is ready! Check your browser for interactive dashboards.
"""
        print(summary)
        logger.info("Automation completed successfully")
    
    def run_complete_automation(self):
        """Run the complete automation sequence"""
        try:
            self.print_banner()
            
            # Step 1: Dependencies
            if not self.check_dependencies():
                return False
            
            # Step 2: Data preparation
            if not self.prepare_data():
                return False
            
            # Step 3: Pipeline processing
            if not self.run_pipeline():
                return False
            
            # Step 4: Analytics
            if not self.generate_analytics():
                return False
            
            # Step 5: Dashboards
            analytics_proc, pipeline_proc = self.launch_dashboards()
            
            # Final summary
            self.print_completion_summary()
            
            # Keep dashboards running
            if analytics_proc and pipeline_proc:
                logger.info("🎮 Dashboards are running. Press Ctrl+C to stop.")
                try:
                    while True:
                        time.sleep(1)
                except KeyboardInterrupt:
                    logger.info("🛑 Stopping dashboards...")
                    analytics_proc.terminate()
                    pipeline_proc.terminate()
                    logger.info("✅ Automation stopped")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Automation failed: {e}")
            return False

def main():
    """Main automation entry point"""
    automation = SMSPipelineAutomation()
    success = automation.run_complete_automation()
    
    if success:
        print("\n🎉 SMS Pipeline automation completed successfully!")
    else:
        print("\n❌ Automation failed. Check automation.log for details.")
        sys.exit(1)

if __name__ == "__main__":
    main()
