"""
AI Procurement Compliance Agent
Single-file application for contract review and vendor spend analysis
"""

import os
import json
import io
import base64
from pathlib import Path
import pandas as pd
import streamlit as st
from anthropic import Anthropic

# ============================================================================
# Config
# ============================================================================

API_KEY = os.environ.get("ANTHROPIC_API_KEY") # left empty for now, need to input this to make sure the code works
MODEL = "claude-opus-4-5-20251101"
SAMPLE_CSV_DATA = """vendor_id,vendor_name,category,amount_spent,invoice_date,description
V001,TechCorp Inc,Software,150000,2024-01-15,Annual software license
V001,TechCorp Inc,Software,50000,2024-03-20,Support services
V002,CloudHost Ltd,Infrastructure,200000,2024-02-10,Cloud hosting services
V002,CloudHost Ltd,Infrastructure,75000,2024-04-05,Additional storage
V003,DataSolutions,Consulting,120000,2024-01-30,Data analytics project
V004,OfficeSupply Co,Supplies,35000,2024-02-28,Office equipment
V001,TechCorp Inc,Software,50000,2024-05-10,Additional licensing"""

# ============================================================================
# PDF PARSING HELPER
# ============================================================================

def extract_text_from_pdf_base64(pdf_base64: str) -> str:
    """Extract text from PDF using Claude's vision capabilities"""
    client = Anthropic()
    
    message = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": pdf_base64,
                        },
                    },
                    {
                        "type": "text",
                        "text": "Extract all key contract terms, clauses, and important details from this document. Format as structured text with sections."
                    }
                ],
            }
        ],
    )
    
    return message.content[0].text


def parse_contract_with_ai(contract_text: str) -> dict:
    """Use Claude to extract structured contract data"""
    client = Anthropic()
    
    prompt = f"""Analyze this contract and extract key information as JSON:
    
Contract Content:
{contract_text}

Return JSON with these fields:
- vendor_name (str)
- contract_type (str)
- start_date (str)
- end_date (str)
- payment_terms (str)
- key_obligations (list)
- penalty_clauses (list)
- spending_limits (str)
- renewal_terms (str)

Return ONLY valid JSON, no markdown."""

    message = client.messages.create(
        model=MODEL,
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )
    
    response_text = message.content[0].text.strip()
    
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        return {"raw_analysis": response_text}


# ============================================================================
# Spend Analysis
# ============================================================================

def analyze_spend_data(csv_content: str) -> dict:
    """Analyze vendor spend data"""
    df = pd.read_csv(io.StringIO(csv_content))
    
    analysis = {
        "total_spend": float(df["amount_spent"].sum()),
        "vendor_count": int(df["vendor_id"].nunique()),
        "by_vendor": df.groupby("vendor_name")["amount_spent"].sum().to_dict(),
        "by_category": df.groupby("category")["amount_spent"].sum().to_dict(),
        "transactions": len(df),
        "avg_transaction": float(df["amount_spent"].mean()),
    }
    
    # Convert numpy types to native Python for JSON serialization
    analysis["by_vendor"] = {k: float(v) for k, v in analysis["by_vendor"].items()}
    analysis["by_category"] = {k: float(v) for k, v in analysis["by_category"].items()}
    
    return analysis


def generate_compliance_risks(contract: dict, spend_analysis: dict) -> dict:
    """Use Claude to identify compliance risks"""
    client = Anthropic()
    
    prompt = f"""Based on the following contract terms and actual spending, identify compliance risks:

CONTRACT TERMS:
{json.dumps(contract, indent=2)}

ACTUAL SPENDING ANALYSIS:
{json.dumps(spend_analysis, indent=2)}

Identify:
1. Budget overruns
2. Payment term violations
3. Unauthorized vendors
4. Spending category mismatches
5. Recommended actions

Return as JSON with fields:
- risks (list of dicts with: type, severity, description, impact)
- recommendations (list of action items)
- compliance_score (0-100)"""

    message = client.messages.create(
        model=MODEL,
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}]
    )
    
    response_text = message.content[0].text.strip()
    
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        return {"analysis": response_text}


# ============================================================================
# Streamlit UI
# ============================================================================

def init_session_state():
    # Initialize Streamlit session state
    if "contract_data" not in st.session_state:
        st.session_state.contract_data = None
    if "spend_analysis" not in st.session_state:
        st.session_state.spend_analysis = None
    if "compliance_report" not in st.session_state:
        st.session_state.compliance_report = None
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []


