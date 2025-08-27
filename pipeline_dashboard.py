#!/usr/bin/env python3
"""
SMS Pipeline Dashboard
Visualize the deterministic pipeline results and confidence scoring
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np

# Configure page
st.set_page_config(
    page_title="SMS Pipeline Dashboard",
    page_icon="🔄",
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
</style>
""", unsafe_allow_html=True)

def load_pipeline_data():
    """Load pipeline results"""
    try:
        df = pd.read_csv('sms_pipeline_results.csv')
        return df
    except FileNotFoundError:
        st.error("Pipeline results not found. Please run the SMS pipeline first.")
        return None

def create_bucket_distribution(df):
    """Create bucket distribution chart"""
    bucket_counts = df['bucket'].value_counts()
    
    # Clean bucket names
    bucket_names = {
        'BucketType.BANK_LEDGER_SUCCESS': 'Ready for Ledger',
        'BucketType.AMBIGUOUS': 'Need LLM Processing',
        'BucketType.REJECTED': 'Rejected (Non-Financial)',
        'BucketType.BANK_LEDGER_FAILED': 'Failed Transactions'
    }
    
    bucket_counts.index = [bucket_names.get(x, x) for x in bucket_counts.index]
    
    colors = ['#2E8B57', '#FFD700', '#FF6347', '#8B0000']
    
    fig = px.pie(
        values=bucket_counts.values,
        names=bucket_counts.index,
        title="SMS Message Classification",
        color_discrete_sequence=colors
    )
    
    fig.update_traces(
        textposition='inside', 
        textinfo='percent+label',
        hovertemplate='<b>%{label}</b><br>Count: %{value}<br>Percentage: %{percent}<extra></extra>'
    )
    
    return fig

def create_confidence_distribution(df):
    """Create confidence score distribution"""
    fig = px.histogram(
        df,
        x='confidence_score',
        nbins=20,
        title="Confidence Score Distribution",
        color_discrete_sequence=['#1f77b4']
    )
    
    fig.update_layout(
        xaxis_title="Confidence Score",
        yaxis_title="Number of Messages"
    )
    
    # Add vertical lines for thresholds
    fig.add_vline(x=70, line_dash="dash", line_color="green", 
                  annotation_text="High Confidence (70%)", annotation_position="top")
    fig.add_vline(x=40, line_dash="dash", line_color="orange", 
                  annotation_text="Low Confidence (40%)", annotation_position="top")
    
    return fig

def create_amount_analysis(df):
    """Create transaction amount analysis"""
    # Filter successful transactions with amounts
    success_df = df[(df['bucket'] == 'BucketType.BANK_LEDGER_SUCCESS') & (df['amount'].notna())]
    
    if success_df.empty:
        return None
    
    # Create subplots
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=('Amount Distribution', 'Debit vs Credit', 'Top Payment Rails', 'Daily Transaction Volume'),
        specs=[[{"type": "histogram"}, {"type": "bar"}],
               [{"type": "bar"}, {"type": "scatter"}]]
    )
    
    # Amount distribution
    fig.add_trace(
        go.Histogram(x=success_df['amount'], name='Amount Distribution', nbinsx=30),
        row=1, col=1
    )
    
    # Debit vs Credit
    txn_type_counts = success_df['txn_type'].value_counts()
    txn_type_names = {
        'TransactionType.DEBIT': 'Debit',
        'TransactionType.CREDIT': 'Credit'
    }
    
    fig.add_trace(
        go.Bar(
            x=[txn_type_names.get(x, x) for x in txn_type_counts.index],
            y=txn_type_counts.values,
            name='Transaction Type',
            marker_color=['#FF6B6B', '#4ECDC4']
        ),
        row=1, col=2
    )
    
    # Payment Rails
    rail_counts = success_df['rail'].value_counts().head(6)
    rail_names = {
        'Rail.UPI': 'UPI',
        'Rail.CARD': 'Card',
        'Rail.ATM': 'ATM',
        'Rail.IMPS': 'IMPS',
        'Rail.NEFT': 'NEFT',
        'Rail.UNKNOWN': 'Unknown'
    }
    
    fig.add_trace(
        go.Bar(
            x=[rail_names.get(x, x) for x in rail_counts.index],
            y=rail_counts.values,
            name='Payment Rails',
            marker_color='#95A5A6'
        ),
        row=2, col=1
    )
    
    # Daily volume
    success_df['date'] = pd.to_datetime(success_df['date'])
    daily_volume = success_df.groupby(success_df['date'].dt.date).size()
    
    fig.add_trace(
        go.Scatter(
            x=daily_volume.index,
            y=daily_volume.values,
            mode='lines+markers',
            name='Daily Volume',
            line=dict(color='#9B59B6', width=2)
        ),
        row=2, col=2
    )
    
    fig.update_layout(height=600, showlegend=False, title_text="Transaction Analysis")
    return fig

