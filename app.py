import streamlit as st
from pypdf import PdfReader, PdfWriter
import os, zipfile, io, csv
import fitz
from PIL import Image

st.set_page_config(page_title="Drawing Manager", layout="wide")
st.title("🗂️ Drawing Manager")

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

        doc = fitz.open(stream=file_bytes, filetype="pdf")
        st.subheader("הזן מק\"ט לכל שרטוט:")

        for i in range(num_pages):
            page = doc[i]
            rect = page.rect
            w, h = rect.width, rect.height

            # Crop bottom-right corner (title block)
            crop = fitz.Rect(w * 0.50, h * 0.75, w, h)
            mat = fitz.Matrix(2, 2)
            clip = page.get_pixmap(matrix=mat, clip=crop)
            img = Image.frombytes("RGB", [clip.width, clip.height], clip.samples)

            col1, col2 = st.columns([2, 1])
            with col1:
                st.image(img, caption=f"עמוד {i+1} — פינת הכותרת", use_container_width=True)
            with col2:
                st.write(f"**עמוד {i+1}**")
                val = st.session_state.catalog_numbers.get(i, "")
                catalog = st.text_input(
                    f"מק\"ט שרטוט:",
                    value=val,
                    key=f"cat_{i}",
                    placeholder="למשל: 20995352132"
                )
                if catalog:
                    st.session_state.catalog_numbers[i] = catalog
                    st.success(f"✅ {catalog}")

        doc.close()

        filled = {k: v for k, v in st.session_state.catalog_numbers.items() if v.strip()}
        st.divider()
        st.write(f"**{len(filled)} / {num_pages} מק\"טים הוזנו**")

        col_a, col_b = st.columns(2)

        with col_a:
            if filled:
                csv_buffer = io.StringIO()
                writer_csv = csv.writer(csv_buffer)
                writer_csv.writerow(["page", "catalog"])
                for page_num, catalog in sorted(filled.items()):
                    writer_csv.writerow([page_num + 1, catalog])
                st.download_button(
                    label="📥 הורד CSV",
                    data=csv_buffer.getvalue(),
                    file_name="catalog_mapping.csv",
                    mime="text/csv"
                )

        with col_b:
            if st.button("✂️ Split and Download ZIP", type="primary", disabled=len(filled) == 0):
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
