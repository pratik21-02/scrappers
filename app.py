# Find Marks
total_label = soup.find(lambda tag: tag.name in ['td', 'th'] and tag.text and "GRAND TOTAL" in tag.text.upper())
percentage_val = 0.0
                        percentage_str = "0%"
                        marks_string = "0 / 0"
                        percentage_str = "N/A"
                        marks_string = "N/A"
result_status = "Unknown"

if total_label:
row = total_label.find_parent('tr')
cells = [c.text.strip() for c in row.find_all(['td', 'th']) if c.text.strip()]
                            result_status = cells[-1] if len(cells) > 0 else "Unknown"

                            middle_text = " ".join(cells[1:-1])
                            nums = re.findall(r'\d+', middle_text)
                            # --- SMART STATUS & MARKS SEPARATION ---
                            # Rule numbers (e.g. RESERVED U.ST.114) se confusion bachane ke liye:
                            status_keywords = ["PASS", "FAIL", "ATKT", "ABSENT", "RESERVED", "WITHHELD", "U.F.M", "U.ST", "WH", "W.H."]
                            
                            found_status_idx = -1
                            for i, cell in enumerate(cells):
                                if any(kw in cell.upper() for kw in status_keywords):
                                    found_status_idx = i
                                    break
                                    
                            if found_status_idx != -1:
                                result_status = " ".join(cells[found_status_idx:])
                                marks_cells = cells[1:found_status_idx] # Status se pehle ke cells
                            else:
                                result_status = cells[-1] if len(cells) > 0 else "Unknown"
                                marks_cells = cells[1:-1]
                                
                            # Ab sirf "marks_cells" mein se numbers nikalenge
                            middle_text = " ".join(marks_cells)
                            nums = [int(n) for n in re.findall(r'\b\d+\b', middle_text)]

if len(nums) >= 2:
                                obtained = int(nums[-2])
                                maximum = int(nums[-1])
                                if maximum > 0:
                                obtained = nums[-2]
                                maximum = nums[-1]
                                
                                # Logic Check: Total marks humesha obtained se zyada hone chahiye
                                if maximum > 0 and obtained <= maximum:
percentage_val = (obtained / maximum) * 100
percentage_str = f"{round(percentage_val, 2)}%"
marks_string = f"{obtained} / {maximum}"
                                else:
                                    marks_string = f"{obtained} / ?" # Fallback for unexpected format
                            elif len(nums) == 1:
                                marks_string = f"{nums[0]} / ?"

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

time.sleep(0.8) # Badhaya gaya delay taaki MKBU server block na kare

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
