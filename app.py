import streamlit as st
import base64
import os
import requests
import json
import pandas as pd
from io import BytesIO
from pydantic.main import BaseModel
import fitz 

def convert_pdf_to_images_and_encode(pdf_path):
    doc = fitz.open(pdf_path)
    encoded_images = []
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        pix = page.get_pixmap()
        image_bytes = pix.tobytes("jpeg")
        encoded_image = base64.b64encode(image_bytes).decode('utf-8')
        encoded_images.append(encoded_image)
    return encoded_images

# Function to encode image
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

# Function to encode PDF
def encode_pdf(pdf_path):
    with open(pdf_path, "rb") as pdf_file:
        return base64.b64encode(pdf_file.read()).decode('utf-8')

# Function to create a downloadable Excel file
def to_excel(data):
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    data.to_excel(writer, index=False, sheet_name='Sheet1')
    writer.close()
    processed_data = output.getvalue()
    return processed_data

# Function to create a downloadable CSV file
def to_csv(data):
    return data.to_csv(index=False).encode('utf-8')

# Streamlit app
st.title("Document Content Extractor")

# Select document type
doc_type = st.selectbox("Select document type", ["Purchase Order", "Invoice", "Bank Statement", "Identity Document", "Payslip", "Local Purchase Order"])

# File uploader
uploaded_file = st.file_uploader("Upload an image or PDF", type=["png", "jpg", "jpeg", "pdf"])

# OpenAI API Key
openai_api_key = st.text_input("OpenAI API Key", type="password")

# Extract content button
if st.button("Extract Content") and uploaded_file and openai_api_key:
    file_extension = os.path.splitext(uploaded_file.name)[1].lower()

    if file_extension in [".png", ".jpg", ".jpeg"]:
        encoded_file = base64.b64encode(uploaded_file.read()).decode('utf-8')
        mime_type = "image/jpeg"
    elif file_extension == ".pdf":
        with open("temp.pdf", "wb") as f:
            f.write(uploaded_file.read())
        encoded_file = convert_pdf_to_images_and_encode("temp.pdf")
        mime_type = "image/jpeg"
    else:
        st.error("Unsupported file type.")
        st.stop()

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {openai_api_key}"
    }

    prompt_content = {
        "type": "text",
        "text": f"Extract contents in this document and return them in json purchase_order_number, purchase_order_date, supplier_name, supplier_address, buyer_name, buyer_address, items (item_description, item_quantity, item_price), total_amount"
    }

    prompt_image_url = {
        "type": "image_url",
        "image_url": {
            "url": f"data:{mime_type};base64,{encoded_file}"
        }
    }

    payload = {
        "model": "gpt-4o",
        "messages": [
            {
                "role": "user",
                "content": [prompt_content, prompt_image_url]
            }
        ],
        "max_tokens": 4096
    }

    response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)

    if response.status_code == 200:
        response_json = response.json()
        output = response_json['choices'][0]['message']['content']

        # Remove leading and trailing formatting characters
        json_str = output.strip().lstrip('```json\n').rstrip('\n```')

        # Convert string to JSON
        try:
            data_json = json.loads(json_str)
            st.json(data_json)

            # Convert JSON to DataFrame
            df = pd.json_normalize(data_json)
            
            # Download buttons
            excel_data = to_excel(df)
            st.download_button(label="Download as Excel", data=excel_data, file_name="extracted_data.xlsx")

            csv_data = to_csv(df)
            st.download_button(label="Download as CSV", data=csv_data, file_name="extracted_data.csv")

        except json.JSONDecodeError as e:
            st.error(f"JSON decoding error: {str(e)}")
    else:
        st.error(f"Failed to extract content: {response.text}")
