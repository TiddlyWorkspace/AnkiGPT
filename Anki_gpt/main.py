import streamlit as st
import os
import shutil
import atexit
from openai.error import OpenAIError
from components.sidebar import sidebar
from utils import (
    embed_docs,
    get_answer,
    parse_docx,
    parse_pdf,
    parse_txt,
    search_docs,
    text_to_docs,
)
from prompts import chat_prompt
import pandas as pd
import base64
import csv
from langchain.callbacks import get_openai_callback

st.set_page_config(page_title="AnkiGPT", page_icon="📇", layout="wide")
st.header("📇AnkiGPT")

def clear_submit():
    st.session_state["submit"] = False

sidebar()

uploaded_file = st.file_uploader(
    "Upload a pdf, docx, or txt file",
    type=["pdf", "docx", "txt"],
    help="Scanned documents are not supported yet!",
    on_change=clear_submit,
)

index = None
doc = None
if uploaded_file is not None:
    if uploaded_file.name.endswith(".pdf"):
        doc = parse_pdf(uploaded_file)
    elif uploaded_file.name.endswith(".docx"):
        doc = parse_docx(uploaded_file)
    elif uploaded_file.name.endswith(".txt"):
        doc = parse_txt(uploaded_file)
    else:
        raise ValueError("File type not supported!")
    text = text_to_docs(doc)

    try:
        with st.spinner("Indexing document... This may take a while⏳"):
            index = embed_docs(text,change_doc=uploaded_file.name)
        st.session_state["api_key_configured"] = True
    except OpenAIError as e:
        st.error(e._message)

query = st.text_input("Write the subject you want flashcards for", on_change=clear_submit)

with st.expander("Advanced Options"):
    show_flashcards = st.checkbox("Show the question, answer flashcards")
    show_source = st.checkbox("Show the source of flashcards")

button = st.button("Submit")
if button or st.session_state.get("submit"):
    if not st.session_state.get("api_key_configured"):
        st.error("Please configure your OpenAI API key!")
    elif not index:
        st.error("Please upload a document!")
    elif not query:
        st.error("Please enter a subject!")
    else:
        st.session_state["submit"] = True
        # Output Columns
        answer_col, sources_col = st.columns(2)
        sources = search_docs(index, query)
    
        try:
            if show_source:
                st.write(sources)
            answer = get_answer(sources,chat_prompt).replace("A:", ";A:")
            answer = answer.replace("\n;A:", ";A:")
            if show_flashcards:
                with st.container():
                    st.write(answer)
            answer1 = answer.replace("Q:", "\nQ:")
            answer2 = answer1.replace("\nQ:", "Q:", 1)
            data = []
            rows = answer2.split('\n')
            rows = list(filter(lambda el: el != '', rows))
            for row in rows:
                columns = row.split(';')
                data.append([columns[0], columns[1]])
            num_columns = len(data[0])

            # Filter out rows with the wrong number of columns
            data = [row for row in data if len(row) == num_columns]

            # Save the data as a CSV file
            if not os.path.exists('.tmp'):
                os.mkdir('.tmp')

            with open(f'.tmp/{query}.csv', 'w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow([ 'Question', 'Answer'])
                writer.writerows(data)

            # Create a download link for your CSV file
            data = pd.read_csv(f".tmp/{query}.csv", encoding='utf-8')
            csvfile = data.to_csv(header=False,index=False)
            b64 = base64.b64encode(csvfile.encode()).decode()
            href = f'<a href="data:file/csv;base64,{b64}" download="{query}.csv">Download CSV file</a>'
            st.markdown(href, unsafe_allow_html=True)

        except OpenAIError as e:
            st.error(e._message)

def exit_handler():
    shutil.rmtree('.tmp')

atexit.register(exit_handler)
