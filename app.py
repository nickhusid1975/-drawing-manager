import streamlit as st
from pypdf import PdfReader, PdfWriter
import os, zipfile, io, csv, base64
import fitz
from PIL import Image

st.set_page_config(page_title="Drawing Manager", layout="wide")
st.title("🗂️ Drawing Manager")

def image_to_base64(img):
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()

def extract_catalog_with_ai(pdf_bytes, page_index):
    """Use Claude API to extract drawing number from page."""
    import anthropic
    
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[page_index]
    rect = page.rect
    w, h = rect.width, rect.height
    
    # Crop bottom-right corner (title block area)
    crop = fitz.Rect(w * 0.50, h * 0.75, w, h)
    mat = fitz.Matrix(2, 2)
    clip = page.get_pixmap(matrix=mat, clip=crop)
    img = Image.frombytes("RGB", [clip.width, clip.height], clip.samples)
    doc.close()
    
    img_b64 = image_to_base64(img)
    
    client = anthropic.Anthropic()
    
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=100,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": img_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": "This is a corner of an engineering drawing. Find the DRAWING NUMBER (a long number like 20995353154). Return ONLY the number, nothing else. If you cannot find it, return 'NOT_FOUND'."
                    }
                ],
            }
        ],
    )
    
    result = response.content[0].text.strip()
    if result == "NOT_FOUND" or not any(c.isdigit() for c in result):
        return None
    # Extract only digits and keep the number
    import re
    numbers = re.findall(r'\d{8,15}', result)
    return numbers[0] if numbers else None

tab1, tab2 = st.tabs(["Split PDF", "Library"])

with tab1:
    st.header("Split PDF by Catalog Number")
    uploaded_file = st.file_uploader("העלה קובץ PDF", type="pdf")

    if uploaded_file:
        file_bytes = uploaded_file.getvalue()

        # Reset catalog numbers when a new file is uploaded
        file_id = uploaded_file.name + str(uploaded_file.size)
        if st.session_state.get("current_file_id") != file_id:
            st.session_state.current_file_id = file_id
            st.session_state.catalog_numbers = {}

        reader = PdfReader(io.BytesIO(file_bytes))
        num_pages = len(reader.pages)
        st.info(f"נמצאו {num_pages} עמודים")

        # Auto-scan button
        if st.button("🤖 סרוק מק\"טים אוטומטית (AI)", type="primary"):
            auto_catalogs = {}
            failed_pages = []
            progress = st.progress(0)
            status = st.empty()

            for i in range(num_pages):
                status.text(f"סורק עמוד {i+1} מתוך {num_pages}...")
                progress.progress((i + 1) / num_pages)
                try:
                    catalog = extract_catalog_with_ai(file_bytes, i)
                    if catalog:
                        auto_catalogs[i] = catalog
                    else:
                        failed_pages.append(i + 1)
                except Exception as e:
                    failed_pages.append(i + 1)

            progress.empty()
            status.empty()

            if auto_catalogs:
                st.session_state.catalog_numbers = auto_catalogs
                st.success(f"✅ נמצאו {len(auto_catalogs)} מק\"טים!")
                if failed_pages:
                    st.warning(f"לא נמצא מק\"ט בעמודים: {failed_pages}")
            else:
                st.error("לא נמצאו מק\"טים אוטומטית.")

        catalog_numbers = st.session_state.get("catalog_numbers", {})

        # Show and allow editing
        if catalog_numbers:
            st.subheader("✏️ בדוק ועדכן מק\"טים:")
            updated = {}
            col_h1, col_h2 = st.columns([1, 3])
            col_h1.markdown("**עמוד**")
            col_h2.markdown("**מק\"ט**")
            for page_num in sorted(catalog_numbers.keys()):
                cols = st.columns([1, 3])
                cols[0].write(f"עמוד {page_num + 1}")
                new_val = cols[1].text_input(
                    label=f"p{page_num}",
                    value=catalog_numbers[page_num],
                    key=f"edit_{page_num}",
                    label_visibility="collapsed"
                )
                updated[page_num] = new_val
            catalog_numbers = updated

            # Download CSV
            csv_buffer = io.StringIO()
            writer_csv = csv.writer(csv_buffer)
            writer_csv.writerow(["page", "catalog"])
            for page_num, catalog in sorted(catalog_numbers.items()):
                writer_csv.writerow([page_num + 1, catalog])
            st.download_button(
                label="📥 הורד CSV",
                data=csv_buffer.getvalue(),
                file_name="catalog_mapping.csv",
                mime="text/csv"
            )

        st.divider()
        filled = {k: v for k, v in catalog_numbers.items() if v.strip()} if catalog_numbers else {}
        st.write(f"**{len(filled)} / {num_pages} מק\"טים**")

        if st.button("✂️ Split and Download ZIP", type="secondary", disabled=len(filled) == 0):
            zip_buffer = io.BytesIO()
            reader3 = PdfReader(io.BytesIO(file_bytes))
            with zipfile.ZipFile(zip_buffer, "w") as zf:
                for page_num, catalog in filled.items():
                    writer = PdfWriter()
                    writer.add_page(reader3.pages[page_num])
                    pdf_buffer = io.BytesIO()
                    writer.write(pdf_buffer)
                    zf.writestr(f"{catalog}.pdf", pdf_buffer.getvalue())
            st.success(f"✅ {len(filled)} קבצים מוכנים!")
            st.download_button(
                label="📦 Download ZIP",
                data=zip_buffer.getvalue(),
                file_name="drawings.zip",
                mime="application/zip"
            )

with tab2:
    st.header("Drawings Library")
    if "library" not in st.session_state:
        st.session_state.library = {}

    uploaded_files = st.file_uploader(
        "העלה שרטוטים לספרייה",
        type="pdf",
        accept_multiple_files=True,
        key="library_upload"
    )

    if uploaded_files:
        for f in uploaded_files:
            name = os.path.splitext(f.name)[0]
            st.session_state.library[name] = f.read()
        st.success(f"נוספו {len(uploaded_files)} שרטוטים")

    if st.session_state.library:
        search = st.text_input("🔍 חפש לפי מק\"ט")
        items = list(st.session_state.library.items())
        if search:
            items = [(k, v) for k, v in items if search.lower() in k.lower()]
        st.write(f"{len(items)} שרטוטים")
        for name, data in items:
            col1, col2 = st.columns([4, 1])
            with col1:
                st.write(f"📄 {name}")
            with col2:
                st.download_button(
                    label="הורד",
                    data=data,
                    file_name=f"{name}.pdf",
                    mime="application/pdf",
                    key=f"dl_{name}"
                )
    else:
        st.info("הספרייה ריקה — העלה שרטוטים למעלה")
