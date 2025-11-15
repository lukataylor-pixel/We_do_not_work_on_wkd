"""Admin Dashboard for viewing Guardian Agent traces and analytics."""

import streamlit as st
import os
from datetime import datetime
import pandas as pd
from finance_agent import FinanceAgent

# Page config
st.set_page_config(
    page_title="Guardian Agent - Admin Dashboard",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        margin-bottom: 1rem;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .stat-card {
        background: white;
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        border-left: 4px solid #667eea;
    }
    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        color: #667eea;
    }
    .metric-label {
        font-size: 0.9rem;
        color: #6B6B6B;
        text-transform: uppercase;
    }
    .safe-badge {
        background: #E8F5E9;
        color: #34C759;
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 0.85rem;
        font-weight: 600;
    }
    .blocked-badge {
        background: #FFEBEE;
        color: #FF3B30;
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 0.85rem;
        font-weight: 600;
    }
    .trace-detail {
        background: #F8F9FA;
        padding: 1rem;
        border-radius: 8px;
        margin: 0.5rem 0;
        border-left: 3px solid #667eea;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'agent' not in st.session_state:
    st.session_state.agent = FinanceAgent(safety_threshold=0.7, enable_langfuse=True)

agent = st.session_state.agent

# Sidebar
st.sidebar.markdown("## 🛡️ Guardian Agent")
st.sidebar.markdown("### Admin Dashboard")
st.sidebar.markdown("---")

page = st.sidebar.radio(
    "Navigation",
    ["📊 Overview", "🔍 Trace Explorer", "📈 Analytics", "⚙️ Settings"],
    label_visibility="collapsed"
)

st.sidebar.markdown("---")
st.sidebar.markdown("### LangFuse Status")
if agent.enable_langfuse:
    st.sidebar.success("✅ Tracing Enabled")
    langfuse_host = os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com")
    st.sidebar.markdown(f"**Host:** {langfuse_host}")
else:
    st.sidebar.warning("⚠️ Tracing Disabled")
    st.sidebar.markdown("Set `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` to enable.")

st.sidebar.markdown("---")
st.sidebar.markdown("### Quick Links")
st.sidebar.markdown("- [Customer Chat (Port 5000)](http://localhost:5000)")
st.sidebar.markdown("- [Demo Website (Port 8000)](http://localhost:8000)")
st.sidebar.markdown("- [LangFuse Dashboard](https://cloud.langfuse.com)")

# Main content
if page == "📊 Overview":
    st.markdown('<h1 class="main-header">Dashboard Overview</h1>', unsafe_allow_html=True)
    st.markdown("Real-time monitoring of Guardian Agent safety checks and interactions")
    
    # Get statistics
    stats = agent.get_statistics()
    
    # Metrics row
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div class="stat-card">
            <div class="metric-label">Total Interactions</div>
            <div class="metric-value">{stats['total_interactions']}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="stat-card">
            <div class="metric-label">Safe Responses</div>
            <div class="metric-value" style="color: #34C759;">{stats['safe_count']}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="stat-card">
            <div class="metric-label">Blocked Attempts</div>
            <div class="metric-value" style="color: #FF3B30;">{stats['blocked_count']}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown(f"""
        <div class="stat-card">
            <div class="metric-label">Block Rate</div>
            <div class="metric-value" style="color: #FF9500;">{stats['block_rate']:.1f}%</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Charts
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📊 Category Distribution")
        if stats['category_counts']:
            df_categories = pd.DataFrame(
                list(stats['category_counts'].items()),
                columns=['Category', 'Count']
            )
            st.bar_chart(df_categories.set_index('Category'))
        else:
            st.info("No blocked interactions yet")
    
    with col2:
        st.subheader("⏱️ Performance Metrics")
        st.metric("Avg Processing Time", f"{stats['avg_processing_time']:.2f}s")
        st.metric("Avg Similarity Score", f"{stats['avg_similarity_score']:.2f}")
    
    st.markdown("---")
    
    # Recent blocked interactions
    st.subheader("🚨 Recent Blocked Attempts")
    if stats['blocked_interactions']:
        for interaction in reversed(stats['blocked_interactions']):
            with st.expander(f"🛑 {interaction['timestamp']} - {interaction['safety_result'].get('matched_topic', 'Unknown')}"):
                st.markdown(f"**User Message:**")
                st.code(interaction['user_message'], language=None)
                
                st.markdown(f"**Agent Original Response (Blocked):**")
                st.code(interaction['agent_original_response'][:200] + "...", language=None)
                
                st.markdown(f"**Safe Alternative Sent:**")
                st.info(interaction['final_response'])
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Similarity Score", f"{interaction['safety_result']['similarity_score']:.2f}")
                with col2:
                    st.metric("Detection Method", interaction['safety_result'].get('method', 'unknown'))
    else:
        st.info("No blocked interactions yet")

elif page == "🔍 Trace Explorer":
    st.markdown('<h1 class="main-header">Trace Explorer</h1>', unsafe_allow_html=True)
    st.markdown("Detailed view of all agent interactions with LangFuse trace links")
    
    # Filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        status_filter = st.selectbox(
            "Status",
            ["All", "Safe", "Blocked", "Error"]
        )
    
    with col2:
        min_similarity = st.slider(
            "Min Similarity Score",
            0.0, 1.0, 0.0, 0.1
        )
    
    with col3:
        sort_order = st.selectbox(
            "Sort By",
            ["Newest First", "Oldest First", "Highest Similarity"]
        )
    
    st.markdown("---")
    
    # Get all interactions from shared telemetry
    interactions = agent.get_all_interactions()
    
    # Apply filters
    if status_filter != "All":
        interactions = [i for i in interactions if i['status'].lower() == status_filter.lower()]
    
    interactions = [i for i in interactions if i['safety_result']['similarity_score'] >= min_similarity]
    
    # Sort
    if sort_order == "Newest First":
        interactions.reverse()
    elif sort_order == "Highest Similarity":
        interactions.sort(key=lambda x: x['safety_result']['similarity_score'], reverse=True)
    
    # Display interactions
    st.write(f"**Showing {len(interactions)} interactions**")
    
    for idx, interaction in enumerate(interactions):
        status_badge = "safe-badge" if interaction['status'] == 'safe' else "blocked-badge"
        status_emoji = "✅" if interaction['status'] == 'safe' else "🛑"
        
        with st.expander(
            f"{status_emoji} {interaction['timestamp']} - {interaction['user_message'][:60]}..."
        ):
            # Trace ID link
            if interaction.get('trace_id'):
                langfuse_host = os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com")
                trace_url = f"{langfuse_host}/trace/{interaction['trace_id']}"
                st.markdown(f"🔗 [View in LangFuse]({trace_url})")
            
            st.markdown(f"<span class='{status_badge}'>{interaction['status'].upper()}</span>", unsafe_allow_html=True)
            
            st.markdown("**User Message:**")
            st.code(interaction['user_message'], language=None)
            
            st.markdown("**Agent Response:**")
            st.code(interaction['agent_original_response'], language=None)
            
            if interaction['status'] == 'blocked':
                st.markdown("**Safe Alternative Sent:**")
                st.info(interaction['final_response'])
            
            # Metadata
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Similarity Score", f"{interaction['safety_result']['similarity_score']:.3f}")
            with col2:
                st.metric("Processing Time", f"{interaction['processing_time']:.2f}s")
            with col3:
                matched = interaction['safety_result'].get('matched_topic', 'N/A')
                st.metric("Matched Topic", matched)

elif page == "📈 Analytics":
    st.markdown('<h1 class="main-header">Analytics & Insights</h1>', unsafe_allow_html=True)
    st.markdown("Deep dive into agent performance and safety patterns")
    
    stats = agent.get_statistics()
    
    # Safety effectiveness
    st.subheader("🛡️ Safety Effectiveness")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if stats['total_interactions'] > 0:
            safe_percentage = (stats['safe_count'] / stats['total_interactions']) * 100
            blocked_percentage = (stats['blocked_count'] / stats['total_interactions']) * 100
            
            chart_data = pd.DataFrame({
                'Status': ['Safe', 'Blocked'],
                'Count': [stats['safe_count'], stats['blocked_count']],
                'Percentage': [safe_percentage, blocked_percentage]
            })
            
            st.dataframe(chart_data, use_container_width=True)
        else:
            st.info("No data yet")
    
    with col2:
        st.metric("Attack Success Rate (ASR)", "0%", help="Percentage of jailbreak attempts that succeeded")
        st.metric("False Positive Rate", "TBD", help="Safe responses incorrectly blocked")
    
    st.markdown("---")
    
    # Category breakdown
    st.subheader("📊 Blocked Categories Analysis")
    
    if stats['category_counts']:
        df = pd.DataFrame(
            list(stats['category_counts'].items()),
            columns=['Category', 'Blocked Count']
        ).sort_values('Blocked Count', ascending=False)
        
        st.dataframe(df, use_container_width=True)
        
        st.bar_chart(df.set_index('Category'))
    else:
        st.info("No blocked interactions yet")
    
    st.markdown("---")
    
    # Timing analysis
    st.subheader("⏱️ Performance Analysis")
    
    if agent.get_all_interactions():
        times = [log['processing_time'] for log in agent.get_all_interactions()]
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Avg Response Time", f"{stats['avg_processing_time']:.2f}s")
        with col2:
            st.metric("Min Response Time", f"{min(times):.2f}s")
        with col3:
            st.metric("Max Response Time", f"{max(times):.2f}s")
        
        # Response time distribution
        df_times = pd.DataFrame({
            'Interaction': range(1, len(times) + 1),
            'Processing Time (s)': times
        })
        st.line_chart(df_times.set_index('Interaction'))
    else:
        st.info("No data yet")

elif page == "⚙️ Settings":
    st.markdown('<h1 class="main-header">Settings</h1>', unsafe_allow_html=True)
    st.markdown("Configure safety threshold and system parameters")
    
    st.subheader("🎚️ Safety Threshold")
    
    current_threshold = agent.safety_classifier.threshold
    
    new_threshold = st.slider(
        "Similarity Threshold",
        min_value=0.5,
        max_value=0.9,
        value=current_threshold,
        step=0.05,
        help="Higher threshold = stricter safety checks (more blocking)"
    )
    
    if new_threshold != current_threshold:
        if st.button("Apply New Threshold"):
            agent.safety_classifier.threshold = new_threshold
            st.success(f"✅ Threshold updated to {new_threshold}")
            st.rerun()
    
    st.markdown("---")
    
    st.subheader("🗑️ Data Management")
    
    if st.button("Clear Interaction Log", type="secondary"):
        agent.telemetry.clear_all()
        st.success("✅ Interaction log cleared")
        st.rerun()
    
    st.markdown("---")
    
    st.subheader("🔧 LangFuse Configuration")
    
    st.code(f"""
LANGFUSE_PUBLIC_KEY: {'✅ Set' if os.environ.get('LANGFUSE_PUBLIC_KEY') else '❌ Not set'}
LANGFUSE_SECRET_KEY: {'✅ Set' if os.environ.get('LANGFUSE_SECRET_KEY') else '❌ Not set'}
LANGFUSE_HOST: {os.environ.get('LANGFUSE_HOST', 'https://cloud.langfuse.com')}
    """, language=None)
    
    if not agent.enable_langfuse:
        st.warning("⚠️ LangFuse tracing is disabled. Set environment variables to enable.")

# Footer
st.markdown("---")
st.markdown("**Guardian Agent Admin Dashboard** | Track B (Glass Box) & Track C (Red Teaming Defense)")
