import streamlit as st
from pypdf import PdfReader, PdfWriter
import os
import zipfile
import io
import csv

st.set_page_config(page_title="Drawing Manager", layout="wide")
st.title("Drawing Manager")

tab1, tab2 = st.tabs(["Split PDF", "Library"])

with tab1:
    st.header("Split PDF by Catalog Number")

    uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")
    csv_file = st.file_uploader("Load catalog mapping (CSV)", type="csv")

    if uploaded_file:
        reader = PdfReader(uploaded_file)
        num_pages = len(reader.pages)
        st.info(f"Found {num_pages} pages")

        catalog_numbers = {}

        if csv_file:
            content = csv_file.read().decode("utf-8").splitlines()
            reader_csv = csv.DictReader(content)
            for row in reader_csv:
                page_idx = int(row["page"]) - 1
                catalog_numbers[page_idx] = row["catalog"]
            st.success(f"Loaded {len(catalog_numbers)} catalog numbers from CSV")

        if st.button("Split and Download", type="primary"):
            if not catalog_numbers:
                st.error("No catalog numbers loaded - please upload CSV file")
            else:
                zip_buffer = io.BytesIO()
                file_bytes = uploaded_file.getvalue()
                reader2 = PdfReader(io.BytesIO(file_bytes))
                with zipfile.ZipFile(zip_buffer, "w") as zf:
                    for page_num, catalog in catalog_numbers.items():
                        writer = PdfWriter()
                        writer.add_page(reader2.pages[page_num])
                        pdf_buffer = io.BytesIO()
                        writer.write(pdf_buffer)
                        zf.writestr(f"{catalog}.pdf", pdf_buffer.getvalue())

                st.success(f"{len(catalog_numbers)} files ready!")
                st.download_button(
                    label="Download all as ZIP",
                    data=zip_buffer.getvalue(),
                    file_name="drawings.zip",
                    mime="application/zip"
                )

        if catalog_numbers:
            st.subheader("Catalog numbers loaded:")
            cols = st.columns(3)
            for i, (page_num, catalog) in enumerate(sorted(catalog_numbers.items())):
                col = cols[i % 3]
                with col:
                    st.write(f"Page {page_num+1}: **{catalog}**")

with tab2:
    st.header("Drawings Library")

    if "library" not in st.session_state:
        st.session_state.library = {}

    uploaded_files = st.file_uploader(
        "Upload drawings to library",
        type="pdf",
        accept_multiple_files=True,
        key="library_upload"
    )

    if uploaded_files:
        for f in uploaded_files:
            name = os.path.splitext(f.name)[0]
            st.session_state.library[name] = f.read()
        st.success(f"Added {len(uploaded_files)} drawings")

    if st.session_state.library:
        search = st.text_input("Search by catalog number")

        items = list(st.session_state.library.items())
        if search:
            items = [(k, v) for k, v in items if search.lower() in k.lower()]

        st.write(f"{len(items)} drawings")

        for name, data in items:
            col1, col2 = st.columns([4, 1])
            with col1:
                st.write(f"{name}")
            with col2:
                st.download_button(
                    label="Download",
                    data=data,
                    file_name=f"{name}.pdf",
                    mime="application/pdf",
                    key=f"dl_{name}"
                )
    else:
        st.info("Library is empty - upload drawings above")