def render_dashboard():
    # Streamlit Dashboard
    st.set_page_config(page_title="Procurement Compliance Agent", layout="wide")
    
    st.title("AI Procurement Compliance Agent")
    st.markdown("Automated contract review and vendor spend analysis")
    
    init_session_state()
    
    # Check API key
    if not API_KEY:
        st.error("❌ ANTHROPIC_API_KEY environment variable not set")
        st.info("Set your API key: `export ANTHROPIC_API_KEY='your-key-here'`") # HERE you can set your key
        return
    
    # Sidebar for data input
    with st.sidebar:
        st.header("📄 Input Data")
        
        # Contract upload
        st.subheader("1. Upload Contract")
        uploaded_file = st.file_uploader("Upload PDF contract", type=["pdf"])
        
        if uploaded_file is not None:
            with st.spinner("📖 Extracting contract data..."):
                pdf_bytes = uploaded_file.read()
                pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")
                
                contract_text = extract_text_from_pdf_base64(pdf_base64)
                st.session_state.contract_data = parse_contract_with_ai(contract_text)
                st.success("Contract parsed!")
        
        # Spend data
        st.subheader("2. Vendor Spend Data")
        
        use_sample = st.checkbox("Use sample data", value=True)
        
        if use_sample:
            csv_content = SAMPLE_CSV_DATA
            st.info("Using sample spend data")
        else:
            uploaded_csv = st.file_uploader("Upload CSV", type=["csv"])
            if uploaded_csv is not None:
                csv_content = uploaded_csv.getvalue().decode("utf-8")
            else:
                csv_content = None
        
        if csv_content and st.button("📊 Analyze Spend Data"):
            with st.spinner("Analyzing spend..."):
                st.session_state.spend_analysis = analyze_spend_data(csv_content)
                st.success("Spend analysis complete!")
        
        # Generate report
        st.subheader("3. Generate Compliance Report")
        
        if (st.session_state.contract_data and 
            st.session_state.spend_analysis and 
            st.button("🔍 Generate Compliance Report")):
            
            with st.spinner("Analyzing compliance..."):
                st.session_state.compliance_report = generate_compliance_risks(
                    st.session_state.contract_data,
                    st.session_state.spend_analysis
                )
                st.success("Report generated!")
    
    # Main content area
    col1, col2 = st.columns(2)
    
    # Contract data
    with col1:
        st.subheader("📋 Contract Terms")
        if st.session_state.contract_data:
            st.json(st.session_state.contract_data)
        else:
            st.info("Upload a contract PDF to see extracted terms")
    
    # Spend analysis
    with col2:
        st.subheader(" Spend Analysis")
        if st.session_state.spend_analysis:
            spend = st.session_state.spend_analysis
            
            col_a, col_b = st.columns(2)
            with col_a:
                st.metric("Total Spend", f"${spend['total_spend']:,.0f}")
            with col_b:
                st.metric("Vendors", spend['vendor_count'])
            
            st.markdown("**By Vendor:**")
            vendor_df = pd.DataFrame(
                list(spend['by_vendor'].items()),
                columns=['Vendor', 'Amount']
            )
            st.dataframe(vendor_df, use_container_width=True)
            
            st.markdown("**By Category:**")
            category_df = pd.DataFrame(
                list(spend['by_category'].items()),
                columns=['Category', 'Amount']
            )
            st.dataframe(category_df, use_container_width=True)
        else:
            st.info("Upload spend data to see analysis")
    
    # Compliance report
    st.subheader(" Detailed Compliance Report")
    
    if st.session_state.compliance_report:
        report = st.session_state.compliance_report
        
        if "compliance_score" in report:
            score = report.get("compliance_score", 0)
            color = "🟢" if score >= 75 else "🟡" if score >= 50 else "🔴"
            st.metric("Compliance Score", f"{score}/100 {color}")
        
        if "risks" in report:
            st.markdown("**Identified Risks:**")
            for risk in report["risks"]:
                severity = risk.get("severity", "Unknown")
                color = "🔴" if severity == "HIGH" else "🟡" if severity == "MEDIUM" else "🟢"
                st.warning(f"{color} [{severity}] {risk.get('type', 'Unknown')}: {risk.get('description', '')}")
        
        if "recommendations" in report:
            st.markdown("**Recommendations:**")
            for rec in report["recommendations"]:
                st.info(f"✅ {rec}")
        
        st.json(report)
    else:
        st.info("Generate a compliance report to see results")
    
    # Interactive chat
    st.divider()
    st.subheader("💬 Interactive Questions")
    
    user_input = st.text_input("Ask about the contract or spending:")
    
    if user_input:
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        
        context = f"""
Contract Data: {json.dumps(st.session_state.contract_data)}
Spend Analysis: {json.dumps(st.session_state.spend_analysis)}
Compliance Report: {json.dumps(st.session_state.compliance_report)}
"""
        
        client = Anthropic()
        
        messages = st.session_state.chat_history.copy()
        messages[0]["content"] = f"{context}\n\nUser: {user_input}"
        
        with st.spinner("Thinking..."):
            response = client.messages.create(
                model=MODEL,
                max_tokens=500,
                messages=messages
            )
        
        assistant_response = response.content[0].text
        st.session_state.chat_history.append({"role": "assistant", "content": assistant_response})
        
        st.markdown(f"**Assistant:** {assistant_response}")
    
    # Chat history
    if st.session_state.chat_history:
        with st.expander("Chat History"):
            for msg in st.session_state.chat_history:
                if msg["role"] == "user":
                    st.write(f"👤 You: {msg['content']}")
                else:
                    st.write(f"🤖 Assistant: {msg['content']}")


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    render_dashboard()
