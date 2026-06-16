import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import time
import PyPDF2
import io

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="MKBU Merit List Generator", page_icon="🎓", layout="wide")

# --- CUSTOM CSS FOR STYLING ---
st.markdown("""
    <style>
    .main-header { font-size: 2.5rem; font-weight: 800; color: #1E3A8A; text-align: center; margin-bottom: 0px; }
    .sub-header { font-size: 1.1rem; color: #64748B; text-align: center; margin-bottom: 30px; }
    .stProgress .st-bo { background-color: #2563EB; }
    .success-msg { color: #16A34A; font-weight: bold; }
    .error-msg { color: #DC2626; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-header">🎓 MKBU Smart Merit App</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Upload Seat Number PDFs to Auto-Generate Sorted Merit Lists</p>', unsafe_allow_html=True)

# --- APP LOGIC ---
URL = "https://mkbhavuni.edu.in/bhavuni_result/result.php"

# File Uploader
uploaded_files = st.file_uploader("Upload PDF Files (Botany, Zoology, Microbiology)", type="pdf", accept_multiple_files=True)

if uploaded_files:
    if st.button("🚀 Fetch Results & Generate Merit List", type="primary", use_container_width=True):
        
        extracted_students = []
        
        # 1. READ PDFs AND EXTRACT SEAT NOS & SIDs
        with st.spinner("Extracting Data from PDFs..."):
            for file in uploaded_files:
                pdf_reader = PyPDF2.PdfReader(file)
                full_text = ""
                for page in pdf_reader.pages:
                    full_text += page.extract_text() + " "
                
                # Determine Course
                t_low = full_text.lower()
                f_low = file.name.lower()
                course = "Unknown"
                if "botany" in t_low or "botany" in f_low: course = "Botany"
                elif "zoology" in t_low or "zoology" in f_low: course = "Zoology"
                elif "microbiology" in t_low or "microbiology" in f_low: course = "Microbiology"
                
                # Regex to find Seat Nos and SIDs
                seats = re.findall(r'\b26\d{6}\b', full_text)
                sids = re.findall(r'\b51\d{8}\b', full_text)
                
                count = min(len(seats), len(sids))
                for i in range(count):
                    # Prevent duplicates
                    if not any(s['seat'] == seats[i] for s in extracted_students):
                        extracted_students.append({"seat": seats[i], "sid": sids[i], "course": course})

        total_students = len(extracted_students)
        
        if total_students == 0:
            st.error("No valid Seat Numbers or SIDs found in the uploaded PDFs.")
        else:
            st.success(f"Successfully extracted {total_students} students! Starting fetch process...")
            
            # 2. FETCH RESULTS FROM UNIVERSITY SERVER
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            results_data = []
            
            for idx, student in enumerate(extracted_students):
                seat_no = student['seat']
                sid = student['sid']
                course = student['course']
                
                # Update progress
                progress = int(((idx) / total_students) * 100)
                progress_bar.progress(progress)
                status_text.text(f"Fetching result for {course} Seat: {seat_no} ({idx+1}/{total_students})")
                
                try:
                    payload = {
                        'sid': sid,
                        'seat_no': seat_no,
                        'search_seat_no': 'View Result'
                    }
                    
                    # Request directly from server (No CORS issue in Python!)
                    response = requests.post(URL, data=payload, timeout=10)
                    
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.text, 'html.parser')
                        
                        # Find Name
                        name_label = soup.find(string=re.compile(r"Student Name", re.IGNORECASE))
                        if name_label:
                            name_node = name_label.find_next('td')
                            name = " ".join(name_node.text.split()) if name_node else "Name Not Found"
                        else:
                            name = "Name Not Found"
                            
                        # Find Marks
                        total_label = soup.find(lambda tag: tag.name in ['td', 'th'] and tag.text and "GRAND TOTAL" in tag.text.upper())
                        percentage_val = 0.0
                        percentage_str = "0%"
                        marks_string = "0 / 0"
                        result_status = "Unknown"
                        
                        if total_label:
                            row = total_label.find_parent('tr')
                            cells = [c.text.strip() for c in row.find_all(['td', 'th']) if c.text.strip()]
                            result_status = cells[-1] if len(cells) > 0 else "Unknown"
                            
                            middle_text = " ".join(cells[1:-1])
                            nums = re.findall(r'\d+', middle_text)
                            
                            if len(nums) >= 2:
                                obtained = int(nums[-2])
                                maximum = int(nums[-1])
                                if maximum > 0:
                                    percentage_val = (obtained / maximum) * 100
                                    percentage_str = f"{round(percentage_val, 2)}%"
                                    marks_string = f"{obtained} / {maximum}"
                        
                        results_data.append({
                            "Seat No": seat_no,
                            "Course": course,
                            "Name": name,
                            "Marks": marks_string,
                            "Percentage": percentage_val,  # Used for sorting
                            "Percentage Str": percentage_str,
                            "Status": result_status
                        })
                    else:
                        st.warning(f"Failed to load {seat_no}")
                        
                except Exception as e:
                    st.error(f"Error fetching {seat_no}: {str(e)}")
                
                time.sleep(0.3) # Short delay
            
            progress_bar.progress(100)
            status_text.text("All results fetched successfully!")
            
            # 3. DISPLAY FINAL MERIT LIST
            if results_data:
                st.markdown("---")
                st.subheader("🏆 Final Merit List")
                
                # Convert to DataFrame and Sort
                df = pd.DataFrame(results_data)
                df = df.sort_values(by="Percentage", ascending=False).reset_index(drop=True)
                df.index = df.index + 1 # Rank (1, 2, 3...)
                
                # Create a display friendly DataFrame
                display_df = df[["Course", "Seat No", "Name", "Marks", "Percentage Str", "Status"]].copy()
                display_df.columns = ["Department", "Seat Number", "Student Name", "Marks", "Percentage", "Result Status"]
                
                # Display table
                st.dataframe(display_df, use_container_width=True, height=600)
                
                # Download as CSV functionality
                csv = display_df.to_csv(index_label="Rank").encode('utf-8')
                st.download_button(
                    label="📥 Download Merit List (Excel/CSV)",
                    data=csv,
                    file_name='MKBU_Merit_List.csv',
                    mime='text/csv',
                    type="primary"
                )
