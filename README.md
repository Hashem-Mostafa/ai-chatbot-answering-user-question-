# PDF Chatbot

## Overview
This is a Flask-based chatbot that allows users to upload PDF documents and interact with them using natural language queries.

## Features
- Upload PDF documents.
- Chat with the document using a user-friendly interface.
- Powered by Azure OpenAI and Azure AI Search.

## Setup
1. Clone the repository.
2. Install dependencies: `pip install -r requirements.txt`.
3. Run the app: `python app.py`.

## API Documentation
- **POST /upload**: Upload a PDF file.
- **POST /chat**: Send a query to the chatbot.

## Docker Deployment
1. Build the Docker image: `docker build -t pdf-chatbot .`
2. Run the container: `docker run -p 5000:5000 pdf-chatbot`

### Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/Hashem-Mostafa/ai-chatbot-answering-user-question-.git
   cd ai-chatbot-answering-user-question-