def create_signal_penalty_analysis(df):
    """Analyze signals and penalties"""
    
    # Extract signals and penalties
    all_signals = []
    all_penalties = []
    
    for _, row in df.iterrows():
        signals = eval(row['signals']) if row['signals'] != '[]' else []
        penalties = eval(row['penalties']) if row['penalties'] != '[]' else []
        
        all_signals.extend(signals)
        all_penalties.extend(penalties)
    
    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=('Top Confidence Signals', 'Top Penalty Patterns'),
        specs=[[{"type": "bar"}, {"type": "bar"}]]
    )
    
    # Signals
    if all_signals:
        signal_counts = pd.Series(all_signals).value_counts().head(8)
        fig.add_trace(
            go.Bar(
                x=signal_counts.values,
                y=signal_counts.index,
                orientation='h',
                name='Signals',
                marker_color='#2ECC71'
            ),
            row=1, col=1
        )
    
    # Penalties
    if all_penalties:
        penalty_counts = pd.Series(all_penalties).value_counts().head(8)
        fig.add_trace(
            go.Bar(
                x=penalty_counts.values,
                y=penalty_counts.index,
                orientation='h',
                name='Penalties',
                marker_color='#E74C3C'
            ),
            row=1, col=2
        )
    
    fig.update_layout(height=400, showlegend=False)
    return fig

def create_bank_analysis(df):
    """Analyze by bank"""
    bank_df = df[df['bank'].notna() & (df['bank'] != '')]
    
    if bank_df.empty:
        return None
    
    bank_stats = bank_df.groupby('bank').agg({
        'amount': ['sum', 'count', 'mean'],
        'confidence_score': 'mean'
    }).round(2)
    
    bank_stats.columns = ['Total Amount', 'Count', 'Avg Amount', 'Avg Confidence']
    bank_stats = bank_stats.sort_values('Total Amount', ascending=False).head(10)
    
    fig = px.bar(
        x=bank_stats.index,
        y=bank_stats['Total Amount'],
        title="Transaction Volume by Bank",
        color=bank_stats['Avg Confidence'],
        color_continuous_scale='Viridis'
    )
    
    fig.update_layout(
        xaxis_title="Bank",
        yaxis_title="Total Amount (₹)",
        coloraxis_colorbar_title="Avg Confidence"
    )
    
    return fig

