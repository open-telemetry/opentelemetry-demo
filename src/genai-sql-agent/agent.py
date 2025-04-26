# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Adapted from https://github.com/langchain-ai/streamlit-agent/blob/main/streamlit_agent/basic_memory.py"""

import logging
import sqlite3
import tempfile
from random import getrandbits

import streamlit as st
from google.cloud import storage
from google.cloud.exceptions import NotFound
from langchain_community.agent_toolkits.sql.toolkit import SQLDatabaseToolkit
from langchain_community.utilities.sql_database import SQLDatabase
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.messages.base import BaseMessage
from langchain_core.runnables.config import (
    RunnableConfig,
)
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import create_react_agent
from patched_vertexai import PatchedChatVertexAI
import streamlit_helpers
from sqlalchemy import Engine, create_engine

from opentelemetry import trace
from opentelemetry.trace.span import format_trace_id

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

_ = """
Ideas for things to add:

- Show the trace ID and possibly a link to the trace
- Download the sqlite db
- Some kind of multimedia input/output
"""

tracer = trace.get_tracer(__name__)

title = "LangGraph SQL Agent Demo"
st.set_page_config(page_title=title, page_icon="📖", layout="wide")
st.title(title)
streamlit_helpers.styles()


model = PatchedChatVertexAI(model="gemini-2.0-flash")

if not st.query_params.get("thread_id"):
    result = model.invoke(
        "Generate a random name composed of an adjective and a noun, to use as a default value in a "
        "web page. Just return the name with no surrounding whitespace, and no other text.",
        max_tokens=50,
        seed=getrandbits(31),
    )
    st.query_params.thread_id = str(result.content).strip()
if "upload_key" not in st.session_state:
    st.session_state.upload_key = 0


# Initialize memory to persist state between graph runs
@st.cache_resource
def get_checkpointer() -> InMemorySaver:
    return InMemorySaver()


checkpointer = get_checkpointer()
with st.sidebar.container():
    streamlit_helpers.render_sidebar(checkpointer)


@st.cache_resource
def get_storage_bucket() -> storage.Bucket:
    storage_client = storage.Client()
    bucket_name = f"{streamlit_helpers.get_project_id()}-langgraph-chatbot-storage"
    try:
        return storage_client.get_bucket(bucket_name)
    except NotFound:
        return storage_client.create_bucket(bucket_name)


bucket = get_storage_bucket()


# Define the tools for the agent to use
@tool
@tracer.start_as_current_span("tool search")
def search(query: str):
    """Call to surf the web."""
    # This is a placeholder, but don't tell the LLM that...
    if "sf" in query.lower() or "san francisco" in query.lower():
        return "It's 60 degrees and foggy."
    return "It's 90 degrees and sunny."


system_prompt = SystemMessage(
    content=f"""\
You are a careful and helpful AI assistant with a mastery of database design and querying. You
have access to an ephemeral sqlite3 database that you can query and modify through some tools.
Help answer questions and perform actions. Follow these rules:

- Make sure you always use sql_db_query_checker to validate SQL statements **before** running
  them! In pseudocode: `checked_query = sql_db_query_checker(query);
  sql_db_query(checked_query)`.
- The sqlite version is {sqlite3.sqlite_version} which supports multiple row inserts.
- Always prefer to insert multiple rows in a single call to the sql_db_query tool, if possible.
- You may request to execute multiple sql_db_query tool calls which will be run in parallel.

If you make a mistake, try to recover."""
)


@st.cache_resource
def get_engine(thread_id: str) -> "tuple[str, Engine]":
    # Ephemeral sqlite database per conversation thread
    _, dbpath = tempfile.mkstemp(suffix=".db")
    return dbpath, create_engine(
        f"sqlite:///{dbpath}",
        echo=True,
        isolation_level="AUTOCOMMIT",
    )


@st.cache_resource
def get_db(thread_id: str) -> SQLDatabase:
    _, engine = get_engine(thread_id)
    return SQLDatabase(engine)


dbpath, engine = get_engine(st.query_params.thread_id)
db = get_db(st.query_params.thread_id)
toolkit = SQLDatabaseToolkit(db=db, llm=model)

tools = [search, *toolkit.get_tools()]

app = create_react_agent(model, tools, checkpointer=checkpointer, prompt=system_prompt)
config: RunnableConfig = {"configurable": {"thread_id": st.query_params.thread_id}}

if checkpoint := checkpointer.get(config):
    messages: list[BaseMessage] = checkpoint["channel_values"]["messages"]
else:
    messages = []


@st.cache_resource
def get_trace_ids(thread_id: str) -> "dict[str, str]":
    # Stores the trace IDs. Unfortunately I can't find a way to easily retrieve this from the
    # checkpointer, so just store it separately.
    return {}


trace_ids = get_trace_ids(st.query_params.thread_id)

col1, col2 = st.columns([0.6, 0.4])
with col1:
    streamlit_helpers.render_intro()
    st.divider()

    # Add system message
    st.expander(
        "System Instructions", icon=":material/precision_manufacturing:"
    ).markdown(system_prompt.content)

    # Render current messages
    for message in messages:
        trace_id = trace_ids.get(message.id or "")
        streamlit_helpers.render_message(message, trace_id)

# If user inputs a new prompt, generate and draw a new response
# TODO: see if st.form() looks better
file_upload = st.file_uploader(
    "Upload an image",
    type=["png", "jpg", "jpeg", "pdf", "webp"],
    # Hack to clear the upload
    key=f"file_uploader_{st.session_state.upload_key}",
)
if prompt := st.chat_input():
    content = []

    # Put the image first https://cloud.google.com/vertex-ai/generative-ai/docs/multimodal/image-understanding#best-practices
    if file_upload:
        filename: str = file_upload.name
        blob = bucket.blob(filename)
        blob.upload_from_file(file_upload, content_type=file_upload.type)
        st.session_state.upload_key += 1

        uri = f"gs://{bucket.name}/{blob.name}"
        content.append({"type": "image_url", "image_url": {"url": uri}})

    content.append({"type": "text", "text": prompt})

    message = HumanMessage(content)

    with col1:
        with tracer.start_as_current_span(
            "chain invoke",
            attributes={"thread_id": st.query_params.thread_id},
        ) as span:
            trace_id = format_trace_id(span.get_span_context().trace_id)
            streamlit_helpers.render_message(message, trace_id=trace_id)

            # Invoke the agent
            with st.spinner("Thinking..."):
                res = app.invoke({"messages": [message]}, config=config)
                logger.debug("agent response", extra={"response": str(res)})

            # Store trace ID for rendering
            trace_ids[message.id or ""] = trace_id
            trace_ids[res["messages"][-1].id] = trace_id

    st.rerun()

with col2:
    with st.expander("See database contents", expanded=True):
        streamlit_helpers.render_db_contents(engine, dbpath)

    with st.expander("See available tools"):
        st.json(tools)

    with st.expander("View the message contents in session state"):
        st.json(messages)
