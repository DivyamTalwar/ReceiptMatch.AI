import streamlit as st
from database.connection import connect_to_db, check_db_connection
from ui.components import UIComponents
import asyncio
import os
import pandas as pd
import json
from services.email_pipeline import EmailProcessingPipeline
from services.email_service import EmailServiceManager
from services.pdf_processor import ReceiptPDFProcessor
from database.operations import add_receipt_transaction, get_all_receipt_transactions, get_all_bank_transactions, add_bank_transaction
from models.schema import BankTransaction
from utils.helpers import GeneralHelpers
from datetime import datetime
import plotly.express as px

class ReceiptReconciliationApp:
    """
    Main Streamlit application with comprehensive navigation and page management.
    """
    
    def __init__(self):
        connect_to_db()
        self.pages = {
            "🏠 Dashboard": self.dashboard_page,
            "📧 Email Processing": self.email_processing_page,
            "📄 Receipt Upload": self.manual_upload_page,
            "🏦 Bank Statement Upload": self.bank_upload_page,
            "🔄 Reconciliation": self.reconciliation_page,
            "📊 Analytics": self.analytics_page,
        }
        
    def run(self):
        st.set_page_config(
            page_title="Receipt Reconciliation System",
            page_icon="💰",
            layout="wide",
            initial_sidebar_state="expanded"
        )
        
        with st.sidebar:
            st.title("💰 Receipt Reconciliation")
            selected_page = st.selectbox("Navigate", list(self.pages.keys()))
            self._display_system_status()
            
        self.pages[selected_page]()

    def _display_system_status(self):
        """
        Displays the current status of the system's backend components.
        """
        st.sidebar.subheader("System Status")
        if check_db_connection():
            st.sidebar.success("✅ Database Connected")
        else:
            st.sidebar.error("❌ Database Disconnected")

    def dashboard_page(self):
        st.title("🏠 Dashboard")
        
        # Add reconciliation stats
        try:
            from services.reconciliation import AdvancedReconciliationEngine
            receipts = get_all_receipt_transactions()
            bank_transactions = get_all_bank_transactions()
            
            if receipts and bank_transactions:
                receipts_list = [json.loads(r.to_json()) for r in receipts]
                bank_list = [json.loads(b.to_json()) for b in bank_transactions]
                engine = AdvancedReconciliationEngine()
                results = engine.reconcile_transactions(receipts_list, bank_list)
                matched_count = len(results["matches"])
            else:
                matched_count = 0
        except:
            matched_count = 0
        
        stats = {
            'total_receipts': len(get_all_receipt_transactions()),
            'total_bank_transactions': len(get_all_bank_transactions()),
            'matched_transactions': matched_count
        }

        col1, col2, col3 = st.columns(3)
        with col1:
            UIComponents.metric_card("Total Receipts", stats['total_receipts'])
        with col2:
            UIComponents.metric_card("Bank Transactions", stats['total_bank_transactions'])
        with col3:
            UIComponents.metric_card("Matched Transactions", stats['matched_transactions'])

    def email_processing_page(self):
        st.title("📧 Email Processing")
        st.markdown("=" * 50)
        
        st.markdown("### Email Configuration Section")
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.markdown("#### Email Provider")
            provider = st.selectbox(
                "Choose Provider:",
                ["gmail", "outlook", "yahoo"],
                key="email_provider"
            )
            
            if provider == "gmail":
                st.info("📝 Gmail requires app password")
            elif provider == "yahoo":
                st.info("📝 Yahoo requires app password") 
            elif provider == "outlook":
                st.info("📝 Outlook uses regular password")
        
        with col2:
            st.markdown("#### Configuration Form")
            
            email_address = st.text_input("Email Address:", placeholder="your_test@gmail.com")
            
            if provider in ["gmail", "yahoo"]:
                password = st.text_input("App Password:", type="password", placeholder="abcd efgh ijkl mnop")
            else:
                password = st.text_input("Password:", type="password")
            
            if st.button("🔄 Start Processing", type="primary"):
                if email_address and password:
                    with st.spinner("Processing emails..."):
                        pipeline = EmailProcessingPipeline(provider, email_address, password)
                        processed_receipts = asyncio.run(pipeline.run())
                        
                        self.display_processing_progress(processed_receipts)
                        self.display_extracted_data(processed_receipts)
                else:
                    st.warning("Please enter both email and password")

    def manual_upload_page(self):
        st.title("📄 Receipt Upload")

        uploaded_files = st.file_uploader("Choose PDF files", accept_multiple_files=True, type="pdf")
        
        if uploaded_files:
            for uploaded_file in uploaded_files:
                temp_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'uploads')
                if not os.path.exists(temp_dir):
                    os.makedirs(temp_dir)
                
                file_path = os.path.join(temp_dir, uploaded_file.name)
                with open(file_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())

                with st.spinner(f"Processing {uploaded_file.name}..."):
                    pdf_processor = ReceiptPDFProcessor()
                    
                    # 🚀 USE BYPASS CLEANING FOR MANUAL UPLOADS
                    result = pdf_processor.process_receipt(file_path, bypass_cleaning=True)

                    if "error" not in result:
                        st.success(f"Successfully processed {uploaded_file.name}")
                        st.json(result)
                        transaction_id = GeneralHelpers.generate_unique_id("receipt")
                        receipt_data = {
                            "transaction_id": transaction_id,
                            "transaction_date": result.get("transaction_date"),  # Changed from "date"
                            "vendor_name": result.get("vendor"),
                            "amount": result.get("amount"),
                            "tax_amount": result.get("tax"),
                            "category": result.get("category"),
                            "description": " ".join(result.get("items", [])),
                            "receipt_filename": uploaded_file.name,
                            "receipt_path": file_path,
                            "extraction_confidence": result.get("confidence"),
                            "processing_status": "processed",
                            "extracted_data": result
                        }

                        # Ensure transaction_date is properly formatted
                        if receipt_data["transaction_date"]:
                            if isinstance(receipt_data["transaction_date"], str):
                                try:
                                    receipt_data["transaction_date"] = datetime.strptime(receipt_data["transaction_date"], "%Y-%m-%d")
                                except ValueError:
                                    receipt_data["transaction_date"] = datetime.now()
                            elif not isinstance(receipt_data["transaction_date"], datetime):
                                receipt_data["transaction_date"] = datetime.now()
                        else:
                            receipt_data["transaction_date"] = datetime.now()  # Provide default
                        add_receipt_transaction(receipt_data)
                    else:
                        st.error(f"Failed to process {uploaded_file.name}. Error: {result['error']}")

    def bank_upload_page(self):
        st.title("🏦 Bank Statement Upload")

        uploaded_file = st.file_uploader("Choose a CSV file", type="csv")

        if uploaded_file:
            df = pd.read_csv(uploaded_file)
            st.write("### Preview of your data")
            st.write(df.head())

            st.subheader("Map your columns")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                date_col = st.selectbox("Date Column", df.columns)
            with col2:
                desc_col = st.selectbox("Description Column", df.columns)
            with col3:
                amount_col = st.selectbox("Amount Column", df.columns)
            with col4:
                type_col = st.selectbox("Transaction Type Column", df.columns)

            if st.button("Process Bank Statement"):
                with st.spinner("Processing bank statement..."):
                    total_transactions = len(df)
                    total_debits = df[df[amount_col] < 0][amount_col].sum()
                    total_credits = df[df[amount_col] > 0][amount_col].sum()
                    net_amount = df[amount_col].sum()
                    date_range = f"{pd.to_datetime(df[date_col]).min().date()} to {pd.to_datetime(df[date_col]).max().date()}"

                    for index, row in df.iterrows():
                        transaction_id = GeneralHelpers.generate_unique_id("bank")
                        bank_data = {
                            "transaction_id": transaction_id,
                            "transaction_date": pd.to_datetime(row[date_col]),
                            "description": row[desc_col],
                            "amount": float(row[amount_col]),
                            "transaction_type": row[type_col].lower(),
                            "account_number": "N/A",
                            "upload_batch_id": uploaded_file.name
                        }
                        add_bank_transaction(bank_data)
                    
                    st.success("Bank statement processed successfully!")
                    
                    st.markdown("### Upload Summary")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Total Transactions", total_transactions)
                        st.metric("Date Range", date_range)
                    with col2:
                        st.metric("Total Debits", f"${total_debits:,.2f}")
                        st.metric("Total Credits", f"${total_credits:,.2f}")
                    st.metric("Net Amount", f"${net_amount:,.2f}")
                    
                    st.info("💾 All transactions saved to database!")

    def reconciliation_page(self):
        st.title("🔄 Reconciliation")

        if st.button("Run Reconciliation"):
            with st.spinner("Reconciling transactions..."):
                from services.reconciliation import AdvancedReconciliationEngine
                receipts = get_all_receipt_transactions()
                bank_transactions = get_all_bank_transactions()
                receipts_list = [json.loads(r.to_json()) for r in receipts]
                bank_list = [json.loads(b.to_json()) for b in bank_transactions]
                engine = AdvancedReconciliationEngine()
                results = engine.reconcile_transactions(receipts_list, bank_list)
                self.display_reconciliation_results(results)

    def display_reconciliation_results(self, results):
        st.success("✅ Reconciliation complete!")
        
        # Summary metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("🔗 Matches Found", len(results["matches"]))
        with col2:
            st.metric("📄 Unmatched Receipts", len(results["unmatched_ledger"]))
        with col3:
            st.metric("🏦 Unmatched Bank Transactions", len(results["unmatched_bank"]))
        
        # Enhanced matches display
        if results["matches"]:
            st.subheader("🔗 Transaction Matches")
            for i, match in enumerate(results["matches"]):
                with st.expander(f"Match {i+1}: {match['receipt'].get('vendor_name', 'Unknown')} ↔ {match['bank_transaction']['description']}", 
                               expanded=False):
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("**📄 Receipt**")
                        st.write(f"Vendor: {match['receipt'].get('vendor_name', 'Unknown')}")
                        st.write(f"Amount: ${match['receipt'].get('amount', 0):.2f}")
                        st.write(f"Date: {match['receipt'].get('transaction_date', 'Unknown')}")
                        st.write(f"Confidence: {match['receipt'].get('extraction_confidence', 0):.1%}")
                    
                    with col2:
                        st.markdown("**🏦 Bank Transaction**")
                        st.write(f"Description: {match['bank_transaction']['description']}")
                        st.write(f"Amount: ${match['bank_transaction']['amount']:.2f}")
                        st.write(f"Date: {match['bank_transaction']['transaction_date']}")
                        st.write(f"Type: {match['bank_transaction']['transaction_type'].title()}")
                    
                    # Match quality indicator
                    confidence = match['confidence']
                    if confidence > 0.9:
                        st.success(f"🎯 Excellent Match ({confidence:.1%})")
                    elif confidence > 0.7:
                        st.warning(f"⚠️ Good Match ({confidence:.1%})")
                    else:
                        st.error(f"❌ Poor Match ({confidence:.1%})")
        
        # Show unmatched transactions in organized tables
        if results["unmatched_ledger"]:
            st.subheader("📄 Unmatched Receipts")
            unmatched_receipts_df = pd.DataFrame([
                {
                    "Vendor": r.get('vendor_name', 'Unknown'),
                    "Amount": f"${r.get('amount', 0):.2f}",
                    "Date": str(r.get('transaction_date', 'Unknown'))[:10],
                    "Confidence": f"{r.get('extraction_confidence', 0):.1%}",
                    "File": r.get('receipt_filename', 'Unknown')
                }
                for r in results["unmatched_ledger"]
            ])
            st.dataframe(unmatched_receipts_df, use_container_width=True)
        
        if results["unmatched_bank"]:
            st.subheader("🏦 Unmatched Bank Transactions") 
            unmatched_bank_df = pd.DataFrame([
                {
                    "Description": b['description'],
                    "Amount": f"${b['amount']:.2f}",
                    "Date": str(b['transaction_date'])[:10],
                    "Type": b['transaction_type'].title()
                }
                for b in results["unmatched_bank"]
            ])
            st.dataframe(unmatched_bank_df, use_container_width=True)

    def analytics_page(self):
        st.title("📊 Analytics")
        
        if st.button("Clean Up Duplicates"):
            try:
                self.cleanup_duplicate_transactions()
            except Exception as e:
                st.error(f"❌ Cleanup failed: {str(e)}")

        receipts = get_all_receipt_transactions()
        if not receipts:
            st.warning("No receipt data to analyze.")
            st.info("💡 Upload some receipts first to see analytics!")
            return
        
        try:
            # Convert to DataFrame
            df = pd.DataFrame([json.loads(r.to_json()) for r in receipts])
            
            # 🔧 SAFE DATA CONVERSION with error handling
            def safe_convert_date(x):
                try:
                    if isinstance(x, dict) and '$date' in x:
                        return pd.to_datetime(x['$date'], unit='ms')
                    return pd.to_datetime(x)
                except:
                    return pd.to_datetime('today')  # Fallback
            
            def safe_convert_amount(x):
                try:
                    if isinstance(x, dict) and '$numberDecimal' in x:
                        return float(x['$numberDecimal'])
                    return float(x)
                except:
                    return 0.0  # Fallback
            
            # Apply conversions
            df['transaction_date'] = df['transaction_date'].apply(safe_convert_date)
            df['amount'] = df['amount'].apply(safe_convert_amount)
            
            # 🎯 CREATE CLEAN DATAFRAME with only needed columns
            clean_df = pd.DataFrame({
                'transaction_date': df['transaction_date'],
                'amount': df['amount'],
                'category': df['category'].astype(str)  # Ensure string type
            })
            
            # Remove any rows with invalid data
            clean_df = clean_df.dropna()
            clean_df = clean_df[clean_df['amount'] > 0]  # Remove zero amounts
            
            if len(clean_df) == 0:
                st.warning("⚠️ No valid transaction data found for analytics.")
                st.info("💡 Check your receipt data quality.")
                return
            
            # 📊 SPENDING OVER TIME (Enhanced Debug)
            st.subheader("📈 Spending Over Time")
            try:
                monthly_spending = clean_df.groupby(
                    clean_df['transaction_date'].dt.to_period("M")
                )['amount'].sum()
                
                st.write(f"**Debug Info:** {len(monthly_spending)} months of data found")
                st.write("Monthly spending data:", monthly_spending)
                
                if len(monthly_spending) > 1:  # Need at least 2 points for a line
                    st.line_chart(monthly_spending)
                else:
                    st.info("📅 Need transactions from multiple months for time series.")
                    st.bar_chart(monthly_spending)  # Show as bar chart instead
                    
            except Exception as e:
                st.error(f"❌ Time series error: {str(e)}")

            # 📊 SPENDING BY CATEGORY (Enhanced Debug)  
            st.subheader("🏷️ Spending by Category")
            try:
                category_spending = clean_df.groupby('category')['amount'].sum()
                
                st.write(f"**Debug Info:** {len(category_spending)} categories found")
                st.write("Category spending data:", category_spending)
                
                if len(category_spending) > 1:  # Need multiple categories
                    fig = px.pie(
                        values=category_spending.values,
                        names=category_spending.index,
                        title="Spending Distribution by Category"
                    )
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("🏷️ All transactions in same category - showing bar chart instead")
                    st.bar_chart(category_spending)
                    
            except Exception as e:
                st.error(f"❌ Category chart error: {str(e)}")
                
            # 📊 SUMMARY STATISTICS
            st.subheader("📋 Summary Statistics")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("💰 Total Spending", f"${clean_df['amount'].sum():.2f}")
            with col2:
                st.metric("📄 Total Receipts", len(clean_df))
            with col3:
                st.metric("📅 Date Range", f"{len(clean_df['transaction_date'].dt.date.unique())} days")
            with col4:
                st.metric("💳 Avg Transaction", f"${clean_df['amount'].mean():.2f}")
                
            # 📊 RECENT TRANSACTIONS TABLE
            st.subheader("🕒 Recent Transactions")
            recent_df = clean_df.sort_values('transaction_date', ascending=False).head(10)
            display_df = recent_df.copy()
            display_df['transaction_date'] = display_df['transaction_date'].dt.strftime('%Y-%m-%d')
            display_df['amount'] = display_df['amount'].apply(lambda x: f"${x:.2f}")
            
            st.dataframe(
                display_df[['transaction_date', 'amount', 'category']].rename(columns={
                    'transaction_date': 'Date',
                    'amount': 'Amount', 
                    'category': 'Category'
                }),
                use_container_width=True
            )
            
        except Exception as e:
            st.error(f"❌ Analytics processing failed: {str(e)}")
            st.info("🔧 Try cleaning up duplicates first, or check your receipt data quality.")
            
            # Debug information
            if st.checkbox("🔍 Show Debug Info"):
                st.code(f"Error details: {str(e)}")
                try:
                    st.write("Sample data structure:")
                    if receipts:
                        sample = json.loads(receipts[0].to_json())
                        st.json(sample)
                except:
                    st.write("Could not display sample data")

    def display_processing_progress(self, pipeline_results):
        st.markdown("### 🔄 Processing emails...")
        progress_bar = st.progress(0)
        status_text = st.empty()
        for i in range(101):
            progress_bar.progress(i)
            if i < 100:
                status_text.text(f'Progress: {"█" * (i//10)}{"░" * (10-i//10)} {i}%')
            else:
                status_text.text('Progress: ██████████ 100%')
        st.success("✅ Processing complete!")
    
        # 📊 REAL EMAIL PROCESSING STATISTICS
        if isinstance(pipeline_results, dict) and 'stats' in pipeline_results:
            # If pipeline returns statistics
            stats = pipeline_results['stats']
            processed_receipts = pipeline_results.get('receipts', [])
            
            total_emails = stats.get('total_emails', len(processed_receipts))
            successful = stats.get('successful', len(processed_receipts))
            failed = stats.get('failed', 0)
        else:
            # Fallback to current logic
            processed_receipts = pipeline_results if isinstance(pipeline_results, list) else []
            total_emails = len(processed_receipts)
            successful = len(processed_receipts)
            failed = 0
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("📧 Total Emails", total_emails)
        with col2:
            st.metric("✅ Processed", successful)
        with col3:
            st.metric("❌ Failed", failed)
            
        # 📈 SUCCESS RATE INDICATOR
        if total_emails > 0:
            success_rate = (successful / total_emails) * 100
            if success_rate == 100:
                st.success(f"🎯 Perfect Success Rate: {success_rate:.0f}%")
            elif success_rate >= 80:
                st.info(f"✅ Good Success Rate: {success_rate:.1f}%")
            else:
                st.warning(f"⚠️ Success Rate: {success_rate:.1f}%")

    def display_extracted_data(self, processed_receipts):
        if processed_receipts:
            st.markdown("### 📊 Extracted Data:")
            for i, receipt in enumerate(processed_receipts, 1):
                with st.expander(f"Receipt {i}: {receipt.get('vendor_name', 'Unknown Vendor')}", expanded=True):
                    transaction_date = receipt.get('transaction_date')
                    date_str = str(transaction_date).split('T')[0] if transaction_date else None
                    
                    formatted_data = {
                        "date": date_str,
                        "vendor": receipt.get('vendor_name'),
                        "amount": receipt.get('amount'),
                        "category": receipt.get('category', 'retail'),
                        "tax": receipt.get('tax_amount'),
                        "confidence": receipt.get('confidence')
                    }
                    st.json(formatted_data)
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write("**Transaction ID:**", receipt.get('transaction_id'))
                        st.write("**File:**", receipt.get('receipt_filename'))
                    with col2:
                        st.write("**Processing Status:**", receipt.get('processing_status', 'processed').title())
                        st.write("**Confidence:**", f"{receipt.get('confidence', 0):.1%}")

    def cleanup_duplicate_transactions(self):
        """Remove duplicate bank transactions from multiple uploads"""
        # Get all bank transactions
        all_bank = get_all_bank_transactions()
        
        # Group by description + amount + date
        seen = {}
        duplicates = []
        
        for txn in all_bank:
            key = (txn.description, txn.amount, txn.transaction_date)
            if key in seen:
                duplicates.append(txn.id)  # or txn._id depending on your model
            else:
                seen[key] = txn.id  # or txn._id
        
        # Delete duplicates
        if duplicates:
            BankTransaction.objects(id__in=duplicates).delete()
            st.success(f"🗑️ Cleaned {len(duplicates)} duplicate transactions")
        else:
            st.info("✨ No duplicates found - database is clean!")
