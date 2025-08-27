#!/usr/bin/env python3
"""
SMS Analytics Dashboard
Comprehensive UI for SMS parsing results using Streamlit
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sqlite3
import numpy as np
from datetime import datetime, timedelta
import os
import threading
import time
from sms_parser import GeminiSMSParser, SMSDataProcessor, DataAnalyzer
import logging

# Configure page
st.set_page_config(
    page_title="SMS Financial Analytics Dashboard",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
    }
    .success-box {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 0.375rem;
        padding: 0.75rem;
        margin: 1rem 0;
    }
    .warning-box {
        background-color: #fff3cd;
        border: 1px solid #ffeaa7;
        border-radius: 0.375rem;
        padding: 0.75rem;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

class SMSAnalyticsDashboard:
    def __init__(self):
        self.api_key = "AIzaSyArZpN-ZVmhAR3emZN9P5p2Y_hjEn8h97Q"
        self.csv_file = "sms_data_from_raw.csv"
        self.db_file = "analytics_transactions.db"
        
    def load_data(self):
        """Load transaction data from database"""
        if not os.path.exists(self.db_file):
            return pd.DataFrame()
        
        try:
            conn = sqlite3.connect(self.db_file)
            df = pd.read_sql_query('SELECT * FROM transactions', conn)
            conn.close()
            
            if not df.empty:
                df['date'] = pd.to_datetime(df['date'], errors='coerce')
                df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
            
            return df
        except Exception as e:
            st.error(f"Error loading data: {e}")
            return pd.DataFrame()
    
    def run_parser(self, progress_callback=None):
        """Run the SMS parser on full dataset"""
        try:
            parser = GeminiSMSParser(self.api_key)
            processor = SMSDataProcessor(parser, self.db_file)
            
            # Process CSV file
            transactions = processor.process_csv_file(self.csv_file, 'sms_body')
            
            if transactions:
                processor.store_transactions(transactions)
                return len(transactions)
            return 0
            
        except Exception as e:
            st.error(f"Error running parser: {e}")
            return 0
    
    def create_overview_metrics(self, df):
        """Create overview metrics"""
        if df.empty:
            st.warning("No transaction data available")
            return
        
        # Separate debit and credit transactions
        debits = df[df.get('transaction_type', 'debit') == 'debit'] if 'transaction_type' in df.columns else df
        credits = df[df.get('transaction_type', 'debit') == 'credit'] if 'transaction_type' in df.columns else pd.DataFrame()
        
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric(
                label="Total Transactions",
                value=f"{len(df):,}",
                delta=None
            )
        
        with col2:
            total_debits = debits['amount'].sum() if not debits.empty else 0
            st.metric(
                label="Total Spent",
                value=f"₹{total_debits:,.2f}",
                delta=None
            )
        
        with col3:
            total_credits = credits['amount'].sum() if not credits.empty else 0
            st.metric(
                label="Total Received",
                value=f"₹{total_credits:,.2f}",
                delta=None
            )
        
        with col4:
            net_amount = total_credits - total_debits
            st.metric(
                label="Net Balance",
                value=f"₹{net_amount:,.2f}",
                delta=None
            )
        
        with col5:
            unique_merchants = df['merchant'].nunique()
            st.metric(
                label="Unique Merchants",
                value=f"{unique_merchants:,}",
                delta=None
            )
    
    def create_time_series_chart(self, df):
        """Create time series chart"""
        if df.empty or 'date' not in df.columns:
            return
        
        # Separate debit and credit transactions
        if 'transaction_type' in df.columns:
            debits = df[df['transaction_type'] == 'debit']
            credits = df[df['transaction_type'] == 'credit']
            
            # Group by date for both types
            daily_debits = debits.groupby(debits['date'].dt.date)['amount'].sum().reset_index()
            daily_credits = credits.groupby(credits['date'].dt.date)['amount'].sum().reset_index()
            daily_debits.columns = ['date', 'debit_amount']
            daily_credits.columns = ['date', 'credit_amount']
            
            # Merge data
            daily_data = pd.merge(daily_debits, daily_credits, on='date', how='outer').fillna(0)
            
            # Create subplot
            fig = make_subplots(
                rows=1, cols=1,
                subplot_titles=('Daily Money Flow'),
            )
            
            # Add debit line
            fig.add_trace(
                go.Scatter(
                    x=daily_data['date'],
                    y=-daily_data['debit_amount'],  # Negative for spending
                    mode='lines+markers',
                    name='Spent (Debit)',
                    line=dict(color='#ff4444', width=2),
                    fill='tonexty'
                )
            )
            
            # Add credit line
            fig.add_trace(
                go.Scatter(
                    x=daily_data['date'],
                    y=daily_data['credit_amount'],  # Positive for income
                    mode='lines+markers',
                    name='Received (Credit)',
                    line=dict(color='#44ff44', width=2),
                    fill='tozeroy'
                )
            )
            
            fig.update_layout(
                height=400,
                title_text="Daily Money Flow (Income vs Spending)",
                showlegend=True,
                hovermode='x unified'
            )
        else:
            # Fallback to original logic if no transaction_type column
            daily_spending = df.groupby(df['date'].dt.date)['amount'].agg(['sum', 'count']).reset_index()
            daily_spending.columns = ['date', 'total_amount', 'transaction_count']
            
            fig = go.Figure()
            fig.add_trace(
                go.Scatter(
                    x=daily_spending['date'],
                    y=daily_spending['total_amount'],
                    mode='lines+markers',
                    name='Daily Amount',
                    line=dict(color='#1f77b4', width=2)
                )
            )
            
            fig.update_layout(
                height=400,
                title_text="Daily Transaction Amounts",
                showlegend=True
            )
        
        fig.update_xaxes(title_text="Date")
        fig.update_yaxes(title_text="Amount (₹)")
        
        return fig
    
    def create_category_charts(self, df):
        """Create category analysis charts"""
        if df.empty:
            return None, None
        
        # Category distribution
        category_dist = df['category'].value_counts()
        
        fig1 = px.pie(
            values=category_dist.values,
            names=category_dist.index,
            title="Spending by Category",
            color_discrete_sequence=px.colors.qualitative.Set3
        )
        
        # Category spending amounts
        category_amounts = df.groupby('category')['amount'].sum().sort_values(ascending=True)
        
        fig2 = px.bar(
            x=category_amounts.values,
            y=category_amounts.index,
            orientation='h',
            title="Total Amount by Category",
            color=category_amounts.values,
            color_continuous_scale='Blues'
        )
        fig2.update_layout(showlegend=False)
        
        return fig1, fig2
    
    def create_merchant_analysis(self, df):
        """Create merchant analysis"""
        if df.empty:
            return None
        
        # Top merchants by transaction count
        top_merchants = df['merchant'].value_counts().head(15)
        
        fig = px.bar(
            x=top_merchants.values,
            y=top_merchants.index,
            orientation='h',
            title="Top 15 Merchants by Transaction Count",
            color=top_merchants.values,
            color_continuous_scale='Viridis'
        )
        fig.update_layout(showlegend=False, height=500)
        
        return fig
    
    def create_amount_distribution(self, df):
        """Create amount distribution chart"""
        if df.empty:
            return None
        
        fig = px.histogram(
            df,
            x='amount',
            nbins=50,
            title="Transaction Amount Distribution",
            color_discrete_sequence=['#1f77b4']
        )
        fig.update_layout(
            xaxis_title="Amount (₹)",
            yaxis_title="Frequency"
        )
        
        return fig
    
    def create_bank_analysis(self, df):
        """Create bank analysis"""
        if df.empty or 'bank' not in df.columns:
            return None
        
        # Filter out null banks
        bank_data = df[df['bank'].notna()]
        if bank_data.empty:
            return None
        
        bank_stats = bank_data.groupby('bank').agg({
            'amount': ['sum', 'count', 'mean']
        }).round(2)
        
        bank_stats.columns = ['Total Amount', 'Transaction Count', 'Average Amount']
        bank_stats = bank_stats.sort_values('Total Amount', ascending=False)
        
        fig = px.bar(
            x=bank_stats.index,
            y=bank_stats['Total Amount'],
            title="Total Spending by Bank",
            color=bank_stats['Total Amount'],
            color_continuous_scale='Blues'
        )
        fig.update_layout(
            xaxis_title="Bank",
            yaxis_title="Total Amount (₹)",
            showlegend=False
        )
        
        return fig
    
    def display_data_table(self, df):
        """Display transaction data table"""
        if df.empty:
            return
        
        st.subheader("📋 Transaction Data")
        
        # Filters
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if 'category' in df.columns:
                categories = ['All'] + list(df['category'].unique())
                selected_category = st.selectbox("Filter by Category", categories)
            else:
                selected_category = 'All'
        
        with col2:
            merchants = ['All'] + list(df['merchant'].unique())
            selected_merchant = st.selectbox("Filter by Merchant", merchants)
        
        with col3:
            if 'bank' in df.columns:
                banks = ['All'] + list(df[df['bank'].notna()]['bank'].unique())
                selected_bank = st.selectbox("Filter by Bank", banks)
            else:
                selected_bank = 'All'
        
        # Apply filters
        filtered_df = df.copy()
        
        if selected_category != 'All':
            filtered_df = filtered_df[filtered_df['category'] == selected_category]
        
        if selected_merchant != 'All':
            filtered_df = filtered_df[filtered_df['merchant'] == selected_merchant]
        
        if selected_bank != 'All':
            filtered_df = filtered_df[filtered_df['bank'] == selected_bank]
        
        # Display filtered data
        st.write(f"Showing {len(filtered_df):,} transactions")
        
        # Select columns to display
        display_columns = ['date', 'amount', 'merchant', 'category', 'transaction_type', 'ref_id', 'bank', 'payment_method']
        available_columns = [col for col in display_columns if col in filtered_df.columns]
        
        st.dataframe(
            filtered_df[available_columns].sort_values('date', ascending=False),
            use_container_width=True,
            height=400
        )
    
    def run_dashboard(self):
        """Main dashboard function"""
        
        # Header
        st.markdown('<h1 class="main-header">💰 SMS Financial Analytics Dashboard</h1>', unsafe_allow_html=True)
        
        # Sidebar
        st.sidebar.title("🔧 Controls")
        
        # Check if data exists
        df = self.load_data()
        
        if df.empty:
            st.sidebar.markdown('<div class="warning-box">⚠️ No transaction data found. Run the parser first!</div>', unsafe_allow_html=True)
            
            if st.sidebar.button("🚀 Run SMS Parser", type="primary"):
                with st.spinner("Processing SMS messages... This may take several minutes."):
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    # Run parser
                    status_text.text("Initializing parser...")
                    progress_bar.progress(10)
                    
                    status_text.text("Processing SMS messages...")
                    progress_bar.progress(30)
                    
                    result = self.run_parser()
                    
                    progress_bar.progress(100)
                    status_text.text("Parsing completed!")
                    
                    if result > 0:
                        st.success(f"✅ Successfully processed {result:,} transactions!")
                        time.sleep(2)
                        st.experimental_rerun()
                    else:
                        st.error("❌ No transactions found or parsing failed")
        else:
            st.sidebar.markdown('<div class="success-box">✅ Transaction data loaded successfully!</div>', unsafe_allow_html=True)
            st.sidebar.metric("📊 Total Transactions", f"{len(df):,}")
            
            # Refresh data button
            if st.sidebar.button("🔄 Refresh Data"):
                st.experimental_rerun()
            
            # Re-run parser button
            if st.sidebar.button("🚀 Re-run Parser"):
                with st.spinner("Re-processing SMS messages..."):
                    result = self.run_parser()
                    if result > 0:
                        st.success(f"✅ Processed {result:,} additional transactions!")
                        st.experimental_rerun()
                    else:
                        st.info("ℹ️ No new transactions found")
            
            # Export options
            st.sidebar.subheader("📥 Export Options")
            if st.sidebar.button("Download CSV"):
                csv = df.to_csv(index=False)
                st.sidebar.download_button(
                    label="💾 Download Transactions",
                    data=csv,
                    file_name=f"transactions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
            
            # Main dashboard content
            if not df.empty:
                # Overview metrics
                st.subheader("📈 Overview")
                self.create_overview_metrics(df)
                
                st.markdown("---")
                
                # Time series analysis
                st.subheader("📅 Spending Trends")
                time_fig = self.create_time_series_chart(df)
                if time_fig:
                    st.plotly_chart(time_fig, use_container_width=True)
                
                st.markdown("---")
                
                # Category and merchant analysis
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("🏷️ Category Analysis")
                    cat_pie, cat_bar = self.create_category_charts(df)
                    if cat_pie:
                        st.plotly_chart(cat_pie, use_container_width=True)
                
                with col2:
                    st.subheader("🏪 Top Merchants")
                    merchant_fig = self.create_merchant_analysis(df)
                    if merchant_fig:
                        st.plotly_chart(merchant_fig, use_container_width=True)
                
                st.markdown("---")
                
                # Amount distribution and bank analysis
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("💰 Amount Distribution")
                    amount_fig = self.create_amount_distribution(df)
                    if amount_fig:
                        st.plotly_chart(amount_fig, use_container_width=True)
                
                with col2:
                    st.subheader("🏦 Bank Analysis")
                    bank_fig = self.create_bank_analysis(df)
                    if bank_fig:
                        st.plotly_chart(bank_fig, use_container_width=True)
                
                st.markdown("---")
                
                # Category spending amounts
                if 'category' in df.columns:
                    st.subheader("💸 Category Spending Breakdown")
                    cat_pie, cat_bar = self.create_category_charts(df)
                    if cat_bar:
                        st.plotly_chart(cat_bar, use_container_width=True)
                
                st.markdown("---")
                
                # Data table
                self.display_data_table(df)
                
                # Statistics summary
                st.markdown("---")
                st.subheader("📊 Summary Statistics")
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Total Spending", f"₹{df['amount'].sum():,.2f}")
                    st.metric("Average Transaction", f"₹{df['amount'].mean():,.2f}")
                
                with col2:
                    st.metric("Median Transaction", f"₹{df['amount'].median():,.2f}")
                    st.metric("Largest Transaction", f"₹{df['amount'].max():,.2f}")
                
                with col3:
                    date_range = df['date'].max() - df['date'].min()
                    st.metric("Date Range", f"{date_range.days} days")
                    st.metric("Transactions/Day", f"{len(df) / max(date_range.days, 1):.1f}")

def main():
    dashboard = SMSAnalyticsDashboard()
    dashboard.run_dashboard()

if __name__ == "__main__":
    main()
