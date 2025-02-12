import os
import uuid
import PyPDF2
from flask import Flask, request, jsonify, render_template
from openai import AzureOpenAI
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from datetime import datetime

# Load environment variables from .env file
load_dotenv()

# Initialize Flask app
app = Flask(__name__, template_folder="templates", static_folder="static")

# Configure upload folder
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "uploads")
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB file size limit

# Load and validate Azure credentials
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION")

AZURE_SEARCH_SERVICE_NAME = os.getenv("AZURE_SEARCH_SERVICE_NAME")
AZURE_SEARCH_INDEX_NAME = os.getenv("AZURE_SEARCH_INDEX_NAME")
AZURE_SEARCH_API_KEY = os.getenv("AZURE_SEARCH_API_KEY")

AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
BLOB_CONTAINER_NAME = os.getenv("BLOB_CONTAINER_NAME")

if not all([AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_VERSION,
            AZURE_SEARCH_SERVICE_NAME, AZURE_SEARCH_INDEX_NAME, AZURE_SEARCH_API_KEY,
            AZURE_STORAGE_CONNECTION_STRING, BLOB_CONTAINER_NAME]):
    raise ValueError("One or more required environment variables are missing.")

# Configure Azure OpenAI API
openai_client = AzureOpenAI(
    api_key=AZURE_OPENAI_API_KEY,
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
    api_version=AZURE_OPENAI_API_VERSION
)

# Configure Azure AI Search
search_client = SearchClient(
    endpoint=f"https://{AZURE_SEARCH_SERVICE_NAME}.search.windows.net",
    index_name=AZURE_SEARCH_INDEX_NAME,
    credential=AzureKeyCredential(AZURE_SEARCH_API_KEY)
)

# Configure Azure Blob Storage
blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)

def extract_text_from_pdf(pdf_path):
    """Extracts text from a PDF file."""
    text = ""
    try:
        with open(pdf_path, "rb") as file:
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                text += page.extract_text() or ""
    except Exception as e:
        print(f"❌ Error extracting text from PDF: {e}")
        raise
    return text

def upload_pdf_to_blob(file_path, blob_name):
    """Uploads a PDF file to Azure Blob Storage and indexes its content in Azure AI Search."""
    try:
        blob_client = blob_service_client.get_blob_client(container=BLOB_CONTAINER_NAME, blob=blob_name)
        
        # Check if the blob already exists
        if blob_client.exists():
            print(f"ℹ️ {blob_name} already exists in Azure Blob Storage. Skipping upload.")
            return "File already exists."

        # Upload PDF to Blob Storage
        with open(file_path, "rb") as data:
            blob_client.upload_blob(data, overwrite=False)
        print(f"✅ Successfully uploaded {blob_name} to Azure Blob Storage.")

        # Extract text from PDF
        text = extract_text_from_pdf(file_path)
        print("Extracted Text:", text)

        # Upload extracted text to Azure AI Search
        document = {
            "id": blob_name,
            "file_name": blob_name,
            "content": text  # Ensure this field is populated
        }

        search_client.upload_documents(documents=[document])
        print(f"✅ Successfully indexed {blob_name} in Azure AI Search.")
        
        return "File uploaded and processed successfully."
    except Exception as e:
        print(f"❌ Error in upload_pdf_to_blob: {e}")
        return "Error processing the file."

def search_documents(query):
    """Searches the Azure AI Search index for relevant documents."""
    try:
        print(f"Searching for: {query}")
        results = search_client.search(search_text=query, top=1)

        # Extract the content field
        retrieved_texts = [doc.get("content", "") for doc in results if "content" in doc]
        print("Retrieved Texts:", retrieved_texts)
        return "\n\n".join(retrieved_texts) if retrieved_texts else "No relevant documents found."
    except Exception as e:
        print(f"❌ Error during search_documents(): {e}")
        return ""

def generate_answer(question, retrieved_text, model="gpt-4o-2"):
    """Generates an answer using OpenAI's GPT model."""
    prompt = f"""
    **Question:** {question}
    **Relevant Information:**
    {retrieved_text}
    **Answer concisely based on the document.**
    """
    try:
        response = openai_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are an AI that provides precise answers based on the given text."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,  # Limit response length
            temperature=0.5   # Reduce randomness
        )
        return response.choices[0].message.content if response.choices else "No response generated."
    except Exception as e:
        print(f"❌ Error in generate_answer(): {e}")
        return "An error occurred while generating the answer."

# Routes
@app.route("/")
def home():
    """Renders the home page."""
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload_pdf():
    """Handles PDF file uploads."""
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    filename = secure_filename(file.filename)
    if filename.endswith(".pdf"):
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(file_path)
        
        print(f"File saved to: {file_path}")
        blob_name = os.path.splitext(filename)[0]
        
        message = upload_pdf_to_blob(file_path, blob_name)
        return jsonify({"message": message}), 200
    else:
        return jsonify({"error": "Invalid file type. Only PDFs are allowed"}), 400

@app.route("/chat", methods=["POST"])
def chat():
    """Handles user queries."""
    data = request.json
    user_query = data.get("query", "").strip()
    if not user_query:
        return jsonify({"error": "No query provided"}), 400

    retrieved_text = search_documents(user_query)
    print(f"Retrieved Text: {retrieved_text}")
    if not retrieved_text or retrieved_text == "No relevant documents found.":
        return jsonify({"response": "No relevant information found in the document."})
    
    answer = generate_answer(user_query, retrieved_text)
    return jsonify({"response": answer})

# Run the app
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)