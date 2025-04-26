# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from textwrap import dedent

import google.auth
import pandas as pd
import streamlit as st
from langchain_core.messages.base import BaseMessage
from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy import Engine, inspect


@st.cache_data
def get_project_id() -> str:
    project_id: str = google.auth.default()[1]  # type: ignore
    return project_id


def render_intro() -> None:
    st.markdown("""\
    This demo allows you to chat with an Agent that has full access to an
    ephemeral sqlite database. The database is initially empty. It is built with the the LangGraph prebuilt [ReAct
    Agent](https://langchain-ai.github.io/langgraph/how-tos/create-react-agent/#code) and the
    [SQLDatabaseToolkit](https://python.langchain.com/docs/integrations/tools/sql_database/).
    """)

    with st.popover("See examples"):
        examples = {
            "Weather": dedent("""\
                - Create a new table to hold weather data.
                - Populate the weather database with 20 example rows.
                - Add a new column for weather observer notes"""),
            "Pets": dedent("""\
                - Create a database table for pets including an `owner_id` column.
                - Add 20 example rows please.
                - Create an owner table.
                - Link the two tables together, adding new columns, values, and rows as needed.
                - Write a query to join these tables and give the result of owners and their pets.
                Show me the query, then the output as a table."""),
        }
        for example, tab in zip(examples.values(), st.tabs(list(examples.keys()))):
            tab.markdown(example)


def render_db_contents(engine: Engine, dbpath: str) -> None:
    inspector = inspect(engine)
    tables = [
        table
        for schema in inspector.get_schema_names()
        for table in inspector.get_table_names(schema=schema)
    ]

    if not tables:
        st.text("Database is empty")
        return

    with open(dbpath, "rb") as file:
        st.download_button("Download SQLite DB", data=file, file_name="demo.sqlite3")

    for table in tables:
        with engine.connect() as conn:
            df = pd.read_sql_table(table, conn)
            st.markdown(f"Table `{table}`")
            st.dataframe(df, hide_index=True, use_container_width=True)


def render_sidebar(checkpointer: InMemorySaver) -> None:
    options = {st.query_params.thread_id}
    options.update(
        {cp.config["configurable"]["thread_id"] for cp in checkpointer.list(None)}
    )

    def on_change() -> None:
        st.query_params.thread_id = st.session_state.pick_session

    st.session_state.pick_session = st.query_params.thread_id
    st.selectbox(
        "Choose a session",
        options=sorted(options),
        key="pick_session",
        on_change=on_change,
    )

    def on_create() -> None:
        st.query_params.thread_id = st.session_state.new_session_name
        st.session_state.new_session_name = None

    st.text_input(
        "Create new session",
        key="new_session_name",
        placeholder="Enter new session name",
        on_change=on_create,
    )

    st.link_button(
        "View in Google Cloud Trace",
        _trace_url(),
        icon=":material/account_tree:",
    )


def styles() -> None:
    st.html("""\
    <style>
        .stChatMessage { padding: 16px; }
        .stChatMessage .stLinkButton { text-align: right; }
    </style>
    """)


def render_message(message: BaseMessage, trace_id: str | None) -> None:
    # Filter out tool calls
    if message.type not in ("human", "ai"):
        return

    content = (
        message.content
        if isinstance(message.content, str)
        else message.content[-1]["text"]
    ).strip()

    # Response was probably blocked by a harm category, go check the trace for details
    if message.response_metadata.get("is_blocked", False):
        content = ":red[:material/error: Response blocked, try again]"

    if not content:
        return

    with st.chat_message(message.type):
        col1, col2 = st.columns([0.9, 0.1])
        col1.markdown(content)
        if trace_id:
            col2.link_button(
                "",
                _trace_url(trace_id),
                icon=":material/account_tree:",
                help="Open in Cloud Trace",
            )


def _trace_url(trace_id: str | None = None) -> str:
    url = f"https://console.cloud.google.com/traces/explorer;query=%7B%22plotType%22:%22HEATMAP%22,%22targetAxis%22:%22Y1%22,%22traceQuery%22:%7B%22resourceContainer%22:%22projects%2F{get_project_id()}%2Flocations%2Fglobal%2FtraceScopes%2F_Default%22,%22spanDataValue%22:%22SPAN_DURATION%22,%22spanFilters%22:%7B%22attributes%22:%5B%5D,%22displayNames%22:%5B%22chain%20invoke%22%5D,%22isRootSpan%22:true,%22kinds%22:%5B%5D,%22maxDuration%22:%22%22,%22minDuration%22:%22%22,%22services%22:%5B%5D,%22status%22:%5B%5D%7D%7D%7D;duration=PT30M"
    if not trace_id:
        return url
    return f"{url};traceId={trace_id}"
