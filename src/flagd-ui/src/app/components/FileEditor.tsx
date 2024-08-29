"use client";
import Ajv from "ajv";

import React, { useCallback, useEffect, useRef } from "react";
import { useState } from "react";

async function makeRequest(url: string) {
  try {
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    const data = await response.json();
    return data;
  } catch (error: any) {
    console.error("There was an error:", error.message);
    return null;
  }
}
const ajv = new Ajv();
let validate: any;

// @ts-ignore
function FileEditor({ setreloadData, flagConfig }) {
  const [schema, setSchema] = useState<[any, any][]>([]);
  useEffect(() => {
    async function loadSchema() {
      const schema1 = await makeRequest(
        "https://flagd.dev/schema/v0/flags.json"
      );
      const schema2 = await makeRequest(
        "https://flagd.dev/schema/v0/targeting.json"
      ); // if there are more in the future
      const schemas: [any, any][] = [schema1, schema2];
      setSchema(schemas);
      validate = ajv.addSchema(schemas[1]).compile(schemas[0]);
    }
    loadSchema();
  }, []);
  const textAreaRef = useRef(null);
  function attemptUpdate() {
    function parseJSON() {
      try {
        // @ts-ignore
        const data = JSON.parse(textAreaRef.current.value);
        return data;
      } catch (objError) {
        window.alert("Error parsing JSON");
        if (objError instanceof SyntaxError) {
          console.error(objError.name);
        } else {
          console.error(objError);
        }
        return null;
      }
    }
    const data = parseJSON();
    if (data === null) return;
    validate(data) ? sendUpdate(data) : window.alert("Schema check failed");
  }

  function sendUpdate(data: any) {
    fetch("/api/write-to-file", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ data }),
    })
      .then((response) => response.json())
      .then((data) => console.log(data))
      .then(() => setreloadData(true))
      .catch((error) => console.error(error));
    return;
  }
  // @ts-ignore
  const DynamicField = ({ flagConfig }) => {
    return (
      <textarea
        className="input_not_matched_case"
        cols={200}
        rows={40}
        ref={textAreaRef}
        defaultValue={JSON.stringify(flagConfig, null, 2)}
      ></textarea>
    );
  };
  return (
    <div className="feature-flag">
      <DynamicField flagConfig={flagConfig} />
      <button className="send-button" onClick={attemptUpdate}>
        Send
      </button>
    </div>
  );
}

export default FileEditor;
