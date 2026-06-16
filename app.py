import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import time
import PyPDF2

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
st.markdown('<p class="sub-header">Upload Seat Number PDFs to Auto-Generate Sorted Merit Lists (For ALL Departments)</p>', unsafe_allow_html=True)

# --- APP LOGIC ---
URL = "https://mkbhavuni.edu.in/bhavuni_result/result.php"

# File Uploader - Removed specific department restriction
uploaded_files = st.file_uploader("Upload PDF Files (Any Department / Course)", type="pdf", accept_multiple_files=True)

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
                
                # Dynamic Course Name Detection from Filename
                f_low = file.name.lower()
                course = "Department"
                
                if "botany" in f_low: course = "Botany"
                elif "zoology" in f_low: course = "Zoology"
                elif "microbiology" in f_low: course = "Microbiology"
                elif "chemistry" in f_low: course = "Chemistry"
                elif "physics" in f_low: course = "Physics"
                elif "math" in f_low: course = "Mathematics"
                elif "b.com" in f_low: course = "B.Com"
                elif "b.a" in f_low: course = "B.A"
                elif "b.sc" in f_low: course = "B.Sc"
                else:
                    # Extracts first word of filename if department unknown
                    clean_name = re.sub(r'[^a-zA-Z\s]', '', file.name.replace('.pdf', ''))
                    words = clean_name.split()
                    if words:
                        course = words[0].capitalize()

                # SMART REGEX UPDATE: 
                # Seat Numbers are usually 6 to 8 digits long
                # SIDs are usually 10 to 14 digits long
                seats = re.findall(r'\b\d{6,8}\b', full_text)
                sids = re.findall(r'\b\d{10,14}\b', full_text)
                
                count = min(len(seats), len(sids))
                for i in range(count):
                    # Prevent duplicates
                    if not any(s['seat'] == seats[i] for s in extracted_students):
                        extracted_students.append({"seat": seats[i], "sid": sids[i], "course": course})

        total_students = len(extracted_students)
        
        if total_students == 0:
            st.error("❌ No valid Seat Numbers or SIDs found. Ensure the PDF contains University formatting.")
        else:
            st.success(f"✅ Successfully extracted {total_students} students! Starting fetch process...")
            
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
            
            # 3. DISPLAY FINAL MERIT LIST WITH CUSTOM UI
            if results_data:
                st.markdown("---")
                
                # Convert to DataFrame and Sort
                df = pd.DataFrame(results_data)
                df = df.sort_values(by="Percentage", ascending=False).reset_index(drop=True)
                df['Rank'] = df.index + 1 # Rank (1, 2, 3...)
                
                # 3.1 HTML UI GENERATOR
                html_rows = ""
                for idx, row in df.iterrows():
                    # Dynamic colors based on first letter of course (to look colorful for any dept)
                    dept_colors = ["bg-blue-100 text-blue-800", "bg-purple-100 text-purple-800", "bg-pink-100 text-pink-800", "bg-green-100 text-green-800", "bg-orange-100 text-orange-800"]
                    color_idx = len(row['Course']) % len(dept_colors)
                    dept_color = dept_colors[color_idx]
                    
                    status = str(row['Status']).upper()
                    if "PASS" in status: icon = "fas fa-check-circle text-green-500"
                    elif "FAIL" in status or "ATKT" in status: icon = "fas fa-times-circle text-red-500"
                    else: icon = "fas fa-exclamation-circle text-yellow-500"
                        
                    rank = row['Rank']
                    if rank == 1: rank_display = '<span class="text-yellow-500 text-xl" title="Rank 1"><i class="fas fa-trophy"></i> 1</span>'
                    elif rank == 2: rank_display = '<span class="text-gray-400 text-xl" title="Rank 2"><i class="fas fa-medal"></i> 2</span>'
                    elif rank == 3: rank_display = '<span class="text-orange-400 text-xl" title="Rank 3"><i class="fas fa-medal"></i> 3</span>'
                    else: rank_display = f'<span class="font-bold text-gray-600 text-lg">#{rank}</span>'

                    html_rows += f"""
                    <tr class="hover:bg-slate-50 transition-colors">
                        <td class="p-3 text-center border-b border-gray-200">{rank_display}</td>
                        <td class="p-3 w-10 text-center border-b border-gray-200"><i class="{icon}" title="{status}"></i></td>
                        <td class="p-3 border-b border-gray-200"><span class="px-3 py-1 rounded-full text-xs font-bold {dept_color} shadow-sm">{row['Course']}</span></td>
                        <td class="p-3 font-mono text-sm text-gray-600 border-b border-gray-200">{row['Seat No']}</td>
                        <td class="p-3 font-medium text-gray-900 border-b border-gray-200">{row['Name']}</td>
                        <td class="p-3 font-bold text-gray-900 border-b border-gray-200">{row['Marks']}</td>
                        <td class="p-3 font-black text-blue-600 border-b border-gray-200">{row['Percentage Str']}</td>
                        <td class="p-3 font-semibold text-gray-700 border-b border-gray-200">{status}</td>
                    </tr>
                    """

                html_template = f"""<!DOCTYPE html>
                <html lang="en">
                <head>
                    <meta charset="UTF-8">
                    <title>MKBU Merit List</title>
                    <script src="https://cdn.tailwindcss.com"></script>
                    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
                    <style>
                        @media print {{
                            .hide-print {{ display: none !important; }}
                            body {{ background: white; padding: 0; }}
                            .shadow-sm {{ box-shadow: none !important; }}
                            .border {{ border: none !important; }}
                        }}
                    </style>
                </head>
                <body class="bg-gray-50 font-sans text-gray-800 p-4 md:p-8">
                    <div class="max-w-6xl mx-auto">
                        <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-8 flex flex-col sm:flex-row justify-between items-center gap-4 hide-print">
                            <div>
                                <h1 class="text-2xl font-bold text-gray-900">🎓 Final Merit List</h1>
                                <p class="text-green-600 text-sm font-bold mt-1"><i class="fas fa-check-circle"></i> Sorted by Highest Percentage</p>
                            </div>
                            <button onclick="window.print()" class="bg-blue-600 hover:bg-blue-700 text-white px-6 py-2 rounded-lg font-bold shadow-md transition-colors duration-200 flex items-center gap-2">
                                <i class="fas fa-print"></i> Print / Save as PDF
                            </button>
                        </div>
                        <div class="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
                            <table class="w-full text-left border-collapse">
                                <thead>
                                    <tr class="bg-slate-100 border-b-2 border-gray-200 text-gray-700 text-sm uppercase tracking-wider">
                                        <th class="p-4 font-bold text-center">Rank</th>
                                        <th class="p-4 font-bold text-center">Status</th>
                                        <th class="p-4 font-bold">Department</th>
                                        <th class="p-4 font-bold">Seat No</th>
                                        <th class="p-4 font-bold">Student Name</th>
                                        <th class="p-4 font-bold">Marks</th>
                                        <th class="p-4 font-bold">Percentage</th>
                                        <th class="p-4 font-bold">Result</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {html_rows}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </body>
                </html>"""

                # 3.2 Embed custom HTML directly inside Streamlit
                import streamlit.components.v1 as components
                st.subheader("🏆 Your Custom Dashboard")
                components.html(html_template, height=600, scrolling=True)
                
                # 3.3 Download Buttons for PDF & Excel
                st.markdown("### 📥 Download Options")
                col1, col2 = st.columns(2)
                
                with col1:
                    st.download_button(
                        label="📄 Download Dashboard (Click to Save PDF)",
                        data=html_template,
                        file_name='MKBU_Merit_Dashboard.html',
                        mime='text/html',
                        type="primary",
                        use_container_width=True,
                        help="Ise download karke open karein aur 'Save as PDF' dabayein. UI ekdum same rahega!"
                    )
                with col2:
                    display_df = df[["Course", "Seat No", "Name", "Marks", "Percentage Str", "Status"]].copy()
                    display_df.columns = ["Department", "Seat Number", "Student Name", "Marks", "Percentage", "Result Status"]
                    csv = display_df.to_csv(index_label="Rank").encode('utf-8')
                    st.download_button(
                        label="📊 Download Excel Data (CSV)",
                        data=csv,
                        file_name='MKBU_Merit_List.csv',
                        mime='text/csv',
                        use_container_width=True
                    )