def main():
    """Main dashboard"""
    
    st.markdown('<h1 class="main-header">🔄 SMS Pipeline Dashboard</h1>', unsafe_allow_html=True)
    
    # Load data
    df = load_pipeline_data()
    if df is None:
        return
    
    # Sidebar stats
    st.sidebar.title("📊 Pipeline Summary")
    
    total_messages = len(df)
    ready_for_ledger = len(df[df['bucket'] == 'BucketType.BANK_LEDGER_SUCCESS'])
    need_llm = len(df[df['bucket'] == 'BucketType.AMBIGUOUS'])
    rejected = len(df[df['bucket'] == 'BucketType.REJECTED'])
    
    st.sidebar.metric("Total Messages", f"{total_messages:,}")
    st.sidebar.metric("Ready for Ledger", f"{ready_for_ledger:,}")
    st.sidebar.metric("Need LLM", f"{need_llm:,}")
    st.sidebar.metric("Rejected", f"{rejected:,}")
    
    # Pipeline efficiency
    efficiency = (ready_for_ledger / total_messages) * 100
    st.sidebar.metric("Pipeline Efficiency", f"{efficiency:.1f}%")
    
    # Main content
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Overview", "💰 Transactions", "🎯 Signals & Penalties", "🏦 Banks", "📋 Data"])
    
    with tab1:
        st.subheader("Pipeline Classification Results")
        
        col1, col2 = st.columns(2)
        
        with col1:
            bucket_fig = create_bucket_distribution(df)
            st.plotly_chart(bucket_fig, use_container_width=True)
        
        with col2:
            confidence_fig = create_confidence_distribution(df)
            st.plotly_chart(confidence_fig, use_container_width=True)
        
        # Summary stats
        st.subheader("Classification Summary")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "High Confidence (≥70%)",
                f"{len(df[df['confidence_score'] >= 70]):,}",
                f"{len(df[df['confidence_score'] >= 70])/len(df)*100:.1f}%"
            )
        
        with col2:
            st.metric(
                "Medium Confidence (40-70%)",
                f"{len(df[(df['confidence_score'] >= 40) & (df['confidence_score'] < 70)]):,}",
                f"{len(df[(df['confidence_score'] >= 40) & (df['confidence_score'] < 70)])/len(df)*100:.1f}%"
            )
        
        with col3:
            st.metric(
                "Low Confidence (<40%)",
                f"{len(df[df['confidence_score'] < 40]):,}",
                f"{len(df[df['confidence_score'] < 40])/len(df)*100:.1f}%"
            )
        
        with col4:
            avg_confidence = df['confidence_score'].mean()
            st.metric(
                "Average Confidence",
                f"{avg_confidence:.1f}%"
            )
    
    with tab2:
        st.subheader("Transaction Analysis")
        
        amount_fig = create_amount_analysis(df)
        if amount_fig:
            st.plotly_chart(amount_fig, use_container_width=True)
        
        # Transaction summary
        success_df = df[df['bucket'] == 'BucketType.BANK_LEDGER_SUCCESS']
        if not success_df.empty and success_df['amount'].notna().any():
            col1, col2, col3 = st.columns(3)
            
            with col1:
                total_amount = success_df['amount'].sum()
                st.metric("Total Transaction Value", f"₹{total_amount:,.2f}")
            
            with col2:
                avg_amount = success_df['amount'].mean()
                st.metric("Average Transaction", f"₹{avg_amount:,.2f}")
            
            with col3:
                median_amount = success_df['amount'].median()
                st.metric("Median Transaction", f"₹{median_amount:,.2f}")
    
    with tab3:
        st.subheader("Signal & Penalty Analysis")
        
        signal_fig = create_signal_penalty_analysis(df)
        if signal_fig:
            st.plotly_chart(signal_fig, use_container_width=True)
        
        st.markdown("""
        **Signals** increase confidence scores:
        - executed_verbs: Contains words like 'debited', 'credited'
        - amount_present: Has clear amount information
        - rail_cue: Contains payment method information
        - ref_id_present: Has reference/transaction ID
        
        **Penalties** decrease confidence scores:
        - otp: OTP or verification messages
        - maintenance: System maintenance messages
        - sip_amc: Investment/SIP related messages
        - failed: Failed transaction messages
        """)
    
    with tab4:
        st.subheader("Bank Analysis")
        
        bank_fig = create_bank_analysis(df)
        if bank_fig:
            st.plotly_chart(bank_fig, use_container_width=True)
        
        # Bank summary table
        bank_df = df[df['bank'].notna() & (df['bank'] != '')]
        if not bank_df.empty:
            bank_summary = bank_df.groupby('bank').agg({
                'amount': ['count', 'sum', 'mean'],
                'confidence_score': 'mean'
            }).round(2)
            
            bank_summary.columns = ['Transaction Count', 'Total Amount', 'Avg Amount', 'Avg Confidence']
            bank_summary = bank_summary.sort_values('Total Amount', ascending=False)
            
            st.dataframe(bank_summary, use_container_width=True)
    
    with tab5:
        st.subheader("Raw Pipeline Data")
        
        # Filter options
        col1, col2, col3 = st.columns(3)
        
        with col1:
            bucket_filter = st.selectbox(
                "Filter by Bucket",
                ['All'] + df['bucket'].unique().tolist()
            )
        
        with col2:
            min_confidence = st.slider("Minimum Confidence", 0, 100, 0)
        
        with col3:
            max_rows = st.selectbox("Max Rows", [100, 500, 1000, 5000], index=1)
        
        # Apply filters
        filtered_df = df.copy()
        
        if bucket_filter != 'All':
            filtered_df = filtered_df[filtered_df['bucket'] == bucket_filter]
        
        filtered_df = filtered_df[filtered_df['confidence_score'] >= min_confidence]
        
        # Display data
        st.write(f"Showing {min(len(filtered_df), max_rows):,} of {len(filtered_df):,} messages")
        
        display_columns = ['confidence_score', 'bucket', 'amount', 'txn_type', 'rail', 'merchant', 'bank', 'ref_id', 'original_sms']
        available_columns = [col for col in display_columns if col in filtered_df.columns]
        
        st.dataframe(
            filtered_df[available_columns].head(max_rows),
            use_container_width=True,
            height=400
        )
        
        # Download options
        st.subheader("Download Data")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("Download Ready Transactions"):
                ready_df = df[df['bucket'] == 'BucketType.BANK_LEDGER_SUCCESS']
                csv = ready_df.to_csv(index=False)
                st.download_button(
                    label="Download CSV",
                    data=csv,
                    file_name="ready_transactions.csv",
                    mime="text/csv"
                )
        
        with col2:
            if st.button("Download LLM Candidates"):
                llm_df = df[df['bucket'] == 'BucketType.AMBIGUOUS']
                csv = llm_df.to_csv(index=False)
                st.download_button(
                    label="Download CSV",
                    data=csv,
                    file_name="llm_candidates.csv",
                    mime="text/csv"
                )
        
        with col3:
            if st.button("Download All Results"):
                csv = df.to_csv(index=False)
                st.download_button(
                    label="Download CSV",
                    data=csv,
                    file_name="pipeline_results.csv",
                    mime="text/csv"
                )

if __name__ == "__main__":
    main()
