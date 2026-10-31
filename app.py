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
import json

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
        csv_b64 = base64.b64encode(csv_string.encode('utf-8')).decode('utf-8')
        
        # PREPARE CLEAN JSON DATA FOR VECTOR PDF ENGINE (100% Mobile & PC Compatible)
        pdf_rows_data = []
        for idx, row in df.iterrows():
            pdf_rows_data.append({
                "rank": int(row['Rank']),
                "status": str(row['Status']).upper(),
                "dept": str(row['Course']),
                "seat": str(row['Seat No']),
                "name": str(row['Name']),
                "marks": str(row['Marks']),
                "perc": str(row['Percentage Str'])
            })
        pdf_rows_json = json.dumps(pdf_rows_data)
        
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
            if rank == 1: rank_display = '<span class="text-yellow-500 text-xs sm:text-lg font-bold" title="Rank 1"><i class="fas fa-trophy"></i> 1</span>'
            elif rank == 2: rank_display = '<span class="text-gray-400 text-xs sm:text-lg font-bold" title="Rank 2"><i class="fas fa-medal"></i> 2</span>'
            elif rank == 3: rank_display = '<span class="text-orange-400 text-xs sm:text-lg font-bold" title="Rank 3"><i class="fas fa-medal"></i> 3</span>'
            else: rank_display = f'<span class="font-bold text-gray-600 text-[10px] sm:text-sm">#{rank}</span>'

            # RESPONSIVE PADDING & FONTS SO MOBILE PREVIEW FITS ALL COLUMNS CLEANLY
            html_rows += f"""
            <tr class="hover:bg-slate-50 transition-colors">
                <td class="py-1.5 px-1 sm:p-2.5 text-center border-b border-gray-200 whitespace-nowrap">{rank_display}</td>
                <td class="py-1.5 px-1 sm:p-2.5 text-center border-b border-gray-200"><i class="{icon} text-[10px] sm:text-sm" title="{status}"></i></td>
                <td class="py-1.5 px-1 sm:p-2.5 border-b border-gray-200 whitespace-nowrap"><span class="px-1.5 py-0.5 sm:px-2 sm:py-1 rounded-full text-[8px] sm:text-[10px] font-bold {dept_color} shadow-sm">{row['Course']}</span></td>
                <td class="py-1.5 px-1 sm:p-2.5 font-mono text-[9px] sm:text-xs text-gray-600 border-b border-gray-200 whitespace-nowrap">{row['Seat No']}</td>
                <td class="py-1.5 px-1 sm:p-2.5 font-medium text-[9px] sm:text-xs text-gray-900 border-b border-gray-200 leading-tight">{row['Name']}</td>
                <td class="py-1.5 px-1 sm:p-2.5 font-bold text-[9px] sm:text-xs text-gray-900 border-b border-gray-200 whitespace-nowrap">{row['Marks']}</td>
                <td class="py-1.5 px-1 sm:p-2.5 font-black text-blue-600 text-[9px] sm:text-sm border-b border-gray-200 whitespace-nowrap">{row['Percentage Str']}</td>
                <td class="py-1.5 px-1 sm:p-2.5 font-semibold text-[8px] sm:text-xs text-gray-700 border-b border-gray-200 whitespace-nowrap">{status}</td>
            </tr>
            """

        html_template = f"""<!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>MKBU Merit List</title>
            <script src="https://cdn.tailwindcss.com"></script>
            <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
            <!-- Pure Vector PDF Libraries (jsPDF + AutoTable) - Zero Cut-off & 100% Mobile Working -->
            <script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
            <script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf-autotable/3.8.2/jspdf.plugin.autotable.min.js"></script>
            <style>
                table {{ table-layout: auto; width: 100%; }}
                ::-webkit-scrollbar {{ height: 5px; width: 5px; }}
                ::-webkit-scrollbar-track {{ background: #f1f1f1; border-radius: 4px; }}
                ::-webkit-scrollbar-thumb {{ background: #c7d2fe; border-radius: 4px; }}
            </style>
        </head>
        <body class="bg-gray-50 font-sans text-gray-800 p-1 sm:p-4 md:p-6 relative">

            <!-- DASHBOARD PREVIEW WRAPPER -->
            <div id="pdf-content" class="max-w-5xl mx-auto relative bg-white p-2 sm:p-6 border border-gray-200 rounded-xl shadow-sm w-full overflow-hidden">
                
                <!-- PREVIEW WATERMARK LAYER -->
                <div style="position: absolute; top: 0; left: 0; right: 0; bottom: 0; pointer-events: none; z-index: 50; background-image: url(&quot;data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='400' height='400'%3E%3Ctext x='200' y='200' transform='rotate(-45, 200, 200)' text-anchor='middle' dominant-baseline='middle' font-size='36' font-family='sans-serif' font-weight='900' fill='rgba(99, 102, 241, 0.10)'%3EATOM ACADEMY%3C/text%3E%3C/svg%3E&quot;); background-repeat: repeat;"></div>
                
                <!-- ACTUAL CONTENT -->
                <div class="relative z-10">
                    <div class="bg-white/95 rounded-xl border border-gray-100 p-3 sm:p-4 mb-4 flex justify-between items-center gap-2">
                        <div>
                            <h1 class="text-base sm:text-2xl font-black text-indigo-950 uppercase tracking-tighter">🎓 Final Merit List</h1>
                            <p class="text-green-600 text-[10px] sm:text-xs font-bold mt-0.5"><i class="fas fa-check-circle"></i> Sorted by Highest Percentage</p>
                        </div>
                        <div class="text-right">
                            <div class="text-[7px] sm:text-[9px] font-bold text-gray-400 uppercase tracking-widest">Generated By</div>
                            <div class="text-xs sm:text-sm font-black text-indigo-800">ATOM ACADEMY</div>
                        </div>
                    </div>
                    
                    <div class="bg-white/95 rounded-xl border border-gray-100 overflow-hidden mb-4 w-full">
                        <div class="overflow-x-auto w-full">
                            <table class="w-full text-left border-collapse">
                                <thead>
                                    <tr class="bg-slate-100 border-b-2 border-gray-200 text-gray-700 text-[8px] sm:text-xs uppercase tracking-wider">
                                        <th class="py-2 px-1 sm:p-2.5 font-bold text-center whitespace-nowrap">Rank</th>
                                        <th class="py-2 px-1 sm:p-2.5 font-bold text-center whitespace-nowrap">Status</th>
                                        <th class="py-2 px-1 sm:p-2.5 font-bold whitespace-nowrap">Dept</th>
                                        <th class="py-2 px-1 sm:p-2.5 font-bold whitespace-nowrap">Seat No</th>
                                        <th class="py-2 px-1 sm:p-2.5 font-bold">Student Name</th>
                                        <th class="py-2 px-1 sm:p-2.5 font-bold whitespace-nowrap">Marks</th>
                                        <th class="py-2 px-1 sm:p-2.5 font-bold whitespace-nowrap">Percentage</th>
                                        <th class="py-2 px-1 sm:p-2.5 font-bold whitespace-nowrap">Result</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {html_rows}
                                </tbody>
                            </table>
                        </div>
                    </div>
                    
                    <!-- FOOTER -->
                    <div class="text-center text-[7px] sm:text-[10px] font-black text-gray-500 uppercase tracking-widest border-t-2 border-gray-300 pt-3 pb-1 mt-2">
                        © ATOM ACADEMY | GENERATED VIA OFFICIAL PORTAL | DO NOT DISTRIBUTE WITHOUT PERMISSION
                    </div>
                </div>
            </div>

            <!-- PREMIUM BUTTONS: SIDE-BY-SIDE AT BOTTOM LEFT -->
            <div class="max-w-5xl mx-auto mt-4 flex flex-row flex-wrap justify-start gap-3 w-full">
                <!-- PDF BUTTON -->
                <button onclick="generatePDF()" id="downloadPdfBtn" class="bg-indigo-600 hover:bg-indigo-700 text-white px-5 py-3 rounded-xl font-black shadow-md transition-all duration-200 flex items-center justify-center gap-2 text-xs sm:text-sm uppercase tracking-widest border-2 border-indigo-800 active:scale-95 flex-1 sm:flex-none">
                    <i class="fas fa-file-pdf text-lg"></i> DOWNLOAD PDF
                </button>
                
                <!-- CSV BUTTON -->
                <button onclick="downloadCSV()" id="downloadCsvBtn" class="bg-emerald-600 hover:bg-emerald-700 text-white px-5 py-3 rounded-xl font-black shadow-md transition-all duration-200 flex items-center justify-center gap-2 text-xs sm:text-sm uppercase tracking-widest border-2 border-emerald-800 active:scale-95 flex-1 sm:flex-none">
                    <i class="fas fa-file-excel text-lg"></i> DOWNLOAD CSV
                </button>
            </div>

            <script>
                const csvBase64 = "{csv_b64}";
                const pdfData = {pdf_rows_json};
                
                // --- CSV DOWNLOAD LOGIC ---
                function downloadCSV() {{
                    const csvStr = atob(csvBase64);
                    const blob = new Blob([csvStr], {{ type: 'text/csv;charset=utf-8;' }});
                    const url = URL.createObjectURL(blob);
                    const link = document.createElement('a');
                    link.href = url;
                    link.setAttribute('download', 'MKBU_Merit_List.csv');
                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);
                }}

                // --- PURE VECTOR PDF GENERATOR (NO CUT-OFF, NO MOBILE CRASH) ---
                function generatePDF() {{
                    const btn = document.getElementById('downloadPdfBtn');
                    const origText = btn.innerHTML;
                    btn.innerHTML = '<i class="fas fa-spinner fa-spin text-lg"></i> SAVING PDF...';
                    btn.disabled = true;

                    try {{
                        const {{ jsPDF }} = window.jspdf;
                        // Exact A4 Portrait (210mm x 297mm)
                        const doc = new jsPDF({{ orientation: 'portrait', unit: 'mm', format: 'a4' }});

                        // 1. TOP HEADER CARD ON PAGE 1
                        doc.setDrawColor(229, 231, 235);
                        doc.setFillColor(255, 255, 255);
                        doc.roundedRect(10, 10, 190, 20, 3, 3, 'FD');

                        doc.setFont('helvetica', 'bold');
                        doc.setFontSize(15);
                        doc.setTextColor(30, 27, 75); // Indigo-950
                        doc.text('FINAL MERIT LIST', 15, 19);

                        doc.setFontSize(8.5);
                        doc.setTextColor(22, 163, 74); // Green-600
                        doc.text('Sorted by Highest Percentage', 15, 25);

                        doc.setFontSize(7);
                        doc.setTextColor(156, 163, 175); // Gray-400
                        doc.text('GENERATED BY', 195, 18, {{ align: 'right' }});

                        doc.setFontSize(10);
                        doc.setTextColor(55, 48, 163); // Indigo-800
                        doc.text('ATOM ACADEMY', 195, 24, {{ align: 'right' }});

                        // 2. PREPARE TABLE ROWS
                        const tableBody = pdfData.map(r => [
                            r.rank <= 3 ? String(r.rank) : '#' + r.rank,
                            '', // Status icon drawn via vector
                            r.dept,
                            r.seat,
                            r.name,
                            r.marks,
                            r.perc,
                            r.status
                        ]);

                        // 3. GENERATE AUTO-PAGINATING PORTRAIT TABLE (Exact 190mm total width)
                        doc.autoTable({{
                            startY: 34,
                            margin: {{ top: 15, bottom: 20, left: 10, right: 10 }},
                            head: [['RANK', 'STATUS', 'DEPT', 'SEAT NO', 'STUDENT NAME', 'MARKS', 'PERCENTAGE', 'RESULT']],
                            body: tableBody,
                            theme: 'grid',
                            rowPageBreak: 'avoid',
                            headStyles: {{
                                fillColor: [241, 245, 249],
                                textColor: [55, 65, 81],
                                fontStyle: 'bold',
                                fontSize: 8,
                                halign: 'left',
                                lineColor: [226, 232, 240],
                                lineWidth: 0.3
                            }},
                            styles: {{
                                font: 'helvetica',
                                fontSize: 8,
                                cellPadding: 2.5,
                                textColor: [17, 24, 39],
                                lineColor: [229, 231, 235],
                                lineWidth: 0.2,
                                valign: 'middle',
                                overflow: 'linebreak'
                            }},
                            columnStyles: {{
                                0: {{ cellWidth: 14, halign: 'center', fontStyle: 'bold' }},
                                1: {{ cellWidth: 15, halign: 'center' }},
                                2: {{ cellWidth: 23, halign: 'center', fontStyle: 'bold', fontSize: 7.5 }},
                                3: {{ cellWidth: 21, fontStyle: 'normal', textColor: [75, 85, 99] }},
                                4: {{ cellWidth: 57, fontStyle: 'bold' }},
                                5: {{ cellWidth: 20, halign: 'center', fontStyle: 'bold' }},
                                6: {{ cellWidth: 23, halign: 'center', fontStyle: 'bold', textColor: [37, 99, 235], fontSize: 8.5 }},
                                7: {{ cellWidth: 17, halign: 'center', fontStyle: 'bold', fontSize: 7 }}
                            }},
                            didParseCell: function(data) {{
                                if (data.section === 'head' && (data.column.index <= 2 || data.column.index >= 5)) {{
                                    data.cell.styles.halign = 'center';
                                }}
                                if (data.section === 'body') {{
                                    // Top 3 Rank Colors
                                    if (data.column.index === 0) {{
                                        const r = pdfData[data.row.index].rank;
                                        if (r === 1) data.cell.styles.textColor = [217, 119, 6]; // Gold
                                        else if (r === 2) data.cell.styles.textColor = [107, 114, 128]; // Silver
                                        else if (r === 3) data.cell.styles.textColor = [234, 88, 12]; // Bronze
                                    }}
                                    // Dept Pill Colors
                                    if (data.column.index === 2) {{
                                        data.cell.styles.textColor = [157, 23, 77];
                                    }}
                                }}
                            }},
                            didDrawCell: function(data) {{
                                if (data.section === 'body' && data.column.index === 1) {{
                                    // Draw Vector Status Circle Badge (Green for PASS, Red for FAIL/ATKT, Yellow otherwise)
                                    const st = pdfData[data.row.index].status;
                                    const cx = data.cell.x + data.cell.width / 2;
                                    const cy = data.cell.y + data.cell.height / 2;
                                    
                                    if (st.includes('PASS')) {{
                                        doc.setFillColor(34, 197, 94); // Green
                                        doc.circle(cx, cy, 2.5, 'F');
                                        doc.setDrawColor(255, 255, 255);
                                        doc.setLineWidth(0.5);
                                        doc.line(cx - 1.1, cy + 0.1, cx - 0.3, cy + 0.9);
                                        doc.line(cx - 0.3, cy + 0.9, cx + 1.2, cy - 0.8);
                                    }} else if (st.includes('FAIL') || st.includes('ATKT')) {{
                                        doc.setFillColor(239, 68, 68); // Red
                                        doc.circle(cx, cy, 2.5, 'F');
                                        doc.setDrawColor(255, 255, 255);
                                        doc.setLineWidth(0.5);
                                        doc.line(cx - 1, cy - 1, cx + 1, cy + 1);
                                        doc.line(cx + 1, cy - 1, cx - 1, cy + 1);
                                    }} else {{
                                        doc.setFillColor(234, 179, 8); // Yellow
                                        doc.circle(cx, cy, 2.5, 'F');
                                        doc.setTextColor(255, 255, 255);
                                        doc.setFontSize(7);
                                        doc.text('!', cx, cy + 1, {{ align: 'center' }});
                                    }}
                                }}
                            }}
                        }});

                        // 4. ADD WATERMARK & FOOTER ON EVERY PAGE
                        const pageCount = doc.internal.getNumberOfPages();
                        for (let i = 1; i <= pageCount; i++) {{
                            doc.setPage(i);
                            
                            // Diagonal Watermark Grid
                            doc.saveGraphicsState();
                            if (doc.GState) {{
                                doc.setGState(new doc.GState({{ opacity: 0.09 }}));
                            }}
                            doc.setFont('helvetica', 'bold');
                            doc.setFontSize(34);
                            doc.setTextColor(99, 102, 241); // Indigo
                            
                            for (let y = 70; y <= 260; y += 85) {{
                                doc.text('ATOM ACADEMY', 65, y, {{ angle: 35, align: 'center' }});
                                doc.text('ATOM ACADEMY', 155, y + 35, {{ angle: 35, align: 'center' }});
                            }}
                            doc.restoreGraphicsState();

                            // Bottom Copyright Footer
                            doc.setDrawColor(209, 213, 219);
                            doc.setLineWidth(0.4);
                            doc.line(10, 285, 200, 285);
                            
                            doc.setFont('helvetica', 'bold');
                            doc.setFontSize(7);
                            doc.setTextColor(107, 114, 128);
                            doc.text('© ATOM ACADEMY | GENERATED VIA OFFICIAL PORTAL | DO NOT DISTRIBUTE WITHOUT PERMISSION', 10, 290);
                            doc.text('Page ' + i + ' of ' + pageCount, 200, 290, {{ align: 'right' }});
                        }}

                        // 5. SAVE PDF INSTANTLY (Works on both Mobile & PC)
                        doc.save('MKBU_Merit_List.pdf');

                        btn.innerHTML = origText;
                        btn.disabled = false;
                    }} catch (err) {{
                        console.error(err);
                        btn.innerHTML = '<i class="fas fa-exclamation-triangle"></i> ERROR';
                        setTimeout(() => {{
                            btn.innerHTML = origText;
                            btn.disabled = false;
                        }}, 3000);
                    }}
                }}
            </script>
        </body>
        </html>"""

        # Embed custom HTML directly inside Streamlit
        st.subheader("🏆 Your Custom Dashboard")
        components.html(html_template, height=1000, scrolling=True)
