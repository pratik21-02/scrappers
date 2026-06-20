import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import time
import PyPDF2
import streamlit.components.v1 as components
import urllib3
import base64

# Disable SSL Warnings for University Websites
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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

# --- SESSION STATE (MEMORY) INIT ---
if 'fetch_done' not in st.session_state:
    st.session_state.fetch_done = False
    st.session_state.results_data = []
    st.session_state.df = pd.DataFrame()

# --- APP LOGIC ---
URL = "https://mkbhavuni.edu.in/bhavuni_result/result.php"

# File Uploader
uploaded_files = st.file_uploader("Upload PDF Files (Any Department / Course)", type="pdf", accept_multiple_files=True)

if uploaded_files:
    # 🚀 DATA FETCHING BLOCK
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
                    clean_name = re.sub(r'[^a-zA-Z\s]', '', file.name.replace('.pdf', ''))
                    words = clean_name.split()
                    if words:
                        course = words[0].capitalize()

                # --- SUPER SMART EXTRACTION LOGIC ---
                clean_text = re.sub(r'\s+', ' ', full_text)
                
                sid_matches = list(re.finditer(r'(?<!\d)\d{10,14}(?!\d)', clean_text))
                seat_matches = list(re.finditer(r'(?<!\d)\d{6,8}(?!\d)', clean_text))
                
                # SEQUENTIAL PAIRING LOGIC
                sids = [m.group() for m in sorted(sid_matches, key=lambda x: x.start())]
                seats = [m.group() for m in sorted(seat_matches, key=lambda x: x.start())]
                
                min_len = min(len(sids), len(seats))
                for i in range(min_len):
                    sid = sids[i]
                    seat = seats[i]
                    if not any(s['sid'] == sid for s in extracted_students):
                        extracted_students.append({"seat": seat, "sid": sid, "course": course})

        total_students = len(extracted_students)
        
        if total_students == 0:
            st.error("❌ No valid Seat Numbers or SIDs found. Ensure the PDF contains University formatting.")
        else:
            st.success(f"✅ Successfully extracted {total_students} accurate pairs! Starting stable fetch process...")
            
            # 2. FETCH RESULTS FROM UNIVERSITY SERVER
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            results_data = []
            
            # CONNECTION STABILITY FIX
            session = requests.Session()
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Content-Type': 'application/x-www-form-urlencoded',
                'Referer': URL
            }
            
            try:
                # SSL Verify False for University websites to prevent blockage
                session.get(URL, headers=headers, timeout=15, verify=False)
            except:
                pass
            
            for idx, student in enumerate(extracted_students):
                seat_no = student['seat']
                sid = student['sid']
                course = student['course']
                
                progress = int(((idx) / total_students) * 100)
                progress_bar.progress(progress)
                status_text.text(f"Fetching result for {course} Seat: {seat_no} ({idx+1}/{total_students})")
                
                try:
                    payload = {
                        'sid': sid,
                        'seat_no': seat_no,
                        'search_seat_no': 'View Result'
                    }
                    
                    response = None
                    for attempt in range(3): 
                        try:
                            response = session.post(URL, data=payload, headers=headers, timeout=20, verify=False)
                            if response.status_code == 200:
                                break
                        except requests.exceptions.RequestException:
                            time.sleep(2)
                    
                    if response and response.status_code == 200:
                        soup = BeautifulSoup(response.text, 'html.parser')
                        
                        name_label = soup.find(string=re.compile(r"Student Name", re.IGNORECASE))
                        if name_label:
                            name_node = name_label.find_next('td')
                            name = " ".join(name_node.text.split()) if name_node else "Name Not Found"
                        else:
                            name = "Name Not Found"
                            
                        total_label = soup.find(lambda tag: tag.name in ['td', 'th'] and tag.text and "GRAND TOTAL" in tag.text.upper())
                        percentage_val = 0.0
                        percentage_str = "0%"
                        marks_string = "0 / 0"
                        result_status = "Unknown"
                        
                        if total_label:
                            row = total_label.find_parent('tr')
                            cells = [c.text.strip() for c in row.find_all(['td', 'th']) if c.text.strip()]
                            result_status = cells[-1] if len(cells) > 0 else "Unknown"
                            
                            # RESERVED Fix:
                            if any(err in result_status.upper() for err in ["RESERVED", "U.ST", "ABSENT", "U.F.M", "WITHHELD"]):
                                percentage_val = -1.0
                                percentage_str = "N/A"
                                marks_string = "N/A"
                            else:
                                middle_text = " ".join(cells[1:-1])
                                nums = re.findall(r'\d+', middle_text)
                                
                                if len(nums) >= 2:
                                    obtained = int(nums[-2])
                                    maximum = int(nums[-1])
                                    if maximum > 0:
                                        percentage_val = (obtained / maximum) * 100
                                        if percentage_val > 100: 
                                            percentage_val = -1.0
                                            percentage_str = "N/A"
                                            marks_string = "N/A"
                                        else:
                                            percentage_str = f"{round(percentage_val, 2)}%"
                                            marks_string = f"{obtained} / {maximum}"
                        
                        results_data.append({
                            "Seat No": seat_no,
                            "Course": course,
                            "Name": name,
                            "Marks": marks_string,
                            "Percentage": percentage_val, 
                            "Percentage Str": percentage_str,
                            "Status": result_status
                        })
                    else:
                        err_reason = f"HTTP {response.status_code}" if response else "Timeout/Blocked"
                        st.warning(f"Failed to load {seat_no} - {err_reason}")
                        
                except Exception as e:
                    st.error(f"Error fetching {seat_no}: {str(e)}")
                
                time.sleep(1)
            
            progress_bar.progress(100)
            status_text.text("All results fetched successfully!")
            
            # Save to Session State (Memory)
            if results_data:
                st.session_state.results_data = results_data
                df = pd.DataFrame(results_data)
                df = df.sort_values(by="Percentage", ascending=False).reset_index(drop=True)
                df['Rank'] = df.index + 1 
                st.session_state.df = df
                st.session_state.fetch_done = True

    # 🏆 DISPLAY FINAL MERIT LIST (Ye hamesha show hoga agar fetch_done True hai)
    if st.session_state.fetch_done and len(st.session_state.results_data) > 0:
        st.markdown("---")
        df = st.session_state.df
        
        # PREPARE CSV DATA FOR HTML INJECTION
        display_df = df[["Rank", "Course", "Seat No", "Name", "Marks", "Percentage Str", "Status"]].copy()
        display_df.columns = ["Rank", "Department", "Seat Number", "Student Name", "Marks", "Percentage", "Result Status"]
        csv_string = display_df.to_csv(index=False)
        # Encode CSV to Base64 to safely pass it to JavaScript
        csv_b64 = base64.b64encode(csv_string.encode('utf-8')).decode('utf-8')
        
        # 3.1 HTML UI GENERATOR
        html_rows = ""
        for idx, row in df.iterrows():
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
            <!-- HTML2PDF Library -->
            <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
            <style>
                @media print {{
                    .hide-print {{ display: none !important; }}
                }}
                /* Force table to fit in width during generation */
                table {{ table-layout: auto; width: 100%; }}
            </style>
        </head>
        <body class="bg-gray-50 font-sans text-gray-800 p-4 md:p-8 relative">

            <!-- PDF CONTENT WRAPPER -->
            <div id="pdf-content" class="max-w-6xl mx-auto relative bg-white p-4 sm:p-8 border border-gray-200 shadow-sm">
                
                <!-- LANDSCAPE WATERMARK LAYER -->
                <div style="position: absolute; top: 0; left: 0; right: 0; bottom: 0; pointer-events: none; z-index: 9999; background-image: url('data:image/svg+xml,%3Csvg xmlns=\\'http://www.w3.org/2000/svg\\' width=\\'800\\' height=\\'600\\'%3E%3Ctext x=\\'400\\' y=\\'300\\' transform=\\'rotate(-30, 400, 300)\\' text-anchor=\\'middle\\' dominant-baseline=\\'middle\\' font-size=\\'70\\' font-family=\\'sans-serif\\' font-weight=\\'900\\' fill=\\'rgba(99, 102, 241, 0.12)\\'%3EATOM ACADEMY%3C/text%3E%3C/svg%3E'); background-repeat: repeat;"></div>
                
                <!-- ACTUAL CONTENT -->
                <div class="relative z-10">
                    <div class="bg-white/95 backdrop-blur-sm rounded-xl border border-gray-100 p-4 sm:p-6 mb-6 flex justify-between items-center gap-4">
                        <div>
                            <h1 class="text-2xl sm:text-3xl font-black text-indigo-950 uppercase tracking-tighter">🎓 Final Merit List</h1>
                            <p class="text-green-600 text-sm font-bold mt-1"><i class="fas fa-check-circle"></i> Sorted by Highest Percentage</p>
                        </div>
                        <div class="text-right hidden sm:block">
                            <div class="text-[10px] font-bold text-gray-400 uppercase tracking-widest">Generated By</div>
                            <div class="text-lg font-black text-indigo-800">ATOM ACADEMY</div>
                        </div>
                    </div>
                    
                    <div class="bg-white/95 backdrop-blur-sm rounded-xl border border-gray-100 overflow-hidden mb-8">
                        <table class="w-full text-left border-collapse">
                            <thead>
                                <tr class="bg-slate-100/90 border-b-2 border-gray-200 text-gray-700 text-sm uppercase tracking-wider">
                                    <th class="p-3 font-bold text-center">Rank</th>
                                    <th class="p-3 font-bold text-center">Status</th>
                                    <th class="p-3 font-bold">Department</th>
                                    <th class="p-3 font-bold">Seat No</th>
                                    <th class="p-3 font-bold">Student Name</th>
                                    <th class="p-3 font-bold">Marks</th>
                                    <th class="p-3 font-bold">Percentage</th>
                                    <th class="p-3 font-bold">Result</th>
                                </tr>
                            </thead>
                            <tbody>
                                {html_rows}
                            </tbody>
                        </table>
                    </div>
                    
                    <!-- FOOTER -->
                    <div class="text-center text-[9px] sm:text-[11px] font-black text-gray-500 uppercase tracking-widest border-t-2 border-gray-300 pt-5 pb-2 mt-4">
                        © ATOM ACADEMY | GENERATED VIA OFFICIAL PORTAL | DO NOT DISTRIBUTE WITHOUT PERMISSION
                    </div>
                </div>
            </div>

            <!-- PREMIUM BUTTONS: SIDE-BY-SIDE AT BOTTOM LEFT -->
            <div class="max-w-6xl mx-auto mt-6 flex flex-row justify-start gap-4 hide-print">
                <!-- PDF BUTTON -->
                <button onclick="generatePDF()" id="downloadPdfBtn" class="bg-indigo-600 hover:bg-indigo-700 text-white px-6 py-3 rounded-xl font-black shadow-md transition-all duration-200 flex items-center justify-center gap-2 text-sm uppercase tracking-widest border-2 border-indigo-800 active:scale-95">
                    <i class="fas fa-file-pdf text-xl"></i> DOWNLOAD PDF
                </button>
                
                <!-- CSV BUTTON -->
                <button onclick="downloadCSV()" id="downloadCsvBtn" class="bg-emerald-600 hover:bg-emerald-700 text-white px-6 py-3 rounded-xl font-black shadow-md transition-all duration-200 flex items-center justify-center gap-2 text-sm uppercase tracking-widest border-2 border-emerald-800 active:scale-95">
                    <i class="fas fa-file-excel text-xl"></i> DOWNLOAD CSV
                </button>
            </div>

            <script>
                // --- CSV DOWNLOAD LOGIC (NO REFRESH) ---
                const csvBase64 = "{csv_b64}";
                
                function downloadCSV() {{
                    const csvStr = atob(csvBase64); // Decode Base64
                    const blob = new Blob([csvStr], {{ type: 'text/csv;charset=utf-8;' }});
                    const url = URL.createObjectURL(blob);
                    const link = document.createElement('a');
                    link.href = url;
                    link.setAttribute('download', 'MKBU_Merit_List.csv');
                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);
                }}

                // --- PDF DOWNLOAD LOGIC ---
                function generatePDF() {{
                    const btn = document.getElementById('downloadPdfBtn');
                    const origText = btn.innerHTML;
                    btn.innerHTML = '<i class="fas fa-spinner fa-spin text-xl"></i> PROCESSING...';
                    btn.disabled = true;
                    btn.classList.add('opacity-75', 'cursor-not-allowed');

                    const element = document.getElementById('pdf-content');
                    
                    const opt = {{
                        margin:       [10, 5, 10, 5],
                        filename:     'MKBU_Merit_List.pdf',
                        image:        {{ type: 'jpeg', quality: 0.98 }},
                        // Removed windowWidth to prevent zoom-out/blank pages
                        // scrollY: 0 prevents blank pages from scroll offsets
                        html2canvas:  {{ scale: 2, useCORS: true, letterRendering: true, scrollY: 0 }},
                        // Changed to LANDSCAPE so wide tables fit perfectly without cutting!
                        jsPDF:        {{ unit: 'mm', format: 'a4', orientation: 'landscape' }}
                    }};
                    
                    html2pdf().set(opt).from(element).save().then(() => {{
                        btn.innerHTML = origText;
                        btn.disabled = false;
                        btn.classList.remove('opacity-75', 'cursor-not-allowed');
                    }}).catch(err => {{
                        btn.innerHTML = '<i class="fas fa-exclamation-triangle"></i> ERROR';
                        setTimeout(() => {{
                            btn.innerHTML = origText;
                            btn.disabled = false;
                            btn.classList.remove('opacity-75', 'cursor-not-allowed');
                        }}, 3000);
                    }});
                }}
            </script>
        </body>
        </html>"""

        # Embed custom HTML directly inside Streamlit
        st.subheader("🏆 Your Custom Dashboard")
        components.html(html_template, height=1000, scrolling=True)
        
        # Removed the external Streamlit download button so the app NEVER refreshes!
